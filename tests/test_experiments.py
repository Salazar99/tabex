"""The experiment scripts (experiments/, madsen/compare.py) rest on these facts."""
from fractions import Fraction

import pytest

from conftest import REPO_ROOT  # noqa: F401  (adds repo root to sys.path)
from similarity.stl_similarity import calc_similarity_from_formulas
from tabex_fast.engine import similarity


def test_compare_equivalent_block_scores_one():
    from madsen.compare import EQUIVALENT
    for f1, f2 in EQUIVALENT:
        assert similarity(f1, f2) == pytest.approx(1.0, abs=1e-9), (f1, f2)


@pytest.mark.parametrize("family", ["G", "F", "GF", "U"])
def test_timing_families_fast_matches_reference(family):
    from experiments.timing import pair
    f1, f2 = pair(family, 1, 3)
    assert similarity(f1, f2) == pytest.approx(calc_similarity_from_formulas(f1, f2), abs=1e-12)


def test_d_sensitivity_closed_form():
    from experiments.d_sensitivity import closed_form, pieces
    from similarity.stl_similarity import point_sim_d
    for D in (Fraction(51, 10), Fraction(100), Fraction(10**4)):
        assert point_sim_d(pieces("x>2"), pieces("x>5"), D) == \
            pytest.approx(closed_form("x>2", "x>5", D), abs=1e-15)
        assert point_sim_d(pieces("x<-2"), pieces("x<-5"), D) == \
            pytest.approx(closed_form("x<-2", "x<-5", D), abs=1e-15)


def test_slam_assertion_translation():
    from experiments.rq4.mine import to_tabex
    from similarity.intervals import UnsupportedFormula
    body = to_tabex("G(F[0,0]((a <= 0.000000)) -> F[0,18]((@(d,1) > 0.000000)))")
    assert body == "F[0,0]((a <= 0.000000)) -> F[0,18]((d_d1 > 0.000000))"
    with pytest.raises(UnsupportedFormula):
        to_tabex("F[0,2](x > 0)")


def test_slam_same_props():
    from experiments.rq4.stlsat_baseline import props
    a = "G(F[0,0]((x >= 1.0) && (x <= 2.0)) && F[0,3]((@(z,1) > 0.0)) -> F[0,4]((y == 1.0)))"
    b = "G(F[0,0]((x >= 1.0) && (x <= 2.0)) && F[2,5]((@(z,1) > 0.0)) -> F[1,9]((y == 1.0)))"
    c = "G(F[0,0]((x >= 1.0) && (x <= 2.5)) && F[2,5]((@(z,1) > 0.0)) -> F[1,9]((y == 1.0)))"
    assert props(a) == props(b) != props(c)
    assert len(props(a)) == 4


def test_leader_clustering_keeps_best_ranked():
    from experiments.rq4.prune import leader
    G = {}
    for (i, j), g in {(1, 2): 0.95, (1, 3): 0.5, (2, 3): 0.97}.items():
        G[("k", i, j)] = G[("k", j, i)] = g
    assert leader([1, 2, 3], ("k",), G, 0.9) == [1, 3]    # 3 is near 2, but 2 is not kept
    assert leader([1, 2, 3], ("k",), G, 0.99) == [1, 2, 3]
    assert leader([1, 2, 3], ("k",), G, 0.4) == [1]


def test_volume_jaccard_closed_forms_and_identity():
    from madsen.compare import EQUIVALENT
    from tabex_fast.volume import volume_jaccard
    theta1, theta2 = "(x>=0.2 && x<=0.4)", "(x>=0.2 && x<=0.44)"
    assert volume_jaccard(f"G[0,20]{theta1}", f"G[0,20]{theta2}") == \
        pytest.approx((0.2 / 0.24) ** 21, rel=1e-4)
    assert volume_jaccard("x>2", "x>5") == pytest.approx(1 / 4, rel=1e-5)
    assert volume_jaccard("F[0,2](x>0)", "G[0,2](x>0)") == pytest.approx(1 / 7, rel=1e-5)
    assert volume_jaccard("false", "x>0 && x<0") == 1.0
    assert volume_jaccard("x>0", "x>=0") < 1.0          # the eps term sees the endpoint
    for f1, f2 in EQUIVALENT:
        assert volume_jaccard(f1, f2) == pytest.approx(1.0, abs=1e-12), (f1, f2)


def test_trace_monitor_agrees_with_the_signal_space():
    import random as rnd

    import numpy as np
    from experiments.rq4.quality import evaluate
    from similarity.reference_semantics import parse, signal_space
    from verification.verify_equivalence import random_proposition
    rng = rnd.Random(5)

    def admits(tree, signal, horizon):
        def inside(iv, x):
            return ((x > iv.l if iv.lo else x >= iv.l) and (x < iv.r if iv.ro else x <= iv.r))
        return any(all(any(inside(iv, signal[v][t]) for iv in pieces)
                       for t, slot in p.timeline.items() for v, pieces in slot.items())
                   for p in signal_space(tree, ["x", "y"], horizon=horizon))

    for _ in range(60):
        a = rng.randint(0, 1)
        text = rng.choice([f"F[{a},{a + 1}]({random_proposition()})",
                           f"G[{a},{a + 1}]({random_proposition()})",
                           f"({random_proposition()}) U[{a},{a + 1}] ({random_proposition()})"])
        tree = parse(text)
        h = tree.horizon()
        for _ in range(10):
            sig = {v: [float(rng.choice([-4, -3, -2.5, -1, 0, 0.5, 1, 2, 3, 3.5, 4]))
                       for _ in range(h + 1)] for v in ("x", "y")}
            got = evaluate(tree, {v: np.array(s) for v, s in sig.items()}, h + 1)[0]
            assert bool(got) == admits(tree, sig, h), (text, sig)


def test_slam_derivative_matches_slam():
    import numpy as np
    from experiments.rq4.quality import column
    trace = {"z": np.array([1.0, 3.0, 2.0, 5.0])}
    # Slam's Derivative::evaluate: z(t+1) - z(t), and z(t) where t+1 runs off the end
    assert column(trace, "z_d1").tolist() == [2.0, -1.0, 3.0, 5.0]


def test_deepstl_conversion_and_filter():
    import sys
    sys.path.insert(0, str(REPO_ROOT / "experiments" / "rq5_deepstl"))
    from deepstl import classify, convert
    assert convert("always ( a > 1 -> eventually [0:3] (b == 2) )") == " a > 1 -> F[0,3] (b == 2) "
    assert classify("always [0:4] (H >= 24)")[0] == "G[0,4] (H >= 24)"
    assert classify("always ( rise (a > 1) -> b < 2 )") == (None, "rise/fall")
    assert classify("always ( a == RYoU_1 -> b < 2 )") == (None, "string constant")
    assert classify("always [0:11.91] (a > 1)") == (None, "fractional bound")
    assert classify("eventually (a > 1)") == (None, "unbounded inner")
    assert classify("always [0:452] (a > 1)")[1].startswith("horizon")
