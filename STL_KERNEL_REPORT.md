# TABEX vs the STL kernel behind stl2vec

This report covers one extra baseline for RQ1. It explains what stl2vec is and whether
comparing TABEX's `G` with it makes sense. It also reports what we measured and how.
RQ numbers follow the paper; the repository's files (`EXPERIMENTS.md`,
`random_suite.py`) call the same research question RQ2.

## 1. Summary

- stl2vec turns an STL formula into a short vector of numbers. It is built on the
  **STL kernel** of Bortolussi et al. (TACAS'22), which compares two formulas by how
  similarly they behave on **random signals**. We compared `G` with that kernel.
- The kernel and `G` measure different things, so this is not a like-for-like
  comparison. Both still claim to measure "semantic similarity of STL formulas", so the
  comparison is worth showing.
- **Equivalent formulas:** `G` scores every equivalent pair as identical (14/14 and
  1000/1000). The kernel does so for 10/14 and 919/1000. The 85 pairs it misses get a
  median distance of 0.05.
- **Strictness:** the kernel cannot tell `x>c` from `x>=c`. It scores all 228 strictness
  flips as identical, as PH does.
- **Grading:** within one family of changes, the kernel ranks small-to-large changes
  very well. Across families its scale is lopsided: moving a time window by 3 steps
  costs about 0.0004, while changing a constant by 1 costs about 0.05.

## 2. What stl2vec is, in simple terms

stl2vec stacks three ideas.

**Robustness.** An STL formula can return a number instead of just true/false. The
number says *how strongly* a signal satisfies the formula. For `x > 0` on a signal with
`x = 2`, robustness is `2 - 0 = 2`: satisfied, with margin 2. With `x = -1` it is `-1`:
violated by 1. For `&&` take the minimum, for `||` the maximum, for `G` the minimum over
the window, and for `F` the maximum. stl2vec squashes every atom's value with `tanh`, so
all values lie between -1 and 1. For example, `tanh(2) = 0.96`.

**A random signal generator (µ0).** The authors fix a recipe for drawing random signals.
Each signal has 101 time steps. It starts at a random value near 0, and its total amount
of movement is small (1 on average across all 101 steps). It changes direction now and
then: at each step with probability `q = 0.1`. Almost all values stay in `[-3, 3]`.

**The kernel.** Draw many random signals. Compute the robustness of formula A and of
formula B on each one, and multiply the two numbers. Then average.
- A large positive average means A and B tend to agree.
- A negative average means they tend to disagree.

After normalising, the result `K(A, B)` lies between -1 and 1, and `K(A, A) = 1`. We use
the distance `1 - K`, which is 0 when the two formulas behave identically on the sampled
signals.

**stl2vec itself.** Applied to a fixed training set of formulas, the kernel gives a big
table of similarities. stl2vec runs kernel PCA on that table and keeps the first few
dozen to few hundred components. Each formula becomes a short vector, and some of the
coordinates have a readable meaning. For example, coordinate 0 tracks the formula's
median robustness. The vectors feed machine-learning tasks:
- predicting the satisfaction probability of a formula on a stochastic model;
- telling a neural trajectory generator which property its output should satisfy.

**Why we compared the kernel and not the stl2vec vectors.** stl2vec only compresses the
kernel. Its distances track the distances between robustness profiles with correlation
0.97, the same as the full kernel's (stl2vec paper, Fig. 2 and Fig. 6). For "how similar
are these two formulas", the kernel is the uncompressed version of the same quantity.

## 3. `G` and the kernel side by side

| | TABEX `G` | STL kernel (stl2vec) |
|---|---|---|
| What it compares | the boxes (constraints) of the exact set of satisfying signals | how much the robustness of the two formulas agrees on random signals |
| Exact or estimated | exact (computed, not sampled) | estimated by sampling (Monte Carlo) |
| Needs a choice of signal distribution | no | yes (µ0) |
| Equivalent formulas score as identical | always (proved) | only if their robustness happens to be identical |
| Sees `>` vs `>=` | yes (a tiny difference, via ε) | no |
| Constants far from the typical signal values | handled by the user parameter `D` | flattened by `tanh` (`x > 10` and `x > 10^7` look the same) |
| Built for | measuring similarity between formulas | feeding machine-learning models |

## 4. Is the comparison meaningful? An honest list

### Reasons it is meaningful

1. **Same stated goal.** Both works say they capture the *semantic* similarity of STL
   formulas. A reader will ask how they differ in practice.
2. **It is the main alternative.** Besides Madsen et al., the kernel line of work
   (kernel, stl2vec) is the only other approach. The paper already cites it.
3. **Venue.** The kernel paper appeared at TACAS'22, and our paper targets TACAS'27.
   Reviewers from that group are plausible.
4. **It tests concrete, checkable properties.** The questions are factual: does the
   measure recognise equivalent formulas, does it notice strictness, does it grade
   bigger changes as bigger. Every answer can be traced to a specific pair of formulas.
5. **Same formulas can be scored.** The kernel's atoms (`x > c`, `x <= c`, ...) and
   operators (`F`, `G`, `U`, Boolean connectives) cover TABEX's fragment, so we scored
   exactly the RQ1 pairs.
6. **It was cheap.** About 2 minutes per run. PH and SD did not have to be recomputed.

### Reasons it is not meaningful, or needs caveats

1. **Different notion of similarity.** The kernel asks "on typical signals, do the two
   formulas behave alike?" `G` asks "do the two formulas impose the same constraints?"
   Neither is wrong. They answer different questions, so a disagreement is not by
   itself a defect of either one.
2. **stl2vec was not designed as a metric.** It is an input representation for learning
   models. Judging it on exact equivalence is judging it on something it never promised.
3. **We tested the kernel, not stl2vec's vectors.** The vectors approximate the kernel
   (see Section 2). Any extra effect of the compression step is not measured.
4. **Our own reimplementation.** We found no public code from the authors, so the kernel
   was rewritten from the papers. Choices that are ours:
   - the *untimed* version: robustness is taken at time 0 only, which both papers allow;
   - `true`/`false` get robustness +1/-1;
   - the Gaussian applied on top of `K` in the original is left out. It cannot change
     which pairs are identical or how pairs are ranked, but it does change the raw
     values.
5. **The random signals may not match theirs exactly.** Our generator matches their
   reported average total movement (0.99 against their 1.008). But our signals change
   direction about 9.9 times on average, while their appendix reports 17.8 for the same
   setting. The source of the gap is unclear. We reran with the direction-change
   probability doubled (`q = 0.2`) and no count changed.
6. **Constants outside µ0's usual range.** The base formulas use constants in `[-3, 3]`,
   where µ0's signals live. Constant mutations go up to ±7, where `tanh` starts to
   flatten everything. The kernel has no equivalent of `D` to adjust for this.
7. **Home advantage.** The RQ1 suites were designed around what `G` is built to do:
   exact equivalence and graded structural changes. We did not test what the kernel is
   likely good at: agreeing with how often two formulas disagree on random signals (the
   RQ4 "oracle"). There, measures based on sampling or volume are expected to do better
   than `G`.
8. **Sampling noise.** The kernel is estimated from 10,000 signals. With another random
   seed some counts move by up to 4 (Section 6f).
9. **No timing comparison.** We did not time the kernel, so the paper's RQ1 question
   about execution time does not cover it.

## 5. How the experiments were set up

### Code

None of the stl2vec authors' code was used: we found none publicly available.
`stlkernel/metrics.py` reimplements the kernel from the papers. It reads formulas with
TABEX's own parser (`similarity/reference_semantics.parse`), so every tool reads the same
syntax. It has three functions:

- `sample_mu0(m, n_vars, rng)` draws `m` random signals following the recipe in stl2vec,
  Appendix A, with its default settings:
  - 101 time steps;
  - start value ~ N(0, 1);
  - total movement ~ N(0, 1)², split into 100 random-sized steps;
  - the direction flips with probability `q = 0.1` at each step.

  Each variable (`x`, `y`, ...) gets its own independent signal.
- `robustness(formula, signals)` computes the tanh-normalised robustness of the formula
  at every time step, for all signals at once (numpy). `U` follows TABEX's convention:
  the left side must also hold at the witness step.
- `kernel_distance(f1, f2, m=10000, seed=0, q=0.1)` computes `1 - K`. It draws one set of
  10,000 signals and uses the **same** signals for both formulas. As a result, two
  formulas with identical robustness score exactly 0.

### Checks that the reimplementation is right

`tests/test_stlkernel.py` has 8 tests:

- **Robustness sign vs truth.** On 4 formulas × 300 random signals, the sign of the
  robustness always agrees with whether the signal satisfies the formula under TABEX's
  own semantics: positive means satisfied, negative means violated.
- **Properties used in the paper.**
  - `F[0,1] F[0,1](x>0)` vs `F[0,2](x>0)` scores 0.
  - `x>0.3` vs `x>=0.3` scores 0.
  - The overlapping-disjunct pair and the tautological-until pair score above 0.

The full test suite passes (233 tests).

### Inputs

The probe re-scores the exact pairs already used for RQ1, so the kernel sees the same
inputs as `G`, VolJ, PH and SD.

| Suite | Size | Where it comes from |
|---|---|---|
| Hand-picked equivalent pairs | 14 | `madsen/compare.py`, list `EQUIVALENT` |
| Generated equivalent pairs | 1000 | `experiments/results/random_equivalence.csv`: a random formula plus one of 28 meaning-preserving rewrites |
| Generated mutants | 2792 | `experiments/results/random_mutations.csv`: 300 random base formulas × 11 mutants, minus the 508 mutants that are actually equivalent to their base (`G = 1`) |

The 11 mutants per base are:
- `const`: one constant moved by 1, 2, 3, 4;
- `shift`: the outer time window moved by 1, 2, 3 steps;
- `widen`: the outer window made 1, 2, 3 steps longer;
- `strict`: one `>` turned into `>=` (or back).

### How results are scored (same rules as `random_suite.py`)

- **Scored as identical:** distance ≤ 10⁻⁹.
- **Blind:** a measure scores a non-equivalent mutant as identical. Lower is better.
- **τ_K (Kendall's tau):** within one base formula's sequence, e.g. constant moved by
  1, 2, 3, 4, does the distance grow in the same order? 1 means perfectly in order, 0
  means no relation. The table reports the average over sequences.

### Runs

| Run | Settings | Time |
|---|---|---|
| Main (reported) | seed 0, `q = 0.1`, 10,000 signals | ≈ 2 min on 24 workers |
| Noise check | seed 1 | ≈ 2 min |
| Signal-shape check | `q = 0.2` | ≈ 2 min |

Reproduce with:

```bash
python experiments/kernel_probe.py                       # writes experiments/results/kernel_probe.{csv,md}
python experiments/kernel_probe.py --seed 1 -o /tmp/s1   # noise check
python experiments/kernel_probe.py --q 0.2 -o /tmp/q02   # signal-shape check
pytest -q tests/test_stlkernel.py
```

## 6. Results

### a) Main table

Left columns: how many equivalent pairs each measure scores as identical (higher is
better). Right columns: how many non-equivalent mutants it scores as identical, i.e.
blind (lower is better), with τ_K in brackets (higher is better).

| Measure | Equiv. hand (14) | Equiv. generated (1000) | const (956) | shift (804) | widen (804) | strict (228) |
|---|---|---|---|---|---|---|
| 1 − G (TABEX) | 14 | 1000 | 0 (0.92) | 0 (0.99) | 0 (1.00) | 0 |
| 1 − VolJ | 14 | 1000 | 1 (0.93) | 0 (0.97) | 0 (1.00) | 3 |
| PH / 2D | 14 | 1000 | 8 (0.95) | 0 (0.01) | 0 (0.05) | 228 |
| SD | 9 | 928 | 299 (0.69) | 205 (0.35) | 431 (0.47) | 228 |
| **1 − K (kernel)** | **10** | **919** | **11 (0.97)** | **0 (1.00)** | **0 (1.00)** | **228** |

### b) Equivalent pairs the kernel misses

Robustness can differ between two formulas that mean exactly the same thing. That is the
whole story behind these misses.

Example: `(0<x<5) || (3<x<8)` and `0<x<8` accept exactly the same values of `x`. At
`x = 4`:

- `0<x<5` gives `min(tanh 4, tanh 1) = 0.76`, and `3<x<8` also gives 0.76. Their `||`
  gives **0.76**.
- `0<x<8` gives `min(tanh 4, tanh 4) = ` **0.999**.

Same meaning, different numbers, so the kernel sees two different formulas. A tautology
behaves the same way: `x>=0 || x<0` is always true, but its robustness is `tanh|x|`,
which varies with `x`.

The 85 misses are:

| Where | Count | What they are |
|---|---|---|
| Generated | 54 | a tautology such as `(y>0) \|\| (y<=0)` conjoined to a formula |
| Generated | 27 | an until whose left side is the tautology `(y>0) \|\| (y<=0)`, compared with `F[a,b] φ` (with the literal `true` instead, the kernel would match) |
| Hand-picked | 1 | `(x>=0 \|\| x<0) U[0,2] (y>0)` vs `F[0,2](y>0)` (distance 0.054) |
| Hand-picked | 3 | overlapping boxes merged into one, e.g. `G[0,2]((0<x<2) \|\| (1<x<3))` vs `G[0,2](0<x<3)` (0.010), the `F` version (0.0096), the L-shape (0.0021) |

Median distance of these misses: **0.05**. For the kernel they are not even "almost
identical". They sit as far apart as a formula and a copy with one constant moved by 1.

Rewrites that keep the robustness unchanged pose no problem for the kernel. That covers
nested `F` collapsing (`F[0,1]F[0,1]φ = F[0,2]φ`), De Morgan, and absorption. SD failed
on the nested-`F` rewrites; the kernel does not.

### c) Strictness

`x > c` and `x >= c` have the same robustness (`x - c`) on every signal. So the kernel
scores all 228 strictness flips as identical, exactly like PH. `G` sees the difference
and scores it as tiny: median distance 8·10⁻⁸.

### d) The 11 blind constant changes (all scored exactly 0)

- **7 cases: the change only affects one single value.** Take
  `y<-3 || y<=-3` → `y<-3 || y<=-4`. The first accepts `y <= -3` and the second accepts
  `y < -3`, so they differ only at `y = -3`. That is a strictness difference in disguise,
  and robustness cannot see it.
- **4 cases: the difference needs a signal that µ0 never draws.** For example
  `F[1,4]((y>=-2 || x<3) U[0,1] (y>=0))` with `-2` moved to `-3, -4, -5, -6`. The two
  formulas only disagree on a signal that rises by at least 2 in a single time step.
  Among the 10,000 random signals, the largest single step is 0.75, so no sample ever
  shows the difference.

### e) Grading: right order, very different scales

Median distance from a base formula to its mutant, by family and size of the change:

| Change | 1 − G | 1 − VolJ | PH / 2D | SD | 1 − K |
|---|---|---|---|---|---|
| constant moved by 1 | 0.075 | 0.13 | 0.062 | 0.021 | 0.047 |
| constant moved by 2 | 0.15 | 0.27 | 0.12 | 0.042 | 0.22 |
| constant moved by 3 | 0.21 | 0.38 | 0.19 | 0.062 | 0.25 |
| constant moved by 4 | 0.27 | 0.46 | 0.25 | 0.083 | 0.26 |
| window moved by 1 | 0.34 | 0.34 | 0.5 | 0.095 | **0.000077** |
| window moved by 2 | 0.57 | 0.54 | 0.5 | 0.19 | **0.00022** |
| window moved by 3 | 0.75 | 0.62 | 0.5 | 0.21 | **0.00041** |
| window widened by 1 | 0.17 | 0.18 | 0.5 | 0 | **0.000037** |
| window widened by 2 | 0.29 | 0.28 | 0.5 | 0 | **0.000098** |
| window widened by 3 | 0.38 | 0.37 | 0.5 | 0 | **0.00019** |
| strictness flipped | 0.00000008 | 0.00000016 | 0 | 0 | 0 |

What this shows:

- **Within a family, the kernel's order is excellent.** τ_K is 0.97, 1.00 and 1.00, as
  good as `G` or better. Bigger changes always look bigger.
- **Across families, the scale is lopsided.** Moving a time window by 3 steps scores
  0.0004. Moving a constant by 1 scores 0.05, about 100 times more. The reason is µ0:
  its signals barely move over a few time steps, so it hardly matters to the kernel
  *when* a condition is checked. In `G`, the two kinds of change land on comparable
  scales.
- **The kernel flattens large constant shifts.** It goes from 0.22 (moved by 2) to only
  0.26 (moved by 4), because `tanh` saturates once constants leave µ0's range. `G`
  keeps growing steadily: 0.15, then 0.21, then 0.27.

### f) Stability

| Run | Equiv. hand | Equiv. generated | const blind (τ_K) | shift | widen | strict |
|---|---|---|---|---|---|---|
| seed 0, q = 0.1 (reported) | 10 | 919 | 11 (0.97) | 0 (1.00) | 0 (1.00) | 228 |
| seed 1 | 10 | 920 | 15 (0.96) | 0 (1.00) | 0 (1.00) | 228 |
| q = 0.2 | 10 | 919 | 11 (0.97) | 0 (1.00) | 0 (1.00) | 228 |

Only the counts that depend on rare signals move, by at most 4. Every conclusion above
holds in all three runs.

## 8. Sources

- G. Saveri, L. Nenzi, L. Bortolussi, J. Křetínský, *stl2vec: Semantic and Interpretable
  Vector Representation of Temporal Logic*, 2024. <https://arxiv.org/abs/2405.14389>
- L. Bortolussi, G. M. Gallo, L. Nenzi, *A kernel function for Signal Temporal Logic
  formulae*, 2020. <https://arxiv.org/abs/2009.05484>
- L. Bortolussi, G. M. Gallo, J. Křetínský, L. Nenzi, *Learning Model Checking and the
  Kernel Trick for Signal Temporal Logic on Stochastic Processes*, TACAS 2022.
  <https://arxiv.org/abs/2201.09928>
