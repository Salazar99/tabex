"""The STL-kernel baseline: its robustness is sound, and it has the properties the paper states."""
import numpy as np
import pytest

from conftest import REPO_ROOT  # noqa: F401  (adds repo root to sys.path)
from similarity.intervals import contains
from similarity.reference_semantics import evaluate, parse
from stlkernel.metrics import kernel_distance, robustness, sample_mu0

FORMULAS = [
    "G[0,2](x>0.5 || y<-0.3)",
    "F[1,3](x>=0.2 && x<0.8)",
    "(x>0) U[0,3] (y>0.4)",
    "G[0,2] F[0,2](x<=-0.1) -> F[0,1](y>1)",
]


def holds(node, trace, names):
    return any(all(contains(iv, float(trace[names.index(v), t])) for (t, v), iv in box.items())
               for box in evaluate(node))


@pytest.mark.parametrize("formula", FORMULAS)
def test_robustness_sign_matches_satisfaction(formula):
    node, names = parse(formula), ["x", "y"]
    X = sample_mu0(300, 2, np.random.default_rng(1))
    rho = robustness(node, X, {"x": 0, "y": 1})[:, 0]
    for trace, r in zip(X, rho):
        if abs(r) > 1e-12:
            assert holds(node, trace, names) == (r > 0), (formula, r)


def test_equivalent_with_equal_robustness_scores_zero():
    assert kernel_distance("F[0,1] F[0,1](x>0)", "F[0,2](x>0)") == pytest.approx(0, abs=1e-12)
    assert kernel_distance("(x>0) U[0,2] (y>0)", "(x>0) U[0,2] (x>0 && y>0)") == pytest.approx(0, abs=1e-12)


def test_strictness_is_invisible():
    assert kernel_distance("G[0,2](x>0.3)", "G[0,2](x>=0.3)") == pytest.approx(0, abs=1e-12)


@pytest.mark.parametrize("f1, f2", [
    ("G[0,2]((x>0 && x<2) || (x>1 && x<3))", "G[0,2](x>0 && x<3)"),
    ("(x>=0 || x<0) U[0,2] (y>0)", "F[0,2](y>0)"),
])
def test_some_equivalent_pairs_are_missed(f1, f2):
    assert kernel_distance(f1, f2) > 1e-6
