use super::*;
use crate::sat::tableau::node::{Node, NodeFormula};

fn interval(lower: i32, upper: i32) -> Interval {
    Interval { lower, upper }
}

fn prop(name: &str) -> Formula {
    Formula::Prop(Expr::bool(name.into()))
}

#[test]
fn test_simple_prop() {
    let f1 = prop("p");
    let node = Node::from_operands(vec![NodeFormula::from(f1)]);
    let sig = Signature::new(&node);

    let p_sig = sig.map.get("p").unwrap();
    assert_eq!(p_sig.len(), 1);
    assert_eq!(p_sig[0].0, interval(0, 0));
    // ID check might be tricky because of global atomic counter.
    // We can check count.
    assert_eq!(p_sig[0].1.len(), 1);
}

#[test]
fn test_global() {
    let f1 = Formula::G {
        interval: interval(0, 5),
        phi: Box::new(prop("p")),
    };
    let node = Node::from_operands(vec![NodeFormula::from(f1)]);
    let sig = Signature::new(&node);

    let p_sig = sig.map.get("p").unwrap();
    assert_eq!(p_sig.len(), 1);
    assert_eq!(p_sig[0].0, interval(0, 5));
}

#[test]
fn test_future() {
    let f1 = Formula::F {
        interval: interval(2, 4),
        phi: Box::new(prop("q")),
    };
    let node = Node::from_operands(vec![NodeFormula::from(f1)]);
    let sig = Signature::new(&node);

    let q_sig = sig.map.get("q").unwrap();
    assert_eq!(q_sig.len(), 1);
    assert_eq!(q_sig[0].0, interval(2, 4));
}

#[test]
fn test_overlap() {
    // G[0, 5] p
    let f1 = Formula::G {
        interval: interval(0, 5),
        phi: Box::new(prop("p")),
    };
    // F[4, 6] p
    let f2 = Formula::F {
        interval: interval(4, 6),
        phi: Box::new(prop("p")),
    };

    let nf1 = NodeFormula::from(f1);
    let nf2 = NodeFormula::from(f2);
    let id1 = nf1.id;
    let id2 = nf2.id;

    let node = Node::from_operands(vec![nf1, nf2]);
    let sig = Signature::new(&node);

    let p_sig = sig.map.get("p").unwrap();

    // Expected: [0, 3] -> {id1}, [4, 5] -> {id1, id2}, [6, 6] -> {id2}
    assert_eq!(p_sig.len(), 3);

    assert_eq!(p_sig[0].0, interval(0, 3));
    assert_eq!(p_sig[0].1, vec![id1]);

    assert_eq!(p_sig[1].0, interval(4, 5));
    let mut ids_mid = p_sig[1].1.clone();
    ids_mid.sort();
    let mut expected_mid = vec![id1, id2];
    expected_mid.sort();
    assert_eq!(ids_mid, expected_mid);

    assert_eq!(p_sig[2].0, interval(6, 6));
    assert_eq!(p_sig[2].1, vec![id2]);
}

#[test]
fn test_until() {
    // p U[0, 5] q
    // p active in [0, 5]
    // q active in [0, 5]
    let f1 = Formula::U {
        interval: interval(0, 5),
        left: Box::new(prop("p")),
        right: Box::new(prop("q")),
    };
    let node = Node::from_operands(vec![NodeFormula::from(f1)]);
    let sig = Signature::new(&node);

    let p_sig = sig.map.get("p").unwrap();
    assert_eq!(p_sig[0].0, interval(0, 5));

    let q_sig = sig.map.get("q").unwrap();
    assert_eq!(q_sig[0].0, interval(0, 5));
}

#[test]
fn test_until_nonzero_start() {
    // p U[2, 5] q
    // With new semantics:
    // p active in [2, 5]
    // q active in [2, 5]
    let f1 = Formula::U {
        interval: interval(2, 5),
        left: Box::new(prop("p")),
        right: Box::new(prop("q")),
    };
    let node = Node::from_operands(vec![NodeFormula::from(f1)]);
    let sig = Signature::new(&node);

    let p_sig = sig.map.get("p").unwrap();
    assert_eq!(p_sig[0].0, interval(2, 5));

    let q_sig = sig.map.get("q").unwrap();
    assert_eq!(q_sig[0].0, interval(2, 5));
}

#[test]
fn test_nested() {
    // G[0, 2] (F[1, 2] p)
    // Outer G: [0, 2]
    // Inner F: [1, 2] relative to G
    // Total p: [0+1, 2+2] = [1, 4]

    let f1 = Formula::G {
        interval: interval(0, 2),
        phi: Box::new(Formula::F {
            interval: interval(1, 2),
            phi: Box::new(prop("p")),
        }),
    };

    let node = Node::from_operands(vec![NodeFormula::from(f1)]);
    let sig = Signature::new(&node);

    let p_sig = sig.map.get("p").unwrap();
    assert_eq!(p_sig.len(), 1);
    assert_eq!(p_sig[0].0, interval(1, 4));
}
