"""The denotational definition E of the signal space (the paper's Appendix A.3).

One test per clause of the recursion, the fragment's exactness, and Theorem 1
itself checked by sampling: box membership against an independent evaluator
of the satisfaction relation of Appendix A.2.
"""
import math
import random
from fractions import Fraction

import pytest

from conftest import REPO_ROOT  # noqa: F401  (puts the repo on sys.path)
from similarity.intervals import UnsupportedFormula
from similarity.reference_semantics import (
    Always,
    And,
    Atom,
    Constant,
    Eventually,
    Or,
    Until,
    atom_intervals,
    evaluate,
    parse,
    signal_space,
)
from similarity.canon import canonicalize, cell_key

INF = math.inf
VARS = ["x", "y"]


def region(paths):
    return {cell_key(cell) for cell in canonicalize(paths)}


def space(formula, horizon=None):
    return region(signal_space(formula, VARS, horizon=horizon))


def contains(interval, value):
    return ((value > interval.l if interval.lo else value >= interval.l) and
            (value < interval.r if interval.ro else value <= interval.r))


def admits(formula, signal, horizon=None):
    """Does the region admit this concrete signal?  signal: {var: [v0, v1, ...]}"""
    if horizon is None:
        horizon = formula.horizon()
    for path in signal_space(formula, VARS, horizon=horizon):
        if all(any(contains(iv, signal[v][t]) for iv in pieces)
               for t, slot in path.timeline.items()
               for v, pieces in slot.items()):
            return True
    return False


# --- one case per line of the recursion -----------------------------------

def test_atom_constrains_exactly_one_axis():
    boxes = evaluate(Atom("x", ">", 0), 0)
    assert len(boxes) == 1
    assert list(boxes[0]) == [(0, "x")]
    assert boxes[0][(0, "x")].to_tuple() == (0.0, INF, True, True)


def test_atom_may_already_be_a_union_of_boxes():
    # "!=" is two open half-lines, so a single atom is two boxes.
    boxes = evaluate(Atom("x", "!=", 5), 0)
    assert [b[(0, "x")].to_tuple() for b in boxes] == [
        (-INF, 5.0, True, True), (5.0, INF, True, True)]


def test_and_intersects_or_unions():
    x, y = Atom("x", ">", 0), Atom("y", ">", 0)
    assert admits(And(x, y), {"x": [1], "y": [1]})
    assert not admits(And(x, y), {"x": [1], "y": [-1]})
    assert admits(Or(x, y), {"x": [1], "y": [-1]})
    assert not admits(Or(x, y), {"x": [-1], "y": [-1]})


def test_always_requires_every_instant_eventually_requires_one():
    positive = Atom("x", ">", 0)
    assert admits(Always(0, 2, positive), {"x": [1, 1, 1], "y": [0, 0, 0]})
    assert not admits(Always(0, 2, positive), {"x": [1, -1, 1], "y": [0, 0, 0]})
    assert admits(Eventually(0, 2, positive), {"x": [-1, 1, -1], "y": [0, 0, 0]})
    assert not admits(Eventually(0, 2, positive), {"x": [-1, -1, -1], "y": [0, 0, 0]})


def test_negate_pushes_to_atoms_and_is_involutive():
    for formula in (Atom("x", ">", 0),
                    And(Atom("x", ">", 0), Atom("y", "<=", 1)),
                    Eventually(0, 2, Atom("x", ">", 0)),
                    Always(0, 1, Or(Atom("x", ">", 0), Atom("y", "==", 2)))):
        assert space(formula.negate().negate()) == space(formula)


def test_negation_really_is_the_complement():
    # phi and !phi must partition the grid: no signal in both, none in neither.
    # This is what needs endpoint openness -- with closed-only intervals the
    # complement of (0,inf) would overlap it at 0.
    formula = Eventually(0, 1, Atom("x", ">", 0))
    negated = formula.negate()
    for values in ([1, 1], [1, -1], [-1, 1], [-1, -1], [0, 0]):
        signal = {"x": values, "y": [0, 0]}
        assert admits(formula, signal, horizon=1) != admits(negated, signal, horizon=1)


# --- the until convention --------------------------------------------------

def test_until_includes_its_witness():
    # THE discriminator. This variant requires the invariant AT the witness, so
    # U[0,0] is "phi && psi"; textbook STL's half-open until gives "psi" alone.
    # It is a definition, not an accident -- the paper's Remark 1.
    until = Until(0, 0, Atom("x", ">", 0), Atom("y", ">", 3))
    assert space(until) == space(And(Atom("x", ">", 0), Atom("y", ">", 3)))
    assert space(until) != space(Atom("y", ">", 3))


def test_until_expands_to_a_finite_disjunction():
    # "until" is sugar in a bounded discrete setting, which is how negate()
    # avoids ever needing a "release" operator.
    until = Until(0, 2, Atom("x", ">", 0), Atom("y", ">", 3))
    assert space(until) == space(until.expand())


def test_negated_until_is_the_complement():
    until = Until(0, 1, Atom("x", ">", 0), Atom("y", ">", 3))
    negated = until.negate()
    for xs in ([1, 1], [1, -1], [-1, 1], [-1, -1]):
        for ys in ([4, 4], [4, 0], [0, 4], [0, 0]):
            signal = {"x": xs, "y": ys}
            assert admits(until, signal, horizon=1) != admits(negated, signal, horizon=1)


# --- the fragment: constants stay exact, operators are checked -------------

