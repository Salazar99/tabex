"""Visualise the whole similarity pipeline, stage by stage.

    parse -> evaluate  ->  canonicalize            ->  metric
    (AST)    (raw boxes)   (breakpoints/fine/coarse)   (Point_sim/Path_sim/G)

Writes one PNG per stage into --out-dir and prints the matching numeric trace,
so every picture can be checked against the numbers that produced it. The trace
is the source of every number in EXAMPLE.md.

Handles any number of variables: a cell's axes are the whole
`{instants} x {variables}` grid, and each figure shows all of them.
"""
import argparse
import itertools
import textwrap
from fractions import Fraction

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import pydot

from reference_semantics import (
    And, Always, Atom, Constant, Eventually, Or, Until, evaluate, intersect, parse,
)
from similarity.canon import _axis_partition, _breakpoints, _fine_cells, canonicalize, cell_key
from similarity.stl_similarity import (
    build_aligned_volumes,
    intersect_pieces,
    is_undefined,
    measure,
    path_similarity,
    point_sim_d,
    resolve_D,
    signal_spaces_from_definition,
    truncate,
    union_pieces,
)
from plot_signal_space import _draw, plot

PHI, THETA = "φ", "θ"


def _label(cell, all_vars):
    """A cell as its whole axis list, `t0: x=.. y=.. | t1: ...`."""
    return " | ".join(
        f"t{t}: " + " ".join(f"{var}{cell.timeline[t][var][0]}" for var in all_vars)
        for t in sorted(cell.timeline))


def _sorted_cells(cells):
    return sorted(cells, key=cell_key)


def _axes_of(paths, all_vars):
    return [(t, var) for t in sorted({t for p in paths for t in p.timeline}) for var in all_vars]


# --------------------------------------------------------------------------
# Stage 0: the formula string as an evaluation tree
# --------------------------------------------------------------------------

def _fmt_region(region):
    """A box list, spelled out when it is small enough to read."""
    if not region:
        return "∅ (empty)"
    if len(region) > 2 or any(len(box) > 3 for box in region):
        return f"{len(region)} boxes"
    return "  ∨  ".join(
        " ∧ ".join(f"{var}@t{t}∈{iv}" for (t, var), iv in sorted(box.items())) or "⊤"
        for box in region)


def ast_figure(name, formula, out, color="lightblue"):
    """The NNF tree, unrolled over instants, each node showing its region.

    This is `evaluate()` drawn: a temporal node fans out one child per offset in
    its window, exactly as the recursion does, so the picture has one node per
    recursive call rather than one per syntactic operator.
    """
    tree = parse(formula)
    graph = pydot.Dot(graph_type="digraph", rankdir="TB", fontname="helvetica")
    ids = itertools.count()

    def add(node, t, parent=None, edge_label=""):
        nid = f"n{next(ids)}"
        region = evaluate(node, t)
        if isinstance(node, Atom):
            head, shape = f"{node.variable}{node.op}{node.constant}", "ellipse"
        elif isinstance(node, Constant):
            head, shape = str(node), "ellipse"
        elif isinstance(node, And):
            head, shape = "&&   (intersect)", "box"
        elif isinstance(node, Or):
            head, shape = "||   (union)", "box"
        elif isinstance(node, Eventually):
            head, shape = f"F[{node.lower},{node.upper}]   (union over u)", "box"
        elif isinstance(node, Always):
            head, shape = f"G[{node.lower},{node.upper}]   (intersect over u)", "box"
        else:
            head, shape = f"U[{node.lower},{node.upper}]   (union over witness u)", "box"
        graph.add_node(pydot.Node(
            nid, shape=shape, style="filled", fillcolor=color, fontname="helvetica",
            fontsize="10", label=f"{head}\\n@ t={t}\\n{_fmt_region(region)}"))
        if parent is not None:
            graph.add_edge(pydot.Edge(parent, nid, label=edge_label,
                                      fontname="helvetica", fontsize="8"))

        if isinstance(node, (And, Or)):
            add(node.left, t, nid)
            add(node.right, t, nid)
        elif isinstance(node, (Eventually, Always)):
            for offset in range(node.lower, node.upper + 1):
                add(node.body, t + offset, nid, f"u={offset}")
        elif isinstance(node, Until):
            for offset in range(node.lower, node.upper + 1):
                # One disjunct per witness instant: the witness there, and the
                # invariant at every moment of the CLOSED range [t, t+offset].
                term = evaluate(node.witness, t + offset)
                for moment in range(t, t + offset + 1):
                    term = intersect(term, evaluate(node.invariant, moment))
                mid = f"n{next(ids)}"
                graph.add_node(pydot.Node(
                    # ponytail: style="dashed" not "filled,dashed" -- pydot 1.4.2
                    # emits a multi-value style unquoted and dot rejects it.
                    mid, shape="box", style="dashed",
                    fontname="helvetica", fontsize="9",
                    label=f"u={offset}: witness @ t={t + offset}\\n"
                          f"∧ invariant @ t={t}..{t + offset}\\n{_fmt_region(term)}"))
                graph.add_edge(pydot.Edge(nid, mid, label=f"u={offset}",
                                          fontname="helvetica", fontsize="8"))
                add(node.witness, t + offset, mid, "witness")
                for moment in range(t, t + offset + 1):
                    add(node.invariant, moment, mid, "invariant")
        return nid

    add(tree, 0)
    out.write_bytes(graph.create_png())
    return sum(1 for _ in graph.get_nodes())


