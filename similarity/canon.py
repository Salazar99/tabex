"""Canonical box decomposition of a formula's signal space.

Replaces the previous pairwise `align(P(phi), P(theta))` with a *unary*
`canonicalize(P(phi))` that depends only on the region S_phi = union of
P(phi), never on the formula it is being compared against. Two tableaux that
cut the same region into different boxes therefore canonicalize to the same
object, which is what the L-shaped example of the paper needs -- without the
joint grid, and without the `_own_constrained_axes` /
`_globally_unconstrained_vars` gates the joint grid forced.

Soundness (G(phi,theta) = 1 => phi == theta) rests on exactly one property
of this module: canonicalisation is lossless, i.e. the union of the returned
cells is the region it started from. Coarsening (step 3-4) is the only step
that could enlarge a cell, and it is admitted only across breakpoints the
region is prismatic at, so it cannot.

Output has the same structure as standardize()'s: list[Path], each
Path.timeline = {t: {var: [Interval]}}, with exactly one interval per slot
since a cell is a box.

Pipeline, per formula: tableau -> standardize -> canonicalize -> trim.
"""
from parse_graph import Interval, Path, merge_pieces

INF = float("inf")


def _cut_piece(piece, cuts):
    """Subdivide `piece` at every breakpoint strictly inside it."""
    inside = sorted(b for b in cuts if piece.l < b < piece.r)
    edges = [piece.l] + inside + [piece.r]
    return [Interval(edges[i], edges[i + 1]) for i in range(len(edges) - 1)]


def cell_key(cell):
    """Structural identity of a cell, for deduplication and comparison."""
    return tuple(sorted(
        (t, var, iv.l, iv.r)
        for t, slot in cell.timeline.items()
        for var, ivs in slot.items()
        for iv in ivs
    ))


def _breakpoints(paths):
    """B(v,t): every finite endpoint this formula's own boxes use on that axis.

    Unary -- the other formula's edges are deliberately not pooled in. An
    axis this formula never bounds gets an empty set and is left whole, which
    is what keeps F[3,4] x>0 from borrowing F[0,2] x>0's breakpoint and
    manufacturing a constraint out of genuine silence.
    """
    breakpoints = {}
    for path in paths:
        for t, slot in path.timeline.items():
            for var, pieces in slot.items():
                bucket = breakpoints.setdefault((t, var), set())
                for iv in merge_pieces(pieces):
                    if iv.l != -INF:
                        bucket.add(iv.l)
                    if iv.r != INF:
                        bucket.add(iv.r)
    return breakpoints


def _fine_cells(paths, breakpoints):
    """The arrangement cells over B that lie inside the region.

    A grid cell over B is either inside a box or disjoint from it, since every
    box boundary is itself in B. So cutting each box at B and deduplicating
    yields precisely that arrangement -- no need to enumerate the full
    cross-axis grid, the overwhelming majority of which is outside the region.
    """
    seen = {}
    for path in paths:
        axes = []
        for t in sorted(path.timeline):
            for var in sorted(path.timeline[t]):
                subpieces = []
                # Merge first: a slot's raw pieces can overlap (e.g. [0,inf)
                # and a degenerate [0,0] from an earlier union), and cutting
                # those separately fabricates extra alternatives.
                for piece in merge_pieces(path.timeline[t][var]):
                    subpieces.extend(_cut_piece(piece, breakpoints.get((t, var), ())))
                axes.append((t, var, subpieces))
        cells = [{}]
        for t, var, subpieces in axes:
            cells = [{**c, t: {**c.get(t, {}), var: [sub]}} for c in cells for sub in subpieces]
        for c in cells:
            cell = Path(c)
            seen.setdefault(cell_key(cell), cell)
    return list(seen.values())


