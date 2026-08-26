import math

import pytest

from conftest import EXAMPLES_DIR, REPO_ROOT, stlsat_available
from parse_graph import Interval, Path, build_tree_from_dot, discover_all_variables, generate_signal_space_from_formula, standardize
from similarity.stl_similarity import (
    build_aligned_volumes,
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
    assert merged[0].to_tuple() == (0.0, math.inf)


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
    # instant. Before trimming, both formulas' genuine "already discharged" /
    # "not yet started" silence at shared instants (t=1,2) scored as
    # agreement (undef == undef), inflating this to ~0.3-0.45.
    v1 = build_volume_from_paths("F[3,4] x>0", generate_signal_space_from_formula("F[3,4] x>0", tabex_root=REPO_ROOT))
    v2 = build_volume_from_paths("F[0,2] x>0", generate_signal_space_from_formula("F[0,2] x>0", tabex_root=REPO_ROOT))
    assert compute_similarity(v1, v2) == 0.0


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_disjoint_time_windows_score_zero_after_alignment_too():
    # Regression: Align must not reintroduce the bug above through a
    # different door. F[3,4]'s tableau genuinely never constrains x before
    # t=3 (undef, not "x<0"); aligning against F[0,2] (which does constrain
    # x at t=0..2) must leave that undef axis uncut rather than slicing it
    # into a half-interval that can coincidentally match F[0,2]'s real
    # constraint -- canonicalize() only ever cuts an axis at breakpoints the
    # formula's *own* boxes contribute, so that silence cannot be sliced this
    # way -- see similarity/canon.py's _breakpoints.
    paths1 = generate_signal_space_from_formula("F[3,4] x>0", tabex_root=REPO_ROOT)
    paths2 = generate_signal_space_from_formula("F[0,2] x>0", tabex_root=REPO_ROOT)
    volume1, volume2 = build_aligned_volumes("F[3,4] x>0", paths1, "F[0,2] x>0", paths2)
    assert compute_similarity(volume1, volume2) == 0.0


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
def test_trim_after_align_matches_paper_worked_example():
    # preliminaries.tex, Definition 7 / Remark 1: phi:=T, theta:=(x<=0)||(x>=0)
    # are equivalent (S(phi)=S(theta)=R). Handled by coarsening rather than
    # by cutting: theta's breakpoint at x=0 is not a bend of the region, so
    # canonicalize() drops it and theta's two cells merge into the single
    # unconstrained cell phi already had. phi is never refined up to theta --
    # see similarity/canon.py's _essential.
    from similarity.stl_similarity import calc_similarity_from_formulas

    assert calc_similarity_from_formulas("true", "(x<=0) || (x>=0)", tabex_root=REPO_ROOT) == 1.0


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_globally_unconstrained_var_is_per_variable_not_per_formula():
    # Regression for the fix's scope: a formula that's globally silent on
    # one variable but genuinely constrains another (at the SAME instant as
    # the other formula's real constraint) must only get the silent
    # variable's axis cut -- not have its real constraint's axis touched,
    # and must not collapse into the disjoint-time-window false-positive
    # this gate exists to prevent.
    from similarity.stl_similarity import calc_similarity_from_formulas

    # x==5 pins x to a single point; theta never mentions x, only y, so
    # theta's silence on x must be free to align with phi's x==5 without
    # either formula's y-less/x-less status corrupting the other axis.
    score = calc_similarity_from_formulas("x==5", "(x==5) && ((y<=0) || (y>=0))", tabex_root=REPO_ROOT)
    assert score == 1.0

    # Sanity: the disjoint-time-window case this gate protects must still
    # be unaffected by the global-unconstrained carve-out (neither formula
    # is ever globally silent on x -- both constrain it, just at different
    # times).
    assert calc_similarity_from_formulas("F[3,4] x>0", "F[0,2] x>0", tabex_root=REPO_ROOT) == 0.0


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
def test_nested_G_in_F_equivalent_to_unfolded_conjunction():
    # F[0,1](G[0,1] x>0) and F[0,1](x>0 && G[1,1] x>0) both reduce to
    # (x(0)>0 && x(1)>0) || (x(1)>0 && x(2)>0). Scored 0.611 before O-marked
    # deferred obligations stopped leaking their inner conjuncts into the
    # continuation branch's own instant.
    from similarity.stl_similarity import calc_similarity_from_formulas

    assert calc_similarity_from_formulas(
        "F[0,1](G[0,1](x>0))", "F[0,1](x>0 && G[1,1](x>0))", tabex_root=REPO_ROOT) == 1.0
