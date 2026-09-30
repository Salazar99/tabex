# TABEX — full results of the experimental campaign

This document collects every result produced for the paper's experimental section, with, for each experiment,
what it was for, how it was set up, what came out, and how to read it. The last section discusses what helps
and what hurts the paper, and how each weakness might be fixed.

**Sources.** Every quotation and every external fact carries its source:

| tag | source |
|---|---|
| [paper] | the draft *Semantic similarity of STL formulae via canonical signal spaces* (`STL_Similarity.pdf`, 30 pp., 2026-09-30) |
| [Madsen] | C. Madsen et al., *Metrics for Signal Temporal Logic Formulae*, CDC 2018 — the PH and SD baselines |
| [Slam] | D. Nicoletti, S. Germiniani, G. Pravadelli, *Mining STL specifications for hybrid systems*, FDL 2024; code https://github.com/Salazar99/Slam, branch `develop` (e195c41) |
| [STLSat] | M. Zamponi's STL satisfiability checker, https://github.com/ZamponiMarco/stlsat |
| [DeepSTL] | J. He et al., *DeepSTL — From English Requirements to Signal Temporal Logic*, ICSE 2022; data https://github.com/JieHE-2020/DeepSTL |
| [ARCH-COMP] | ARCH-COMP Falsification category reports (the requirement set was transcribed from memory of those reports — **constants must be re-checked** against the report that will be cited) |
| [repo] | a file of this repository; the path is given |

Numbers without a tag are this campaign's own measurements; the file they come from is given in each section.
Everything is reproducible with the commands in `EXPERIMENTS.md` (section "Reproducing everything"), which also tracks the status of each research question.

**Environment.** Ubuntu, Python 3.10.12, 32 cores, 31 GB RAM, no GPU. Every TABEX score comes from `tabex_fast`
(the decision-diagram engine, [paper] Sec. 7) unless stated otherwise. Several runs shared the CPU (in particular
the STLSat baseline ran 30 processes for ~2 h), so absolute times outside the RQ2 timing study are pessimistic.

---

## 0. Sanity of the implementation

**Purpose.** Before any experiment: the code must compute what the paper defines, and the fast engine must agree
with the literal pipeline.

