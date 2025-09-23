use std::collections::VecDeque;
use dot_graph::{Graph, Kind, Node as DotNode, Edge as DotEdge};
use nom::combinator::Opt;

use crate::decompose::*;
use crate::node::Node;
use crate::solver::Solver;
use crate::store::Store;

pub struct TableauOptions {
    pub max_depth: usize,
    pub graph_output: bool,
    pub memoization: bool,
    pub simple_first: bool,
    pub jump_rule_enabled: bool
}

impl Default for TableauOptions {
    fn default() -> Self {
        TableauOptions {
            max_depth: 1000,
            graph_output: true,
            memoization: true,
            simple_first: true,
            jump_rule_enabled: true
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
        root.current_time = 0;

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
        if (!local_solver.check(&node)) {
            return Some(false);
        }
        let res = node.decompose();
        let result = self.process_children(res, node, local_solver, depth);
        local_solver.pop();
        result
    }

    fn process_children(&mut self, children: Vec<Node>, node: Node, local_solver: &mut Solver, depth: usize) -> Option<bool> {
        let mut depth_reached = false;

        for child in children.iter() {
            self.add_graph_node(&child);
            self.add_graph_edge(&node, &child);
        }

        for child in children {
            let result = if child.current_time == node.current_time {
                self.add_children(child, local_solver, depth + 1)
            } else {
                self.add_children(child, &mut Solver::new(), depth + 1)
            };

            match result {
                Some(true) => return Some(true),
                Some(false) => (),
                None => depth_reached = true,
            }
        }

        if depth_reached {
            return None;
        }
        return Some(true)
    }

    fn add_graph_node(&mut self, node: &Node) {
        if let Some(graph) = &mut self.graph {
            let dot_node = DotNode::new(format!("Node{}", node.id).as_str()).label(format!("{}", node.to_string()).as_str());
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