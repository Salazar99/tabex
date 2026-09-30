"""Canonical box decomposition of a formula's signal space.

`canonicalize(P(phi))` is *unary*: it depends only on the region
S_phi = union of P(phi), never on the formula it is being compared against.
Two decompositions that cut the same region into different boxes therefore
canonicalize to the same object (Theorem 2 of the paper), which is what the
L-shaped example needs -- no alignment step between the two formulas.

Soundness (G(phi,theta) = 1 => phi == theta) rests on exactly one property of
this module: canonicalisation is lossless, i.e. the union of the returned cells
is the region it started from (Proposition 2).

Two invariants make that work, and both are easy to break:

1. `_fine_cells` must be a genuine ARRANGEMENT -- the cells must partition the
   region. Cutting a piece at `b` into "..,b)" and "[b,..)" partitions a single
   box but NOT a union of boxes that disagree about whether `b` itself is in:
   "x>=1 && y>-1" and "x>1 && y>=-1" then yield two cells that overlap on the
   interior and each own a different boundary sliver. So the cut also emits the
   point slab [b,b]: the arrangement of R induced by b1<..<bk is
   (-inf,b1), [b1,b1], (b1,b2), [b2,b2], ..., (bk,inf).

2. The coarse form must be a PRODUCT GRID, not a greedy merge. Greedy pairwise
   coalescing is not confluent -- on the L-shape, merging x first and y first
   give two different (both minimal) answers, so the "canonical" form would
   depend on axis order. `_axis_partition` instead computes, per axis and once
   from the fine arrangement, the maximal runs of adjacent atoms carrying the
   same cross-section. Those runs do not depend on any traversal order, so
   their product is a grid.

Output: list[Path], each
Path.timeline = {t: {var: [Interval]}}, with exactly one interval per slot
since a cell is a box.

`canonicalize` computes this without materialising the fine arrangement
(exponential in the axis count); `_canonicalize_reference` is the literal
version of Definition 6, and the two are tested to agree.

Pipeline, per formula: evaluate E -> canonicalize -> trim.
"""
import itertools

from similarity.intervals import Interval, Path, merge_pieces

INF = float("inf")


def _cut_piece(piece, cuts):
    """Subdivide `piece` into the arrangement atoms induced by `cuts`.

    Emits the point slab [b,b] at every breakpoint the piece contains, so the
    result partitions the piece even when a neighbouring box is open where this
    one is closed. Without the point slabs the fine cells overlap and every
    later step -- which assumes a partition -- quietly goes wrong.
    """
    inside = sorted(b for b in cuts if piece.l < b < piece.r)
    atoms = []
    lo, lo_open = piece.l, piece.lo
    for b in inside:
        atoms.append(Interval(lo, b, lo_open, True))
        atoms.append(Interval(b, b))
        lo, lo_open = b, True
    atoms.append(Interval(lo, piece.r, lo_open, piece.ro))
    # A closed own endpoint sitting exactly on a breakpoint is an atom too.
    if not piece.lo and piece.l in cuts and piece.l != piece.r:
        head = atoms[0]
        atoms[0] = Interval(head.l, head.r, True, head.ro)
        atoms.insert(0, Interval(piece.l, piece.l))
    if not piece.ro and piece.r in cuts and piece.l != piece.r:
        tail = atoms[-1]
        atoms[-1] = Interval(tail.l, tail.r, tail.lo, True)
        atoms.append(Interval(piece.r, piece.r))
    return [iv for iv in atoms if not iv.is_empty()]