# --------------------------------------------------------------------------
# Stages 1-3: the region, before and after canonicalisation
# --------------------------------------------------------------------------

def canon_figure(name, formula, paths, all_vars, D, color, out):
    """Raw boxes -> fine arrangement -> canonical cells, one column per axis."""
    breakpoints = _breakpoints(paths)
    fine = _sorted_cells(_fine_cells(paths, breakpoints))
    canon = _sorted_cells(canonicalize(paths))
    stages = [(f"(1) raw boxes: P({name}), {len(paths)} paths", paths),
              (f"(2) fine arrangement: cut at B, {len(fine)} cells", fine),
              (f"(3) canonical cells: coarsen, {len(canon)} cells", canon)]
    axes_list = _axes_of(paths, all_vars)

    partitions = {axis: _axis_partition(fine, axis) for axis in breakpoints}

    def column_title(t, var):
        # B and the partition belong next to the axis they describe, not in a
        # shared caption that would collide with four columns of titles.
        head = f"axis (t={t}, {var})"
        if (t, var) not in breakpoints:
            return head + "\nunconstrained"
        return (head
                + f"\nB = {{{', '.join(str(b) for b in sorted(breakpoints[(t, var)]))}}}"
                + "\npartition: " + ", ".join(str(iv) for iv in partitions[(t, var)]))

    # Column width follows the widest title line: a long axis partition
    # ("(-inf, 0], (0, 2), [2, 4], (4, 6), [6, inf)") is wider than a default
    # column and would overrun its neighbour.
    titles = [column_title(t, var) for t, var in axes_list]
    widest = max(len(line) for title in titles for line in title.split("\n"))
    col_w = max(2.6, 0.065 * widest)

    heights = [max(len(cells), 3) for _, cells in stages]
    # No sharex: each axis carries its own breakpoints, and a shared x axis
    # would show only the last column's ticks.
    # Wrap the header and let it set a width floor: a long formula over two
    # narrow columns would otherwise run off both edges of the figure.
    header = "\n".join(line for line in textwrap.wrap(
        f"canonicalisation of {name} = {formula}", 76))
    head_in = 0.55 + 0.22 * len(header.split("\n"))
    plot_in = 0.17 * sum(heights)
    fig_h = head_in + 0.55 + plot_in
    # hspace is a fraction of the MEAN row height, so a formula with few cells
    # per stage gets a tiny absolute gap and its stage caption lands on the row
    # above's tick labels. Solve for a constant ~0.55in gap instead.
    hspace = min(1.5, 0.55 / (plot_in / len(stages)))
    fig, axes = plt.subplots(len(stages), len(axes_list), squeeze=False,
                             gridspec_kw={"height_ratios": heights, "hspace": hspace},
                             figsize=(max(col_w * len(axes_list),
                                          0.085 * max(len(l) for l in header.split("\n"))),
                                      fig_h))
    for row, (title, cells) in enumerate(stages):
        for col, (t, var) in enumerate(axes_list):
            ax = axes[row][col]
            for b in sorted(breakpoints.get((t, var), ())):
                ax.axvline(float(b), color="0.6", ls="--", lw=0.7, zorder=0)
            _draw(ax, cells, t, var, D, color)
            ax.set_xlim(-D, D)
            ax.set_ylim(len(cells) - 0.5, -0.5)
            ax.set_yticks([])
            ax.set_xticks(sorted(float(b) for b in breakpoints.get((t, var), ())))
            if row == 0:
                # pad clears the stage caption drawn just below at y=1.02
                ax.set_title(titles[col], fontsize=8, pad=16)
        axes[row][0].text(0.0, 1.02, title, transform=axes[row][0].transAxes,
                          fontsize=8, va="bottom", ha="left", color=color)

    fig.suptitle(header, fontsize=10)
    fig.tight_layout(h_pad=1.8)
    fig.subplots_adjust(top=1 - head_in / fig_h, hspace=hspace)
    fig.savefig(out, dpi=150)
    return breakpoints, fine, canon, partitions


