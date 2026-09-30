"""Madsen et al., "Metrics for Signal Temporal Logic Formulae", CDC 2018.

A baseline to compare TABEX against. Two distances between formulas:

* `d_ph` -- Pompeiu-Hausdorff distance between the bounded-time languages,
  computed per Theorem 2 as a MILP (scipy's HiGHS instead of Gurobi).
* `d_sd` -- symmetric difference of the "area of satisfaction" boxes of
  Algorithm 1 (AoS), normalised by the horizon T.

Both walk `reference_semantics`' NNF AST, so the two tools read formulas with
one parser. The paper's assumptions are enforced here:

* the signal domain is compact, S = [lo, hi] per variable (Assumption 1);
* predicates are rectangular `x ~ c` with ~ in {<, <=, >, >=} (Assumption 2).
  Strictness is dropped: the paper works with closed languages and counts
  rho = 0 as satisfaction. `==` / `!=` are refused.
"""
import itertools
import sys
from pathlib import Path as FilePath

import numpy as np
from scipy.optimize import Bounds, LinearConstraint, milp
from scipy.sparse import coo_matrix

sys.path.insert(0, str(FilePath(__file__).resolve().parent.parent))

from similarity.intervals import UnsupportedFormula  # noqa: E402
from similarity.reference_semantics import (  # noqa: E402
    Always, And, Atom, Constant, Eventually, Or, Until, constants, parse, variables,
)

LOWER = (">", ">=")   # x >= c
UPPER = ("<", "<=")   # x <= c


def _check_rectangular(op):
    if op not in LOWER + UPPER:
        raise UnsupportedFormula(
            f"Madsen et al. need rectangular predicates (<, <=, >, >=); got {op!r}")


def _tree(formula):
    return parse(formula) if isinstance(formula, str) else formula


# --------------------------------------------------------------------------
# Pompeiu-Hausdorff distance (Section IV-A)
# --------------------------------------------------------------------------

class _Milp:
    """Row-by-row MILP builder: s[t,v] continuous, eps continuous, z binary."""

    def __init__(self, lo, hi, big_m):
        self.lo, self.hi, self.big_m = lo, hi, big_m
        self.lb, self.ub, self.integer = [0.0], [hi - lo], [0]   # var 0 is eps
        self.signal = {}
        self.rows, self.row_lb, self.row_ub = [], [], []

    def var(self, lb, ub, integer):
        self.lb.append(lb), self.ub.append(ub), self.integer.append(integer)
        return len(self.lb) - 1

    def binary(self, ub=1):
        return self.var(0, ub, 1)

    def s(self, t, v):
        if (t, v) not in self.signal:
            self.signal[(t, v)] = self.var(self.lo, self.hi, 0)
        return self.signal[(t, v)]

    def row(self, coeffs, lb=-np.inf, ub=np.inf):
        self.rows.append(coeffs), self.row_lb.append(lb), self.row_ub.append(ub)

    def encode(self, node, t, tight):
        """Binary z with z = 1  =>  node holds at t.

        One direction suffices: we only ask whether a satisfying signal exists.
        `tight` shrinks every predicate by eps (x >= c + eps, x <= c - eps).
        """
        if isinstance(node, Constant):
            return self.binary(ub=1 if node.value else 0)
        z = self.binary()
        if isinstance(node, Atom):
            _check_rectangular(node.op)
            c, x, e, m = float(node.constant), self.s(t, node.variable), 0, self.big_m
            if node.op in LOWER:   # x - tight*eps + M(1-z) >= c
                self.row({x: 1, e: -tight, z: -m}, lb=c - m)
            else:                  # x + tight*eps - M(1-z) <= c
                self.row({x: 1, e: tight, z: m}, ub=c + m)
            return z
        if isinstance(node, Until):
            node = node.expand()
        if isinstance(node, (And, Or)):
            kids = [self.encode(node.left, t, tight), self.encode(node.right, t, tight)]
        elif isinstance(node, (Always, Eventually)):
            kids = [self.encode(node.body, t + k, tight)
                    for k in range(node.lower, node.upper + 1)]
        else:
            raise TypeError(f"not a formula node: {node!r}")
        if isinstance(node, (And, Always)):
            for k in kids:                                    # z <= z_k
                self.row({z: 1, k: -1}, ub=0)
        else:                                                 # z <= sum z_k
            coeffs = {k: -1 for k in kids}
            coeffs[z] = 1
            self.row(coeffs, ub=0)
        return z

    def solve(self):
        n = len(self.lb)
        data, rows, cols = [], [], []
        for i, coeffs in enumerate(self.rows):
            for j, a in coeffs.items():
                if a:
                    rows.append(i), cols.append(j), data.append(a)
        A = coo_matrix((data, (rows, cols)), shape=(len(self.rows), n))
        objective = np.zeros(n)
        objective[0] = -1                                     # maximise eps
        return milp(objective, integrality=np.array(self.integer),
                    bounds=Bounds(self.lb, self.ub),
                    constraints=LinearConstraint(A, self.row_lb, self.row_ub))


