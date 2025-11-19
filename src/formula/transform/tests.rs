use crate::formula::{
    Expr, Formula, Interval,
    transform::{
        FlatTransformer, NegationNormalFormTransformer, RecursiveFormulaTransformer,
        STLTransformer, ShiftBoundsTransformer,
    },
};
use std::sync::Arc;

fn prop(name: &str) -> Formula {
    Formula::prop(Expr::bool(Arc::from(name)))
}

fn make_test_push_negation(input: Formula) -> Formula {
    NegationNormalFormTransformer.visit(&input)
}

fn make_test_shift_bounds(input: Formula) -> Formula {
    ShiftBoundsTransformer.visit(&input)
}

fn make_test_flatten(input: Formula) -> Formula {
    FlatTransformer.visit(&input)
}

fn make_test_rewrite_stl(input: Formula) -> Formula {
    STLTransformer.visit(&input)
}

mod push_negation_tests {
    use super::*;

    #[test]
    fn push_negation_prop() {
        let p = prop("a");
        let res = make_test_push_negation(Formula::not(p.clone()));
        assert_eq!(res, Formula::not(p));
    }

    #[test]
    fn push_negation_double_negation() {
        let a = prop("a");
        let input_formula = Formula::not(Formula::not(a.clone()));
        let result_formula = a;
        let res = make_test_push_negation(input_formula);
        assert_eq!(res, result_formula);
    }

    #[test]
    fn push_negation_not_and() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::not(Formula::and(vec![a.clone(), b.clone()]));
        let result_formula = Formula::or(vec![Formula::not(a), Formula::not(b)]);
        let res = make_test_push_negation(input_formula);
        assert_eq!(res, result_formula);
    }

    #[test]
    fn push_negation_not_or() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::not(Formula::or(vec![a.clone(), b.clone()]));
        let result_formula = Formula::and(vec![Formula::not(a), Formula::not(b)]);
        let res = make_test_push_negation(input_formula);
        assert_eq!(res, result_formula);
    }

    #[test]
    fn push_negation_not_imply() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::not(Formula::imply(a.clone(), b.clone()));
        let result_formula = Formula::and(vec![a, Formula::not(b)]);
        let res = make_test_push_negation(input_formula);
        assert_eq!(res, result_formula);
    }

    #[test]
    fn push_negation_not_globally() {
        let a = prop("a");
        let input_formula = Formula::not(Formula::g(Interval { lower: 0, upper: 5 }, a.clone()));
        let result_formula = Formula::f(Interval { lower: 0, upper: 5 }, Formula::not(a));
        let res = make_test_push_negation(input_formula);
        assert_eq!(res, result_formula);
    }

    #[test]
    fn push_negation_not_finally() {
        let a = prop("a");
        let input_formula = Formula::not(Formula::f(Interval { lower: 0, upper: 5 }, a.clone()));
        let result_formula = Formula::g(Interval { lower: 0, upper: 5 }, Formula::not(a));
        let res = make_test_push_negation(input_formula);
        assert_eq!(res, result_formula);
    }

    #[test]
    fn push_negation_not_until() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::not(Formula::u(
            Interval { lower: 0, upper: 5 },
            a.clone(),
            b.clone(),
        ));
        let result_formula = Formula::r(
            Interval { lower: 0, upper: 5 },
            Formula::not(a),
            Formula::not(b),
        );
        let res = make_test_push_negation(input_formula);
        assert_eq!(res, result_formula);
    }

    #[test]
    fn push_negation_not_release() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::not(Formula::r(
            Interval { lower: 0, upper: 5 },
            a.clone(),
            b.clone(),
        ));
        let result_formula = Formula::u(
            Interval { lower: 0, upper: 5 },
            Formula::not(a),
            Formula::not(b),
        );
        let res = make_test_push_negation(input_formula);
        assert_eq!(res, result_formula);
    }

    #[test]
    fn push_negation_nested_globally_and() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::not(Formula::g(
            Interval { lower: 0, upper: 5 },
            Formula::and(vec![a.clone(), b.clone()]),
        ));
        let result_formula = Formula::f(
            Interval { lower: 0, upper: 5 },
            Formula::or(vec![Formula::not(a), Formula::not(b)]),
        );
        let res = make_test_push_negation(input_formula);
        assert_eq!(res, result_formula);
    }

    #[test]
    fn push_negation_nested_until_or() {
        let a = prop("a");
        let b = prop("b");
        let c = prop("c");
        let input_formula = Formula::not(Formula::u(
            Interval { lower: 0, upper: 5 },
            a.clone(),
            Formula::or(vec![b.clone(), c.clone()]),
        ));
        let result_formula = Formula::r(
            Interval { lower: 0, upper: 5 },
            Formula::not(a),
            Formula::and(vec![Formula::not(b), Formula::not(c)]),
        );
        let res = make_test_push_negation(input_formula);
        assert_eq!(res, result_formula);
    }

    #[test]
    fn push_negation_inside() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::g(
            Interval { lower: 0, upper: 5 },
            Formula::not(Formula::and(vec![a.clone(), b.clone()])),
        );
        let result_formula = Formula::g(
            Interval { lower: 0, upper: 5 },
            Formula::or(vec![Formula::not(a), Formula::not(b)]),
        );
        let res = make_test_push_negation(input_formula);
        assert_eq!(res, result_formula);
    }
}

