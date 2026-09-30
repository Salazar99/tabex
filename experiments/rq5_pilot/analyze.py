"""RQ5: quantify semantic drift among LLM formalisations of one requirement.

    python experiments/rq5_pilot/analyze.py

Inputs: requirements.csv (12 requirements, each with a hand-written reference
formalisation) and samples/<model>-<k>.json, one per independent LLM run of
prompt.txt (the answer, verbatim). Every output is parsed by
`reference_semantics.parse`; parse errors and formulas outside the fragment are
reported separately from drift and excluded from the scores.

Per requirement, with one D for all of its formulas (max|constant| + 1 over
samples and reference, so every score of a requirement is on one scale):

* syntactic spread -- distinct strings (whitespace-normalised);
* semantic classes -- groups with G = 1 (same canonical region);
* drift -- mean and min pairwise G between samples;
* accuracy -- G, and both OWSim directions, of each sample vs the reference.

Scored by tabex_fast. Output: results/pairs.csv, results/vs_reference.csv,
results/summary.md, results/drift.png.
"""
import csv
import json
import re
import sys
from fractions import Fraction
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from similarity.reference_semantics import constants, parse  # noqa: E402
from tabex_fast.engine import one_way, regions  # noqa: E402

HERE = FilePath(__file__).resolve().parent
RESULTS = HERE / "results"
MODELS = ["haiku", "sonnet", "opus"]
TOL = 1e-9


def scores(f1, f2, D):
    r1, r2, _, _ = regions(f1, f2)
    fw, bw = one_way(r1, r2, D), one_way(r2, r1, D)
    return fw, bw, (fw + bw) / 2


