# TABEX's modifications to stlsat

Base: [`ZamponiMarco/stlsat`](https://github.com/ZamponiMarco/stlsat), branch
`fix-completeness` (through `2e1439e`).

Everything here is upstream except **one file**, `src/sat/tableau/mod.rs`, and
within it one idea: *when a graph is being exported, do not stop early.*
(Upstream's `.github/` is not vendored — a nested workflow directory only
confuses tooling in the parent repo.)

## Why

stlsat is a satisfiability checker, so as soon as one branch comes back `Sat`
it clears the remaining siblings and answers. TABEX does not want the answer —
it wants the **whole tableau**, because every branch is a disjunct of the
signal space `parse_graph.standardize()` reads back. A tableau truncated at the
first satisfying branch is a signal space missing most of its region.

## The changes

Both are in `tableau_loop`, both guarded by `self.graph.is_none()` so plain
solving keeps its early exit and only `--graph-output` runs pay for the full
expansion.

1. **Case 1.2, `JobState::Sat`** — skip `parent.children.clear()`.
2. **Case 2.1, `JobState::Sat`** — skip `job.children.clear()`.

The `children.clear()` calls in the `Unsat`/`implies` arms are left alone: those
prune genuinely rejected implication branches, which TABEX also wants gone.

3. **Case 2.1 merges instead of assigns** — `job.result = merge_results(job.result, res, implies)`.

   (3) is required by (1) and (2), not independent of them. Case 1.2 already
   went through `merge_results`; Case 2.1 assigned, so a later unsatisfiable
   sibling overwrote a branch the node had already found satisfiable. Upstream
   never sees this because `children.clear()` guarantees nothing *comes* after
   the first `Sat` — removing the early exit unmasks it. Without (3), formulas
   like `(x<1) && ((F[2,3](y<2)) || (x>=1))` answer `Some(false)` while the
   disjunct-swapped twin answers `Some(true)`, on identical tableaux.

## Re-applying after an upstream refresh

Diff `src/sat/tableau/mod.rs` against the upstream commit you rebased onto;
that file should be the only one that differs. Then check:

```bash
# every branch present: the nested-G tableau roughly doubles
echo 'G[0,1](G[0,1](((y<=-3 || x>=3) && x<-2)))' > /tmp/t.stl
cargo run --release /tmp/t.stl --graph-output /tmp/t.dot \
    --no-jump-rule --no-formula-simplifications --no-formula-optimizations
grep -c 'label=' /tmp/t.dot     # ~49 with the fork, ~23 truncated

cd .. && pytest -q && python verify_semantics.py --boundary && python verify_equivalence.py
```

TABEX does not read the `Tableau result:` verdict (`parse_graph.run_stlsat`
explains why), so (3) is not load-bearing for the extraction — but a fork that
reports the wrong answer for its own CLI is not worth shipping.
