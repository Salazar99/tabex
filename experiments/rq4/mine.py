"""RQ4, step 1: mine candidate assertions with Slam on its own case studies.

    python experiments/rq4/mine.py [--slam ~/Slam/build/slam] [--maxd 10]

Slam (https://github.com/Salazar99/Slam, branch `develop`) is run on the six
case studies shipped in its `tests/` directory, with the configurations shipped
there (the hints -- propositions, templates, metrics -- are the Slam authors'),
changed in two ways only:

* every template's `maxd` (maximum temporal distance of a decision-tree
  operand) is capped at `--maxd`, so mined windows stay within the horizons
  tabex_fast scores in about a second per pair (RQ2's timing study);
* Controlled_PU ships with its mining contexts commented out and only an
  assertion check active; the check is dropped and the two mining contexts are
  re-enabled.

Each candidate is recorded with its Slam rank (order in Slam's dump, which is
its ranking) and its translation into TABEX's fragment (see `to_tabex`), or
the reason it is outside the fragment.

Output: experiments/rq4/results/candidates.csv (+ configs/ with the XMLs used).
"""
import argparse
import csv
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from similarity.intervals import UnsupportedFormula  # noqa: E402
from similarity.reference_semantics import parse  # noqa: E402

HERE = FilePath(__file__).resolve().parent
SLAM_TESTS = FilePath.home() / "Slam" / "tests"
CASES = {   # name: (config, trace), as in each case's run.sh
    "WaterTanks": ("waterTanksCase/WT_config.xml", "waterTanksCase/WT_Trace_Date.csv"),
    "Heater": ("HeaterCase/HT_config.xml", "HeaterCase/HT_trace.csv"),
    "Gearbox": ("gearboxCase/Gearbox_config.xml", "gearboxCase/trace_gearbox_Date.csv"),
    "ControlledPU": ("Controlled_PU/CPU_config.xml", "Controlled_PU/CPU_new_2stage.csv"),
    "EngineTiming": ("Engine_timing/Engineconfig.xml", "Engine_timing/Engine_timing.csv"),
    "FuelControl": ("Fuel_control/Fuelconfig.xml", "Fuel_control/Fuel_Control.csv"),
}


def config_for(case, maxd):
    text = (SLAM_TESTS / CASES[case][0]).read_text()
    if case == "ControlledPU":
        text = re.sub(r'<context name="Check ass">.*?</context>', "", text, flags=re.S)
        text = text.replace("<!--", "").replace("-->", "")
    return re.sub(r"(\d+)maxd", lambda m: f"{min(int(m.group(1)), maxd)}maxd", text)


def to_tabex(assertion):
    """Slam's `G(ant -> cons)` -> TABEX formula, or raise UnsupportedFormula.

    * The outer unbounded G is common to every Slam assertion; what differs is
      the body, an implication checked at every instant. The body is what is
      compared (G[0,0] of it, i.e. the body itself, over its own horizon).
    * `@(v,k)` (Slam's k-step derivative of v) is not an atom over v, but it is
      an ordinary real-valued signal of the trace: it becomes the fresh
      variable `v_dk`. Two assertions over `@(z,1)` then constrain the same
      signal, which is all a comparison between them needs.
    """
    text = assertion.strip()
    if not (text.startswith("G(") and text.endswith(")")):
        raise UnsupportedFormula(f"not of the form G(...): {text}")
    body = re.sub(r"@\(\s*(\w+)\s*,\s*(\d+)\s*\)", r"\1_d\2", text[2:-1])
    parse(body)   # raises UnsupportedFormula outside the fragment
    return body


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--slam", default=str(FilePath.home() / "Slam" / "build" / "slam"))
    parser.add_argument("--maxd", type=int, default=10)
    args = parser.parse_args()

    (HERE / "configs").mkdir(exist_ok=True)
    (HERE / "results").mkdir(exist_ok=True)
    env = dict(os.environ)
    antlr = FilePath.home() / "harm" / "third_party" / "antlr4" / "lib"
    env["LD_LIBRARY_PATH"] = f"{antlr}:{env.get('LD_LIBRARY_PATH', '')}"

    rows = []
    for case, (_, trace) in CASES.items():
        conf = HERE / "configs" / f"{case}.xml"
        conf.write_text(config_for(case, args.maxd))
        with tempfile.TemporaryDirectory() as out:
            start = time.perf_counter()
            subprocess.run([args.slam, "--csv", str(SLAM_TESTS / trace), "--conf", str(conf),
                            "--silent", "--dump-to", out], check=True, env=env,
                           stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            elapsed = time.perf_counter() - start
            n_case = 0
            for dump in sorted(FilePath(out).glob("*_ass.txt")):
                context = dump.name[:-len("_ass.txt")]
                for rank, line in enumerate(dump.read_text().splitlines(), 1):
                    if not line.strip():
                        continue
                    try:
                        formula, reason = to_tabex(line), ""
                    except (UnsupportedFormula, ValueError) as exc:
                        formula, reason = "", str(exc).splitlines()[0][:120]
                    rows.append((case, context, rank, line.strip(), formula, reason))
                    n_case += 1
        print(f"{case:13} {n_case:5} candidates  (Slam {elapsed:.1f}s)", flush=True)

    with open(HERE / "results" / "candidates.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["case", "context", "rank", "slam", "tabex", "unsupported"])
        writer.writerows(rows)
    rejected = sum(1 for r in rows if r[5])
    print(f"total {len(rows)} candidates, {rejected} outside TABEX's fragment")


if __name__ == "__main__":
    main()
