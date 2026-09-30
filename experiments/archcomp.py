"""Fragment coverage and scoreability of the ARCH-COMP falsification requirements.

    python experiments/archcomp.py [--dt 1] [--timeout 60]

The requirements of the ARCH-COMP FALS category (AT, AFC, NN, CC, F16, SC), as
stated in the competition reports (e.g. Ernst et al., ARCH-COMP 2021/2022
Category Report: Falsification), written in TABEX's syntax with continuous
time bounds. Each row records:

* in fragment as stated -- rectangular atoms only (`|mu| < c` is the box
  -c < mu < c, so it is in; `y5 - y4 <= 40` and `|Pos - Ref| > ...` are not);
* in fragment with derived signals -- after introducing d_ij = y_i - y_j as a
  signal of its own (as RQ4 does for Slam's derivative); NN still relates two
  signals nonlinearly and stays out;
* the discretised formula at step `--dt` (bounds rounded OUTWARD: lower down,
  upper up, so a sub-step window such as F[0,0.05] becomes F[0,1]);
* its horizon T and number of signals, and whether tabex_fast scores it
  against itself and against a perturbed copy (every constant * 1.05, 0 -> 0.5) within
  the timeout / 3 GB (the RQ2 timing harness).

Output: experiments/results/archcomp.{csv,md}.
"""
import argparse
import csv
import math
import re
import sys
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from experiments.timing import timed  # noqa: E402
from similarity.reference_semantics import parse, variables  # noqa: E402

OUT = ROOT / "experiments" / "results"

AT5 = "G[0,30]((!(gear=={g}) && F[0.001,0.1](gear=={g})) -> F[0.001,0.1] G[0,2.5](gear=={g}))"
AT6 = "(G[0,30](rpm < 3000)) -> (G[0,{b}](speed < {s}))"
RISE = "((theta < 8.8) && F[0,0.05](theta > 40.0))"
FALL = "((theta > 40.0) && F[0,0.05](theta < 8.8))"

# (id, as stated, with derived signals or None if the same, derived-signal note)
REQS = [
    ("AT1", "G[0,20](speed < 120)", None),
    ("AT2", "G[0,10](rpm < 4750)", None),
    ("AT51", AT5.format(g=1), None), ("AT52", AT5.format(g=2), None),
    ("AT53", AT5.format(g=3), None), ("AT54", AT5.format(g=4), None),
    ("AT6a", AT6.format(b=4, s=35), None), ("AT6b", AT6.format(b=8, s=50), None),
    ("AT6c", AT6.format(b=20, s=65), None),
    ("AT6abc", " && ".join(f"({AT6.format(b=b, s=s)})" for b, s in ((4, 35), (8, 50), (20, 65))), None),
    ("AFC27", f"G[11,50](({RISE} || {FALL}) -> G[1,5](mu > -0.008 && mu < 0.008))", None),
    ("AFC29", "G[11,50](mu > -0.007 && mu < 0.007)", None),
    ("AFC33", "G[11,50](mu > -0.007 && mu < 0.007)", None),
    ("NN", "G[1,37](|Pos - Ref| > 0.005 + 0.03 * |Ref| -> F[0,2] G[0,1](!(0.005 + 0.03 * |Ref| <= |Pos - Ref|)))", "NN"),
    ("NNx", "F[0,1](Pos > 3.2) && F[1,1.5](G[0,0.5](Pos > 1.75 && Pos < 2.25)) && G[2,3](Pos > 1.825 && Pos < 1.875)", None),
    ("CC1", "G[0,100](y5 - y4 <= 40)", "G[0,100](d54 <= 40)"),
    ("CC2", "G[0,70] F[0,30](y5 - y4 >= 15)", "G[0,70] F[0,30](d54 >= 15)"),
    ("CC3", "G[0,80]((G[0,20](y2 - y1 <= 20)) || (F[0,20](y5 - y4 >= 40)))",
     "G[0,80]((G[0,20](d21 <= 20)) || (F[0,20](d54 >= 40)))"),
    ("CC4", "G[0,65] F[0,30] G[0,20](y5 - y4 >= 8)", "G[0,65] F[0,30] G[0,20](d54 >= 8)"),
    ("CC5", "G[0,72] F[0,8]((G[0,5](y2 - y1 >= 9)) -> (G[5,20](y5 - y4 >= 9)))",
     "G[0,72] F[0,8]((G[0,5](d21 >= 9)) -> (G[5,20](d54 >= 9)))"),
    ("CCx", " && ".join(f"G[0,50](y{i + 1} - y{i} > 7.5)" for i in range(1, 5)),
     " && ".join(f"G[0,50](d{i + 1}{i} > 7.5)" for i in range(1, 5))),
    ("F16", "G[0,15](altitude > 0)", None),
    ("SC", "G[30,35](pressure >= 87 && pressure <= 87.5)", None),
]


