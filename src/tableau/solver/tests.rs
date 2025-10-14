use std::sync::Arc;

use num_rational::Ratio;

use crate::{formula::{parser::parse_formula, Expr, Formula}, node::Node, tableau::solver::Solver};


fn parse_node(input: &str) -> Node {
    let (_, formula) = parse_formula(input).unwrap();
    let mut node = Node::from_operands(vec![formula]);
    node.flatten();
    node
}

fn make_solver_test(input: &str) -> bool {
    let mut solver = Solver::new(false, false);
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
    let mut solver = Solver::new(false, false);

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

#[test]
fn test_push_pop_real() {
    let mut solver = Solver::new(false, false);

    solver.push();

    let node = parse_node("R_x > 0 && R_x < 5"); 
    assert_eq!(solver.check(&node), true);

    solver.push();

    let node_false = parse_node("R_x < 0");
    assert_eq!(solver.check(&node_false), false);

    solver.pop();

    solver.push();
    let node_true = parse_node("R_y > 1");
    assert_eq!(solver.check(&node_true), true);

    solver.push();
    let node_false_2 = parse_node("R_x < 0");
    assert_eq!(solver.check(&node_false_2), false);
}

#[test]
#[should_panic]
fn mltl_real_constraint() {
    let mut solver = Solver::new(false, true);
    let node = parse_node("R_x > 0");
    solver.check(&node);
}

#[test]
fn mltl_boolean() {
    let mut solver = Solver::new(false, true);
    let node = parse_node("a && b");
    assert_eq!(solver.check(&node), true);
}

#[test]
fn test_unsat_core_not_enabled() {
    let mut solver = Solver::new(false, false);

    let one = Formula::prop(Expr::bool(Arc::from("a")));
    let two = Formula::not(Formula::prop(Expr::bool(Arc::from("a"))));
    
    let node = Node::from_operands(vec![one, two]); 

    assert_eq!(solver.check(&node), false);
    assert_eq!(solver.extract_unsat_core(), None);
}

#[test]
fn test_unsat_core_bool() {
    let mut solver = Solver::new(true, false);

    let one = Formula::prop(Expr::bool(Arc::from("a")));
    let two = Formula::not(Formula::prop(Expr::bool(Arc::from("a"))));
    
    let node = Node::from_operands(vec![one.clone(), two.clone()]); 

    assert_eq!(solver.check(&node), false);

    let id = if let Formula::Prop(prop) = one { prop.id } else { unreachable!() };
    let id2 = if let Formula::Not(inner) = two && let Formula::Prop(expr) = *inner { expr.id } else { unreachable!() };
    
    assert_eq!(solver.extract_unsat_core(), Some(vec![id, id2]));
}

#[test]
fn test_unsat_core_bool_sat() {
    let mut solver = Solver::new(true, false);

    let one = Formula::prop(Expr::bool(Arc::from("a")));
    let two = Formula::prop(Expr::bool(Arc::from("b")));

    let node = Node::from_operands(vec![one, two]);

    assert_eq!(solver.check(&node), true);
    assert_eq!(solver.extract_unsat_core(), None);
}

#[test]
fn test_unsat_core_bool_one_excluded() {
    let mut solver = Solver::new(true, false);

    let one = Formula::prop(Expr::bool(Arc::from("a")));
    let two = Formula::not(Formula::prop(Expr::bool(Arc::from("a"))));
    let three = Formula::prop(Expr::bool(Arc::from("b")));

    let node = Node::from_operands(vec![one.clone(), two.clone(), three.clone()]);

    assert_eq!(solver.check(&node), false);
    let core = solver.extract_unsat_core().unwrap();
    assert_eq!(core.len(), 2);

    let id = if let Formula::Prop(expr) = one { expr.id } else { unreachable!() };
    let id2 = if let Formula::Not(inner) = two && let Formula::Prop(expr) = *inner { expr.id } else { unreachable!() };
    
    assert!(core.contains(&id));
    assert!(core.contains(&id2));
}

#[test]
fn test_unsat_core_real() {
    let mut solver = Solver::new(true, false);

    let one = Formula::prop(Expr::real ( 
        crate::formula::RelOp::Ge, crate::formula::AExpr::Var(Arc::from("x")), crate::formula::AExpr::Num(Ratio::from_integer(5))
    ));
    let two = Formula::prop(Expr::real ( 
        crate::formula::RelOp::Le, crate::formula::AExpr::Var(Arc::from("x")), crate::formula::AExpr::Num(Ratio::from_integer(0))
    ));

    let node = Node::from_operands(vec![one.clone(), two.clone()]);

    let id = if let Formula::Prop(expr) = one { expr.id } else { unreachable!() };
    let id2 = if let Formula::Prop(expr) = two { expr.id } else { unreachable!() };

    assert_eq!(solver.check(&node), false);
    assert_eq!(solver.extract_unsat_core(), Some(vec![id, id2]));
}

#[test]
fn test_unsat_core_real_sat() {
    let mut solver = Solver::new(true, false);

    let one = Formula::prop(Expr::real(
        crate::formula::RelOp::Ge,
        crate::formula::AExpr::Var(Arc::from("x")),
        crate::formula::AExpr::Num(Ratio::from_integer(0)),
    ));
    let two = Formula::prop(Expr::real(
        crate::formula::RelOp::Le,
        crate::formula::AExpr::Var(Arc::from("x")),
        crate::formula::AExpr::Num(Ratio::from_integer(5)),
    ));

    let node = Node::from_operands(vec![one, two]);

    assert_eq!(solver.check(&node), true);
    assert_eq!(solver.extract_unsat_core(), None);
}

#[test]
fn test_unsat_core_real_one_excluded() {
    let mut solver = Solver::new(true, false);

    let one = Formula::prop(Expr::real(
        crate::formula::RelOp::Ge,
        crate::formula::AExpr::Var(Arc::from("x")),
        crate::formula::AExpr::Num(Ratio::from_integer(5)),
    ));
    let two = Formula::prop(Expr::real(
        crate::formula::RelOp::Le,
        crate::formula::AExpr::Var(Arc::from("x")),
        crate::formula::AExpr::Num(Ratio::from_integer(0)),
    ));
    let three = Formula::prop(Expr::real(
        crate::formula::RelOp::Ge,
        crate::formula::AExpr::Var(Arc::from("y")),
        crate::formula::AExpr::Num(Ratio::from_integer(1)),
    ));

    let node = Node::from_operands(vec![one.clone(), two.clone(), three]);

    let id = if let Formula::Prop(expr) = one { expr.id } else { unreachable!() };
    let id2 = if let Formula::Prop(expr) = two { expr.id } else { unreachable!() };

    assert_eq!(solver.check(&node), false);
    let core = solver.extract_unsat_core().unwrap();
    assert_eq!(core.len(), 2);
    assert!(core.contains(&id));
    assert!(core.contains(&id2));
}