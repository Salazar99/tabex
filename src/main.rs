use std::fs;

use stlcc::node::*;
use stlcc::parser::*;
use stlcc::tableau::*;
use stlcc::config::{get_tableau_options, ConfigSource};

fn main() {
    let (options, filename) = get_tableau_options(ConfigSource::Cli);
    let file_content = fs::read_to_string(&filename).unwrap();
    let example = file_content.lines().next().unwrap();
    let node = Node::from_operands(vec![parse_formula(example).unwrap().1]);
    
    let start = std::time::Instant::now();
    
    let mut tableau = Tableau::new(options);
    let res = tableau.make_tableau(node);
    
    let duration = start.elapsed();
    println!("Tableau result: {:?}", res);

    if tableau.options.graph_output && let Ok(graph) = tableau.graph.unwrap().to_dot_string() {
        println!("Node count: {:?}", NODE_ID);
        fs::write("resources/tmp/g.dot", &graph).expect("Unable to write file");
    }

    println!("DURATION_SEC: {:.6}", duration.as_secs_f64());
}