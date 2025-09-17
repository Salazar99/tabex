#![allow(unused)]
use std::fs;
use std::time::Duration;
use std::time::Instant;

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
    let example = "a R[0, 5] b";
    let node = Node::from_operands(vec![parse_formula(example).unwrap().1]);
    let options = TableauOptions { max_depth: 10000, graph_output: true };
    let mut tableau = TableauData::new(options);
    let start = Instant::now();
    let res = tableau.make_tableau(node);
    let duration = start.elapsed();

    println!("Tableau result: {:?}", res);
    if let Ok(graph) = tableau.graph.unwrap().to_dot_string() {
        fs::write("g.dot", &graph).expect("Unable to write file");
    }

    println!("DURATION_SEC: {:.6}", duration.as_secs_f64());
}