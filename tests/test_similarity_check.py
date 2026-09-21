import subprocess
import sys

import pytest

from conftest import REPO_ROOT, stlsat_available


def _run_checker(stdin):
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "similarity_check.py")],
        input=stdin,
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=60,
    )


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_interactive_loop_reports_score_and_exits_on_quit():
    # Three prompts per comparison: two formulas, then D. Blank D = auto.
    result = _run_checker("G[0,2] x>0\nG[0,2] x>0\n\nquit\n")
    assert result.returncode == 0
    assert "Similarity score: 1.0000" in result.stdout


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_interactive_loop_accepts_an_explicit_D():
    # The paper's Section 5.2 worked example, driven from the prompt.
    result = _run_checker("x>2\nx>5\n100\nquit\n")
    assert result.returncode == 0
    assert "Similarity score: 0.9694" in result.stdout


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_interactive_loop_survives_an_ill_formed_D():
    # A refused D must report the required minimum and keep the loop alive,
    # not kill the session -- so the good comparison after it still scores.
    result = _run_checker("x>2\nx>5\n3\nx>2\nx>5\n100\nquit\n")
    assert result.returncode == 0
    assert "must exceed 5" in result.stdout
    assert "Similarity score: 0.9694" in result.stdout
