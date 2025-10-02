use dot_graph::{Graph, Kind, Node as DotNode, Edge as DotEdge};

use crate::node::Node;
use crate::solver::Solver;
use crate::store::{RejectedNode, Store};

#[cfg(test)]
mod tests;

pub struct TableauOptions {
    pub max_depth: usize,
    pub graph_output: bool,
    pub memoization: bool,
    pub simple_first: bool,
    pub formula_optimizations: bool,
    pub jump_rule_enabled: bool,
    pub mltl: bool
}

impl Default for TableauOptions {
    fn default() -> Self {
        TableauOptions {
            max_depth: 1000,
            graph_output: true,
            memoization: true,
            simple_first: true,
            formula_optimizations: true,
            jump_rule_enabled: true,
            mltl: false
        }
    }
}

pub struct TableauData {
    pub options: TableauOptions,
    pub graph: Option<Graph>,
    pub store: Option<Store>,
}

impl TableauData {

    pub fn new(options: TableauOptions) -> Self {
        let graph = if options.graph_output { Some(Graph::new("Tableau", Kind::Graph)) } else { None };
        let store = if options.memoization { Some(Store::new()) } else { None };
        TableauData {
            options,
            graph,
            store
        }
    }

    pub fn make_tableau(&mut self, mut root: Node) -> Option<bool> {
        if !self.options.mltl {
            root.rewrite_u_r();
        }
        root.push_negation();
        if self.options.formula_optimizations {
            root.shift_bounds();
        }
        root.flatten();
        
        self.add_graph_node(&root);

        let mut local_solver = Solver::new();
        self.add_children(root, &mut local_solver, 0)
    }

    fn add_children(&mut self, node: Node, local_solver: &mut Solver, depth: usize) -> Option<bool> {
        if depth >= self.options.max_depth {
            println!("Max depth reached!");
            return None;
        }

        local_solver.push();
        let result: Option<bool> = if !local_solver.check(&node) {
            Some(false)
        } else {
            let new_nodes = self.decompose(&node);
            if new_nodes.is_empty() {
                return Some(true);
            }
            self.process_children(new_nodes, node, local_solver, depth)
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
            let implies_siblings = child.implies_siblings;
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

    fn add_graph_node(&mut self, node: &Node) {
        if let Some(graph) = &mut self.graph {
            let mut dot_node = DotNode::new(format!("Node{}", node.id).as_str()).label(format!("{}", node.to_string()).as_str());
            if node.implies_siblings {
                dot_node = dot_node.style(dot_graph::Style::Filled).color(Some("lightgray"));
            }
            graph.add_node(dot_node);
        }
    }

    fn add_graph_edge(&mut self, from: &Node, to: &Node) {
        if let Some(graph) = &mut self.graph {
            let edge = DotEdge::new(
                format!("Node{}", from.id).as_str(),
                format!("Node{}", to.id).as_str(),
                ""
            );
            graph.add_edge(edge);
        }
    }
}