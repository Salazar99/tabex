# `tabex_fast` vs the reference pipeline

How `tabex_fast/engine.py` differs from the reference TABEX pipeline
(`similarity/reference_semantics.py` → `similarity/canon.py` →
`similarity/stl_similarity.py::calc_similarity_from_formulas`), why it differs,
and why it still returns the same score.

## 1. Summary

Both compute the same quantity: the global similarity G of Eq. 8, over the
canonical, trimmed cells of each formula's region. Same D (`resolve_D`), same
ε-Jaccard point similarity (`point_sim_d`), same canonical form. They agree to
float rounding (tests use `abs=1e-9`).

They differ in **what they materialise**. The reference builds every box of E,
every canonical cell, and scores every pair of cells. `tabex_fast` builds none of
these. Each region is a decision diagram, and the score is a dynamic program
over that diagram.

This matters because the objects the reference lists are exponential in the
horizon:

| formula (θ1 = `x>=0.2 && x<=0.4`) | reference must list |
|---|---|
| `F[0,20]θ1` | 3²¹ − 2²¹ ≈ 1.05·10¹⁰ canonical cells |
| `G[0,16] F[0,4]θ1` | 5¹⁷ ≈ 7.6·10¹¹ boxes out of E (~3.5·10⁹ cells) |

`tabex_fast` scores that pair in well under a second.

## 2. Stage-by-stage

### 2.1 Region construction

**Reference.** `evaluate()` (`similarity/reference_semantics.py:388`) returns a
list of boxes. `Or`/`F` concatenate lists. `And`/`G` call `intersect`
(`reference_semantics.py:364`), which is a pairwise product. So `G[0,n]` of an
`F[0,m]` body yields (m+1)^(n+1) boxes, and the result is not deduplicated or
shared.

**Fast.** A `Diagram` (`tabex_fast/engine.py:44`) is a hash-consed,
quasi-reduced MDD. It has one level per axis `(t, var)` in t-major order, one
edge per arrangement atom of that axis, and levels are never skipped. `mk`
interns nodes, so equal subdiagrams are one node. `apply` (`engine.py:69`) is
the memoised product construction for AND/OR, with terminal shortcuts.
`Region._build` (`engine.py:151`) mirrors `evaluate` clause by clause,
including the closed-range Until. It is memoised on `(subformula, instant)`, so
`G[0,16] F[0,4]` reuses the body at each instant rather than multiplying boxes.

**Why:** a box list cannot share structure. Since the diagram is canonical for
a fixed atom order, its size tracks the region, not the syntax.

### 2.2 Breakpoints (the fine arrangement)

**Reference.** `_breakpoints` (`similarity/canon.py:90`) collects, per axis
`(t, var)`, only the finite endpoints that this formula's boxes carry on that
axis. An axis that is never bounded stays whole.

**Fast.** `Region.__init__` (`engine.py:131-134`) cuts every axis of variable
`v` at every constant compared against `v` anywhere in the formula, at every
instant. This is a superset of the reference's breakpoints. Both use the same
`_cut_piece`, so the atoms, including the point slabs `[b,b]`, are built the
same way.

**Why it is still the same answer:** the canonical runs (Def. 5) are a function
of the region alone (Thm 2). Extra breakpoints only split atoms that coarsening
merges back. The fast engine needs one fixed alphabet per level before building
anything, and the reference's per-axis sets are only known after the boxes
exist.

### 2.3 Canonicalisation (per-axis runs)

**Reference.** `_axis_partition_boxes` (`canon.py:237`) walks adjacent atoms on
an axis. It merges them when their fibres cover the same region, which it
decides with `_same_region`/`_covered` (`canon.py:215-234`), a split-and-recurse
union-cover test that is exponential in the worst case. Cells are then
enumerated as products of slabs (`canon.py:294-307`).

**Fast.** `_canonicalize` (`engine.py:182`) takes each level's reachable nodes.
Two adjacent atoms are merged when every reachable node at that level sends them
to the same child (`engine.py:187-197`). The diagram is deterministic, so every
prefix reaches exactly one node per level, and "same child under every reachable
node" is exactly "same fibre". Equality of children is node-id equality, thanks
to hash-consing. The canonical region is then a second, coarser `Diagram` whose
edges are slabs (`coarse`, `engine.py:210-219`). Its accepted strings are the
canonical cells, and `count` (`engine.py:89`) gives their number without listing
them.

