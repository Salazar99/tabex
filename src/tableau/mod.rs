use std::collections::{HashSet, VecDeque};

use dot_graph::{Graph, Kind};

use crate::node::Node;
use crate::formula::parser::parse_formula;
use crate::tableau::core::UnsatCore;
use crate::tableau::solver::Solver;
use crate::tableau::store::{RejectedNode, Store};
use crate::tableau::config::TableauOptions;

#[cfg(test)]
mod tests;

pub mod config;
pub mod solver;
pub mod store;
pub mod core;
pub mod graph;

pub struct Tableau {
    pub options: TableauOptions,
    pub graph: Option<Graph>,
    pub store: Option<Store>,
    pub unsat_core: Option<UnsatCore>
}

struct Job {
    node: Node,
    depth: usize,
    father_time: Option<i32>,
    solver: Solver
}

struct SimpleFirstPool {
    expandable: HashSet<usize>,
    implied: HashSet<usize>
}

impl SimpleFirstPool {
    fn from_implied(id: usize, implied: Vec<usize>) -> Self {
        SimpleFirstPool { expandable: HashSet::from_iter(vec![id]), implied: implied.into_iter().collect()}
    }

    fn pop(&mut self, id: usize) -> Option<HashSet<usize>> {
        self.expandable.remove(&id);
        if self.expandable.is_empty() {
            Some(self.implied.clone())
        } else {
            None
        }
    }

    fn contains(&self, id: usize) -> bool {
        self.expandable.contains(&id)
    }
}

struct Worker {
    stack: VecDeque<Job>,
    pools: Vec<SimpleFirstPool>,
    excluded_nodes: HashSet<usize>
}

impl Worker {
    fn pop_true(&mut self, id: usize) -> bool {
        let mut to_remove = vec![];
        for (i, pool) in self.pools.iter_mut().enumerate() {
            if pool.contains(id) {
                to_remove.push(i);
            }
        }

        if to_remove.is_empty() {
            return false;
        }

        for i in to_remove.into_iter().rev() {
            self.pools[i].pop(id);
            if self.pools[i].expandable.is_empty() {
                self.pools.remove(i);
            }
        }
        return true;
    }

    fn pop_false(&mut self, id: usize) -> Option<Vec<HashSet<usize>>>{
        let mut to_remove = vec![];
        let mut res = vec![];
        for (i, pool) in self.pools.iter_mut().enumerate() {
            if pool.contains(id) {
                if let Some(implied) = pool.pop(id) {
                    res.push(implied);
                    to_remove.push(i);
                }
            }
        }

        if to_remove.is_empty() {
            return None;
        }
        for i in to_remove.into_iter().rev() {
            self.pools.remove(i);
        }
        Some(res)
    }

    fn remove_id_from_pools(&mut self, id: usize) {
        for pool in self.pools.iter_mut() {
            pool.expandable.remove(&id);
        }
    }

    fn new_pool(&mut self, id: usize, implies: Option<Vec<usize>>) {
        if let Some(implied) = implies {
            self.pools.push(SimpleFirstPool::from_implied(id, implied));
        }
    }

    fn get_pool(&mut self, id: usize) -> Option<&mut SimpleFirstPool> {
        for pool in self.pools.iter_mut() {
            if pool.contains(id) {
                return Some(pool);
            }
        }
        None
    }
}

impl Tableau {
    pub fn new(options: TableauOptions) -> Self {
        let graph = if options.graph_output { Some(Graph::new("Tableau", Kind::Graph)) } else { None };
        let store = if options.memoization { Some(Store::new()) } else { None };
        let unsat_core = if options.unsat_core_extraction { Some(UnsatCore::new()) } else { None };
        Tableau {
            options,
            graph,
            store,
            unsat_core
        }
    }

