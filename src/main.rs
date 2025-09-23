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
mod store;

use crate::formula::*;
use crate::node::*;
use crate::parser::*;
use crate::tableau::*;

const GRAPH_OUTPUT: bool = true;
const MEMOIZATION: bool = true;

fn main() {
    let example = "(G[0,100] (dist > 0.1)) && (G[0,20] ((dist < 6) -> (F[0,15] (acc2)))) && (F[12,20] ((dec2) -> (F[3,18] (acc2)))) && (F[4,40] ((dec2) U[10,20] ((|x| <= 0.5) && (|y| <= 0.5))))";
    let node = Node::from_operands(vec![parse_formula(example).unwrap().1]);
    let options = TableauOptions { max_depth: 10000, graph_output: GRAPH_OUTPUT, memoization: MEMOIZATION };
    let mut tableau = TableauData::new(options);
    let start = std::time::Instant::now();
    let res = tableau.make_tableau(node);
    let duration = start.elapsed();
    println!("Tableau result: {:?}", res);

    if GRAPH_OUTPUT && let Ok(graph) = tableau.graph.unwrap().to_dot_string() {
        fs::write("resources/tmp/g.dot", &graph).expect("Unable to write file");
    }

    println!("DURATION_SEC: {:.6}", duration.as_secs_f64());
}