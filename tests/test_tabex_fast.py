"""tabex_fast computes the same score as the reference pipeline, without cells."""
import random
import time

import pytest

from conftest import REPO_ROOT  # noqa: F401  (adds repo root to sys.path)
from similarity.reference_semantics import parse, signal_space, variables
from similarity.canon import canonicalize
from similarity.stl_similarity import calc_similarity_from_formulas
from tabex_fast.engine import Region, similarity

THETA1 = "(x>=0.2 && x<=0.4)"
THETA2 = "(x>=0.2 && x<=0.44)"

CELL_FORMULAS = [
    "F[0,2](x>0)", "G[0,2](x>0 || y>0)", "F[0,2](x>0 && y>0)", "(x>0) U[0,2] (y<3)",
    "G[0,1](x>0) && F[0,1](y<3)", "F[0,1]((x>0 && x<2) || (x>4 && x<6))", "(x<=100)||(x>=100)",
    "(x>=1 && y>-1) || (x>1 && y>=-1)", "G[0,2](x!=3) || F[1,2](y==2)", "F[1,2](x>0)",
    f"F[0,4]{THETA1}", f"G[0,3] F[0,2]{THETA1}", "true", "false",
]

PAIRS = [
    # benchmarks/Manual
    ("F[0,2](x>0)", "G[0,2](x>0)"), ("F[0,2](x>0)", "F[3,4](x>0)"),
    ("F[0,2](z>0)", "F[0,2](x>0)"), ("G[0,2](x>0)", "G[0,2](x>0 || y>0)"),
    ("G[0,2](x>0)", "G[0,2](x>0 && y>0)"), ("F[0,2](x>0)", "F[0,2](x>0 || y>0 || z>0 || w>0)"),
    ("F[0,2](x>0)", "F[0,2](x>0 && y>0 && z>0 && w>0)"), ("F[0,2](x>0 && y>0)", "F[0,2](x>0 || y>0)"),
    ("F[0,2](x<5)", "F[0,2](x>0)"), ("F[0,4](x>0)", "F[0,2](x>0)"),
    # EXAMPLE.md
    ("G[0,1](x>0) && F[0,1](y<3)", "(x>0) U[0,1] (y<3)"),
    ("F[0,1]((x>0 && x<2) || (x>4 && x<6))", "F[0,1](x>1 && x<5)"),
    # Madsen et al.'s Example 1, shortened so the reference pipeline finishes
    (f"G[0,5]{THETA1}", f"F[0,5]{THETA1}"), (f"G[0,5]{THETA1}", f"G[0,3] F[0,2]{THETA1}"),
    (f"G[0,5]{THETA2}", f"F[0,5]{THETA1}"), (f"F[0,4]{THETA1}", f"G[0,2] F[0,2]{THETA1}"),
    # empty / whole regions, trimmed lengths that differ
    ("true", "F[0,2](x>0)"), ("false", "x>0"), ("false", "false"), ("F[1,2](x>0)", "G[0,1](y<1)"),
    # no variables at all: V = {}, the grid has no axes
    ("true", "true"), ("F[0,2](true)", "true"), ("G[0,3](true)", "F[0,1](false)"),
]


@pytest.mark.parametrize("formula", CELL_FORMULAS)
def test_cell_count_matches_canonicalize(formula):
    tree = parse(formula)
    all_vars = sorted(variables(tree))
    assert Region(tree, all_vars, tree.horizon()).cells() == \
        len(canonicalize(signal_space(tree, all_vars)))


@pytest.mark.parametrize("pair", PAIRS)
def test_score_matches_reference(pair):
    assert similarity(*pair) == pytest.approx(calc_similarity_from_formulas(*pair), abs=1e-9)


def test_random_pairs_match_reference():
    from verification.verify_equivalence import random_proposition, rewrites

    random.seed(3)
    for _ in range(40):
        first, second = random_proposition(), random_proposition()
        lower = random.randint(0, 2)
        _, rewrite = random.choice(rewrites(lower, lower + random.randint(0, 2),
                                            random.randint(0, 3)))
        original, rewritten = rewrite(first, second)
        assert similarity(original, rewritten) == pytest.approx(1.0, abs=1e-9)
        assert similarity(original, second) == \
            pytest.approx(calc_similarity_from_formulas(original, second), abs=1e-9)


def test_madsen_example_at_full_horizon():
    # phi3 has ~1.05e10 canonical cells and phi6 ~3.5e9; the reference
    # pipeline cannot enumerate either.
    phi3, phi6 = f"F[0,20]{THETA1}", f"G[0,16] F[0,4]{THETA1}"
    tree = parse(phi3)
    assert Region(tree, ["x"], 20).cells() == 3**21 - 2**21
    start = time.perf_counter()
    score = similarity(phi3, phi6)
    assert 0 <= score <= 1
    assert time.perf_counter() - start < 10
