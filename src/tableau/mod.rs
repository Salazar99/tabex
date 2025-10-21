use std::cell::RefCell;
use std::collections::{VecDeque};
use std::rc::Rc;

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

#[derive(Clone, Copy, Debug, PartialEq)]
enum FrameResult {
    Sat,
    Unsat,
    Undefined
}

struct Frame {
    node: Node,
    children: VecDeque<Node>,
    depth: usize,
    solver: Rc<RefCell<Solver>>,
    result: Option<FrameResult>,
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

        let mut solver = Solver::new(self.options.unsat_core_extraction, self.options.mltl);
        solver.push();
        
        if !solver.check(&root) {
            return Some(false)
        }

        let children = match self.decompose(&root) {
            None => { return Some(true); }
            Some(c) => {
                for child in c.iter() {
                    self.add_graph_node(&child);
                    self.add_graph_edge(&root, &child);
                }
                c
            },
        };
        
        let mut stack = VecDeque::new();
        let mut any_undefined = false;
        stack.push_front(Frame { node: root, children: children.into(), depth: 0, solver: Rc::new(RefCell::new(solver)), result: None });

        while let Some(mut job) = stack.pop_front() {
            match job.children.pop_front() {
                None => {
                    if let Some(parent) = stack.front_mut() {
                        parent.solver.borrow_mut().pop();
                        match job.result {
                            Some(FrameResult::Sat) => {
                                if job.node.implies.is_none() {
                                    parent.result = Some(FrameResult::Sat);
                                    parent.children.drain(..);
                                }
                            }
                            Some(FrameResult::Unsat) => { 
                                parent.result = Some(FrameResult::Unsat);
                                if job.node.implies.is_some() {
                                    parent.children.drain(..);
                                }
                                if parent.node.current_time < job.node.current_time && let Some(store) = &mut self.store {
                                    let rejected_node = RejectedNode::from_node(&job.node);
                                    store.add_rejected(rejected_node);
                                }
                            }
                            Some(FrameResult::Undefined) => { 
                                parent.result = Some(FrameResult::Undefined);
                                any_undefined = true;
                            }
                            None => {
                                panic!()
                            }
                        }
                    } else {
                        return match job.result {
                            Some(FrameResult::Sat) => Some(true),
                            Some(FrameResult::Unsat) => {
                                if any_undefined { None } else { Some(false) }
                            }
                            Some(FrameResult::Undefined) => None,
                            None => panic!(),
                        };
                    }
                }
                Some(child ) => {
                    let implies = child.implies.is_some();

                    job.solver.borrow_mut().push();
                    let res = self.process_job(child, job.node.current_time, &mut job.solver, job.depth);

                    match res.0 {
                        Some(true) if !implies => {
                            job.children.drain(..);
                            job.result = Some(FrameResult::Sat);
                        }
                        None => {
                            job.result = Some(FrameResult::Undefined);
                            if res.1.is_none() {
                                any_undefined = true;
                            }
                        }
                        Some(false) => {
                            job.result = Some(FrameResult::Unsat);
                            if job.node.implies.is_some() {
                                job.children.drain(..);
                            }
                        }
                        _ => {}
                    }
                    
                    stack.push_front(job);
                    if let Some(new_job) = res.1 {
                        stack.push_front(new_job);
                    }
                }
            }
        }
        None
    }


    fn process_job(&mut self, node: Node, parent_time: i32, solver: &mut Rc<RefCell<Solver>>, depth: usize) -> (Option<bool>, Option<Frame>) {
        if depth >= self.options.max_depth {
            solver.borrow_mut().pop();
            return (None, None);
        }

        if !solver.borrow_mut().check(&node) {
            if let Some(core) = &mut self.unsat_core {
                if let Some(new_core) = solver.borrow_mut().extract_unsat_core() {
                    core.add_to_unsat_core(new_core);
                }
            }
            solver.borrow_mut().pop();
            return (Some(false), None);
        } 

        if let Some(store) = &mut self.store && parent_time < node.current_time {
            let rejected_node = RejectedNode::from_node(&node);
            if store.check_rejected(&rejected_node) {
                solver.borrow_mut().pop();
                return (Some(false), None);
            }
        }

        let new_nodes = self.decompose(&node);
        match new_nodes {
            None => {
                solver.borrow_mut().pop();
                return (Some(true), None)
            }
            Some(children) => {
                for child in children.iter() {
                    self.add_graph_node(&child);
                    self.add_graph_edge(&node, &child);
                }

                let solver_ref = if parent_time < node.current_time {
                    Rc::new(RefCell::new(solver.borrow().empty_solver())) 
                } else {
                    solver.clone()
                };

                let job = Frame {
                    node: node,
                    children: children.into(),
                    depth: depth + 1,
                    solver: solver_ref,
                    result: None,
                };
                return (None, Some(job))
            }
        }

    }

}