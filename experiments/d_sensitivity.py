"""RQ3: sensitivity of the metric to the domain parameter D.

    python experiments/d_sensitivity.py

Pairs, each scored over D log-spaced from just above Definition 2's bound
(max|constant|) to 10^4:

* offset family -- one-sided constraints differing only in their constant, by
  Delta, in both directions (`x>2` vs `x>2+Delta`, `x<-2` vs `x<-2-Delta`);
* an endpoint-only pair (`x>=2` vs `x>2`, Delta = 0: only the eps term differs);
* controls: bounded vs bounded (D-independent once D exceeds both) and bounded
  vs unbounded (the unbounded side's mass grows with D, so the score falls);
* temporal versions, scored by the full G (tabex_fast): G, F and U over [0,2].

For the offset family Point_sim_D has a closed form -- with c1 < c2 and both
strict, meet = (c2, D], union = (c1, D] which contains the endpoint c2:

    Point_sim_D = (D - c2) / (D - c1 + eps)

checked against the computed value at every D. Contrasted with the fixed,
D-free decay of the earlier draft's Eq. 4, 1/(1 + dist), dist the gap between
the finite endpoints (bounded side: its midpoint).

Output: experiments/results/d_sensitivity.csv and d_sensitivity.png.
"""
import csv
import sys
from fractions import Fraction
from pathlib import Path as FilePath

ROOT = FilePath(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from similarity.intervals import Interval  # noqa: E402
from similarity.reference_semantics import atom_intervals, parse  # noqa: E402
from similarity.stl_similarity import EPS, point_sim_d, resolve_D  # noqa: E402
from tabex_fast.engine import similarity  # noqa: E402

OUT = ROOT / "experiments" / "results"
INF = float("inf")

OFFSETS = [Fraction(1, 2), Fraction(1), Fraction(3), Fraction(10)]
POINT_PAIRS = (
    [(f"x>2 vs x>{2 + d}", "offset >", d, "x>2", f"x>{2 + d}") for d in OFFSETS]
    + [(f"x<-2 vs x<{-2 - d}", "offset <", d, "x<-2", f"x<{-2 - d}") for d in OFFSETS]
    + [("x>=2 vs x>2", "endpoint", Fraction(0), "x>=2", "x>2"),
       ("[2,5] vs [2,8]", "bounded/bounded", None, "x>2 && x<5", "x>2 && x<8"),
       ("[2,5] vs x>2", "bounded/unbounded", None, "x>2 && x<5", "x>2")]
)
TEMPORAL_PAIRS = [
    ("G[0,2](x>2) vs G[0,2](x>5)", "G[0,2](x>2)", "G[0,2](x>5)"),
    ("F[0,2](x>2) vs F[0,2](x>5)", "F[0,2](x>2)", "F[0,2](x>5)"),
    ("(x>2) U[0,2] (y>0) vs (x>5) U[0,2] (y>0)", "(x>2) U[0,2] (y>0)", "(x>5) U[0,2] (y>0)"),
    ("G[0,2](x>2 && x<5) vs G[0,2](x>2)", "G[0,2](x>2 && x<5)", "G[0,2](x>2)"),
]


def d_grid(bound, n=41):
    """bound + 10^k, k from -2 to log10(10^4 - bound), as exact rationals."""
    import math
    top = math.log10(10**4 - bound)
    return [bound + Fraction(10 ** (-2 + (top + 2) * i / (n - 1))).limit_denominator(10**6)
            for i in range(n)]


def pieces(formula):
    """The allowed set of an atom or a conjunction of atoms on one variable."""
    tree = parse(formula)
    atoms = [tree] if not hasattr(tree, "left") else [tree.left, tree.right]
    out = [Interval(-INF, INF)]
    for a in atoms:
        out = [m for iv in out for c in atom_intervals(a.op, a.constant)
               if (m := iv.intersect(c)) is not None]
    return out


def endpoint(p):
    iv = p[0]
    if iv.l != -INF and iv.r != INF:
        return (iv.l + iv.r) / 2
    return iv.l if iv.l != -INF else iv.r


def eq4(f1, f2):
    """Earlier draft's Eq. 4: 1/(1 + dist), for pairs with an unbounded side."""
    p1, p2 = pieces(f1), pieces(f2)
    bounded = lambda p: p[0].l != -INF and p[0].r != INF  # noqa: E731
    if bounded(p1) and bounded(p2):
        return None    # that draft used the Jaccard index there, D-free as well
    return float(1 / (1 + abs(endpoint(p1) - endpoint(p2))))


def closed_form(f1, f2, D):
    p1, p2 = pieces(f1)[0], pieces(f2)[0]
    if p1.r == INF:     # x > c1 vs x > c2, c1 < c2
        c1, c2 = p1.l, p2.l
        return float((D - c2) / (D - c1 + EPS))
    c1, c2 = -p1.r, -p2.r   # x < -c1 vs x < -c2, mirrored
    return float((D - c2) / (D - c1 + EPS))


def run():
    rows = []
    for label, kind, delta, f1, f2 in POINT_PAIRS:
        bound = resolve_D(None, parse(f1), parse(f2)) - 1
        e4 = eq4(f1, f2)
        for D in d_grid(bound):
            p = point_sim_d(pieces(f1), pieces(f2), D)
            g = similarity(f1, f2, D=D)
            assert abs(p - g) < 1e-12, (label, D, p, g)   # one instant, one variable: G = Point_sim
            cf = closed_form(f1, f2, D) if kind.startswith("offset") else ""
            if cf != "":
                assert abs(cf - p) < 1e-12, (label, D, cf, p)
            rows.append((label, kind, "" if delta is None else float(delta), float(bound),
                         float(D), p, cf, "" if e4 is None else e4))
    for label, f1, f2 in TEMPORAL_PAIRS:
        bound = resolve_D(None, parse(f1), parse(f2)) - 1
        for D in d_grid(bound, n=21):
            rows.append((label, "temporal", "", float(bound), float(D),
                         similarity(f1, f2, D=D), "", ""))
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "d_sensitivity.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["pair", "kind", "delta", "bound", "D", "score", "closed_form", "eq4"])
        writer.writerows(rows)
    return rows


COLORS = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]


