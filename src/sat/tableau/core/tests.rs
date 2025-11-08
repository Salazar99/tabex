use crate::formula::{Expr, ExprKind, Formula};
use crate::sat::tableau::core::UnsatCore;
use crate::sat::tableau::node::Node;
use std::sync::Arc;

#[test]
fn test_unsat_core_new() {
    let core = UnsatCore::new();
    assert!(core.map.is_empty());
    assert!(core.node.is_none());
    assert!(core.unsat_core.is_empty());
}

#[test]
fn test_initialize_root_node() {
    let mut core = UnsatCore::new();
    let expr1 = Expr {
        id: 1,
        kind: ExprKind::Atom(Arc::from("p")),
    };
    let expr2 = Expr {
        id: 2,
        kind: ExprKind::Atom(Arc::from("q")),
    };
    let operands = vec![Formula::Prop(expr1).into(), Formula::Prop(expr2).into()];
    let node = Node::from_operands(operands);
    core.initialize_root_node(&node);
    assert!(core.node.is_some());
    assert_eq!(core.map.get(&1), Some(&0));
    assert_eq!(core.map.get(&2), Some(&1));
}

#[test]
fn test_get_unsat_core() {
    let mut core = UnsatCore::new();
    let expr1 = Expr {
        id: 1,
        kind: ExprKind::Atom(Arc::from("p")),
    };
    let expr2 = Expr {
        id: 2,
        kind: ExprKind::Atom(Arc::from("q")),
    };
    let expr3 = Expr {
        id: 3,
        kind: ExprKind::Atom(Arc::from("r")),
    };
    let operands = vec![
        Formula::Prop(expr1.clone()).into(),
        Formula::Prop(expr2.clone()).into(),
        Formula::Prop(expr3.clone()).into(),
    ];
    let node = Node::from_operands(operands);
    core.initialize_root_node(&node);
    core.unsat_core.insert(1);
    core.unsat_core.insert(3);
    let unsat_formulas = core.get_unsat_core();
    assert_eq!(unsat_formulas.len(), 2);
    assert!(unsat_formulas.contains(&Formula::Prop(expr1)));
    assert!(unsat_formulas.contains(&Formula::Prop(expr3)));
}

#[test]
#[should_panic]
fn test_get_unsat_core_without_init_returns_empty() {
    let mut core = UnsatCore::new();
    core.unsat_core.insert(1);
    let unsat_formulas = core.get_unsat_core();
    assert!(unsat_formulas.is_empty());
}