mod shift_bounds_tests {
    use super::*;

    #[test]
    fn no_shift() {
        let a = prop("a");
        let res = make_test_shift_bounds(Formula::g(Interval { lower: 0, upper: 5 }, a.clone()));
        let exp = Formula::g(Interval { lower: 0, upper: 5 }, a);
        assert_eq!(res, exp);
    }

    #[test]
    fn nested_globally_finally() {
        let b_a = prop("B_a");
        let res = make_test_shift_bounds(Formula::g(
            Interval {
                lower: 3,
                upper: 50,
            },
            Formula::f(
                Interval {
                    lower: 5,
                    upper: 20,
                },
                b_a.clone(),
            ),
        ));
        let exp = Formula::g(
            Interval {
                lower: 8,
                upper: 55,
            },
            Formula::f(
                Interval {
                    lower: 0,
                    upper: 15,
                },
                b_a,
            ),
        );
        assert_eq!(res, exp);
    }

    #[test]
    fn no_shift_complex() {
        let b_a = prop("B_a");
        let input = Formula::g(
            Interval {
                lower: 10,
                upper: 60,
            },
            Formula::imply(
                b_a.clone(),
                Formula::g(
                    Interval {
                        lower: 20,
                        upper: 40,
                    },
                    Formula::not(b_a),
                ),
            ),
        );
        let res = make_test_shift_bounds(input.clone());
        assert_eq!(res, input);
    }

    #[test]
    fn nested_finally_globally() {
        let b_a = prop("B_a");
        let input = Formula::g(
            Interval {
                lower: 3,
                upper: 50,
            },
            Formula::f(
                Interval {
                    lower: 5,
                    upper: 20,
                },
                Formula::f(
                    Interval {
                        lower: 20,
                        upper: 30,
                    },
                    Formula::g(
                        Interval {
                            lower: 20,
                            upper: 40,
                        },
                        Formula::not(b_a.clone()),
                    ),
                ),
            ),
        );
        let res = make_test_shift_bounds(input);
        let exp = Formula::g(
            Interval {
                lower: 48,
                upper: 95,
            },
            Formula::f(
                Interval {
                    lower: 0,
                    upper: 15,
                },
                Formula::f(
                    Interval {
                        lower: 0,
                        upper: 10,
                    },
                    Formula::g(
                        Interval {
                            lower: 0,
                            upper: 20,
                        },
                        Formula::not(b_a),
                    ),
                ),
            ),
        );
        assert_eq!(res, exp);
    }

    #[test]
    fn finally_and_globally() {
        let b_a = prop("B_a");
        let input = Formula::f(
            Interval { lower: 0, upper: 5 },
            Formula::and(vec![
                Formula::g(
                    Interval {
                        lower: 10,
                        upper: 20,
                    },
                    b_a.clone(),
                ),
                Formula::g(
                    Interval {
                        lower: 20,
                        upper: 30,
                    },
                    b_a.clone(),
                ),
            ]),
        );
        let res = make_test_shift_bounds(input);
        let exp = Formula::f(
            Interval {
                lower: 10,
                upper: 15,
            },
            Formula::and(vec![
                Formula::g(
                    Interval {
                        lower: 0,
                        upper: 10,
                    },
                    b_a.clone(),
                ),
                Formula::g(
                    Interval {
                        lower: 10,
                        upper: 20,
                    },
                    b_a,
                ),
            ]),
        );
        assert_eq!(res, exp);
    }