**Setup.** The repository test suite (`pytest -q`), which includes the reproduction of [Madsen]'s Table I
(`tests/test_madsen.py`), the fast-vs-reference checks (`tests/test_tabex_fast.py`) and the new
`tests/test_experiments.py` (volume Jaccard closed forms, the trace monitor against the signal space on 600
random formula/signal pairs, Slam's derivative semantics, the DeepSTL filter).

**Results.**
- 231 tests pass. Before this campaign 50 tests failed on Python 3.10 because a test helper and a plot label
  formatted a `Fraction` with `:g` (only valid from Python 3.12); both were fixed (`tests/conftest.py`,
  `plotting/plot_signal_space.py`), since the README states Python 3.10+.
- On the 74 points of the timing study where both the reference pipeline and `tabex_fast` finished, the scores
  differ by at most 1.1·10⁻¹⁵ (`experiments/results/timing.csv`).
- [Madsen] Table I is reproduced except one SD cell: d_SD(⊤, φ6) = 0.83 here vs 0.84 in [Madsen]; the other φ6
  cells imply 0.83 ([repo] `EXPERIMENTS.md`, pre-existing).

---

## 1. RQ2 — comparison with Pompeiu-Hausdorff (PH) and Symmetric-Difference (SD)

### 1.1 Hand-picked suite (pre-existing) + equivalent block (new)

**Purpose.** Show, on readable pairs, where TABEX's G and [Madsen]'s PH and SD agree and disagree; add pairs that
are syntactically different but equivalent, where every measure should report identity.

**Setup.** `python -m madsen.compare -o madsen/results.md`. 45 pairs: the 10 manual benchmark pairs
(`benchmarks/Manual/benchmark_gen.sh`), the 21 pairs of [Madsen]'s Example 1 at horizon 20, and 14 equivalent
pairs (new). Same domain for both tools: TABEX's D = max|constant| + 1 ([paper] Def. 2) and [Madsen]'s S = [−D, D].
PH is also shown normalised by 2D. PH is the MILP of [Madsen] Theorem 2 solved with scipy/HiGHS; SD is [Madsen]
Algorithm 1. **Implementation choice to keep in mind:** [Madsen] leaves open how the `||` "choice set" of
Algorithm 1 is resolved; this implementation takes the most favourable pair of alternatives ([repo]
`madsen/metrics.py`, docstring of `d_sd`). Several SD results below depend on that choice.

**Results** (`madsen/results.md`).
- *Equivalent block*: G = 1 on 14/14, PH = 0 on 14/14, **SD ≠ 0 on 5/14**:
  `F[0,1](x>0)` vs `F[0,0](x>0) || F[1,1](x>0)` → 0.50; `F[0,1]F[0,1](x>0)` vs `F[0,2](x>0)` → 0.25;
  `(x>=0 || x<0) U[0,2] (y>0)` vs `F[0,2](y>0)` → 0.25; `G[0,2]((0<x<2)||(1<x<3))` vs `G[0,2](0<x<3)` → 0.125;
  the same under F → 0.0625. At horizon 0 every AoS box has zero width in time and SD is 0 for every pair, so the
  block was kept at horizon ≥ 1.
- *PH saturates on one-sided constraints*: all 10 benchmark pairs get PH/2D = 0.5, while G ranges 0–0.97.
- *SD scores 0 on non-equivalent pairs*: e.g. `G[0,2](x>0)` vs `G[0,2](x>0 || y>0)` (G = 0.4167),
  `F[0,4](x>0)` vs `F[0,2](x>0)` (G = 0.5903).
- *Opposite verdicts*: disjoint windows `F[0,2]` vs `F[3,4]` and the same formula on different variables get G = 0,
  but moderate PH/SD distances.
- *⊤*: G(⊤, φ) = 0 for every constrained φ of Example 1, whereas [Madsen] treats ⊤ as the superset.
- *Rank correlation* of 1 − G over the 31 non-equivalent pairs: vs PH −0.035, vs SD 0.638.

**Reading.** On identity, G and PH are both right and SD is not. On graded values the three measures order pairs
differently; with 31 hand-picked pairs this alone cannot say which is "right" (see 1.2 and 5).

### 1.2 Generated suite: equivalence detection and controlled perturbations (new)

**Purpose.** Answer the objection that 45 author-chosen pairs can be cherry-picked. Nothing here is chosen by hand:
(1) how often does each measure recognise an equivalent pair; (2) does each measure's distance grow with a
perturbation of known, graded severity?

**Setup.** `python experiments/random_suite.py` → `experiments/results/random_suite.md`, `random_equivalence.csv`,
`random_mutations.csv`.
- *Part 1*: 1000 pairs = a random formula and one of the 28 meaning-preserving rewrites of [repo]
  `verification/verify_equivalence.py` (so equivalent by construction; variables x, y; constants −3..3). A measure
  detects the pair iff it reports identity (G = 1, VolJ = 1, PH = 0, SD = 0).
- *Part 2*: 300 random base formulas (Boolean combination of atoms under one or two bounded temporal operators,
  or an until), each mutated 11 times: one atom's constant shifted by Δ = 1, 2, 3, 4 (same direction); the outer
  window shifted `[a,b] → [a+k,b+k]`, k = 1..3; widened `[a,b] → [a,b+k]`, k = 1..3; one atom's strictness flipped
  (`>` ↔ `>=`). One D = 8 for everything so that a severity sequence is on one scale. Mutants with G = 1 are
  equivalent to their base ([paper] Sec. 6) and were dropped: 508 of 3300.
- Four measures: 1 − G, 1 − VolJ (exact volume Jaccard, §1.4), PH/2D, SD.

**Results.**

Part 1 — equivalent pairs recognised:

| measure | recognised | missed (by rewrite) |
|---|---|---|
| G | 1000/1000 | — |
| VolJ | 1000/1000 | — |
| PH | 1000/1000 | — |
| SD | **928/1000** | 72: "nested F collapses" `F[0,1]F[0,1]φ ≡ F[0,2]φ` (43), "U with a true invariant" `⊤ U[a,b] φ ≡ F[a,b] φ` (29) |

Part 2 — "blind" = scored identical although not equivalent; "monotone" = severity sequences whose distance never
decreases; τ = mean Kendall τ between severity and distance:

| measure | constant shift Δ (blind · monotone · τ) | window shift k | window widening k | strictness flip (blind) |
|---|---|---|---|---|
| 1 − G | 0/956 · 235/240 · 0.924 | 0/804 · 268/268 · 0.991 | 0/804 · 268/268 · 1.000 | 0/228 |
| 1 − VolJ | 1/956 · 228/240 · 0.929 | 0/804 · 268/268 · 0.965 | 0/804 · 268/268 · 1.000 | 3/228 |
| PH/2D | 8/956 · 240/240 · 0.954 | 0/804 · 255/268 · **0.006** | 0/804 · 252/268 · **0.047** | **228/228** |
| SD | **299/956** · 240/240 · 0.687 | **205/804** · 157/268 · 0.346 | **431/804** · 268/268 · 0.466 | **228/228** |

A strictness flip is scored as a smaller change than a constant shift by 1 in 221/225 bases for G (and for VolJ;
PH "225/225" and SD "158/225" are trivial because they give the flip distance 0).

Two anomalies, both real:
- *G is not always monotone*: 5/240 constant-shift sequences decrease (VolJ: 12/240). Example from
  `random_mutations.csv`: base `F[2,3]((x>=-2) U[0,2] ((x>=3 && x<=3)))`, widening the upper bound 3 → 4, 5, 6, 7
  gives 1 − G = 0.295, 0.319, 0.315, 0.284. Another: `G[2,3](F[1,2]((x<0 || (x>c && y<=-1))))` with c = 1 → 0 → −1 →
  −2 → −3 gives 0.0625, 0.0367, 0.0367, 0.0367 — once `x>c` overlaps `x<0` the region stops growing.
- *Discontinuity at ⊤*: base `F[0,3](G[1,2]((y<1 || (x<=1 || y>-1))))` is a tautology; the mutant with `y<-1`
  differs from it only on the single value y = −1 (with x > 1) and scores **G = 0**, while 1 − VolJ = 5·10⁻¹⁶.
- VolJ's 1 + 3 "blind" cases are float-level: 1 − VolJ ≈ 10⁻¹⁰ on strictness flips (the ε mass of one endpoint
  spread over a product measure), i.e. not truly blind but below practical resolution. G sees them at ~10⁻⁷.

**Reading.** G is the only measure that never calls a non-equivalent mutant identical and grades all three
perturbation families. PH is a value-space distance: perfect on constants, flat in time (τ ≈ 0) because the
worst-case gap saturates after the first shift, and blind to strictness by construction ([Madsen] works with
closed languages; the reimplementation drops strictness, [repo] `madsen/metrics.py`). SD is blind to 30–54 % of
the mutants of every family.

