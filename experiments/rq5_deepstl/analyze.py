"""RQ5 on DeepSTL: score LLM formalisations against the reference, and check G.

    python experiments/rq5_deepstl/analyze.py

Inputs: results/requirements.csv, results/samples.jsonl (generate.py).

Each answer is cleaned (markdown fences, quotes, first formula line), put
through the same conversion as the references (deepstl.convert: DeepSTL
keywords, [a:b] bounds, an outermost unbounded G dropped), and parsed.
Parse errors and formulas outside the fragment are counted per model and
excluded. Every parsed answer is scored against its reference by G
(tabex_fast), VolJ (tabex_fast.volume), PH/2D and SD (madsen; `==` written as a
closed range, answers with `!=` get no PH/SD), with one D per requirement
(max|c| over reference and all its answers, + 1).

Independent check -- a sampling oracle that does not use TABEX: signals are
drawn per axis from the formulas' own breakpoints (a random constant, a point
strictly between two consecutive constants, or beyond the extremes, each atom
of the joint arrangement equally likely) and both formulas are evaluated on
them by the trace monitor of experiments/rq4/quality.py. For each pair:

* disagree -- fraction of N_SIGNALS signals on which exactly one formula holds.

G = 1 must coincide with "no distinguishing signal found" up to sampling (a
G < 1 pair may differ on too thin a set to be hit), and among non-equivalent
answers the rank correlation of each measure's distance with `disagree` says
which measure grades an error the way the signals do.

Also per requirement: pairwise G among the samples of one model (drift), and
distinct strings vs G = 1 classes.

Output: results/scores.csv, results/summary.md, results/rq5.png.
"""
import csv
import json
import random
import re
import sys
from collections import defaultdict
from fractions import Fraction
from pathlib import Path as FilePath

import numpy as np

HERE = FilePath(__file__).resolve().parent
ROOT = HERE.parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(HERE))

from deepstl import convert  # noqa: E402
from experiments.rq4.quality import evaluate  # noqa: E402
from similarity.reference_semantics import constants, parse, variables  # noqa: E402
from tabex_fast.engine import _atoms, one_way, regions  # noqa: E402
from tabex_fast.volume import volume_jaccard  # noqa: E402

RESULTS = HERE / "results"
N_SIGNALS = 4000
TOL = 1e-9


def clean(answer):
    text = answer.strip()
    text = re.sub(r"^```[a-zA-Z]*\s*|```$", "", text, flags=re.M).strip()
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    text = lines[0] if lines else ""
    return text.strip("`\"' ").rstrip(".")


def sample_signals(trees, horizon, rng):
    cuts = defaultdict(set)
    for t in trees:
        for var, c in _atoms(t):
            cuts[var].add(float(c))
    all_vars = sorted(set().union(*(variables(t) for t in trees)))
    n = horizon + 1
    sigs = {}
    for v in all_vars:
        cs = sorted(cuts[v])
        points = cs + [(a + b) / 2 for a, b in zip(cs, cs[1:])] + [cs[0] - 1, cs[-1] + 1] if cs else [0.0]
        # a random point *inside* each open gap, not only its midpoint
        choice = rng.integers(0, len(points), size=(N_SIGNALS, n))
        vals = np.array(points)[choice]
        gaps = [(a, b) for a, b in zip(cs, cs[1:])]
        for g, (a, b) in enumerate(gaps):
            mask = choice == len(cs) + g
            vals[mask] = rng.uniform(a, b, size=mask.sum()) if b > a else a
        sigs[v] = vals
    return sigs


def disagreement(f1, f2, seed):
    t1, t2 = parse(f1), parse(f2)
    h = max(t1.horizon(), t2.horizon())
    rng = np.random.default_rng(seed)
    sigs = sample_signals([t1, t2], h, rng)
    # Evaluated at t = 0 a formula reads only instants 0..h (locality, Lemma 7), so the
    # N signals are laid end to end as one trace and read back at every block start.
    trace = {v: arr.reshape(-1) for v, arr in sigs.items()}
    starts = np.arange(N_SIGNALS) * (h + 1)
    a = evaluate(t1, trace, N_SIGNALS * (h + 1))[starts]
    b = evaluate(t2, trace, N_SIGNALS * (h + 1))[starts]
    diff = int((a != b).sum())
    return diff / N_SIGNALS


def rectangular(f):
    return re.sub(r"\(?\s*(\w+)\s*==\s*(-?[\d.]+)\s*\)?", r"(\1 >= \2 && \1 <= \2)", f)


BUDGET_S = 120


def _child(fn, job, queue):
    queue.put(fn(job))


def budgeted(fn, job, on_timeout):
    """fn(job) in a forked child, killed after BUDGET_S (the RQ2 timing harness idea)."""
    import multiprocessing as mp
    ctx = mp.get_context("fork")
    queue = ctx.Queue()
    proc = ctx.Process(target=_child, args=(fn, job, queue))
    proc.start()
    proc.join(BUDGET_S)
    if proc.is_alive():
        proc.kill()
        proc.join()
        return on_timeout(job)
    try:
        return queue.get(timeout=10)
    except Exception:  # noqa: BLE001  -- child died without a result (e.g. out of memory)
        return on_timeout(job)


