mod tests {
    use super::*;
    use crate::{node::Node, parser::parse_formula};

    fn make_test_push_negation(input: &str, result: &str) -> (Node, Node) {
        let (_, input_formula) = parse_formula(input).unwrap();
        let mut input_node: Node = Node::from_operands(vec![input_formula]);
        input_node.push_negation();
        let (_, result_formula) = parse_formula(result).unwrap();
        let result_node: Node = Node::from_operands(vec![result_formula]);
        (input_node, result_node)
    }

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