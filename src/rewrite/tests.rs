use crate::{node::Node, parser::parse_formula, rewrite::{rewrite_chain}};

fn make_test_push_negation(input: &str, result: &str) -> (Node, Node) {
    let (_, input_formula) = parse_formula(input).unwrap();
    let mut input_node: Node = Node::from_operands(vec![input_formula]);
    input_node.push_negation();
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

fn make_test_rewrite_chain(input: &str, expected: &str) -> (Node, Node) {
    let (_, input_formula) = parse_formula(input).unwrap();
    let mut input_node: Node = Node::from_operands(vec![input_formula]);
    input_node.flatten();
    input_node.operands = rewrite_chain(&input_node.operands, input_node.current_time).unwrap_or(input_node.operands);
    let (_, expected_formula) = parse_formula(expected).unwrap();
    let mut expected_node: Node = Node::from_operands(vec![expected_formula]);
    expected_node.flatten();
    (input_node, expected_node)
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
            Formula::Prop(Expr::Atom(Arc::from("a"))),
            Formula::Prop(Expr::Atom(Arc::from("b"))),
            Formula::Prop(Expr::Atom(Arc::from("c"))),
        ]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn flatten_or() {
        let res = make_test_flatten("(a || (b || c))");
        let exp = Node::from_operands(vec![
            Formula::Or(vec![
                Formula::Prop(Expr::Atom(Arc::from("a"))),
                Formula::Prop(Expr::Atom(Arc::from("b"))),
                Formula::Prop(Expr::Atom(Arc::from("c"))),
            ])
        ]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn flatten_mixed() {
        let res = make_test_flatten("(a && ((b || c) && (d && e)))");
        let exp = Node::from_operands(vec![
            Formula::Prop(Expr::Atom(Arc::from("a"))),
            Formula::Or(vec![
                Formula::Prop(Expr::Atom(Arc::from("b"))),
                Formula::Prop(Expr::Atom(Arc::from("c"))),
            ]),
            Formula::Prop(Expr::Atom(Arc::from("d"))),
            Formula::Prop(Expr::Atom(Arc::from("e"))),
        ]);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn flatten_nested() {
        let res = make_test_flatten("G[0, 10] ((a && b) && c)");
        let exp = Node::from_operands(vec![
            Formula::G { parent_upper: None, interval: Interval { lower: 0, upper: 10 }, phi: Box::new(
                Formula::And(vec![
                    Formula::Prop(Expr::Atom(Arc::from("a"))),
                    Formula::Prop(Expr::Atom(Arc::from("b"))),
                    Formula::Prop(Expr::Atom(Arc::from("c"))),
                ])
            )}
        ]);
        assert_eq!(res.operands, exp.operands);
    }
}

mod rewrite_globally_tests {
    use super::*;

    #[test]
    fn no_rewrite() {
        let (res, exp) = make_test_rewrite_chain("G[0,5] a", "G[0,5] a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_containment() {
        let (res, exp) = make_test_rewrite_chain("G[0,5] a && G[1,4] a", "G[0,5] a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_union_intersection() {
        let (res, exp) = make_test_rewrite_chain("G[0,5] a && G[4,10] a", "G[0,10] a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_union_contiguous() {
        let (res, exp) = make_test_rewrite_chain("G[0,5] a && G[6,10] a", "G[0,10] a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_no_match() {
        let (res, exp) = make_test_rewrite_chain("G[0,5] a && G[7,10] a", "G[0,5] a && G[7,10] a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_multiple() {
        let (res, exp) = make_test_rewrite_chain("G[0,5] a && G[8,12] a && G[4,8] a", "G[0,12] a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_multiple_one_excluded() {
        let (res, exp) = make_test_rewrite_chain("G[0,5] a && G[10,12] a && G[4,7] a", "G[0,7] a && G[10,12] a" );
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_single_count_match() {
        let (res, exp) = make_test_rewrite_chain("G[0,10] a && G[11, 20] a && G[0, 10] b", "G[0,20] a && G[0, 10] b");
        assert_eq!(res.operands, exp.operands);
    }
} 

mod rewrite_finally_tests {
    use super::*;

    #[test]
    fn no_rewrite() {
        let (res, exp) = make_test_rewrite_chain("F[0,5] a", "F[0,5] a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_containment() {
        let (res, exp) = make_test_rewrite_chain("F[0,5] a && F[1,4] a", "F[1,4] a");
        assert_eq!(res.operands, exp.operands);
    }
    
    #[test]
    fn rewrite_containment_2() {
        let (res, exp) = make_test_rewrite_chain("F[1,4] a && F[0,5] a", "F[1,4] a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_no_match() {
        let (res, exp) = make_test_rewrite_chain("F[0,5] a && F[4,10] a", "F[0,5] a && F[4,10] a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_multiple() {
        let (res, exp) = make_test_rewrite_chain("F[0,10] a && F[1,5] a && F[2,4] a", "F[2,4] a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_multiple_one_excluded() {
        let (res, exp) = make_test_rewrite_chain("F[0,5] a && F[10,12] a && F[1,4] a", "F[10,12] a && F[1,4] a");
        assert_eq!(res.operands, exp.operands);
    }

     #[test]
    fn rewrite_single_count_match() {
        let (res, exp) = make_test_rewrite_chain("F[0,20] a && F[5, 15] a && F[0, 10] b", "F[5,15] a && F[0, 10] b");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_equal() {
        let (res, exp) = make_test_rewrite_chain("F[0,5] a && F[0,5] a", "F[0,5] a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_equal_position() {
        let (res, exp) = make_test_rewrite_chain("F[0,5] a && b && F[0,5] a", "F[0,5] a && b");
        assert_eq!(res.operands, exp.operands);
    }
}

mod rewrite_globally_finally_tests {
    use super::*;

    #[test]
    fn rewrite_no_match() {
        let (res, exp) = make_test_rewrite_chain("G[0,5] a && F[1,3] a && F[2,4] a", "G[0,5] a && F[1,3] a && F[2,4] a");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_match_simple() {
        let (res, exp) = make_test_rewrite_chain("G[0,5] F[0,3] a", "G[2,5] F[0, 3] a && (F[1, 3] a || G[0, 0] a && G[4, 4] a)");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_order() {
        let (res, exp) = make_test_rewrite_chain("G[0,5] F[0,3] a && F[0,3] b", "G[2,5] F[0, 3] a && F[0,3] b && (F[1, 3] a || G[0, 0] a && G[4, 4] a)");
        assert_eq!(res.operands, exp.operands);
    }
}