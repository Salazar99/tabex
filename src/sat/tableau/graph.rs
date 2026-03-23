use dot_graph::{Edge as DotEdge, Node as DotNode};

use crate::sat::tableau::{
    Tableau,
    node::{Node, NodeFormula},
};

impl Tableau {
    pub(crate) fn add_graph_node(&mut self, node: &Node) {
        if let Some(graph) = &mut self.graph {
            let label = node.fmt_node_label();
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

impl NodeFormula {
    fn fmt_operand(&self) -> String {
        let mark = if self.marked { "ZOK" } else { "" };

        let parent_str = match self.parent_id {
            Some(pid) => format!(" → ({})", pid),
            None => "".into(),
        };

        let op_str = format!("{}{}", mark, self.kind);

        // final compact form:
        // (id) ->(pid) | operator
        format!("({}){} | {}", self.id, parent_str, op_str)
    }
}

impl Node {
    fn fmt_node_label(&self) -> String {
        let mut s = String::new();

        s.push_str(&format!("Node {} | t = {}\n", self.id, self.current_time));
        s.push_str("----------------------------------------\n");
        for nf in &self.operands {
            s.push_str(&nf.fmt_operand());
            s.push('\n');
        }

        s
    }
}