### 2.4 Trimming trailing silence

**Reference.** `trim_trailing_undef` (`stl_similarity.py:210`) runs on each
cell. It drops the trailing instants where every variable is `(-∞,∞)`. After
this, cells have different timeline lengths.

**Fast.** Cells are never listed, so length becomes a filter instead.
`Region.of_length(L)` (`engine.py:224`) builds a mask diagram that accepts
exactly the cells whose trimmed length is L: every slot at t ≥ L is undefined,
and some slot at t = L−1 is defined. It then ANDs the mask with the region.
Scoring loops over L = 0..horizon+1.

### 2.5 Scoring (Eq. 6–8)

**Reference.** `one_way_similarity` (`stl_similarity.py:179`) computes, for each
cell of C1, the maximum `path_similarity` over all cells of C2, then takes the
mean. That is |C1|·|C2| calls, each summing `point_sim_d` over instants × vars.

**Fast.** `one_way` (`engine.py:253`) replaces this with a DP over levels:

- `point_sim_d` is computed once per (level, slab₁, slab₂) into `table`
  (`engine.py:263`). Point similarity depends only on the two slabs.
- For each trimmed length L1, a DP **state** is a pair: a node of C1's diagram,
  plus a Viterbi vector. The vector holds, for every (L2, node of C2), the best
  partial sum of point similarities over the C2 prefixes that reach that node.
- The max can be taken inside the sum because `path_similarity` is a sum over
  axes. The future contribution depends only on (L2, current C2 node), so
  keeping only the best prefix per key loses nothing.
- States with equal keys are merged and their **counts** added
  (`engine.py:289`). Every C1 cell that shares a state has the same best score
  from there on. This merging is what makes cost scale with distinct states
  instead of with the ~10¹⁰ cells.
- The reference rules are reproduced exactly:
  - An instant contributes only if it is in both trimmed timelines:
    `active = t < min(L1, L2)` (`engine.py:282`).
  - The denominator is `|T1 ∪ T2| · |V| = max(L1, L2) · |V|`.
  - An empty-vs-empty timeline scores 1 (`engine.py:292`).
  - The empty-region cases of Eq. 7 are handled at `engine.py:256-259`.

## 3. Non-algorithmic differences

These are differences in behaviour or interface, not in the maths:

1. **ε validation (fixed).** `tabex_fast.engine.similarity` used to accept
   `eps=0`, which scores `x>0` vs `x>=0` as `1.0` — exactly what Def. 3 exists
   to prevent. It now refuses `eps <= 0` like `calc_similarity_from_formulas`
   (`stl_similarity.py:283-285`); pinned by
   `tests/test_tabex_fast.py::test_eps_must_be_positive`.
2. **Float summation order.** Partial sums are accumulated along the DP instead
   of per cell, so results match to ~1e-9, not bit for bit.
3. **Output surface.** `tabex_fast` returns the score, plus a cell count through
   `Region.cells()`. It returns no boxes, cells or per-pair values. So
   `run_similarity.py`, `similarity_check.py`, `plotting/`, `EXAMPLE.md`'s
   figures and `verification/` all use the reference. Only `madsen/compare.py`
   uses `tabex_fast`.
4. **`Region` depends on the pair's grid.** A `Region` is built over the joint
   variable set and joint horizon of the two formulas (`regions`,
   `engine.py:297`). One formula's `Region` can therefore be reused across
   pairs only if they share `(vars, horizon)`. This is relevant to the "cache
   each formula's Region" note in `EXPERIMENTS.md` (RQ4).
5. **Recursion.** `apply`, `count` and `coarse` are recursive over diagram depth
   (= number of axes), so the engine raises the recursion limit
   (`engine.py:41`).
6. **CLI.** Same arguments (`formula1 formula2 --D --eps`), but no help text,
   and it is run as a module: `python -m tabex_fast.engine`.

## 4. Cost

