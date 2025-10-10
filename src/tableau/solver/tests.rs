use crate::{formula::parser::parse_formula, node::Node, tableau::solver::Solver};


fn parse_node(input: &str) -> Node {
    let (_, formula) = parse_formula(input).unwrap();
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

    solver.push();

    let node = parse_node("a && b"); 
    assert_eq!(solver.check(&node), true);

    solver.push();

    let node_false = parse_node("!a, a");
    assert_eq!(solver.check(&node_false), false);

    solver.pop();

    solver.push();
    let node_true = parse_node("c");
    assert_eq!(solver.check(&node_true), true);

    solver.push();
    let node_false_2 = parse_node("!a");
    assert_eq!(solver.check(&node_false_2), false);
}