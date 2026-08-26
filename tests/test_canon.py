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
    assert compute_similarity(build_volume_from_paths("phi1", phi1),
                              build_volume_from_paths("phi2", phi2)) == 0.75
    volume1, volume2 = build_aligned_volumes("phi1", phi1, "phi2", phi2)
    assert compute_similarity(volume1, volume2) == 1.0


def test_canonical_form_does_not_depend_on_the_other_formula():
    # The whole point of making this unary: phi1's cells are the same whether
    # it is compared against phi2, against itself, or against nothing.
    phi1, phi2 = l_shape_paths()
    alone = cell_set(canonicalize(phi1))
    against_other, _ = build_aligned_volumes("phi1", phi1, "phi2", phi2)
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
    volume1, volume2 = build_aligned_volumes("T", top, "split", split)
    assert compute_similarity(volume1, volume2) == 1.0


def test_genuine_bends_are_kept():
    # Disconnected region and a real half-line boundary must survive.
    gap = [Path({0: {"x": [Interval(0, 1)]}}), Path({0: {"x": [Interval(2, 3)]}})]
    assert len(canonicalize(gap)) == 2
    assert cell_set(canonicalize([Path({0: {"x": [Interval(-INF, 0)]}})])) == {((0, "x", -INF, 0.0),)}


# --------------------------------------------------------------------------
# "==" atoms: a point box a wider box already covers must not pin a breakpoint
# --------------------------------------------------------------------------

def test_subsumed_equality_atom_does_not_split_the_region():
    # 0<=x<=10  vs  (0<=x<=5) || (x==5) || (5<=x<=10). Without _drop_subsumed
    # the point cell [5,5] both survives and pins x=5, and the two sides
    # canonicalize differently.
    whole = [Path({0: {"x": [Interval(0, 10)]}})]
    with_point = [Path({0: {"x": [Interval(0, 5)]}}),
                  Path({0: {"x": [Interval(5, 5)]}}),
                  Path({0: {"x": [Interval(5, 10)]}})]
    assert cell_set(canonicalize(with_point)) == cell_set(canonicalize(whole)) == {((0, "x", 0.0, 10.0),)}


def test_isolated_equality_atom_survives():
    assert cell_set(canonicalize([Path({0: {"x": [Interval(5, 5)]}})])) == {((0, "x", 5.0, 5.0),)}
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
    assert [iv.to_tuple() for iv in canonical_phi[0].timeline[0]["x"]] == [(-INF, INF)]
    volume_phi, volume_theta = build_aligned_volumes("phi", phi, "theta", theta)
    assert compute_similarity(volume_phi, volume_theta) == 0.0


def test_axis_no_formula_bounds_is_never_subdivided():
    p1 = Path({0: {"x": [Interval(0, 1)], "y": UNDEF}})
    p2 = Path({0: {"x": [Interval(2, 3)], "y": UNDEF}})
    for paths in ([p1], [p2]):
        cells = canonicalize(paths)
        assert len(cells) == 1
        assert [iv.to_tuple() for iv in cells[0].timeline[0]["y"]] == [(-INF, INF)]


def test_self_canonicalization_reproduces_the_same_box():
    p = Path({0: {"x": [Interval(0, 5)]}})
    assert cell_set(canonicalize([p])) == {((0, "x", 0.0, 5.0),)}


# --------------------------------------------------------------------------
# equivalent-but-differently-shaped tableaux
# --------------------------------------------------------------------------

def test_tautological_conjunct_at_a_later_instant_scores_one():
    # phi := (x>0) & G[1,1](y>0);  theta := phi & G[1,1]((x<=0)||(x>0)).
    # The extra conjunct is a tautology. Under the old joint grid this scored
    # 0.75, because only theta cut the (x, 1) axis.
    phi = [Path({0: {"x": [Interval(0, INF)], "y": UNDEF},
                 1: {"x": UNDEF, "y": [Interval(0, INF)]}})]
    theta = [Path({0: {"x": [Interval(0, INF)], "y": UNDEF},
                   1: {"x": [Interval(-INF, 0)], "y": [Interval(0, INF)]}}),
             Path({0: {"x": [Interval(0, INF)], "y": UNDEF},
                   1: {"x": [Interval(0, INF)], "y": [Interval(0, INF)]}})]
    volume1, volume2 = build_aligned_volumes("phi", phi, "theta", theta)
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
    volume1, volume2 = build_aligned_volumes("phi", phi, "theta", theta)
    assert compute_similarity(volume1, volume2) == 1.0


def test_a_real_extra_constraint_still_scores_below_one():
    # Guard against the coarsening being too eager: x>0 and x>0 & G[1,1](x>0)
    # are *not* equivalent, and must not be merged into agreement.
    phi = [Path({0: {"x": [Interval(0, INF)]}, 1: {"x": UNDEF}})]
    theta = [Path({0: {"x": [Interval(0, INF)]}, 1: {"x": [Interval(0, INF)]}})]
    volume1, volume2 = build_aligned_volumes("phi", phi, "theta", theta)
    assert compute_similarity(volume1, volume2) < 1.0


# --------------------------------------------------------------------------
# the property soundness rests on
# --------------------------------------------------------------------------

def _covered(cells, samples):
    return {
        point for point in samples
        if any(all(cell.timeline[t][var][0].l <= value <= cell.timeline[t][var][0].r
                   for (t, var), value in point)
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
