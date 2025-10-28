use std::sync::atomic::AtomicUsize;

use dot_graph::{Graph, Kind, Node as DotNode};

use crate::{formula::Formula, node::Node};

pub static ID: AtomicUsize = AtomicUsize::new(0);

fn esc_label(s: &str) -> String {
    s.replace('\\', "\\\\").replace('"', "\\\"")
}

fn build_graph(formula: &Formula, graph: &mut Graph) -> usize {
    let label = match formula {
        Formula::Prop(_) | Formula::O(_) | Formula::Not(_) => {
            format!("{formula}")
        }
        Formula::And(_) => "&&".to_string(),
        Formula::Or(_) => "||".to_string(),
        Formula::Imply { .. } => "->".to_string(),
        Formula::G { interval, .. } => format!("G{interval}"),
        Formula::F { interval, .. } => format!("F{interval}"),
        Formula::U { interval, .. } => format!("U{interval}"),
        Formula::R { interval, .. } => format!("R{interval}"),
    };
    let id = ID.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
    let node = DotNode::new(&format!("n{id}")).label(&esc_label(&label));
    graph.add_node(node);

    match formula {
        Formula::And(ops) | Formula::Or(ops) => {
            for op in ops {
                let cid = build_graph(op, graph);
                let edge = dot_graph::Edge::new(&format!("n{id}"), &format!("n{cid}"), "");
                graph.add_edge(edge);
            }
        }
        Formula::Imply {
            left,
            right,
            not_left,
        } => {
            let lid = build_graph(left, graph);
            let rid = build_graph(right, graph);
            let nlid = build_graph(not_left, graph);
            graph.add_edge(dot_graph::Edge::new(
                &format!("n{id}"),
                &format!("n{lid}"),
                "",
            ));
            graph.add_edge(dot_graph::Edge::new(
                &format!("n{id}"),
                &format!("n{rid}"),
                "",
            ));
            graph.add_edge(dot_graph::Edge::new(
                &format!("n{id}"),
                &format!("n{nlid}"),
                "",
            ));
        }
        Formula::G { phi, .. } | Formula::F { phi, .. } => {
            let cid = build_graph(phi, graph);
            graph.add_edge(dot_graph::Edge::new(
                &format!("n{id}"),
                &format!("n{cid}"),
                "",
            ));
        }
        Formula::U { left, right, .. } | Formula::R { left, right, .. } => {
            let lid = build_graph(left, graph);
            let rid = build_graph(right, graph);
            graph.add_edge(dot_graph::Edge::new(
                &format!("n{id}"),
                &format!("n{lid}"),
                "",
            ));
            graph.add_edge(dot_graph::Edge::new(
                &format!("n{id}"),
                &format!("n{rid}"),
                "",
            ));
        }
        _ => {}
    }
    id
}

impl Node {
    pub fn id_tree(&self) {
        let mut graph = Graph::new("node_formulas", Kind::Digraph);
        for formula in &self.operands {
            build_graph(formula, &mut graph);
        }
        println!("{}", graph.to_dot_string().unwrap());
    }
}
