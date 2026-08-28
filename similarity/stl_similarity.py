"""STL similarity metric, per preliminaries.tex.

Operates directly on parse_graph.py's signal space (list[Path], each
Path.timeline: {t: {var: [Interval, ...]}}) instead of a separate JSON
"bounds" format -- see similarity/stl_similarity.py.bk for the previous
implementation, which consumed dotparser/input_creator.py's output.
"""
import argparse
import sys
from fractions import Fraction
from pathlib import Path as FilePath

sys.path.insert(0, str(FilePath(__file__).resolve().parent.parent))

from parse_graph import (
    Interval,
    Path,
    build_tree_from_dot,
    collect_times,
    discover_all_variables,
    generate_signal_space_from_formula,
    merge_pieces,
    run_stlsat,
    standardize,
)
from similarity.canon import canonicalize

UNDEFINED = [Interval(float("-inf"), float("inf"))]


def measure(pieces):
    # Endpoints are exact rationals, so lengths are computed exactly and only
    # the Jaccard ratio at the end is turned into a float.
    total = Fraction(0)
    for iv in merge_pieces(pieces):
        if iv.l == float("-inf") or iv.r == float("inf"):
            return float("inf")
        total += iv.r - iv.l
    return total


def intersect_pieces(a, b):
    result = [iv for x in a for y in b if (iv := x.intersect(y)) is not None]
    return merge_pieces(result)


def union_pieces(a, b):
    return merge_pieces(list(a) + list(b))


def is_undefined(pieces):
    # standardize() pads an unconstrained (t, var) slot with exactly this.
    return len(pieces) == 1 and pieces[0].l == float("-inf") and pieces[0].r == float("inf")


def is_bounded(pieces):
    return all(iv.l != float("-inf") and iv.r != float("inf") for iv in pieces)


def truncate(pieces, D):
    # Clamp via intersect so endpoint openness survives the window.
    window = Interval(-D, D)
    return [clamped for iv in pieces if (clamped := iv.intersect(window)) is not None]


def point_sim_d(pieces1, pieces2, D):
    # Eq. PointSimD: truncate to the D-window first, then a single Jaccard
    # formula covers every remaining case (no separate distance-decay case).
    undef1, undef2 = is_undefined(pieces1), is_undefined(pieces2)
    if undef1 and undef2:
        return 1.0
    if undef1 != undef2:
        return 0.0

    t1, t2 = truncate(pieces1, D), truncate(pieces2, D)
    m1, m2 = merge_pieces(t1), merge_pieces(t2)
    if [iv.to_tuple() for iv in m1] == [iv.to_tuple() for iv in m2]:
        # Eq. 5 case 1: ĉ1,D = ĉ2,D. Must be checked before the Jaccard case
        # below, or two identical degenerate constraints (e.g. x==5, both
        # truncate to a zero-length point) hit intersection==0 and wrongly
        # score 0 instead of 1.
        return 1.0
    intersection = measure(intersect_pieces(t1, t2))
    if intersection == 0:
        return 0.0
    union = measure(union_pieces(t1, t2))
    # float() at the boundary: the ratio is exact, the score is reported as a
    # float so callers and "== 1.0" comparisons behave as before.
    return float(intersection / union) if union > 0 else 0.0


def _finite_bounds(volumes):
    for volume in volumes:
        for path in volume.volume:
            for slot in path.timeline.values():
                for pieces in slot.values():
                    for iv in pieces:
                        if iv.l != float("-inf"):
                            yield abs(iv.l)
                        if iv.r != float("inf"):
                            yield abs(iv.r)


def default_D(volumes, margin=1.0):
    # Well-formedness (preliminaries.tex): D must exceed every finite bound
    # occurring in either formula, so this is derived rather than guessed.
    bounds = list(_finite_bounds(volumes))
    return (max(bounds) if bounds else Fraction(0)) + Fraction(str(margin))


def path_similarity(path1, path2, all_vars, D):
    times = set(path1.timeline.keys()) | set(path2.timeline.keys())
    total = 0.0
    for t in times:
        if t not in path1.timeline or t not in path2.timeline:
            # t is entirely outside one formula's own horizon -- not a shared
            # instant where both are "silent" (which is Point_sim's undef/undef
            # case), just not comparable, so it contributes 0 rather than
            # falling back to a vacuous undef/undef match.
            continue
        slot1, slot2 = path1.timeline[t], path2.timeline[t]
        for var in all_vars:
            total += point_sim_d(slot1.get(var, UNDEFINED), slot2.get(var, UNDEFINED), D)
    denom = len(times) * len(all_vars)
    return total / denom if denom else 1.0


def one_way_similarity(volume1, volume2, all_vars, D):
    # Eq. 7: both empty -> 1 (two unsatisfiable formulas are equivalent);
    # exactly one empty -> 0 (sat vs unsat is maximally dissimilar).
    if not volume1.volume and not volume2.volume:
        return 1.0
    if not volume1.volume or not volume2.volume:
        return 0.0
    total = sum(
        max(path_similarity(path1, path2, all_vars, D) for path2 in volume2.volume)
        for path1 in volume1.volume
    )
    return total / len(volume1.volume)


def compute_similarity(volume1, volume2, D=None):
    all_vars = sorted(set(volume1.vars) | set(volume2.vars))
    if D is None:
        D = default_D([volume1, volume2])
    forward = one_way_similarity(volume1, volume2, all_vars, D)
    backward = one_way_similarity(volume2, volume1, all_vars, D)
    return (forward + backward) / 2


class FormulaVolume:
    def __init__(self, formula_name, vars, paths):
        self.formula_name = formula_name
        self.vars = vars
        self.volume = paths
        self.horizon = max((t for path in paths for t in path.timeline), default=0)


