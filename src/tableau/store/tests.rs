use crate::{formula::parser::parse_formula, node::Node, tableau::store::{RejectedNode, Store}};


fn make_check_rejected_test(store_content: Vec<&str>, test_node: &str) -> bool {
    let mut store = Store::new();
    for content in store_content {
        let (_, formula) = parse_formula(content).expect("Failed to parse formula");
        let mut node = Node::from_operands(vec![formula]);
        node.flatten();
        let rejected = RejectedNode::from_node(&node);
        store.add_rejected(rejected);
    }
    let (_, test_formula) = parse_formula(test_node).expect("Failed to parse test formula");
    let mut test_node = Node::from_operands(vec![test_formula]);
    test_node.flatten();
    let rejected_test_node = RejectedNode::from_node(&test_node);
    return store.check_rejected(&rejected_test_node);
}

#[test]
fn test_empty_store() {
    assert_eq!(make_check_rejected_test(vec![], "G[0, 10] a"), false);
}

#[test]
fn test_globally() {
    assert_eq!(make_check_rejected_test(vec!["G[0, 10] a"], "G[2, 5] a"), false);
    assert_eq!(make_check_rejected_test(vec!["G[0, 10] a"], "G[0, 10] a"), true);
    assert_eq!(make_check_rejected_test(vec!["G[0, 10] a"], "G[0, 15] a"), true);
}

#[test]
fn test_finally() {
    assert_eq!(make_check_rejected_test(vec!["F[0, 10] a"], "F[2, 5] a"), true);
    assert_eq!(make_check_rejected_test(vec!["F[0, 10] a"], "F[0, 10] a"), true);
    assert_eq!(make_check_rejected_test(vec!["F[0, 10] a"], "F[0, 15] a"), false);
}

#[test]
fn test_complex() {
    assert_eq!(make_check_rejected_test(
        vec!["G[0,16] (angle >= 80 -> G[20,40] angle < 60) && G[0,11] F[0,15] angle >= 80 && G[0,20] angle < 60"], 
        "G[9,29] (angle >= 80 -> F[1,20] pos <= 0) && G[0,49] (angle >= 80 -> G[20,40] angle < 60) && G[1,44] F[0,15] angle >= 80 && G[13,13] angle >= 80 && G[15,15] angle >= 80 && G[19,49] angle < 60)"
    ), true);
}