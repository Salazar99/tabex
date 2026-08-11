import math

from parse_graph import (
    Interval,
    Node,
    Path,
    advance_paths,
    discover_all_variables,
    get_immediate_constraints,
    invert_operator,
    merge_paths,
    parse_inequality_to_interval,
)


def test_interval_intersect_overlap():
    a = Interval(0, 10)
    b = Interval(5, 15)
    assert a.intersect(b).to_tuple() == (5, 10)


def test_interval_intersect_disjoint_is_none():
    a = Interval(0, 1)
    b = Interval(2, 3)
    assert a.intersect(b) is None


def test_interval_union_spans():
    a = Interval(0, 1)
    b = Interval(5, 6)
    assert a.union(b).to_tuple() == (0, 6)


def test_interval_is_empty():
    assert Interval(5, 1).is_empty()
    assert not Interval(1, 5).is_empty()


def test_interval_repr_infinities():
    assert repr(Interval(0, float("inf"))) == "[0.0, inf]"
    assert repr(Interval(float("-inf"), 0)) == "[-inf, 0.0]"


def test_invert_operator():
    assert invert_operator(">") == "<="
    assert invert_operator(">=") == "<"
    assert invert_operator("<") == ">="
    assert invert_operator("<=") == ">"
    assert invert_operator("==") == "!="
    assert invert_operator("!=") == "=="  # unknown op falls back to '=='


def test_parse_inequality_to_interval():
    assert parse_inequality_to_interval(">", "0").to_tuple() == (0, math.inf)
    assert parse_inequality_to_interval(">=", "0").to_tuple() == (0, math.inf)
    assert parse_inequality_to_interval("<", "0").to_tuple() == (-math.inf, 0)
    assert parse_inequality_to_interval("<=", "0").to_tuple() == (-math.inf, 0)
    assert parse_inequality_to_interval("==", "3").to_tuple() == (3, 3)


def test_discover_all_variables_ignores_temporal_operators():
    dot_content = "F[0,2] x > 0\nOG[0,2] y >= 3\nG[0,1] x == 1\nU[0,4] y < 2"
    assert discover_all_variables(dot_content) == ["x", "y"]


def test_get_immediate_constraints_from_atomic_formulas():
    node = Node("N0", 0, label="", properties={}, formulas=["x > 0", "y == 3"])
    constraints = get_immediate_constraints(node)
    assert constraints["x"].to_tuple() == (0, math.inf)
    assert constraints["y"].to_tuple() == (3, 3)


def test_advance_paths_adds_constraint_at_time():
    path = Path({})
    constraints = {"x": Interval(0, math.inf)}
    result = advance_paths([path], 1, constraints)
    assert result[0].timeline[1]["x"].to_tuple() == (0, math.inf)
    # Original path list object is copied, not mutated in place
    assert path.timeline == {}


def test_advance_paths_noop_without_constraints():
    path = Path({0: {"x": Interval(0, 1)}})
    paths = [path]
    result = advance_paths(paths, 0, {})
    assert result is paths
    assert result[0] is path


def test_merge_paths_unions_shared_variable_intervals():
    left = Path({0: {"x": Interval(0, 1)}})
    right = Path({0: {"x": Interval(5, 6)}})
    merged = merge_paths([left], [right])
    assert len(merged) == 1
    assert merged[0].timeline[0]["x"].to_tuple() == (0, 6)


def test_merge_paths_keeps_distinct_variables_separate():
    left = Path({0: {"x": Interval(0, 1)}})
    right = Path({0: {"y": Interval(5, 6)}})
    merged = merge_paths([left], [right])
    assert merged[0].timeline[0]["x"].to_tuple() == (0, 1)
    assert merged[0].timeline[0]["y"].to_tuple() == (5, 6)


def test_merge_paths_cartesian_product_size():
    left_paths = [Path({0: {"x": Interval(0, 1)}}), Path({0: {"x": Interval(2, 3)}})]
    right_paths = [Path({0: {"y": Interval(0, 1)}})]
    merged = merge_paths(left_paths, right_paths)
    assert len(merged) == 2
