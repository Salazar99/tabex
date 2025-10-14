use crate::{tableau::{Tableau, TableauOptions}};

fn make_test(formula_str: &str, mltl: bool) -> Option<bool> {
    let options = TableauOptions {
        max_depth: 10000,
        graph_output: false,
        memoization: true,
        simple_first: true,
        formula_optimizations: true,
        jump_rule_enabled: true,
        mltl: mltl,
        smtlib_result: false,
    };
    let mut tableau = Tableau::new(options);
    tableau.make_tableau(formula_str)
}

#[test]
fn test_and() {
    assert_eq!(make_test("a && b", false), Some(true));
}

#[test]
fn test_many_ops() {
    assert_eq!(make_test("a && b && c && (a || b || c) && d", false), Some(true));
}

#[test]
fn test_true() {
    assert_eq!(make_test("a && !TrUe", false), Some(false));
}

#[test]
fn test_false() {
    assert_eq!(make_test("a && FaLsE", false), Some(false));
}

#[test]
fn test_globally0() {
    assert_eq!(make_test("G[2,5] (R_x > 5 || R_x < 0)", false), Some(true));
}

#[test]
fn test_globally_add() {
    assert_eq!(make_test("G[2,5] (R_x + R_y > 5 && R_x - R_y < 0)", false), Some(true));
}

#[test]
fn test_globally_add_many() {
    assert_eq!(make_test("G[2,5] (R_x + R_y - R_z + R_x > 5 && R_x - R_y < 0)", false), Some(true));
}

#[test]
fn test_release() {
    assert_eq!(make_test("(R_x == 10) R[1,6] (R_x < 10)", false), Some(true));
}

#[test]
fn test_abs() {
    assert_eq!(make_test("G[0,5] (|x| > 20 || |x| < 10) && F[0,5] (x == -15)", false), Some(false));
}

#[test]
fn test_mltl() {
    let formula = "F[58,92] ((a1) U[87,100] ((a1 && a0 && ! a1) U[9,100] (a0)))";
    assert_eq!(make_test(formula, false), Some(false));
    assert_eq!(make_test(formula, true), Some(true));
}

#[test]
fn test_release_false() {
    assert_eq!(make_test("false R[0,10] a", false), Some(true));
}

#[test]
fn test_gfgg() {
    assert_eq!(make_test("G[0,6] F[2,4] a && G[0,6] (a -> G[1,3] !a)", false), Some(false));
}

#[test]
fn test_jump1_0() {
    assert_eq!(make_test("!a && G[10,20] !a && F[0,20] a", false), Some(true));
}

#[test]
fn test_jump1_g() {
    assert_eq!(make_test("G[0,10] !a && F[5,20] a && G[15,25] !a", false), Some(true));
}

#[test]
fn test_jump1_f() {
    assert_eq!(make_test("F[0,10] !a && G[0,9] a && F[10,20] a && G[15,20] !a", false), Some(true));
}

#[test]
fn test_jump1_u() {
    assert_eq!(make_test("b U[0,10] !a && G[0,9] a && F[10,20] a && G[15,20] !a", false), Some(true));
}

#[test]
fn test_g_is_derived() {
    assert_eq!(make_test("G[0,6] (!(a0 U[2,10] (F[0,6] (a0))))", true), Some(true));
}

#[test]
fn test_u_parent() {
    assert_eq!(make_test("(G[0,89] F[88,100] a2 U[0,78] !a1) && a1", true), Some(true));
}

#[test]
fn test_implication_negation() {
    assert_eq!(make_test("G[0, 6] !a && (G[0, 3] !a -> F[0, 3] a)", false), Some(false))
}

#[test]
fn test_globally_imply_merge() {
    assert_eq!(make_test("G[0, 10] (a -> G[10, 15] b) && G[0, 10] a && G[16, 16] !b", false), Some(false))
}

#[test]
fn test_until_mltl() {
    assert_eq!(make_test("a U[39, 77] (G[0, 15] a) && G[82, 100] !a", true), Some(true));
}