    pub fn make_tableau_from_str(&mut self, formula: &str) -> Option<bool> {
        // Parsing Stage
        let root = {
            let parsed = parse_formula(formula);
            let formula_ast = match parsed {
                Ok((_, f)) => f,
                Err(err) => {
                    eprintln!("Failed to parse formula '{}': {:?}", formula, err);
                    panic!("{}", formula);
                }
            };
            Node::from_operands(vec![formula_ast])
        };

        self.make_tableau_from_root(root)
    }

    pub fn make_tableau_from_root(&mut self, mut root: Node) -> Option<bool> {
        // Normalization Stage
        root.negative_normal_form_rewrite();
        root.flatten();
        
        if !self.options.mltl {
            root.mltl_rewrite();
        }

        // Formula Optimization Stage
        if self.options.formula_optimizations {
            root.shift_bounds();
        }
        
        // Id Assignment Stage
        if let Some(core) = &mut self.unsat_core {
            core.initialize_root_node(&root);
        }

        // Solving Stage
        self.add_graph_node(&root);

        let mut worker = Worker {
            stack: VecDeque::new(),
            pools: Vec::new(),
            excluded_nodes: HashSet::new()
        };

        let solver = Solver::new(self.options.unsat_core_extraction, self.options.mltl);
        worker.stack.push_front(Job { node: root, depth: 0, father_time: None, solver: solver });

        while let Some(job) = worker.stack.pop_front() {
            let father_time = job.father_time;
            let node_time = job.node.current_time;
            let node_id = job.node.id;
            let rejected_node = RejectedNode::from_node(&job.node);

            worker.new_pool(node_id, job.node.implies.clone());
            match self.process_job(job, &mut worker) {
                Some(true) => {
                    if !worker.pop_true(node_id) {
                        return Some(true)
                    }
                },
                Some(false) => {
                    if let (Some(father_time), Some(store)) = (father_time, &mut self.store) && node_time > father_time {
                        store.add_rejected(rejected_node);
                    }
                    if let Some(to_exclude) = worker.pop_false(node_id) {
                        for v in to_exclude {
                            worker.excluded_nodes.extend(v);
                        }
                    }
                },
                None => {},
            }
        }

        Some(false)
    }

    fn process_job(&mut self, job: Job, worker: &mut Worker) -> Option<bool> {
        let Job { node, depth, father_time, mut solver } = job;

        if worker.excluded_nodes.remove(&node.id) {
            return Some(false);
        }

        if !solver.check(&node) {
            if let Some(core) = &mut self.unsat_core {
                if let Some(new_core) = solver.extract_unsat_core() {
                    core.add_to_unsat_core(new_core);
                }
            }
            return Some(false);
        } 

        if let (Some(father_time), Some(store)) = (father_time, &mut self.store) && father_time < node.current_time {
            let rejected_node = RejectedNode::from_node(&node);
            if store.check_rejected(&rejected_node) {
                return Some(false);
            }
        }

        let new_nodes = self.decompose(&node);
        match new_nodes {
            None => return Some(true),
            Some(mut children) => {
                for child in children.iter() {
                    self.add_graph_node(&child);
                    self.add_graph_edge(&node, &child);
                }

                children.reverse();
                for child in children {
                    let child_id = child.id;

                    let new_job = if depth >= self.options.max_depth {
                        None
                    } else if child.current_time == node.current_time {
                        Some(Job { node: child, depth: depth + 1, father_time: Some(node.current_time), solver: solver.clone() })
                    } else {
                        Some(Job { node: child, depth: depth + 1, father_time: Some(node.current_time), solver: solver.empty_solver() })
                    };

                    match new_job {
                        Some(job) => {
                            worker.stack.push_front(job);
                            match worker.get_pool(node.id) {
                                Some(pool) => {
                                    pool.expandable.insert(child_id);
                                },
                                None => {}
                            }
                        },
                        _ => {}
                    }
                }
                worker.remove_id_from_pools(node.id);
            }
        }
        None
    }

}