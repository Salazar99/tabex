"""The Madsen et al. (CDC 2018) baseline reproduces the paper's Table I."""
import pytest

from madsen.metrics import d_ph, d_sd, directed_ph
from similarity.intervals import UnsupportedFormula

THETA1 = "(x>=0.2 && x<=0.4)"
THETA2 = "(x>=0.2 && x<=0.44)"
PHI = {   # eq. (3); S = U = [0, 1]
    "T": "true",
    1: f"G[0,20]{THETA1}",
    2: f"G[0,20]{THETA2}",
    3: f"F[0,20]{THETA1}",
    4: f"G[0,20]{THETA1} && F[0,20]{THETA2}",
    5: f"G[0,10]{THETA1} && G[12,20]{THETA2}",
    6: f"G[0,16] F[0,4]{THETA1}",
}

# Table I, lower half: row i, column j reads d(phi_i -> phi_j) / d(phi_j -> phi_i).
PH_TABLE = {
    (1, "T"): (0, 0.6), (2, "T"): (0, 0.56), (3, "T"): (0, 0.6),
    (4, "T"): (0, 0.6), (5, "T"): (0, 0.6), (6, "T"): (0, 0.6),
    (2, 1): (0.04, 0), (3, 1): (0.6, 0), (4, 1): (0, 0), (5, 1): (0.6, 0), (6, 1): (0.6, 0),
    (3, 2): (0.56, 0.04), (4, 2): (0, 0.04), (5, 2): (0.56, 0.04), (6, 2): (0.56, 0.04),
    (4, 3): (0, 0.6), (5, 3): (0, 0.6), (6, 3): (0, 0.6),
    (5, 4): (0.6, 0), (6, 4): (0.6, 0),
    (6, 5): (0.6, 0.04),
}

# Table I, upper half.
SD_TABLE = {
    ("T", 1): 0.8, ("T", 2): 0.76, ("T", 3): 0.99, ("T", 4): 0.8, ("T", 5): 0.804,
    # The paper prints 0.84. Every other phi6 cell (0.03, 0.07, 0.16, 0.066)
    # implies phi6's box is 17 wide, which makes this one (20 - 3.4) / 20.
    ("T", 6): 0.83,
    (1, 2): 0.04, (1, 3): 0.19, (1, 4): 0, (1, 5): 0.036, (1, 6): 0.03,
    (2, 3): 0.23, (2, 4): 0.04, (2, 5): 0.044, (2, 6): 0.07,
    (3, 4): 0.19, (3, 5): 0.186, (3, 6): 0.16,
    (4, 5): 0.036, (4, 6): 0.03,
    (5, 6): 0.066,
}


@pytest.mark.parametrize("pair", PH_TABLE)
def test_table1_directed_ph(pair):
    i, j = pair
    _, forward, backward = d_ph(PHI[i], PHI[j])
    assert (forward, backward) == pytest.approx(PH_TABLE[pair], abs=1e-6)


@pytest.mark.parametrize("pair", SD_TABLE)
def test_table1_sd(pair):
    i, j = pair
    assert d_sd(PHI[i], PHI[j]) == pytest.approx(SD_TABLE[pair], abs=1e-9)
    assert d_sd(PHI[j], PHI[i]) == pytest.approx(SD_TABLE[pair], abs=1e-9)


@pytest.mark.parametrize("formula", ["x>0", "F[0,2](x>0 || y<1)", "(x>0) U[0,2] (y<3)"])
def test_identity(formula):
    assert d_ph(formula, formula, -5, 5)[0] == pytest.approx(0, abs=1e-9)
    assert d_sd(formula, formula, -5, 5) == 0


def test_ph_in_raw_units():
    # S = [-6, 6]: x in [5, 6] is at most 4 from x <= 2 (at x = 6);
    # x in [-6, 2] is at most 11 from x >= 5 (at x = -6).
    assert directed_ph("x>5", "x<=2", -6, 6) == pytest.approx(4)
    assert directed_ph("x<=2", "x>5", -6, 6) == pytest.approx(11)


def test_non_rectangular_rejected():
    with pytest.raises(UnsupportedFormula):
        d_ph("x==1", "x>0")
    with pytest.raises(UnsupportedFormula):
        d_sd("x!=1", "x>0")