# --------------------------------------------------------------------------
# Stage 1-2: the paths themselves, one colour each
# --------------------------------------------------------------------------

def paths_figure(formula1, paths1, formula2, paths2, all_vars, D, out):
    """One row per raw path, its own colour, every axis side by side.

    The region figure draws all of a formula's paths in one colour, so the eye
    cannot follow a single path across instants. Here each path is a colour and
    a labelled row: reading across tells you exactly which axes that path
    constrains and which it leaves free -- which is what distinguishes one
    disjunct, or one witness instant, from another.
    """
    axes_list = _axes_of(paths1 + paths2, all_vars)
    # One running palette across BOTH formulas, so no two paths anywhere in the
    # figure share a colour. The row labels already say which formula is which.
    cmap = plt.get_cmap("tab10")
    rows = [(f"{name}{i}", path)
            for name, paths in (("\u03c6", paths1), ("\u03b8", paths2))
            for i, path in enumerate(paths)]
    rows = [(label, path, cmap(k % 10)) for k, (label, path) in enumerate(rows)]

    header = "\n".join(
        line for para in ("one row per raw path, one colour each "
                          "(grey = unconstrained on that axis)",
                          f"\u03c6 = {formula1}   \u2014   {len(paths1)} paths",
                          f"\u03b8 = {formula2}   \u2014   {len(paths2)} paths")
        for line in textwrap.wrap(para, 92) or [para])
    head_in = 0.28 + 0.20 * len(header.split("\n"))
    fig_h = head_in + 0.55 + 0.62 * len(rows)
    # Reserve the left gutter explicitly. tight_layout under-measures a
    # multi-line rotation=0 ylabel and clips it, whatever labelpad says.
    notes = [("constrains every axis" if all(not is_undefined(path.timeline[t][v])
                                             for t, v in axes_list)
              else "free on " + ", ".join(f"(t{t},{v})" for t, v in axes_list
                                          if is_undefined(path.timeline[t][v])))
             for _, path, _ in rows]
    gutter = 0.18 + 0.062 * max(len(n) for n in notes)
    fig_w = gutter + 2.3 * len(axes_list) + 0.4
    fig, axes = plt.subplots(len(rows), len(axes_list), squeeze=False, sharex="col",
                             gridspec_kw={"hspace": 0.55}, figsize=(fig_w, fig_h))
    for row, (label, path, color) in enumerate(rows):
        for col, (t, var) in enumerate(axes_list):
            ax = axes[row][col]
            _draw(ax, [path], t, var, D, color)
            ax.set_xlim(-D, D)
            ax.set_ylim(0.6, -0.6)
            ax.set_yticks([])
            ax.grid(axis="x", ls=":", lw=0.5, color="0.85")
            if row == 0:
                ax.set_title(f"axis (t={t}, {var})", fontsize=9)
        axes[row][0].set_ylabel(f"{label}\n{notes[row]}", fontsize=8.5, color=color,
                                rotation=0, labelpad=6, va="center", ha="right")

    fig.suptitle(header, fontsize=8.5)
    fig.tight_layout()
    fig.subplots_adjust(left=gutter / fig_w, right=0.98,
                        top=1 - head_in / fig_h)
    fig.savefig(out, dpi=150)


# --------------------------------------------------------------------------
# Stage 1-3, two-variable case: the region in the plane
# --------------------------------------------------------------------------