def trim_trailing_undef(path):
    # Once every variable is undefined from some point to the end of a path,
    # nothing more is asserted there (an eventuality already discharged, or
    # a formula's own horizon ended) -- drop that trailing run so it can't
    # spuriously match another formula's unrelated silence at the same instants.
    times = sorted(path.timeline.keys())
    cutoff = len(times)
    for t in reversed(times):
        if all(is_undefined(pieces) for pieces in path.timeline[t].values()):
            cutoff -= 1
        else:
            break
    return Path({t: path.timeline[t] for t in times[:cutoff]})


def build_volume_from_paths(formula_name, paths, all_vars=None, trim=True):
    if all_vars is None:
        all_vars = sorted(next(iter(paths[0].timeline.values())).keys()) if paths else []
    volume_paths = [trim_trailing_undef(p) for p in paths] if trim else list(paths)
    return FormulaVolume(formula_name, all_vars, volume_paths)


def build_aligned_volumes(formula1, paths1, formula2, paths2, all_vars=None):
    # Pipeline: extract -> canonicalize -> trim, each side independently.
    #
    # canonicalize() (similarity/canon.py) depends only on the region a
    # formula's paths cover, never on the formula it is being compared
    # against, so two tableaux that cut the same region into different boxes
    # produce the identical cell list. That is what the L-shaped example
    # needs, and it is why no pairwise alignment step -- and none of the
    # axis-cutting gates it used to require -- appears here any more.
    #
    # Trimming must still come last: it drops a cell's trailing all-undef
    # run, and coarsening can turn a spuriously-split instant back into a
    # silent one that then becomes trimmable.
    volume1 = build_volume_from_paths(formula1, paths1, all_vars, trim=False)
    volume2 = build_volume_from_paths(formula2, paths2, all_vars, trim=False)
    volume1.volume = [trim_trailing_undef(c) for c in canonicalize(volume1.volume)]
    volume2.volume = [trim_trailing_undef(c) for c in canonicalize(volume2.volume)]
    return volume1, volume2


def signal_spaces_from_definition(formula1, formula2):
    """Both regions straight from `reference_semantics`, over the joint grid.

    This is the path with a proof behind it (FORMAL_PROOFS.md Theorem A). The
    joint variable set and joint horizon put the two regions in the same ambient
    space, which Path_sim's |T1 u T2| denominator needs and which is also
    hypothesis H1 of Theorem B. Padding with [-inf, +inf] changes neither region.
    """
    from reference_semantics import parse, signal_space, variables

    tree1, tree2 = parse(formula1), parse(formula2)
    all_vars = sorted(variables(tree1) | variables(tree2))
    horizon = max(tree1.horizon(), tree2.horizon())
    return (signal_space(tree1, all_vars, horizon=horizon),
            signal_space(tree2, all_vars, horizon=horizon),
            all_vars)


def signal_spaces_from_tableau(formula1, formula2, tabex_root=None):
    """Both regions via stlsat's tableau -- the faster alternative.

    Kept because the tableau scales to formulas the denotational evaluator
    cannot, and because it is the only path that can read a hand-written .dot.
    It is *cross-checked* against the definition rather than trusted; see
    tests/test_reference_semantics.py.

    stlsat's SAT verdict is not consulted: standardize() prunes the branches
    stlsat left unexpanded, so an unsatisfiable formula extracts to no paths on
    its own. Eq. 7 then handles empty-vs-empty (1) and empty-vs-nonempty (0).
    """
    dot1 = run_stlsat(formula1, tabex_root=tabex_root)
    dot2 = run_stlsat(formula2, tabex_root=tabex_root)
    tree1, tree2 = build_tree_from_dot(dot1), build_tree_from_dot(dot2)
    all_vars = sorted(set(discover_all_variables(dot1)) | set(discover_all_variables(dot2)))
    all_times = sorted(collect_times(tree1) | collect_times(tree2))
    return (standardize(tree1, all_vars, all_times),
            standardize(tree2, all_vars, all_times),
            all_vars)


def calc_similarity_from_formulas(formula1, formula2, tabex_root=None, D=None,
                                  via="definition"):
    """Similarity of two formula strings.

    `via="definition"` (the default) computes each signal space by structural
    recursion on the formula -- the route Theorem A is about. `via="tableau"`
    computes it from stlsat instead, which is faster on large formulas and is
    validated against the definition rather than trusted.
    """
    if via == "definition":
        paths1, paths2, all_vars = signal_spaces_from_definition(formula1, formula2)
    elif via == "tableau":
        paths1, paths2, all_vars = signal_spaces_from_tableau(formula1, formula2, tabex_root)
    else:
        raise ValueError(f"via must be 'definition' or 'tableau', not {via!r}")
    volume1, volume2 = build_aligned_volumes(formula1, paths1, formula2, paths2, all_vars=all_vars)
    return compute_similarity(volume1, volume2, D=D)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute STL formula similarity from parse_graph.py's signal space.")
    parser.add_argument("formula1")
    parser.add_argument("formula2")
    parser.add_argument("--tabex-root", help="Override $TABEX_ROOT / ~/tabex.")
    parser.add_argument("--D", type=float, default=None, help="Truncation window; auto-derived if omitted.")
    parser.add_argument("--via", choices=("definition", "tableau"), default="definition",
                        help="Compute the signal space denotationally (default) or via stlsat's tableau.")
    cli_args = parser.parse_args()

    score = calc_similarity_from_formulas(cli_args.formula1, cli_args.formula2,
                                          tabex_root=cli_args.tabex_root, D=cli_args.D,
                                          via=cli_args.via)
    print(f"Similarity score between formula {cli_args.formula1!r} and formula {cli_args.formula2!r} is: {score}")
