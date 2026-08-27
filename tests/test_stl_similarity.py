import math

import pytest

from conftest import EXAMPLES_DIR, REPO_ROOT, stlsat_available
from parse_graph import Interval, Path, build_tree_from_dot, discover_all_variables, generate_signal_space_from_formula, standardize
from similarity.stl_similarity import (
    build_volume_from_paths,
    compute_similarity,
    is_bounded,
    is_undefined,
    measure,
    merge_pieces,
    point_sim_d,
    trim_trailing_undef,
)


def volume_from_dot_fixture(dot_name):
    content = (EXAMPLES_DIR / dot_name).read_text(encoding="utf-8")
    root = build_tree_from_dot(content)
    all_vars = discover_all_variables(content)
    paths = standardize(root, all_vars)
    return build_volume_from_paths(dot_name, paths, all_vars)


def test_point_sim_d_matches_preliminaries_worked_example():
    # preliminaries.tex, Section AltPointSim: c1=[2,inf), c2=[5,inf).
    c1 = [Interval(2, math.inf)]
    c2 = [Interval(5, math.inf)]
    assert math.isclose(point_sim_d(c1, c2, 100), 95 / 98)
    assert math.isclose(point_sim_d(c1, c2, 10), 5 / 8)


def test_point_sim_d_undefined_cases():
    undef = [Interval(-math.inf, math.inf)]
    defined = [Interval(0, 5)]
    assert point_sim_d(undef, undef, 100) == 1.0
    assert point_sim_d(undef, defined, 100) == 0.0
    assert point_sim_d(defined, undef, 100) == 0.0


def test_point_sim_d_disjoint_is_zero():
    a = [Interval(0, 1)]
    b = [Interval(2, 3)]
    assert point_sim_d(a, b, 100) == 0.0


def test_point_sim_d_identical_bounded_is_one():
    a = [Interval(0, 5)]
    assert point_sim_d(a, a, 100) == 1.0


def test_is_undefined_and_is_bounded():
    assert is_undefined([Interval(-math.inf, math.inf)])
    assert not is_bounded([Interval(-math.inf, math.inf)])
    assert not is_undefined([Interval(0, 5)])
    assert is_bounded([Interval(0, 5)])
    assert not is_bounded([Interval(0, math.inf)])


def test_merge_pieces_collapses_duplicates():
    pieces = [Interval(0, math.inf), Interval(0, math.inf)]
    merged = merge_pieces(pieces)
    assert len(merged) == 1
    assert merged[0].to_tuple() == (0.0, math.inf, False, True)


def test_measure_ignores_duplicate_overlap():
    # a naive sum-of-lengths would double-count this to 6, the correct
    # measure of the union [2,5] is 3.
    pieces = [Interval(2, 5), Interval(2, 5)]
    assert measure(pieces) == 3.0


def test_measure_is_infinite_for_unbounded_piece():
    assert measure([Interval(0, math.inf)]) == math.inf


def test_self_similarity_is_exactly_one():
    # preliminaries.tex "Soundness demonstration": S(phi)=S(theta) => G=1.
    # Comparing a formula's signal space against itself is the sharpest
    # instance of that (phi == theta), checked against real code.
    for dot_name in ("graph_G.dot", "graph_F_gex.dot", "graph_G_or.dot", "graph_F_g_or_eqx.dot"):
        volume = volume_from_dot_fixture(dot_name)
        assert compute_similarity(volume, volume) == 1.0


def test_trim_trailing_undef_drops_trailing_silence_only():
    # A path that discharges its obligation at t=0 and is free afterwards --
    # only the trailing undef run should be dropped.
    path = Path({
        0: {"x": [Interval(0, math.inf)]},
        1: {"x": [Interval(-math.inf, math.inf)]},
        2: {"x": [Interval(-math.inf, math.inf)]},
    })
    trimmed = trim_trailing_undef(path)
    assert sorted(trimmed.timeline.keys()) == [0]


def test_trim_trailing_undef_leaves_leading_and_real_content_alone():
    # Leading undef (not yet triggered) and any real content are untouched --
    # only a trailing all-undef run is dropped.
    path = Path({
        0: {"x": [Interval(-math.inf, math.inf)]},
        1: {"x": [Interval(0, math.inf)]},
        2: {"x": [Interval(-math.inf, math.inf)]},
    })
    trimmed = trim_trailing_undef(path)
    assert sorted(trimmed.timeline.keys()) == [0, 1]


