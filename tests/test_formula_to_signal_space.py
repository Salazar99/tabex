import pytest

from conftest import EXAMPLES_DIR, REPO_ROOT, serialize_paths, stlsat_available
from parse_graph import (
    build_tree_from_dot,
    discover_all_variables,
    generate_signal_space_from_formula,
    run_stlsat,
    standardize,
)

pytestmark = pytest.mark.integration

if not stlsat_available():
    pytest.skip("cargo/z3 not available", allow_module_level=True)

# (formula string, matching checked-in tableau fixture)
FORMULA_EXAMPLES = [
    ("F[3,4] (x > 0 || y > 0)", "graph_F[3,4]x_or_y.dot"),
    ("F[0,2] (x > 0 || x == 0)", "graph_F_g_or_eqx.dot"),
    ("F[0,2] x >= 0", "graph_F_gex.dot"),
    ("G[0,2] x > 0", "graph_G.dot"),
    ("G[0,2] (x > 0 || y > 3)", "graph_G_or.dot"),
    ("(x>=0 && x<=5) || (x==5 || (x>=5 && x<=10))", "graph_or3.dot"),
]


def signal_space_from_dot_fixture(dot_name):
    content = (EXAMPLES_DIR / dot_name).read_text(encoding="utf-8")
    root = build_tree_from_dot(content)
    all_vars = discover_all_variables(content)
    return standardize(root, all_vars)


def test_run_stlsat_produces_a_dot_tableau():
    dot_content = run_stlsat("G[0,2] x > 0", tabex_root=REPO_ROOT)
    assert dot_content.startswith("graph Tableau {")


@pytest.mark.parametrize("formula,dot_name", FORMULA_EXAMPLES, ids=[e[1] for e in FORMULA_EXAMPLES])
def test_formula_matches_checked_in_tableau(formula, dot_name):
    live_paths = generate_signal_space_from_formula(formula, tabex_root=REPO_ROOT)
    fixture_paths = signal_space_from_dot_fixture(dot_name)
    assert serialize_paths(live_paths) == serialize_paths(fixture_paths)