### 1.3 Computational performance (new)

**Purpose.** Measure time vs formula complexity (horizon T, number of signals |V|) for the four methods.

**Setup.** `python experiments/timing.py` → `experiments/results/timing.{csv,png}`. Four families, each
instantiated with θ1 = [0.2, 0.4] and θ2 = [0.2, 0.44] on every variable (the predicates of [Madsen] Example 1;
partially overlapping, so no identity shortcut): `G[0,T]θ`, `F[0,T]θ`, `G[0,T−2]F[0,2]θ`, `θ_lo U[0,T] θ_hi`.
T ∈ {2, …, 40}, |V| ∈ {1, …, 5}. Methods: the reference pipeline (literal E → canon → trim → Eq. 7, [paper]
Sec. 7.1), `tabex_fast`, PH (both directed MILPs), SD. Each run in a fresh process, 60 s and 3 GB limits, minimum
of ≤ 3 repetitions, 8 runs in parallel; a failure ends that series. 0 errors.

**Results.** Largest T finished within 60 s, for |V| = 1/2/3/4/5:

| family | reference | tabex_fast | PH | SD |
|---|---|---|---|---|
| G | 40/40/40/40/40 | 40/40/40/40/40 | 40/40/40/40/40 | 40 (all) |
| F | 4/2/–/–/– | 40/20/12/8/6 | 40/28/12/8/8 | 40 (all) |
| G∘F | 4/2/–/–/– | 40/16/8/6/4 | 8/6/4/4/4 | 40 (all) |
| U | 4/2/–/–/– | 40/24/16/12/10 | 24/6/4/4/2 | 40 (all) |

- The reference pipeline dies at T ≈ 4 on every F-type family (`F[0,4]θ`, |V| = 1: 31.7 s; tabex_fast 0.013 s).
- With one variable tabex_fast grows polynomially (F: 0.43 s at T = 20, 3.9 s at T = 40, ≈ T^3.2).
- vs PH: comparable on F (PH reaches further at |V| = 2 and 5), clearly ahead on G∘F and U (U, |V| = 1, T = 20:
  0.23 s vs 24.4 s; PH's U encoding hits the 3 GB cap at T = 28).
- SD is milliseconds everywhere (it computes an over-approximation over AoS boxes).
- Both exact methods are exponential in |V| on F-type families.

**Reading.** Consistent with [paper] Remark 2: "We claim no polynomial bound, however: the number of distinct
Viterbi vectors can grow with the horizon." The data show it also grows with |V|.

### 1.4 Ablation: G vs exact volume Jaccard (new)

**Purpose.** The decision diagram makes the obvious alternative to G nearly free: the exact volume Jaccard of the
two signal spaces, VolJ = |S(φ) ∩ S(θ)|_ε / |S(φ) ∪ S(θ)|_ε on [−D, D]^A (product of the ε-measure of [paper]
Def. 3 per axis). It is also 1 exactly on equivalent formulas. A reviewer will ask why box-by-box matching is
needed; this experiment answers it.

**Setup.** `tabex_fast/volume.py` (both formulas on one joint diagram; memoised measure; unit-tested against closed
forms), `python experiments/volume_ablation.py` → `experiments/results/volume_ablation.{csv,png}`,
`volume_suite.csv`. Pairs θ1 vs θ2 under `G[0,T]` and `F[0,T]` on |V| = 1..3; plus the 45-pair suite of §1.1.

**Results.**
- `G[0,T]θ1` vs `G[0,T]θ2`: G = 0.8333 for every T and |V|. VolJ = (5/6)^{(T+1)|V|}: at |V| = 1, 0.402 (T = 4),
  0.135 (T = 10), 0.022 (T = 20), 5.7·10⁻⁴ (T = 40); at |V| = 3, 1.8·10⁻¹⁰ (T = 40).
- `F[0,T]θ1` vs `F[0,T]θ2`: VolJ drifts the other way, 0.83 (T = 0) → 0.975 (T = 40) at |V| = 1, as both regions fill
  the box, and depends on |V| (0.58 at |V| = 3 vs 0.83 at |V| = 1, T = 0); G stays 0.83–0.93 whatever |V|.
- VolJ = 1 on 14/14 of the equivalent block.
- Spearman ρ between distances over the 31 non-equivalent pairs of §1.1: ρ(1−G, 1−VolJ) = 0.048,
  ρ(1−VolJ, PH) = 0.601, ρ(1−G, SD) = 0.638.
- VolJ is better behaved at ⊤: VolJ(⊤, x>0) = 0.5 where G = 0.

**Reading.** Volume is driven by the dimension (T+1)|V| of the grid rather than by the constraint, and it goes to 0
or towards 1 depending on the operator; G's per-axis average (Box_sim, [paper] Eq. 6) removes that dependence. This
is the strongest argument for the design — and §4.3 shows its price.

### 1.5 Realistic specifications: ARCH-COMP falsification requirements (new)

**Purpose.** Show how much of a standard benchmark the fragment covers ([paper] App. A.2 restricts atoms to
`v ⋈ c`) and whether realistic requirements can be scored.

**Setup.** `python experiments/archcomp.py` → `experiments/results/archcomp.{csv,md}`. 23 requirements of the
[ARCH-COMP] FALS category (AT1, AT2, AT51–54, AT6a/b/c/abc, AFC27/29/33, NN, NNx, CC1–5, CCx, F16, SC), written in
TABEX's syntax from memory of the reports, discretised at Δt = 1 s with windows rounded outward (`F[0,0.05]` →
`F[0,1]`). `|μ| < c` is written as the box −c < μ < c. Each is scored against itself and against a copy with every
constant × 1.05 (0 → 0.5), 60 s / 3 GB per run.

