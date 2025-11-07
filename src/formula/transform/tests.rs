use crate::{
    formula::{Expr, Formula, Interval},
    sat::tableau::node::Node,
};
use std::sync::Arc;

fn prop(name: &str) -> Formula {
    Formula::prop(Expr::bool(Arc::from(name)))
}

fn make_test_push_negation(input: Vec<Formula>, result: Vec<Formula>) -> (Node, Node) {
    let mut input_node: Node = Node::from_operands(input);
    input_node.negative_normal_form_rewrite();
    let result_node: Node = Node::from_operands(result);
    (input_node, result_node)
}

fn make_test_shift_bounds(input: Formula, result: Formula) -> (Node, Node) {
    let mut input_node: Node = Node::from_operands(vec![input]);
    input_node.shift_bounds();
    let result_node: Node = Node::from_operands(vec![result]);
    (input_node, result_node)
}

fn make_test_flatten(input: Formula) -> Node {
    let mut input_node: Node = Node::from_operands(vec![input]);
    input_node.flatten();
    input_node
}

mod push_negation_tests {
    use super::*;

    #[test]
    fn push_negation_prop() {
        let p = prop("a");
        let (res, exp) =
            make_test_push_negation(vec![Formula::not(p.clone())], vec![Formula::not(p)]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_double_negation() {
        let a = prop("a");
        let input_formula = Formula::not(Formula::not(a.clone()));
        let result_formula = a;
        let (res, exp) = make_test_push_negation(vec![input_formula], vec![result_formula]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_and() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::not(Formula::and(vec![a.clone(), b.clone()]));
        let result_formula = Formula::or(vec![Formula::not(a), Formula::not(b)]);
        let (res, exp) = make_test_push_negation(vec![input_formula], vec![result_formula]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_or() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::not(Formula::or(vec![a.clone(), b.clone()]));
        let result_formula = Formula::and(vec![Formula::not(a), Formula::not(b)]);
        let (res, exp) = make_test_push_negation(vec![input_formula], vec![result_formula]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_imply() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::not(Formula::imply(a.clone(), b.clone()));
        let result_formula = Formula::and(vec![a, Formula::not(b)]);
        let (res, exp) = make_test_push_negation(vec![input_formula], vec![result_formula]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_globally() {
        let a = prop("a");
        let input_formula =
            Formula::not(Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone()));
        let result_formula = Formula::f(Interval { lower: 0, upper: 5 }, None, Formula::not(a));
        let (res, exp) = make_test_push_negation(vec![input_formula], vec![result_formula]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_finally() {
        let a = prop("a");
        let input_formula =
            Formula::not(Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone()));
        let result_formula = Formula::g(Interval { lower: 0, upper: 5 }, None, Formula::not(a));
        let (res, exp) = make_test_push_negation(vec![input_formula], vec![result_formula]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_until() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::not(Formula::u(
            Interval { lower: 0, upper: 5 },
            None,
            a.clone(),
            b.clone(),
        ));
        let result_formula = Formula::r(
            Interval { lower: 0, upper: 5 },
            None,
            Formula::not(a),
            Formula::not(b),
        );
        let (res, exp) = make_test_push_negation(vec![input_formula], vec![result_formula]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_release() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::not(Formula::r(
            Interval { lower: 0, upper: 5 },
            None,
            a.clone(),
            b.clone(),
        ));
        let result_formula = Formula::u(
            Interval { lower: 0, upper: 0 },
            None,
            Formula::not(a),
            Formula::not(b),
        );
        let (res, exp) = make_test_push_negation(vec![input_formula], vec![result_formula]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_next() {
        let a = prop("a");
        let input_formula = Formula::not(Formula::o(a.clone()));
        let result_formula = Formula::o(Formula::not(a));
        let (res, exp) = make_test_push_negation(vec![input_formula], vec![result_formula]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_nested_globally_and() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::not(Formula::g(
            Interval { lower: 0, upper: 5 },
            None,
            Formula::and(vec![a.clone(), b.clone()]),
        ));
        let result_formula = Formula::f(
            Interval { lower: 0, upper: 5 },
            None,
            Formula::or(vec![Formula::not(a), Formula::not(b)]),
        );
        let (res, exp) = make_test_push_negation(vec![input_formula], vec![result_formula]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_nested_until_or() {
        let a = prop("a");
        let b = prop("b");
        let c = prop("c");
        let input_formula = Formula::not(Formula::u(
            Interval { lower: 0, upper: 5 },
            None,
            a.clone(),
            Formula::or(vec![b.clone(), c.clone()]),
        ));
        let result_formula = Formula::r(
            Interval { lower: 0, upper: 5 },
            None,
            Formula::not(a),
            Formula::and(vec![Formula::not(b), Formula::not(c)]),
        );
        let (res, exp) = make_test_push_negation(vec![input_formula], vec![result_formula]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_inside() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::g(
            Interval { lower: 0, upper: 5 },
            None,
            Formula::not(Formula::and(vec![a.clone(), b.clone()])),
        );
        let result_formula = Formula::g(
            Interval { lower: 0, upper: 5 },
            None,
            Formula::or(vec![Formula::not(a), Formula::not(b)]),
        );
        let (res, exp) = make_test_push_negation(vec![input_formula], vec![result_formula]);
        assert_eq!(res.operands, exp.operands);
    }
}

mod shift_bounds_tests {
    use super::*;

    #[test]
    fn no_shift() {
        let a = prop("a");
        let (res, exp) = make_test_shift_bounds(
            Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone()),
            Formula::g(Interval { lower: 0, upper: 5 }, None, a),
        );
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn nested_globally_finally() {
        let b_a = prop("B_a");
        let (res, exp) = make_test_shift_bounds(
            Formula::g(
                Interval {
                    lower: 3,
                    upper: 50,
                },
                None,
                Formula::f(
                    Interval {
                        lower: 5,
                        upper: 20,
                    },
                    None,
                    b_a.clone(),
                ),
            ),
            Formula::g(
                Interval {
                    lower: 8,
                    upper: 55,
                },
                None,
                Formula::f(
                    Interval {
                        lower: 0,
                        upper: 15,
                    },
                    None,
                    b_a,
                ),
            ),
        );
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn no_shift_complex() {
        let b_a = prop("B_a");
        let input = Formula::g(
            Interval {
                lower: 10,
                upper: 60,
            },
            None,
            Formula::imply(
                b_a.clone(),
                Formula::g(
                    Interval {
                        lower: 20,
                        upper: 40,
                    },
                    None,
                    Formula::not(b_a),
                ),
            ),
        );
        let (res, exp) = make_test_shift_bounds(input.clone(), input);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn nested_finally_globally() {
        let b_a = prop("B_a");
        let (res, exp) = make_test_shift_bounds(
            Formula::g(
                Interval {
                    lower: 3,
                    upper: 50,
                },
                None,
                Formula::f(
                    Interval {
                        lower: 5,
                        upper: 20,
                    },
                    None,
                    Formula::f(
                        Interval {
                            lower: 20,
                            upper: 30,
                        },
                        None,
                        Formula::g(
                            Interval {
                                lower: 20,
                                upper: 40,
                            },
                            None,
                            Formula::not(b_a.clone()),
                        ),
                    ),
                ),
            ),
            Formula::g(
                Interval {
                    lower: 48,
                    upper: 95,
                },
                None,
                Formula::f(
                    Interval {
                        lower: 0,
                        upper: 15,
                    },
                    None,
                    Formula::f(
                        Interval {
                            lower: 0,
                            upper: 10,
                        },
                        None,
                        Formula::g(
                            Interval {
                                lower: 0,
                                upper: 20,
                            },
                            None,
                            Formula::not(b_a),
                        ),
                    ),
                ),
            ),
        );
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn finally_and_globally() {
        let b_a = prop("B_a");
        let (res, exp) = make_test_shift_bounds(
            Formula::f(
                Interval { lower: 0, upper: 5 },
                None,
                Formula::and(vec![
                    Formula::g(
                        Interval {
                            lower: 10,
                            upper: 20,
                        },
                        None,
                        b_a.clone(),
                    ),
                    Formula::g(
                        Interval {
                            lower: 20,
                            upper: 30,
                        },
                        None,
                        b_a.clone(),
                    ),
                ]),
            ),
            Formula::f(
                Interval {
                    lower: 10,
                    upper: 15,
                },
                None,
                Formula::and(vec![
                    Formula::g(
                        Interval {
                            lower: 0,
                            upper: 10,
                        },
                        None,
                        b_a.clone(),
                    ),
                    Formula::g(
                        Interval {
                            lower: 10,
                            upper: 20,
                        },
                        None,
                        b_a,
                    ),
                ]),
            ),
        );
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn until_globally() {
        let b_a = prop("B_a");
        let (res, exp) = make_test_shift_bounds(
            Formula::u(
                Interval { lower: 0, upper: 5 },
                None,
                Formula::g(
                    Interval {
                        lower: 10,
                        upper: 20,
                    },
                    None,
                    b_a.clone(),
                ),
                Formula::g(
                    Interval {
                        lower: 20,
                        upper: 30,
                    },
                    None,
                    b_a.clone(),
                ),
            ),
            Formula::u(
                Interval {
                    lower: 10,
                    upper: 15,
                },
                None,
                Formula::g(
                    Interval {
                        lower: 0,
                        upper: 10,
                    },
                    None,
                    b_a.clone(),
                ),
                Formula::g(
                    Interval {
                        lower: 10,
                        upper: 20,
                    },
                    None,
                    b_a,
                ),
            ),
        );
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn until_globally_or() {
        let b_a = prop("B_a");
        let (res, exp) = make_test_shift_bounds(
            Formula::u(
                Interval { lower: 0, upper: 5 },
                None,
                Formula::g(
                    Interval {
                        lower: 10,
                        upper: 20,
                    },
                    None,
                    b_a.clone(),
                ),
                Formula::or(vec![
                    Formula::g(
                        Interval {
                            lower: 20,
                            upper: 30,
                        },
                        None,
                        b_a.clone(),
                    ),
                    b_a.clone(),
                ]),
            ),
            Formula::u(
                Interval { lower: 0, upper: 5 },
                None,
                Formula::g(
                    Interval {
                        lower: 10,
                        upper: 20,
                    },
                    None,
                    b_a.clone(),
                ),
                Formula::or(vec![
                    Formula::g(
                        Interval {
                            lower: 20,
                            upper: 30,
                        },
                        None,
                        b_a.clone(),
                    ),
                    b_a,
                ]),
            ),
        );
        assert_eq!(res.operands, exp.operands);
    }
}

mod flatten_tests {
    use super::*;

    #[test]
    fn flatten_and() {
        let p1 = prop("a");
        let p2 = prop("b");
        let p3 = prop("c");
        let res = make_test_flatten(Formula::and(vec![
            p1.clone(),
            Formula::and(vec![p2.clone(), p3.clone()]),
        ]));
        let exp = Node::from_operands(vec![p1, p2, p3]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn flatten_or() {
        let p1 = prop("a");
        let p2 = prop("b");
        let p3 = prop("c");
        let res = make_test_flatten(Formula::or(vec![
            p1.clone(),
            Formula::or(vec![p2.clone(), p3.clone()]),
        ]));
        let exp = Node::from_operands(vec![Formula::or(vec![p1, p2, p3])]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn flatten_mixed() {
        let p1 = prop("a");
        let p2 = prop("b");
        let p3 = prop("c");
        let p4 = prop("d");
        let p5 = prop("e");

        let res = make_test_flatten(Formula::and(vec![
            p1.clone(),
            Formula::or(vec![p2.clone(), p3.clone()]),
            p4.clone(),
            p5.clone(),
        ]));
        let exp = Node::from_operands(vec![p1, Formula::or(vec![p2, p3]), p4, p5]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn flatten_nested() {
        let p1 = prop("a");
        let p2 = prop("b");
        let p3 = prop("c");

        let res = make_test_flatten(Formula::g(
            Interval {
                lower: 0,
                upper: 10,
            },
            None,
            Formula::and(vec![p1.clone(), Formula::and(vec![p2.clone(), p3.clone()])]),
        ));
        let exp = Node::from_operands(vec![Formula::g(
            Interval {
                lower: 0,
                upper: 10,
            },
            None,
            Formula::and(vec![p1, p2, p3]),
        )]);
        assert_eq!(res.operands, exp.operands);
    }
}
