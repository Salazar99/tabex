"""TABEX's similarity score, computed without listing cells.

Same number as `similarity.stl_similarity.calc_similarity_from_formulas`
(via="definition"), up to float rounding, but the pipeline
evaluate -> boxes -> canonicalize -> trim -> average-of-max never
materialises a box or a cell:

1. Each formula's region is a quasi-reduced, hash-consed multi-valued decision
   diagram (MDD) over the axes (t, var), one level per axis in t-major order,
   one edge per arrangement atom. AND/OR are memoised `apply`s, and
   `build(node, t)` is memoised per (subformula, instant). `G[0,16] F[0,4]` stays
   a few nodes per level; the box list would have 5^17 entries.
2. Canonicalisation reads off the diagram. The diagram is deterministic, so
   every prefix reaches exactly one node per level, and `_axis_partition`'s
   fibre test becomes "same child under every reachable node". Relabelling edges
   by slab gives the canonical cells as the diagram's accepted strings.
3. The score is a DP over levels. Each state carries a c1-diagram node and a
   Viterbi vector: the best partial path_similarity over every (length, node)
   of the c2 diagram. States with equal keys merge by adding their counts, so
   the cost follows the number of distinct keys, not the ~10^10 cells.

    python -m tabex_fast.engine "F[0,20](x>=0.2 && x<=0.4)" "G[0,16] F[0,4](x>=0.2 && x<=0.4)"
"""
import argparse
import sys
from collections import defaultdict
from fractions import Fraction
from pathlib import Path as FilePath

sys.path.insert(0, str(FilePath(__file__).resolve().parent.parent))

from similarity.intervals import Interval  # noqa: E402
from similarity.reference_semantics import (  # noqa: E402
    Always, And, Atom, Constant, Eventually, Or, Until, atom_intervals, constant_value,
    parse, variables,
)
from similarity.canon import _cut_piece  # noqa: E402
from similarity.stl_similarity import EPS, is_undefined, point_sim_d, resolve_D  # noqa: E402

INF = float("inf")
sys.setrecursionlimit(max(10000, sys.getrecursionlimit()))


class Diagram:
    """Hash-consed MDD over fixed levels. Node = (level, children); level K is terminal."""

    def __init__(self, arities):
        self.K = len(arities)
        self.nodes = [(self.K, ()), (self.K, ())]          # 0 = reject, 1 = accept
        self.unique, self.memo, self.counts = {}, {}, {}
        self.false, self.true = [0] * (self.K + 1), [1] * (self.K + 1)
        for k in reversed(range(self.K)):
            self.false[k] = self.mk(k, (self.false[k + 1],) * arities[k])
            self.true[k] = self.mk(k, (self.true[k + 1],) * arities[k])

    def mk(self, k, children):
        key = (k, children)
        if key not in self.unique:
            self.unique[key] = len(self.nodes)
            self.nodes.append(key)
        return self.unique[key]

    def children(self, n):
        return self.nodes[n][1]

    def is_false(self, n):
        return n == self.false[self.nodes[n][0]]

    def apply(self, op, a, b):
        k = self.nodes[a][0]
        if op == "and":
            if a == self.false[k] or b == self.true[k]:
                return a
            if b == self.false[k] or a == self.true[k]:
                return b
        else:
            if a == self.true[k] or b == self.false[k]:
                return a
            if b == self.true[k] or a == self.false[k]:
                return b
        if a == b:
            return a
        key = (op, min(a, b), max(a, b))
        if key not in self.memo:
            self.memo[key] = self.mk(k, tuple(
                self.apply(op, x, y) for x, y in zip(self.children(a), self.children(b))))
        return self.memo[key]

    def count(self, n):
        """Accepted strings below n -- the number of cells."""
        if n in (0, 1):
            return n
        if n not in self.counts:
            self.counts[n] = sum(self.count(c) for c in self.children(n))
        return self.counts[n]

    def reachable(self, root):
        levels, frontier = [], {root}
        for _ in range(self.K):
            levels.append(sorted(frontier))
            frontier = {c for n in frontier for c in self.children(n) if not self.is_false(c)}
        return levels


def _atoms(node):
    """Every (variable, constant) the formula compares."""
    if isinstance(node, Atom):
        yield node.variable, constant_value(node.constant)
    elif isinstance(node, (And, Or)):
        yield from _atoms(node.left)
        yield from _atoms(node.right)
    elif isinstance(node, (Eventually, Always)):
        yield from _atoms(node.body)
    elif isinstance(node, Until):
        yield from _atoms(node.invariant)
        yield from _atoms(node.witness)


