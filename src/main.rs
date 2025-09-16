#![allow(unused)]
mod formula;
mod node;
mod decompose;
mod parser;
mod tableau;
mod solver;

use crate::formula::*;
use crate::node::*;
use crate::parser::*;
use crate::tableau::*;

fn main() {
    let example = "G[0,5] a";
    let node = Node::from_operands(vec![parse_formula(example).unwrap().1]);
    let options = TableauOptions { max_depth: 10000, graph_output: true };
    let mut tableau = TableauData::new(options);
    let res = tableau.make_tableau(node);
    println!("Tableau result: {:?}", res);
    if let Ok(graph) = tableau.graph.unwrap().to_dot_string() {
        println!("DOT representation:\n{}", graph);
    }
}