"""RQ2 at scale: generated (not hand-picked) pairs for G, VolJ, PH and SD.

    python experiments/random_suite.py [--equiv 1000] [--bases 300] [--workers 24]

Part 1 -- equivalence detection. Random formula + a meaning-preserving rewrite
of it (the generator and the 28 rewrite rules of verification/verify_equivalence.py),
so every pair is equivalent BY CONSTRUCTION. A measure detects the pair iff it
reports identity (G = 1, VolJ = 1, PH = 0, SD = 0; tolerance 1e-9, PH 1e-6).

Part 2 -- controlled perturbations. A random base formula (a Boolean
combination of atoms under one or two bounded temporal operators) is mutated
with a known, graded severity:

    const    one atom's constant shifted by Delta = 1, 2, 3, 4 (same direction)
    shift    the outer window [a,b] moved to [a+k, b+k],     k = 1, 2, 3
    widen    the outer window [a,b] widened to [a, b+k],     k = 1, 2, 3
    strict   one atom's strictness flipped (> <-> >=, < <-> <=)

and each measure's distance to the base (1 - G, 1 - VolJ, PH/2D, SD) is
recorded. One D for everything (D = 8 > every constant that can occur), so a
severity sequence is scored on one scale. A mutant with G = 1 is equivalent to
its base (Section 6) and is dropped. Reported per measure and family:

* blind      -- fraction of (non-equivalent) mutants scored as identical;
* monotone   -- fraction of severity sequences whose distance never decreases
                (strictly increasing is not required: ties are allowed);
* kendall    -- mean Kendall tau between severity and distance per sequence;
* strict<const1 -- fraction of bases where flipping strictness is scored as a
                smaller change than shifting a constant by 1 (it is: it moves
                a single point of the value axis).

Output: experiments/results/random_equivalence.csv, random_mutations.csv,
random_suite.md.
"""
import argparse
import csv
import random
import re
import sys
from collections import defaultdict
from fractions import Fraction
from multiprocessing import Pool
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "experiments" / "results"
D = 8
MEASURES = ["1-G", "1-VolJ", "PH/2D", "SD"]


def distances(f1, f2, D_=None):
    from madsen.metrics import d_ph, d_sd
    from similarity.reference_semantics import parse
    from similarity.stl_similarity import resolve_D
    from tabex_fast.engine import similarity
    from tabex_fast.volume import volume_jaccard

    Dv = Fraction(D_) if D_ is not None else resolve_D(None, parse(f1), parse(f2))
    Df = float(Dv)
    out = {"1-G": 1 - similarity(f1, f2, D=Dv), "1-VolJ": 1 - volume_jaccard(f1, f2, D=Dv)}
    try:
        out["PH/2D"] = d_ph(f1, f2, -Df, Df)[0] / (2 * Df)
        out["SD"] = d_sd(f1, f2, -Df, Df)
    except Exception as exc:  # noqa: BLE001  -- recorded, e.g. an unsupported predicate
        out["PH/2D"] = out["SD"] = None
        out["error"] = f"{type(exc).__name__}: {exc}"[:100]
    return out


# ---------------------------------------------------------------- part 1

def equivalence_jobs(n, seed):
    from verification.verify_equivalence import random_proposition, rewrites
    random.seed(seed)
    jobs = []
    for _ in range(n):
        first, second = random_proposition(), random_proposition()
        lower = random.randint(0, 2)
        name, rewrite = random.choice(rewrites(lower, lower + random.randint(0, 2),
                                               random.randint(0, 3)))
        original, rewritten = rewrite(first, second)
        jobs.append((name, original, rewritten))
    return jobs


def run_equivalence(job):
    name, f1, f2 = job
    return (name, f1, f2, distances(f1, f2))


# ---------------------------------------------------------------- part 2

ATOM = re.compile(r"([a-z])\s*(<=|>=|<|>)\s*(-?\d+)")
FLIP = {">": ">=", ">=": ">", "<": "<=", "<=": "<"}


def random_base(rng):
    from verification.verify_equivalence import OPS, VARS

    def atom():
        return f"{rng.choice(VARS)}{rng.choice(OPS)}{rng.randint(-3, 3)}"

    def prop(depth=0):
        if depth >= 2 or rng.random() < 0.45:
            return atom()
        return f"({prop(depth + 1)} {rng.choice(['&&', '||'])} {prop(depth + 1)})"

    a = rng.randint(0, 2)
    b = a + rng.randint(1, 3)
    op = rng.choice(["F", "G"])
    body = prop()
    if rng.random() < 0.4:   # one nested operator
        c = rng.randint(0, 1)
        body = f"{rng.choice(['F', 'G'])}[{c},{c + rng.randint(1, 2)}]({body})"
    elif rng.random() < 0.3:  # or an until
        body = f"({prop(1)}) U[0,{rng.randint(1, 2)}] ({prop(1)})"
    return op, a, b, body


def mutants(rng, base):
    op, a, b, body = base
    text = f"{op}[{a},{b}]({body})"
    atoms = list(ATOM.finditer(body))
    m = rng.choice(atoms)
    sign = rng.choice([-1, 1])

    def with_atom(new):
        return f"{op}[{a},{b}]({body[:m.start()]}{new}{body[m.end():]})"

    out = [("const", d, with_atom(f"{m.group(1)}{m.group(2)}{int(m.group(3)) + sign * d}"))
           for d in (1, 2, 3, 4)]
    out += [("shift", k, f"{op}[{a + k},{b + k}]({body})") for k in (1, 2, 3)]
    out += [("widen", k, f"{op}[{a},{b + k}]({body})") for k in (1, 2, 3)]
    out += [("strict", 0, with_atom(f"{m.group(1)}{FLIP[m.group(2)]}{m.group(3)}"))]
    return text, out


