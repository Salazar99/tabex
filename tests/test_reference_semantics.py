"""The denotational definition, and the tableau checked against it.

`reference_semantics.py` IS the definition of the signal space (PROOF.md §2).
`parse_graph.standardize()` computes the same region from stlsat's tableau, and
that path is an *optimisation* -- so it is validated here rather than trusted.
A bug in the tableau, or in the string-parsing that reads it, has to show up as
a failure in this file.

The unit tests need no cargo/z3: they exercise the definition on its own.
"""
import math
from fractions import Fraction

import pytest

from conftest import REPO_ROOT, stlsat_available  # noqa: F401  (REPO_ROOT puts the repo on sys.path)
from parse_graph import (
    build_tree_from_dot,
    collect_times,
    discover_all_variables,
    run_stlsat,
    standardize,
)
from parse_graph import UnsupportedFormula
from reference_semantics import (
    Always,
    And,
    Atom,
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
    # It is a definition, not an accident -- PROOF.md 2.4.
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


# --- the tableau, validated against the definition -------------------------

DIFFERENTIAL = [
    Atom("x", ">", 0),
    Atom("x", "!=", 5),
    And(Atom("x", ">", 0), Atom("y", ">", 0)),
    Or(Atom("x", ">", 0), Atom("y", ">", 0)),
    Always(0, 2, Atom("x", ">", 0)),
    Eventually(0, 2, Atom("x", ">", 0)),
    Eventually(0, 2, Or(Atom("x", ">", 0), Atom("y", ">", 0))),
    Always(0, 2, And(Atom("x", ">", 0), Atom("y", ">", 0))),
    Eventually(0, 1, Always(0, 1, Atom("x", ">", 0))),
    Always(0, 1, Eventually(0, 1, Atom("x", ">", 0))),
    Eventually(0, 1, Eventually(0, 1, Atom("x", ">", 0))),
    Eventually(0, 2, Atom("x", ">", 0)).negate(),
    Always(0, 2, Atom("x", ">", 0)).negate(),
    Until(0, 2, Atom("x", ">", 0), Atom("y", ">", 3)),
    Until(0, 0, Atom("x", ">", 0), Atom("y", ">", 3)),
    Until(1, 2, Atom("x", ">", 0), Atom("y", ">", 3)),
    Until(0, 1, Atom("x", ">", 0), Atom("y", ">", 3)).negate(),
]


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
@pytest.mark.parametrize("formula", DIFFERENTIAL, ids=lambda f: str(f)[:48])
def test_tableau_agrees_with_the_definition(formula):
    # Exact set equality of canonical cells -- not sampling. If these diverge,
    # the tableau path (or the parser reading it) is what is wrong, because the
    # definition is the side with a proof behind it.
    text = str(formula)
    dot = run_stlsat(text, tabex_root=REPO_ROOT)
    tree = build_tree_from_dot(dot)
    all_vars = sorted(set(discover_all_variables(dot)) | set(VARS))
    all_times = sorted(collect_times(tree) | set(range(formula.horizon() + 1)))

    from_definition = region(signal_space(formula, all_vars, horizon=max(all_times)))
    from_tableau = region(standardize(tree, all_vars, all_times))
    assert from_definition == from_tableau, text


# --- the fragment, enforced on BOTH paths ---------------------------------
# These exist because a shared component made a bug invisible: both the
# reference and the tableau called one `atom_to_pieces`, so a differential test
# could never see that it collapsed rationals to binary64. The reference now
# owns its atom layer, and each side is checked separately.

@pytest.mark.parametrize("text,expected", [
    ("x > 1/3", Fraction(1, 3)),
    ("x > 0.1", Fraction(1, 10)),
    ("x > 10000000000000000001", Fraction(10000000000000000001)),
])
def test_constants_are_kept_exact(text, expected):
    # Rounding to binary64 would make the region denote {x : x > float(c)} --
    # a DIFFERENT subset of the reals than the atom does (Lemma 3), and would
    # let two distinct endpoints collapse onto one breakpoint, which is what
    # Lemma 7's dichotomy forbids.
    formula = parse(text)
    assert evaluate(formula, 0)[0][(0, "x")].l == expected


def test_distinct_constants_stay_distinct():
    # Corollary A1's reverse direction needs this: two INEQUIVALENT formulas
    # must not be handed the same region. Under binary64 these two collide.
    assert space(parse("x > 1/3")) != space(parse("x > 0.3333333333333333"))


def test_the_tableau_path_keeps_them_exact_too():
    from parse_graph import atom_to_pieces
    assert atom_to_pieces(">", "1/3")[0].l == Fraction(1, 3)
    assert atom_to_pieces(">", "0.1")[0].l == Fraction(1, 10)


@pytest.mark.parametrize("constant,expected", [
    ("5", 5.0), ("-2", -2.0), ("1.5", 1.5), ("3/2", 1.5), ("1/2", 0.5), ("-0.25", -0.25),
])
def test_exactly_representable_constants_still_work(constant, expected):
    assert atom_intervals(">", constant)[0].l == expected


def test_unknown_operator_raises_on_both_paths():
    # '=' is the symbol FORMAL_PROOFS Lemma 3 writes; the code's key is '=='.
    # It used to fall through to "the whole real line", i.e. `true` -- the
    # widest possible claim, from a typo.
    from parse_graph import atom_to_pieces
    with pytest.raises(UnsupportedFormula):
        Atom("x", "=", 5)
    with pytest.raises(UnsupportedFormula):
        atom_intervals("=", 5)
    with pytest.raises(UnsupportedFormula):
        atom_to_pieces("=", 5)


def test_parse_round_trips_through_str():
    # `__str__` emits stlsat syntax and `parse` reads it, which is what lets one
    # AST be evaluated here AND handed to the solver for the differential test.
    for text in ["x>0", "x!=5", "((x>0) && (y>0))", "((x>0) || (y>0))",
                 "F[0,2](x>0)", "G[1,3](x>0)", "((x>0) U[0,2] (y>3))",
                 "F[0,1](G[0,1](x>0))", "true", "((true) && (x>0))"]:
        assert str(parse(str(parse(text)))) == str(parse(text))


def test_parse_puts_negation_in_normal_form():
    assert str(parse("!(F[0,2](x>0))")) == "G[0,2](x<=0)"
    assert str(parse("(x>0) -> (y>0)")) == "((x<=0) || (y>0))"


def test_ambient_variables_must_cover_the_formula():
    # Precondition P1. Silently dropping y would make S(phi) the region of a
    # DIFFERENT formula.
    with pytest.raises(UnsupportedFormula):
        signal_space(parse("(x>0) && (y>0)"), ["x"])


def test_tautological_witness_leaves_no_continuation():
    # complement_of used to answer "unconstrained" when the complement was
    # genuinely EMPTY, handing a witness that always holds a continuation
    # branch that constrains nothing.
    from parse_graph import atom_to_pieces, complement_of, merge_pieces, negate_witness_boxes

    covering = merge_pieces(atom_to_pieces(">", 0) + atom_to_pieces("<=", 0))
    assert complement_of(covering) == []
    assert negate_witness_boxes([{"x": covering}]) == []
    # ... while an empty input still means "nothing required", complement R.
    assert [iv.to_tuple() for iv in complement_of([])] == [(-INF, INF, True, True)]
