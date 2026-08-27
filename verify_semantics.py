"""Randomised check that the extracted signal space IS the formula's semantics.

Complements verify_equivalence.py. That one asks whether two equivalent
formulas score G = 1; this one asks the more basic question the whole pipeline
rests on -- does the region standardize() + canonicalize() produce actually
equal the set of signals satisfying the formula?

It samples random discrete signals, evaluates the formula directly with the
small STL interpreter below, and compares that verdict against membership in
the extracted region. An over-approximation means the region admits a signal
the formula rejects; an under-approximation means the formula is satisfied by
a signal the region does not contain. Both are extraction bugs.

Nothing here consults stlsat's own "Tableau result:" verdict -- the pipeline
does not read it either, deriving emptiness from the graph instead (see
parse_graph.prune_incomplete).

Run with samples ON the integer boundaries as well as off them:

    python verify_semantics.py            # off-boundary (default)
    python verify_semantics.py --boundary # values land exactly on the bounds

The boundary run is the one that proves endpoint openness is right: with
closed-only intervals "x > 0" admits x = 0 and this reports it.

Needs cargo/z3 on PATH (it runs the real stlsat). Run from the repo root.
"""
import argparse
import random
import sys

sys.path.insert(0, ".")
from parse_graph import (  # noqa: E402
    build_tree_from_dot,
    discover_all_variables,
    merge_pieces,
    run_stlsat,
    standardize,
)
from similarity.canon import canonicalize  # noqa: E402
from similarity.stl_similarity import is_undefined, trim_trailing_undef  # noqa: E402

VARS = ["x", "y"]
OPS = [">", ">=", "<", "<="]
VALUES = [-3, -2, -1, 0, 1, 2, 3]


# --- a small STL interpreter, the ground truth ----------------------------
class Atom:
    def __init__(self, var, op, const):
        self.var, self.op, self.const = var, op, const

    def holds(self, signal, t):
        value = signal[self.var][t]
        return {'>': value > self.const, '>=': value >= self.const,
                '<': value < self.const, '<=': value <= self.const}[self.op]

    def __str__(self):
        return f"{self.var}{self.op}{self.const}"


class Not:
    def __init__(self, inner):
        self.inner = inner

    def holds(self, signal, t):
        return not self.inner.holds(signal, t)

    def __str__(self):
        return f"(!({self.inner}))"


class Binary:
    def __init__(self, op, left, right):
        self.op, self.left, self.right = op, left, right

    def holds(self, signal, t):
        if self.op == '&&':
            return self.left.holds(signal, t) and self.right.holds(signal, t)
        return self.left.holds(signal, t) or self.right.holds(signal, t)

    def __str__(self):
        return f"(({self.left}) {self.op} ({self.right}))"


class Temporal:
    def __init__(self, kind, lower, upper, body):
        self.kind, self.lower, self.upper, self.body = kind, lower, upper, body

    def holds(self, signal, t):
        window = range(t + self.lower, t + self.upper + 1)
        if self.kind == 'F':
            return any(self.body.holds(signal, u) for u in window)
        return all(self.body.holds(signal, u) for u in window)

    def __str__(self):
        return f"{self.kind}[{self.lower},{self.upper}]({self.body})"


def horizon(formula):
    if isinstance(formula, Temporal):
        return formula.upper + horizon(formula.body)
    if isinstance(formula, Binary):
        return max(horizon(formula.left), horizon(formula.right))
    if isinstance(formula, Not):
        return horizon(formula.inner)
    return 0


def random_proposition(depth=0):
    roll = random.random()
    if depth >= 2 or roll < 0.5:
        return Atom(random.choice(VARS), random.choice(OPS), random.randint(-2, 2))
    if roll < 0.6:
        return Not(random_proposition(depth + 1))
    return Binary(random.choice(['&&', '||']),
                  random_proposition(depth + 1), random_proposition(depth + 1))


def random_formula():
    # F/G/propositional only: their semantics are unambiguous, so a
    # disagreement is unambiguously the extraction's fault.
    if random.random() < 0.30:
        return random_proposition()
    lower = random.randint(0, 2)
    upper = lower + random.randint(0, 2)
    return Temporal(random.choice(['F', 'G']), lower, upper, random_proposition())


# --- membership in the extracted region -----------------------------------
def contains(interval, value):
    return ((value > interval.l if interval.lo else value >= interval.l) and
            (value < interval.r if interval.ro else value <= interval.r))


def in_region(cells, signal):
    for cell in cells:
        admitted = True
        for t, slot in cell.timeline.items():
            for var, pieces in slot.items():
                if is_undefined(pieces):
                    continue
                if not any(contains(iv, signal[var][t]) for iv in merge_pieces(pieces)):
                    admitted = False
                    break
            if not admitted:
                break
        if admitted:
            return True
    return False


def check(formula, tabex_root, samples, offset):
    text = str(formula)
    dot = run_stlsat(text, tabex_root=tabex_root)
    tree = build_tree_from_dot(dot)
    all_vars = discover_all_variables(dot) or VARS
    paths = standardize(tree, all_vars)
    cells = [trim_trailing_undef(c) for c in canonicalize(paths)]
    length = max(horizon(formula),
                 max((t for p in paths for t in p.timeline), default=0)) + 3
    over = under = 0
    for _ in range(samples):
        signal = {v: [random.choice(VALUES) + offset for _ in range(length)] for v in VARS}
        satisfied = formula.holds(signal, 0)
        admitted = in_region(cells, signal)
        if satisfied and not admitted:
            under += 1
        elif admitted and not satisfied:
            over += 1
    return over, under, len(cells)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--boundary", action="store_true",
                        help="Sample exactly ON the integer bounds (proves endpoint openness).")
    parser.add_argument("--trials", type=int, default=60)
    parser.add_argument("--samples", type=int, default=400)
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--tabex-root", default=".")
    args = parser.parse_args()

    random.seed(args.seed)
    offset = 0.0 if args.boundary else 0.5
    mismatched, errors, checked = [], [], 0
    for _ in range(args.trials):
        formula = random_formula()
        try:
            over, under, cells = check(formula, args.tabex_root, args.samples, offset)
        except Exception as exc:  # stlsat failure, parse failure, ...
            errors.append((str(formula), str(exc).splitlines()[0][:80]))
            continue
        checked += 1
        if over or under:
            mismatched.append((str(formula), over, under, cells))

    for text, over, under, cells in mismatched:
        print(f"MISMATCH over={over} under={under} cells={cells}\n    {text}")
    for text, message in errors:
        print(f"ERROR      {text}\n       {message}")

    print()
    status = "ok" if not mismatched and not errors else "FAIL"
    where = "on-boundary" if args.boundary else "off-boundary"
    print(f"  {checked} formulas checked ({where}, {args.samples} signals each), "
          f"{len(mismatched)} disagreed with the semantics, {len(errors)} errored   {status}")
    return 1 if mismatched or errors else 0


if __name__ == "__main__":
    sys.exit(main())
