use std::sync::Arc;

use crate::{formula::{Expr, Formula, Interval}, node::Node, tableau::{Tableau, config::TableauOptions}};

fn prop(name: &str) -> Formula {
    Formula::prop(Expr::bool(Arc::from(name)))
}

fn tableau_data_gen(options: Option<TableauOptions>) -> Tableau {
    Tableau::new(
        if let Some(tops) = options {
            tops
        } else {
            TableauOptions { graph_output: false, ..Default::default() }
        }
    )
}

fn decompose_jump_opt() -> TableauOptions {
    TableauOptions { jump_rule_enabled: true, graph_output: false, simple_first: false, ..Default::default() }
}

fn make_test_decompose(input: Vec<Formula>, expected: Vec<Node>, options: Option<TableauOptions>) {
    let node = Node::from_operands(input);
    let tableau_data = tableau_data_gen(options);
    let decomposed = tableau_data.decompose(&node).unwrap();
    let decomposed_operands = decomposed.iter().map(|n| n.operands.clone()).collect::<Vec<Vec<Formula>>>();
    let expected_operands = expected.iter().map(|n| n.operands.clone()).collect::<Vec<Vec<Formula>>>();
    assert_eq!(decomposed_operands, expected_operands);
}

#[test]
fn test_and() {
    let a = prop("a");
    let b = prop("b");
    let expected: Node = Node::from_operands(vec![
        a.clone(),
        b.clone()
    ]);
    make_test_decompose(vec![Formula::and(vec![a, b])], vec![expected], None);
}

#[test]
fn test_or() {
    let a = prop("a");
    let b = prop("b");
    let expected1: Node = Node::from_operands(vec![
        a.clone()
    ]);
    let expected2: Node = Node::from_operands(vec![
        b.clone()
    ]);
    make_test_decompose(vec![Formula::or(vec![a, b])], vec![expected1, expected2], None);
}

#[test]
fn test_imply() {
    let a = prop("a");
    let b = prop("b");
    let imply = Formula::imply(a.clone(), b.clone());
    let Formula::Imply { not_left, .. } = imply.clone() else {
        panic!()
    };
    let expected1: Node = Node::from_operands(vec![
        *not_left.clone()
    ]);
    let expected_optimization: Node = Node::from_operands(vec![
        a.clone(),
        b.clone()
    ]);
    let expected_non_optimization: Node = Node::from_operands(vec![
        b.clone()
    ]);
    make_test_decompose(vec![imply.clone()], vec![expected1.clone(), expected_optimization], None);
    make_test_decompose(vec![imply], vec![expected1, expected_non_optimization], Some(TableauOptions { formula_optimizations: false, ..Default::default() }));
}

#[test]
fn test_globally() {
    let a = prop("a");
    let expected1: Node = Node::from_operands(vec![
        Formula::o(Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone())),
        a.clone(),
    ]);
    make_test_decompose(vec![Formula::g(Interval { lower: 0, upper: 5 }, None, a)], vec![expected1], None);
}

#[test]
fn test_finally() {
    let a = prop("a");
    let expected1: Node = Node::from_operands(vec![
        a.clone(),
    ]);
    let expected2: Node = Node::from_operands(vec![
        Formula::o(Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone()))
    ]);
    make_test_decompose(vec![Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone())], vec![expected1, expected2], None);
}

#[test]
fn test_finally_end() {
    let a = prop("a");
    let expected1: Node = Node::from_operands(vec![
        a.clone(),
    ]);
    make_test_decompose(vec![Formula::f(Interval { lower: 0, upper: 0 }, None, a.clone())], vec![expected1], None);
}

#[test] 
fn test_gf(){
    let a = prop("a");
    
    let expected1: Node = Node::from_operands(vec![
        Formula::o(Formula::g(Interval { lower: 0, upper: 5 }, None, Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone()))),
        Formula::f(Interval { lower: 0, upper: 5 }, Some(5), a.clone()),
    ]);
    let options = TableauOptions { formula_optimizations: false, ..Default::default() };
    make_test_decompose(vec![Formula::g(Interval { lower: 0, upper: 5 }, None, Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone()))], vec![expected1], Some(options));
}