def plane_figure(formula1, cells1, formula2, cells2, all_vars, D, out, kind):
    """Both regions as rectangles in the x-y plane, one panel per instant.

    Only meaningful for exactly two variables, and it is the only view that
    shows the SHAPE: two independent per-axis projections of an L-shaped region
    are indistinguishable from projections of the full rectangle, so the bar
    figures cannot show what canonicalisation is doing here.
    """
    xvar, yvar = all_vars
    instants = sorted({t for c in cells1 + cells2 for t in c.timeline})
    panels = [("\u03c6", formula1, cells1, "tab:blue"), ("\u03b8", formula2, cells2, "tab:red")]
    fig, axes = plt.subplots(len(panels), len(instants), squeeze=False,
                             figsize=(max(3.0 * len(instants) + 1.0, 6.6),
                                      3.2 * len(panels)))
    # A finite frame: clamp to the data, not to D, or a single unbounded slab
    # would flatten every real box against one edge.
    edges = [float(v) for c in cells1 + cells2 for slot in c.timeline.values()
             for pieces in slot.values() for iv in pieces
             for v in (iv.l, iv.r) if abs(float(v)) != float("inf")]
    lo, hi = (min(edges), max(edges)) if edges else (-1.0, 1.0)
    pad = max(0.25, 0.15 * (hi - lo))
    lo, hi = max(lo - pad, -D), min(hi + pad, D)

    for row, (name, formula, cells, color) in enumerate(panels):
        for col, t in enumerate(instants):
            ax = axes[row][col]
            for i, cell in enumerate(cells):
                slot = cell.timeline.get(t)
                if slot is None:
                    continue
                xs, ys = slot[xvar][0], slot[yvar][0]
                x0, x1 = max(float(xs.l), lo), min(float(xs.r), hi)
                y0, y1 = max(float(ys.l), lo), min(float(ys.r), hi)
                ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, facecolor=color,
                                       edgecolor="white", lw=1.5, alpha=0.55))
                ax.text((x0 + x1) / 2, (y0 + y1) / 2, str(i), ha="center",
                        va="center", fontsize=9, color="black")
            ax.set_xlim(lo, hi)
            ax.set_ylim(lo, hi)
            ax.set_aspect("equal")
            ax.grid(ls=":", lw=0.5, color="0.8")
            ax.set_xlabel(xvar)
            if col == 0:
                ax.set_ylabel(f"{name}\n{yvar}", color=color)
            ax.set_title(f"t = {t}   ({len(cells)} {kind})", fontsize=9)
    header = "\n".join(
        line for para in (f"the region in the {xvar}-{yvar} plane, {kind}",
                          f"\u03c6 = {formula1}", f"\u03b8 = {formula2}")
        for line in textwrap.wrap(para, 84) or [para])
    fig.suptitle(header, fontsize=8)
    fig.tight_layout()
    fig.savefig(out, dpi=150)


# --------------------------------------------------------------------------
# Stage 4: Point_sim on one cell pair, every axis
# --------------------------------------------------------------------------

