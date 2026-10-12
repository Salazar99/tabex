"""RQ4, step 3: cluster and prune Slam's candidates with G; compare with STLSat.

    python experiments/rq4/prune.py

Clustering is leader clustering in Slam's rank order, on G (symmetric): walk
the candidates best-ranked first; a candidate joins the first kept
representative with G >= tau, otherwise it becomes a representative itself.
So every cluster is represented by its best-ranked member, which is what a
user of a ranked miner wants to keep, and every pruned candidate is within
tau of a representative that outranks it. G, not OWSim: OWSim(a->b) = 1 only
says a's cells all have a perfect match in b, not that b says everything a
does, so it is not a redundancy criterion on its own; it is reported alongside.

Inputs: results/candidates.csv, pairs.csv.gz (similarity_matrix.py), and, if
present, implications.csv / stlsat_kept.csv (stlsat_baseline.py).
Output: results/summary.md, results/reduction.csv, results/reduction.png.
"""
import csv
import gzip
from collections import defaultdict
from pathlib import Path as FilePath

HERE = FilePath(__file__).resolve().parent
RESULTS = HERE / "results"
TAUS = [0.5, 0.6, 0.7, 0.8, 0.85, 0.9, 0.95, 0.99, 1.0]
TOL = 1e-9


def load():
    cands = defaultdict(list)
    with open(RESULTS / "candidates.csv") as fh:
        for r in csv.DictReader(fh):
            cands[(r["case"], r["context"])].append(int(r["rank"]))
    G, OW, secs = {}, {}, defaultdict(float)
    with gzip.open(RESULTS / "pairs.csv.gz", "rt", newline="") as fh:
        for r in csv.DictReader(fh):
            key, i, j = (r["case"], r["context"]), int(r["i"]), int(r["j"])
            G[key + (i, j)] = G[key + (j, i)] = float(r["G"])
            OW[key + (i, j)], OW[key + (j, i)] = float(r["ow_ij"]), float(r["ow_ji"])
            secs[key[0]] += float(r["seconds"])
    return cands, G, OW, secs


def leader(ranks, key, G, tau):
    reps = []
    for a in sorted(ranks):
        if not any(G[key + (b, a)] >= tau - TOL for b in reps):
            reps.append(a)
    return reps