@pytest.mark.parametrize("text,expected", [
    ("x > 1/3", Fraction(1, 3)),
    ("x > 0.1", Fraction(1, 10)),
    ("x > 10000000000000000001", Fraction(10000000000000000001)),
])
def test_constants_are_kept_exact(text, expected):
    # Rounding to binary64 would make the region denote {x : x > float(c)} --
    # a DIFFERENT subset of the reals than the atom does (Lemma 4), and would
    # let two distinct endpoints collapse onto one breakpoint, which is what
    # Lemma 5's dichotomy forbids.
    formula = parse(text)
    assert evaluate(formula, 0)[0][(0, "x")].l == expected


def test_distinct_constants_stay_distinct():
    # Corollary 2's reverse direction needs this: two INEQUIVALENT formulas
    # must not be handed the same region. Under binary64 these two collide.
    assert space(parse("x > 1/3")) != space(parse("x > 0.3333333333333333"))


@pytest.mark.parametrize("constant,expected", [
    ("5", 5.0), ("-2", -2.0), ("1.5", 1.5), ("3/2", 1.5), ("1/2", 0.5), ("-0.25", -0.25),
])
def test_exactly_representable_constants_still_work(constant, expected):
    assert atom_intervals(">", constant)[0].l == expected


def test_unknown_operator_raises():
    # '=' is the symbol the paper writes; the code's key is '=='. It used to
    # fall through to "the whole real line", i.e. `true` -- the widest
    # possible claim, from a typo.
    with pytest.raises(UnsupportedFormula):
        Atom("x", "=", 5)
    with pytest.raises(UnsupportedFormula):
        atom_intervals("=", 5)


def test_parse_round_trips_through_str():
    # `__str__` and `parse` are inverse, so a formula survives a print/read cycle.
    for text in ["x>0", "x!=5", "((x>0) && (y>0))", "((x>0) || (y>0))",
                 "F[0,2](x>0)", "G[1,3](x>0)", "((x>0) U[0,2] (y>3))",
                 "F[0,1](G[0,1](x>0))", "true", "((true) && (x>0))"]:
        assert str(parse(str(parse(text)))) == str(parse(text))


def test_parse_puts_negation_in_normal_form():
    assert str(parse("!(F[0,2](x>0))")) == "G[0,2](x<=0)"
    assert str(parse("(x>0) -> (y>0)")) == "((x<=0) || (y>0))"


def test_ambient_variables_must_cover_the_formula():
    # Precondition (P1). Silently dropping y would make S(phi) the region of a
    # DIFFERENT formula.
    with pytest.raises(UnsupportedFormula):
        signal_space(parse("(x>0) && (y>0)"), ["x"])


# --- Theorem 1, by sampling ----------------------------------------------

_CMP = {">": lambda v, c: v > c, ">=": lambda v, c: v >= c, "<": lambda v, c: v < c,
        "<=": lambda v, c: v <= c, "==": lambda v, c: v == c, "!=": lambda v, c: v != c}


def _sat(node, w, t):
    """(w, t) |= node, clause by clause as in Appendix A.2 -- not via evaluate()."""
    if isinstance(node, Constant):
        return node.value
    if isinstance(node, Atom):
        return _CMP[node.op](w[t][node.variable], Fraction(str(node.constant)))
    if isinstance(node, And):
        return _sat(node.left, w, t) and _sat(node.right, w, t)
    if isinstance(node, Or):
        return _sat(node.left, w, t) or _sat(node.right, w, t)
    window = range(node.lower, node.upper + 1)
    if isinstance(node, Eventually):
        return any(_sat(node.body, w, t + u) for u in window)
    if isinstance(node, Always):
        return all(_sat(node.body, w, t + u) for u in window)
    return any(_sat(node.witness, w, t + u) and
               all(_sat(node.invariant, w, s) for s in range(t, t + u + 1))
               for u in window)


def _random_formula(rng, depth=0):
    if depth >= 3 or rng.random() < 0.3:
        op = rng.choice(["<", "<=", ">", ">=", "==", "!="])
        return f"{rng.choice('xy')}{op}{rng.choice(['-2', '0', '1', '3', '1/2'])}"
    a = rng.randint(0, 2)
    b = a + rng.randint(0, 1)
    kind = rng.choice(["&&", "||", "F", "G", "U", "!", "const"])
    if kind == "const":
        return rng.choice(["true", "false"])
    if kind in ("&&", "||"):
        return f"({_random_formula(rng, depth + 1)}) {kind} ({_random_formula(rng, depth + 1)})"
    if kind == "U":
        return f"({_random_formula(rng, depth + 1)}) U[{a},{b}] ({_random_formula(rng, depth + 1)})"
    if kind == "!":
        return f"!({_random_formula(rng, depth + 1)})"
    return f"{kind}[{a},{b}]({_random_formula(rng, depth + 1)})"


def test_evaluate_matches_pointwise_semantics():
    # Theorem 1: w lies in a box of E(phi, 0) iff (w, 0) |= phi. Signal values
    # land exactly on every constant and in every gap between them, so each
    # endpoint's openness is exercised.
    rng = random.Random(5)
    values = [Fraction(v) for v in (-3, -2, 0, "1/4", "1/2", 1, 2, 3, 4)]
    for _ in range(80):
        text = _random_formula(rng)
        formula = parse(text)
        boxes = evaluate(formula, 0)
        for _ in range(60):
            w = {t: {v: rng.choice(values) for v in VARS} for t in range(formula.horizon() + 1)}
            member = any(all(contains(iv, w[t][v]) for (t, v), iv in box.items()) for box in boxes)
            assert member == _sat(formula, w, 0), (text, w)
