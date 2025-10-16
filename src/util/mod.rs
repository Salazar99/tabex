use std::{collections::HashSet, sync::atomic::AtomicUsize};

use dot_graph::{Graph, Kind, Node as DotNode};

use crate::{formula::Formula};

pub static ID: AtomicUsize = AtomicUsize::new(0);

impl Formula {
    
    pub fn id_tree(&self) {
        let mut graph = Graph::new("formula", Kind::Digraph);
        let mut visited: HashSet<usize> = HashSet::new();

        fn esc_label(s: &str) -> String {
            s.replace('\\', "\\\\").replace('"', "\\\"")
        }

        fn walk(f: &Formula, graph: &mut Graph, visited: &mut HashSet<usize>) -> usize {
            let label = match &f {
                Formula::Prop(_) | Formula::O(_) | Formula::Not(_) => {
                    // leaf: show the whole formula
                    format!("{}", f)
                }
                // internal: show only the operator
                Formula::And(_) => format!("&&"),
                Formula::Or(_) => format!("||"),
                Formula::Imply { .. } => format!("->"),
                Formula::G { interval, .. } => format!("G{}", interval ),
                Formula::F { interval, .. } => format!("F{}", interval),
                Formula::U { interval, .. } => format!("U{}", interval),
                Formula::R { interval, .. } => format!("R{}", interval),
            };
            let id = ID.fetch_add(1, std::sync::atomic::Ordering::Relaxed);
            let node = DotNode::new(&format!("n{}", id)).label(&esc_label(&label));
            graph.add_node(node);

            match &f {
                Formula::And(ops) | Formula::Or(ops) => {
                    for op in ops {
                        let cid = walk(op, graph, visited);
                        let edge = dot_graph::Edge::new(&format!("n{}", id), &format!("n{}", cid), "");
                        graph.add_edge(edge);
                    }
                }
                Formula::Imply { left, right, not_left } => {
                    let lid = walk(left, graph, visited);
                    let rid = walk(right, graph, visited);
                    let nlid = walk(not_left, graph, visited);
                    graph.add_edge(dot_graph::Edge::new(&format!("n{}", id), &format!("n{}", lid), ""));
                    graph.add_edge(dot_graph::Edge::new(&format!("n{}", id), &format!("n{}", rid), ""));
                    graph.add_edge(dot_graph::Edge::new(&format!("n{}", id), &format!("n{}", nlid), ""));
                }
                Formula::G { phi, .. } | Formula::F { phi, .. } => {
                    let cid = walk(phi, graph, visited);
                    graph.add_edge(dot_graph::Edge::new(&format!("n{}", id), &format!("n{}", cid), ""));
                }
                Formula::U { left, right, .. } | Formula::R { left, right, .. } => {
                    let lid = walk(left, graph, visited);
                    let rid = walk(right, graph, visited);
                    graph.add_edge(dot_graph::Edge::new(&format!("n{}", id), &format!("n{}", lid), ""));
                    graph.add_edge(dot_graph::Edge::new(&format!("n{}", id), &format!("n{}", rid), ""));
                }
                _ => {}
            }
            id
        }

        walk(self, &mut graph, &mut visited);

        println!("{}", graph.to_dot_string().unwrap());
    }

}