def cell_key(cell):
    """Structural identity of a cell, for deduplication and comparison.

    Endpoint openness is part of the identity: without it "(1,inf)" and
    "[1,inf)" collide and one of them is silently deduped away.
    """
    return tuple(sorted(
        (t, var) + iv.to_tuple()
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

    An arrangement atom is either inside a box or disjoint from it, since every
    box boundary is itself in B. So cutting each box at B and deduplicating
    yields precisely that arrangement -- no need to enumerate the full
    cross-axis grid, the overwhelming majority of which is outside the region.
    """
    seen = {}
    for path in paths:
        axes = []
        for t in sorted(path.timeline):
            for var in sorted(path.timeline[t]):
                atoms = []
                # Merge first: a slot's raw pieces can overlap (e.g. [0,inf)
                # and a degenerate [0,0] from an earlier union), and cutting
                # those separately fabricates extra alternatives.
                for piece in merge_pieces(path.timeline[t][var]):
                    atoms.extend(_cut_piece(piece, breakpoints.get((t, var), ())))
                axes.append((t, var, atoms))
        cells = [{}]
        for t, var, atoms in axes:
            cells = [{**c, t: {**c.get(t, {}), var: [atom]}} for c in cells for atom in atoms]
        for c in cells:
            cell = Path(c)
            seen.setdefault(cell_key(cell), cell)
    return list(seen.values())


def _projection(cell, axis):
    """The cell with `axis` projected out -- its cross-section coordinates."""
    return tuple(sorted(
        (t, var) + iv.to_tuple()
        for t, slot in cell.timeline.items()
        for var, ivs in slot.items()
        for iv in ivs
        if (t, var) != axis
    ))


def _axis_partition(cells, axis):
    """Maximal runs of adjacent atoms carrying the same cross-section.

    A run may be collapsed because the region is prismatic across it: the
    cross-section does not change, so the split is an artifact of how this
    particular decomposition happened to cut it. Two decompositions of one region
    disagree on exactly such splits.

    Computed once, from the fine arrangement, independently per axis -- that is
    what makes the product of these partitions a canonical grid rather than an
    order-dependent greedy merge. A hole needs no special case: "(x<1)||(x>1)"
    simply has no [1,1] atom, and two atoms open at 1 do not touch.
    """
    t0, v0 = axis
    fibres = {}
    for cell in cells:
        iv = cell.timeline[t0][v0][0]
        fibres.setdefault(iv.to_tuple(), set()).add(_projection(cell, axis))
    atoms = sorted(fibres, key=lambda key: (key[0], key[2]))
    current, current_fibre, partition = Interval(*atoms[0]), fibres[atoms[0]], []
    for key in atoms[1:]:
        iv = Interval(*key)
        touching = iv.l == current.r and not (iv.lo and current.ro)
        if touching and fibres[key] == current_fibre:
            current = Interval(current.l, iv.r, current.lo, iv.ro)
        else:
            partition.append(current)
            current, current_fibre = iv, fibres[key]
    partition.append(current)
    return partition


def _slab_of(partition, iv):
    for slab in partition:
        starts_within = slab.l < iv.l or (slab.l == iv.l and (iv.lo or not slab.lo))
        ends_within = iv.r < slab.r or (iv.r == slab.r and (iv.ro or not slab.ro))
        if starts_within and ends_within:
            return slab
    return iv


#: Stands in for a projected-out axis, so a cross-section keeps its tuple shape.
_STAR = frozenset({"*"})


def _atom_boxes(paths, axes, breakpoints):
    """Each path as a product: one frozenset of atom keys per axis.

    The same arrangement atoms `_fine_cells` enumerates, without multiplying
    them out. Atoms on an axis come from one arrangement, so two of them are
    either identical or disjoint -- set operations on the keys are exact.
    """
    boxes = []
    for path in paths:
        box = tuple(
            frozenset(atom.to_tuple()
                      for piece in merge_pieces(path.timeline[t][var])
                      for atom in _cut_piece(piece, breakpoints.get((t, var), ())))
            for t, var in axes)
        if all(box):     # an empty axis contributes no cell, as in _fine_cells
            boxes.append(box)
    return boxes


def _covered(box, others):
    """Is the product `box` inside the union `others`? Split-and-recurse.

    ponytail: exponential in the worst case (it is a union-cover test); linear
    on the G/F shapes formulas produce. Memoise on (box, others) if it bites.
    """
    meeting = [q for q in others if all(p & s for p, s in zip(box, q))]
    if not meeting:
        return False
    if any(all(p <= s for p, s in zip(box, q)) for q in meeting):
        return True
    q = meeting[0]
    i = next(i for i, (p, s) in enumerate(zip(box, q)) if not p <= s)
    inside, outside = box[:i] + (box[i] & q[i],) + box[i + 1:], box[:i] + (box[i] - q[i],) + box[i + 1:]
    return _covered(inside, meeting) and _covered(outside, meeting)


def _same_region(boxes_a, boxes_b):
    return all(_covered(b, boxes_b) for b in boxes_a) and \
        all(_covered(b, boxes_a) for b in boxes_b)


def _axis_partition_boxes(boxes, i):
    """`_axis_partition` on axis `i`, read off the boxes instead of the fine cells.

    An atom's fibre -- the set of fine cells projected from the cells above it
    -- is a set of cells of the projected arrangement, which partition space;
    so two fibres are equal iff the regions they cover are. That region is the
    union of the projections of the boxes containing the atom, which can be
    compared without enumerating a single cell.
    """
    holders = {}
    for n, box in enumerate(boxes):
        for key in box[i]:
            holders.setdefault(key, []).append(n)

    def fibre(key):
        return [boxes[n][:i] + (_STAR,) + boxes[n][i + 1:] for n in holders[key]]

    atoms = sorted(holders, key=lambda key: (key[0], key[2]))
    current, partition = Interval(*atoms[0]), []
    for prev, key in zip(atoms, atoms[1:]):
        iv = Interval(*key)
        touching = iv.l == current.r and not (iv.lo and current.ro)
        if touching and (holders[prev] == holders[key]
                         or _same_region(fibre(prev), fibre(key))):
            current = Interval(current.l, iv.r, current.lo, iv.ro)
        else:
            partition.append(current)
            current = iv
    partition.append(current)
    return partition


def canonicalize(paths):
    """P(phi) -> the canonical cell list of the region it covers.

    Depends only on the union of `paths`, so two decompositions of the same
    region return the identical object. Lossless: the returned cells cover
    exactly that region, no more and no less.

    Computes exactly `_canonicalize_reference` -- same cells, same order -- but
    never builds the fine arrangement, which is exponential in the number of
    axes even when the answer is one cell (`G[0,20] 0.2<=x<=0.4` cuts into
    3^21 fine cells and coarsens back to 1). Partitions come from
    `_axis_partition_boxes`; each path's cells are then its product over
    per-axis slabs. The atom -> slab map is monotone, so walking that product
    lexicographically meets the cells in the reference's first-seen order.
    `tests/test_canon.py` checks the two agree.
    """
    if not paths:
        return []
    axes = sorted({(t, var) for path in paths
                   for t, slot in path.timeline.items() for var in slot})
    breakpoints = _breakpoints(paths)
    boxes = _atom_boxes(paths, axes, breakpoints)
    if not boxes:
        return []
    partitions = [_axis_partition_boxes(boxes, i) for i in range(len(axes))]
    canonical = {}
    for box in boxes:
        slabs = []
        for i, atoms in enumerate(box):
            ordered = sorted(atoms, key=lambda key: (key[0], key[2]))
            slabs.append(list(dict.fromkeys(
                _slab_of(partitions[i], Interval(*key)).to_tuple() for key in ordered)))
        for combo in itertools.product(*slabs):
            timeline = {}
            for (t, var), key in zip(axes, combo):
                timeline.setdefault(t, {})[var] = [Interval(*key)]
            cell = Path(timeline)
            canonical.setdefault(cell_key(cell), cell)
    return list(canonical.values())


def _canonicalize_reference(paths):
    """Definition 6 of the paper, literally: build the fine
    arrangement, coarsen each axis, map every fine cell to its coarse cell.
    Exponential in the axis count; kept as the specification `canonicalize`
    is tested against.
    """
    if not paths:
        return []
    breakpoints = _breakpoints(paths)
    fine = _fine_cells(paths, breakpoints)
    partitions = {axis: _axis_partition(fine, axis) for axis in breakpoints}
    canonical = {}
    for cell in fine:
        timeline = {}
        for t, slot in cell.timeline.items():
            for var, ivs in slot.items():
                axis = (t, var)
                coarse = _slab_of(partitions[axis], ivs[0]) if axis in partitions else ivs[0]
                timeline.setdefault(t, {})[var] = [coarse]
        coarse_cell = Path(timeline)
        canonical.setdefault(cell_key(coarse_cell), coarse_cell)
    return list(canonical.values())
