"""Draw two formulas' signal spaces, one panel per time instant.

Each row of a panel is one element of the signal space (a raw path from
`reference_semantics.signal_space`, or a canonical cell with `--canonical`);
each bar is the interval that element allows for a variable at that instant.
Grey bar = unconstrained, blank = the cell does not reach that instant.
Open circle = open endpoint. Everything is clamped to the metric's window
[-D, D], so a bar running to the panel edge with no endpoint marker is
unbounded.
"""
import argparse
import textwrap
from fractions import Fraction

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

from reference_semantics import parse
from similarity.stl_similarity import (
    build_aligned_volumes,
    calc_similarity_from_formulas,
    is_undefined,
    resolve_D,
    signal_spaces_from_definition,
)


def _draw(ax, paths, t, var, D, color):
    for i, path in enumerate(paths):
        pieces = path.timeline.get(t, {}).get(var)
        if pieces is None:
            continue                                  # cell trimmed before t
        if is_undefined(pieces):
            ax.hlines(i, -D, D, color="0.85", lw=5, zorder=1)
            continue
        for iv in pieces:
            lo, hi = max(float(iv.l), -D), min(float(iv.r), D)
            ax.hlines(i, lo, hi, color=color, lw=5, zorder=2)
            for x, open_end, finite in ((lo, iv.lo, iv.l != float("-inf")),
                                        (hi, iv.ro, iv.r != float("inf"))):
                if finite:
                    ax.plot(x, i, "o", ms=5, color=color, zorder=3,
                            markerfacecolor="white" if open_end else color)


def plot(formula1, formula2, out, canonical=False, D=None):
    paths1, paths2, all_vars = signal_spaces_from_definition(formula1, formula2)
    D = float(resolve_D(D, parse(formula1), parse(formula2)))
    if canonical:
        volume1, volume2 = build_aligned_volumes(formula1, paths1, formula2,
                                                 paths2, all_vars=all_vars)
        paths1, paths2 = volume1.volume, volume2.volume

    instants = sorted({t for p in paths1 + paths2 for t in p.timeline})
    ticks = sorted({float(iv.l) for p in paths1 + paths2 for slot in p.timeline.values()
                    for pieces in slot.values() for iv in pieces
                    if abs(float(iv.l)) <= D}
                   | {float(iv.r) for p in paths1 + paths2 for slot in p.timeline.values()
                      for pieces in slot.values() for iv in pieces
                      if abs(float(iv.r)) <= D})
    panels = [("\u03c6", paths1, "tab:blue"), ("\u03b8", paths2, "tab:red")]
    # One row per (formula, variable); the formula's own label is drawn once
    # per group, on its first row, or it repeats for every variable.
    rows = [(f, ps, c, v, k == 0)
            for f, ps, c in panels for k, v in enumerate(all_vars)]

    # Width has to hold the suptitle too: one instant gives a narrow figure and
    # a long formula would run off both edges of it.
    title = f"\u03c6 = {formula1}\n\u03b8 = {formula2}"
    title = "\n".join(line for para in title.split("\n")
                      for line in textwrap.wrap(para, 78) or [para])
    fig_w = max(3.2 * len(instants),
                0.075 * max(len(line) for line in title.split("\n")))
    fig, axes = plt.subplots(len(rows), len(instants), squeeze=False,
                             sharex=True, figsize=(fig_w,
                                                   1 + 0.32 * sum(len(p) for _, p, _, _, _ in rows)))
    for row, (formula, paths, color, var, first_of_group) in enumerate(rows):
        for col, t in enumerate(instants):
            ax = axes[row][col]
            _draw(ax, paths, t, var, D, color)
            ax.set_xlim(-D, D)
            ax.set_ylim(len(paths) - 0.5, -0.5)
            ax.grid(axis="x", ls=":", lw=0.5, color="0.8")
            if row == 0:
                ax.set_title(f"t = {t}")
            ax.set_xticks(ticks)
            if col == 0:
                ax.set_ylabel(var)
                ax.set_yticks(range(len(paths)))
                ax.tick_params(labelsize=6)
            else:
                ax.set_yticks([])
            if col == len(instants) - 1 and first_of_group:
                right = ax.twinx()
                right.set_yticks([])
                right.set_ylabel(formula, fontsize=13, color=color, rotation=0,
                                 labelpad=10, va="center")

    kind = "canonical cells" if canonical else "raw paths"
    score = calc_similarity_from_formulas(formula1, formula2, D=Fraction(D))
    fig.suptitle(f"{title}\n"
                 f"signal space ({kind}), D = {D:g}, similarity = {score:.4f}",
                 fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    print(f"wrote {out}  ({len(paths1)} vs {len(paths2)} {kind})")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("formula1")
    p.add_argument("formula2")
    p.add_argument("-o", "--out", default="signal_space.png")
    p.add_argument("--canonical", action="store_true",
                   help="Plot the canonical cells the metric actually compares.")
    p.add_argument("--D", type=Fraction, default=None)
    a = p.parse_args()
    plot(a.formula1, a.formula2, a.out, canonical=a.canonical, D=a.D)
