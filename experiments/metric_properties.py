"""Is 1 - G a metric? Triangle inequality on every triple of the RQ4 matrices.

    python experiments/metric_properties.py

G is symmetric by construction, 1 - G >= 0, and 1 - G = 0 iff the formulas are
equivalent (Section 6), so 1 - G is a metric on equivalence classes iff the
triangle inequality d(a,c) <= d(a,b) + d(b,c) holds. It is checked on every
ordered triple of distinct candidates within each RQ4 context (all pairwise
G are in experiments/rq4/results/pairs.csv.gz), and the worst violation is
printed with its formulas -- a counterexample, if there is one.

Output: experiments/results/metric_properties.md.
"""
import csv
import gzip
import sys
from collections import defaultdict
from pathlib import Path as FilePath

import numpy as np

ROOT = FilePath(__file__).resolve().parent.parent
RQ4 = ROOT / "experiments" / "rq4" / "results"


def main():
    rows = defaultdict(list)
    for r in csv.DictReader(gzip.open(RQ4 / "pairs.csv.gz", "rt", newline="")):
        rows[(r["case"], r["context"])].append((int(r["i"]), int(r["j"]), float(r["G"])))
    total = violations = 0
    worst = (0.0, None)
    per_context = []
    for key, rs in rows.items():
        ids = sorted({i for i, _, _ in rs} | {j for _, j, _ in rs})
        pos = {v: n for n, v in enumerate(ids)}
        d = np.zeros((len(ids), len(ids)))
        for i, j, g in rs:
            d[pos[i], pos[j]] = d[pos[j], pos[i]] = 1 - g
        n_ctx = v_ctx = 0
        for b in range(len(ids)):
            excess = d - (d[:, b][:, None] + d[b, :][None, :])
            excess[b, :] = excess[:, b] = -1
            np.fill_diagonal(excess, -1)
            v_ctx += int((excess > 1e-9).sum())
            n_ctx += (len(ids) - 1) * (len(ids) - 2)
            if excess.max() > worst[0]:
                a, c = np.unravel_index(excess.argmax(), excess.shape)
                worst = (excess.max(), (key, ids[a], ids[b], ids[c], d[a, c], d[a, b], d[b, c]))
        per_context.append((key, n_ctx, v_ctx))
        total, violations = total + n_ctx, violations + v_ctx

    cands = {(r["case"], r["context"], int(r["rank"])): r["tabex"]
             for r in csv.DictReader(open(RQ4 / "candidates.csv"))}
    lines = ["# Is 1 − G a metric?", "",
             f"Triangle inequality d(a,c) ≤ d(a,b) + d(b,c), d = 1 − G, on every ordered triple "
             f"of distinct candidates within each RQ4 context: **{violations} violations out of "
             f"{total} triples ({violations / total:.4%})**.", "",
             "| case | context | triples | violations |", "|---|---|---|---|"]
    lines += [f"| {k[0]} | {k[1]} | {n} | {v} |" for k, n, v in per_context]
    if worst[1]:
        (case, ctx), a, b, c, dac, dab, dbc = worst[1]
        lines += ["", f"Worst violation: d(a,c) = {dac:.4f} > d(a,b) + d(b,c) = {dab:.4f} + {dbc:.4f} "
                  f"= {dab + dbc:.4f}", "",
                  f"- a = `{cands[(case, ctx, a)]}`",
                  f"- b = `{cands[(case, ctx, b)]}`",
                  f"- c = `{cands[(case, ctx, c)]}`", "",
                  "So G is a similarity measure whose complement is a semimetric (symmetric, zero "
                  "exactly on equivalent formulas) but not a metric."]
    (ROOT / "experiments" / "results" / "metric_properties.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