**Results.**
- In the fragment as stated: **16/23**. With difference signals d_ij = y_i − y_j introduced as signals of their own
  (as RQ4 does for Slam's derivative): **22/23**; only NN (|Pos − Ref| compared with 0.005 + 0.03·|Ref|) stays out.
- Scored within 60 s: **13/23**. Failures: AT51–54 (T = 34, `F[0,1]G[0,3]` under `G[0,30]`; AT54 took 59.8 s in a
  first run), AFC27 (T = 55), CC2–CC5 (T = 100–115, G∘F and G∘F∘G). G-only requirements up to T = 100 take ≤ 1 s
  (CC1 0.25 s at T = 100; CCx, 4 signals, 1.0 s).
- Example scores vs the perturbed copy: AT1 0.976, AT6a 0.748, AFC29 0.963, NNx 0.451, F16 0.667, SC 0.833.

**Reading.** The fragment is not the bottleneck; the cost of nested temporal operators at horizons ≳ 30 steps is.
A coarser Δt halves T but changes the formula; its effect on scores was not studied.

### 1.6 Is 1 − G a metric? (new)

**Purpose.** The paper calls G a "comprehensive similarity metric" ([paper] Sec. 1) and compares it with [Madsen],
whose PH and SD are metrics. G is symmetric, and 1 − G = 0 iff the formulas are equivalent ([paper] Sec. 6); the open
question is the triangle inequality.

**Setup.** `python experiments/metric_properties.py` → `experiments/results/metric_properties.md`: every ordered
triple of distinct candidates within each RQ4 context (all pairwise G are available, §3).

**Results.** **43 142 violations out of 62 486 772 triples (0.069 %)**. Worst: d(a,c) = 0.4848 > d(a,b) + d(b,c) =
0.1818 + 0.1818 with
- a = `F[0,0](fuel∈[1.118445,1.533941]) ∧ F[4,10](map∈[0.549475,0.727315]) → F[4,10](air_fuel_ratio > 10)`
- b = `F[0,0](throttle∈[12.25,12.95]) ∧ F[0,0](ego = 1) → F[4,10](air_fuel_ratio > 10)`
- c = `F[0,0](map∈[0.514331,0.709944]) ∧ F[4,10](fuel∈[1.215924,1.409387]) → F[4,10](air_fuel_ratio > 10)`

**Reading.** 1 − G is a semimetric, not a metric. The word "metric" should go.

---

## 2. RQ3 — sensitivity to the domain parameter D

**Purpose.** [paper] Sec. 5.2 claims that for two one-sided constraints differing only in their endpoint,
"Point_simD is monotonically increasing in D and tends to 1 as D grows relative to |l1 − l2|", in place of the
"fixed, non-parametric decay 1/(1+dist(b_c1, b_c2))" of Eq. 4. Verify it, and characterise the controls.

**Setup.** `python experiments/d_sensitivity.py` → `experiments/results/d_sensitivity.{csv,png,txt}`. D log-spaced
from max|c| + 0.01 to 10⁴ (41 points; 21 for temporal pairs). Pairs: `x>2` vs `x>2+Δ` and `x<−2` vs `x<−2−Δ`,
Δ ∈ {0.5, 1, 3, 10}; `x>=2` vs `x>2`; `[2,5]` vs `[2,8]`; `[2,5]` vs `x>2`; `G/F/U[0,2]` versions (full G). Eq. 4 was
recomputed from the implementation removed in commit 6190e6f ([repo] git history, `distance_decay_similarity`).

**Results** (`d_sensitivity.txt`).
- Closed form, asserted at every D: Point_sim_D(`x>c1`, `x>c2`) = (D − c2)/(D − c1 + ε). Rescaled by (D − c1)/Δ the four
  offsets collapse onto 1 − Δ/(D − c1). `x>2` vs `x>5`: 0.0033 at D = 5.01, 0.769 at D = 15, 0.9997 at D = 10⁴. The `<`
  direction gives identical values. Eq. 4 instead gives a constant 1/(1+Δ): 0.667, 0.5, 0.25, 0.091.
- G equals Point_sim_D on single-instant pairs and on the `G[0,2]` versions; the `F[0,2]` and `U[0,2]` versions start
  higher (0.337 and 0.622 at D = 5.01) and rise to 1 the same way.
- `x>=2` vs `x>2`: 0.9999 at D = 2.01 — the ε term separates them without letting a point matter.
- Controls: `[2,5]` vs `[2,8]` is 0.5 for every D > 8; `[2,5]` vs `x>2` *decreases*: 0.9967 → 0.231 (D = 15) → 0.0003
  (D = 10⁴); Eq. 4 gives it a fixed 0.4.

**Reading.** The claim of [paper] Sec. 5.2 holds exactly; D only acts on unbounded tails. This RQ is essentially
analytical and can be a paragraph with one figure.

---

## 3. RQ4 — redundancy pruning of mined specifications

### 3.1 Candidates from Slam

**Purpose.** [paper] Sec. 1: "a similarity measure allows for pruning or ranking of these candidates instead of
returning redundant duplicates to the engineer". Obtain a realistic batch of mined candidates.

**Setup.** `python experiments/rq4/mine.py` → `experiments/rq4/results/candidates.csv`. [Slam] `develop`, run on the
six case studies shipped in its `tests/` directory with their shipped configurations, changed only in: every
template's `maxd` capped at 10 (with the shipped values a single pair did not score in 10 min), and Controlled_PU's
commented-out mining contexts re-enabled (it ships with only an assertion check active). Slam emits
`G(ant → cons)`; the outer unbounded G (common to all candidates) is dropped and the body compared; Slam's
derivative `@(v,k)` — defined in [Slam] `src/exp/src/classes/expression/Derivative.cc` as v(t+k) − v(t) — becomes a
fresh signal `v_dk`. Build note: Slam's `install_antlr.sh` leaves the headers out; the antlr4 4.13.2 runtime of
`~/harm/third_party` was used.

**Results.** 951 candidates in 9 contexts (WaterTanks 46, Heater 12, Gearbox 166, ControlledPU 350, EngineTiming 6,
FuelControl 371), **0 outside the fragment**. Slam mining time 0.0–163 s per case.

### 3.2 Pairwise similarity and clustering

**Purpose.** Prune with G and report the reduction.

**Setup.** `similarity_matrix.py` (all pairs within a context; per-pair grid as in [paper] Def. 1; one D per context),
`prune.py`: leader clustering on G in Slam's rank order (a candidate joins the first kept, better-ranked
representative with G ≥ τ). G rather than OWSim, because OWSim(a→b) = 1 does not mean b says everything a says.

