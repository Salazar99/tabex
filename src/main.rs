use std::fs;

use stlcc::node::*;
use stlcc::parser::*;
use stlcc::tableau::*;

const MLTL: bool = false;

const GRAPH_OUTPUT: bool = false;
const MEMOIZATION: bool = true;
const SIMPLE_FIRST: bool = true;
const FORMULA_OPTIMIZATIONS: bool = true;
const JUMP_RULE_ENALED: bool = true;

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let filename = args.get(1).expect("Please provide the formula filename as the first argument.");
    let file_content = fs::read_to_string(filename).unwrap();
    let example = file_content.lines().next().unwrap();
    let node = Node::from_operands(vec![parse_formula(example).unwrap().1]);
    
    let options = TableauOptions { 
        max_depth: 10000000, 
        graph_output: GRAPH_OUTPUT, 
        memoization: MEMOIZATION, 
        simple_first: SIMPLE_FIRST, 
        formula_optimizations: FORMULA_OPTIMIZATIONS,
        jump_rule_enabled: JUMP_RULE_ENALED,
        mltl: MLTL
    };

    let start = std::time::Instant::now();
    
    let mut tableau = TableauData::new(options);
    let res = tableau.make_tableau(node);
    
    let duration = start.elapsed();
    println!("Tableau result: {:?}", res);

    if GRAPH_OUTPUT && let Ok(graph) = tableau.graph.unwrap().to_dot_string() {
        fs::write("resources/tmp/g.dot", &graph).expect("Unable to write file");
    }

    println!("DURATION_SEC: {:.6}", duration.as_secs_f64());
}