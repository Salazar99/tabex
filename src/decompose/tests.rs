use crate::{formula::{Expr, Formula, Interval}, node::Node, tableau::{TableauData, TableauOptions}};

fn make_test_decompose(input: &str, expected: Vec<Node>, options: Option<TableauOptions>) {
    let (_, formula) = crate::parser::parse_formula(input).unwrap();
    let node = Node::from_operands(vec![formula]);
    let tableau_data = TableauData::new(
        if let Some(tops) = options {
            tops
        } else {
            TableauOptions { graph_output: false, ..Default::default() }
        }
    );
    let decomposed = tableau_data.decompose(&node);
    let decomposed_operands = decomposed.iter().map(|n| n.operands.clone()).collect::<Vec<Vec<Formula>>>();
    let expected_operands = expected.iter().map(|n| n.operands.clone()).collect::<Vec<Vec<Formula>>>();
    assert_eq!(decomposed_operands, expected_operands);
}

#[test]
fn test_and() {
    let expected: Node = Node::from_operands(vec![
        Formula::Prop(Expr::Atom("a".into())),
        Formula::Prop(Expr::Atom("b".into()))
    ]);
    make_test_decompose("a && b", vec![expected], None);
}

#[test]
fn test_or() {
    let expected1: Node = Node::from_operands(vec![
        Formula::Prop(Expr::Atom("a".into()))
    ]);
    let expected2: Node = Node::from_operands(vec![
        Formula::Prop(Expr::Atom("b".into()))
    ]);
    make_test_decompose("a || b", vec![expected1, expected2], None);
}

#[test]
fn test_imply() {
    let expected1: Node = Node::from_operands(vec![
        Formula::Not(Box::new(Formula::Prop(Expr::Atom("a".into())))),
    ]);
    let expected_optimization: Node = Node::from_operands(vec![
        Formula::Prop(Expr::Atom("b".into())),
        Formula::Prop(Expr::Atom("a".into()))
    ]);
    let expected_non_optimization: Node = Node::from_operands(vec![
        Formula::Prop(Expr::Atom("b".into()))
    ]);
    make_test_decompose("a -> b", vec![expected1.clone(), expected_optimization], None);
    make_test_decompose("a -> b", vec![expected1, expected_non_optimization], Some(TableauOptions { formula_optimizations: false, ..Default::default() }));
}

#[test]
fn test_globally() {
    let expected1: Node = Node::from_operands(vec![
        Formula::Prop(Expr::Atom("a".into())),
        Formula::O(Box::new(
            Formula::G { interval: Interval { lower: 0, upper: 5 }, 
            parent_upper: None, phi: Box::new(Formula::Prop(Expr::Atom("a".into()))) }
        ))
    ]);
    make_test_decompose("G[0,5] a", vec![expected1], None);
}

#[test]
fn test_finally() {
    let expected1: Node = Node::from_operands(vec![
        Formula::Prop(Expr::Atom("a".into())),
    ]);
    let expected2: Node = Node::from_operands(vec![
        Formula::O(Box::new(
            Formula::F { interval: Interval { lower: 0, upper: 5 }, 
            parent_upper: None, phi: Box::new(Formula::Prop(Expr::Atom("a".into()))) }
        ))
    ]);
    make_test_decompose("F[0,5] a", vec![expected1, expected2], None);
}

#[test] 
fn test_gf(){
    let expected1: Node = Node::from_operands(vec![
        Formula::F {
            interval: Interval { lower: 0, upper: 5 }, 
            parent_upper: Some(5), phi: Box::new(Formula::Prop(Expr::Atom("a".into())))
        },
        Formula::O(Box::new(
            Formula::G { 
                interval: Interval { lower: 0, upper: 5 }, 
                parent_upper: None, 
                phi: Box::new(Formula::F {
                    interval: Interval { lower: 0, upper: 5 }, 
                    parent_upper: None, 
                    phi: Box::new(Formula::Prop(Expr::Atom("a".into())))
                }) 
            }
        ))
    ]);
    let options = TableauOptions { formula_optimizations: false, ..Default::default() };
    make_test_decompose("G[0,5] F[0,5] a", vec![expected1], Some(options));
}

#[test]
fn test_jump_only_prop() {
    let to_decompose = Node::from_operands(vec![
        Formula::Prop(Expr::Atom("a".into())),
        Formula::Prop(Expr::Atom("b".into()))
    ]);
    let res = to_decompose.decompose_jump(false, true);
    assert_eq!(res, None);
}

#[test]
fn test_jump_temporal_end() {
    let mut to_decompose = Node::from_operands(vec![
        Formula::O(Box::new(
            Formula::G { interval: Interval { lower: 0, upper: 5 }, 
            parent_upper: None, phi: Box::new(Formula::Prop(Expr::Atom("a".into()))) }
        )),
        Formula::F { interval: Interval { lower: 3, upper: 5 }, 
            parent_upper: None, phi: Box::new(Formula::Prop(Expr::Atom("a".into()))) 
        }
    ]);
    to_decompose.current_time = 5;
    let res = to_decompose.decompose_jump(false, true);
    assert_eq!(res, None);
}

#[test]
fn test_jump_step_interval_end() {
    let mut to_decompose = Node::from_operands(vec![
        Formula::O(Box::new(
            Formula::G { interval: Interval { lower: 0, upper: 5 }, parent_upper: None, phi: Box::new(Formula::Prop(Expr::Atom("a".into()))) }
        )),
        Formula::O(Box::new(
            Formula::F { interval: Interval { lower: 0, upper: 8 }, parent_upper: None, phi: Box::new(Formula::Not(Box::new(Formula::Prop(Expr::Atom("a".into()))))) }
        )),
    ]);
    to_decompose.current_time = 5;
    let res = to_decompose.decompose_jump(false, true);
    assert!(res.is_some());
    let vec = res.unwrap();
    assert_eq!(vec.len(), 1);
    let node = &vec[0];
    let expected = Node::from_operands(vec![
        Formula::F { interval: Interval { lower: 0, upper: 8 }, parent_upper: None, phi: Box::new(Formula::Not(Box::new(Formula::Prop(Expr::Atom("a".into()))))) }
    ]);
    assert_eq!(node.current_time, 6);
    assert_eq!(node.operands, expected.operands);
}

#[test]
fn test_jump_step_closure() {
    let mut to_decompose = Node::from_operands(vec![
        Formula::O(Box::new(
            Formula::G { interval: Interval { lower: 0, upper: 5 }, parent_upper: None, phi: Box::new(
                Formula::F { interval: Interval { lower: 0, upper: 2 }, parent_upper: None, phi: Box::new(Formula::Prop(Expr::Atom("a".into()))) }
            ) }
        )),
    ]);
    to_decompose.current_time = 1;
    let res = to_decompose.decompose_jump(false, true);
    assert!(res.is_some());
    let vec = res.unwrap();
    assert_eq!(vec.len(), 1);
    let node = &vec[0];
    let expected = Node::from_operands(vec![
        Formula::G { interval: Interval { lower: 0, upper: 5 }, parent_upper: None, phi: Box::new(
            Formula::F { interval: Interval { lower: 0, upper: 2 }, parent_upper: None, phi: Box::new(Formula::Prop(Expr::Atom("a".into()))) }
        ) }  
    ]);
    assert_eq!(node.current_time, 2);
    assert_eq!(node.operands, expected.operands);
}