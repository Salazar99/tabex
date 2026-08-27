import math

from conftest import REPO_ROOT  # noqa: F401  (adds repo root to sys.path)
from parse_graph import Interval, Path
from similarity.canon import canonicalize, cell_key
from similarity.stl_similarity import build_aligned_volumes, build_volume_from_paths, compute_similarity

INF = math.inf
UNDEF = [Interval(-INF, INF)]


def box(t0_x, t0_y):
    # A single-instant path constraining x and y at t=0 only.
    return Path({0: {"x": [Interval(*t0_x)], "y": [Interval(*t0_y)]}})


def l_shape_paths():
    # preliminaries.tex, the worked L-shaped example.
    phi1 = [box((0, 2), (0, 1)), box((0, 1), (1, 2))]
    phi2 = [box((0, 1), (0, 2)), box((1, 2), (0, 1))]
    return phi1, phi2


# These tests build regions directly as Path/Interval boxes rather than going
# through stlsat, so that they stay unit tests (no cargo/z3 needed). The names
# below are the STL each hand-built region corresponds to -- they are what the
# end-of-run similarity report in conftest.py prints, so they have to say what
# was actually compared.
L_SHAPE_1 = "(0<=x<=2 && 0<=y<=1) || (0<=x<=1 && 1<=y<=2)"
L_SHAPE_2 = "(0<=x<=1 && 0<=y<=2) || (1<=x<=2 && 0<=y<=1)"


def cell_set(paths):
    return {cell_key(path) for path in paths}


# --------------------------------------------------------------------------
# canonicalize() is unary: same region => same object, whoever it is compared to
# --------------------------------------------------------------------------

def test_l_shape_canonicalizes_identically_on_both_sides():
    phi1, phi2 = l_shape_paths()
    assert len(canonicalize(phi1)) == 3
    assert cell_set(canonicalize(phi1)) == cell_set(canonicalize(phi2))


def test_l_shape_scores_one_after_canonicalization_but_not_before():
    phi1, phi2 = l_shape_paths()
    assert compute_similarity(build_volume_from_paths(L_SHAPE_1, phi1),
                              build_volume_from_paths(L_SHAPE_2, phi2)) == 0.75
    volume1, volume2 = build_aligned_volumes(L_SHAPE_1, phi1, L_SHAPE_2, phi2)
    assert compute_similarity(volume1, volume2) == 1.0


def test_canonical_form_does_not_depend_on_the_other_formula():
    # The whole point of making this unary: phi1's cells are the same whether
    # it is compared against phi2, against itself, or against nothing.
    phi1, phi2 = l_shape_paths()
    alone = cell_set(canonicalize(phi1))
    against_other, _ = build_aligned_volumes(L_SHAPE_1, phi1, L_SHAPE_2, phi2)
    assert cell_set(against_other.volume) == alone


def test_a_redundant_split_is_coarsened_away():
    # 0<=x<=2  vs  (0<=x<=1) || (1<=x<=2): same region, x=1 is not a bend.
    whole = [Path({0: {"x": [Interval(0, 2)]}})]
    split = [Path({0: {"x": [Interval(0, 1)]}}), Path({0: {"x": [Interval(1, 2)]}})]
    assert cell_set(canonicalize(whole)) == cell_set(canonicalize(split))
    assert len(canonicalize(split)) == 1


def test_tautological_disjunction_coarsens_to_a_single_unconstrained_cell():
    # phi := T  vs  theta := (x<=0) || (x>=0). theta's breakpoint at 0 is not
    # a bend -- the region is R on both sides of it -- so theta is coarsened
    # down to phi rather than phi being refined up to theta.
    top = [Path({0: {"x": UNDEF}})]
    split = [Path({0: {"x": [Interval(-INF, 0)]}}), Path({0: {"x": [Interval(0, INF)]}})]
    assert cell_set(canonicalize(top)) == cell_set(canonicalize(split))
    volume1, volume2 = build_aligned_volumes("true", top, "(x<=0) || (x>=0)", split)
    assert compute_similarity(volume1, volume2) == 1.0


def test_genuine_bends_are_kept():
    # Disconnected region and a real half-line boundary must survive.
    gap = [Path({0: {"x": [Interval(0, 1)]}}), Path({0: {"x": [Interval(2, 3)]}})]
    assert len(canonicalize(gap)) == 2
    assert cell_set(canonicalize([Path({0: {"x": [Interval(-INF, 0)]}})])) == {((0, "x", -INF, 0.0, True, False),)}


# --------------------------------------------------------------------------
# "==" atoms: a point box a wider box already covers must not pin a breakpoint
# --------------------------------------------------------------------------

def test_subsumed_equality_atom_does_not_split_the_region():
    # 0<=x<=10  vs  (0<=x<=5) || (x==5) || (5<=x<=10). Without a true
    # arrangement the point cell [5,5] both survives and pins x=5, so the two
    # sides canonicalize differently even though they cover the same region.
    whole = [Path({0: {"x": [Interval(0, 10)]}})]
    with_point = [Path({0: {"x": [Interval(0, 5)]}}),
                  Path({0: {"x": [Interval(5, 5)]}}),
                  Path({0: {"x": [Interval(5, 10)]}})]
    assert cell_set(canonicalize(with_point)) == cell_set(canonicalize(whole)) == {((0, "x", 0.0, 10.0, False, False),)}


