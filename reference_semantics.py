"""The signal space, defined denotationally.

This module IS the definition of `S(φ)`. It computes a formula's signal space by
structural recursion on the formula itself -- no tableau, no solver -- so that
`S(φ) = ⟦φ⟧` is provable by an elementary induction with one case per
connective. See FORMAL_PROOFS.md §1.

`similarity.stl_similarity.calc_similarity_from_formulas()` computes its regions
from here, so the theorem is about the code that actually runs.
`parse_graph.standardize()` derives the same region from stlsat's tableau and is
kept as a faster alternative, cross-checked against this module by
`tests/test_reference_semantics.py`.

**The atom layer below is deliberately duplicated, not imported from
`parse_graph`.** Two implementations that share a component are not independent,
and agreement between them is not evidence about that component: a rational
constant was silently collapsed to binary64 in the shared `atom_to_pieces` for
this entire codebase's history, and no differential test could see it, because
both sides made the same mistake. The duplication is ~20 lines and it is the
point.

Two conventions, both choices rather than laws:

* **Time is discrete and bounded**, so a formula constrains the finite grid
  `{0..horizon(φ)} × variables`.
* **`until` includes its witness** -- see `Until`.

Everything is evaluated in negation normal form: `negate()` pushes `¬` down to
the atoms, where it is one flip of a comparison operator. That keeps the
evaluator cheap, since complementing a compound region of `k` boxes over `d`
axes costs `d**k` while complementing an atom costs nothing.
"""
import re
from fractions import Fraction

from parse_graph import Interval, Path, UnsupportedFormula

INF = float("inf")

# --------------------------------------------------------------------------
# The atom layer. Independent of parse_graph on purpose (see the module
# docstring): this is where the fragment's assumptions are enforced.
# --------------------------------------------------------------------------

#: Complementation on comparison operators. An involution: each pair partitions
#: the reals, so `x op c` and `x NEGATE[op] c` are exact complements.
NEGATE = {">": "<=", "<=": ">", ">=": "<", "<": ">=", "==": "!=", "!=": "=="}

OPERATORS = frozenset(NEGATE)


def exact(constant):
    """The constant as a float, or raise if that is lossy.

    The signal space compares against binary64 endpoints, so a constant that is
    not exactly representable would denote a *different* set of reals than the
    formula says. Two distinct rationals could then produce the same region,
    which breaks `S(φ) = S(θ) ⟹ φ ≡ θ` (FORMAL_PROOFS Corollary A1). Rather
    than silently answer a question nobody asked, refuse it.

    `1/2`, `1.5`, `-3` and anything else with a finite binary expansion pass;
    `1/3` and integers beyond 2**53 do not.
    """
    try:
        rational = Fraction(str(constant))
    except (ValueError, ZeroDivisionError) as exc:
        raise UnsupportedFormula(f"not a constant: {constant!r}") from exc
    approximation = float(rational)
    if Fraction(approximation) != rational:
        raise UnsupportedFormula(
            f"constant {constant!r} is not exactly representable in binary64, so the "
            f"region would denote a different set of reals than the formula does. "
            f"See FORMAL_PROOFS.md §0.1.")
    return approximation


def atom_intervals(op, constant):
    """`{ x : x op constant }`, as a union of intervals.

    Strict operators give OPEN endpoints, which is what makes the complement of
    an atom exact -- `¬(x > c)` is `x ≤ c` and the two share no point.
    """
    if op not in OPERATORS:
        raise UnsupportedFormula(
            f"unsupported comparison operator {op!r}; the fragment allows "
            f"{sorted(OPERATORS)}. See README's 'Supported fragment'.")
    value = exact(constant)
    if op == ">":
        return [Interval(value, INF, lo=True)]
    if op == ">=":
        return [Interval(value, INF)]
    if op == "<":
        return [Interval(-INF, value, ro=True)]
    if op == "<=":
        return [Interval(-INF, value)]
    if op == "==":
        return [Interval(value, value)]
    # "!=" is two disjoint open half-lines -- one atom, two boxes.
    return [Interval(-INF, value, ro=True), Interval(value, INF, lo=True)]


# --------------------------------------------------------------------------
# Formulas. Each node knows its NNF negation and how to print itself in
# stlsat's syntax, so the same object can be evaluated here *and* handed to the
# solver for a differential comparison.
# --------------------------------------------------------------------------

