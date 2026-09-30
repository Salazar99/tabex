# Experiments tracker

Status of the paper's experimental research questions against what exists in this repository.
Legend: ✅ done · 🟡 partial · ⬜ not started. Numbers are reproducible with the command shown next to them.

| RQ | Topic | Status |
|---|---|---|
| RQ2 | Baseline comparison (PH, SD) and computational performance | 🟡 scores done, timing study not done |
| RQ3 | Sensitivity of the domain parameter D | 🟡 metric supports it, sweep/plot not done |
| RQ4 | Redundancy pruning in specification mining | ⬜ |
| RQ5 | Semantic drift in LLM translations | ⬜ |

---

## RQ2 — Baseline comparison and computational performance

*How does the metric compare to Pompeiu-Hausdorff (PH) and Symmetric-Difference (SD) distances, in scores and
in execution time?*

### What exists
- **Baselines implemented**: `madsen/metrics.py` — PH as the MILP of Madsen et al.'s Theorem 2 (scipy/HiGHS
  instead of Gurobi), SD via their Algorithm 1 (AoS boxes).
- **Baselines validated**: `tests/test_madsen.py` reproduces their Table I — every directed PH value and every
  SD value except one cell: d_SD(⊤, φ6) = 0.83 here vs 0.84 in the paper; the other φ6 cells imply 0.83, so the
  paper's value looks like an arithmetic slip.
- **Comparison run**: `python -m madsen.compare -o madsen/results.md` — 31 pairs (the 10 manual benchmark pairs
  + all 21 pairs of Madsen's Example 1 at horizon 20), same domain for both sides (TABEX's D, S = [-D, D]).
  TABEX scored by `tabex_fast` (identical to the reference pipeline, checked by `tests/test_tabex_fast.py`).

