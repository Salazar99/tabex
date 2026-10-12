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

# Syntactically different but equivalent pairs: every metric should report
# identity (TABEX 1, PH 0, SD 0). Several target SD's AoS approximation of F
# (a mandatory delta-hold per window) and of || (its most favourable
# alternative). Kept at horizon >= 1: at horizon 0 every AoS box has zero
# width in time, so SD is 0 for every pair and says nothing.
L_SHAPE = ("(x>0 && x<2 && y>0 && y<1) || (x>0 && x<1 && y>0 && y<2)",
           "(x>0 && x<1 && y>0 && y<2) || (x>=1 && x<2 && y>0 && y<1)")
EQUIVALENT = [
    ("F[0,1](x>0)", "F[0,0](x>0) || F[1,1](x>0)"),
    ("F[0,2](x>0)", "F[0,1](x>0) || F[2,2](x>0)"),
    ("G[0,2](x>0 && y<1)", "G[0,2](x>0) && G[0,2](y<1)"),
    ("F[0,2](x>0 || y>0)", "F[0,2](x>0) || F[0,2](y>0)"),
    ("!F[0,2](x>0)", "G[0,2](x<=0)"),
    ("G[0,1] G[0,1](x>0)", "G[0,2](x>0)"),
    ("F[0,1] F[0,1](x>0)", "F[0,2](x>0)"),
    ("G[0,2](x>0)", "G[0,2](x>0) && F[0,2](x>0)"),
    ("(x>0) U[0,2] (y>0)", "(x>0) U[0,2] (x>0 && y>0)"),
    ("(x>=0 || x<0) U[0,2] (y>0)", "F[0,2](y>0)"),
    ("G[0,2]((x>0 && x<2) || (x>1 && x<3))", "G[0,2](x>0 && x<3)"),
    ("F[0,2]((x>0 && x<2) || (x>1 && x<3))", "F[0,2](x>0 && x<3)"),
    (f"G[0,2]({L_SHAPE[0]})", f"G[0,2]({L_SHAPE[1]})"),
    ("G[0,3](x>0) || F[0,3](x>0 && x<1)", "G[0,3](x>0) || F[0,3](x>0 && x<1) || G[0,3](x>2)"),
]

BENCHMARK = [
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
]
MADSEN = [(TABLE1[a], TABLE1[b]) for i, a in enumerate(TABLE1) for b in list(TABLE1)[i + 1:]]
PAIRS = [("benchmark", p) for p in BENCHMARK] + [("madsen", p) for p in MADSEN] + \
    [("equivalent", p) for p in EQUIVALENT]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("-o", "--output", help="Also write the markdown table here.")
    args = parser.parse_args()

    lines = ["| # | block | phi | theta | D | TABEX sim | PH | PH/2D | SD |",
             "|---|---|---|---|---|---|---|---|---|"]
    tabex_dist, ph_dist, sd_dist = [], [], []
    missed = {"TABEX": 0, "PH": 0, "SD": 0}
    for n, (block, (f1, f2)) in enumerate(PAIRS, 1):
        D = float(resolve_D(None, parse(f1), parse(f2)))
        score = similarity(f1, f2)
        ph = d_ph(f1, f2, -D, D)[0]
        sd = d_sd(f1, f2, -D, D)
        tabex_dist.append(1 - score), ph_dist.append(ph), sd_dist.append(sd)
        if block == "equivalent":
            missed["TABEX"] += abs(score - 1) > 1e-9
            missed["PH"] += ph > 1e-6
            missed["SD"] += sd > 1e-9
        lines.append(f"| {n} | {block} | `{f1}` | `{f2}` | {D:g} | {score:.4f} | {ph:.4f} | "
                     f"{ph / (2 * D):.4f} | {sd:.4f} |")
        print(lines[-1], flush=True)

    # The correlation is over the non-equivalent pairs, as before the equivalent
    # block existed: identical pairs would only add ties at the origin.
    n_neq = len(BENCHMARK) + len(MADSEN)
    tabex_dist, ph_dist, sd_dist = tabex_dist[:n_neq], ph_dist[:n_neq], sd_dist[:n_neq]
    rho_ph = spearmanr(tabex_dist, ph_dist).statistic
    rho_sd = spearmanr(tabex_dist, sd_dist).statistic
    lines += ["", f"Spearman rank correlation of TABEX distance (1 - sim), over "
              f"all {len(tabex_dist)} pairs: "
              f"vs PH = {rho_ph:.3f}, vs SD = {rho_sd:.3f}"]
    print(lines[-1])
    lines.append(f"Equivalent block ({len(EQUIVALENT)} pairs), pairs NOT scored as identical: "
                 + ", ".join(f"{k} {v}" for k, v in missed.items()))
    print(lines[-1])
    if args.output:
        FilePath(args.output).write_text("\n".join(lines) + "\n")


if __name__ == "__main__":
    main()
