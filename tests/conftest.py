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