def test_trim_trailing_undef_noop_when_no_trailing_silence():
    path = Path({0: {"x": [Interval(0, math.inf)]}, 1: {"x": [Interval(0, math.inf)]}})
    trimmed = trim_trailing_undef(path)
    assert sorted(trimmed.timeline.keys()) == [0, 1]


def test_trim_trailing_undef_fully_silent_path_collapses_to_empty():
    path = Path({0: {"x": [Interval(-math.inf, math.inf)]}, 1: {"x": [Interval(-math.inf, math.inf)]}})
    trimmed = trim_trailing_undef(path)
    assert trimmed.timeline == {}


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_disjoint_time_windows_score_zero_not_spuriously_positive():
    # The reported bug: F[3,4] and F[0,2] are never obligated at the same
    # instant. Both formulas' genuine "already discharged" / "not yet started"
    # silence at the shared instants (t=1,2) used to score as agreement
    # (undef == undef), inflating this to ~0.3-0.45.
    #
    # The silence also must not be sliced into a concrete half-interval that
    # could coincidentally match the other formula's real constraint:
    # F[3,4]'s tableau never constrains x before t=3 (undef, not "x<0"), and
    # canonicalize() only ever cuts an axis at breakpoints the formula's *own*
    # boxes contribute -- see similarity/canon.py's _breakpoints.
    from similarity.stl_similarity import calc_similarity_from_formulas

    assert calc_similarity_from_formulas(
        "F[3,4] x>0", "F[0,2] x>0", tabex_root=REPO_ROOT) == 0.0


def test_point_sim_d_identical_degenerate_interval_is_one():
    # preliminaries.tex, Definition AltPointSim: two identical degenerate
    # constraints (e.g. from an atom x==5) must score 1, not fall through to
    # the Jaccard case as 0/0 (zero-length intersection).
    c = [Interval(5, 5)]
    assert point_sim_d(c, c, 100) == 1.0


def test_one_way_similarity_unsat_vs_sat_is_zero_not_one():
    # Eq. 7: exactly one of P(phi), P(theta) empty -> 0 (maximally
    # dissimilar), not 1. Also must not crash computing the reverse
    # direction (max() over an empty path list).
    from similarity.stl_similarity import one_way_similarity

    unsat = build_volume_from_paths("unsat", [])
    sat_paths = [Path({0: {"x": [Interval(0, math.inf)]}})]
    sat = build_volume_from_paths("sat", sat_paths, all_vars=["x"])

    assert one_way_similarity(unsat, sat, ["x"], 100) == 0.0
    assert one_way_similarity(sat, unsat, ["x"], 100) == 0.0
    assert compute_similarity(unsat, sat) == 0.0


