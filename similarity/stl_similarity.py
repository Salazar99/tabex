"""STL similarity metric, per preliminaries.tex.

Operates directly on parse_graph.py's signal space (list[Path], each
Path.timeline: {t: {var: [Interval, ...]}}) instead of a separate JSON
"bounds" format -- see similarity/stl_similarity.py.bk for the previous
implementation, which consumed dotparser/input_creator.py's output.
"""
import argparse
import sys
from pathlib import Path as FilePath

sys.path.insert(0, str(FilePath(__file__).resolve().parent.parent))

from parse_graph import Interval, Path, generate_signal_space_from_formula, merge_pieces
from similarity.align import align

UNDEFINED = [Interval(float("-inf"), float("inf"))]


def measure(pieces):
    total = 0.0
    for iv in merge_pieces(pieces):
        length = iv.r - iv.l
        if length == float("inf"):
            return float("inf")
        total += length
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
    result = []
    for iv in pieces:
        l, r = max(iv.l, -D), min(iv.r, D)
        if l <= r:
            result.append(Interval(l, r))
    return result


def point_sim_d(pieces1, pieces2, D):
    # Eq. PointSimD: truncate to the D-window first, then a single Jaccard
    # formula covers every remaining case (no separate distance-decay case).
    undef1, undef2 = is_undefined(pieces1), is_undefined(pieces2)
    if undef1 and undef2:
        return 1.0
    if undef1 != undef2:
        return 0.0

    t1, t2 = truncate(pieces1, D), truncate(pieces2, D)
    intersection = measure(intersect_pieces(t1, t2))
    if intersection == 0:
        return 0.0
    union = measure(union_pieces(t1, t2))
    return intersection / union if union > 0 else 0.0


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
    return (max(bounds) if bounds else 0.0) + margin


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
    if not volume1.volume:
        return 1.0
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


def build_volume_from_paths(formula_name, paths, all_vars=None):
    if all_vars is None:
        all_vars = sorted(next(iter(paths[0].timeline.values())).keys()) if paths else []
    return FormulaVolume(formula_name, all_vars, [trim_trailing_undef(p) for p in paths])


def build_aligned_volumes(formula1, paths1, formula2, paths2, all_vars=None):
    # Align both formulas' path decompositions onto a shared cell grid
    # (Section 4.3) before they're compared -- required for the soundness
    # guarantee G(phi,theta)=1 <=> phi==theta (Section 6): two equivalent
    # formulas can otherwise cut the same region into different boxes.
    volume1 = build_volume_from_paths(formula1, paths1, all_vars)
    volume2 = build_volume_from_paths(formula2, paths2, all_vars)
    volume1.volume, volume2.volume = align(volume1.volume, volume2.volume)
    return volume1, volume2


def calc_similarity_from_formulas(formula1, formula2, tabex_root=None, D=None):
    paths1 = generate_signal_space_from_formula(formula1, tabex_root=tabex_root)
    paths2 = generate_signal_space_from_formula(formula2, tabex_root=tabex_root)
    volume1, volume2 = build_aligned_volumes(formula1, paths1, formula2, paths2)
    return compute_similarity(volume1, volume2, D=D)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute STL formula similarity from parse_graph.py's signal space.")
    parser.add_argument("formula1")
    parser.add_argument("formula2")
    parser.add_argument("--tabex-root", help="Override $TABEX_ROOT / ~/tabex.")
    parser.add_argument("--D", type=float, default=None, help="Truncation window; auto-derived if omitted.")
    cli_args = parser.parse_args()

    score = calc_similarity_from_formulas(cli_args.formula1, cli_args.formula2, tabex_root=cli_args.tabex_root, D=cli_args.D)
    print(f"Similarity score between formula {cli_args.formula1!r} and formula {cli_args.formula2!r} is: {score}")
