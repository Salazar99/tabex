"""Ablation: G (box matching) vs exact volume Jaccard of the two regions.

    python experiments/volume_ablation.py

The decision diagram makes the obvious alternative to G cheap: the exact
(eps-)volume Jaccard of the two signal spaces on [-D, D]^A (tabex_fast/volume.py).
Both are 1 exactly on equivalent formulas; they differ in how they aggregate.
This script shows where that matters:

1. collapse -- theta1 = [0.2, 0.4] vs theta2 = [0.2, 0.44] under G[0,T] and
   F[0,T] on |V| = 1..3 variables. A per-instant discrepancy is multiplied
   once per axis by volume, so VolJ decays geometrically in (T+1)|V|; G
   averages per axis and does not.
2. the RQ2 suite (madsen/compare.py's 45 pairs): G, VolJ, PH/2D, SD side by
   side, and rank correlations of the distances.

Output: experiments/results/volume_ablation.{csv,png}, volume_suite.csv.
"""
import csv
import sys
import time
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from experiments.timing import pair  # noqa: E402
from tabex_fast.engine import similarity  # noqa: E402
from tabex_fast.volume import volume_jaccard  # noqa: E402

OUT = ROOT / "experiments" / "results"
# Largest T per (family, |V|) that tabex_fast scores in a few seconds (RQ2 timing).
T_MAX = {("G", 1): 40, ("G", 2): 40, ("G", 3): 40, ("F", 1): 40, ("F", 2): 12, ("F", 3): 8}
TS = [0, 1, 2, 3, 4, 6, 8, 10, 12, 16, 20, 24, 28, 32, 36, 40]


def collapse():
    rows = []
    for (fam, n), tmax in T_MAX.items():
        for T in [t for t in TS if t <= tmax]:
            f1, f2 = pair(fam, n, max(T, 0)) if T > 0 else pair(fam, n, 2)
            if T == 0:   # the bare predicate, one instant
                f1, f2 = f1.replace(f"{fam}[0,2]", ""), f2.replace(f"{fam}[0,2]", "")
            start = time.perf_counter()
            g = similarity(f1, f2)
            tg = time.perf_counter() - start
            start = time.perf_counter()
            v = volume_jaccard(f1, f2)
            tv = time.perf_counter() - start
            rows.append((fam, n, T, g, v, tg, tv, f1, f2))
            print(f"{fam} |V|={n} T={T:2}  G={g:.4f}  VolJ={v:.3e}  ({tg:.2f}s / {tv:.3f}s)", flush=True)
    with open(OUT / "volume_ablation.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["family", "n_vars", "T", "G", "VolJ", "seconds_G", "seconds_VolJ",
                    "formula1", "formula2"])
        w.writerows(rows)
    return rows


def suite():
    from scipy.stats import spearmanr
    from madsen.compare import PAIRS
    from madsen.metrics import d_ph, d_sd
    from similarity.reference_semantics import parse
    from similarity.stl_similarity import resolve_D

    rows = []
    for block, (f1, f2) in PAIRS:
        D = float(resolve_D(None, parse(f1), parse(f2)))
        rows.append((block, f1, f2, similarity(f1, f2), volume_jaccard(f1, f2),
                     d_ph(f1, f2, -D, D)[0] / (2 * D), d_sd(f1, f2, -D, D)))
    with open(OUT / "volume_suite.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["block", "phi", "theta", "G", "VolJ", "PH_over_2D", "SD"])
        w.writerows(rows)
    neq = [r for r in rows if r[0] != "equivalent"]
    eq = [r for r in rows if r[0] == "equivalent"]
    dist = {"1-G": [1 - r[3] for r in neq], "1-VolJ": [1 - r[4] for r in neq],
            "PH/2D": [r[5] for r in neq], "SD": [r[6] for r in neq]}
    names = list(dist)
    print("\nSpearman rho of distances over the", len(neq), "non-equivalent pairs:")
    for a in names:
        print("  " + a.ljust(7) + " ".join(f"{spearmanr(dist[a], dist[b]).statistic:6.3f}"
                                           for b in names))
    print(f"equivalent block: VolJ = 1 on {sum(abs(r[4] - 1) < 1e-9 for r in eq)}/{len(eq)}")
    return rows


COLORS = {1: "#2a78d6", 2: "#eb6834", 3: "#1baf7a"}


def plot(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(12, 4.4))
    for ax, fam, title in zip(axes, ["G", "F"], ["G[0,T] θ1 vs G[0,T] θ2", "F[0,T] θ1 vs F[0,T] θ2"]):
        for n in (1, 2, 3):
            pts = sorted((r[2], r[3], r[4]) for r in rows if r[0] == fam and r[1] == n)
            if not pts:
                continue
            ts = [p[0] for p in pts]
            ax.plot(ts, [p[1] for p in pts], color=COLORS[n], linewidth=2, marker="o",
                    markersize=4, label=f"G, |V|={n}")
            ax.plot(ts, [p[2] for p in pts], color=COLORS[n], linewidth=1.5, linestyle="--",
                    marker="s", markersize=3, label=f"volume Jaccard, |V|={n}")
        if fam == "G":
            ax.set_yscale("log")
            ax.set_ylim(1e-6, 1.5)
        else:
            ax.set_ylim(0.5, 1.0)
        ax.set_xlabel("horizon T")
        ax.set_title(title, fontsize=10)
        ax.grid(True, color="#e6e5e1", linewidth=0.6)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].set_ylabel("similarity (log scale)")
    axes[1].set_ylabel("similarity")
    handles, labels = axes[1].get_legend_handles_labels()
    fig.legend(handles, labels, frameon=False, fontsize=8, loc="lower center", ncol=6)
    fig.suptitle("θ1 = [0.2, 0.4] vs θ2 = [0.2, 0.44] on every variable.\nVolume Jaccard is driven by "
                 "the dimension (T+1)|V|: to 0 under G, towards 1 under F. G is not "
                 "(left: its three |V| curves coincide at 0.8333)", fontsize=10)
    fig.tight_layout(rect=(0, 0.07, 1, 1))
    fig.savefig(OUT / "volume_ablation.png", dpi=150)


if __name__ == "__main__":
    rows = collapse()
    plot(rows)
    suite()
