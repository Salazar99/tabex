use crate::{node::Node, parser::parse_formula};

fn make_test_rewrite_chain(input: &str, expected: &str) -> (Node, Node) {
    let (_, input_formula) = parse_formula(input).unwrap();
    let mut input_node: Node = Node::from_operands(vec![input_formula]);
    input_node.flatten();
    input_node = input_node.rewrite_chain().unwrap_or(vec![input_node.clone()])[0].clone();
    let (_, expected_formula) = parse_formula(expected).unwrap();
    let mut expected_node: Node = Node::from_operands(vec![expected_formula]);
    expected_node.flatten();
    (input_node, expected_node)
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
        let (res, exp) = make_test_rewrite_chain("G[0,5] F[0,3] a", "G[2,5] F[0, 3] a && (F[1, 3] a || F[0, 0] a && F[4, 4] a)");
        assert_eq!(res.operands, exp.operands);
    }

    #[test]
    fn rewrite_order() {
        let (res, exp) = make_test_rewrite_chain("G[0,5] F[0,3] a && F[0,3] b", "G[2,5] F[0, 3] a && F[0,3] b && (F[1, 3] a || F[0, 0] a && F[4, 4] a)");
        assert_eq!(res.operands, exp.operands);
    }
}