class Atom:
    """`variable op constant` -- the whole atomic fragment (see README)."""

    def __init__(self, variable, op, constant):
        if op not in OPERATORS:
            raise UnsupportedFormula(
                f"unsupported comparison operator {op!r}; the fragment allows "
                f"{sorted(OPERATORS)}")
        exact(constant)          # reject a non-representable constant at construction
        self.variable, self.op, self.constant = variable, op, constant

    def negate(self):
        return Atom(self.variable, NEGATE[self.op], self.constant)

    def horizon(self):
        return 0

    def __str__(self):
        return f"{self.variable}{self.op}{self.constant}"


class Constant:
    """`true` / `false`.

    Denotable exactly -- `true` is the unconstrained region and `false` the
    empty one -- so the fragment may as well contain them. (A `false` appearing
    as a *tableau label* is a different matter, and `canonical_atoms` still
    refuses it: there the empty region cannot be expressed as an interval union
    over an unnamed variable.)
    """

    def __init__(self, value):
        self.value = bool(value)

    def negate(self):
        return Constant(not self.value)

    def horizon(self):
        return 0

    def __str__(self):
        return "true" if self.value else "false"


TRUE = Constant(True)
FALSE = Constant(False)


class And:
    def __init__(self, left, right):
        self.left, self.right = left, right

    def negate(self):
        return Or(self.left.negate(), self.right.negate())

    def horizon(self):
        return max(self.left.horizon(), self.right.horizon())

    def __str__(self):
        return f"(({self.left}) && ({self.right}))"


class Or:
    def __init__(self, left, right):
        self.left, self.right = left, right

    def negate(self):
        return And(self.left.negate(), self.right.negate())

    def horizon(self):
        return max(self.left.horizon(), self.right.horizon())

    def __str__(self):
        return f"(({self.left}) || ({self.right}))"


class Eventually:
    """`F[a,b] φ` -- φ holds at some instant of the window."""

    def __init__(self, lower, upper, body):
        self.lower, self.upper, self.body = lower, upper, body

    def negate(self):
        return Always(self.lower, self.upper, self.body.negate())

    def horizon(self):
        return self.upper + self.body.horizon()

    def __str__(self):
        return f"F[{self.lower},{self.upper}]({self.body})"


class Always:
    """`G[a,b] φ` -- φ holds at every instant of the window."""

    def __init__(self, lower, upper, body):
        self.lower, self.upper, self.body = lower, upper, body

    def negate(self):
        return Eventually(self.lower, self.upper, self.body.negate())

    def horizon(self):
        return self.upper + self.body.horizon()

    def __str__(self):
        return f"G[{self.lower},{self.upper}]({self.body})"


class Until:
    """`φ U[a,b] ψ` -- the invariant holds up to AND INCLUDING the witness:

        w, t ⊨ φ U[a,b] ψ   ⟺   ∃ u ∈ [a,b] :  w, t+u ⊨ ψ
                                        ∧  ∀ v ∈ [t, t+u] :  w, v ⊨ φ

    Note the closed `[t, t+u]`. Textbook STL uses the half-open `[t, t+u)`, so
    it does not require the invariant at the witness; `φ U_here ψ` is exactly
    `φ U_textbook (φ ∧ ψ)`.

    This variant is chosen deliberately. Both are *equally* easy to prove
    correct here -- the induction case has the same shape and only the range of
    the inner intersection changes -- so the tiebreaker is what it costs
    elsewhere, and this one is what stlsat's tableau already computes, keeping
    the cross-check in `tests/test_reference_semantics.py` translation-free.
    FORMAL_PROOFS.md §0.2 and §1.2.

    In a bounded, discrete setting `until` is sugar: expanding over the witness
    instant gives a finite disjunction of `F`/`G`, which is how `negate()` is
    obtained without needing a `release` operator.
    """

    def __init__(self, lower, upper, invariant, witness):
        self.lower, self.upper = lower, upper
        self.invariant, self.witness = invariant, witness

    def expand(self):
        # phi U[a,b] psi  ==  OR_{u=a..b} ( G[0,u] phi  &&  G[u,u] psi )
        # The invariant window is [0,u] -- closed, because the witness instant
        # is included.
        disjuncts = None
        for u in range(self.lower, self.upper + 1):
            term = And(Always(0, u, self.invariant), Always(u, u, self.witness))
            disjuncts = term if disjuncts is None else Or(disjuncts, term)
        return disjuncts

    def negate(self):
        return self.expand().negate()

    def horizon(self):
        return self.upper + max(self.invariant.horizon(), self.witness.horizon())

    def __str__(self):
        return f"(({self.invariant}) U[{self.lower},{self.upper}] ({self.witness}))"