def test_isolated_equality_atom_survives():
    assert cell_set(canonicalize([Path({0: {"x": [Interval(5, 5)]}})])) == {((0, "x", 5.0, 5.0, False, False),)}
    # ... and is still isolated when the rest of the region is far away.
    apart = [Path({0: {"x": [Interval(0, 1)]}}), Path({0: {"x": [Interval(5, 5)]}})]
    assert len(canonicalize(apart)) == 2


# --------------------------------------------------------------------------
# no borrowed breakpoints: genuine silence stays silent
# --------------------------------------------------------------------------

def test_axis_this_formula_never_bounds_is_left_whole():
    # phi only ever talks about x at t=1. Its silence at t=0 must not be cut
    # at theta's breakpoint -- that would turn "no constraint" into a concrete
    # half-interval able to coincidentally match theta's real one.
    phi = [Path({0: {"x": UNDEF}, 1: {"x": [Interval(0, INF)]}})]
    theta = [Path({0: {"x": [Interval(-INF, 0)]}, 1: {"x": UNDEF}})]
    canonical_phi = canonicalize(phi)
    assert len(canonical_phi) == 1
    assert [iv.to_tuple() for iv in canonical_phi[0].timeline[0]["x"]] == [(-INF, INF, True, True)]
    volume_phi, volume_theta = build_aligned_volumes(
        "G[1,1] x>=0", phi, "x<=0 (t=0 only)", theta)
    assert compute_similarity(volume_phi, volume_theta) == 0.0


def test_axis_no_formula_bounds_is_never_subdivided():
    p1 = Path({0: {"x": [Interval(0, 1)], "y": UNDEF}})
    p2 = Path({0: {"x": [Interval(2, 3)], "y": UNDEF}})
    for paths in ([p1], [p2]):
        cells = canonicalize(paths)
        assert len(cells) == 1
        assert [iv.to_tuple() for iv in cells[0].timeline[0]["y"]] == [(-INF, INF, True, True)]


def test_self_canonicalization_reproduces_the_same_box():
    p = Path({0: {"x": [Interval(0, 5)]}})
    assert cell_set(canonicalize([p])) == {((0, "x", 0.0, 5.0, False, False),)}


# --------------------------------------------------------------------------
# equivalent-but-differently-shaped tableaux
# --------------------------------------------------------------------------

def test_tautological_conjunct_at_a_later_instant_scores_one():
    # phi := (x>0) & G[1,1](y>0);  theta := phi & G[1,1]((x<=0)||(x>0)).
    # The extra conjunct is a tautology, so theta's split of the (x, 1) axis is
    # not a bend of the region and must coarsen away -- only phi's real
    # constraints may survive on either side.
    phi = [Path({0: {"x": [Interval(0, INF)], "y": UNDEF},
                 1: {"x": UNDEF, "y": [Interval(0, INF)]}})]
    theta = [Path({0: {"x": [Interval(0, INF)], "y": UNDEF},
                   1: {"x": [Interval(-INF, 0)], "y": [Interval(0, INF)]}}),
             Path({0: {"x": [Interval(0, INF)], "y": UNDEF},
                   1: {"x": [Interval(0, INF)], "y": [Interval(0, INF)]}})]
    volume1, volume2 = build_aligned_volumes(
        "x>=0 && G[1,1] y>=0", phi,
        "x>=0 && G[1,1] y>=0 && G[1,1](x<=0||x>=0)", theta)
    assert compute_similarity(volume1, volume2) == 1.0


def test_spurious_extra_instant_is_coarsened_then_trimmed():
    # phi := x>0;  theta := (x>0) & G[1,1]((y>0)||(y<=0)), over the joint time
    # domain. theta's split at t=1 is not a bend, so it coarsens to silence
    # and trimming then removes the instant -- previously this scored 0.5.
    phi = [Path({0: {"x": [Interval(0, INF)], "y": UNDEF}, 1: {"x": UNDEF, "y": UNDEF}})]
    theta = [Path({0: {"x": [Interval(0, INF)], "y": UNDEF},
                   1: {"x": UNDEF, "y": [Interval(0, INF)]}}),
             Path({0: {"x": [Interval(0, INF)], "y": UNDEF},
                   1: {"x": UNDEF, "y": [Interval(-INF, 0)]}})]
    volume1, volume2 = build_aligned_volumes(
        "x>=0", phi, "x>=0 && G[1,1](y>=0||y<=0)", theta)
    assert compute_similarity(volume1, volume2) == 1.0


def test_a_real_extra_constraint_still_scores_below_one():
    # Guard against the coarsening being too eager: x>0 and x>0 & G[1,1](x>0)
    # are *not* equivalent, and must not be merged into agreement.
    phi = [Path({0: {"x": [Interval(0, INF)]}, 1: {"x": UNDEF}})]
    theta = [Path({0: {"x": [Interval(0, INF)]}, 1: {"x": [Interval(0, INF)]}})]
    volume1, volume2 = build_aligned_volumes(
        "x>=0", phi, "x>=0 && G[1,1] x>=0", theta)
    assert compute_similarity(volume1, volume2) < 1.0