def plot(rows):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    def series(label):
        pts = [(r[4], r[5]) for r in rows if r[0] == label]
        return [p[0] for p in pts], [p[1] for p in pts]

    fig, axes = plt.subplots(1, 3, figsize=(18, 4.6))
    style = lambda ax: ([ax.spines[s].set_visible(False) for s in ("top", "right")],  # noqa: E731
                        ax.grid(True, color="#e6e5e1", linewidth=0.6), ax.set_axisbelow(True))

    ax = axes[0]
    for k, d in enumerate(OFFSETS):
        label = f"x>2 vs x>{2 + d}"
        ax.plot(*series(label), color=COLORS[k], linewidth=2, label=f"Δ = {float(d):g}")
        ax.plot(*series(f"x<-2 vs x<{-2 - d}"), color=COLORS[k], linewidth=0, marker="o",
                markersize=3)
        e4 = next(r[7] for r in rows if r[0] == label)
        ax.axhline(e4, color=COLORS[k], linewidth=1, linestyle="--")
    ax.set_xscale("log")
    ax.set_xlabel("D")
    ax.set_ylabel("Point_sim_D  (= G)")
    ax.set_title("offset family: x>2 vs x>2+Δ (lines), x<-2 vs x<-2-Δ (dots)\n"
                 "dashed: Eq. 4, 1/(1+Δ), D-free", fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    style(ax)

    ax = axes[1]
    for k, d in enumerate(OFFSETS):
        xs, ys = series(f"x>2 vs x>{2 + d}")
        ax.plot([(D - 2) / float(d) for D in xs], ys, color=COLORS[k], linewidth=2,
                label=f"Δ = {float(d):g}")
    u = [10 ** (i / 20) for i in range(0, 101)]
    ax.plot(u, [1 - 1 / x for x in u], color="#0b0b0b", linewidth=1, linestyle=":",
            label="1 − Δ/(D−c₁)")
    ax.set_xscale("log")
    ax.set_xlim(1, 2e4)
    ax.set_ylim(0, 1.02)
    ax.set_xlabel("(D − c₁) / Δ")
    ax.set_title("same curves, rescaled: they collapse onto 1 − Δ/(D − c₁)", fontsize=9)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    style(ax)

    ax = axes[2]
    others = ["x>=2 vs x>2", "[2,5] vs [2,8]", "[2,5] vs x>2"] + [t[0] for t in TEMPORAL_PAIRS]
    for k, label in enumerate(others):
        ax.plot(*series(label), color=COLORS[k], linewidth=2, label=label)
    ax.set_xscale("log")
    ax.set_xlabel("D")
    ax.set_ylabel("G")
    ax.set_title("controls and temporal pairs (full G, tabex_fast)", fontsize=9)
    ax.legend(frameon=False, fontsize=7, loc="upper left", bbox_to_anchor=(1.01, 1))
    style(ax)

    fig.tight_layout()
    fig.savefig(OUT / "d_sensitivity.png", dpi=150)


if __name__ == "__main__":
    rows = run()
    plot(rows)
    for label in dict.fromkeys(r[0] for r in rows):
        pts = [r for r in rows if r[0] == label]
        pick = [pts[0], pts[len(pts) // 2], pts[-1]]
        print(f"{label:45} " + "  ".join(f"D={r[4]:<9.4g} {r[5]:.4f}" for r in pick)
              + (f"   eq4={pts[0][7]:.4f}" if pts[0][7] != "" else ""))
