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
mod rewrite;

use crate::formula::*;
use crate::node::*;
use crate::parser::*;
use crate::rewrite::rewrite_chain;
use crate::tableau::*;

const GRAPH_OUTPUT: bool = true;
const MEMOIZATION: bool = true;
const SIMPLE_FIRST: bool = true;
const FORMULA_OPTIMIZATIONS: bool = true;
const JUMP_RULE_ENALED: bool = true;

fn main() {
    let example = "G[0, 4] (F[0, 3] a)";
    let mut node = Node::from_operands(vec![parse_formula(example).unwrap().1]);
    let options = TableauOptions { 
        max_depth: 100, 
        graph_output: GRAPH_OUTPUT, 
        memoization: MEMOIZATION, 
        simple_first: SIMPLE_FIRST, 
        formula_optimizations: FORMULA_OPTIMIZATIONS,
        jump_rule_enabled: JUMP_RULE_ENALED 
    };
    let mut tableau = TableauData::new(options);
    let start = std::time::Instant::now();
    node.flatten();
    let res = tableau.make_tableau(node);
    let duration = start.elapsed();
    println!("Tableau result: {:?}", res);

    if GRAPH_OUTPUT && let Ok(graph) = tableau.graph.unwrap().to_dot_string() {
        fs::write("resources/tmp/g.dot", &graph).expect("Unable to write file");
    }

    println!("DURATION_SEC: {:.6}", duration.as_secs_f64());
}