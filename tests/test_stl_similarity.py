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
    # constraint -- see similarity/align.py's _own_constrained_axes.
    paths1 = generate_signal_space_from_formula("F[3,4] x>0", tabex_root=REPO_ROOT)
    paths2 = generate_signal_space_from_formula("F[0,2] x>0", tabex_root=REPO_ROOT)
    volume1, volume2 = build_aligned_volumes("F[3,4] x>0", paths1, "F[0,2] x>0", paths2)
    assert compute_similarity(volume1, volume2) == 0.0