def score(job):
    """One answer vs its reference; None scores if it exceeds BUDGET_S (reported)."""
    return budgeted(_score, job, lambda j: {"id": j[0], "model": j[1], "sample": j[2],
                                             "formula": j[3], "G": None, "over_budget": True})


def _score(job):
    rid, model, k, answer_f, ref_f, D, seed = job
    from madsen.metrics import d_ph, d_sd
    r1, r2, _, _ = regions(answer_f, ref_f)
    fw, bw = one_way(r1, r2, D), one_way(r2, r1, D)
    out = {"id": rid, "model": model, "sample": k, "formula": answer_f,
           "ow_ans_ref": fw, "ow_ref_ans": bw, "G": (fw + bw) / 2,
           "VolJ": volume_jaccard(answer_f, ref_f, D=D),
           "disagree": disagreement(answer_f, ref_f, seed)}
    if "!=" in answer_f or "!=" in ref_f:
        out["PH"] = out["SD"] = None
    else:
        try:
            a, b = rectangular(answer_f), rectangular(ref_f)
            out["PH"] = d_ph(a, b, -float(D), float(D))[0] / (2 * float(D))
            out["SD"] = d_sd(a, b, -float(D), float(D))
        except Exception:  # noqa: BLE001
            out["PH"] = out["SD"] = None
    return out


def _pair_G(job):
    rid, model, a, b, fa, fb, D = job
    r1, r2, _, _ = regions(fa, fb)
    return rid, model, a, b, (one_way(r1, r2, D) + one_way(r2, r1, D)) / 2


def pair_G(job):
    return budgeted(_pair_G, job, lambda j: (j[0], j[1], j[2], j[3], None))


