use dot_graph::{Edge as DotEdge, Node as DotNode};

use crate::{node::Node, tableau::Tableau};

impl Tableau {
    pub(crate) fn add_graph_node(&mut self, node: &Node) {
        if let Some(graph) = &mut self.graph {
            let mut dot_node =
                DotNode::new(format!("Node{}", node.id).as_str()).label(format!("{node}").as_str());
            if node.implies.is_some() {
                dot_node = dot_node
                    .style(dot_graph::Style::Filled)
                    .color(Some("lightgray"));
            }
            graph.add_node(dot_node);
        }
    }

    pub(crate) fn add_graph_edge(&mut self, from: &Node, to: &Node) {
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