def _drop_subsumed(cells):
    """Delete grid cells contained in another grid cell.

    Fat grid cells have disjoint interiors, so this can only ever fire on a
    cell that is degenerate (a point) on some axis -- one contributed by an
    "==" atom that a wider box already covers. Left in place such a cell both
    adds a spurious element to the decomposition and pins a breakpoint the
    region does not bend at, so `0<=x<=10` and
    `(0<=x<=5) || (x==5) || (5<=x<=10)` would not canonicalise alike.
    Cutting first is what makes pairwise containment sufficient: a point cell
    in the grid is either inside a single grid cell or genuinely its own
    region.
    """
    # ponytail: O(n^2), but short-circuited to a no-op unless an "==" atom
    # produced a degenerate cell. Index by projection if that stops holding.
    def box(cell):
        return {(t, var): ivs[0] for t, slot in cell.timeline.items() for var, ivs in slot.items()}

    boxes = [box(c) for c in cells]
    if not any(iv.l == iv.r for b in boxes for iv in b.values()):
        return cells
    kept = []
    for i, bi in enumerate(boxes):
        if not any(
            j != i and all(o.l <= bi[k].l and bi[k].r <= o.r for k, o in bj.items())
            and (bi != bj or j < i)
            for j, bj in enumerate(boxes)
        ):
            kept.append(cells[i])
    return kept


def _projection(cell, axis):
    """The cell with `axis` projected out -- its cross-section coordinates."""
    return tuple(sorted(
        (t, var, iv.l, iv.r)
        for t, slot in cell.timeline.items()
        for var, ivs in slot.items()
        for iv in ivs
        if (t, var) != axis
    ))


def _essential(cells, axis, candidates):
    """Breakpoints the region actually bends at.

    `b` is inessential when the region's cross-section just below `b` equals
    the one just above it: the split at `b` is then an artifact of how this
    particular tableau happened to branch, not a feature of the region, and
    two decompositions of one region disagree on exactly such breakpoints.
    Because `cells` is the full grid over B, comparing the two cross-sections
    as sets of cell projections is the same as comparing them as regions.

    A point slab {b} left over after _drop_subsumed is a genuine isolated
    feature (e.g. a lone `x == 5`), so it pins `b`.
    """
    t0, v0 = axis
    ends, starts, degenerate = {}, {}, set()
    for cell in cells:
        iv = cell.timeline[t0][v0][0]
        if iv.l == iv.r:
            degenerate.add(iv.l)
            continue
        ends.setdefault(iv.r, set()).add(_projection(cell, axis))
        starts.setdefault(iv.l, set()).add(_projection(cell, axis))
    keep = set()
    for b in candidates:
        below, above = ends.get(b), starts.get(b)
        if b in degenerate or below is None or above is None or below != above:
            keep.add(b)
    return keep


def _coarsen(cell, essential):
    """Widen every axis interval to the enclosing interval of the coarse grid.

    No containment test is needed: the region is prismatic across every
    dropped breakpoint, so a coarse cell is either entirely inside the region
    or entirely outside it. That is what makes this lossless, and losslessness
    is what soundness rests on.
    """
    timeline = {}
    for t, slot in cell.timeline.items():
        new_slot = {}
        for var, ivs in slot.items():
            iv = ivs[0]
            edges = essential.get((t, var), ())
            lo = max((e for e in edges if e <= iv.l), default=-INF)
            hi = min((e for e in edges if e >= iv.r), default=INF)
            new_slot[var] = [Interval(lo, hi)]
        timeline[t] = new_slot
    return Path(timeline)


def canonicalize(paths):
    """P(phi) -> the canonical cell list of the region it covers.

    Depends only on the union of `paths`, so two decompositions of the same
    region return the identical object. Lossless: the returned cells cover
    exactly that region, no more and no less.
    """
    if not paths:
        return []
    breakpoints = _breakpoints(paths)
    fine = _drop_subsumed(_fine_cells(paths, breakpoints))
    essential = {axis: _essential(fine, axis, cands) for axis, cands in breakpoints.items()}
    seen = {}
    for cell in fine:
        coarse = _coarsen(cell, essential)
        seen.setdefault(cell_key(coarse), coarse)
    return list(seen.values())
