use std::collections::VecDeque;
use std::iter;
use dot_graph::{Graph, Kind, Node as DotNode, Edge as DotEdge};
use nom::combinator::Opt;

use crate::{decompose::*, store};
use crate::node::Node;
use crate::solver::Solver;
use crate::store::{RejectedNode, Store};

pub struct TableauOptions {
    pub max_depth: usize,
    pub graph_output: bool,
    pub memoization: bool,
    pub simple_first: bool,
    pub formula_optimizations: bool,
    pub jump_rule_enabled: bool
}

impl Default for TableauOptions {
    fn default() -> Self {
        TableauOptions {
            max_depth: 1000,
            graph_output: true,
            memoization: true,
            simple_first: true,
            formula_optimizations: true,
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
        let mut result: Option<bool> = if (!local_solver.check(&node)) {
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
            let rejected_node: RejectedNode = RejectedNode::from_node(&child);

            let result = if child.current_time == node.current_time {
                self.add_children(child, local_solver, depth + 1)
            } else {
                self.add_children(child, &mut Solver::new(), depth + 1)
            };

            match result {
                Some(true) => {
                    if !implies_siblings {
                        return Some(true)
                    }
                },
                Some(false) => {
                    if let Some(store) = &mut self.store { 
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

#[cfg(test)]
mod tests {
    use super::*;
    use crate::parser::parse_formula;

    fn make_test(formula_str: &str, mltl: bool) -> Option<bool> {
        let (_, formula) = parse_formula(formula_str).unwrap();
        let mut node = Node::from_operands(vec![formula]);
        let options = TableauOptions {
            max_depth: 10000,
            graph_output: true,
            memoization: true,
            simple_first: true,
            formula_optimizations: true,
            jump_rule_enabled: true,
        };
        let mut tableau = TableauData::new(options);
        if !mltl {
            node.rewrite_u_r();
        }
        node.flatten();
        tableau.make_tableau(node)
    }

    #[test]
    fn test_and() {
        assert_eq!(make_test("a && b", false), Some(true));
    }

    #[test]
    fn test_many_ops() {
        assert_eq!(make_test("a && b && c && (a || b || c) && d", false), Some(true));
    }

    #[test]
    fn test_true() {
        assert_eq!(make_test("a && !TrUe", false), Some(false));
    }

    #[test]
    fn test_false() {
        assert_eq!(make_test("a && FaLsE", false), Some(false));
    }

    #[test]
    fn test_globally0() {
        assert_eq!(make_test("G[2,5] (R_x > 5 || R_x < 0)", false), Some(true));
    }

    #[test]
    fn test_globally_add() {
        assert_eq!(make_test("G[2,5] (R_x + R_y > 5 && R_x - R_y < 0)", false), Some(true));
    }

    #[test]
    fn test_globally_add_many() {
        assert_eq!(make_test("G[2,5] (R_x + R_y - R_z + R_x > 5 && R_x - R_y < 0)", false), Some(true));
    }

    #[test]
    fn test_release() {
        assert_eq!(make_test("(R_x == 10) R[1,6] (R_x < 10)", false), Some(true));
    }

    #[test]
    fn test_abs() {
        assert_eq!(make_test("G[0,5] (|x| > 20 || |x| < 10) && F[0,5] (x == -15)", false), Some(false));
    }

    #[test]
    fn test_mltl() {
        let formula = "F[58,92] ((a1) U[87,100] ((a1 && a0 && ! a1) U[9,100] (a0)))";
        assert_eq!(make_test(formula, false), Some(false));
        assert_eq!(make_test(formula, true), Some(true));
    }

    #[test]
    fn test_release_false() {
        assert_eq!(make_test("false R[0,10] a", false), Some(true));
    }

    #[test]
    fn test_gfgg() {
        assert_eq!(make_test("G[0,6] F[2,4] a && G[0,6] (a -> G[1,3] !a)", false), Some(false));
    }

    #[test]
    fn test_jump1_0() {
        assert_eq!(make_test("!a && G[10,20] !a && F[0,20] a", false), Some(true));
    }

    #[test]
    fn test_jump1_g() {
        assert_eq!(make_test("G[0,10] !a && F[5,20] a && G[15,25] !a", false), Some(true));
    }

    #[test]
    fn test_jump1_f() {
        assert_eq!(make_test("F[0,10] !a && G[0,9] a && F[10,20] a && G[15,20] !a", false), Some(true));
    }

    #[test]
    fn test_jump1_u() {
        assert_eq!(make_test("b U[0,10] !a && G[0,9] a && F[10,20] a && G[15,20] !a", false), Some(true));
    }

    #[test]
    fn test_g_is_derived() {
        assert_eq!(make_test("G[0,6]  (! (a0 U[2,10] (F[0,6] (! a0))))", true), Some(true));
    }

    #[test]
    fn test_u_parent() {
        assert_eq!(make_test("(G[0,89] F[88,100] a2 U[0,78] !a1) && a1", true), Some(true));
    }

}