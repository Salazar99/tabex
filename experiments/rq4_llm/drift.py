"""RQ4: reference-free drift among the samples of one model, against correctness.

    python experiments/rq4_llm/drift.py

Inputs: results/{requirements.csv,samples.jsonl,scores.csv} (generate.py, analyze.py).
For every requirement and model, pairwise G among the parsed samples (same
cleaning, conversion, D and 120 s budget as analyze.py). A group "drifts" if
some pair has G < 1. Groups whose samples were all scored against the
reference are cross-tabulated by correctness: all samples equivalent to the
reference, some, or none.

Since G = 1 iff equivalent, an all-correct group cannot drift and a mixed group
must; only the all-wrong groups carry information (one shared wrong reading, or
several).

Output: results/drift_pairs.csv, results/drift.md.
"""
import csv
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from statistics import median

import analyze as A
from deepstl import convert
from similarity.reference_semantics import constants, parse

R, TOL = A.RESULTS, A.TOL


def main():
    reqs = {r["id"]: r for r in csv.DictReader(open(R / "requirements.csv"))}
    by_req = defaultdict(list)
    for line in open(R / "samples.jsonl"):
        s = json.loads(line)
        f = convert(A.clean(s["answer"]))
        try:
            parse(f)
        except Exception:  # noqa: BLE001 -- parse failures are counted by analyze.py
            continue
        by_req[s["id"]].append((s, f))
    jobs = []
    for rid, lst in by_req.items():
        D = max((abs(c) for f in [reqs[rid]["reference"]] + [f for _, f in lst]
                 for c in constants(parse(f))), default=Fraction(0)) + 1
        per_model = defaultdict(list)
        for s, f in lst:
            per_model[s["model"]].append((s["sample"], f))
        for m, xs in per_model.items():
            jobs += [(rid, m, a, b, fa, fb, D) for i, (a, fa) in enumerate(xs) for b, fb in xs[i + 1:]]
    with ThreadPoolExecutor(24) as pool:     # each job forks its own killable child
        pairs = list(pool.map(A.pair_G, jobs))
    with open(R / "drift_pairs.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["id", "model", "a", "b", "G"])
        w.writerows(pairs)

    correct = {(r["id"], r["model"], int(r["sample"])): float(r["G"]) >= 1 - TOL
               for r in csv.DictReader(open(R / "scores.csv")) if r["G"]}
    groups = defaultdict(list)
    for p in pairs:
        groups[(p[0], p[1])].append(p)
    lines = ["# RQ4 — drift among the samples of one model", "",
             "Group = one requirement × one model, ≥ 2 parsed samples. Complete = every pair scored "
             f"within {A.BUDGET_S} s and every sample scored against the reference.", "",
             "| model | pairs scored | equivalent | mean pairwise G | complete groups | all correct: drift | "
             "mixed: drift | all wrong: drift | median min-pair G of drifting groups |",
             "|---|---|---|---|---|---|---|---|---|"]
    for m in sorted({k[1] for k in groups}):
        gs = [p[4] for k, v in groups.items() if k[1] == m for p in v if p[4] is not None]
        tab, mins = defaultdict(lambda: [0, 0]), []
        for (rid, mm), v in groups.items():
            samp = {p[2] for p in v} | {p[3] for p in v}
            if mm != m or any(p[4] is None for p in v) or any((rid, m, s) not in correct for s in samp):
                continue
            n_ok = sum(correct[(rid, m, s)] for s in samp)
            kind = "all correct" if n_ok == len(samp) else "all wrong" if n_ok == 0 else "mixed"
            drift = any(p[4] < 1 - TOL for p in v)
            tab[kind][0] += drift
            tab[kind][1] += 1
            if drift:
                mins.append(min(p[4] for p in v))
        cell = lambda k: f"{tab[k][0]}/{tab[k][1]}"  # noqa: E731
        lines.append(f"| {m} | {len(gs)} | {sum(g >= 1 - TOL for g in gs)} | {sum(gs) / len(gs):.4f} | "
                     f"{sum(t[1] for t in tab.values())} | {cell('all correct')} | {cell('mixed')} | "
                     f"{cell('all wrong')} | {median(mins) if mins else float('nan'):.3f} |")
    (R / "drift.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
