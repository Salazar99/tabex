"""TABEX vs Madsen et al. (CDC 2018) on shared formula pairs.

    python -m madsen.compare [-o madsen/results.md]

Both sides use the same domain: TABEX's D (derived as max|constant| + 1) and
Madsen's compact signal space S = [-D, D]. TABEX reports a similarity in [0, 1];
the Madsen columns are distances, PH also shown normalised by |S| = 2D so it
sits in [0, 1] like the SD. TABEX is scored by `tabex_fast` (the same number as
the reference pipeline), which is what lets Example 1 run at horizon 20.
"""
import argparse
import sys
from pathlib import Path as FilePath

from scipy.stats import spearmanr

sys.path.insert(0, str(FilePath(__file__).resolve().parent.parent))

from madsen.metrics import d_ph, d_sd  # noqa: E402
from similarity.reference_semantics import parse  # noqa: E402
from similarity.stl_similarity import resolve_D  # noqa: E402
from tabex_fast.engine import similarity  # noqa: E402

THETA1 = "(x>=0.2 && x<=0.4)"
THETA2 = "(x>=0.2 && x<=0.44)"
TABLE1 = {   # the paper's Example 1, eq. (3)
    "T": "true",
    "phi1": f"G[0,20]{THETA1}",
    "phi2": f"G[0,20]{THETA2}",
    "phi3": f"F[0,20]{THETA1}",
    "phi4": f"G[0,20]{THETA1} && F[0,20]{THETA2}",
    "phi5": f"G[0,10]{THETA1} && G[12,20]{THETA2}",
    "phi6": f"G[0,16] F[0,4]{THETA1}",
}

PAIRS = [
    # benchmarks/Manual/benchmark_gen.sh
    ("F[0,2](x>0)", "G[0,2](x>0)"),
    ("F[0,2](x>0)", "F[3,4](x>0)"),
    ("F[0,2](z>0)", "F[0,2](x>0)"),
    ("G[0,2](x>0)", "G[0,2](x>0 || y>0)"),
    ("G[0,2](x>0)", "G[0,2](x>0 && y>0)"),
    ("F[0,2](x>0)", "F[0,2](x>0 || y>0 || z>0 || w>0)"),
    ("F[0,2](x>0)", "F[0,2](x>0 && y>0 && z>0 && w>0)"),
    ("F[0,2](x>0 && y>0)", "F[0,2](x>0 || y>0)"),
    ("F[0,2](x<5)", "F[0,2](x>0)"),
    ("F[0,4](x>0)", "F[0,2](x>0)"),
] + [(TABLE1[a], TABLE1[b]) for i, a in enumerate(TABLE1) for b in list(TABLE1)[i + 1:]]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", help="Also write the markdown table here.")
    args = parser.parse_args()

    lines = ["| # | phi | theta | D | TABEX sim | PH | PH/2D | SD |",
             "|---|---|---|---|---|---|---|---|"]
    tabex_dist, ph_dist, sd_dist = [], [], []
    for n, (f1, f2) in enumerate(PAIRS, 1):
        D = float(resolve_D(None, parse(f1), parse(f2)))
        score = similarity(f1, f2)
        ph = d_ph(f1, f2, -D, D)[0]
        sd = d_sd(f1, f2, -D, D)
        tabex_dist.append(1 - score), ph_dist.append(ph), sd_dist.append(sd)
        lines.append(f"| {n} | `{f1}` | `{f2}` | {D:g} | {score:.4f} | {ph:.4f} | "
                     f"{ph / (2 * D):.4f} | {sd:.4f} |")
        print(lines[-1], flush=True)

    rho_ph = spearmanr(tabex_dist, ph_dist).statistic
    rho_sd = spearmanr(tabex_dist, sd_dist).statistic
    lines += ["", f"Spearman rank correlation of TABEX distance (1 - sim), over "
              f"all {len(tabex_dist)} pairs: "
              f"vs PH = {rho_ph:.3f}, vs SD = {rho_sd:.3f}"]
    print(lines[-1])
    if args.output:
        FilePath(args.output).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
