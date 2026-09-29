"""Draw a three-axis signal space as voxels.

A formula over `|V| x (H+1) = 3` axes has its region in `R^3`, so it can be
shown as one solid rather than as one 1-D panel per instant, which is all
`plot_signal_space.py` can do. Left panel: the region truncated to `[-D,D]^3`.
Right panel: the same cells shaded by how many boxes of the decomposition
cover them -- the overlap that makes a decomposition a cover and not a
partition.
"""
import argparse

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from reference_semantics import parse, signal_space, variables
from similarity.stl_similarity import resolve_D
from verify_semantics import contains

COVER_COLORS = ["#4c78a8", "#f58518", "#d62728"]   # covered by 1, 2, 3+ boxes


def grid(paths, axes, D):
    """Cut points per axis: the finite breakpoints inside (-D,D), plus +-D.

    Sampling each cell at its midpoint is exact, not an approximation: every
    box endpoint is a cut point, so by Lemma 7 (FORMAL_PROOFS.md) a box either
    contains a whole cell or misses it entirely.
    """
    cuts = {}
    for a in axes:
        finite = {float(iv.l) for p in paths for iv in p.timeline[a[0]][a[1]]
                  if abs(float(iv.l)) < D}
        finite |= {float(iv.r) for p in paths for iv in p.timeline[a[0]][a[1]]
                   if abs(float(iv.r)) < D}
        cuts[a] = np.array(sorted({-D, D} | finite))
    return cuts


def coverage(paths, axes, cuts):
    """Per cell, how many boxes of the decomposition contain it."""
    mids = [(c[:-1] + c[1:]) / 2 for c in (cuts[a] for a in axes)]
    counts = np.zeros([len(m) for m in mids], dtype=int)
    for i, x in enumerate(mids[0]):
        for j, y in enumerate(mids[1]):
            for k, z in enumerate(mids[2]):
                for path in paths:
                    if all(any(contains(iv, v) for iv in path.timeline[t][var])
                           for (t, var), v in zip(axes, (x, y, z))):
                        counts[i, j, k] += 1
    return counts


def explode(cuts, counts, gap):
    """Pull the cells apart so the interior is visible, sizes kept to scale."""
    grids = [np.array([v for i in range(len(c) - 1)
                       for v in (c[i] + i * gap, c[i + 1] + i * gap)])
             for c in cuts]
    blown = np.zeros([2 * n - 1 for n in counts.shape], dtype=counts.dtype)
    blown[::2, ::2, ::2] = counts
    return grids, blown


def _panel(ax, cuts, axes, counts, colorof, title, gap=0.0):
    grids = [cuts[a] for a in axes]
    if gap:
        grids, counts = explode(grids, counts, gap)
    mesh = np.meshgrid(*grids, indexing="ij")
    ax.voxels(*mesh, counts > 0, facecolors=colorof(counts), edgecolor="0.25",
              linewidth=0.35)
    ax.set_xlabel(f"{axes[0][1]}({axes[0][0]})")
    ax.set_ylabel(f"{axes[1][1]}({axes[1][0]})")
    ax.set_zlabel(f"{axes[2][1]}({axes[2][0]})")
    if gap:                      # exploded coords are shifted: ticks would lie
        ax.set_xticklabels([]); ax.set_yticklabels([]); ax.set_zticklabels([])
    ax.set_title(title, fontsize=10)
    ax.view_init(elev=22, azim=-58)


def plot(formula, out, D=None):
    tree = parse(formula)
    paths = signal_space(tree, sorted(variables(tree)))
    axes = sorted((t, v) for t in paths[0].timeline for v in paths[0].timeline[t])
    if len(axes) != 3:
        raise SystemExit(
            f"{formula!r} has {len(axes)} axes ({'; '.join(f'{v}({t})' for t, v in axes)}); "
            "a 3-D plot needs exactly 3, i.e. |V| * (horizon+1) == 3.")
    D = float(resolve_D(D, tree, tree))
    cuts = grid(paths, axes, D)
    counts = coverage(paths, axes, cuts)

    def solid(c):
        return np.where((c > 0)[..., None], np.array([0.30, 0.47, 0.66, 1.0]),
                        np.zeros(4))

    def graded(c):
        out = np.zeros(c.shape + (4,))
        for n in range(1, c.max() + 1):
            out[c == n] = matplotlib.colors.to_rgba(COVER_COLORS[min(n, 3) - 1])
        return out

    fig = plt.figure(figsize=(13, 6))
    left = fig.add_subplot(121, projection="3d")
    right = fig.add_subplot(122, projection="3d")
    _panel(left, cuts, axes, counts, solid,
           f"$R$ for {formula}\ntruncated to $[-{D:g},{D:g}]^3$"
           f"  ({len(paths)} boxes)")
    _panel(right, cuts, axes, counts, graded,
           "exploded, shaded by how many boxes cover",
           gap=0.42 * (2 * D) / len(cuts[axes[0]]))
    right.legend(handles=[
        plt.Line2D([], [], marker="s", ls="", markersize=10,
                   color=COVER_COLORS[n - 1], label=f"{n} box" + "es" * (n > 1))
        for n in range(1, counts.max() + 1)], loc="upper left", fontsize=9)
    fig.subplots_adjust(left=0.02, right=0.98, wspace=0.05)
    fig.savefig(out, dpi=160)
    print(f"{out}  ({len(paths)} boxes, D={D:g}, "
          f"cells by coverage: "
          f"{ {n: int((counts == n).sum()) for n in range(counts.max() + 1)} })")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("formula", nargs="?", default="F[0,2](x>1 && x<5)")
    ap.add_argument("-o", "--out", default="figures/example-3d/region_3d.png")
    ap.add_argument("-D", type=float, default=None)
    args = ap.parse_args()
    plot(args.formula, args.out, args.D)
