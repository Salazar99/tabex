# Experiments tracker

Status of the paper's experimental research questions against what exists in this repository.
Full write-up of every result, with setup, sources and a discussion of strengths and weaknesses: `RESULTS.md`.
Legend: ✅ done · 🟡 partial · ⬜ not started. Numbers are reproducible with the command shown next to them.
Every TABEX score in RQ2–RQ5 is computed by `tabex_fast` (same number as the reference pipeline: checked by
`tests/test_tabex_fast.py`, and again on the 74 timing points where both finished — max difference 1.1·10⁻¹⁵).

| RQ | Topic | Status |
|---|---|---|
| RQ2 | Baseline comparison (PH, SD) and computational performance | ✅ scores, equivalent-pair block, timing study |
| RQ3 | Sensitivity of the domain parameter D | ✅ sweep, closed form verified, plot |
| RQ4 | Redundancy pruning in specification mining | ✅ Slam (develop) candidates, clustering, STLSat baseline |
| RQ5 | Semantic drift in LLM translations | ✅ DeepSTL: Qwen 180 req. × 3, Gemini 142 req. × 3 (budget), oracle-checked |

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
- **Comparison run**: `python -m madsen.compare -o madsen/results.md` — 45 pairs in three blocks: the 10 manual
  benchmark pairs, all 21 pairs of Madsen's Example 1 at horizon 20, and 14 syntactically different but
  **equivalent** pairs. Same domain for both sides (TABEX's D, S = [-D, D]).
- **Timing study**: `python experiments/timing.py` → `experiments/results/timing.{csv,png}`.

### Steps
| Step | Status | Notes |
|---|---|---|
| Diverse test suite, equivalent + partially overlapping | ✅ | 31 non-equivalent pairs + 14 equivalent (`EQUIVALENT` in `madsen/compare.py`), pinned by `tests/test_experiments.py`. |
| Run G, PH, SD over the suite | ✅ | `madsen/results.md` |
| Compare scores, conceptual differences | ✅ | Observations below. |
| Time vs formula complexity (horizon T, #variables) | ✅ | 4 families × \|V\| ∈ 1..5 × T ∈ {2..40} × 4 methods, 60 s / 3 GB per run. |

### Observations (from `madsen/results.md`)
- **Equivalent block (rows 32–45)**: TABEX scores all 14 at exactly 1, PH all 14 at 0, **SD misses 5 of 14**:
  `F[0,1]x>0` vs `F[0,0]x>0 || F[1,1]x>0` (0.50), `F[0,1]F[0,1]x>0` vs `F[0,2]x>0` (0.25),
  `(x>=0||x<0) U[0,2] y>0` vs `F[0,2]y>0` (0.25), and the two interval-union rewrites
  `G/F[0,2]((0<x<2)||(1<x<3))` vs `G/F[0,2](0<x<3)` (0.125, 0.0625). Causes: AoS encodes `F` as a mandatory
  δ-hold per window, and resolves `||` to one alternative rather than the union. TABEX's canonical form is what
  makes identity robust to rewriting; PH gets it right because it works on the language, but see below.
  (At horizon 0 every AoS box has zero width, so SD is 0 for every pair — the block is kept at horizon ≥ 1.)
- **PH saturates on one-sided constraints**: all 10 benchmark pairs get PH/2D = 0.5 — one extreme sample
  decides it — while TABEX ranges 0–0.97 over the same pairs.
- **SD scores 0 on non-equivalent pairs**: rows 4 (`G(x>0)` vs `G(x>0 || y>0)`), 6, 10 (`F[0,4]` vs `F[0,2]`) —
  the AoS choice set (`||`) resolved to its most favourable alternative hides the difference. TABEX: 0.42, 0.24, 0.59.
  So SD has both false "equivalent" verdicts (these) and false "different" ones (the equivalent block).
- **Opposite verdicts**: row 2 (`F[0,2]` vs `F[3,4]`, disjoint windows) and row 3 (same formula on different
  variables): TABEX 0 (fully dissimilar), Madsen moderate distances.
- **⊤ (rows 11–16)**: TABEX scores `true` 0 against every constrained formula (its canonical box trims to an empty
  time domain, Eq. 6); Madsen treats ⊤ as the superset. A definitional difference worth a sentence in the paper.
- **Rank correlation** of TABEX distance (1 − G) over the 31 non-equivalent pairs: vs PH −0.035, vs SD 0.638.

### Timing (`experiments/results/timing.png`)
Pair per point: the family instantiated with θ1 = [0.2, 0.4] and θ2 = [0.2, 0.44] on every variable
(partially overlapping, no identity shortcut). Families: `G[0,T]θ`, `F[0,T]θ`, `G[0,T-2]F[0,2]θ`,
`θ_lo U[0,T] θ_hi`. Each run in a fresh process (8 in parallel on 32 cores), min of ≤ 3 repetitions; a
timeout/memout ends that series. Largest T finished within 60 s, for |V| = 1/2/3/4/5:

| family | reference pipeline | tabex_fast | PH (2 MILPs) | SD |
|---|---|---|---|---|
| G | 40/40/40/40/40 | 40/40/40/40/40 | 40/40/40/40/40 | 40/… |
| F | 4/2/–/–/– | 40/20/12/8/6 | 40/28/12/8/8 | 40/… |
| G∘F | 4/2/–/–/– | 40/16/8/6/4 | 8/6/4/4/4 | 40/… |
| U | 4/2/–/–/– | 40/24/16/12/10 | 24/6/4/4/2 | 40/… |

- **G** is cheap for everything (one canonical cell): ≤ 0.7 s at T = 40, |V| = 5.
- **tabex_fast vs reference**: the reference pipeline enumerates canonical cells and dies at T ≈ 4 on every
  F-type family (31.7 s for `F[0,4]` with one variable, 0.013 s in tabex_fast). With one variable tabex_fast
  grows polynomially in T (F: 0.43 s at T = 20, 3.9 s at T = 40; ≈ T^3.2).
- **tabex_fast vs PH**: comparable on F (PH reaches slightly further at |V| = 2 and 5), clearly ahead on G∘F
  and U (U, |V|=1, T=20: 0.23 s vs 24.4 s; PH's U encoding hits the 3 GB cap at T = 28).
- **SD** is milliseconds everywhere — it is an over-approximation over AoS boxes (see the equivalent block for
  what that costs in accuracy).
- **Both exact methods are exponential in |V|** on F-type families. For tabex_fast the cost is the number of
  distinct DP states (Viterbi vectors over the partner's diagram), which grows with the number of per-instant
  atoms; it is polynomial in T for fixed |V| on these families but not guaranteed polynomial in general.

### Performance claim, stated precisely
Endpoints and the canonical form are exact (Fractions); the score itself is summed in floats. tabex_fast's cost
is bounded by the number of distinct DP states, which is small on these families but not guaranteed polynomial.

### Generated suite (`python experiments/random_suite.py` → `experiments/results/random_suite.md`)
Answers the "hand-picked pairs" objection: nothing here is chosen by the authors.

**Part 1 — 1000 random equivalent pairs** (random formula + one of the 28 meaning-preserving rewrites of
`verification/verify_equivalence.py`): G, VolJ and PH report identity on 1000/1000; **SD misses 72/1000**
(43 "nested F collapses" `F[0,1]F[0,1]φ ≡ F[0,2]φ`, 29 "U with a true invariant" `⊤ U[a,b] φ ≡ F[a,b]φ`).

**Part 2 — controlled perturbations**: 300 random bases × 11 graded mutants (constant shifted by Δ = 1..4; outer
window shifted / widened by k = 1..3; one atom's strictness flipped), one D = 8 throughout; 508 mutants equivalent
to their base (G = 1) dropped, 2792 kept.

| measure | const Δ: blind / monotone / Kendall τ | shift k | widen k | strictness flip: blind |
|---|---|---|---|---|
| 1 − G | 0/956 · 235/240 · 0.924 | 0/804 · 268/268 · 0.991 | 0/804 · 268/268 · 1.000 | 0/228 |
| 1 − VolJ | 1/956 · 228/240 · 0.929 | 0/804 · 268/268 · 0.965 | 0/804 · 268/268 · 1.000 | 3/228 (≈1e-10, float floor) |
| PH/2D | 8/956 · 240/240 · 0.954 | 0/804 · 255/268 · **0.006** | 0/804 · 252/268 · **0.047** | **228/228** |
| SD | **299/956** · 240/240 · 0.687 | **205/804** · 157/268 · 0.346 | **431/804** · 268/268 · 0.466 | **228/228** |

("blind" = scored as identical although not equivalent; "monotone" = severity sequences whose distance never
decreases; τ = mean Kendall τ between severity and distance.)
- G never calls a non-equivalent mutant identical, and grades all three families (τ 0.92–1.0).
- PH grades constants perfectly (it *is* a value-space distance) but is flat in time: τ ≈ 0 for window shifts
  and widenings — the worst-case gap saturates after the first step. It is blind to strictness by design.
- SD is blind to 30–54 % of mutants in every family.
- **G is not always monotone**: 5/240 constant sequences decrease (VolJ: 12). Examples in
  `random_mutations.csv`: widening `x∈[3,3]` towards D, or a disjunct `x>c` that swallows its neighbour `x<0`,
  where the region stops growing and box matching re-balances. Worth a sentence; no claim of monotonicity.
- **Discontinuity at ⊤**: base `F[0,3]G[1,2](y<1 ∨ x≤1 ∨ y>−1)` is a tautology; the mutant `y<−1 ∨ …` differs only
  on the point y = −1 (with x > 1) and scores **G = 0** (VolJ: 1 − 5·10⁻¹⁶). Any non-equivalent formula scores 0
  against ⊤ (rows 11–16 above): the all-undef box of ⊤ trims to an empty time domain and matches nothing.

### Ablation: G vs exact volume Jaccard (`python experiments/volume_ablation.py`, `tabex_fast/volume.py`)
VolJ = |S(φ) ∩ S(θ)|_ε / |S(φ) ∪ S(θ)|_ε on [−D, D]^A, computed exactly on one joint decision diagram (ms per
pair). It is the obvious alternative a reviewer will ask about; it is also 1 exactly on equivalent pairs
(14/14 in the equivalent block, 1000/1000 above).
- **Volume is driven by dimension** (`volume_ablation.png`): `G[0,T]θ1` vs `G[0,T]θ2` — G = 0.8333 for every T and
  |V|; VolJ = (5/6)^{(T+1)|V|}: 0.022 at T = 20, 1.8·10⁻¹⁰ at T = 40, |V| = 3. Under `F[0,T]` VolJ drifts the other way
  (0.83 → 0.975 as T grows, both regions filling the box) and depends on |V| (0.58 vs 0.83 at T = 0), while G stays
  0.83–0.93 whatever |V|. The per-axis average of Box_sim is what keeps the score about the constraint, not about
  the number of axes.
- Rank agreement over the 31 non-equivalent RQ2 pairs (`volume_suite.csv`): ρ(1−G, 1−VolJ) = 0.05,
  ρ(1−VolJ, PH) = 0.60, ρ(1−G, SD) = 0.64 — G and VolJ order pairs very differently.
- VolJ is the better *value-space* measure in one respect: `true` vs `x>0` is 0.5, not 0 (see ⊤ above).

### Realistic specifications: ARCH-COMP FALS (`python experiments/archcomp.py` → `experiments/results/archcomp.md`)
23 requirements of the ARCH-COMP falsification category (AT, AFC, NN, NNx, CC, F16, SC), written from the
competition report (constants to be double-checked against the report cited), discretised at Δt = 1 s with
windows rounded outward.
- **In the fragment as stated: 16/23**; with difference signals d_ij = y_i − y_j introduced as signals (as RQ4 does
  for Slam's derivative): **22/23** — only NN (|Pos − Ref| against 0.005 + 0.03|Ref|) is out.
- **Scored within 60 s** (self and vs a copy with every constant × 1.05, 0 → 0.5): **13/23**; the failures are
  the long F-type horizons — AT51–54 (T = 34, `F[0,1] G[0,3]` under `G[0,30]`; AT54 finished in 59.8 s in a first run; both
  runs shared the CPU with the 30-process STLSat baseline, so all times here are pessimistic), AFC27 (T = 55), CC2–CC5 (T = 100–115,
  G∘F / G∘F∘G). G-only requirements at T = 50–100 take ≤ 1 s (CCx, 4 signals: 1.0 s).
- So the fragment covers the benchmark almost entirely; the limit is the cost of nested temporal operators at
  horizons ≳ 30 steps, i.e. the time discretisation. A coarser step (Δt = 2 s halves every T) is the practical
  knob; its effect on the score is not studied here.

### Is 1 − G a metric? (`python experiments/metric_properties.py` → `experiments/results/metric_properties.md`)
**No.** On all 62.5 M ordered triples of the RQ4 matrices, the triangle inequality fails 43 142 times (0.069 %);
worst: d(a,c) = 0.485 > d(a,b) + d(b,c) = 0.364 (three FuelControl candidates, formulas in the report). 1 − G is a
semimetric (symmetric, 0 exactly on equivalent formulas). The paper should say "similarity measure", not
"metric", and can cite this counterexample.

---

## RQ3 — Sensitivity of the domain parameter D

*How does D affect sensitivity to discrepancies in unbounded constraints?*

`python experiments/d_sensitivity.py` → `experiments/results/d_sensitivity.{csv,png,txt}`.
D log-spaced from max|c| + 0.01 to 10⁴ (41 points; 21 for temporal pairs).

| Step | Status | Notes |
|---|---|---|
| Select one-sided pairs differing only in offset | ✅ | `x>2` vs `x>2+Δ` and `x<-2` vs `x<-2-Δ`, Δ ∈ {0.5, 1, 3, 10}; `x>=2` vs `x>2` (Δ = 0); controls `[2,5]` vs `[2,8]`, `[2,5]` vs `x>2`. |
| Compute Point_sim_D over a wide D range | ✅ | Also full G on `G[0,2]`, `F[0,2]`, `U[0,2]` versions (tabex_fast). |
| Plot, show monotone increase to 1 | ✅ | Monotone in every offset pair; closed form verified. |

### Results
- **Closed form, verified at every D** (the script asserts it): for `x>c1` vs `x>c2`, c1 < c2,
  Point_sim_D = (D − c2)/(D − c1 + ε), i.e. 1 − Δ/(D − c1) up to ε. Plotted against (D − c1)/Δ, all four Δ
  collapse onto one curve (middle panel): **what matters is D relative to the offset**. The `<` direction gives
  the identical values (mirror symmetry). Example: `x>2` vs `x>5` is 0.0033 at D = 5.01, 0.77 at D = 15,
  0.9997 at D = 10⁴.
- **G equals Point_sim_D** on single-instant, single-variable pairs (asserted), and on `G[0,2]` versions
  (identical curve). `F[0,2]` and `U[0,2]` versions start higher (0.34, 0.62 at D = 5.01) — in their canonical
  cells the offset constraint occupies only some of the (instant, variable) slots, the rest match — and rise to 1
  the same way.
- **Endpoint only** (`x>=2` vs `x>2`): 1 − ε/(D − 2 + ε), i.e. 0.9999 at D = 2.01 and 1.0000 beyond — the ε-measure
  distinguishes them without letting a single point matter.
- **Controls**: bounded vs bounded is flat (0.5 for every D > 8), so D only acts on unbounded tails; bounded vs
  unbounded *decreases* to 0 (0.9967 → 0.23 at D = 15 → 0.0003 at 10⁴), as the unbounded side's mass grows.
- **Contrast with the earlier draft's Eq. 4** (1/(1 + dist), dist = gap between finite endpoints, recovered from
  git history): fixed at 1/(1+Δ) = 0.67, 0.5, 0.25, 0.09 for the four offsets, whatever the domain. It also gives
  `[2,5]` vs `x>2` a fixed 0.4, while the D-truncated Jaccard goes anywhere in (0, 1) depending on D — Eq. 5 makes
  the dependence on the assumed signal range explicit instead of hiding it in a constant.

---

## RQ4 — Redundancy pruning in specification mining

*Can G cluster and prune redundant candidate formulas returned by specification miners?*

Miner: **Slam** (https://github.com/Salazar99/Slam), branch `develop` (e195c41), built against the antlr4
4.13.2 runtime in `~/harm/third_party` (Slam's own `install_antlr.sh` leaves the headers out).

```bash
python experiments/rq4/mine.py               # Slam on its 6 case studies -> results/candidates.csv
python experiments/rq4/similarity_matrix.py  # all pairwise OWSim/G per context -> results/pairs.csv.gz
python experiments/rq4/stlsat_baseline.py    # Slam's --remove-impl (STLSat) -> implications.csv, stlsat_kept.csv
python experiments/rq4/prune.py              # clustering + comparison -> summary.md, reduction.{csv,png}
```

| Step | Status | Notes |
|---|---|---|
| Collect a large batch of mined candidates | ✅ | 951 candidates, 9 contexts, 6 case studies; **0 rejected** as `UnsupportedFormula`. |
| Pairwise one-way and global similarity | ✅ | 107 072 pairs, 1060 s wall on 30 workers (13 000 CPU-s; FuelControl is 87 % of it). |
| Threshold clustering, one representative per cluster, reduction rate | ✅ | Leader clustering on G in Slam's rank order. |

### Setup decisions
- **Case studies and hints are Slam's own** (`tests/` of develop: WaterTanks, Heater, Gearbox, Controlled_PU,
  Engine_timing, Fuel_control), with the shipped configs, changed only in: `maxd` capped at 10 (keeps mined
  windows ≤ 30 steps — at the shipped 100 a single pair did not finish in 10 min), and Controlled_PU's
  commented-out mining contexts re-enabled (it ships with only an assertion check active). Configs used are in
  `experiments/rq4/configs/`.
- **Translation** (`mine.py::to_tabex`): Slam emits `G(ant -> cons)` with an unbounded outer `G`, common to every
  candidate; the body is compared. Slam's derivative `@(v,k)` becomes a fresh signal `v_dk`.
- **One D per context** (max|c| over the context + 1), so a context's matrix is on one scale; pairs are compared
  within a context (one template/consequent — where the redundancy is).
- **G, not OWSim, for clustering**: OWSim(a→b) = 1 says a's cells all have a perfect match in b, not that b says
  everything a does. Only 2 ordered pairs out of 214 144 have OWSim = 1 anyway.

### Results (`experiments/rq4/results/summary.md`, `reduction.png`)
Kept candidates (reduction rate) under leader clustering at threshold τ:

| case | n | τ=0.8 | τ=0.9 | τ=0.95 | τ=0.99 | τ=1 | STLSat |
|---|---|---|---|---|---|---|---|
| WaterTanks | 46 | 11 (76 %) | 19 (59 %) | 31 (33 %) | 40 (13 %) | 46 (0 %) | 43 (7 %) |
| Heater | 12 | 9 (25 %) | 10 (17 %) | 11 (8 %) | 11 (8 %) | 12 (0 %) | 6 (50 %) |
| Gearbox | 166 | 24 (86 %) | 33 (80 %) | 49 (70 %) | 63 (62 %) | 166 (0 %) | 161 (3 %) |
| ControlledPU | 350 | 60 (83 %) | 116 (67 %) | 171 (51 %) | 274 (22 %) | 350 (0 %) | 341 (3 %) |
| EngineTiming | 6 | 3 (50 %) | 3 (50 %) | 5 (17 %) | 5 (17 %) | 6 (0 %) | 6 (0 %) |
| FuelControl | 371 | 59 (84 %) | 127 (66 %) | 220 (41 %) | 362 (2 %) | 371 (0 %) | 363 (2 %) |
| **all** | 951 | 166 (83 %) | 308 (68 %) | 487 (49 %) | 755 (21 %) | 951 (0 %) | 920 (3 %) |

**STLSat baseline** (`stlsat_baseline.py`, Slam's `--remove-impl` re-implemented: same greedy walk, same
same-proposition filter, same `G(` → `G[0,100](` wrapping, same `stlsat` query `(b) && !(a)`; parallel and with a
60 s timeout per check): 1645 same-proposition pairs → 3290 checks, **3211 timed out (97.6 %)**, 79 decided
"implied"; **194 161 CPU-s (≈ 54 CPU-hours) against 12 954 CPU-s for all 107 072 TABEX pairs**. It removes 31 of
951 candidates (3 %). Two caveats:
- *Semantics.* `stlsat` decides dense-time STL by default, which is what Slam calls. On 18 of the pairs it declares
  mutually implied (equivalent), the discrete-time bodies are not equivalent: e.g. `… F[7,16] map∈… → F[7,16] afr>10`
  vs `… F[7,15] … → F[7,15] …` — the signal with fuel at t=0, ego at 4, map at 15 and afr > 10 only at 16 satisfies
  `G[0,100]` of the first and violates the second (checked with the trace monitor), yet `stlsat` answers unsat in
  0.004 s. With `--mltl` (discrete time) a single such check did not finish in 900 s. So the baseline answers a
  different question than TABEX (and the traces) do, and answers the right one too slowly to be usable.
- *Binary.* Both the TABEX fork of stlsat (a local build in `m_stlsat/`, not committed; its source was removed from the repo in 6190e6f) and upstream `ZamponiMarco/stlsat` master (16e5ea6; the `fix` branch
  Slam's installer names no longer exists) give the same verdicts on the checks above; the run used the fork.
- G on the 79 "implied" pairs: mean 0.65, range 0.08–0.94 — implication (a partial order) and closeness are
  different relations; a strong antecedent implies a weak one while the two stay far apart.

**SD as the clustering distance** (`sd_matrix.py`): SD is **0 on all 107 072 pairs**. Every candidate of a
context is `ant → cons` with the same consequent, i.e. `¬ant ∨ cons`; SD resolves `∨` to the most favourable pair
of alternatives, and the shared `cons` alternative matches exactly. SD-clustering therefore keeps one candidate
per context at every threshold (9/951) — it cannot tell mined candidates apart.

### Pruning quality on the traces (`quality.py` → `results/quality.md`)
Reduction rate alone is arbitrary, so each candidate's antecedent is monitored on its own trace (Slam's derivative
semantics reproduced; the monitor is cross-checked against the signal space in `tests/test_experiments.py`).
*Coverage* = share of the instants activated by some candidate of a context that a kept candidate still
activates; compared at the **same number of kept candidates** with Slam's own top-k ranking and with random
subsets (mean of 50):

| τ | kept | coverage, G-pruning | top-k by Slam rank | random | fidelity (pruned vs its representative) |
|---|---|---|---|---|---|
| 0.5 | 54 | **0.973** | 0.921 | 0.579 | 0.307 |
| 0.7 | 110 | **0.988** | 0.921 | 0.709 | 0.347 |
| 0.8 | 166 | **0.988** | 0.921 | 0.878 | 0.375 |
| 0.9 | 308 | **0.988** | 0.933 | 0.949 | 0.465 |
| 0.95 | 487 | 1.000 | 1.000 | 0.974 | 0.455 |

- At every τ ≤ 0.9, G-pruning keeps more of the behaviour the mined set describes than the miner's own ranking and
  than chance, with 6–32 % of the candidates. SD's single survivor per context covers 0.658.
- *Fidelity* (Jaccard of the activation sets of a pruned candidate and its representative) is only 0.3–0.47: G
  measures closeness over all signals, not agreement on this trace, so a merged candidate is "near" its
  representative semantically without firing at the same instants. Coverage is the right claim; "the
  representative behaves like each merged candidate on the trace" is not supported.

---

## RQ5 — Semantic drift in LLM translations

*How well does G quantify drift among multiple LLM formalisations of one natural-language requirement?*

```bash
python experiments/rq5_deepstl/generate.py select                      # requirement set
GOOGLE_API_KEY=... python experiments/rq5_deepstl/generate.py gemini  # budget-guarded
python experiments/rq5_deepstl/generate.py ollama                      # local model (docker ollama)
python experiments/rq5_deepstl/analyze.py                              # -> results/summary.md, scores.csv, rq5.png
```

| Step | Status | Notes |
|---|---|---|
| Requirement set with ground truth | ✅ | DeepSTL (He et al., ICSE 2022), 120 000 English/STL pairs, filtered to the fragment (`deepstl.py`), 60 per type, seed 0. |
| Several formalisations per requirement, ≥ 2 models, reproducible | ✅ | Gemini 3.8 Flash (API) and Qwen2.5-7B-Instruct (local, ollama 0.12.3); temperature 0.8, 3 samples, seeds 1–3; raw answers in `samples.jsonl`. |
| Score vs reference and pairwise; validate against an independent oracle | ✅ | G, VolJ, PH, SD; sampling oracle independent of TABEX. |

### Data
- **Fragment filter over the 120 000 DeepSTL formulas**: 8 275 kept. Rejected: `rise`/`fall` 69 950, string-valued
  constants 27 519, horizon > 12 6 619, fractional time bounds 4 013, unbounded inner operators 2 969, other
  parse 508, > 3 signals 147. DeepSTL's `stabilization_recurrence` type does not survive at all (edges and strings);
  the other three do: invariance/reachability 7 705, immediate response 432, temporal response 138.
- A top-level unbounded `always ( … )` is compared by its body, for references and answers alike (as in RQ4).
- **Gemini 3.8 Flash**: thinking cannot be switched off (≈ 1 200 output tokens per answer) and there is one
  candidate per call. The budget guard (list prices of 2027, $1.50 / $7.50 per M tokens, i.e. twice the current
  ones) stopped it at 425 answers, 142 requirements × 3, estimated $4.58 at those prices (≈ $2.3 at current prices).
- **Qwen2.5-7B**: all 540 answers. (A second local model, Llama 3.1 8B, was dropped: the registry pull failed and later
  ran at ~1 MB/s, and CPU generation is ~10 s per answer.)

### Results (`results/summary.md`)
| model | answers | parsed | not scored (> 120 s) | **G = 1 (correct)** | exact string match | mean G | mean G when wrong |
|---|---|---|---|---|---|---|---|
| Gemini 3.8 Flash | 425 | 415 | 18 | **376/397 (94.7 %)** | 102 | 0.990 | 0.819 |
| Qwen2.5-7B | 540 | 227 | 10 | **70/217 (32.3 %)** | 21 | 0.702 | 0.561 |

- **String match badly under-counts correctness**: 102 vs 376 (Gemini), 21 vs 70 (Qwen) — the accuracy metric
  used by syntactic NL→STL evaluations. G certifies semantic correctness exactly.
- **Parsing failures are grammar violations, not fragment limits**: Qwen 309/540 (`G` used as a signal, `U[a,b]`
  without operands, `[0,infinity)`, constant on the left of a comparison); Gemini 10/425. Reported separately
  from drift.
- **Drift among the samples of one model**: Gemini mean pairwise G 0.996 (337/345 sample pairs equivalent; 5
  requirements with any disagreement); Qwen 0.743 (55/138; 44 requirements). The same measure, no reference needed,
  separates a stable translator from an unstable one.
- **352 distinct answer strings, at most 285 semantic classes** (answers equivalent to the reference merged).

### Independent check (sampling oracle, not TABEX)
Random signals, each axis drawn from the atoms of the two formulas' own breakpoints; both formulas evaluated by
the trace monitor (cross-checked against the signal space in `tests/test_experiments.py`).
- **G = 1 and a distinguishing signal found: 0/446.** G < 1 and one found: 163/168 (the other 5 differ on sets
  too thin to hit, e.g. single endpoints).
- **Scored as identical although not equivalent**: G 0/168, VolJ 20/168 (float-level, 1 − VolJ ≤ 10⁻⁹ on
  endpoint/point differences), PH 25/117, SD 74/117.
- **Graded severity — a negative result for G**: Spearman ρ between distance and the oracle's disagreement rate,
  over the 168 wrong answers: **1 − G 0.011**, 1 − VolJ 0.320, PH/2D 0.334, SD 0.066. G's value on a *wrong*
  answer does not predict how often it disagrees with the reference on sampled signals. Two cases show why
  (`scores.csv`):
  - `G[6,7](v==31.15) ∧ …` vs `G[0,7](v==31.15)`: G = 0, disagreement 0.001 — both are almost never true, so they
    "agree" behaviourally; G compares the constraints and finds different windows. (Base-rate effect; favours G.)
  - `¬(A → B)` vs `A → ¬B`: **G = 0.956**, disagreement 0.77. The two differ completely on one axis (V > 387 vs
    V ≤ 387) and agree elsewhere; Box_sim averages over all (t, v) axes and counts undef/undef as 1, so a total
    disagreement on 1 of n axes costs 1/n. **This dilution is the price of G not collapsing like VolJ (see the
    ablation), and it is the most likely reviewer objection to the graded part of G.** A possible fix, not
    implemented: average Point_sim only over axes constrained by at least one of the two boxes (the identity
    proof of Lemma 1 is unaffected; the ⊤ case would need its own rule).

### Pilot (superseded)
`experiments/rq5_pilot/`: 12 hand-written requirements × 9 runs of Claude Haiku/Sonnet/Opus subagents (no temperature
control). 41 distinct strings, 16 semantic classes; drift only on the three ambiguous requirements (`rpm != 4750`
for "never reach", G = 0.75; window readings, 0.83–0.98). Kept as a qualitative example, not as evidence.

---

## Reproducing everything

```bash
pytest -q                                     # incl. Table I, fast-vs-reference, tests/test_experiments.py
python -m madsen.compare -o madsen/results.md # RQ2 scores (~1 min)
python experiments/timing.py                  # RQ2 timing (~1 h on 8 workers)
python experiments/d_sensitivity.py           # RQ3 (~1 min)
python experiments/rq4/mine.py && python experiments/rq4/similarity_matrix.py \
  && python experiments/rq4/stlsat_baseline.py && python experiments/rq4/prune.py   # RQ4
python experiments/rq5_deepstl/analyze.py     # RQ5 (generation: see RQ5; analysis ~15 min)
python experiments/random_suite.py            # RQ2 generated suite (~20 min, 24 workers)
python experiments/volume_ablation.py         # G vs volume Jaccard (~1 min)
python experiments/archcomp.py                # ARCH-COMP coverage (~15 min)
python experiments/metric_properties.py       # triangle inequality on the RQ4 matrices
python experiments/rq4/sd_matrix.py && python experiments/rq4/quality.py   # RQ4 SD baseline, trace coverage
python run_similarity.py "x>2" "x>5" --D 100
bash benchmarks/Manual/benchmark_gen.sh
```