def main():
    cands, G, OW, secs = load()
    cases = list(dict.fromkeys(k[0] for k in cands))
    kept = {(k, tau): len(leader(r, k, G, tau)) for k, r in cands.items() for tau in TAUS}

    stl_kept, implied = {}, {}
    if (RESULTS / "stlsat_kept.csv").exists():
        with open(RESULTS / "stlsat_kept.csv") as fh:
            for r in csv.DictReader(fh):
                stl_kept[(r["case"], r["context"])] = int(r["kept"])
    stl_secs, stl_status = defaultdict(float), defaultdict(int)
    if (RESULTS / "implications.csv").exists():
        with open(RESULTS / "implications.csv") as fh:
            for r in csv.DictReader(fh):
                key = (r["case"], r["context"], int(r["b"]), int(r["a"]))
                implied[key] = r["b_implies_a"]
                stl_secs[r["case"]] += float(r["seconds"])
                stl_status[r["b_implies_a"]] += 1

    with open(RESULTS / "reduction.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["case", "context", "candidates"] + [f"kept_G>={t}" for t in TAUS] + ["kept_stlsat"])
        for k, r in cands.items():
            w.writerow(list(k) + [len(r)] + [kept[(k, t)] for t in TAUS] + [stl_kept.get(k, "")])

    def total(case, fn):
        return sum(fn(k) for k in cands if k[0] == case)

    n_all = sum(len(r) for r in cands.values())
    lines = ["# RQ4 — redundancy pruning of Slam candidates", "",
             "Reduction rate = 1 − kept/candidates, leader clustering on G in Slam's rank order "
             "(`prune.py`). STLSat = Slam's `--remove-impl` (`stlsat_baseline.py`).", "",
             "| case | candidates | " + " | ".join(f"G≥{t:g}" for t in TAUS) + " | STLSat |",
             "|---|---|" + "---|" * (len(TAUS) + 1)]
    for case in cases + ["**all**"]:
        sel = (lambda k: True) if case == "**all**" else (lambda k, c=case: k[0] == c)
        n = sum(len(r) for k, r in cands.items() if sel(k))
        cells = []
        for t in TAUS:
            kk = sum(kept[(k, t)] for k in cands if sel(k))
            cells.append(f"{kk} ({1 - kk / n:.0%})")
        sk = sum(stl_kept.get(k, len(cands[k])) for k in cands if sel(k))
        cells.append(f"{sk} ({1 - sk / n:.0%})" if stl_kept else "—")
        lines.append(f"| {case} | {n} | " + " | ".join(cells) + " |")

    # Agreement with implication, on the pairs STLSat decided.
    buckets = defaultdict(list)
    for (case, ctx, b, a), status in implied.items():
        buckets[status].append(G[(case, ctx, b, a)])
    lines += ["", "## G on the pairs STLSat decided (same propositions)", "",
              "| stlsat verdict (b ⇒ a) | ordered pairs | mean G | min G | max G | G = 1 |",
              "|---|---|---|---|---|---|"]
    for status, gs in sorted(buckets.items()):
        lines.append(f"| {status} | {len(gs)} | {sum(gs) / len(gs):.4f} | {min(gs):.4f} | "
                     f"{max(gs):.4f} | {sum(g >= 1 - TOL for g in gs)} |")
    both = sum(1 for (c, x, b, a), s in implied.items()
               if s == "implied" and implied.get((c, x, a, b)) == "implied")
    lines.append(f"\nMutually implied (equivalent) ordered pairs: {both}; "
                 f"of those, G = 1: {sum(1 for (c, x, b, a), s in implied.items() if s == 'implied' and implied.get((c, x, a, b)) == 'implied' and G[(c, x, b, a)] >= 1 - TOL)}.")

    n_pairs = len(G) // 2
    g1 = sum(1 for v in G.values() if v >= 1 - TOL) // 2
    ow1 = sum(1 for v in OW.values() if v >= 1 - TOL)
    lines += ["", "## Pairs", "",
              f"- {n_pairs} unordered pairs scored, {g1} with G = 1 (semantically identical "
              f"canonical forms), {ow1} ordered pairs with OWSim = 1.",
              "- Cost (sum of per-call CPU-seconds): TABEX "
              + ", ".join(f"{c} {secs[c]:.0f}s" for c in cases)
              + (" | STLSat " + ", ".join(f"{c} {stl_secs[c]:.0f}s" for c in cases if c in stl_secs)
                 + f" ({dict(stl_status)})" if stl_secs else "")]
    lines.append(f"- {n_all} candidates in {len(cands)} contexts.")
    (RESULTS / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    plot(cands, kept, stl_kept, cases)


COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]


def plot(cands, kept, stl_kept, cases):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 4.8))
    for c, case in enumerate(cases):
        keys = [k for k in cands if k[0] == case]
        n = sum(len(cands[k]) for k in keys)
        ys = [1 - sum(kept[(k, t)] for k in keys) / n for t in TAUS]
        ax.plot(TAUS, ys, color=COLORS[c], marker="o", markersize=4, linewidth=2,
                label=f"{case} (n={n})")
        if stl_kept:
            sk = sum(stl_kept.get(k, len(cands[k])) for k in keys)
            ax.plot([1.03], [1 - sk / n], color=COLORS[c], marker="D", markersize=7,
                    linestyle="none")
    ax.set_xticks(TAUS + ([1.03] if stl_kept else []))
    ax.set_xticklabels([f"{t:g}" for t in TAUS] + (["STLSat"] if stl_kept else []), fontsize=8)
    ax.set_xlabel("threshold τ on G")
    ax.set_ylabel("reduction rate (1 − kept / candidates)")
    ax.set_ylim(0, 1)
    ax.grid(True, color="#e6e5e1", linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="upper right")
    ax.set_title("Pruning Slam's candidates: leader clustering on G vs STLSat implication",
                 fontsize=10)
    fig.tight_layout()
    fig.savefig(RESULTS / "reduction.png", dpi=150)


if __name__ == "__main__":
    main()
