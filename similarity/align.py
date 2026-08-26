"""Align two formulas' signal-space path decompositions onto a shared cell
grid, per preliminaries.tex Section 4.3 ("Aligning Path Decompositions",
Definitions 5-6). Required before comparison for the soundness guarantee
G(phi,theta)=1 <=> phi==theta (Section 6): two logically equivalent formulas
can decompose the same region into differently-shaped boxes, and comparing
those boxes directly can understate their similarity.

A cell survives inside an existing box `P` iff it's produced by subdividing
`P`'s own per-axis interval(s) at whichever joint breakpoints land inside
them -- breakpoints outside a box's own range can't slice it. So this never
materializes the full cross-axis grid: for each existing Path it just cuts
that path's own axes and takes their Cartesian product, which is exactly
Definition 6's cell set restricted to that box.
"""
from parse_graph import Interval, Path, merge_pieces


def _joint_breakpoints(paths1, paths2):
    # Definition 5: B(v, t) = every finite piece endpoint either formula
    # uses to bound v at t.
    breakpoints = {}
    for path in paths1 + paths2:
        for t, slot in path.timeline.items():
            for var, pieces in slot.items():
                bucket = breakpoints.setdefault((var, t), set())
                for iv in pieces:
                    if iv.l != float("-inf"):
                        bucket.add(iv.l)
                    if iv.r != float("inf"):
                        bucket.add(iv.r)
    return breakpoints


def _is_undef(pieces):
    return len(pieces) == 1 and pieces[0].l == float("-inf") and pieces[0].r == float("inf")


def _own_constrained_axes(paths):
    # (var, t) axes where at least one of this formula's own paths has a
    # real constraint -- as opposed to an axis this formula never
    # constrains anywhere, which must stay untouched even if the other
    # formula happens to have a real bound there (see _cells_of_path).
    axes = set()
    for path in paths:
        for t, slot in path.timeline.items():
            for var, pieces in slot.items():
                if not _is_undef(pieces):
                    axes.add((var, t))
    return axes


def _cut_piece(piece, cuts):
    # Subdivide `piece` at every breakpoint strictly inside it.
    inside = sorted(b for b in cuts if piece.l < b < piece.r)
    edges = [piece.l] + inside + [piece.r]
    return [Interval(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]


def _cells_of_path(path, breakpoints, own_constrained_axes):
    # Definition 6: Cartesian product of the per-(var, t) elementary
    # sub-intervals that subdivide `path`'s own box. An axis this formula
    # never constrains anywhere is left uncut even if the *other* formula
    # has a real breakpoint there -- otherwise slicing manufactures a
    # spurious "half-undef" cell that can coincidentally equal the other
    # formula's real constraint and score as a false match, when the
    # original box asserted nothing about that axis at all.
    axes = []  # [(t, var, [Interval, ...]), ...]
    for t in sorted(path.timeline):
        slot = path.timeline[t]
        for var in sorted(slot):
            cuts = breakpoints.get((var, t), ()) if (var, t) in own_constrained_axes else ()
            subpieces = []
            # Merge first: a slot's raw pieces can overlap/be redundant (e.g.
            # [0,inf) and the degenerate point [0,0] from a prior union
            # merge), and cutting those independently would fabricate
            # spurious extra alternatives instead of one region.
            for piece in merge_pieces(slot[var]):
                subpieces.extend(_cut_piece(piece, cuts))
            axes.append((t, var, subpieces))

    cells = [{}]
    for t, var, subpieces in axes:
        cells = [
            {**cell, t: {**cell.get(t, {}), var: [sub]}}
            for cell in cells
            for sub in subpieces
        ]
    return [Path(cell) for cell in cells]


def _cell_key(cell):
    return tuple(sorted(
        (t, var, iv.l, iv.r)
        for t, slot in cell.timeline.items()
        for var, ivs in slot.items()
        for iv in ivs
    ))


def align(paths1, paths2):
    """Align(P(phi), P(theta)) -> (Pe(phi), Pe(theta)) (Definition 6).

    Cuts both formulas' paths down to a shared grid of elementary cells fine
    enough that every original box is exactly a union of cells (Lemma 1), so
    comparing the two aligned lists never understates similarity just
    because the two tableaus cut the same region into different boxes.
    Despite the name, each returned list is a set of cells (deduplicated by
    structural equality), not one path per formula -- alignment never
    collapses a formula's paths into one.
    """
    breakpoints = _joint_breakpoints(paths1, paths2)
    own1, own2 = _own_constrained_axes(paths1), _own_constrained_axes(paths2)

    def aligned(paths, own_constrained_axes):
        seen = {}
        for path in paths:
            for cell in _cells_of_path(path, breakpoints, own_constrained_axes):
                seen.setdefault(_cell_key(cell), cell)
        return list(seen.values())

    return aligned(paths1, own1), aligned(paths2, own2)
