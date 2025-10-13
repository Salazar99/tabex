use crate::formula::parser::parse_formula;

#[test]
fn test_parse_simple_proposition() {
    let input = "a";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_true() {
    let input = "TRUE";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_false() {
    let input = "FALSE";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_negation() {
    let input = "!a";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_conjunction() {
    let input = "a && b";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_disjunction() {
    let input = "a || b";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_implication() {
    let input = "a -> b";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_globally() {
    let input = "G[0,10] a";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_finally() {
    let input = "F[1,5] b";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_until() {
    let input = "a U[2,8] b";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_release() {
    let input = "a R[3,7] b";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_with_parentheses() {
    let input = "(a && b)";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_parentheses_nested() {
    let input = "(TRUE -> (a -> b))";
    let result = parse_formula(input);
    assert!(result.is_ok());
}

#[test]
fn test_parse_parentheses_space() {
    let input = "( a && b )";
    let result = parse_formula(input);
    assert!(result.is_ok());
}