#![allow(unused)]
mod formula;
mod node;
mod decompose;

use crate::formula::*;
use crate::node::*;

fn main() {
    // Scenario 1: Simple G with O
    let phi1 = Formula::G { lower: 0, upper: 5, phi: Box::new(Formula::Prop(Expr::Atom("p".to_string()))) };
    let node1 = Node::from_operands(vec![Formula::O(Box::new(phi1))]);
    println!("Original: {}", node1);
    match node1.decompose() {
        Ok(nodes) => println!("Decomposed: {:?}", nodes),
        Err(e) => println!("Error: {}", e),
    }

    // Scenario 2: F with jump
    let phi2 = Formula::F { lower: 1, upper: 3, phi: Box::new(Formula::Prop(Expr::Atom("q".to_string()))) };
    let node2 = Node::from_operands(vec![phi2]);
    println!("\nOriginal: {}", node2);
    match node2.decompose() {
        Ok(nodes) => println!("Decomposed: {:?}", nodes),
        Err(e) => println!("Error: {}", e),
    }

    // Scenario 3: And with O and G
    let phi3 = Formula::G { lower: 2, upper: 4, phi: Box::new(Formula::Prop(Expr::Atom("r".to_string()))) };
    let node3 = Node::from_operands(vec![Formula::O(Box::new(phi3)), Formula::Prop(Expr::Atom("s".to_string()))]);
    println!("\nOriginal: {}", node3);
    match node3.decompose() {
        Ok(nodes) => println!("Decomposed: {:?}", nodes),
        Err(e) => println!("Error: {}", e),
    }
}