def test_one_way_similarity_both_unsat_is_one():
    unsat1 = build_volume_from_paths("unsat1", [])
    unsat2 = build_volume_from_paths("unsat2", [])
    assert compute_similarity(unsat1, unsat2) == 1.0


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_tautological_disjunction_scores_one_end_to_end():
    # preliminaries.tex, Definition 7 / Remark 1: phi:=T, theta:=(x<=0)||(x>=0)
    # are equivalent (S(phi)=S(theta)=R). Handled by coarsening rather than
    # by cutting: theta's breakpoint at x=0 is not a bend of the region, so
    # canonicalize() drops it and theta's two cells merge into the single
    # unconstrained cell phi already had. phi is never refined up to theta --
    # see similarity/canon.py's _axis_partition.
    #
    # test_canon.py builds the same region by hand and compares cell sets;
    # this one is the end-to-end path, through a real tableau.
    from similarity.stl_similarity import calc_similarity_from_formulas

    assert calc_similarity_from_formulas("true", "(x<=0) || (x>=0)", tabex_root=REPO_ROOT) == 1.0


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_negated_bounds_are_equivalent_to_plain_bounds():
    # !(x<0) && !(x>10) is the same region as x>=0 && x<=10. Scored 0.0 before
    # canonical_atoms() learned to flip a negated atom's operator: stlsat's
    # "(!x < 0)" label matched no atom pattern, so the constraint was dropped
    # and the formula extracted as fully unconstrained.
    from similarity.stl_similarity import calc_similarity_from_formulas

    assert calc_similarity_from_formulas(
        "x>=0 && x<=10", "!(x<0) && !(x>10)", tabex_root=REPO_ROOT) == 1.0


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
@pytest.mark.parametrize("formula,rewritten,why", [
    ("y<-1", "(y<-1) && ((y>0) || (y<=0))",
     "dead disjunct: y<-1 && y>0 is a branch stlsat emits but rejects"),
    ("x==5", "(x==5) && ((y<=0) || (y>=0))",
     "tautological conjunct over a DEGENERATE region: x==5 is a point, and "
     "coarsening away the tautology's split must not erase it"),
    ("F[0,0](x<=2)", "(F[0,0](x<=2)) || ((F[0,0](x<=2)) && (x>0))",
     "absorption: the && conjunct must intersect, not union, into the slot"),
    ("((x<=2 || y<0) && x>=2)", "(((x<=2 || y<0) && x>=2)) || (((x<=2 || y<0) && x>=2))",
     "idempotence: merging branches on x must not drop their disagreement on y"),
    ("F[0,1]((x>1 && x<0))", "(F[0,1]((x>1 && x<0))) && ((y>0) || (y<=0))",
     "unsatisfiable both sides: stlsat's graph still holds the surviving tautology"),
    ("F[0,1]((x>0 && y>0) || (x<0 && y<0))",
     "(F[0,1](x>0 && y>0)) || (F[0,1](x<0 && y<0))",
     "two witness boxes: negating a pooled per-variable bucket kills both continuations"),
    ("((y<0) U[1,1] (x>0))", "(((y<0) U[1,1] (x>0))) && ((y>0) || (y<=0))",
     "closed-only intervals: the dead y<0 && y>0 branch survives as the point [0,0]"),
    ("(x<1) || (x>1)", "!(x==1)",
     "a hole at a breakpoint is a genuine bend, not a coarsenable split"),
    ("F[0,1](F[0,1](((x>-2 || y<-2) && (x<=-2 || y>=-2))))",
     "F[0,2](((x>-2 || y<-2) && (x<=-2 || y>=-2)))",
     "nested F over an XOR body: the witness disjunction must distribute"),
])
def test_equivalence_preserving_rewrites_score_one(formula, rewritten, why):
    # Minimal counterexamples from the randomised equivalence sweep
    # (verify_equivalence.py). Each scored below 1.0 before its fix in
    # parse_graph.py; `why` names the specific extraction bug.
    from similarity.stl_similarity import calc_similarity_from_formulas

    assert calc_similarity_from_formulas(formula, rewritten, tabex_root=REPO_ROOT) == 1.0, why


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_nested_G_in_F_equivalent_to_unfolded_conjunction():
    # F[0,1](G[0,1] x>0) and F[0,1](x>0 && G[1,1] x>0) both reduce to
    # (x(0)>0 && x(1)>0) || (x(1)>0 && x(2)>0). Scored 0.611 before O-marked
    # deferred obligations stopped leaking their inner conjuncts into the
    # continuation branch's own instant.
    from similarity.stl_similarity import calc_similarity_from_formulas

    assert calc_similarity_from_formulas(
        "F[0,1](G[0,1](x>0))", "F[0,1](x>0 && G[1,1](x>0))", tabex_root=REPO_ROOT) == 1.0


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_unsatisfiable_formula_extracts_to_no_paths_without_a_sat_verdict():
    # stlsat stops expanding a branch once it knows the branch is dead, so its
    # DOT keeps childless nodes that were never COMPLETED -- here a leaf whose
    # only formula is still "F[0,1] (x > 1 && x < 0)". Read as an accepted
    # branch it becomes a fully unconstrained path and this unsatisfiable
    # formula comes out with a non-empty signal space.
    from parse_graph import generate_signal_space_from_formula

    paths = generate_signal_space_from_formula(
        "F[0,1]((x>1) && (x<0)) && ((y>0) || (y<=0))", tabex_root=REPO_ROOT)
    assert paths == []


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_disjunct_order_does_not_change_the_region():
    # These two differ only in the order of a disjunction, so they must extract
    # the same region. The shape is worth pinning: it used to make
    # tableau_loop() answer UNSAT for the first and SAT for the second, on
    # identical tableaux, because a later unsatisfiable sibling overwrote a
    # branch already found satisfiable. The extraction never reads that verdict
    # -- prune_incomplete() derives emptiness from the graph -- so this held
    # even while stlsat got it wrong, and it must keep holding.
    from parse_graph import generate_signal_space_from_formula
    from similarity.stl_similarity import calc_similarity_from_formulas

    formula = "(x<1) && ((F[2,3](y<2)) || (x>=1))"
    swapped = "(x<1) && ((x>=1) || (F[2,3](y<2)))"
    assert generate_signal_space_from_formula(formula, tabex_root=REPO_ROOT) != []
    assert calc_similarity_from_formulas(formula, swapped, tabex_root=REPO_ROOT) == 1.0


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_nested_G_collapse_over_a_dead_disjunct():
    # G[0,1](G[0,1] P) == G[0,2] P. Here P = (y<=-3 || x>=3) && x<-2, whose
    # second disjunct is dead against x<-2. That shape used to make stlsat
    # answer UNSAT for both sides (both are satisfiable, e.g. x=-3, y=-4) and,
    # having "decided", stop expanding -- leaving a branch that still owed
    # "G[0,1] G[0,1] P", which standardize() then dropped rather than extract a
    # partial constraint from an unfinished node. It needs stlsat to unroll the
    # whole tableau, which is what m_stlsat's graph-output mode now does.
    from similarity.stl_similarity import calc_similarity_from_formulas

    body = "((y<=-3 || x>=3) && x<-2)"
    assert calc_similarity_from_formulas(
        f"G[0,1](G[0,1]{body})", f"G[0,2]{body}", tabex_root=REPO_ROOT) == 1.0


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_a_truncated_branch_is_dropped_not_partially_extracted():
    # The invariant the above rests on: in a fully unrolled tableau every leaf
    # carries atoms only (graph_G.dot ends at "x > 0", graph_U.dot at
    # "x > 0, y > 3"), so a leaf still naming F/G/U is a branch stlsat stopped
    # expanding. Extracting from it would silently under-constrain the region.
    from parse_graph import build_tree_from_dot, prune_incomplete
    from conftest import EXAMPLES_DIR

    for name in ("graph_G.dot", "graph_U.dot", "graph_F_gex.dot"):
        tree = build_tree_from_dot((EXAMPLES_DIR / name).read_text(encoding="utf-8"))
        assert not prune_incomplete(tree), f"{name} is complete; nothing may be pruned"


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
@pytest.mark.parametrize("original,rewritten,why", [
    ("((x>0) U[0,0] (y>3))", "((x>0) && (y>3))",
     "U[0,0] pins the invariant AT the witness: it is not just the witness"),
    ("((x>0) U[2,2] (y>3))", "(G[0,2](x>0)) && (G[2,2](y>3))",
     "a point until is the invariant up to the witness, and the witness"),
    ("((x>0) U[0,2] (y>3))", "((x>0) U[0,2] ((x>0) && (y>3)))",
     "the invariant is already required at the witness, so conjoining it is a no-op"),
    ("((x>0) U[0,2] ((y>3) || (y<-3)))",
     "(((x>0) U[0,2] (y>3))) || (((x>0) U[0,2] (y<-3)))",
     "until distributes over a disjunction in its right argument"),
    ("(((y>0) || (y<=0)) U[1,3] (x>0))", "F[1,3](x>0)",
     "a vacuous invariant collapses until to eventually"),
])
def test_until_semantics(original, rewritten, why):
    # stlsat rewrites "phi U[a,b] psi" into "G[0,a] phi && (phi U[a,b] (phi && psi))",
    # so its until requires the invariant up to AND INCLUDING the witness --
    # NOT the textbook half-open [t, witness). Every case here is false under
    # the half-open reading, so this is the file to look at if a future stlsat
    # changes that rewrite.
    from similarity.stl_similarity import calc_similarity_from_formulas

    assert calc_similarity_from_formulas(original, rewritten, tabex_root=REPO_ROOT) == 1.0, why