def main():
    reqs = {r["id"]: r for r in csv.DictReader(open(RESULTS / "requirements.csv"))}
    samples = [json.loads(l) for l in open(RESULTS / "samples.jsonl")]
    models = sorted({s["model"] for s in samples})
    parsed, failures = [], defaultdict(lambda: defaultdict(int))
    for s in samples:
        text = convert(clean(s["answer"]))
        try:
            parse(text)
            parsed.append((s, text))
        except Exception as exc:  # noqa: BLE001
            failures[s["model"]][type(exc).__name__] += 1
    by_req = defaultdict(list)
    for s, f in parsed:
        by_req[s["id"]].append((s, f))
    D = {}
    for rid, lst in by_req.items():
        fs = [reqs[rid]["reference"]] + [f for _, f in lst]
        D[rid] = max((abs(c) for f in fs for c in constants(parse(f))), default=Fraction(0)) + 1
    jobs = [(s["id"], s["model"], s["sample"], f, reqs[s["id"]]["reference"], D[s["id"]], n)
            for n, (s, f) in enumerate(parsed)]
    pjobs = []
    for rid, lst in by_req.items():
        per_model = defaultdict(list)
        for s, f in lst:
            per_model[s["model"]].append((s["sample"], f))
        for m, xs in per_model.items():
            pjobs += [(rid, m, a, b, fa, fb, D[rid]) for i, (a, fa) in enumerate(xs)
                      for b, fb in xs[i + 1:]]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(24) as pool:     # each job forks its own killable child
        scores = list(pool.map(score, jobs))
        pairs = list(pool.map(pair_G, pjobs))

    fields = ["id", "model", "sample", "formula", "G", "ow_ans_ref", "ow_ref_ans", "VolJ",
              "PH", "SD", "disagree", "over_budget"]
    with open(RESULTS / "scores.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(scores)
    over = [s for s in scores if s.get("over_budget")]
    scores = [s for s in scores if not s.get("over_budget")]
    pairs = [p for p in pairs if p[4] is not None]

    from scipy.stats import spearmanr
    lines = ["# RQ5 on DeepSTL — LLM formalisations vs reference", "",
             f"{len(reqs)} DeepSTL requirements with answers: {len(by_req)}; "
             f"{len(samples)} answers from {', '.join(models)}.", "",
             "## Parsing", "", "| model | answers | parsed | failures by reason |", "|---|---|---|---|"]
    for m in models:
        n = sum(1 for s in samples if s["model"] == m)
        p = sum(1 for s, _ in parsed if s["model"] == m)
        lines.append(f"| {m} | {n} | {p} | {dict(failures[m]) or '—'} |")

    lines += ["", f"Not scored within {BUDGET_S} s per answer (long nested windows, cf. RQ2 timing): "
              f"{len(over)} — " + ", ".join(f"{m} {sum(o['model'] == m for o in over)}" for m in models)]
    lines += ["", "## Correctness (G = 1 ⇔ equivalent to the reference)", "",
              "| model | parsed | G = 1 | exact string match | mean G | mean G when wrong |",
              "|---|---|---|---|---|---|"]
    for m in models:
        sc = [s for s in scores if s["model"] == m]
        exact = sum(re.sub(r"\s+", "", s["formula"]) == re.sub(r"\s+", "", reqs[s["id"]]["reference"])
                    for s in sc)
        wrong = [s["G"] for s in sc if s["G"] < 1 - TOL]
        lines.append(f"| {m} | {len(sc)} | {sum(s['G'] >= 1 - TOL for s in sc)} | {exact} | "
                     f"{np.mean([s['G'] for s in sc]):.4f} | "
                     f"{np.mean(wrong) if wrong else float('nan'):.4f} |")
    by_type = defaultdict(list)
    for s in scores:
        by_type[reqs[s["id"]]["type"]].append(s["G"] >= 1 - TOL)
    lines += ["", "By DeepSTL requirement type: " + ", ".join(
        f"{t} {sum(v)}/{len(v)}" for t, v in sorted(by_type.items()))]

    eq = [s for s in scores if s["G"] >= 1 - TOL]
    neq = [s for s in scores if s["G"] < 1 - TOL]
    lines += ["", "## Independent check (sampling oracle, not TABEX)", "",
              f"- G = 1 and a distinguishing signal found: "
              f"{sum(s['disagree'] > 0 for s in eq)}/{len(eq)} (must be 0).",
              f"- G < 1 and a distinguishing signal found: "
              f"{sum(s['disagree'] > 0 for s in neq)}/{len(neq)} "
              f"(the rest differ on a set too thin for {N_SIGNALS} samples, e.g. one endpoint)."]
    lines += ["", f"Spearman ρ between each distance and the disagreement rate, over the "
              f"{len(neq)} non-equivalent answers (pairs with PH/SD undefined dropped for those):", ""]
    for name, key, tr in (("1 − G", "G", lambda v: 1 - v), ("1 − VolJ", "VolJ", lambda v: 1 - v),
                          ("PH/2D", "PH", lambda v: v), ("SD", "SD", lambda v: v)):
        pts = [(tr(s[key]), s["disagree"]) for s in neq if s.get(key) is not None]
        rho = spearmanr(*zip(*pts)).statistic if len(pts) > 2 else float("nan")
        blind = sum(1 for d, _ in pts if d <= (1e-6 if key == "PH" else TOL))
        lines.append(f"- {name}: ρ = {rho:.3f} (n = {len(pts)}); scored as identical although "
                     f"not equivalent: {blind}")

    lines += ["", "## Drift among the samples of one model", ""]
    drift = defaultdict(list)
    for rid, m, a, b, g in pairs:
        drift[m].append(g)
    for m in models:
        gs = drift[m]
        lines.append(f"- {m}: {len(gs)} sample pairs, mean pairwise G {np.mean(gs):.4f}, "
                     f"{sum(g >= 1 - TOL for g in gs)} equivalent; requirements with some "
                     f"disagreement: {len({r for r, mm, a, b, g in pairs if mm == m and g < 1 - TOL})}")
    gmap = {(x["id"], x["model"], x["sample"]): x["G"] for x in scores}
    strings = classes = 0
    for rid, lst in by_req.items():
        scored = [(s, f) for s, f in lst if (rid, s["model"], s["sample"]) in gmap]
        norm = {re.sub(r"\s+", "", f) for _, f in scored}
        right = {re.sub(r"\s+", "", f) for s, f in scored
                 if gmap[(rid, s["model"], s["sample"])] >= 1 - TOL}
        strings += len(norm)
        classes += (1 if right else 0) + len(norm - right)
    lines += ["", f"Distinct (scored) answer strings over all requirements: {strings}; at most "
              f"{classes} semantic classes (all answers equivalent to the reference are one class; "
              f"wrong answers counted as distinct strings)."]
    (RESULTS / "summary.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    plot(scores, reqs, models)


COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100"]


def plot(scores, reqs, models):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    neq = [s for s in scores if s["G"] < 1 - TOL]
    fig, axes = plt.subplots(1, 4, figsize=(16, 4), sharey=True)
    for ax, (name, key, tr) in zip(axes, (("1 − G", "G", lambda v: 1 - v),
                                          ("1 − VolJ", "VolJ", lambda v: 1 - v),
                                          ("PH/2D", "PH", lambda v: v), ("SD", "SD", lambda v: v))):
        for c, m in enumerate(models):
            pts = [(tr(s[key]), s["disagree"]) for s in neq if s["model"] == m and s.get(key) is not None]
            if pts:
                ax.scatter(*zip(*pts), s=14, color=COLORS[c], alpha=0.7, label=m,
                           edgecolors="white", linewidths=0.5)
        ax.set_xlabel(f"distance to reference: {name}")
        ax.grid(True, color="#e6e5e1", linewidth=0.6)
        ax.set_axisbelow(True)
        for s_ in ("top", "right"):
            ax.spines[s_].set_visible(False)
    axes[0].set_ylabel("disagreement rate on sampled signals")
    axes[0].legend(frameon=False, fontsize=8)
    fig.suptitle("Wrong LLM translations of DeepSTL requirements: each measure's distance "
                 "vs the fraction of signals on which the translation disagrees", fontsize=10)
    fig.tight_layout()
    fig.savefig(RESULTS / "rq5.png", dpi=150)


if __name__ == "__main__":
    main()
