use crate::{node::Node, solver::Solver};

fn parse_node(input: &str) -> Node {
    let (_, formula) = crate::parser::parse_formula(input).unwrap();
    let mut node = Node::from_operands(vec![formula]);
    node.flatten();
    node
}

fn make_solver_test(input: &str) -> bool {
    let mut solver = Solver::new();
    solver.check(&parse_node(input))
}

#[test]
fn test_bool_true() {
    assert_eq!(make_solver_test("a && b"), true);
}

#[test]
fn test_bool_false() {
    assert_eq!(make_solver_test("a && !a"), false);
}

#[test]
fn test_real_true() {
    assert_eq!(make_solver_test("R_x > 0 && R_x < 5"), true);
}

#[test]
fn test_real_false() {
    assert_eq!(make_solver_test("R_x > 5 && R_x < 0"), false);
}

#[test]
fn test_push_pop_bool() {
    let mut solver = Solver::new();
    assert_eq!(solver.result_cache, Some(true));

    solver.push();

    let node = parse_node("a && b"); 
    assert_eq!(solver.check(&node), true);
    assert_eq!(solver.result_cache, Some(true));

    solver.push();
    assert_eq!(solver.result_cache, Some(true));

    let node_false = parse_node("!a");
    assert_eq!(solver.check(&node_false), false);
    assert_eq!(solver.result_cache, Some(false));

    solver.pop();

    let node_true = parse_node("c");
    assert_eq!(solver.check(&node_true), true);
    assert_eq!(solver.result_cache, Some(true));
}