| | dominated by |
|---|---|
| reference | #boxes of E × union-cover test in canonicalisation, then \|C1\|·\|C2\| cell-pair scores |
| `tabex_fast` | diagram size × number of distinct DP states per level |

The fast engine's bound is **not** polynomial in general. The number of distinct
Viterbi vectors can grow. It is small on the G / F / G∘F / U families used so
far, but that is an observation, not a theorem (as `EXPERIMENTS.md` RQ2 step 3
already notes).

Measured, one run each, reference capped at 60 s (Python 3.12, WSL2):

| φ | ψ | G reference | G fast | reference (s) | fast (s) |
|---|---|---|---|---|---|
| `F[0,2](x>0)` | `G[0,2](x>0)` | 0.785714 | 0.785714 | 0.002 | 0.001 |
| `G[0,1](x>0) && F[0,1](y<3)` | `(x>0) U[0,1] (y<3)` | 0.950000 | 0.950000 | 0.002 | 0.001 |
| `G[0,2]θ1` | `F[0,2]θ1` | 0.736842 | 0.736842 | 0.003 | 0.001 |
| `G[0,4]θ1` | `F[0,4]θ1` | 0.691943 | 0.691943 | 0.032 | 0.002 |
| `G[0,6]θ1` | `F[0,6]θ1` | 0.677028 | 0.677028 | 0.409 | 0.002 |
| `G[0,8]θ1` | `F[0,8]θ1` | 0.671118 | 0.671118 | 4.975 | 0.003 |
| `G[0,10]θ1` | `F[0,10]θ1` | 0.668616 | 0.668616 | 57.974 | 0.004 |
| `G[0,20]θ1` | `F[0,20]θ1` | — | 0.666700 | >60 | 0.009 |
| `F[0,4]θ1` | `G[0,2] F[0,2]θ1` | 0.958294 | 0.958294 | 3.101 | 0.003 |
| `F[0,6]θ1` | `G[0,4] F[0,2]θ1` | — | 0.947547 | >60 | 0.004 |
| `F[0,8]θ1` | `G[0,6] F[0,2]θ1` | — | 0.942251 | >60 | 0.006 |
| `F[0,20]θ1` | `G[0,18] F[0,2]θ1` | — | 0.934065 | >60 | 0.019 |

The reference grows roughly ×12 per +2 horizon on `G` vs `F`, while the fast
engine stays in milliseconds. Where both finish, the scores agree to 6 decimals.

## 5. How equivalence is checked

`tests/test_tabex_fast.py` (39 tests, all passing):

- `Region.cells()` equals `len(canonicalize(signal_space(...)))` on 14
  formulas. These include `true`/`false`, a hole (`x!=3`), open/closed
  boundaries, and an equivalent-to-`true` disjunction.
- The score matches `calc_similarity_from_formulas` on 23 fixed pairs: the
  manual benchmarks, `EXAMPLE.md`, shortened Madsen pairs, empty and whole
  regions, and V = {}.
- 40 random pairs from `verification/verify_equivalence.py`'s rewrites. Each
  rewrite scores 1.0, and each score matches the reference.
- Madsen's full-horizon `F[0,20]θ1` vs `G[0,16]F[0,4]θ1`. The cell count equals
  3²¹ − 2²¹ exactly, and scoring finishes in < 10 s.

What is *not* covered: `tabex_fast` is only checked against the reference at
horizons the reference can finish. Beyond that, correctness rests on the
per-stage arguments in §2.

## 6. When to use which

- **Reference:** small horizons; anything that needs the boxes or canonical
  cells (plots, `EXAMPLE.md`, debugging); the implementation the paper's
  definitions and proofs map onto line by line.
- **`tabex_fast`:** long horizons, nested temporal operators, and n²-pair
  workloads (RQ2 timing, RQ4 pruning, RQ5 drift). The paper's Section 7
  (`paper/methodology.tex`) presents it as the implementation and proves it
  computes G.

Reproduce: `pytest -q tests/test_tabex_fast.py`. The timing table came from a
throwaway script that calls both `similarity()` and
`calc_similarity_from_formulas()` on the pairs above, running the reference in a
subprocess with a 60 s timeout.
