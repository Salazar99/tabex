"""The interval and box algebra every stage of the pipeline shares.

`Interval` is one constraint on one axis; `Path` is a box over the grid,
`timeline = {t: {var: [Interval, ...]}}`; `merge_pieces` normalises a union of
intervals; `UnsupportedFormula` marks input outside the fragment.
"""
from fractions import Fraction


def _endpoint(value):
    """An interval endpoint: an exact Fraction, or a float infinity.

    Fraction and float compare exactly against each other in Python, so the
    rest of the pipeline needs no special handling -- only construction does.
    """
    if isinstance(value, Fraction):
        return value
    if value in (float('inf'), float('-inf')):
        return value
    return Fraction(str(value)) if isinstance(value, (str, float)) else Fraction(value)


class Interval:
    # Endpoints carry their own openness (`lo`/`ro`: True = OPEN at that end).
    # Without it "y < 0" and "y > 0" both become bounds touching at 0 and their
    # intersection is the non-empty point [0,0], so a contradictory conjunction
    # survives as a spurious degenerate box.
    #
    # A finite endpoint is an EXACT rational, not a float. Rounding "1/3" to
    # binary64 would make the interval denote {x : x > float(1/3)} -- a
    # different subset of R, since float(1/3) < 1/3 -- and, worse, would let two
    # distinct endpoints collapse onto one breakpoint. A box endpoint that is
    # not a breakpoint is exactly what the dichotomy lemma (Lemma 5) forbids,
    # so the canonical form's proof depends on this being exact.
    #
    # Nothing downstream can reintroduce rounding: every use of `l`/`r` in the
    # region pipeline compares or copies them, never combines them
    # arithmetically, so the endpoints appearing anywhere are always a subset of
    # those the atoms introduced (Lemma 8).
    __slots__ = ("l", "r", "lo", "ro")

    def __init__(self, l, r, lo=False, ro=False):
        self.l = _endpoint(l)
        self.r = _endpoint(r)
        # An infinite end is unreachable, so it is always open.
        self.lo = bool(lo) or self.l == float('-inf')
        self.ro = bool(ro) or self.r == float('inf')

    def is_empty(self):
        # A single point survives only when closed on both sides: (0,0], [0,0)
        # and (0,0) all admit no value.
        return self.l > self.r or (self.l == self.r and (self.lo or self.ro))

    def intersect(self, other):
        if self.l > other.l:
            nl, nlo = self.l, self.lo
        elif self.l < other.l:
            nl, nlo = other.l, other.lo
        else:
            nl, nlo = self.l, self.lo or other.lo
        if self.r < other.r:
            nr, nro = self.r, self.ro
        elif self.r > other.r:
            nr, nro = other.r, other.ro
        else:
            nr, nro = self.r, self.ro or other.ro
        result = Interval(nl, nr, nlo, nro)
        return None if result.is_empty() else result

    def __repr__(self):
        l_str = "-inf" if self.l == float('-inf') else str(self.l)
        r_str = "inf" if self.r == float('inf') else str(self.r)
        return f"{'(' if self.lo else '['}{l_str}, {r_str}{')' if self.ro else ']'}"

    def to_tuple(self):
        return (self.l, self.r, self.lo, self.ro)

    def __eq__(self, other):
        return isinstance(other, Interval) and self.to_tuple() == other.to_tuple()

    def __hash__(self):
        return hash(self.to_tuple())


def contains(interval, value):
    """Is `value` in `interval`, honouring each end's openness?"""
    return ((value > interval.l if interval.lo else value >= interval.l) and
            (value < interval.r if interval.ro else value <= interval.r))


def merge_pieces(pieces):
    # Collapse overlapping/touching Interval pieces into a minimal disjoint
    # set, so duplicate/overlapping pieces (e.g. [[0,inf],[0,inf]]) don't
    # double-count length or get treated as distinct alternatives.
    # Empty pieces are dropped: they admit no value, so they must not survive
    # as an alternative.
    #
    # Two pieces meeting at b only touch when at least one of them is CLOSED
    # there -- "(-inf,1)" and "(1,inf)" leave a hole at 1 and stay separate,
    # which is what makes "(x<1) || (x>1)" different from "true".
    merged = []
    for iv in sorted((p for p in pieces if not p.is_empty()), key=lambda p: (p.l, p.lo)):
        if merged and (iv.l < merged[-1].r or
                       (iv.l == merged[-1].r and not (iv.lo and merged[-1].ro))):
            last = merged[-1]
            if iv.r > last.r or (iv.r == last.r and last.ro and not iv.ro):
                merged[-1] = Interval(last.l, iv.r, last.lo, iv.ro)
        else:
            merged.append(Interval(iv.l, iv.r, iv.lo, iv.ro))
    return merged


class Path:
    """A box over the grid: `timeline = {t: {var: [Interval, ...]}}`."""

    def __init__(self, timeline):
        self.timeline = timeline

    def copy(self):
        new_tl = {t: {v: list(pieces) for v, pieces in slot.items()}
                  for t, slot in self.timeline.items()}
        return Path(new_tl)


class UnsupportedFormula(ValueError):
    """A formula outside the fragment the signal space can represent.

    Raised rather than silently dropping the offending part: a dropped
    constraint is indistinguishable from a genuinely free axis, so it would
    widen the signal space and the pipeline would report a confident, wrong
    answer. See README's "Supported fragment".
    """
