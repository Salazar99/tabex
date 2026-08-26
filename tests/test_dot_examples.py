import json

import pytest

from conftest import EXAMPLES_DIR, FIXTURES_DIR, serialize_paths
from parse_graph import build_tree_from_dot, discover_all_variables, standardize

# (dot filename, golden fixture filename, expected node count)
EXAMPLES = [
    ("graph_F_g_or_eqx.dot", "graph_F_g_or_eqx.json", 14),
    ("graph_F_gex.dot", "graph_F_gex.json", 8),
    ("graph_G.dot", "graph_G.json", 6),
    ("graph_G_or.dot", "graph_G_or.json", 28),
    ("graph_U.dot", "graph_U.json", 20),
    ("graph_F[3,4]x_or_y.dot", "graph_F_3,4_x_or_y.json", 12),
    ("graph_or3.dot", "graph_or3.json", 6),
]


def count_nodes(node):
    return 1 + sum(count_nodes(c) for c in node.children)


@pytest.fixture(params=EXAMPLES, ids=[e[0] for e in EXAMPLES])
def example(request):
    dot_name, fixture_name, expected_node_count = request.param
    content = (EXAMPLES_DIR / dot_name).read_text(encoding="utf-8")
    golden = json.loads((FIXTURES_DIR / fixture_name).read_text(encoding="utf-8"))
    return content, golden, expected_node_count


def test_build_tree_from_dot_structure(example):
    content, _golden, expected_node_count = example
    root = build_tree_from_dot(content)
    assert root is not None
    assert count_nodes(root) == expected_node_count


def test_discover_all_variables_matches_golden(example):
    content, golden, _ = example
    assert discover_all_variables(content) == golden["vars"]


def test_standardize_matches_golden(example):
    content, golden, _ = example
    root = build_tree_from_dot(content)
    all_vars = discover_all_variables(content)
    paths = standardize(root, all_vars)
    assert serialize_paths(paths) == golden["paths"]


@pytest.mark.slow
def test_large_graph_g_u_builds_tree():
    # graph_G_U.dot is ~4.3MB / 17k+ nodes; standardize() on it is combinatorial
    # and not bounded here, so this only exercises the (already ~40s) tree build
    # and variable discovery, not a full standardize() golden comparison.
    content = (EXAMPLES_DIR / "graph_G_U.dot").read_text(encoding="utf-8")
    root = build_tree_from_dot(content)
    assert root is not None
    assert count_nodes(root) == 17329
    assert discover_all_variables(content) == ["x", "y"]
