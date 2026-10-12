"""Paper figures (vector PDF, LNCS text width) from the experiment CSVs.

    python experiments/paper_figures.py [OUT_DIR]

Reads experiments/results/{timing,d_sensitivity}.csv; writes timing.pdf and
d_sensitivity.pdf to OUT_DIR (default experiments/results/paper), and the
largest-horizon table and quoted times of RQ1 to experiments/results/timing.md.
The full-size working plots stay with each experiment script.
"""
import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

RES = Path(__file__).resolve().parent / "results"
WIDTH = 4.8                       # in, LNCS \textwidth = 12.2 cm
# categorical slots 1-4 of the validated default palette; markers carry identity in grayscale
C = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]
INK, MUTED, GRID = "#1a1a19", "#6b6a66", "#e6e5e1"
BOX = {"frameon": True, "framealpha": 1, "facecolor": "white", "edgecolor": "none"}  # legend hides lines behind it
plt.rcParams.update({"font.size": 7, "axes.titlesize": 7, "axes.labelsize": 7, "legend.fontsize": 6.5,
                     "xtick.labelsize": 6, "ytick.labelsize": 6, "axes.edgecolor": MUTED,
                     "axes.labelcolor": INK, "xtick.color": MUTED, "ytick.color": MUTED,
                     "pdf.fonttype": 42, "lines.linewidth": 1.2, "lines.markersize": 3})


def style(ax):
    ax.grid(True, color=GRID, linewidth=0.5)
    ax.set_axisbelow(True)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def timing(out, timeout=60.0):
    rows = list(csv.DictReader(open(RES / "timing.csv")))
    methods = [("fast_similarity", "fast_similarity", "s"),
               ("reference", "definitional pipeline", "o"), ("PH", "PH (MILP)", "^"), ("SD", "SD (AoS)", "D")]
    fams = [("G", r"$\mathsf{G}_{[0,T]}\theta$"), ("F", r"$\mathsf{F}_{[0,T]}\theta$"),
            ("GF", r"$\mathsf{G}_{[0,T-2]}\mathsf{F}_{[0,2]}\theta$"), ("U", r"$\theta\,\mathsf{U}_{[0,T]}\,\theta'$")]
    nvs = [1, 3]
    fig, axes = plt.subplots(len(nvs), len(fams), figsize=(WIDTH, 2.7), sharex=True, sharey=True)
    for i, n in enumerate(nvs):
        for j, (fam, title) in enumerate(fams):
            ax = axes[i][j]
            for k, (m, label, mk) in enumerate(methods):
                sel = [r for r in rows if r["family"] == fam and int(r["n_vars"]) == n and r["method"] == m]
                ok = [(int(r["T"]), float(r["seconds"])) for r in sel if r["status"] == "ok"]
                if ok:
                    ax.plot(*zip(*ok), color=C[k], marker=mk, label=label)
                fail = [int(r["T"]) for r in sel if r["status"] in ("timeout", "memout")]
                if fail:           # a failure ends the series: mark the first one on the limit line
                    ax.plot([min(fail)], [timeout], color=C[k], marker="x", markersize=5, linestyle="none")
            ax.axhline(timeout, color=MUTED, linewidth=0.6, linestyle=":")
            ax.set_yscale("log")
            ax.set_ylim(1e-4, 2e2)
            ax.set_yticks([1e-4, 1e-2, 1, 1e2])
            style(ax)
            if i == 0:
                ax.set_title(title)
            if j == 0:
                ax.set_ylabel(f"$|V|={n}$\ntime (s)")
            if i == len(nvs) - 1:
                ax.set_xlabel("horizon $T$")
    handles, labels = axes[0][0].get_legend_handles_labels()
    handles.append(plt.Line2D([], [], color=MUTED, marker="x", linestyle="none"))
    labels.append(f"limit hit ({timeout:g} s / 3 GB)")
    fig.legend(handles, labels, loc="upper center", ncol=5, frameon=False, handletextpad=0.3,
               columnspacing=0.9)
    fig.tight_layout(rect=(0, 0, 1, 0.92), pad=0.3, w_pad=0.4, h_pad=0.4)
    fig.savefig(out / "timing.pdf")