def run_mutation(job):
    base_id, base, family, severity, mutant = job
    return (base_id, base, family, severity, mutant, distances(base, mutant, D))


def kendall(xs, ys):
    from scipy.stats import kendalltau
    if len(set(ys)) == 1:
        return 0.0
    return kendalltau(xs, ys).statistic


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--equiv", type=int, default=1000)
    parser.add_argument("--bases", type=int, default=300)
    parser.add_argument("--workers", type=int, default=24)
    parser.add_argument("--seed", type=int, default=11)
    args = parser.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)

    with Pool(args.workers) as pool:
        eq = pool.map(run_equivalence, equivalence_jobs(args.equiv, args.seed), chunksize=4)
        rng = random.Random(args.seed)
        jobs = []
        for i in range(args.bases):
            base, muts = mutants(rng, random_base(rng))
            jobs += [(i, base, fam, sev, m) for fam, sev, m in muts]
        mu = pool.map(run_mutation, jobs, chunksize=4)

    with open(OUT / "random_equivalence.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["rewrite", "original", "rewritten"] + MEASURES + ["error"])
        for name, f1, f2, d in eq:
            w.writerow([name, f1, f2] + [d.get(k) for k in MEASURES] + [d.get("error", "")])
    with open(OUT / "random_mutations.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["base_id", "base", "family", "severity", "mutant"] + MEASURES + ["error"])
        for bid, base, fam, sev, m, d in mu:
            w.writerow([bid, base, fam, sev, m] + [d.get(k) for k in MEASURES] + [d.get("error", "")])

    # ---- report
    tol = {"1-G": 1e-9, "1-VolJ": 1e-9, "PH/2D": 1e-6, "SD": 1e-9}
    lines = ["# Generated suite: equivalence detection and controlled perturbations", "",
             f"## Part 1 — {len(eq)} random equivalent pairs (28 rewrite rules)", "",
             "| measure | scored identical | missed | missed pairs by rewrite (top 5) |",
             "|---|---|---|---|"]
    for k in MEASURES:
        vals = [(name, d[k]) for name, _, _, d in eq if d.get(k) is not None]
        missed = defaultdict(int)
        for name, v in vals:
            if v > tol[k]:
                missed[name] += 1
        top = ", ".join(f"{n} ({c})" for n, c in sorted(missed.items(), key=lambda x: -x[1])[:5])
        lines.append(f"| {k} | {len(vals) - sum(missed.values())}/{len(vals)} | "
                     f"{sum(missed.values())} | {top or '—'} |")

    kept = [r for r in mu if r[5]["1-G"] > 1e-9]
    n_equiv = len(mu) - len(kept)
    lines += ["", f"## Part 2 — {args.bases} random bases × 11 mutants, D = {D}", "",
              f"{len(mu)} mutants, {n_equiv} equivalent to their base (G = 1) and dropped.", "",
              "| measure | family | blind (scored identical) | monotone sequences | mean Kendall τ |",
              "|---|---|---|---|---|"]
    seqs = defaultdict(list)
    for bid, base, fam, sev, m, d in kept:
        seqs[(bid, fam)].append((sev, d))
    for k in MEASURES:
        for fam in ("const", "shift", "widen", "strict"):
            rows = [d[k] for _, _, f, _, _, d in kept if f == fam and d.get(k) is not None]
            blind = sum(v <= tol[k] for v in rows)
            if fam == "strict":
                lines.append(f"| {k} | {fam} | {blind}/{len(rows)} | — | — |")
                continue
            mono, taus = 0, []
            for (bid, f), pts in seqs.items():
                if f != fam or len(pts) < 2 or any(d.get(k) is None for _, d in pts):
                    continue
                pts.sort(key=lambda p: p[0])
                ys = [d[k] for _, d in pts]
                mono += all(y2 >= y1 - 1e-12 for y1, y2 in zip(ys, ys[1:]))
                taus.append(kendall([p[0] for p in pts], ys))
            lines.append(f"| {k} | {fam} | {blind}/{len(rows)} | {mono}/{len(taus)} | "
                         f"{sum(taus) / len(taus):.3f} |")
    lines += ["", "Strictness flip scored as a smaller change than a constant shift by 1:", ""]
    by_base = defaultdict(dict)
    for bid, base, fam, sev, m, d in kept:
        if fam == "strict" or (fam == "const" and sev == 1):
            by_base[bid][fam] = d
    for k in MEASURES:
        pairs = [(v["strict"][k], v["const"][k]) for v in by_base.values()
                 if "strict" in v and "const" in v and v["strict"].get(k) is not None]
        smaller = sum(s < c for s, c in pairs)
        lines.append(f"- {k}: {smaller}/{len(pairs)}")
    errors = [r for r in mu if r[5].get("error")] + [r for r in eq if r[3].get("error")]
    lines += ["", f"PH/SD errors (excluded): {len(errors)}"]
    (OUT / "random_suite.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
