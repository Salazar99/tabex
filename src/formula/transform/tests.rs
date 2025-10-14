use crate::{formula::parser::parse_formula, node::Node};



fn make_test_push_negation(input: &str, result: &str) -> (Node, Node) {
    let (_, input_formula) = parse_formula(input).unwrap();
    let mut input_node: Node = Node::from_operands(vec![input_formula]);
    input_node.negative_normal_form_rewrite();
    let (_, result_formula) = parse_formula(result).unwrap();
    let result_node: Node = Node::from_operands(vec![result_formula]);
    (input_node, result_node)
}

fn make_test_shift_bounds(input: &str, result: &str) -> (Node, Node) {
    let (_, input_formula) = parse_formula(input).unwrap();
    let mut input_node: Node = Node::from_operands(vec![input_formula]);
    input_node.shift_bounds();
    let (_, result_formula) = parse_formula(result).unwrap();
    let result_node: Node = Node::from_operands(vec![result_formula]);
    (input_node, result_node)
}

fn make_test_flatten(input: &str) -> Node {
    let (_, input_formula) = parse_formula(input).unwrap();
    let mut input_node: Node = Node::from_operands(vec![input_formula]);
    input_node.flatten();
    input_node
}

mod push_negation_tests {
    use super::*;

    #[test]
    fn push_negation_prop() {
        let (res, exp) = make_test_push_negation("!a", "!a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_double_negation() {
        let (res, exp) = make_test_push_negation("!!a", "a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_and() {
        let (res, exp) = make_test_push_negation("!(a && b)", "(!a || !b)");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_or() {
        let (res, exp) = make_test_push_negation("!(a || b)", "(!a && !b)");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_imply() {
        let (res, exp) = make_test_push_negation("!(a -> b)", "(a && !b)");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_globally() {
        let (res, exp) = make_test_push_negation("!(G[0,5] a)", "F[0,5] (!a)");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_finally() {
        let (res, exp) = make_test_push_negation("!(F[0,5] a)", "G[0,5] (!a)");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_until() {
        let (res, exp) = make_test_push_negation("!(a U[0,5] b)", "(!a R[0,5] !b)");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_release() {
        let (res, exp) = make_test_push_negation("!(a R[0,5] b)", "(!a U[0,0] !b)");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_not_next() {
        let (res, exp) = make_test_push_negation("!(O a)", "O (!a)");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_nested_globally_and() {
        let (res, exp) = make_test_push_negation("!(G[0,5] (a && b))", "F[0,5] (!a || !b)");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_nested_until_or() {
        let (res, exp) = make_test_push_negation("!(a U[0,5] (b || c))", "(!a R[0,5] (!b && !c))");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn push_negation_inside() {
        let (res, exp) = make_test_push_negation("G[0,5] !(a && b)", "G[0,5] (!a || !b)");
        assert_eq!(res.operands, exp.operands);
    }
}

mod shift_bounds_tests {
    use super::*;

    #[test]
    fn no_shift() {
        let (res, exp) = make_test_shift_bounds("G[0,5] a", "G[0,5] a");
        assert_eq!(res.operands, exp.operands);
    }
    
    #[test]
    fn nested_globally_finally() {
        let (res, exp) = make_test_shift_bounds("G[3,50] (F[5,20] (B_a))", "G[8,55] (F[0,15] (B_a))");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn no_shift_complex() {
        let (res, exp) = make_test_shift_bounds(
            "G[10,60] ((B_a) -> (G[20,40] (!(B_a))))",
            "G[10,60] ((B_a) -> (G[20,40] (!(B_a))))"
        );
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn nested_finally_globally() {
        let (res, exp) = make_test_shift_bounds(
            "G[3,50] (F[5,20] (F[20,30] (G[20,40] (!(B_a)))))",
            "G[48,95] (F[0,15] (F[0,10] (G[0,20] (!(B_a)))))"
        );
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn finally_and_globally() {
        let (res, exp) = make_test_shift_bounds(
            "F[0,5] ((G[10,20] (B_a)) && (G[20,30] (B_a)))",
            "F[10,15] ((G[0,10] (B_a)) && (G[10,20] (B_a)))"
        );
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn until_globally() {
        let (res, exp) = make_test_shift_bounds(
            "(G[10,20] (B_a)) U[0,5] (G[20,30] (B_a))",
            "(G[0,10] (B_a)) U[10,15] (G[10,20] (B_a))"
        );
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn until_globally_or() {
        let (res, exp) = make_test_shift_bounds(
            "(G[10,20] (B_a)) U[0,5] ((G[20,30] (B_a)) || (B_a))",
            "(G[10,20] (B_a)) U[0,5] ((G[20,30] (B_a)) || (B_a))"
        );
        assert_eq!(res.operands, exp.operands);
    }
}

mod flatten_tests {
    use std::sync::Arc;

    use crate::formula::{Expr, Formula, Interval};

    use super::*;

    #[test]
    fn flatten_and() {
        let res = make_test_flatten("(a && (b && c))");
        let exp = Node::from_operands(vec![
            Formula::prop(Expr::bool(Arc::from("a"))),
            Formula::prop(Expr::bool(Arc::from("b"))),
            Formula::prop(Expr::bool(Arc::from("c"))),
        ]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn flatten_or() {
        let res = make_test_flatten("(a || (b || c))");
        let exp = Node::from_operands(vec![
            Formula::or(vec![
                Formula::prop(Expr::bool(Arc::from("a"))),
                Formula::prop(Expr::bool(Arc::from("b"))),
                Formula::prop(Expr::bool(Arc::from("c"))),
            ])
        ]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn flatten_mixed() {
        let res = make_test_flatten("(a && ((b || c) && (d && e)))");
        let exp = Node::from_operands(vec![
            Formula::prop(Expr::bool(Arc::from("a"))),
            Formula::or(vec![
                Formula::prop(Expr::bool(Arc::from("b"))),
                Formula::prop(Expr::bool(Arc::from("c"))),
            ]),
            Formula::prop(Expr::bool(Arc::from("d"))),
            Formula::prop(Expr::bool(Arc::from("e"))),
        ]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn flatten_nested() {
        let res = make_test_flatten("G[0, 10] ((a && b) && c)");
        let exp = Node::from_operands(vec![
            Formula::g(Interval { lower: 0, upper: 10 }, None,
                Formula::and(vec![
                    Formula::prop(Expr::bool(Arc::from("a"))),
                    Formula::prop(Expr::bool(Arc::from("b"))),
                    Formula::prop(Expr::bool(Arc::from("c"))),
                ])
            )
        ]);
        assert_eq!(res.operands, exp.operands);
    }
}
