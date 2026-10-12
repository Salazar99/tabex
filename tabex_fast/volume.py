"""Exact volume Jaccard of two signal spaces -- the ablation baseline for G.

    VolJ(phi, theta) = |S(phi) ∩ S(theta)|_eps / |S(phi) ∪ S(theta)|_eps

on the D-window [-D, D]^A of the common grid, with the endpoint-aware measure
of Definition 3 taken axis by axis (a product measure): an open atom weighs its
Lebesgue length inside [-D, D], a point atom [c, c] weighs eps. This is the
"whole-region" similarity one gets for free from the decision diagram, without
canonical boxes: VolJ = 1 iff the two regions coincide (the eps term sees every
endpoint), exactly like G, but it aggregates by volume instead of by box.

Both formulas are built on ONE diagram over the joint arrangement (every
constant of either formula), so AND/OR of the two roots are single applys, and
the measure is a memoised sum over children. Weights are normalised per axis
(divided by the axis' total mass) so products stay in [0, 1] at any horizon; the
ratio is unchanged by that.

    python -m tabex_fast.volume "G[0,20](x>=0.2 && x<=0.4)" "G[0,20](x>=0.2 && x<=0.44)"
"""
import argparse
import sys
from collections import defaultdict
from fractions import Fraction
from pathlib import Path as FilePath

sys.path.insert(0, str(FilePath(__file__).resolve().parent.parent))

from similarity.canon import _cut_piece  # noqa: E402
from similarity.intervals import Interval  # noqa: E402
from similarity.reference_semantics import parse, variables  # noqa: E402
from similarity.stl_similarity import EPS, resolve_D  # noqa: E402
from tabex_fast.engine import INF, Diagram, Region, _atoms  # noqa: E402


class JointRegions(Region):
    """Several formulas over one fine diagram (no canonicalisation needed)."""

    def __init__(self, trees, all_vars, horizon):
        self.axes = [(t, v) for t in range(horizon + 1) for v in all_vars]
        cuts = defaultdict(set)
        for tree in trees:
            for var, c in _atoms(tree):
                cuts[var].add(c)
        self.cuts = cuts
        self.fine = [_cut_piece(Interval(-INF, INF), cuts[v]) for _, v in self.axes]
        self.diagram = Diagram([len(a) for a in self.fine])
        self.level = {axis: k for k, axis in enumerate(self.axes)}
        memo = {}
        self.roots = [self._build(self.diagram, tree, 0, memo) for tree in trees]


def _weights(atoms, D, eps):
    window = Interval(-D, D)
    out = []
    for a in atoms:
        clipped = a.intersect(window)
        if clipped is None:
            out.append(Fraction(0))
        elif clipped.l == clipped.r:
            out.append(eps)
        else:
            out.append(Fraction(clipped.r - clipped.l))
    total = sum(out)
    return [float(w / total) for w in out]


def volume_jaccard(formula1, formula2, D=None, eps=EPS):
    tree1, tree2 = parse(formula1), parse(formula2)
    D = Fraction(resolve_D(D, tree1, tree2))
    all_vars = sorted(variables(tree1) | variables(tree2))
    horizon = max(tree1.horizon(), tree2.horizon())
    joint = JointRegions([tree1, tree2], all_vars, horizon)
    d = joint.diagram
    weights = [_weights(atoms, D, Fraction(eps)) for atoms in joint.fine]
    memo = {0: 0.0, 1: 1.0}

    def mass(n):
        if n not in memo:
            k, children = d.nodes[n]
            memo[n] = 0.0 if d.is_false(n) else sum(
                w * mass(c) for w, c in zip(weights[k], children) if w)
        return memo[n]

    r1, r2 = joint.roots
    union = mass(d.apply("or", r1, r2))
    if union == 0.0:
        return 1.0          # both empty: equivalent, as in Eq. 7
    return mass(d.apply("and", r1, r2)) / union


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Exact volume Jaccard of two signal spaces.")
    parser.add_argument("formula1")
    parser.add_argument("formula2")
    parser.add_argument("--D", type=Fraction, default=None)
    args = parser.parse_args()
    print(volume_jaccard(args.formula1, args.formula2, D=args.D))