**Results** (`experiments/rq4/results/summary.md`).
- 107 072 pairs, 1060 s wall on 30 workers, 12 954 CPU-s (FuelControl 87 %); 0 pairs with G = 1 (Slam already removes
  exact duplicates); 2 ordered pairs with OWSim = 1.
- Kept candidates (reduction): τ = 0.8: 166 (83 %); 0.9: 308 (68 %); 0.95: 487 (49 %); 0.99: 755 (21 %); 1: 951 (0 %).
  Per case, e.g. Gearbox 80 % at τ = 0.9, Heater 17 %.

### 3.3 Baseline: Slam's own implication-based pruning (STLSat)

**Purpose.** Compare with the miner's native redundancy removal, `--remove-impl` ([Slam] README: "discard assertions
that are implied by others using the STLSat tool").

**Setup.** `stlsat_baseline.py` re-implements [Slam] `Qualifier::filterAssertionsWithImplications`: same greedy walk
in rank order, same filter (only pairs with the same propositions are checked), same query — `G(` replaced by
`G[0,100](` and `stlsat` run on `(b) && !(a)`, unsat meaning "b implies a". Deviations: the checks are decided up
front in parallel and the greedy walk replayed (same decisions), and each call has a 60 s timeout counted as "not
implied". Binary: the TABEX fork of stlsat, a local build in `m_stlsat/` (not committed; described by `m_stlsat/TABEX_FORK.md`, [repo] git history before 6190e6f); upstream [STLSat]
master (16e5ea6) gives the same verdicts on the checks below (the `fix` branch named by Slam's installer no longer
exists).

**Results.**
- 1645 same-proposition pairs → 3290 checks: **3211 timeouts (97.6 %)**, 79 "implied". **194 161 CPU-s (≈ 54 CPU-h)**
  vs 12 954 CPU-s for all 107 072 TABEX pairs. Kept: 920/951 (3 % reduction).
- **Semantic mismatch**: 18 pairs are declared mutually implied (equivalent) by stlsat, yet G < 1 for all. First one:
  `… F[7,16](map∈…) → F[7,16](afr > 10)` vs `… F[7,15](map∈…) → F[7,15](afr > 10)` (G = 0.941). The discrete signal
  with fuel in range at t = 0, ego at t = 4, map at t = 15 and afr > 10 only at t = 16 satisfies `G[0,100]` of the first
  and violates `G[0,100]` of the second (checked with the trace monitor of §3.5), but stlsat answers unsat in 0.004 s.
  stlsat decides dense-time STL by default (option `--mltl` selects discrete-time semantics, [STLSat] `--help`);
  with `--mltl` a single such check did not finish in 900 s.
- G on the 79 "implied" pairs: mean 0.65, range 0.08–0.94.

**Reading.** As Slam invokes it, STLSat answers a different (dense-time) question than the one the discrete traces
and TABEX pose, and answers the discrete one too slowly to be usable. Implication (a partial order) and closeness are
different relations anyway.

### 3.4 Baseline: SD as the clustering distance

**Purpose.** Cluster with [Madsen]'s SD instead of G.

**Setup.** `sd_matrix.py`: same pairs, same domain; `v == c` written as the closed range `v >= c && v <= c` (SD
needs rectangular predicates).

**Results.** **SD = 0 on all 107 072 pairs.** Every candidate of a context is `ant → cons` with the same consequent,
i.e. `¬ant ∨ cons`; with the most-favourable resolution of `||` (see §1.1), the shared `cons` alternatives match
exactly. SD-clustering keeps one candidate per context at every threshold (9/951).

### 3.5 Pruning quality on the traces

**Purpose.** A reduction rate alone is arbitrary. Check that what is kept still describes what the whole mined set
describes on the trace it was mined from.

**Setup.** `quality.py`. Each candidate's antecedent is monitored on its trace (Slam's derivative reproduced; the
monitor agrees with the signal space on 600 random checks, `tests/test_experiments.py`). *Coverage* = share of trace
instants activated by some candidate of the context that a kept candidate still activates. Compared at the **same
number of kept candidates** with Slam's own ranking (top-k) and random subsets (mean of 50). *Fidelity* = Jaccard
between the activation sets of a pruned candidate and its representative.

