"""Monte-Carlo Jaccard (MCJ): the sampling estimate of the VolJ ablation.

    python experiments/mc_jaccard.py

MCJ(phi, theta) = |A ∩ B| / |A ∪ B| over N signals drawn uniformly on [-D, D]
per (variable, instant), A and B being the samples that satisfy each formula.
Given |A ∪ B| = m > 0, each of those m samples lies in A ∩ B independently with
probability VolJ (eps = 0), so MCJ is an unbiased estimate of VolJ. It is
undefined (None) when no sample satisfies either formula: on G[0,T] of a box,
whose probability decays as p^((T+1)|V|), that happens already at small T,
where G and VolJ remain exact. Both formulas are read on the SAME samples, so
an equivalent pair scores exactly 1 whenever MCJ is defined.

Reports (1) the hand-picked RQ1 pairs of madsen/compare.py: G, VolJ (eps = 0),
MCJ, equivalences missed, rank correlation with G, and agreement with VolJ
within 3 standard errors; (2) the timing families of experiments/timing.py:
time per call and where MCJ is undefined.

Output: experiments/results/mc_jaccard.md, mc_jaccard_timing.csv.
"""
import csv
import sys
import time
from pathlib import Path as FilePath

import numpy as np

ROOT = FilePath(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from experiments.rq4.quality import evaluate  # noqa: E402
from similarity.reference_semantics import parse, variables  # noqa: E402
from similarity.stl_similarity import resolve_D  # noqa: E402

OUT = ROOT / "experiments" / "results"
N_SIGNALS = 10_000


def mc_counts(f1, f2, D, n=N_SIGNALS, seed=0):
    """(|A ∩ B|, |A ∪ B|) over n signals uniform on [-D, D] per variable and instant."""
    t1, t2 = parse(f1), parse(f2)
    h = max(t1.horizon(), t2.horizon())
    rng = np.random.default_rng(seed)
    # Evaluated at t = 0 a formula reads only instants 0..h (locality, Lemma 7), so the
    # n signals are laid end to end as one trace and read back at every block start.
    trace = {v: rng.uniform(-D, D, n * (h + 1)) for v in sorted(variables(t1) | variables(t2))}
    starts = np.arange(n) * (h + 1)
    a = evaluate(t1, trace, n * (h + 1))[starts]
    b = evaluate(t2, trace, n * (h + 1))[starts]
    return int((a & b).sum()), int((a | b).sum())


def mc_jaccard(f1, f2, D, n=N_SIGNALS, seed=0):
    """MCJ in [0, 1], or None when no sampled signal satisfies either formula."""
    inter, union = mc_counts(f1, f2, float(D), n, seed)
    return inter / union if union else None


def pairs_report():
    from scipy.stats import spearmanr
    from madsen.compare import PAIRS
    from tabex_fast.engine import similarity
    from tabex_fast.volume import volume_jaccard

    lines = ["## RQ1 hand-picked pairs (madsen/compare.py)", "",
             "| # | block | phi | theta | D | G | VolJ (eps=0) | MCJ | \\|A∪B\\| | within 3 SE |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    rows = []
    for i, (block, (f1, f2)) in enumerate(PAIRS, 1):
        D = resolve_D(None, parse(f1), parse(f2))
        inter, union = mc_counts(f1, f2, float(D))
        j = inter / union if union else None
        g, v = similarity(f1, f2), volume_jaccard(f1, f2, eps=0)
        # SE under the null "MCJ estimates VolJ": binomial on the m samples in A ∪ B
        ok = None if j is None else abs(j - v) <= 3 * (v * (1 - v) / union) ** 0.5 + 1e-12
        rows.append((block, g, v, j, ok))
        lines.append(f"| {i} | {block} | `{f1}` | `{f2}` | {float(D):g} | {g:.4f} | {v:.4f} | "
                     f"{'undef' if j is None else f'{j:.4f}'} | {union} | {'—' if ok is None else ok} |")
        if block == "equivalent" and j is not None:
            assert j == 1.0, (f1, f2, j)   # same samples, same truth value on each

    eq = [r for r in rows if r[0] == "equivalent"]
    neq = [r for r in rows if r[0] != "equivalent" and r[3] is not None]
    checked = [r[4] for r in rows if r[4] is not None]
    rho = spearmanr([1 - r[1] for r in neq], [1 - r[3] for r in neq]).statistic
    lines += ["",
              f"- Equivalent block ({len(eq)} pairs): missed 0, "
              f"undefined {sum(r[3] is None for r in eq)}.",
              f"- Spearman of 1 - G vs 1 - MCJ over the {len(neq)} defined non-equivalent pairs: "
              f"{rho:.3f} (undefined: {sum(r[0] != 'equivalent' and r[3] is None for r in rows)}).",
              f"- MCJ within 3 SE of VolJ (eps = 0): {sum(checked)}/{len(checked)}."]
    return lines


def timing_report():
    from experiments.timing import FAMILIES, HORIZONS, N_VARS, pair

    rows = []
    for fam in FAMILIES:
        for nv in N_VARS:
            for T in HORIZONS:
                f1, f2 = pair(fam, nv, T)
                D = float(resolve_D(None, parse(f1), parse(f2)))
                seconds = float("inf")
                for _ in range(3):   # minimum of 3 runs, as in experiments/timing.py
                    start = time.perf_counter()
                    inter, union = mc_counts(f1, f2, D)
                    seconds = min(seconds, time.perf_counter() - start)
                rows.append((fam, nv, T, f"{seconds:.6f}", inter / union if union else "", union, f1, f2))
    with open(OUT / "mc_jaccard_timing.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["family", "n_vars", "T", "seconds", "MCJ", "union_samples", "formula1", "formula2"])
        w.writerows(rows)

    undef = [r for r in rows if r[4] == ""]
    lines = ["## Timing families (experiments/timing.py), same pairs and D", "",
             f"MCJ undefined (no sample satisfies either formula) on {len(undef)}/{len(rows)} pairs.", "",
             f"| family | horizons with MCJ undefined, of {len(HORIZONS)}, for \\|V\\| = 1/2/3/4/5 "
             "| max time (s) |", "|---|---|---|"]
    for fam in FAMILIES:
        sel = [r for r in rows if r[0] == fam]
        counts = "/".join(str(sum(r[4] == "" for r in sel if r[1] == nv)) for nv in N_VARS)
        lines.append(f"| {fam} | {counts} | {max(float(r[3]) for r in sel):.3f} |")
    return lines


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lines = [f"# Monte-Carlo Jaccard (MCJ): N = {N_SIGNALS} uniform signals on [-D, D], seed 0", ""]
    lines += pairs_report() + [""] + timing_report()
    (OUT / "mc_jaccard.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