# --------------------------------------------------------------------------
# the property soundness rests on
# --------------------------------------------------------------------------

def _contains(interval, value):
    return ((value > interval.l if interval.lo else value >= interval.l) and
            (value < interval.r if interval.ro else value <= interval.r))


def _covered(cells, samples):
    return {
        point for point in samples
        if any(all(_contains(cell.timeline[t][var][0], value) for (t, var), value in point)
               for cell in cells)
    }


def test_canonicalization_is_lossless():
    # G(phi,theta)=1 => phi==theta holds because the canonical cells cover
    # exactly the region they came from -- no more (coarsening never
    # over-reaches) and no less (cutting never drops anything).
    paths = [Path({0: {"x": [Interval(0, 2)], "y": [Interval(0, 1)]}}),
             Path({0: {"x": [Interval(0, 1)], "y": [Interval(1, 2)]}}),
             Path({0: {"x": [Interval(5, 5)], "y": [Interval(0, 2)]}})]
    grid = [i * 0.5 for i in range(0, 13)]
    samples = [(((0, "x"), a), ((0, "y"), b)) for a in grid for b in grid]
    assert _covered(canonicalize(paths), samples) == _covered(paths, samples)


# --- regression guards, one minimal case per fixed bug --------------------


def test_open_and_closed_cells_are_not_deduped_together():
    # cell_key must include endpoint openness. Keyed on (l, r) alone, the
    # arrangement cell "x in [1,inf)" and "x in (1,inf)" collide and
    # _fine_cells' seen.setdefault silently discards one of them -- taking a
    # genuine part of the region with it.
    closed = Path({0: {"x": [Interval(1, INF)]}})
    open_ = Path({0: {"x": [Interval(1, INF, lo=True)]}})
    assert cell_key(closed) != cell_key(open_)


def test_a_hole_at_a_breakpoint_is_not_coarsened_away():
    # "(x<1) || (x>1)" has the SAME cross-section either side of 1 and still
    # excludes 1. Judging the breakpoint inessential from matching
    # cross-sections alone returns the whole line and admits x == 1.
    gap = [Path({0: {"x": [Interval(-INF, 1, ro=True)]}}),
           Path({0: {"x": [Interval(1, INF, lo=True)]}})]
    cells = canonicalize(gap)
    assert len(cells) == 2
    assert not any(_contains(c.timeline[0]["x"][0], 1.0) for c in cells)
    # ... while the closed pair really is the whole line
    covering = [Path({0: {"x": [Interval(-INF, 1)]}}),
                Path({0: {"x": [Interval(1, INF)]}})]
    assert cell_set(canonicalize(covering)) == {((0, "x", -INF, INF, True, True),)}


def test_boundary_sliver_survives_a_two_axis_union():
    # "x>=1 && y>-1" and "x>1 && y>=-1" cut at the same breakpoints into cells
    # that OVERLAP on the interior and each own a different boundary sliver.
    # Only a true arrangement -- point slabs included -- keeps both, so the
    # signal x=1, y=-1 stays out while x=1, y=0 stays in.
    paths = [Path({0: {"x": [Interval(1, INF)], "y": [Interval(-1, INF, lo=True)]}}),
             Path({0: {"x": [Interval(1, INF, lo=True)], "y": [Interval(-1, INF)]}})]
    cells = canonicalize(paths)

    def admits(x, y):
        return any(_contains(c.timeline[0]["x"][0], x) and _contains(c.timeline[0]["y"][0], y)
                   for c in cells)

    assert admits(1.0, 0.0)      # x>=1 and y>-1
    assert admits(2.0, -1.0)     # x>1  and y>=-1
    assert not admits(1.0, -1.0)  # neither box contains the corner
    assert not admits(0.5, 0.0)


def test_canonical_form_does_not_depend_on_axis_order():
    # Greedy pairwise coalescing is not confluent: merging x first and y first
    # give two different (both minimal) answers on the L-shape. The canonical
    # form has to be the product grid, so the same region must come back as
    # the same cells no matter which axis is nominally "first".
    l_shape = [Path({0: {"x": [Interval(0, 2)], "y": [Interval(0, 1)]}}),
               Path({0: {"x": [Interval(0, 1)], "y": [Interval(1, 2)]}})]
    transposed = [Path({0: {"y": [Interval(0, 2)], "x": [Interval(0, 1)]}}),
                  Path({0: {"y": [Interval(0, 1)], "x": [Interval(1, 2)]}})]

    def swap_axes(keys):
        flip = {"x": "y", "y": "x"}
        return {tuple(sorted((t, flip[v]) + tuple(rest) for (t, v, *rest) in key))
                for key in keys}

    assert len(canonicalize(l_shape)) == 3
    assert swap_axes(cell_set(canonicalize(transposed))) == cell_set(canonicalize(l_shape))