# --------------------------------------------------------------------------
# Parsing. Needed because the pipeline is handed formula *strings*.
# --------------------------------------------------------------------------

_TOKEN = re.compile(r"""
      (?P<ws>\s+)
    | (?P<temporal>[FGU]\s*\[\s*\d+\s*,\s*\d+\s*\])
    | (?P<op>>=|<=|==|!=|->|&&|\|\||[<>!()])
    | (?P<number>[+-]?\d+(?:\.\d+)?(?:/\d+)?)
    | (?P<name>[A-Za-z_][A-Za-z_0-9]*)
""", re.VERBOSE)

_WINDOW = re.compile(r"([FGU])\s*\[\s*(\d+)\s*,\s*(\d+)\s*\]")


def _tokenize(text):
    tokens, position = [], 0
    while position < len(text):
        match = _TOKEN.match(text, position)
        if match is None:
            raise UnsupportedFormula(f"cannot tokenise {text[position:position + 20]!r}")
        position = match.end()
        if match.lastgroup != "ws":
            tokens.append(match.group())
    return tokens


class _Parser:
    """Recursive descent over the README grammar.

    Precedence, loosest first: `->`, `||`, `&&`, `U[a,b]`, then unary `!`,
    `F[a,b]`, `G[a,b]`, then atoms and parentheses. `!` is applied via
    `negate()` at parse time, so the AST is in negation normal form by
    construction and `evaluate` never needs a negation case.
    """

    def __init__(self, tokens):
        self.tokens, self.i = tokens, 0

    def peek(self):
        return self.tokens[self.i] if self.i < len(self.tokens) else None

    def take(self, expected=None):
        token = self.peek()
        if token is None:
            raise UnsupportedFormula("unexpected end of formula")
        if expected is not None and token != expected:
            raise UnsupportedFormula(f"expected {expected!r}, found {token!r}")
        self.i += 1
        return token

    def parse(self):
        formula = self.implication()
        if self.peek() is not None:
            raise UnsupportedFormula(f"trailing input at {self.peek()!r}")
        return formula

    def implication(self):
        left = self.disjunction()
        if self.peek() == "->":
            self.take()
            return Or(left.negate(), self.implication())   # A -> B  ==  !A || B
        return left

    def disjunction(self):
        node = self.conjunction()
        while self.peek() == "||":
            self.take()
            node = Or(node, self.conjunction())
        return node

    def conjunction(self):
        node = self.until()
        while self.peek() == "&&":
            self.take()
            node = And(node, self.until())
        return node

    def until(self):
        node = self.unary()
        while self.peek() is not None and self.peek().startswith("U"):
            _, lower, upper = _WINDOW.match(self.take()).groups()
            node = Until(int(lower), int(upper), node, self.unary())
        return node

    def unary(self):
        token = self.peek()
        if token == "!":
            self.take()
            return self.unary().negate()
        if token is not None and (token.startswith("F") or token.startswith("G")) \
                and _WINDOW.match(token):
            kind, lower, upper = _WINDOW.match(self.take()).groups()
            body = self.unary()
            node = Eventually if kind == "F" else Always
            return node(int(lower), int(upper), body)
        return self.primary()

    def primary(self):
        if self.peek() == "(":
            self.take("(")
            inner = self.implication()
            self.take(")")
            return inner
        name = self.take()
        if name in ("true", "false"):
            return Constant(name == "true")
        if not re.fullmatch(r"[A-Za-z_][A-Za-z_0-9]*", name):
            raise UnsupportedFormula(f"expected a variable, found {name!r}")
        op = self.take()
        if op not in OPERATORS:
            raise UnsupportedFormula(
                f"{name!r} is not compared to a constant: the fragment requires "
                f"'variable op constant'. See README's 'Supported fragment'.")
        return Atom(name, op, self.take())


def parse(text):
    """Formula string -> AST in negation normal form.

    `parse(str(f))` reproduces `f`, which is what makes the round-trip a usable
    property test.
    """
    return _Parser(_tokenize(text)).parse()


