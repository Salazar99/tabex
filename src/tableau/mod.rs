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

    pub fn make_tableau_from_root(&mut self, mut root: Node) -> Option<bool> {
        // Normalization Stage
        root.negative_normal_form_rewrite();

        if !self.options.mltl {
            root.mltl_rewrite();
        }

        // Formula Optimization Stage
        if self.options.formula_simplifications {
            root.simplify();
        }

        root.flatten();

        if self.options.formula_optimizations {
            root.shift_bounds();
        }
        
        // Id Assignment Stage
        if let Some(core) = &mut self.unsat_core {
            core.initialize_root_node(&root);
        }

        // Solving Stage
        self.add_graph_node(&root);
        let mut local_solver = Solver::new(self.options.unsat_core_extraction, self.options.mltl);
        self.add_children(root, &mut local_solver, 0)
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

    fn add_children(&mut self, node: Node, local_solver: &mut Solver, depth: usize) -> Option<bool> {
        if depth >= self.options.max_depth {
            return None;
        }

        local_solver.push();
        let result: Option<bool> = if !local_solver.check(&node) {
            if let Some(core) = &mut self.unsat_core {
                if let Some(new_core) = local_solver.extract_unsat_core() {
                    core.add_to_unsat_core(new_core);
                }
            }
            Some(false)
        } else {
            let new_nodes = self.decompose(&node);
            if new_nodes.is_none() {
                return Some(true);
            } else {
                self.process_children(new_nodes.unwrap(), node, local_solver, depth)
            }
        };
        local_solver.pop();
        result
    }

    fn process_children(&mut self, children: Vec<Node>, node: Node, local_solver: &mut Solver, depth: usize) -> Option<bool> {
        for child in children.iter() {
            self.add_graph_node(&child);
            self.add_graph_edge(&node, &child);
        }
        
        let mut depth_reached = false;
        for child in children {
            let implies_siblings = child.implies.is_some();
            let child_time = child.current_time;
            let rejected_node = RejectedNode::from_node(&child);

            let result = if child.current_time == node.current_time {
                self.add_children(child, local_solver, depth + 1)
            } else {
                if let Some(store) = &self.store && store.check_rejected(&rejected_node) { 
                    Some(false) 
                } else {
                    self.add_children(child, &mut local_solver.empty_solver(), depth + 1)
                }
            };

            match result {
                Some(true) => {
                    if !implies_siblings {
                        return Some(true)
                    }
                },
                Some(false) => {
                    if child_time > node.current_time && let Some(store) = &mut self.store { 
                        store.add_rejected(rejected_node)
                    }
                    if implies_siblings { return Some(false) }
                },
                None => depth_reached = true,
            }
        }

        if depth_reached {
            return None;
        }
        return Some(false)
    }
}