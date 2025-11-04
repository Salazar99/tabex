use std::sync::Arc;

use crate::{
    formula::{Expr, Formula, Interval},
    node::Node,
    tableau::store::{RejectedNode, Store},
};

fn prop(name: &str) -> Formula {
    Formula::prop(Expr::bool(Arc::from(name)))
}

fn make_check_rejected_test(
    store_content: Vec<Vec<Formula>>,
    test_node: Vec<Formula>,
    store_time: i32,
    test_time: i32,
) -> bool {
    let mut store = Store::new();
    for content in store_content {
        let mut node = Node::from_operands(content);
        node.flatten();
        node.current_time = store_time;
        let rejected = RejectedNode::from_node(&node);
        store.add_rejected(rejected);
    }
    let mut test_node = Node::from_operands(test_node);
    test_node.flatten();
    test_node.current_time = test_time;
    let rejected_test_node = RejectedNode::from_node(&test_node);
    store.check_rejected(&rejected_test_node)
}

#[test]
fn test_empty_store() {
    let a = prop("a");
    assert!(
        !make_check_rejected_test(
            vec![],
            vec![Formula::g(
                Interval {
                    lower: 0,
                    upper: 10
                },
                None,
                a.clone()
            )],
            0,
            0
        )
    );
}

#[test]
fn test_globally() {
    let a = prop("a");
    assert!(
        !make_check_rejected_test(
            vec![vec![Formula::g(
                Interval {
                    lower: 0,
                    upper: 10
                },
                None,
                a.clone()
            )]],
            vec![Formula::g(Interval { lower: 2, upper: 5 }, None, a.clone())],
            0,
            0
        )
    );
    assert!(
        make_check_rejected_test(
            vec![vec![Formula::g(
                Interval {
                    lower: 0,
                    upper: 10
                },
                None,
                a.clone()
            )]],
            vec![Formula::g(
                Interval {
                    lower: 0,
                    upper: 10
                },
                None,
                a.clone()
            )],
            0,
            0
        )
    );
    assert!(
        make_check_rejected_test(
            vec![vec![Formula::g(
                Interval {
                    lower: 0,
                    upper: 10
                },
                None,
                a.clone()
            )]],
            vec![Formula::g(
                Interval {
                    lower: 0,
                    upper: 15
                },
                None,
                a.clone()
            )],
            0,
            0
        )
    );
}

#[test]
fn test_finally() {
    let a = prop("a");
    assert!(
        make_check_rejected_test(
            vec![vec![Formula::f(
                Interval {
                    lower: 0,
                    upper: 10
                },
                None,
                a.clone()
            )]],
            vec![Formula::f(Interval { lower: 2, upper: 5 }, None, a.clone())],
            0,
            0
        )
    );
    assert!(
        make_check_rejected_test(
            vec![vec![Formula::f(
                Interval {
                    lower: 0,
                    upper: 10
                },
                None,
                a.clone()
            )]],
            vec![Formula::f(
                Interval {
                    lower: 0,
                    upper: 10
                },
                None,
                a.clone()
            )],
            0,
            0
        )
    );
    assert!(
        !make_check_rejected_test(
            vec![vec![Formula::f(
                Interval {
                    lower: 0,
                    upper: 10
                },
                None,
                a.clone()
            )]],
            vec![Formula::f(
                Interval {
                    lower: 0,
                    upper: 15
                },
                None,
                a.clone()
            )],
            0,
            0
        )
    );
}

#[test]
fn test_shift() {
    let a = prop("a");
    assert!(
        !make_check_rejected_test(
            vec![vec![
                Formula::g(
                    Interval {
                        lower: 16,
                        upper: 17
                    },
                    None,
                    Formula::not(a.clone())
                ),
                Formula::f(
                    Interval {
                        lower: 16,
                        upper: 17
                    },
                    None,
                    a.clone()
                )
            ]],
            vec![
                Formula::g(
                    Interval {
                        lower: 16,
                        upper: 17
                    },
                    None,
                    Formula::not(a.clone())
                ),
                Formula::f(
                    Interval {
                        lower: 18,
                        upper: 18
                    },
                    None,
                    a.clone()
                )
            ],
            17,
            16
        )
    );
}