def main():
    reqs = list(csv.DictReader(open(HERE / "requirements.csv")))
    samples = {p.stem: json.loads(p.read_text()) for p in sorted((HERE / "samples").glob("*.json"))}
    RESULTS.mkdir(exist_ok=True)

    failures, per_req, pair_rows, ref_rows = [], [], [], []
    for req in reqs:
        rid, ref = req["id"], req["reference"]
        ok = {}
        for name, answer in samples.items():
            text = answer.get(rid)
            if text is None:
                failures.append((name, rid, "missing", ""))
                continue
            try:
                parse(text)
                ok[name] = text
            except Exception as exc:  # noqa: BLE001  -- parse error or UnsupportedFormula
                failures.append((name, rid, type(exc).__name__, str(exc).splitlines()[0][:100]))
        D = max((abs(c) for f in list(ok.values()) + [ref] for c in constants(parse(f))),
                default=Fraction(0)) + 1

        names = sorted(ok)
        G = {}
        for a, n1 in enumerate(names):
            for n2 in names[a + 1:]:
                fw, bw, g = scores(ok[n1], ok[n2], D)
                G[(n1, n2)] = G[(n2, n1)] = g
                pair_rows.append((rid, n1, n2, f"{fw:.6f}", f"{bw:.6f}", f"{g:.6f}"))
        vs_ref = {}
        for n in names:
            fw, bw, g = scores(ok[n], ref, D)
            vs_ref[n] = g
            ref_rows.append((rid, n, ok[n], f"{fw:.6f}", f"{bw:.6f}", f"{g:.6f}"))

        classes = []   # G = 1 is an equivalence (same canonical region)
        for n in names:
            for cls in classes:
                if G[(cls[0], n)] >= 1 - TOL:
                    cls.append(n)
                    break
            else:
                classes.append([n])
        norm = {re.sub(r"\s+", "", ok[n]) for n in names}
        pg = [G[(a, b)] for i, a in enumerate(names) for b in names[i + 1:]]
        per_req.append(dict(
            id=rid, D=D, n=len(names), strings=len(norm), classes=len(classes),
            biggest=max(len(c) for c in classes), mean_pair=sum(pg) / len(pg), min_pair=min(pg),
            mean_ref=sum(vs_ref.values()) / len(vs_ref), min_ref=min(vs_ref.values()),
            exact_ref=sum(v >= 1 - TOL for v in vs_ref.values()), vs_ref=vs_ref,
            worst=min(names, key=lambda n: vs_ref[n]), ok=ok))
        print(f"{rid}: {len(norm)} strings, {len(classes)} classes, "
              f"mean pairwise G {sum(pg) / len(pg):.4f}, mean G vs ref {per_req[-1]['mean_ref']:.4f}",
              flush=True)

    with open(RESULTS / "pairs.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["req", "sample1", "sample2", "ow_12", "ow_21", "G"])
        w.writerows(pair_rows)
    with open(RESULTS / "vs_reference.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["req", "sample", "formula", "ow_sample_ref", "ow_ref_sample", "G"])
        w.writerows(ref_rows)

    lines = ["# RQ5 — semantic drift in LLM formalisations", "",
             f"{len(samples)} independent runs of `prompt.txt` ({', '.join(samples)}), "
             f"{len(reqs)} requirements. Scored by tabex_fast, one D per requirement.", "",
             f"Parse / fragment failures (excluded from scores): {len(failures)}"]
    lines += [f"- {n} {r}: {kind} {msg}" for n, r, kind, msg in failures]
    lines += ["", "| req | D | samples | distinct strings | G=1 classes | largest class | "
              "mean pairwise G | min pairwise G | mean G vs ref | min G vs ref | = ref | "
              "worst sample |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in per_req:
        lines.append(f"| {r['id']} | {float(r['D']):g} | {r['n']} | {r['strings']} | {r['classes']} | "
                     f"{r['biggest']} | {r['mean_pair']:.4f} | {r['min_pair']:.4f} | "
                     f"{r['mean_ref']:.4f} | {r['min_ref']:.4f} | {r['exact_ref']}/{r['n']} | "
                     f"`{r['ok'][r['worst']]}` ({r['worst']}, {r['vs_ref'][r['worst']]:.4f}) |")
    lines += ["", "Mean G vs reference, per model:", ""]
    for m in MODELS:
        vals = [v for r in per_req for n, v in r["vs_ref"].items() if n.startswith(m)]
        if vals:
            lines.append(f"- {m}: {sum(vals) / len(vals):.4f} over {len(vals)} formulas, "
                         f"{sum(v >= 1 - TOL for v in vals)} equivalent to the reference")
    total_strings = sum(r["strings"] for r in per_req)
    total_classes = sum(r["classes"] for r in per_req)
    lines += ["", f"Across all requirements: {total_strings} distinct strings collapse to "
              f"{total_classes} semantic classes (G = 1)."]
    (RESULTS / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    plot(per_req)


COLORS = {"haiku": "#2a78d6", "sonnet": "#eb6834", "opus": "#1baf7a"}
MARKERS = {"haiku": "o", "sonnet": "s", "opus": "^"}


def plot(per_req):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(10, 4.5))
    for x, r in enumerate(per_req):
        for k, m in enumerate(MODELS):
            vals = sorted(v for n, v in r["vs_ref"].items() if n.startswith(m))
            xs = [x + (k - 1) * 0.22 + (i - (len(vals) - 1) / 2) * 0.05 for i in range(len(vals))]
            ax.plot(xs, vals, color=COLORS[m], marker=MARKERS[m], markersize=6, linestyle="none",
                    label=m if x == 0 else None)
        ax.plot([x - 0.4, x + 0.4], [r["mean_pair"]] * 2, color="#52514e", linewidth=1.5,
                label="mean pairwise G among samples" if x == 0 else None)
    ax.set_xticks(range(len(per_req)))
    ax.set_xticklabels([r["id"] for r in per_req])
    ax.set_ylabel("G(sample, reference)")
    ax.set_ylim(min(r["min_ref"] for r in per_req) - 0.05, 1.02)
    ax.grid(True, axis="y", color="#e6e5e1", linewidth=0.6)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.legend(frameon=False, fontsize=8, loc="lower left", ncol=4)
    ax.set_title("LLM formalisations vs reference, per requirement (3 runs per model)", fontsize=10)
    fig.tight_layout()
    fig.savefig(RESULTS / "drift.png", dpi=150)


if __name__ == "__main__":
    main()