def point_sim_figure(cell_a, cell_b, all_vars, D, out, labels=("A", "B")):
    """Per axis: the two truncated pieces, their meet and join, the ratio."""
    instants = sorted(set(cell_a.timeline) & set(cell_b.timeline))
    axes_list = [(t, var) for t in instants for var in all_vars]
    fig, axes = plt.subplots(1, len(axes_list), squeeze=False, sharey=True,
                             figsize=(3.0 * len(axes_list), 3.2))
    scores = []
    for col, (t, var) in enumerate(axes_list):
        ax = axes[0][col]
        a = truncate(cell_a.timeline[t][var], D)
        b = truncate(cell_b.timeline[t][var], D)
        meet, join = intersect_pieces(a, b), union_pieces(a, b)
        score = point_sim_d(cell_a.timeline[t][var], cell_b.timeline[t][var], D)
        scores.append(score)
        for y, (pieces, color) in enumerate([(a, "tab:blue"), (b, "tab:red"),
                                             (meet, "tab:purple"), (join, "tab:green")]):
            for iv in pieces:
                ax.hlines(y, float(iv.l), float(iv.r), color=color, lw=7)
        ax.set_yticks(range(4))
        ax.set_yticklabels([labels[0], labels[1], "meet ∩", "join ∪"], fontsize=8)
        ax.set_ylim(3.6, -0.6)
        ax.set_xlim(-D, D)
        ax.grid(axis="x", ls=":", lw=0.5)
        ax.set_title(f"axis (t={t}, {var})\n|∩| = {measure(meet)}, |∪| = {measure(join)}\n"
                     f"Point_sim = {score:.4f}", fontsize=9)
    total = sum(scores) / len(axes_list)
    fig.suptitle(f"Point_sim_D on {labels[0]} vs {labels[1]}, one call per axis; "
                 f"Path_sim = mean = ({' + '.join(f'{s:.4f}' for s in scores)}) / "
                 f"{len(axes_list)} = {total:.4f}", fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    return list(zip(axes_list, scores)), total


# --------------------------------------------------------------------------
# Stage 5: the Path_sim matrix and the two directional maxima
# --------------------------------------------------------------------------

def matrix_figure(cells_a, cells_b, all_vars, D, out):
    matrix = [[path_similarity(a, b, all_vars, D) for b in cells_b] for a in cells_a]
    row_max = [max(row) for row in matrix]
    col_max = [max(matrix[i][j] for i in range(len(cells_a))) for j in range(len(cells_b))]
    forward = sum(row_max) / len(cells_a)
    backward = sum(col_max) / len(cells_b)

    fig, ax = plt.subplots(figsize=(2.4 + 2.0 * len(cells_b), 2.0 + 0.55 * len(cells_a)))
    ax.imshow(matrix, cmap="Blues", vmin=-0.2, vmax=1.6, aspect="auto")
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            ax.text(j, i, f"{value:.4f}", ha="center", va="center", fontsize=9)
            if value == row_max[i]:
                ax.add_patch(Rectangle((j - .5, i - .5), 1, 1, fill=False,
                                       edgecolor="black", lw=2.5))
            if value == col_max[j]:
                ax.add_patch(Rectangle((j - .40, i - .40), .80, .80, fill=False,
                                       edgecolor="tab:red", lw=1.8, ls=":"))
    ax.set_xticks(range(len(cells_b)))
    ax.set_xticklabels([f"{THETA}{j}\n{_label(b, all_vars)}" for j, b in enumerate(cells_b)],
                       fontsize=6)
    ax.set_yticks(range(len(cells_a)))
    ax.set_yticklabels([f"{PHI}{i}\n{_label(a, all_vars)}" for i, a in enumerate(cells_a)],
                       fontsize=6)
    ax.set_title(
        f"Path_sim matrix (rows = canonical cells of {PHI}, cols = of {THETA})\n"
        f"solid black = row max -> G({PHI},{THETA}) = mean = {forward:.4f}   |   "
        f"dotted red = col max -> G({THETA},{PHI}) = mean = {backward:.4f}\n"
        f"similarity = ({forward:.4f} + {backward:.4f}) / 2 = {(forward + backward) / 2:.4f}",
        fontsize=9)
    fig.tight_layout()
    fig.savefig(out, dpi=150)
    return matrix, forward, backward


def run(formula1, formula2, out_dir, D=None):
    from pathlib import Path as FilePath
    out_dir = FilePath(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths1, paths2, all_vars = signal_spaces_from_definition(formula1, formula2)
    D = float(resolve_D(D, parse(formula1), parse(formula2)))
    horizon = max(parse(formula1).horizon(), parse(formula2).horizon())

    print(f"{PHI} = {formula1}\n{THETA} = {formula2}")
    print(f"vars = {all_vars}, horizon = {horizon}, D = {D:g}, "
          f"axes per cell = {(horizon + 1) * len(all_vars)}\n")

    sides = ((PHI, "phi", formula1, paths1, "tab:blue", "lightblue"),
             (THETA, "theta", formula2, paths2, "tab:red", "mistyrose"))

    for name, slug, formula, _, _, fill in sides:
        out = out_dir / f"01_ast_{slug}.png"
        nodes = ast_figure(name, formula, out, color=fill)
        print(f"{name}: evaluation tree has {nodes} nodes   wrote {out}")

    for canonical in (False, True):
        out = out_dir / ("04_region_canonical.png" if canonical else "02_region_raw.png")
        plot(formula1, formula2, out, canonical=canonical, D=Fraction(D))

    out = out_dir / "02a_paths.png"
    paths_figure(formula1, paths1, formula2, paths2, all_vars, D, out)
    print(f"wrote {out}  ({len(paths1)} vs {len(paths2)} paths, one colour each)")

    for name, slug, formula, paths, color, _ in sides:
        out = out_dir / f"03_canon_{slug}.png"
        breakpoints, fine, canon, partitions = canon_figure(
            name, formula, paths, all_vars, D, color, out)
        print(f"\n{name}: {len(paths)} raw boxes -> {len(fine)} fine cells -> "
              f"{len(canon)} canonical cells")
        for axis in sorted(breakpoints):
            print(f"   B{axis} = {sorted(map(str, breakpoints[axis]))}"
                  f"  -> partition {[str(iv) for iv in partitions[axis]]}")
        print(f"   wrote {out}")

    volume1, volume2 = build_aligned_volumes(formula1, paths1, formula2, paths2,
                                             all_vars=all_vars)
    cells_a, cells_b = _sorted_cells(volume1.volume), _sorted_cells(volume2.volume)

    # Only when the projection is FAITHFUL: a cell is a box over every
    # (instant, variable) axis, so with more than one instant, plotting the
    # (x,y) plane at one instant collapses cells that differ only at another
    # and draws them on top of each other.
    if len(all_vars) == 2 and horizon == 0:
        for cells, label, name in (((paths1, paths2), "raw boxes", "02b_plane_raw.png"),
                                   ((cells_a, cells_b), "canonical cells",
                                    "04b_plane_canonical.png")):
            out = out_dir / name
            plane_figure(formula1, list(cells[0]), formula2, list(cells[1]),
                         all_vars, D, out, label)
            print(f"wrote {out}  ({len(cells[0])} vs {len(cells[1])} {label}, in the plane)")
    print(f"\ncanonical cells of {PHI}:")
    for i, cell in enumerate(cells_a):
        print(f"   {PHI}{i}  {_label(cell, all_vars)}")
    print(f"canonical cells of {THETA}:")
    for j, cell in enumerate(cells_b):
        print(f"   {THETA}{j}  {_label(cell, all_vars)}")

    out = out_dir / "05_point_sim.png"
    per_axis, total = point_sim_figure(cells_a[0], cells_b[0], all_vars, D, out,
                                       labels=(f"{PHI}0", f"{THETA}0"))
    print(f"\nPoint_sim {PHI}0 vs {THETA}0, per axis:")
    for axis, score in per_axis:
        print(f"   {axis} -> {score:.4f}")
    print(f"   Path_sim = {total:.4f}   wrote {out}")

    out = out_dir / "06_matrix.png"
    matrix, forward, backward = matrix_figure(cells_a, cells_b, all_vars, D, out)
    # The figure re-derives Eq. 7 from the matrix, so check it against the
    # real metric -- a drift here would draw a picture of the wrong number.
    from similarity.stl_similarity import calc_similarity_from_formulas
    reference = calc_similarity_from_formulas(formula1, formula2, D=Fraction(D))
    assert abs((forward + backward) / 2 - reference) < 1e-12, \
        f"matrix says {(forward + backward) / 2}, metric says {reference}"
    print(f"\nPath_sim matrix ({len(cells_a)} x {len(cells_b)}), "
          f"{len(cells_a) * len(cells_b) * len(per_axis) * 2} point_sim_d calls:")
    for i, row in enumerate(matrix):
        print(f"   {PHI}{i}: " + " ".join(f"{s:.4f}" for s in row)
              + f"   row max = {max(row):.4f}")
    print("   col max: " + " ".join(
        f"{max(matrix[i][j] for i in range(len(cells_a))):.4f}" for j in range(len(cells_b))))
    print(f"\nG({PHI},{THETA}) = {forward:.6f}   G({THETA},{PHI}) = {backward:.6f}   "
          f"similarity = {(forward + backward) / 2:.6f}  (== calc_similarity_from_formulas)")
    print(f"   wrote {out}")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("formula1")
    p.add_argument("formula2")
    p.add_argument("-o", "--out-dir", default="pipeline")
    p.add_argument("--D", type=Fraction, default=None)
    a = p.parse_args()
    run(a.formula1, a.formula2, a.out_dir, D=a.D)
