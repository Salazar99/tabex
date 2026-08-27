import math

from parse_graph import (
    Interval,
    atom_to_pieces,
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
    assert repr(Interval(0, float("inf"))) == "[0.0, inf)"
    assert repr(Interval(float("-inf"), 0)) == "(-inf, 0.0]"


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
