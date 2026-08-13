import subprocess
import sys

import pytest

from conftest import REPO_ROOT, stlsat_available


@pytest.mark.integration
@pytest.mark.skipif(not stlsat_available(), reason="cargo/z3 not available")
def test_interactive_loop_reports_score_and_exits_on_quit():
    result = subprocess.run(
        [sys.executable, str(REPO_ROOT / "similarity_check.py")],
        input="G[0,2] x>0\nG[0,2] x>0\nquit\n",
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
        timeout=60,
    )
    assert result.returncode == 0
    assert "Similarity score: 1.0000" in result.stdout