def directed_ph(phi1, phi2, lo=0.0, hi=1.0):
    """Directed PH distance, Theorem 2: max eps s.t. s |= phi1, s |/= phi2^{eps+}.

    s |/= phi2^{eps+}  <=>  rho(s, phi2) + eps < 0  <=>  rho(s, !phi2) > eps, so
    the second constraint is !phi2 (NNF) with every predicate tightened by eps
    (closed, as the paper's sup permits). Infeasible means L(phi1) is inside
    L(phi2) -- or phi1 is unsatisfiable -- and the distance is 0 (eq. 10).

    ponytail: eps is capped at hi - lo, which is what an unsatisfiable phi2
    (infinite distance, outside the paper's L != {} assumption) returns.
    """
    t1, t2 = _tree(phi1), _tree(phi2)
    consts = [abs(float(c)) for c in constants(t1) | constants(t2)]
    big_m = 2 * (hi - lo) + max(consts + [abs(lo), abs(hi)]) + 1
    model = _Milp(lo, hi, big_m)
    for root in (model.encode(t1, 0, 0), model.encode(t2.negate(), 0, 1)):
        model.lb[root] = 1
    res = model.solve()
    if res.status == 2:        # infeasible
        return 0.0
    if res.status != 0:
        raise RuntimeError(f"MILP failed: {res.message}")
    return max(0.0, -res.fun)


def d_ph(phi1, phi2, lo=0.0, hi=1.0):
    """Undirected PH distance, eq. (4): (d, d(phi1->phi2), d(phi2->phi1))."""
    forward, backward = directed_ph(phi1, phi2, lo, hi), directed_ph(phi2, phi1, lo, hi)
    return max(forward, backward), forward, backward


# --------------------------------------------------------------------------
# Symmetric difference (Section IV-B, Algorithm 1)
#
# A box is (lt, ut, lv, uv, var) in time x normalised value. aos() returns the
# paper's "choice set" (the || operator) as a list of alternatives; each
# alternative is a list of boxes read CONJUNCTIVELY: at any instant, a
# variable's allowed values are the intersection of its boxes covering that
# instant. That is exactly what Algorithm 1's `combine` computes pairwise
# (intersection on the time overlap, each box's own values outside it), so
# conjunction reduces to concatenating box lists.
# --------------------------------------------------------------------------

def aos(node, lo, hi, delta=1):
    """Algorithm 1: area-of-satisfaction boxes, as a list of alternatives."""
    if isinstance(node, Constant):
        # ponytail: a nested `true` constrains nothing, so it adds no box. The
        # top-level one (paper's column/row for T) is handled in d_sd.
        return [[]] if node.value else []
    if isinstance(node, Atom):
        _check_rectangular(node.op)
        c = min(max((float(node.constant) - lo) / (hi - lo), 0.0), 1.0)
        values = (c, 1.0) if node.op in LOWER else (0.0, c)
        return [[(0, 0, *values, node.variable)]]
    if isinstance(node, Until):
        return aos(node.expand(), lo, hi, delta)
    if isinstance(node, And):
        return [a + b for a, b in itertools.product(aos(node.left, lo, hi, delta),
                                                    aos(node.right, lo, hi, delta))]
    if isinstance(node, Or):
        return aos(node.left, lo, hi, delta) + aos(node.right, lo, hi, delta)
    if isinstance(node, Always):
        return [[(lt + node.lower, ut + node.upper, lv, uv, v)
                 for lt, ut, lv, uv, v in alt]
                for alt in aos(node.body, lo, hi, delta)]
    if isinstance(node, Eventually):
        # F[t1,t2] ~ OR_i G[t1+delta(i-1), t1+delta*i]: a mandatory delta "hold".
        windows = [(node.lower + delta * (i - 1), node.lower + delta * i)
                   for i in range(1, (node.upper - node.lower) // delta + 1)]
        windows = windows or [(node.lower, node.lower)]
        return [alt for a, b in windows
                for alt in aos(Always(a, b, node.body), lo, hi, delta)]
    raise TypeError(f"not a formula node: {node!r}")


def _sd_area(alt1, alt2):
    """sum over variables of the area of (U alt1) symmetric-difference (U alt2)."""
    total = 0.0
    for var in {b[4] for b in alt1 + alt2}:
        boxes1 = [b for b in alt1 if b[4] == var]
        boxes2 = [b for b in alt2 if b[4] == var]
        cuts = sorted({t for b in boxes1 + boxes2 for t in b[:2]})
        for p, q in zip(cuts, cuts[1:]):
            spans = []
            for boxes in (boxes1, boxes2):
                cover = [b for b in boxes if b[0] <= p and b[1] >= q]
                if cover:
                    spans.append((max(b[2] for b in cover), min(b[3] for b in cover)))
                else:
                    spans.append((0.0, 0.0))
            (l1, u1), (l2, u2) = spans
            len1, len2 = max(0.0, u1 - l1), max(0.0, u2 - l2)
            meet = max(0.0, min(u1, u2) - max(l1, l2)) if len1 and len2 else 0.0
            total += (q - p) * (len1 + len2 - 2 * meet)
    return total


def d_sd(phi1, phi2, lo=0.0, hi=1.0, delta=1):
    """SD distance: |B1 sym-diff B2| / T, T the larger horizon.

    Normalised by T, not the T+1 of Definition 3: that is what reproduces
    Table I (and Fig. 1's 0.72 / 20 = 0.036). The || choice is resolved by the
    most favourable pair of alternatives -- the paper leaves it open.
    """
    t1, t2 = _tree(phi1), _tree(phi2)
    horizon = max(t1.horizon(), t2.horizon())
    all_vars = sorted(variables(t1) | variables(t2))

    def alternatives(tree):
        if isinstance(tree, Constant) and tree.value:     # T: the whole space
            return [[(0, horizon, 0.0, 1.0, v) for v in all_vars]]
        return aos(tree, lo, hi, delta) or [[]]           # unsat: no area

    return min(_sd_area(a, b) for a in alternatives(t1) for b in alternatives(t2)) \
        / max(horizon, 1)
