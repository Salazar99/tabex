"""RQ1 probe: the STL kernel (Bortolussi et al. 2022, embedded by stl2vec) on RQ1's suites.

    python experiments/kernel_probe.py [--m 10000] [--seed 0] [--q 0.1] [--workers 24] [-o DIR]

Scores 1 - K (stlkernel/metrics.py) on exactly the pairs already scored by
random_suite.py -- experiments/results/random_equivalence.csv and
random_mutations.csv, so PH and SD are not rerun -- and on the 14 hand-picked
equivalent pairs of madsen.compare.EQUIVALENT. Same rules as random_suite.py:
a pair is scored identical iff 1 - K <= 1e-9, and mutants with 1 - G <= 1e-9
(equivalent to their base) are dropped.

Output: DIR/kernel_probe.csv, DIR/kernel_probe.md (DIR defaults to experiments/results).
"""
import argparse
import csv
import sys
from collections import defaultdict
from functools import partial
from multiprocessing import Pool
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from experiments.random_suite import kendall  # noqa: E402
from madsen.compare import EQUIVALENT  # noqa: E402
from stlkernel.metrics import kernel_distance  # noqa: E402

RESULTS = ROOT / "experiments" / "results"
TOL = 1e-9


def score(pair, m, seed, q):
    return kernel_distance(pair[0], pair[1], m=m, seed=seed, q=q)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--m", type=int, default=10_000)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--q", type=float, default=0.1)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("-o", "--out", type=FilePath, default=RESULTS)
    args = parser.parse_args()

    with open(RESULTS / "random_equivalence.csv") as fh:
        eq = list(csv.DictReader(fh))
    with open(RESULTS / "random_mutations.csv") as fh:
        mu = [r for r in csv.DictReader(fh) if float(r["1-G"]) > TOL]
    pairs = ([(f1, f2) for f1, f2 in EQUIVALENT] + [(r["original"], r["rewritten"]) for r in eq]
             + [(r["base"], r["mutant"]) for r in mu])
    with Pool(args.workers) as pool:
        k = pool.map(partial(score, m=args.m, seed=args.seed, q=args.q), pairs, chunksize=8)
    k_hand, k_eq, k_mu = k[:len(EQUIVALENT)], k[len(EQUIVALENT):len(EQUIVALENT) + len(eq)], \
        k[len(EQUIVALENT) + len(eq):]

    args.out.mkdir(parents=True, exist_ok=True)
    with open(args.out / "kernel_probe.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["suite", "label", "severity", "f1", "f2", "1-K"])
        for (f1, f2), v in zip(EQUIVALENT, k_hand):
            w.writerow(["hand", "", "", f1, f2, v])
        for r, v in zip(eq, k_eq):
            w.writerow(["generated", r["rewrite"], "", r["original"], r["rewritten"], v])
        for r, v in zip(mu, k_mu):
            w.writerow(["mutation", r["family"], r["severity"], r["base"], r["mutant"], v])

    missed = defaultdict(int)
    for r, v in zip(eq, k_eq):
        missed[r["rewrite"]] += v > TOL
    lines = [f"# STL kernel (1 - K) on RQ1's suites  (m = {args.m}, seed = {args.seed}, q = {args.q})", "",
             f"Equivalent pairs scored identical: hand {sum(v <= TOL for v in k_hand)}/{len(k_hand)}, "
             f"generated {sum(v <= TOL for v in k_eq)}/{len(k_eq)}.", "",
             "Missed hand-picked pairs:", ""]
    lines += [f"- `{f1}` vs `{f2}`: {v:.3g}" for (f1, f2), v in zip(EQUIVALENT, k_hand) if v > TOL]
    lines += ["", "Missed generated pairs by rewrite: " + ", ".join(
        f"{n} ({c})" for n, c in sorted(missed.items(), key=lambda x: -x[1]) if c), "",
        f"Non-equivalent mutants ({len(mu)}):", "",
        "| family | blind (scored identical) | monotone sequences | mean Kendall τ |", "|---|---|---|---|"]
    seqs = defaultdict(list)
    for r, v in zip(mu, k_mu):
        seqs[(r["base_id"], r["family"])].append((int(r["severity"]), v))
    for fam in ("const", "shift", "widen", "strict"):
        rows = [v for r, v in zip(mu, k_mu) if r["family"] == fam]
        blind = f"{sum(v <= TOL for v in rows)}/{len(rows)}"
        if fam == "strict":
            lines.append(f"| {fam} | {blind} | — | — |")
            continue
        runs = [sorted(pts) for (_, f), pts in seqs.items() if f == fam and len(pts) >= 2]
        mono = sum(all(b[1] >= a[1] - 1e-12 for a, b in zip(p, p[1:])) for p in runs)
        taus = [kendall([s for s, _ in p], [v for _, v in p]) for p in runs]
        lines.append(f"| {fam} | {blind} | {mono}/{len(runs)} | {sum(taus) / len(taus):.3f} |")
    by_base = defaultdict(dict)
    for r, v in zip(mu, k_mu):
        if r["family"] == "strict" or (r["family"] == "const" and r["severity"] == "1"):
            by_base[r["base_id"]][r["family"]] = v
    both = [b for b in by_base.values() if len(b) == 2]
    lines += ["", f"Strictness flip scored as a smaller change than a constant shift by 1: "
                  f"{sum(b['strict'] < b['const'] for b in both)}/{len(both)}"]
    (args.out / "kernel_probe.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
