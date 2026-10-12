"""RQ4: does pruning with G keep what the mined set says about the trace?

    python experiments/rq4/quality.py

Reduction rate alone says nothing -- any threshold gives any reduction. Here
each candidate is also monitored on the trace it was mined from: its
*activation set* Act(a) is the set of instants at which its antecedent holds
(every Slam candidate holds on its trace, so the antecedent is where it says
something). For a pruned set K of a context with candidates C:

* coverage   = |U_{a in K} Act(a)| / |U_{a in C} Act(a)|  -- instants still explained;
* fidelity   = mean over pruned a of Jaccard(Act(a), Act(rep(a))), rep(a) the
               representative a was merged into (G-clustering only).

G-pruning (leader clustering, prune.py) at each tau is compared, at the SAME
number of kept candidates per context, with:

* top-k      -- Slam's own ranking: keep the k best-ranked candidates;
* random     -- k candidates drawn uniformly (mean of 50 draws, seed 0);
* SD         -- leader clustering on 1 - SD. SD is 0 on all 107 072 pairs
                (sd_matrix.py, results/sd_pairs.csv.gz), so it keeps one candidate per context whatever
                the threshold, and cannot be matched to k; reported as is.

The monitor evaluates antecedents in TABEX's translation on the CSV trace,
with Slam's derivative @(v,k)(t) = v(t+k) - v(t) (v(t) where t+k runs past the
end, as Slam's Derivative::evaluate), over the instants where the whole
assertion's window fits in the trace.

Output: results/quality.csv, results/quality.md.
"""
import csv
import random
import re
import sys
from collections import defaultdict
from pathlib import Path as FilePath

import numpy as np

