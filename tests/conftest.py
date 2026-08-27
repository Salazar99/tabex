import shutil
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
EXAMPLES_DIR = REPO_ROOT / "graph_examples"
FIXTURES_DIR = Path(__file__).resolve().parent / "fixtures"

# parse_graph.py lives at the repo root, not on sys.path when pytest is run from tests/.
sys.path.insert(0, str(REPO_ROOT))


def stlsat_available():
    return shutil.which("cargo") is not None and shutil.which("z3") is not None


def serialize_paths(final_path_list):
    # Path.timeline[t][var] is a list of Interval pieces; turn it into plain,
    # JSON-comparable/sortable (t, var, [l, r]) data for golden-file comparison.
    serialized = []
    for path in final_path_list:
        timeline = {}
        for t in sorted(path.timeline.keys()):
            slot = path.timeline[t]
            timeline[str(t)] = {
                var: sorted(list(iv.to_tuple()) for iv in ivs)
                for var, ivs in sorted(slot.items())
            }
        serialized.append(timeline)
    return serialized


# --------------------------------------------------------------------------
# End-of-run similarity report
#
# pytest already reports pass/fail counts, so the thing it can't tell you is
# what the metric actually scored. Every score flows through
# compute_similarity(), and build_volume_from_paths() already stores each
# side's formula string (or .dot fixture name) as FormulaVolume.formula_name,
# so wrapping that one function catches every comparison the suite makes --
# including the ones reached via calc_similarity_from_formulas(), which calls
# it internally. Wrapped at conftest import time, which happens before test
# modules do their `from similarity.stl_similarity import ...`.
# --------------------------------------------------------------------------
import pytest  # noqa: E402

import similarity.stl_similarity as _stl_similarity  # noqa: E402  (needs sys.path above)

SIMILARITY_LOG = []
MAX_REPORTED_CELLS = 4
_unwrapped_compute_similarity = _stl_similarity.compute_similarity
_current_test = {"nodeid": None}


@pytest.fixture(autouse=True)
def _track_current_test(request):
    # So each logged comparison knows which test (and so which file) it came
    # from, to group the report by.
    _current_test["nodeid"] = request.node.nodeid
    yield
    _current_test["nodeid"] = None


def _format_bound(value):
    if value == float("inf"):
        return "inf"
    if value == float("-inf"):
        return "-inf"
    return f"{value:g}"


def _format_path(path):
    # One canonical cell -> "t0:x[0,2] y[0,1] t1:*", where "*" is an instant
    # the cell leaves entirely unconstrained.
    instants = []
    for t in sorted(path.timeline):
        constrained = {
            var: pieces
            for var, pieces in path.timeline[t].items()
            if not (len(pieces) == 1 and pieces[0].l == float("-inf") and pieces[0].r == float("inf"))
        }
        if constrained:
            body = " ".join(
                var + "u".join(
                    f"{'(' if iv.lo else '['}{_format_bound(iv.l)},"
                    f"{_format_bound(iv.r)}{')' if iv.ro else ']'}"
                    for iv in pieces
                )
                for var, pieces in sorted(constrained.items())
            )
        else:
            body = "*"
        instants.append(f"t{t}:{body}")
    return " ".join(instants) if instants else "(empty time domain)"


def _format_volume(volume):
    cells = [_format_path(path) for path in volume.volume]
    if not cells:
        return ["(no paths -- unsatisfiable)"]
    shown = cells[:MAX_REPORTED_CELLS]
    if len(cells) > MAX_REPORTED_CELLS:
        shown.append(f"... +{len(cells) - MAX_REPORTED_CELLS} more cell(s)")
    return shown


def _recording_compute_similarity(volume1, volume2, D=None):
    score = _unwrapped_compute_similarity(volume1, volume2, D=D)
    # Format eagerly: build_aligned_volumes() mutates volume.volume in place,
    # so the cells have to be rendered while they are the ones just scored.
    SIMILARITY_LOG.append((
        _current_test["nodeid"] or "(outside a test)",
        volume1.formula_name,
        volume2.formula_name,
        score,
        tuple(_format_volume(volume1)),
        tuple(_format_volume(volume2)),
    ))
    return score


_stl_similarity.compute_similarity = _recording_compute_similarity


def pytest_terminal_summary(terminalreporter):
    if not SIMILARITY_LOG:
        return
    # Deduplicate, keeping first-seen order: the suite compares some pairs
    # repeatedly (e.g. the self-similarity loop) and the repeats add nothing.
    seen, rows = set(), []
    for entry in SIMILARITY_LOG:
        if entry not in seen:
            seen.add(entry)
            rows.append(entry)

    terminalreporter.write_sep("=", "similarity scores")
    current_batch = None
    for nodeid, formula1, formula2, score, cells1, cells2 in rows:
        batch = nodeid.split("::")[0]
        if batch != current_batch:
            terminalreporter.write_sep("-", batch)
            current_batch = batch
        equivalent = "==" if score == 1.0 else "!=" if score == 0.0 else "~ "
        terminalreporter.write_line(f"  {score:>6.4f} {equivalent}")
        for formula, cells in ((formula1, cells1), (formula2, cells2)):
            terminalreporter.write_line(f"      {formula}")
            for cell in cells:
                terminalreporter.write_line(f"        - {cell}")
        terminalreporter.write_line("")
    ones = sum(1 for row in rows if row[3] == 1.0)
    terminalreporter.write_line(
        f"  {len(rows)} comparison(s), {ones} scored 1.0 (equivalent)"
    )