#[test]
fn test_until() {
    let a = prop("a");
    let b = prop("b");
    let expected1: Node = Node::from_operands(vec![
        b.clone(),
    ]);
    let expected2: Node = Node::from_operands(vec![
        a.clone(),
        Formula::o(Formula::u(Interval { lower: 0, upper: 5 }, None, a.clone(), b.clone()))
    ]);
    make_test_decompose(vec![Formula::u(Interval { lower: 0, upper: 5 }, None, a.clone(), b.clone())], vec![expected1, expected2], None);
}

#[test]
fn test_until_end() {
    let a = prop("a");
    let b = prop("b");
    
    let expected1: Node = Node::from_operands(vec![
        b.clone()
    ]);
    make_test_decompose(vec![Formula::u(Interval { lower: 0, upper: 0 }, None, a.clone(), b.clone())], vec![expected1], None);
}

#[test]
fn test_release() {
    let a = prop("a");
    let b = prop("b");
    let expected1: Node = Node::from_operands(vec![
        a.clone(),
        b.clone()
    ]);
    let expected2: Node = Node::from_operands(vec![
        b.clone(),
        Formula::o(Formula::r(Interval { lower: 0, upper: 5 }, None, a.clone(), b.clone()))
    ]);
    make_test_decompose(vec![Formula::r(Interval { lower: 0, upper: 5 }, None, a.clone(), b.clone())], vec![expected1, expected2], None);
}

#[test]
fn test_jump_only_prop() {
    let a = prop("a");
    let b = prop("b");
    let to_decompose = Node::from_operands(vec![
        a.clone(),
        b.clone()
    ]);
    let res = tableau_data_gen(Some(decompose_jump_opt())).decompose_jump(&to_decompose);
    assert_eq!(res, None);
}

#[test]
fn test_jump_temporal_end() {
    let a = prop("a");
    let mut to_decompose = Node::from_operands(vec![
        Formula::o(Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone())),
        Formula::f(Interval { lower: 3, upper: 5 }, None, a.clone())
    ]);
    to_decompose.current_time = 5;
    let res = tableau_data_gen(Some(decompose_jump_opt())).decompose_jump(&to_decompose);
    assert_eq!(res, None);
}

#[test]
fn test_jump_step_interval_end() {
    let a = prop("a");
    let mut to_decompose = Node::from_operands(vec![
        Formula::o(Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone())),
        Formula::o(Formula::f(Interval { lower: 0, upper: 8 }, None, Formula::not(a.clone()))),
    ]);
    to_decompose.current_time = 5;
    let res = tableau_data_gen(Some(decompose_jump_opt())).decompose_jump(&to_decompose);
    assert!(res.is_some());
    let vec = res.unwrap();
    assert_eq!(vec.len(), 1);
    let node = &vec[0];
    let expected = Node::from_operands(vec![
        Formula::f(Interval { lower: 0, upper: 8 }, None, Formula::not(a.clone()))
    ]);
    assert_eq!(node.current_time, 6);
    assert_eq!(node.operands, expected.operands);
}

#[test]
fn test_jump_step_closure() {
    let a = prop("a");
    let mut to_decompose = Node::from_operands(vec![
        Formula::o(Formula::g(Interval { lower: 0, upper: 5 }, None, Formula::f(Interval { lower: 0, upper: 2 }, None, a.clone()))),
    ]);
    to_decompose.current_time = 1;
    let res = tableau_data_gen(Some(decompose_jump_opt())).decompose_jump(&to_decompose);
    assert!(res.is_some());
    let vec = res.unwrap();
    assert_eq!(vec.len(), 1);
    let node = &vec[0];
    let expected = Node::from_operands(vec![
        Formula::g(Interval { lower: 0, upper: 5 }, None, Formula::f(Interval { lower: 0, upper: 2 }, None, a.clone()))
    ]);
    assert_eq!(node.current_time, 2);
    assert_eq!(node.operands, expected.operands);
}

#[test]
fn test_jump_end() {
    let a = prop("a");
    let mut to_decompose = Node::from_operands(vec![
        Formula::o(Formula::f(Interval { lower: 20, upper: 50 }, None, a.clone()))
    ]);
    to_decompose.current_time = 20;
    let res = tableau_data_gen(Some(decompose_jump_opt())).decompose_jump(&to_decompose);
    assert!(res.is_some());
    let vec = res.unwrap();
    assert_eq!(vec.len(), 1);
    let node = &vec[0];

    let expected = Node::from_operands(vec![
        Formula::f(Interval { lower: 20, upper: 50 }, None, a.clone())
    ]);

    assert_eq!(node.current_time, 50);
    assert_eq!(node.operands, expected.operands);
}