def d_sensitivity(out):
    rows = list(csv.DictReader(open(RES / "d_sensitivity.csv")))

    def series(pair):
        pts = sorted((float(r["D"]), float(r["score"])) for r in rows if r["pair"] == pair)
        return list(zip(*pts))

    fig, (a, b) = plt.subplots(1, 2, figsize=(WIDTH, 1.9), sharey=True)
    for k, (c2, delta) in enumerate([("5/2", "0.5"), ("3", "1"), ("5", "3"), ("12", "10")]):
        a.plot(*series(f"x>2 vs x>{c2}"), color=C[k], label=rf"$\Delta={delta}$")
        eq4 = next(float(r["eq4"]) for r in rows if r["pair"] == f"x>2 vs x>{c2}")
        a.axhline(eq4, color=C[k], linewidth=0.8, linestyle="--")
    a.set_title(r"$x>2$ vs $x>2+\Delta$; dashed: $1/(1+\Delta)$")
    a.set_ylabel(r"$\mathrm{Point\_sim}_D$ ($=G$)")
    a.legend(loc="lower right", handlelength=1.5, **BOX)
    for pair, label, color, ls in [
            ("G[0,2](x>2) vs G[0,2](x>5)", r"$\mathsf{G}_{[0,2]}$", C[0], "-"),
            ("F[0,2](x>2) vs F[0,2](x>5)", r"$\mathsf{F}_{[0,2]}$", C[1], "-"),
            ("(x>2) U[0,2] (y>0) vs (x>5) U[0,2] (y>0)", r"$\mathsf{U}_{[0,2]}$", C[2], "-"),
            ("[2,5] vs [2,8]", r"$2<x<5$ vs $2<x<8$", INK, "--"),
            ("[2,5] vs x>2", r"$2<x<5$ vs $x>2$", INK, ":")]:
        b.plot(*series(pair), color=color, linestyle=ls, label=label)
    b.set_title(r"$x>2$ vs $x>5$ under $\mathsf{G},\mathsf{F},\mathsf{U}$; controls")
    b.legend(loc="lower right", bbox_to_anchor=(1, 0.06), handlelength=1.8, **BOX)
    for ax in (a, b):
        ax.set_xscale("log")
        ax.set_xlabel("domain $D$")
        ax.set_ylim(-0.03, 1.03)
        style(ax)
    fig.tight_layout(pad=0.3, w_pad=0.8)
    fig.savefig(out / "d_sensitivity.pdf")


def timing_table():
    """Table 4 (largest T completed) and the times quoted in Section 6.2, from timing.csv."""
    rows = list(csv.DictReader(open(RES / "timing.csv")))
    ok = {}
    for r in rows:
        if r["status"] == "ok":
            ok[(r["family"], r["method"], int(r["n_vars"]), int(r["T"]))] = float(r["seconds"])
    methods = [("reference", "definitional pipeline"), ("fast_similarity", "fast_similarity"), ("PH", "PH")]
    fams = [("G", "G[0,T] θ"), ("F", "F[0,T] θ"), ("GF", "G[0,T-2] F[0,2] θ"), ("U", "θ U[0,T] θ'")]
    lines = ["# RQ1 timing summary (from timing.csv)", "",
             "Largest horizon T ≤ 40 completed within the limits, for |V| = 1/2/3/4/5 (–: none).", "",
             "| family | " + " | ".join(label for _, label in methods) + " |",
             "|---|" + "---|" * len(methods)]
    for fam, label in fams:
        cells = ["/".join(str(max((T for (f, m, n, T) in ok if f == fam and m == meth and n == nv), default="–"))
                          for nv in range(1, 6)) for meth, _ in methods]
        lines.append(f"| {label} | " + " | ".join(cells) + " |")
    lines += ["", "Times quoted in the text (|V| = 1):", "",
              f"- F[0,4]θ: definitional pipeline {ok[('F', 'reference', 1, 4)]:.1f} s, "
              f"fast_similarity {ok[('F', 'fast_similarity', 1, 4)]:.3f} s",
              f"- θ U[0,20] θ': fast_similarity {ok[('U', 'fast_similarity', 1, 20)]:.2f} s, "
              f"PH {ok[('U', 'PH', 1, 20)]:.1f} s"]
    (RES / "timing.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else RES / "paper"
    out.mkdir(parents=True, exist_ok=True)
    timing(out)
    d_sensitivity(out)
    timing_table()