### Steps
| Step | Status | Notes |
|---|---|---|
| Diverse test suite, equivalent + partially overlapping | 🟡 | 31 pairs; only **one** equivalent pair (φ1 ≡ φ4, row 19). Needs a block of syntactically different but equivalent pairs (e.g. from `verification/verify_equivalence.py`'s rewrites). |
| Run G, PH, SD over the suite | ✅ | `madsen/results.md` |
| Compare scores, conceptual differences | 🟡 | Observations below; not yet written up. The normal-form vs measure argument still needs its dedicated evidence (see next steps). |
| Time vs formula complexity (horizon T, #variables) | ⬜ | Only spot measurements so far (below). |

### Observations so far (from `madsen/results.md`)
- **PH saturates on one-sided constraints**: all 10 benchmark pairs get PH/2D = 0.5 — one extreme sample
  decides it — while TABEX ranges 0–0.97 over the same pairs.
- **SD scores 0 on non-equivalent pairs**: rows 4 (`G(x>0)` vs `G(x>0 || y>0)`), 6, 10 (`F[0,4]` vs `F[0,2]`) —
  the AoS choice set (`||`) resolved to its most favourable alternative hides the difference. TABEX: 0.42, 0.24, 0.59.
- **Opposite verdicts**: row 2 (`F[0,2]` vs `F[3,4]`, disjoint windows) and row 3 (same formula on different
  variables): TABEX 0 (fully dissimilar), Madsen moderate distances.
- **Agreement**: row 19 (φ1 ≡ φ4): TABEX 1.0, PH 0, SD 0.
- **⊤ (rows 11–16)**: TABEX scores `true` 0 against every constrained formula (its canonical box trims to an empty
  time domain, Eq. 6); Madsen treats ⊤ as the superset. A definitional difference worth a sentence in the paper.
- **Rank correlation** of TABEX distance (1 − G) over the 31 pairs: vs PH −0.035, vs SD 0.638.

### Timing data points so far (not a study)
- Reference pipeline, before the canon rewrite: `G[0,h]` of one box took 0.09 s (h=5), 0.66 s (h=7), 11.6 s (h=9) —
  exponential fine arrangement. After the rewrite (`similarity/canon.py`): single-box horizon-20 formulas in ms;
  the 10 benchmark pairs 93 s → 3.7 s.
- The reference pipeline still cannot score `F[0,20]θ1` (≈1.05·10¹⁰ canonical cells) or `G[0,16]F[0,4]θ1`
  (5¹⁷ boxes from E). `tabex_fast` scores every Table I pair at horizon 20 in < 0.1 s each.
- Madsen PH + SD for all of Table I (horizon 20): ~7 s total.

### Next steps
1. Add equivalent-pair block to the suite; include pairs where SD's AoS approximation may break equivalence
   (e.g. `F[0,1](x>0)` vs `F[0,0](x>0) || F[1,1](x>0)`) — measure, don't assume.
2. Timing script (`experiments/timing.py`): sweep T ∈ {2,…,40} and |V| ∈ {1,…,5} over formula families
   (G-box, F-box, G∘F, until); time reference pipeline, `tabex_fast`, PH (both MILPs), SD; per-run timeout; CSV + plot.
3. State the performance claim precisely: exact *endpoints and canonical form* (Fractions); the score itself is
   summed in floats. `tabex_fast`'s cost is bounded by the number of distinct DP states, which is small on these
   families but not guaranteed polynomial.

---

## RQ3 — Sensitivity of the domain parameter D

*How does D affect sensitivity to discrepancies in unbounded constraints?*

### What exists
- `Point_sim_D` (Eq. 5, with the ε-measure of Definition 3) in `similarity/stl_similarity.py::point_sim_d`;
  D validated/derived by `resolve_D` (refused unless D > max|constant|).
- CLI takes `--D` (exact rationals). Known values for `x>2` vs `x>5` (c₁=[2,∞), c₂=[5,∞)):
  G = 0.25 at the derived D = 6, 0.9694 at D = 100 (`python run_similarity.py "x>2" "x>5" --D 100`).
- Tests: `test_point_sim_d_matches_preliminaries_worked_example`, `test_user_D_reaches_the_score`,
  `test_resolve_D_*` in `tests/test_stl_similarity.py`.

### Steps
| Step | Status | Notes |
|---|---|---|
| Select one-sided pairs differing only in offset | 🟡 | `x>2` vs `x>5` used; add a family with varying offset Δ and both directions (`<`, `>`), plus a bounded-vs-unbounded pair as control. |
| Compute Point_sim_D over a wide D range | ⬜ | Only two D values computed. |
| Plot, show monotone increase to 1 | ⬜ | Expected shape (ε → 0): (D − 5)/(D − 2) for the example; verify empirically incl. the ε term. |

### Next steps
1. `experiments/d_sensitivity.py`: D log-spaced from just above the bound to 10⁴, several Δ; both Point_sim_D
   and full G on temporal versions (e.g. `G[0,2](x>2)` vs `G[0,2](x>5)`); plot score vs D/Δ.
2. Contrast with the paper's Eq. 4 decay 1/(1+dist) at the same pairs (fixed, non-parametric).

---

## RQ4 — Redundancy pruning in specification mining

*Can G cluster and prune redundant candidate formulas returned by specification miners?*

| Step | Status | Notes |
|---|---|---|
| Collect a large batch of mined candidates | ⬜ | No miner in the repo. Need a source (tool + traces). Candidates must be in the supported fragment (rectangular atoms, no `R`, no `x>y`); log how many are rejected (`UnsupportedFormula`). |
| Pairwise one-way and global similarity | ⬜ | n² pairs: use `tabex_fast.engine.similarity` (same score, scales to long horizons); cache each formula's `Region` rather than rebuilding per pair. |
| Threshold clustering, one representative per cluster, reduction rate | ⬜ | OWSim is asymmetric — decide whether clustering uses G or OWSim (e.g. OWSim(a→b)=1 means a's boxes all occur in b). Report reduction vs threshold. |

---

## RQ5 — Semantic drift in LLM translations

*How well does G quantify drift among multiple LLM formalisations of one natural-language requirement?*

| Step | Status | Notes |
|---|---|---|
| Generate several STL formalisations per requirement with an LLM | ⬜ | Needs requirement set, prompt, model, sample count; output must be parsed by `reference_semantics.parse` — report parse/fragment failures separately from drift. |
| Score outputs pairwise with G | ⬜ | Same machinery as RQ4; report per-requirement similarity matrix / mean pairwise G. A known-good reference formalisation per requirement would allow OWSim against ground truth too. |

---

## Reproducing what exists

```bash
pytest -q                                   # includes Table I reproduction and fast-vs-reference checks
python -m madsen.compare -o madsen/results.md
python run_similarity.py "x>2" "x>5" --D 100
bash benchmarks/Manual/benchmark_gen.sh
```
