use std::sync::Arc;

use crate::{formula::{Expr, Formula, Interval}, node::Node};

fn prop(name: &str) -> Formula {
    Formula::prop(Expr::bool(Arc::from(name)))
}

fn make_test_rewrite_chain(input: Vec<Formula>, expected: Vec<Formula>, time_input: i32) -> (Node, Node) {
    let mut input_node: Node = Node::from_operands(input);
    input_node.current_time = time_input;
    input_node.flatten();
    input_node = input_node.rewrite_chain().unwrap_or(vec![input_node.clone()])[0].clone();
    let mut expected_node: Node = Node::from_operands(expected);
    expected_node.flatten();
    (input_node, expected_node)
}

mod rewrite_globally_tests {
    use super::*;

    #[test]
    fn no_rewrite() {
        let a = prop("a");
        let f = Formula::g(Interval { lower: 0, upper: 5 }, None, a);
        let (res, exp) = make_test_rewrite_chain(vec![
            f.clone()
        ], vec![
            f
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_containment() {
        let a = prop("a");
        let f1 = Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone());
        let f2 = Formula::g(Interval { lower: 1, upper: 4 }, None, a);
        let (res, exp) = make_test_rewrite_chain(vec![
            f1.clone(),
            f2.clone()
        ], vec![
            f1
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_union_intersection() {
        let a = prop("a");
        let f1 = Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone());
        let f2 = Formula::g(Interval { lower: 4, upper: 10 }, None, a.clone());
        let (res, exp) = make_test_rewrite_chain(vec![
            f1.clone(),
            f2.clone()
        ], vec![
            Formula::g(Interval { lower: 0, upper: 10 }, None, a)
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_union_contiguous() {
        let a = prop("a");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone()),
            Formula::g(Interval { lower: 6, upper: 10 }, None, a.clone())
        ], vec![
            Formula::g(Interval { lower: 0, upper: 10 }, None, a)
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_no_match() {
        let a = prop("a");
        let f = Formula::and(vec![
            Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone()),
            Formula::g(Interval { lower: 7, upper: 10 }, None, a)
        ]);
        let (res, exp) = make_test_rewrite_chain(vec![f.clone()], vec![f], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_multiple() {
        let a = prop("a");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone()),
            Formula::g(Interval { lower: 8, upper: 12 }, None, a.clone()),
            Formula::g(Interval { lower: 4, upper: 8 }, None, a.clone())
        ], vec![
            Formula::g(Interval { lower: 0, upper: 12 }, None, a)
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_multiple_one_excluded() {
        let a = prop("a");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone()),
            Formula::g(Interval { lower: 10, upper: 12 }, None, a.clone()),
            Formula::g(Interval { lower: 4, upper: 7 }, None, a.clone())
        ], vec![
            Formula::g(Interval { lower: 0, upper: 7 }, None, a.clone()),
            Formula::g(Interval { lower: 10, upper: 12 }, None, a)
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_single_count_match() {
        let a = prop("a");
        let b = prop("b");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::g(Interval { lower: 0, upper: 10 }, None, a.clone()),
            Formula::g(Interval { lower: 11, upper: 20 }, None, a.clone()),
            Formula::g(Interval { lower: 0, upper: 10 }, None, b.clone())
        ], vec![
            Formula::g(Interval { lower: 0, upper: 20 }, None, a),
            Formula::g(Interval { lower: 0, upper: 10 }, None, b)
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }
} 

mod rewrite_finally_tests {
    use super::*;

    #[test]
    fn no_rewrite() {
        let a = prop("a");
        let f = Formula::f(Interval { lower: 0, upper: 5 }, None, a);
        let (res, exp) = make_test_rewrite_chain(vec![f.clone()], vec![f], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_containment() {
        let a = prop("a");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone()),
            Formula::f(Interval { lower: 1, upper: 4 }, None, a.clone())
        ], vec![
            Formula::f(Interval { lower: 1, upper: 4 }, None, a)
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }
    
    #[test]
    fn rewrite_containment_2() {
        let a = prop("a");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::f(Interval { lower: 1, upper: 4 }, None, a.clone()),
            Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone())
        ], vec![
            Formula::f(Interval { lower: 1, upper: 4 }, None, a)
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_no_match() {
        let a = prop("a");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone()),
            Formula::f(Interval { lower: 4, upper: 10 }, None, a.clone())
        ], vec![
            Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone()),
            Formula::f(Interval { lower: 4, upper: 10 }, None, a)
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_multiple() {
        let a = prop("a");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::f(Interval { lower: 0, upper: 10 }, None, a.clone()),
            Formula::f(Interval { lower: 1, upper: 5 }, None, a.clone()),
            Formula::f(Interval { lower: 2, upper: 4 }, None, a.clone())
        ], vec![
            Formula::f(Interval { lower: 2, upper: 4 }, None, a)
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_multiple_one_excluded() {
        let a = prop("a");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone()),
            Formula::f(Interval { lower: 10, upper: 12 }, None, a.clone()),
            Formula::f(Interval { lower: 1, upper: 4 }, None, a.clone())
        ], vec![
            Formula::f(Interval { lower: 10, upper: 12 }, None, a.clone()),
            Formula::f(Interval { lower: 1, upper: 4 }, None, a.clone()),
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

     #[test]
    fn rewrite_single_count_match() {
        let a = prop("a");
        let b = prop("b");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::f(Interval { lower: 0, upper: 20 }, None, a.clone()),
            Formula::f(Interval { lower: 5, upper: 15 }, None, a.clone()),
            Formula::f(Interval { lower: 0, upper: 10 }, None, b.clone())
        ], vec![
            Formula::f(Interval { lower: 5, upper: 15 }, None, a),
            Formula::f(Interval { lower: 0, upper: 10 }, None, b)
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_equal() {
        let a = prop("a");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone()),
            Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone())
        ], vec![
            Formula::f(Interval { lower: 0, upper: 5 }, None, a)
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_equal_position() {
        let a = prop("a");
        let b = prop("b");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone()),
            b.clone(),
            Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone())
        ], vec![
            Formula::f(Interval { lower: 0, upper: 5 }, None, a.clone()),
            b,
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_finally_time_shift() {
        let a = prop("a");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::f(Interval { lower: 18, upper: 20 }, None, a.clone()),
            Formula::f(Interval { lower: 17, upper: 19 }, None, a.clone()),
            Formula::f(Interval { lower: 18, upper: 18 }, None, a.clone())
        ], vec![
            Formula::f(Interval { lower: 18, upper: 18 }, None, a)
        ], 18);
        assert_eq!(res.operands, exp.operands);
    }
}

mod rewrite_globally_finally_tests {
    use std::vec;

    use super::*;

    #[test]
    fn rewrite_no_match() {
        let a = prop("a");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone()),
            Formula::f(Interval { lower: 1, upper: 3 }, None, a.clone()),
            Formula::f(Interval { lower: 2, upper: 4 }, None, a.clone())
        ], vec![
            Formula::g(Interval { lower: 0, upper: 5 }, None, a.clone()),
            Formula::f(Interval { lower: 1, upper: 3 }, None, a.clone()),
            Formula::f(Interval { lower: 2, upper: 4 }, None, a)
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_match_simple() {
        let a = prop("a");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::g(Interval { lower: 0, upper: 5 }, None, Formula::f(Interval { lower: 0, upper: 3 }, None, a.clone())),
        ], vec![
            Formula::g(Interval { lower: 2, upper: 5 }, None, Formula::f(Interval { lower: 0, upper: 3 }, None, a.clone())),
            Formula::or(vec![
                Formula::f(Interval { lower: 1, upper: 3 }, None, a.clone()),
                Formula::and(vec![
                    Formula::f(Interval { lower: 0, upper: 0 }, None, a.clone()),
                    Formula::f(Interval { lower: 4, upper: 4 }, None, a.clone())
                ])
            ])
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_order() {
        let a = prop("a");
        let b = prop("b");
        let (res, exp) = make_test_rewrite_chain(vec![
            Formula::g(Interval { lower: 0, upper: 5 }, None, Formula::f(Interval { lower: 0, upper: 3 }, None, a.clone())),
            Formula::f(Interval { lower: 0, upper: 3 }, None, b.clone())
        ], vec![
            Formula::g(Interval { lower: 2, upper: 5 }, None, Formula::f(Interval { lower: 0, upper: 3 }, None, a.clone())),
            Formula::f(Interval { lower: 0, upper: 3 }, None, b.clone()),
            Formula::or(vec![
                Formula::f(Interval { lower: 1, upper: 3 }, None, a.clone()),
                Formula::and(vec![
                    Formula::f(Interval { lower: 0, upper: 0 }, None, a.clone()),
                    Formula::f(Interval { lower: 4, upper: 4 }, None, a.clone())
                ])
            ])
        ], 0);
        assert_eq!(res.operands, exp.operands);
    }
}