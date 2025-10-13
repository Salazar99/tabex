use std::sync::Arc;

use num_rational::Ratio;

use crate::{formula::{parser::parse_formula, Expr, Formula}, node::Node, tableau::solver::Solver};


fn parse_node(input: &str) -> Node {
    let (_, formula) = parse_formula(input).unwrap();
    let mut node = Node::from_operands(vec![formula]);
    node.flatten();

    for formula in node.operands.iter_mut() {
        formula.assign_ids();
    }

    node
}

fn make_solver_test(input: &str) -> bool {
    let mut solver = Solver::new(false);
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
    let mut solver = Solver::new(false);

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
    let mut solver = Solver::new(false);

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
fn test_unsat_core_not_enabled() {
    let mut solver = Solver::new(false);

    let mut one = Formula::prop(Expr::Atom(Arc::from("a")));
    one.id = Some(0);
    let mut two = Formula::not(Formula::prop(Expr::Atom(Arc::from("a"))));
    two.id = Some(1);
    
    let node = Node::from_operands(vec![one, two]); 

    assert_eq!(solver.check(&node), false);
    assert_eq!(solver.extract_unsat_core(), None);
}

#[test]
fn test_unsat_core_bool() {
    let mut solver = Solver::new(true);

    let mut one = Formula::prop(Expr::Atom(Arc::from("a")));
    one.id = Some(0);
    let mut two = Formula::not(Formula::prop(Expr::Atom(Arc::from("a"))));
    two.id = Some(1);
    
    let node = Node::from_operands(vec![one, two]); 

    assert_eq!(solver.check(&node), false);
    assert_eq!(solver.extract_unsat_core(), Some(vec![0, 1]));
}

#[test]
fn test_unsat_core_bool_sat() {
    let mut solver = Solver::new(true);

    let mut one = Formula::prop(Expr::Atom(Arc::from("a")));
    one.id = Some(0);
    let mut two = Formula::prop(Expr::Atom(Arc::from("b")));
    two.id = Some(1);

    let node = Node::from_operands(vec![one, two]);

    assert_eq!(solver.check(&node), true);
    assert_eq!(solver.extract_unsat_core(), None);
}

#[test]
fn test_unsat_core_bool_one_excluded() {
    let mut solver = Solver::new(true);

    let mut one = Formula::prop(Expr::Atom(Arc::from("a")));
    one.id = Some(0);
    let mut two = Formula::not(Formula::prop(Expr::Atom(Arc::from("a"))));
    two.id = Some(1);
    let mut three = Formula::prop(Expr::Atom(Arc::from("b")));
    three.id = Some(2);

    let node = Node::from_operands(vec![one, two, three]);

    assert_eq!(solver.check(&node), false);
    let core = solver.extract_unsat_core().unwrap();
    assert_eq!(core.len(), 2);
    assert!(core.contains(&0));
    assert!(core.contains(&1));
}

#[test]
fn test_unsat_core_real() {
    let mut solver = Solver::new(true);

    let mut one = Formula::prop(Expr::Rel { 
        op: crate::formula::RelOp::Ge, left: crate::formula::AExpr::Var(Arc::from("x")), right: crate::formula::AExpr::Num(Ratio::from_integer(5))
    });
    one.id = Some(0);
    let mut two = Formula::prop(Expr::Rel { 
        op: crate::formula::RelOp::Le, left: crate::formula::AExpr::Var(Arc::from("x")), right: crate::formula::AExpr::Num(Ratio::from_integer(0))
    });
    two.id = Some(1);

    let node = Node::from_operands(vec![one, two]);

    assert_eq!(solver.check(&node), false);
    assert_eq!(solver.extract_unsat_core(), Some(vec![0, 1]));
}

#[test]
fn test_unsat_core_real_sat() {
    let mut solver = Solver::new(true);

    let mut one = Formula::prop(Expr::Rel { 
        op: crate::formula::RelOp::Ge, left: crate::formula::AExpr::Var(Arc::from("x")), right: crate::formula::AExpr::Num(Ratio::from_integer(0))
    });
    one.id = Some(0);
    let mut two = Formula::prop(Expr::Rel { 
        op: crate::formula::RelOp::Le, left: crate::formula::AExpr::Var(Arc::from("x")), right: crate::formula::AExpr::Num(Ratio::from_integer(5))
    });
    two.id = Some(1);

    let node = Node::from_operands(vec![one, two]);

    assert_eq!(solver.check(&node), true);
    assert_eq!(solver.extract_unsat_core(), None);
}

#[test]
fn test_unsat_core_real_one_excluded() {
    let mut solver = Solver::new(true);

    let mut one = Formula::prop(Expr::Rel { 
        op: crate::formula::RelOp::Ge, left: crate::formula::AExpr::Var(Arc::from("x")), right: crate::formula::AExpr::Num(Ratio::from_integer(5))
    });
    one.id = Some(0);
    let mut two = Formula::prop(Expr::Rel { 
        op: crate::formula::RelOp::Le, left: crate::formula::AExpr::Var(Arc::from("x")), right: crate::formula::AExpr::Num(Ratio::from_integer(0))
    });
    two.id = Some(1);
    let mut three = Formula::prop(Expr::Rel { 
        op: crate::formula::RelOp::Ge, left: crate::formula::AExpr::Var(Arc::from("y")), right: crate::formula::AExpr::Num(Ratio::from_integer(1))
    });
    three.id = Some(2);

    let node = Node::from_operands(vec![one, two, three]);

    assert_eq!(solver.check(&node), false);
    let core = solver.extract_unsat_core().unwrap();
    assert_eq!(core.len(), 2);
    assert!(core.contains(&0));
    assert!(core.contains(&1));
}