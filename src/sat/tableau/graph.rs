use dot_graph::{Edge as DotEdge, Node as DotNode};

use crate::sat::tableau::{
    Tableau,
    node::{Node, NodeFormula},
};

impl Tableau {
    fn fmt_operand(&self, nf: &NodeFormula) -> String {
        let mark = if nf.marked { "O" } else { "" };

        let parent_str = match nf.parent_id {
            Some(pid) => format!(" → ({})", pid),
            None => "".into(),
        };

        let op_str = format!("{}{}", mark, nf.kind);

        // final compact form:
        // (id) ->(pid) | operator
        format!("({}){} | {}", nf.id, parent_str, op_str)
    }

    fn fmt_node_label(&self, node: &Node) -> String {
        let mut s = String::new();

        s.push_str(&format!("Node {} | t = {}\n", node.id, node.current_time));
        s.push_str("----------------------------------------\n");
        for nf in &node.operands {
            s.push_str(&self.fmt_operand(nf));
            s.push('\n');
        }

        s
    }

    pub(crate) fn add_graph_node(&mut self, node: &Node) {
        let label = self.fmt_node_label(node);
        if let Some(graph) = &mut self.graph {
            let mut dot_node = DotNode::new(&format!("Node{}", node.id)).label(label.as_str()); // plain text label

            if node.implies.is_some() {
                dot_node = dot_node
                    .style(dot_graph::Style::Filled)
                    .color(Some("lightgray"));
            }

            graph.add_node(dot_node);
        }
    }

    fn add_graph_edge(&mut self, from: &Node, to: &Node) {
        if let Some(graph) = &mut self.graph {
            let edge = DotEdge::new(
                format!("Node{}", from.id).as_str(),
                format!("Node{}", to.id).as_str(),
                "",
            );
            graph.add_edge(edge);
        }
    }

    pub(crate) fn add_graph_children(&mut self, parent: &Node, children: &[Node]) {
        for child in children {
            self.add_graph_node(child);
            self.add_graph_edge(parent, child);
        }
    }
}