class Region:
    """One formula's canonical region, over a given ambient grid.

    `slabs[k]` is the canonical partition of axis k; the accepted strings of
    `diagram` from `root` are exactly `canonicalize(signal_space(...))`.
    """

    def __init__(self, tree, all_vars, horizon):
        self.axes = [(t, v) for t in range(horizon + 1) for v in all_vars]
        # Breakpoints: every constant on the variable. A superset of what the
        # boxes carry; runs are defined from the region alone (Definition 5,
        # Theorem 2), so any refining breakpoint set gives the same ones.
        cuts = defaultdict(set)
        for var, c in _atoms(tree):
            cuts[var].add(c)
        self.fine = [_cut_piece(Interval(-INF, INF), cuts[v]) for _, v in self.axes]
        fine = Diagram([len(a) for a in self.fine])
        self.level = {axis: k for k, axis in enumerate(self.axes)}
        root = self._build(fine, tree, 0, {})
        self._canonicalize(fine, root)

    def _atom(self, fine, node, t):
        k0 = self.level[(t, node.variable)]
        allowed = atom_intervals(node.op, node.constant)
        n = fine.true[k0 + 1]
        inside = tuple(n if any(a.intersect(iv) is not None for iv in allowed)
                       else fine.false[k0 + 1] for a in self.fine[k0])
        n = fine.mk(k0, inside)
        for k in reversed(range(k0)):
            n = fine.mk(k, (n,) * len(self.fine[k]))
        return n

    def _build(self, fine, node, t, memo):
        key = (id(node), t)
        if key in memo:
            return memo[key]
        if isinstance(node, Constant):
            out = fine.true[0] if node.value else fine.false[0]
        elif isinstance(node, Atom):
            out = self._atom(fine, node, t)
        elif isinstance(node, (And, Or)):
            out = fine.apply("and" if isinstance(node, And) else "or",
                             self._build(fine, node.left, t, memo),
                             self._build(fine, node.right, t, memo))
        elif isinstance(node, (Eventually, Always)):
            op = "or" if isinstance(node, Eventually) else "and"
            out = fine.true[0] if op == "and" else fine.false[0]
            for offset in range(node.lower, node.upper + 1):
                out = fine.apply(op, out, self._build(fine, node.body, t + offset, memo))
        elif isinstance(node, Until):
            # As reference_semantics.evaluate: the invariant holds on the
            # CLOSED range up to and including the witness instant.
            out = fine.false[0]
            for offset in range(node.lower, node.upper + 1):
                term = self._build(fine, node.witness, t + offset, memo)
                for moment in range(t, t + offset + 1):
                    term = fine.apply("and", term, self._build(fine, node.invariant, moment, memo))
                out = fine.apply("or", out, term)
        else:
            raise TypeError(f"not a formula node: {node!r}")
        memo[key] = out
        return out

    def _canonicalize(self, fine, root):
        reach = fine.reachable(root)
        self.slabs, firsts = [], []
        for k, atoms in enumerate(self.fine):
            nodes = reach[k] if not fine.is_false(root) else []
            column = [tuple(fine.children(n)[i] for n in nodes) for i in range(len(atoms))]
            occurring = [i for i in range(len(atoms))
                         if any(not fine.is_false(c) for c in column[i])]
            slabs, first = [], []
            for i in occurring:      # _cut_piece emits atoms in order
                iv = atoms[i]
                if slabs:
                    cur = slabs[-1]
                    touching = iv.l == cur.r and not (iv.lo and cur.ro)
                    if touching and column[i] == column[first[-1]]:
                        slabs[-1] = Interval(cur.l, iv.r, cur.lo, iv.ro)
                        continue
                slabs.append(iv)
                first.append(i)
            self.slabs.append(slabs)
            firsts.append(first)

        self.diagram = Diagram([max(1, len(s)) for s in self.slabs])
        if fine.is_false(root):
            self.root = self.diagram.false[0]
            return
        memo = {0: 0, 1: 1}

        def coarse(n):
            if n not in memo:
                k, children = fine.nodes[n]
                if fine.is_false(n):
                    memo[n] = self.diagram.false[k]
                else:
                    memo[n] = self.diagram.mk(k, tuple(coarse(children[i]) for i in firsts[k]))
            return memo[n]

        self.root = coarse(root)

    def cells(self):
        return self.diagram.count(self.root)

    def of_length(self, length):
        """Root of the cells whose trimmed length (trim_trailing_undef) is `length`."""
        d, undef = self.diagram, [next((i for i, s in enumerate(slabs) if is_undefined([s])), None)
                                  for slabs in self.slabs]
        horizon = self.axes[-1][0] if self.axes else -1
        memo = {}

        def rec(k, defined):   # `defined`: seen a defined slab at instant length-1
            if k == d.K:
                return d.true[k] if length != horizon + 1 or defined or length == 0 else d.false[k]
            t = self.axes[k][0]
            first_of_instant = k == 0 or self.axes[k - 1][0] != t
            if 1 <= length == t and first_of_instant and not defined:
                return d.false[k]
            if (k, defined) not in memo:
                kids = []
                for i in range(len(d.children(d.true[k]))):
                    if t >= length:
                        kids.append(rec(k + 1, defined) if i == undef[k] else d.false[k + 1])
                    elif t == length - 1:
                        kids.append(rec(k + 1, defined or i != undef[k]))
                    else:
                        kids.append(rec(k + 1, False))
                memo[(k, defined)] = d.mk(k, tuple(kids))
            return memo[(k, defined)]

        return d.apply("and", self.root, rec(0, False))


