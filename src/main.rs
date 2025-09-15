#![allow(unused)]
mod formula;
mod node;
mod decompose;
mod parser;

use crate::formula::*;
use crate::node::*;
use crate::parser::*;

fn test_decomposition_recursive(formula_str: &str) {
    println!("\nInput: {}", formula_str);
    match parse_formula(formula_str) {
        Ok((rem, f)) => {
            println!("Parsed formula: {} (remaining: '{}')", f, rem);
            let mut current_nodes = vec![Node::from_operands(vec![f])];
            let mut level = 0;

            while !current_nodes.is_empty() {
                println!("\n--- Decomposition Level {} ---", level);
                let mut next_nodes = Vec::new();

                for node in &current_nodes {
                    println!("Node: {}", node);
                    match node.decompose() {
                        Ok(parts) => {
                            println!("  Decomposed into {} part(s):", parts.len());
                            for (i, part) in parts.iter().enumerate() {
                                println!("    {}: {}", i + 1, part);
                                next_nodes.push(part.clone());
                            }
                        }
                        Err(e) => {
                            println!("  Cannot decompose further: {}", e);
                        }
                    }
                }

                current_nodes = next_nodes;
                level += 1;

                if current_nodes.is_empty() {
                    println!("\nFully decomposed at level {}.", level - 1);
                }
            }
        }
        Err(e) => println!("Parse error: {:?}", e),
    }
}

fn main() {
    println!("=== Recursive Decomposition Tests ===");

    let examples = vec![
        //"G[0,10] (a || b)",
        //"F[0,5] (a)",
        //"(G[0, 5] (a && b)) && c",
        "G[0,2] (F[0,2] (a))",  // Problematic: O inside G
    ];

    for s in examples {
        test_decomposition_recursive(s);
    }
}