ROOT = FilePath(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from experiments.rq4.mine import CASES, SLAM_TESTS  # noqa: E402
from experiments.rq4.prune import TAUS, leader, load  # noqa: E402
from similarity.reference_semantics import (  # noqa: E402
    Always, And, Atom, Constant, Eventually, Or, Until, atom_intervals, parse,
)

RESULTS = FilePath(__file__).resolve().parent / "results"


def read_trace(path):
    with open(path) as fh:
        header = fh.readline()
        names = [tok.split()[-1] for tok in header.strip().split(",")]
        data = np.array([[float(x) for x in line.split(",")] for line in fh if line.strip()])
    return {n: data[:, k] for k, n in enumerate(names)}


def column(trace, name):
    m = re.fullmatch(r"(\w+)_d(\d+)", name)
    if name in trace or not m:
        return trace[name]
    base, k = trace[m.group(1)], int(m.group(2))
    out = base.copy()
    out[:-k] = base[k:] - base[:-k]     # t + k < len: v(t+k) - v(t); else v(t)
    return out


def evaluate(node, trace, n):
    """Boolean array over t in [0, n): (trace, t) |= node, False where undefined."""
    if isinstance(node, Constant):
        return np.full(n, bool(node.value))
    if isinstance(node, Atom):
        x = column(trace, node.variable)
        ok = np.zeros(n, dtype=bool)
        for iv in atom_intervals(node.op, node.constant):
            lo = x > float(iv.l) if iv.lo else x >= float(iv.l)
            hi = x < float(iv.r) if iv.ro else x <= float(iv.r)
            ok |= lo & hi
        return ok
    if isinstance(node, (And, Or)):
        a, b = evaluate(node.left, trace, n), evaluate(node.right, trace, n)
        return a & b if isinstance(node, And) else a | b

    def shifted(arr, u):
        out = np.zeros(n, dtype=bool)
        if u < n:
            out[:n - u] = arr[u:]
        return out

    if isinstance(node, (Eventually, Always)):
        body = evaluate(node.body, trace, n)
        acc = np.full(n, isinstance(node, Always))
        for u in range(node.lower, node.upper + 1):
            acc = acc & shifted(body, u) if isinstance(node, Always) else acc | shifted(body, u)
        return acc
    if isinstance(node, Until):   # invariant on the closed [t, t+u] (Remark 4)
        inv, wit = evaluate(node.invariant, trace, n), evaluate(node.witness, trace, n)
        acc, hold = np.zeros(n, dtype=bool), np.ones(n, dtype=bool)
        for u in range(0, node.upper + 1):
            hold &= shifted(inv, u)
            if u >= node.lower:
                acc |= shifted(wit, u) & hold
        return acc
    raise TypeError(node)


def antecedent(slam_text):
    body = re.sub(r"@\(\s*(\w+)\s*,\s*(\d+)\s*\)", r"\1_d\2", slam_text.strip()[2:-1])
    depth = 0
    for k in range(len(body) - 1):
        depth += body[k] == "("
        depth -= body[k] == ")"
        if depth == 0 and body[k:k + 2] == "->":
            return body[:k], body
    raise ValueError(slam_text)


def activations(cands_rows):
    """(case, context) -> {rank: frozenset(instants)}."""
    traces = {case: read_trace(SLAM_TESTS / trace) for case, (_, trace) in CASES.items()}
    act = defaultdict(dict)
    for r in cands_rows:
        tr = traces[r["case"]]
        n = len(next(iter(tr.values())))
        ant, whole = antecedent(r["slam"])
        valid = n - parse(whole).horizon()
        holds = evaluate(parse(ant), tr, n)[:max(valid, 0)]
        act[(r["case"], r["context"])][int(r["rank"])] = frozenset(np.flatnonzero(holds).tolist())
    return act


def coverage(sets, kept, universe):
    if not universe:
        return 1.0
    return len(set().union(*(sets[a] for a in kept))) / len(universe)


def jaccard(a, b):
    return 1.0 if not a and not b else len(a & b) / len(a | b)


def main():
    cands, G, _, _ = load()
    rows = list(csv.DictReader(open(RESULTS / "candidates.csv")))
    act = activations(rows)
    rng = random.Random(0)
    out = []
    for key, ranks in cands.items():
        sets = act[key]
        universe = set().union(*sets.values())
        for tau in TAUS:
            reps = leader(ranks, key, G, tau)
            k = len(reps)
            # representative of each pruned candidate: the first kept one within tau
            fid = [jaccard(sets[a], sets[next(b for b in reps if G[key + (b, a)] >= tau - 1e-9)])
                   for a in ranks if a not in reps]
            topk = sorted(ranks)[:k]
            rand = [coverage(sets, rng.sample(ranks, k), universe) for _ in range(50)]
            out.append((key[0], key[1], len(ranks), tau, k, len(universe),
                        coverage(sets, reps, universe), coverage(sets, topk, universe),
                        sum(rand) / len(rand), sum(fid) / len(fid) if fid else 1.0,
                        coverage(sets, [min(ranks)], universe)))
    with open(RESULTS / "quality.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case", "context", "candidates", "tau", "kept", "active_instants",
                    "coverage_G", "coverage_topk", "coverage_random", "fidelity_G",
                    "coverage_SD_one_kept"])
        w.writerows(out)

    lines = ["# RQ4 — pruning quality on the traces", "",
             "Coverage = fraction of the trace instants activated by some candidate of the "
             "context that are still activated by a kept candidate; pooled over contexts, "
             "weighted by active instants. Same number of kept candidates for every method "
             "at a given τ.", "",
             "| τ | kept / candidates | coverage G | coverage top-k (Slam rank) | "
             "coverage random | fidelity G (Act Jaccard, pruned vs rep) |",
             "|---|---|---|---|---|---|"]
    for tau in TAUS:
        sel = [r for r in out if r[3] == tau]
        wsum = sum(r[5] for r in sel)
        wavg = lambda i: sum(r[i] * r[5] for r in sel) / wsum  # noqa: E731
        lines.append(f"| {tau:g} | {sum(r[4] for r in sel)}/{sum(r[2] for r in sel)} | "
                     f"{wavg(6):.3f} | {wavg(7):.3f} | {wavg(8):.3f} | {wavg(9):.3f} |")
    sel = [r for r in out if r[3] == TAUS[0]]
    wsum = sum(r[5] for r in sel)
    lines += ["", f"SD keeps 1 candidate per context at every threshold (SD = 0 on all pairs): "
              f"{len(sel)}/{sum(r[2] for r in sel)} kept, coverage "
              f"{sum(r[10] * r[5] for r in sel) / wsum:.3f}."]
    (RESULTS / "quality.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