**Results** (`experiments/rq4/results/quality.md`):

| τ | kept | coverage, G | top-k (Slam rank) | random | fidelity |
|---|---|---|---|---|---|
| 0.5 | 54 | **0.973** | 0.921 | 0.579 | 0.307 |
| 0.7 | 110 | **0.988** | 0.921 | 0.709 | 0.347 |
| 0.8 | 166 | **0.988** | 0.921 | 0.878 | 0.375 |
| 0.9 | 308 | **0.988** | 0.933 | 0.949 | 0.465 |
| 0.95 | 487 | 1.000 | 1.000 | 0.974 | 0.455 |

SD's one-per-context survivor covers 0.658.

**Reading.** At every τ ≤ 0.9, pruning with G retains more of the mined set's behaviour than the miner's own ranking
and than chance, with 6–32 % of the candidates. But fidelity is low: a merged candidate is close to its
representative over *all* signals, not on *this* trace — the claim to make is coverage, not per-candidate
behavioural equivalence.

---

## 4. RQ5 — semantic drift in LLM formalisations

### 4.1 Requirement set (DeepSTL)

**Purpose.** [paper] Sec. 1: "a similarity score allows for checking whether those candidates agree or have drifted
apart in meaning". Use a public dataset with ground truth, not author-written requirements.

