#![allow(unused)]
mod formula;
mod node;
mod decompose;
mod parser;

use crate::formula::*;
use crate::node::*;
use crate::parser::*;

fn main() {
	println!("=== Decomposition tests ===");

	let examples = vec![
		"G[0,10] (a || b)",
		"F[0,5] (a)",
	];

	for s in examples {
		println!("\nInput: {}", s);
		match parse_formula(s) {
			Ok((rem, f)) => {
                println!(" Parsed formula: {} (remaining: '{}')", f, rem);
				let node = Node::from_operands(vec![f.clone()]);
				match node.decompose() {
					Ok(parts) => {
						println!(" Decomposed into {} node(s):", parts.len());
						for p in parts { println!("  - {}", p); }
					}
					Err(e) => println!(" Decompose error: {}", e),
				}
			}
			Err(e) => println!(" Parse error: {:?}", e),
		}
	}
}
