use std::sync::Arc;

use crate::formula::{statistics::Formula, Expr, Interval, AExpr, RelOp};

fn prop(name: &str) -> Formula {
    Formula::prop(Expr::bool(Arc::from(name)))
}

mod depth_tests {
    use super::*;

    #[test]
    fn test_prop() {
        let f = prop("a");
        assert_eq!(f.depth(), 1);
    }

    #[test]
    fn test_nested() {
        let f = Formula::And(vec![
            Formula::or(vec![
                prop("a"),
                Formula::Not(Box::new(prop("b"))),
            ]),
            Formula::u (
                Interval { lower: 0, upper: 5},
                None,
                prop("c"),
                Formula::g (
                    Interval { lower: 1, upper: 3},
                    None,
                    prop("d")
                )
            ),
        ]);
        assert_eq!(f.depth(), 4);
    }
}

mod length_tests {
    use super::*;

    #[test]
    fn test_prop() {
        let f = prop("a");
        assert_eq!(f.length(), 0);
    }

    #[test]
    fn test_nested() {
        let f = Formula::And(vec![
            Formula::or(vec![
                prop("a"),
                Formula::Not(Box::new(prop("b"))),
            ]),
            Formula::u (
                Interval { lower: 0, upper: 5},
                None,
                prop("c"),
                Formula::g (
                    Interval { lower: 1, upper: 3},
                    None,
                    prop("d")
                )
            ),
        ]);
        assert_eq!(f.length(), 8);
    }

}

mod boolean_variables_tests {
    use super::*;

    #[test]
    fn test_nested_no_rep() {
        let f = Formula::And(vec![
            Formula::or(vec![
                prop("a"),
                Formula::Not(Box::new(prop("b"))),
            ]),
            Formula::u (
                Interval { lower: 0, upper: 5},
                None,
                prop("c"),
                Formula::g (
                    Interval { lower: 1, upper: 3},
                    None,
                    prop("d")
                )
            ),
        ]);
        assert_eq!(f.boolean_variables(), 4);
    }

    #[test]
    fn test_nested_with_rep() {
        let f = Formula::And(vec![
            Formula::or(vec![
                prop("a"),
                Formula::Not(Box::new(prop("b"))),
            ]),
            Formula::u (
                Interval { lower: 0, upper: 5},
                None,
                prop("c"),
                Formula::g (
                    Interval { lower: 1, upper: 3},
                    None,
                    prop("a")
                )
            ),
        ]);
        assert_eq!(f.boolean_variables(), 3);
    }
}

mod real_variables_tests {

    use num_rational::Ratio;

    use super::*;

    #[test]
    fn test_nested_no_rep() {
        let f = Formula::And(vec![
            Formula::Prop(Expr::real(
                RelOp::Ge,
                AExpr::Var(Arc::from("x")),
                AExpr::Num(Ratio::from_integer(1)),
            )),
            Formula::u (
                Interval { lower: 0, upper: 5},
                None,
                Formula::Prop(Expr::real(
                    RelOp::Lt,
                    AExpr::Var(Arc::from("y")),
                    AExpr::Num(Ratio::from_integer(2)),
                )),
                Formula::g (
                    Interval { lower: 1, upper: 3},
                    None,
                    Formula::Prop(Expr::real(
                        RelOp::Eq,
                        AExpr::Var(Arc::from("z")),
                        AExpr::Num(Ratio::from_integer(3))
                    )),
                )
            ),
        ]);
        assert_eq!(f.real_variables(), 3);
    }

    #[test]
    fn test_nested_rep() {
        let f = Formula::And(vec![
            Formula::Prop(Expr::real(
                RelOp::Ge,
                AExpr::Var(Arc::from("x")),
                AExpr::Num(Ratio::from_integer(1)),
            )),
            Formula::u (
                Interval { lower: 0, upper: 5},
                None,
                Formula::Prop(Expr::real(
                    RelOp::Lt,
                    AExpr::Var(Arc::from("y")),
                    AExpr::Num(Ratio::from_integer(2)),
                )),
                Formula::g (
                    Interval { lower: 1, upper: 3},
                    None,
                    Formula::Prop(Expr::real(
                        RelOp::Eq,
                        AExpr::Var(Arc::from("x")),
                        AExpr::Num(Ratio::from_integer(3))
                    )),
                )
            ),
        ]);
        assert_eq!(f.real_variables(), 2);
    }
}