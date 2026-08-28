import math

import pytest

from parse_graph import (
    NEGATED_OP,
    Interval,
    UnsupportedFormula,
    atom_to_pieces,
    canonical_atoms,
    complement_of,
    discover_all_variables,
    merge_pieces,
)


def test_interval_intersect_overlap():
    a = Interval(0, 10)
    b = Interval(5, 15)
    assert a.intersect(b).to_tuple() == (5, 10, False, False)


def test_interval_intersect_disjoint_is_none():
    a = Interval(0, 1)
    b = Interval(2, 3)
    assert a.intersect(b) is None


def test_interval_is_empty():
    assert Interval(5, 1).is_empty()
    assert not Interval(1, 5).is_empty()


def test_interval_repr_infinities():
    assert repr(Interval(0, float("inf"))) == "[0, inf)"
    assert repr(Interval(float("-inf"), 0)) == "(-inf, 0]"


# --- endpoint openness ----------------------------------------------------
# The whole point of carrying open/closed: a contradictory pair of strict
# bounds has to come out EMPTY, or the dead tableau branch stlsat wrote before
# Z3 rejected it survives standardize()'s filter as a degenerate cell.


def test_strict_bounds_touching_at_a_point_are_empty():
    assert Interval(0, 0, lo=True).is_empty()
    assert Interval(0, 0, ro=True).is_empty()
    assert not Interval(0, 0).is_empty()


def test_contradictory_strict_atoms_intersect_to_nothing():
    below = atom_to_pieces("<", 0)[0]   # (-inf, 0)
    above = atom_to_pieces(">", 0)[0]   # (0, inf)
    assert below.intersect(above) is None
    # ... while the non-strict pair still meets at the single point 0
    assert atom_to_pieces("<=", 0)[0].intersect(atom_to_pieces(">=", 0)[0]).to_tuple() == (
        0, 0, False, False
    )


def test_atom_to_pieces_openness():
    assert atom_to_pieces(">", 0)[0].to_tuple() == (0, math.inf, True, True)
    assert atom_to_pieces(">=", 0)[0].to_tuple() == (0, math.inf, False, True)
    assert atom_to_pieces("<", 0)[0].to_tuple() == (-math.inf, 0, True, True)
    assert atom_to_pieces("<=", 0)[0].to_tuple() == (-math.inf, 0, True, False)
    assert atom_to_pieces("==", 3)[0].to_tuple() == (3, 3, False, False)


def test_not_equal_is_two_open_half_lines():
    pieces = atom_to_pieces("!=", 5)
    assert [iv.to_tuple() for iv in pieces] == [
        (-math.inf, 5, True, True),
        (5, math.inf, True, True),
    ]
    # and they must NOT merge back into the whole line -- the hole at 5 is real
    assert len(merge_pieces(pieces)) == 2


def test_merge_pieces_needs_one_closed_end_to_touch():
    # (-inf,1) and (1,inf) leave a hole at 1
    assert len(merge_pieces(atom_to_pieces("<", 1) + atom_to_pieces(">", 1))) == 2
    # (-inf,1] and (1,inf) cover everything
    assert len(merge_pieces(atom_to_pieces("<=", 1) + atom_to_pieces(">", 1))) == 1


def test_merge_pieces_drops_empty_and_coalesces_overlap():
    assert merge_pieces([Interval(5, 1)]) == []
    merged = merge_pieces([Interval(0, 5), Interval(3, 10)])
    assert [iv.to_tuple() for iv in merged] == [(0, 10, False, False)]


def test_complement_flips_openness():
    # not (0, inf) is (-inf, 0], so the two never overlap at 0
    assert [iv.to_tuple() for iv in complement_of(atom_to_pieces(">", 0))] == [
        (-math.inf, 0, True, False)
    ]
    assert [iv.to_tuple() for iv in complement_of(atom_to_pieces(">=", 0))] == [
        (-math.inf, 0, True, True)
    ]


def test_discover_all_variables_ignores_temporal_operators():
    dot_content = "F[0,2] x > 0\nOG[0,2] y >= 3\nG[0,1] x == 1\nU[0,4] y < 2"
    assert discover_all_variables(dot_content) == ["x", "y"]


# --- the supported fragment, enforced -------------------------------------
# canonical_atoms() returns {} for anything it cannot parse, and {} already
# means "constrains nothing at this instant" -- a real answer for F, U,
# O-marked obligations and branching connectives. So a dropped label is
# indistinguishable from a genuinely free one and widens the signal space to
# all of R. Everything below pins which side of that line each shape is on.


@pytest.mark.parametrize("label,expected", [
    ("x != 5", [(-math.inf, 5.0, True, True), (5.0, math.inf, True, True)]),
    ("(!x != 5)", [(5.0, 5.0, False, False)]),          # negated "!=" is "=="
    ("x == 5", [(5.0, 5.0, False, False)]),
    ("x > 3/2", [(1.5, math.inf, True, True)]),          # stlsat prints rationals
    ("x > 1.5", [(1.5, math.inf, True, True)]),
    ("x >= -2", [(-2.0, math.inf, False, True)]),
])
def test_supported_atoms(label, expected):
    # "!=" and rational constants ARE "variable op constant" -- they were
    # dropped only by a regex gap, which made "x != 5" silently unconstrained
    # while "!(x == 5)" worked.
    assert [iv.to_tuple() for iv in canonical_atoms(label, 0)["x"]] == expected


def test_negated_op_covers_every_supported_operator():
    # A missing key here is a KeyError at extraction time, not a clean failure.
    assert set(NEGATED_OP) == {">", ">=", "<", "<=", "==", "!="}
    assert NEGATED_OP["!="] == "=="


def test_discover_all_variables_sees_every_supported_operator():
    # It must accept exactly what _ATOM does: a variable constrained only by an
    # omitted form drops out of the ambient space altogether.
    assert discover_all_variables("x != 5") == ["x"]
    assert discover_all_variables("y == 3/2") == ["y"]


@pytest.mark.parametrize("label", [
    "UNDEF",                        # out of window, rewritten by parse_tableau
    "true",                         # asserts nothing
    "OG[0,2] x > 0",                # deferred obligation
    "O(x > 0 U[0,4] (y > 3))",      # deferred until
    "F[0,2] x > 0",                 # splits into witness / continuation
    "(x > 0 U[0,4] (y > 3))",       # splits; invariant arrives as a sibling G
    "(x > 0 || y > 0)",             # disjuncts are separate children
    "(x > 0 -> y > 0)",             # "A -> B" is "!A || B": same branching case
    "G[1,2] x > 0",                 # t=0 is outside the window
])
def test_shapes_that_legitimately_assert_nothing(label):
    # This list is what keeps the recognizer from firing on correct input, so
    # it is executable rather than a comment.
    assert canonical_atoms(label, 0) == {}


@pytest.mark.parametrize("label,because", [
    ("x > y", "a relation between variables is a half-plane, not a box"),
    ("(x + y) > 0", "an arithmetic term is not a box"),
    ("|x| > 1", "an absolute value is not a box"),
    ("p", "a bare boolean atom is not a real-valued signal"),
    ("false", "admits no signal, which {} cannot express"),
    ("(x > 0 R[0,2] y > 0)", "release should have been rewritten into F/U/G"),
])
def test_unsupported_shapes_raise_rather_than_widen_the_region(label, because):
    with pytest.raises(UnsupportedFormula) as raised:
        canonical_atoms(label, 0)
    # The message has to name the offending label, or a failure deep in a
    # tableau is untraceable.
    assert label.strip("()") in str(raised.value), because