def one_way(r1, r2, D, eps=EPS):
    """Eq. 7: mean over r1's cells of the best path_similarity against r2's."""
    n1, n2 = r1.cells(), r2.cells()
    if not n1 and not n2:
        return 1.0
    if not n1 or not n2:
        return 0.0
    d1, d2 = r1.diagram, r2.diagram
    n_vars = len({v for _, v in r1.axes})
    horizon = r1.axes[-1][0] if r1.axes else -1   # V = {}: no axes, one empty box
    table = [[[point_sim_d([a], [b], D, eps) for b in s2] for a in s1]
             for s1, s2 in zip(r1.slabs, r2.slabs)]
    by_length = [(L, r2.of_length(L)) for L in range(horizon + 2)]
    by_length = [(L, n) for L, n in by_length if d2.count(n)]

    total = 0.0
    for L1 in range(horizon + 2):
        root1 = r1.of_length(L1)
        if not d1.count(root1):
            continue
        states = {(root1, tuple(((L2, n), 0.0) for L2, n in by_length)): 1}
        for k, (t, _) in enumerate(r1.axes):
            step = defaultdict(int)
            for (node1, entries), count in states.items():
                for a, child1 in enumerate(d1.children(node1)):
                    if d1.is_false(child1):
                        continue
                    best = {}
                    for (L2, node2), value in entries:
                        active = t < min(L1, L2)
                        for b, child2 in enumerate(d2.children(node2)):
                            if d2.is_false(child2):
                                continue
                            v = value + table[k][a][b] if active else value
                            if v > best.get((L2, child2), -1.0):
                                best[(L2, child2)] = v
                    step[(child1, tuple(sorted(best.items())))] += count
            states = step
        for (_, entries), count in states.items():
            total += count * max(1.0 if max(L1, L2) == 0 else value / (max(L1, L2) * n_vars)
                                 for (L2, _), value in entries)
    return total / n1


def regions(formula1, formula2):
    """Both canonical regions over the joint grid, as signal_spaces_from_definition."""
    tree1, tree2 = parse(formula1), parse(formula2)
    all_vars = sorted(variables(tree1) | variables(tree2))
    horizon = max(tree1.horizon(), tree2.horizon())
    return Region(tree1, all_vars, horizon), Region(tree2, all_vars, horizon), tree1, tree2


def similarity(formula1, formula2, D=None, eps=EPS):
    r1, r2, tree1, tree2 = regions(formula1, formula2)
    D = resolve_D(D, tree1, tree2)
    eps = Fraction(eps)
    if eps <= 0:
        raise ValueError(f"eps must be positive (Definition 3: eps > 0), got {eps}")
    return (one_way(r1, r2, D, eps) + one_way(r2, r1, D, eps)) / 2


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="TABEX similarity via decision diagrams.")
    parser.add_argument("formula1")
    parser.add_argument("formula2")
    parser.add_argument("--D", type=Fraction, default=None)
    parser.add_argument("--eps", type=Fraction, default=EPS)
    args = parser.parse_args()
    score = similarity(args.formula1, args.formula2, D=args.D, eps=args.eps)
    print(f"Similarity score between formula {args.formula1!r} and formula {args.formula2!r} is: {score}")