def discretise(formula, dt):
    def bounds(m):
        a, b = float(m.group(2)), float(m.group(3))
        return f"{m.group(1)}[{math.floor(a / dt + 1e-9)},{math.ceil(b / dt - 1e-9)}]"
    return re.sub(r"([FGU])\[\s*([\d.]+)\s*,\s*([\d.]+)\s*\]", bounds, formula)


def perturb(formula):
    def scale(m):       # * 1.05; a zero constant is moved by +0.5 instead
        c = float(m.group(2))
        return f"{m.group(1)}{c * 1.05 if c else 0.5:g}"
    return re.sub(r"(<=|>=|==|!=|<|>)\s*(-?\d+(?:\.\d+)?)", scale, formula)


def fragment(formula):
    try:
        parse(formula)
        return True, ""
    except Exception as exc:  # noqa: BLE001
        return False, str(exc).splitlines()[0][:70]


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dt", type=float, default=1.0)
    parser.add_argument("--timeout", type=float, default=60.0)
    args = parser.parse_args()
    rows = []
    for rid, stated, derived in REQS:
        ok_stated, why = fragment(discretise(stated, args.dt))
        if derived == "NN":
            cand, ok_derived = None, False
        else:
            cand = stated if derived is None else derived
            ok_derived = fragment(discretise(cand, args.dt))[0]
        row = dict(id=rid, stated=stated, in_fragment=ok_stated,
                   in_fragment_derived=ok_derived, reason="" if ok_stated else why)
        if ok_derived:
            f = discretise(cand, args.dt)
            tree = parse(f)
            row.update(discretised=f, T=tree.horizon(), n_vars=len(variables(tree)))
            for label, other in (("self", f), ("perturbed", perturb(f))):
                status, secs, value = timed("tabex_fast", f, other, args.timeout, 3 * 2**30)
                row[f"{label}_status"] = status
                row[f"{label}_seconds"] = "" if secs is None else f"{secs:.3f}"
                row[f"{label}_G"] = "" if value is None else f"{value:.4f}"
        rows.append(row)
        print(rid, {k: v for k, v in row.items() if k not in ("stated", "discretised")}, flush=True)

    fields = ["id", "in_fragment", "in_fragment_derived", "reason", "T", "n_vars",
              "self_status", "self_seconds", "self_G", "perturbed_status",
              "perturbed_seconds", "perturbed_G", "stated", "discretised"]
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "archcomp.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    lines = [f"# ARCH-COMP FALS requirements: fragment and scoreability (dt = {args.dt:g})", "",
             "| req | in fragment | with derived signals | T | signals | self (s) | "
             "vs perturbed: G (s) |", "|---|---|---|---|---|---|---|"]
    for r in rows:
        mark = lambda b: "yes" if b else "no"  # noqa: E731
        self_c = (f"{r['self_seconds']}" if r.get("self_status") == "ok"
                  else r.get("self_status", "—"))
        pert = (f"{r['perturbed_G']} ({r['perturbed_seconds']})" if r.get("perturbed_status") == "ok"
                else r.get("perturbed_status", "—"))
        lines.append(f"| {r['id']} | {mark(r['in_fragment'])} | {mark(r['in_fragment_derived'])} | "
                     f"{r.get('T', '—')} | {r.get('n_vars', '—')} | {self_c} | {pert} |")
    n = len(rows)
    lines += ["", f"In fragment as stated: {sum(r['in_fragment'] for r in rows)}/{n}; "
              f"with derived difference signals: {sum(r['in_fragment_derived'] for r in rows)}/{n}; "
              f"scored within {args.timeout:g} s: "
              f"{sum(r.get('perturbed_status') == 'ok' for r in rows)}/{n}."]
    (OUT / f"archcomp{'' if args.dt == 1 else '_dt' + str(args.dt)}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
