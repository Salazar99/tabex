import math

from conftest import REPO_ROOT  # noqa: F401  (adds repo root to sys.path)
from parse_graph import Interval, Path
from similarity.align import align
from similarity.stl_similarity import build_aligned_volumes, build_volume_from_paths, compute_similarity

INF = math.inf


def box(t0_x, t0_y):
    # A single-instant path constraining x and y at t=0 only.
    return Path({0: {"x": [Interval(*t0_x)], "y": [Interval(*t0_y)]}})


def l_shape_paths():
    # preliminaries.tex Section 4.3 worked example.
    phi1 = [box((0, 2), (0, 1)), box((0, 1), (1, 2))]
    phi2 = [box((0, 1), (0, 2)), box((1, 2), (0, 1))]
    return phi1, phi2


def cell_set(paths):
    return {
        tuple(sorted(
            (t, var, iv.l, iv.r)
            for t, slot in path.timeline.items()
            for var, ivs in slot.items()
            for iv in ivs
        ))
        for path in paths
    }


def test_l_shape_example_produces_identical_cells_on_both_sides():
    phi1, phi2 = l_shape_paths()
    aligned1, aligned2 = align(phi1, phi2)
    assert len(aligned1) == 3
    assert len(aligned2) == 3
    assert cell_set(aligned1) == cell_set(aligned2)


def test_l_shape_example_scores_one_after_alignment_but_not_before():
    phi1, phi2 = l_shape_paths()

    volume1 = build_volume_from_paths("phi1", phi1)
    volume2 = build_volume_from_paths("phi2", phi2)
    assert compute_similarity(volume1, volume2) == 0.75

    aligned_volume1, aligned_volume2 = build_aligned_volumes("phi1", phi1, "phi2", phi2)
    assert compute_similarity(aligned_volume1, aligned_volume2) == 1.0


def test_axis_with_no_cross_formula_breakpoints_is_untouched():
    # y is unconstrained in both formulas at every instant -- no breakpoints
    # for (y, 0), so it must survive as a single (-inf, inf) piece, not be
    # spuriously subdivided.
    p1 = Path({0: {"x": [Interval(0, 1)], "y": [Interval(-INF, INF)]}})
    p2 = Path({0: {"x": [Interval(2, 3)], "y": [Interval(-INF, INF)]}})
    aligned1, aligned2 = align([p1], [p2])
    assert len(aligned1) == 1
    assert len(aligned2) == 1
    assert [iv.to_tuple() for iv in aligned1[0].timeline[0]["y"]] == [(-INF, INF)]
    assert [iv.to_tuple() for iv in aligned2[0].timeline[0]["y"]] == [(-INF, INF)]


def test_self_alignment_reproduces_the_same_box():
    p = Path({0: {"x": [Interval(0, 5)]}})
    aligned1, aligned2 = align([p], [p])
    assert cell_set(aligned1) == cell_set(aligned2) == {((0, "x", 0.0, 5.0),)}


def test_axis_undef_in_every_path_of_one_formula_is_never_cut():
    # Regression: phi never constrains x at t=0 (genuinely undef -- it only
    # ever talks about x at t=1). Slicing that undef axis at theta's
    # breakpoint would turn "no constraint" into a concrete half-interval
    # that can coincidentally equal theta's real constraint and score as a
    # false match -- exactly the disjoint-time-window bug this guards
    # against (see test_stl_similarity.py's
    # test_disjoint_time_windows_score_zero_not_spuriously_positive, which
    # this alignment-level fix must not reintroduce).
    phi = [Path({0: {"x": [Interval(-INF, INF)]}, 1: {"x": [Interval(0, INF)]}})]
    theta = [Path({0: {"x": [Interval(-INF, 0)]}})]

    aligned_phi, aligned_theta = align(phi, theta)
    assert len(aligned_phi) == 1
    assert [iv.to_tuple() for iv in aligned_phi[0].timeline[0]["x"]] == [(-INF, INF)]

    volume_phi, volume_theta = build_aligned_volumes("phi", phi, "theta", theta)
    assert compute_similarity(volume_phi, volume_theta) == 0.0