**Setup.** `experiments/rq5_deepstl/deepstl.py`, `generate.py select` → `results/requirements.csv`. [DeepSTL]
`corpus_no_split.csv`: 120 000 English/STL pairs (generated by its authors' grammar). Converted to TABEX syntax and
filtered to the fragment and to tractable size (horizon ≤ 12, ≤ 3 signals). A top-level unbounded `always( … )` is
compared by its body (as in RQ4), for references and answers alike. 60 requirements per surviving DeepSTL type,
seed 0.

**Results.** 8 275 of 120 000 kept. Rejected: `rise`/`fall` edge operators 69 950; string-valued constants (e.g.
`W2 == RYoU_1`) 27 519; horizon > 12 6 619; fractional time bounds 4 013; unbounded inner operators 2 969; other parse
508; > 3 signals 147. Kept by type: invariance/reachability 7 705, immediate response 432, temporal response 138;
**stabilization/recurrence: 0** (all its formulas use edges or strings). Sampled: 180 requirements.

### 4.2 LLM formalisations

**Setup.** `generate.py`. One fixed prompt (grammar of the fragment + the English requirement; answer = one formula).
Temperature 0.8, 3 samples per requirement, seeds 1–3.
- *Gemini 3.8 Flash* (API): one candidate per call (multiple candidates are "not enabled for this model", API error)
  and thinking cannot be disabled (≈ 1 370 output tokens per answer on average). A budget guard priced tokens at the
  2027 list price ($1.50/$7.50 per M input/output, twice the current $0.75/$3.75 per the Gemini API pricing page) and
  stopped at 425 answers (142 requirements: 141 with 3 samples, 1 with 2): 147 824 input and 581 424 output tokens, **$2.29 at current
  prices** ($4.58 at the guard's prices). Requirements were interleaved by type, so the cut is balanced.
- *Qwen2.5-7B-Instruct* (local, ollama 0.12.3 in Docker, CPU): all 540 answers.
- A second local model (Llama 3.1 8B) was dropped: registry pulls failed on DNS timeouts and later ran at ~1 MB/s.

### 4.3 Scoring and independent check

**Setup.** `analyze.py` → `results/{summary.md,scores.csv,rq5.png}`. Answers cleaned (fences, quotes, first line),
converted like the references, parsed. Scored against the reference by G, VolJ, PH/2D, SD, one D per requirement;
120 s budget per answer (each answer in its own killable process). **Independent oracle (does not use TABEX)**:
4 000 random signals per pair, each axis drawn from the atoms of the two formulas' own breakpoints (a constant, a
point strictly between two constants, or beyond the extremes, equally likely); both formulas evaluated by the trace
monitor; *disagreement* = fraction of signals on which exactly one holds.

**Results** (`results/summary.md`).

| model | answers | parsed | not scored (> 120 s) | **G = 1** | exact string match | mean G | mean G when wrong |
|---|---|---|---|---|---|---|---|
| Gemini 3.8 Flash | 425 | 415 | 18 | **376/397 (94.7 %)** | 102 | 0.990 | 0.819 |
| Qwen2.5-7B | 540 | 227 | 10 | **70/217 (32.3 %)** | 21 | 0.702 | 0.561 |

- By DeepSTL type (both models): immediate response 171/219, invariance/reachability 148/214, temporal response
  127/181 correct.
- Parse failures are grammar violations (Qwen 309/540, e.g. `G` used as a signal, `U[1,2]` without a right operand,
  `F[0,infinity)`, a constant on the left of a comparison); Gemini 10/425.
- Drift among the 3 samples of one model: Gemini mean pairwise G 0.996 (337/345 pairs equivalent; 5 requirements
  with any disagreement); Qwen 0.743 (55/138; 44 requirements).
- 352 distinct answer strings, at most 285 semantic classes.
- **Oracle vs G = 1**: G = 1 and a distinguishing signal found: **0/446**. G < 1 and one found: 163/168 (the other 5
  differ on sets too thin for 4 000 samples, e.g. an endpoint).
- **Scored identical although not equivalent**: G 0/168, VolJ 20/168 (float-level), PH 25/117, SD 74/117.
- **Graded severity**: Spearman ρ between each distance and the oracle's disagreement rate over the 168 wrong
  answers: **1 − G 0.011**, 1 − VolJ 0.320, PH/2D 0.334, SD 0.066 (PH/SD undefined for answers with `!=`).

Two cases that explain the last point (`scores.csv`):

| requirement (DeepSTL English, abridged) | answer (Qwen) | reference (DeepSTL) | G | VolJ | PH/2D | disagreement |
|---|---|---|---|---|---|---|
| D35929: "The value of VmGOB05sE will be consecutively 31.15 for each moment within 7 time units." | `G[6,7] (VmGOB05sE == 31.15) && (!VmGOB05sE == 31.15 U[0,1] VmGOB05sE == 31.15)` | `G[0,7] (VmGOB05sE == 31.15)` | 0.000 | 0.000 | — | 0.001 |
| D29478: "On condition that the value of V is larger than 387, and the value of r is no less than 90 then in response the condition that MXZOVH0n will be keeping larger than 0 continuously within 3 time units isn't true." | `!((V > 387 && r >= 90) -> G[0,3] (MXZOVH0n > 0))` | `V > 387 && r >= 90 -> ! (G[0,3] (MXZOVH0n > 0))` | **0.956** | 0.0004 | 0.999 | **0.771** |

- In the first, both formulas are almost never satisfied, so a behavioural rate calls them "agreeing"; G compares the
  constraints and sees different windows. This favours G.
- In the second, the answer is A ∧ ¬B, the reference ¬A ∨ ¬B: they disagree on every signal where the antecedent is
  false. VolJ and PH see it; **G = 0.956**. The two regions differ completely on one axis (V > 387 vs V ≤ 387) and agree
  elsewhere. Box_sim ([paper] Eq. 6) averages Point_sim over all |T1 ∪ T2|·Nvars axes and Point_sim ([paper] Eq. 5)
  scores two undefined constraints as 1, so a total disagreement on one of n axes costs only 1/n.

### 4.4 Pilot (superseded)

`experiments/rq5_pilot/`: 12 hand-written ARCH-COMP-style requirements, 9 runs of Claude Haiku/Sonnet/Opus as
in-session subagents (no temperature control, no API). 41 distinct strings, 16 semantic classes; drift only on the
three ambiguous requirements (`rpm != 4750` for "never reach 4750", G = 0.75; readings of "every window of 3 time
units", 0.83–0.98; a one-instant boundary shift, 0.95). Qualitative example only.

---

## 5. Discussion: what helps, what hurts, and how to fix it

### 5.1 What the results support

1. **Exact identity — the paper's main claim ([paper] Sec. 6, "G(φ, ϑ) = 1 ⇐⇒ φ ≡ ϑ").** Confirmed in every setting,
   including by an oracle that does not use TABEX: 1000/1000 random equivalent rewrites (§1.2), 0 of 2792 mutants
   called identical (§1.2), 0/446 G = 1 answers with a distinguishing signal and 0/168 wrong answers called
   identical (§4.3). Every baseline fails here: SD misses 72/1000 equivalent pairs and is blind to 30–54 % of
   mutants and to 74/117 wrong LLM answers; PH is blind to all strictness changes and to 25/117 wrong answers; VolJ
   is numerically blind on endpoint-only differences (20/168).
2. **The canonical form is useful in practice.** Exact string match credits 102 correct Gemini answers where G
   certifies 376, and 21 vs 70 for Qwen (§4.3) — syntactic accuracy grossly understates NL→STL quality. Reference-free
   drift separates a stable translator (mean pairwise G 0.996) from an unstable one (0.743).
3. **Box-by-box comparison is justified** against the natural alternative: VolJ is driven by grid dimension (to 0
   under G, towards 1 under F, §1.4); G is not.
4. **Pruning mined candidates works** where the baselines do not: G-pruning keeps 0.97–0.99 of trace coverage vs
   0.92–0.93 for the miner's ranking at the same size (§3.5); SD cannot separate any two Slam candidates (§3.4);
   STLSat is slow and answers a dense-time question (§3.3).
5. **The fast engine makes the method usable** (§1.3): three orders of magnitude over the reference pipeline, and
   ahead of PH on G∘F and U. The fragment covers 22/23 ARCH-COMP requirements with difference signals (§1.5).
6. **RQ3 holds analytically** (§2).

### 5.2 What hurts, in order of risk, and possible fixes

**1. The graded value of G on non-equivalent formulas is weakly grounded (high risk).**
*Evidence:* ρ = 0.011 between 1 − G and behavioural disagreement over 168 wrong LLM answers, against 0.32–0.33 for VolJ
and PH (§4.3); `¬(A→B)` vs `A→¬B` scores 0.956 (§4.3); ρ(1−G, 1−VolJ) = 0.05 on the RQ2 suite (§1.4). A reviewer who
builds the `¬(A→B)` example will argue that G does not measure semantic closeness.
*Mitigating facts:* the oracle's disagreement rate is itself a volume-type quantity (probability mass under one
chosen signal distribution), so it naturally agrees with VolJ and PH; and G grades controlled perturbations well
(τ 0.92–1.0, §1.2). The problem is specific: *dilution* — a total disagreement on one axis is averaged with many
undef/undef agreements.
*Possible fixes:*
- (a) **Average only over constrained axes**: in Box_sim ([paper] Eq. 6), sum and normalise over the axes where at
  least one of the two boxes is defined, not over all |T1 ∪ T2|·Nvars. Identity (Lemma 1) still holds: two boxes that
  agree on every axis either constrains are equal. A rule is needed when neither box constrains anything.
- (b) **Weight axes** by how much the constraint restricts (e.g. 1 − |ĉ|_ε/|D|_ε), so an unconstrained match weighs
  nothing and a tight constraint weighs a lot.
- Either variant must be re-run on the graded experiments (§1.2 part 2, §1.4, §4.3) to check it removes the dilution
  without re-introducing VolJ's dimension dependence. That is a few hours of computation with the existing scripts.
- Minimum fix, no change to the definition: position G as a *structural* (per-constraint) similarity whose headline
  property is exact identity, show the dilution example in the paper, and do not claim that G's value predicts
  behavioural disagreement.

**2. "Metric" is incorrect (certain, easy to fix).** 43 142 triangle-inequality violations (§1.6). Fix: call G a
similarity measure and 1 − G a semimetric; cite the counterexample. If a metric is wanted, the shortest-path closure of
1 − G is one, but it loses the direct interpretation.

**3. Discontinuity at ⊤ (moderate).** Any non-equivalent formula scores G = 0 against ⊤, even one that differs on a
single point (§1.2), and G(⊤, φ) = 0 for every constrained φ (§1.1), whereas VolJ(⊤, x>0) = 0.5. Cause: ⊤'s canonical
box constrains nothing, trimming ([paper] Sec. 4.2) leaves it an empty time domain, and Eq. 5's second case scores
"exactly one of c1, c2 is undef" as 0 ([paper] Eq. 5). *Possible fixes:* treat undef as the full D-window, so
Point_sim(undef, c) = |ĉ_D|_ε / |D|_ε — consistent with Def. 2, and identity survives because every defined
constraint has ĉ_D ⊊ D ([paper] Sec. 5.2); and do not trim a box whose time domain would become empty. At minimum,
state the behaviour at ⊤ explicitly.

**4. Scalability (moderate, already acknowledged by [paper] Remark 2).** Exponential in |V| on F-type families
(§1.3); 10/23 ARCH-COMP requirements not scored in 60 s (§1.5); RQ4 needed `maxd` ≤ 10; 28 LLM answers exceeded 120 s
(§4.3). *Possible fixes:* coarser Δt (changes the formula — should be measured); variable ordering in the diagram;
bounded-width (beam) Viterbi vectors as an approximate mode with an error bound; and actually implementing the reuse
of [paper] Remark 3.

**5. [paper] Remark 3 contradicts Definition 1 (text fix).** Remark 3: "When many formulas are compared pairwise over
one grid, each diagram is built once". But Def. 1 fixes the grid per pair: "We take V exactly equal to this union"
([paper] Sec. 4). In a batch whose formulas mention different signals, the grid changes from pair to pair, so
diagrams cannot be reused (RQ4 rebuilt regions for every pair). Fix: qualify Remark 3 (reuse holds among formulas
over the same signals), or allow a fixed batch-wide V and state that it shifts scores (undef/undef axes — the same
dilution as point 1).

**6. Non-monotonicity (low).** 5/240 constant-shift sequences where G decreases (§1.2). Fix: claim no monotonicity;
one sentence with an example.

**7. RQ4 caveats (low–moderate).**
- Fidelity 0.31–0.47 (§3.5): claim coverage, not per-candidate behavioural equivalence.
- The outer unbounded G of Slam's assertions is dropped; justify it (shared by all candidates) or check the
  ranking under a bounded closure `G[0,k]`.
- `maxd` capped at 10 is a deviation from Slam's shipped configurations; say why (cost).
- The STLSat comparison invites a dispute about semantics; present it as a cost remark and note the dense/discrete
  difference, rather than as a correctness result.

**8. RQ5 caveats (moderate).**
- DeepSTL's English is grammar-generated, and the filter removes all `rise`/`fall` and string-valued requirements
  (the whole stabilization/recurrence type) — the requirement set is biased towards simpler shapes.
- Gemini is near ceiling (94.7 % correct), so most graded evidence comes from Qwen.
- Two models, one per vendor type; Gemini budget-limited to 142 of 180 requirements.
- The oracle's signal distribution is a choice; a different one would move the ρ values. Report it as such.

**9. Baseline fairness (must be stated).**
- SD's zero-on-Slam result and several of its equivalence failures depend on resolving `||` by the most
  favourable alternative, which [Madsen] leaves open (§1.1).
- PH is solved with scipy/HiGHS instead of Gurobi ([repo] `madsen/metrics.py`); only times, not values, should depend
  on that.
- PH is blind to strictness by construction ([Madsen] closed languages), not by accident.

**10. Data provenance to double-check before submission.**
- ARCH-COMP constants (transcribed from memory, §1.5).
- The one Table I cell where the reproduction differs from [Madsen] (0.83 vs 0.84, §0).

### 5.3 Bottom line

The experiments strongly support the claim the paper can actually prove — a canonical, exact representation in which
equivalence is detected with neither false positives nor false negatives, where every baseline fails — and they
justify the box-by-box design against volume. They do not support reading G's value as a measure of behavioural
distance between non-equivalent formulas. The paper should be framed accordingly, fix the terminology ("metric") and
the ⊤ behaviour, and either adopt a constrained-axes variant of Box_sim (to be evaluated with the existing scripts)
or show the dilution example itself.