# --------------------------------------------------------------------------
# The box algebra. A region is a list of boxes; a box maps an axis
# `(instant, variable)` to an Interval, and any axis it omits is unconstrained.
# --------------------------------------------------------------------------

def intersect(region_a, region_b):
    """Pairwise intersection. Boxes are products, so this is per-axis."""
    out = []
    for box_a in region_a:
        for box_b in region_b:
            merged, feasible = dict(box_a), True
            for axis, interval in box_b.items():
                if axis in merged:
                    narrowed = merged[axis].intersect(interval)
                    if narrowed is None:
                        feasible = False
                        break
                    merged[axis] = narrowed
                else:
                    merged[axis] = interval
            if feasible:
                out.append(merged)
    return out


EVERYTHING = [{}]   # the unconstrained region: one box constraining no axis
NOTHING = []        # the empty region


def evaluate(formula, instant=0):
    """The set of signals satisfying `formula` at `instant`, as a box list.

    One case per connective, each a one-line identity against the pointwise
    semantics -- which is why Theorem A is provable (FORMAL_PROOFS.md §1.2).
    """
    if isinstance(formula, Constant):
        return EVERYTHING if formula.value else NOTHING

    if isinstance(formula, Atom):
        # A union of intervals is a union of boxes: "x != 5" is two half-lines.
        return [{(instant, formula.variable): piece}
                for piece in atom_intervals(formula.op, formula.constant)]

    if isinstance(formula, And):
        return intersect(evaluate(formula.left, instant),
                         evaluate(formula.right, instant))

    if isinstance(formula, Or):
        return evaluate(formula.left, instant) + evaluate(formula.right, instant)

    if isinstance(formula, Eventually):
        region = NOTHING
        for offset in range(formula.lower, formula.upper + 1):
            region = region + evaluate(formula.body, instant + offset)
        return region

    if isinstance(formula, Always):
        region = EVERYTHING
        for offset in range(formula.lower, formula.upper + 1):
            region = intersect(region, evaluate(formula.body, instant + offset))
        return region

    if isinstance(formula, Until):
        region = NOTHING
        for offset in range(formula.lower, formula.upper + 1):
            witness_at = instant + offset
            term = evaluate(formula.witness, witness_at)
            # Closed range: the invariant is required AT the witness too.
            for moment in range(instant, witness_at + 1):
                term = intersect(term, evaluate(formula.invariant, moment))
            region = region + term
        return region

    raise TypeError(f"not a formula node: {formula!r}")


def variables(formula):
    """Every variable the formula mentions -- the minimum ambient axis set."""
    if isinstance(formula, Constant):
        return set()
    if isinstance(formula, Atom):
        return {formula.variable}
    if isinstance(formula, (And, Or)):
        return variables(formula.left) | variables(formula.right)
    if isinstance(formula, (Eventually, Always)):
        return variables(formula.body)
    if isinstance(formula, Until):
        return variables(formula.invariant) | variables(formula.witness)
    raise TypeError(f"not a formula node: {formula!r}")


def signal_space(formula, all_vars, horizon=None):
    """`evaluate()` lifted to the `list[Path]` the rest of the pipeline speaks.

    Every path is padded to the full `{0..horizon} × all_vars` grid, because
    canonicalize() requires all paths to share one ambient axis set
    (FORMAL_PROOFS hypothesis H1) and raises on ragged input.

    `all_vars` must cover `variables(formula)`; otherwise the omitted variable's
    constraints are silently dropped, which is precondition P1.
    """
    missing = variables(formula) - set(all_vars)
    if missing:
        raise UnsupportedFormula(
            f"ambient variables {sorted(all_vars)} do not cover {sorted(missing)}; "
            f"the region would silently drop those constraints (FORMAL_PROOFS P1)")
    if horizon is None:
        horizon = formula.horizon()
    if horizon < formula.horizon():
        raise UnsupportedFormula(
            f"horizon {horizon} is below the formula's own {formula.horizon()}; "
            f"the region would be truncated (FORMAL_PROOFS P1)")
    instants = range(horizon + 1)
    return [
        Path({t: {v: [box.get((t, v), Interval(-INF, INF))] for v in all_vars}
              for t in instants})
        for box in evaluate(formula, 0)
    ]
