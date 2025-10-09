use std::collections::HashSet;
use std::sync::atomic::{AtomicUsize, Ordering};

use dot_graph::{Graph, Kind, Node as DotNode, Edge as DotEdge};

use crate::formula::{Formula, FormulaKind};
use crate::node::Node;
use crate::parser::parse_formula;
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
            graph_output: false,
            memoization: true,
            simple_first: true,
            formula_optimizations: true,
            jump_rule_enabled: true,
            mltl: false
        }
    }
}

pub struct Tableau {
    pub options: TableauOptions,
    pub graph: Option<Graph>,
    pub store: Option<Store>,
}

impl Tableau {

    pub fn new(options: TableauOptions) -> Self {
        let graph = if options.graph_output { Some(Graph::new("Tableau", Kind::Graph)) } else { None };
        let store = if options.memoization { Some(Store::new()) } else { None };
        Tableau {
            options,
            graph,
            store
        }
    }

    pub fn make_tableau(&mut self, formula: &str) -> Option<bool> {
        // Parsing Stage
        let mut root = Node::from_operands(vec![parse_formula(formula).unwrap().1]);
        
        // Normalization Stage
        root.negative_normal_form_rewrite();
        root.flatten();
        if !self.options.mltl {
            root.mltl_rewrite();
        }
        
        // Id Assignment Stage
        for formula in root.operands.iter_mut() {
            formula.assign_ids();
        }

        // Formula Optimization Stage
        if self.options.formula_optimizations {
            root.shift_bounds();
        }

        // Solving Stage
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

pub static FORMULA_ID: AtomicUsize = AtomicUsize::new(0);

impl Formula {
    pub fn assign_ids(&mut self) {
        if self.id.is_none() {
            self.id = Some(FORMULA_ID.fetch_add(1, Ordering::Relaxed));
        }
        match &mut self.kind {
            FormulaKind::And(ops) | FormulaKind::Or(ops) => {
                for op in ops {
                    op.assign_ids();
                }
            }
            FormulaKind::Imply { left, right, not_left } => {
                left.assign_ids();
                right.assign_ids();
                not_left.assign_ids();
            }
            FormulaKind::G { phi, .. } | FormulaKind::F { phi, .. } => {
                phi.assign_ids();
            }
            FormulaKind::U { left, right, .. } | FormulaKind::R { left, right, .. } => {
                left.assign_ids();
                right.assign_ids();
            }
            _ => {}
        }
    }

    pub fn id_tree(&self) {
        if self.id.is_none() {
            panic!("Formula ids not assigned. Call assign_ids() on a mutable formula before generating the .dot graph.");
        }

        let mut graph = Graph::new("formula", Kind::Digraph);
        let mut visited: HashSet<usize> = HashSet::new();

        fn esc_label(s: &str) -> String {
            s.replace('\\', "\\\\").replace('"', "\\\"")
        }

        fn walk(f: &Formula, graph: &mut Graph, visited: &mut HashSet<usize>) {
            let id = f.id.expect("missing id");
            if !visited.insert(id) {
                return;
            }

            let label = match &f.kind {
                FormulaKind::Prop(_) | FormulaKind::True | FormulaKind::False | FormulaKind::Not(_) | FormulaKind::O(_) => {
                    // leaf: show the whole formula
                    format!("{}: {}", id, f)
                }
                // internal: show only the operator
                FormulaKind::And(_) => format!("{}: &&", id),
                FormulaKind::Or(_) => format!("{}: ||", id),
                FormulaKind::Imply { .. } => format!("{}: ->", id),
                FormulaKind::G { interval, .. } => format!("{}: G{}", id, interval ),
                FormulaKind::F { interval, .. } => format!("{}: F{}", id, interval),
                FormulaKind::U { interval, .. } => format!("{}: U{}", id, interval),
                FormulaKind::R { interval, .. } => format!("{}: R{}", id, interval),
            };
            let node = DotNode::new(&format!("n{}", id)).label(&esc_label(&label));
            graph.add_node(node);

            match &f.kind {
                FormulaKind::And(ops) | FormulaKind::Or(ops) => {
                    for op in ops {
                        let cid = op.id.expect("child missing id");
                        let edge = DotEdge::new(&format!("n{}", id), &format!("n{}", cid), "");
                        graph.add_edge(edge);
                        walk(op, graph, visited);
                    }
                }
                FormulaKind::Imply { left, right, not_left } => {
                    let lid = left.id.expect("child missing id");
                    let rid = right.id.expect("child missing id");
                    let nid = not_left.id.expect("child missing id");
                    graph.add_edge(DotEdge::new(&format!("n{}", id), &format!("n{}", lid), ""));
                    graph.add_edge(DotEdge::new(&format!("n{}", id), &format!("n{}", rid), ""));
                    graph.add_edge(DotEdge::new(&format!("n{}", id), &format!("n{}", nid), ""));
                    walk(left, graph, visited);
                    walk(right, graph, visited);
                    walk(not_left, graph, visited);
                }
                FormulaKind::G { phi, .. } | FormulaKind::F { phi, .. } => {
                    let cid = phi.id.expect("child missing id");
                    graph.add_edge(DotEdge::new(&format!("n{}", id), &format!("n{}", cid), ""));
                    walk(phi, graph, visited);
                }
                FormulaKind::U { left, right, .. } | FormulaKind::R { left, right, .. } => {
                    let lid = left.id.expect("child missing id");
                    let rid = right.id.expect("child missing id");
                    graph.add_edge(DotEdge::new(&format!("n{}", id), &format!("n{}", lid), ""));
                    graph.add_edge(DotEdge::new(&format!("n{}", id), &format!("n{}", rid), ""));
                    walk(left, graph, visited);
                    walk(right, graph, visited);
                }
                _ => {}
            }
        }

        walk(self, &mut graph, &mut visited);

        println!("{}", graph.to_dot_string().unwrap());
    }
}