    #[test]
    fn until_globally() {
        let b_a = prop("B_a");
        let input = Formula::u(
            Interval { lower: 0, upper: 5 },
            Formula::g(
                Interval {
                    lower: 10,
                    upper: 20,
                },
                b_a.clone(),
            ),
            Formula::g(
                Interval {
                    lower: 20,
                    upper: 30,
                },
                b_a.clone(),
            ),
        );
        let res = make_test_shift_bounds(input);
        let exp = Formula::u(
            Interval {
                lower: 10,
                upper: 15,
            },
            Formula::g(
                Interval {
                    lower: 0,
                    upper: 10,
                },
                b_a.clone(),
            ),
            Formula::g(
                Interval {
                    lower: 10,
                    upper: 20,
                },
                b_a,
            ),
        );
        assert_eq!(res, exp);
    }

    #[test]
    fn until_globally_or() {
        let b_a = prop("B_a");
        let input = Formula::u(
            Interval { lower: 0, upper: 5 },
            Formula::g(
                Interval {
                    lower: 10,
                    upper: 20,
                },
                b_a.clone(),
            ),
            Formula::or(vec![
                Formula::g(
                    Interval {
                        lower: 20,
                        upper: 30,
                    },
                    b_a.clone(),
                ),
                b_a.clone(),
            ]),
        );
        let res = make_test_shift_bounds(input);
        let exp = Formula::u(
            Interval { lower: 0, upper: 5 },
            Formula::g(
                Interval {
                    lower: 10,
                    upper: 20,
                },
                b_a.clone(),
            ),
            Formula::or(vec![
                Formula::g(
                    Interval {
                        lower: 20,
                        upper: 30,
                    },
                    b_a.clone(),
                ),
                b_a,
            ]),
        );
        assert_eq!(res, exp);
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
        let exp = Formula::and(vec![p1, p2, p3]);
        assert_eq!(res, exp);
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
        let exp = Formula::or(vec![p1, p2, p3]);
        assert_eq!(res, exp);
    }

    #[test]
    fn flatten_mixed() {
        let p1 = prop("a");
        let p2 = prop("b");
        let p3 = prop("c");
        let p4 = prop("d");
        let p5 = prop("e");

        let input = Formula::and(vec![
            p1.clone(),
            Formula::or(vec![p2.clone(), p3.clone()]),
            p4.clone(),
            p5.clone(),
        ]);
        let res = make_test_flatten(input.clone());
        assert_eq!(res, input);
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
            Formula::and(vec![p1.clone(), Formula::and(vec![p2.clone(), p3.clone()])]),
        ));
        let exp = Formula::g(
            Interval {
                lower: 0,
                upper: 10,
            },
            Formula::and(vec![p1, p2, p3]),
        );
        assert_eq!(res, exp);
    }
}

mod stl_rewrite_tests {
    use super::*;

    #[test]
    fn rewrite_until() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::u(Interval { lower: 2, upper: 5 }, a.clone(), b.clone());
        let result_formula = Formula::and(vec![
            Formula::g(Interval { lower: 0, upper: 2 }, a.clone()),
            Formula::u(
                Interval { lower: 2, upper: 5 },
                a.clone(),
                Formula::and(vec![a, b]),
            ),
        ]);
        let res = make_test_rewrite_stl(input_formula);
        assert_eq!(res, result_formula);
    }

    #[test]
    fn rewrite_release() {
        let a = prop("a");
        let b = prop("b");
        let input_formula = Formula::r(Interval { lower: 3, upper: 7 }, a.clone(), b.clone());
        let result_formula = Formula::or(vec![
            Formula::f(Interval { lower: 0, upper: 3 }, a.clone()),
            Formula::u(Interval { lower: 3, upper: 7 }, b.clone(), a),
            Formula::g(Interval { lower: 3, upper: 7 }, b),
        ]);
        let res = make_test_rewrite_stl(input_formula);
        assert_eq!(res, result_formula);
    }
}
