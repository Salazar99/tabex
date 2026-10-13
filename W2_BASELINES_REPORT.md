# Report: STL kernel, stl2vec and Monte-Carlo Jaccard as baselines (reviewer W2)

Scope: feasibility and design only. Nothing has been implemented. Branch references are to `TACAS27`,
where RQ1–RQ4 live.

## 1. Verdict

- **Feasible.** All three baselines can be added to RQ1 (`madsen/compare.py`,
  `experiments/random_suite.py`, `experiments/timing.py`) and RQ3 (`experiments/rq3_mining/`). They
  share one sampling-and-evaluation core of about 200 lines of numpy. No new dependency is needed.
  Total effort is about 1.5–2 days, and the compute cost is small.
- **Reimplementation is unavoidable, and it can be faithful.**
  - No official code exists (§2).
  - The stl2vec paper [S] and the STL-kernel paper [K] specify almost every parameter.
  - **Only the papers' text is used.** The unofficial code (§2) is not used, and no parameter is chosen
    by matching the papers' published results.
  - Seven details are unspecified. Each is closed by a rule that comes from the papers' own text, so
    none is our own design choice (§4.1).
  - Published numbers serve only as a check, reported as is, whether they match or not (§6).
  - [S] §3.2 (explaining the principal components) is not needed for a distance baseline.
- **The comparison is meaningful only when each baseline is judged on what it claims** (§3). Done that
  way, it answers W2 without strawmen.

## 2. The reviewer's claim "both with public code" is not accurate

Searched on 2026-10-12:

- The arXiv pages of [S] (2405.14389) and [K] (2201.09928): no code link.
- The first author's GitHub (GaiaSaveri): her repositories include LogicVAE and GNN-sharpSAT, but no
  stl2vec or kernel.
- The lab organisation (ailab-units): only TorCheck, which is just an STL robustness module.
- Papers-with-Code ("No code available yet").
- Zenodo: no record for stl2vec or the kernel.

The only copy we found is **unofficial**. A later paper by the same group (Candussio, Saveri et al.,
ECML 2025) has a fork of HuggingFace `transformers` that contains `kernel.py` (`StlKernel`),
`traj_measure.py` (μ0), `phis_generator.py` and `stl.py`. The code is torch-based and has no kernel PCA,
so it is not stl2vec itself. It is cited here only for completeness and is not used anywhere in the plan:
`github.com/gaoithee/transformers/tree/main/src/transformers/models/stldec`.

## 3. Does comparing them against G make sense?

Yes, but the four candidates do not all measure the same thing.

| Group | Measures | What notion of "similar" | Fair to judge on |
|---|---|---|---|
| Same notion as G | VolJ (ablation), **MC-J** | overlap of the satisfaction sets | every RQ1 metric, equivalence detection included; RQ3 |
| Different notion | **[K]**, **[S]** | closeness of robustness profiles under a signal distribution μ0 | grading (Kendall τ, monotone, strict<const1), RQ3 matched-k coverage, cost |
| Existing | PH, SD | language distances | as now |

**Why [K] and [S] belong in the comparison.** Both papers claim that formulae with similar semantics get
nearby representations ([S] §3, Fig. 2: Pearson 0.9688 with robustness distance). Checking whether their
distance grows with perturbation severity therefore tests their own claim. The reviewer names them, so
leaving them out invites W2 again.

**What would be unfair:**
- Counting their equivalence misses and their strictness blindness as our wins. Both are deliberate
  properties of robustness under μ0:
  - [S] §3.1 says formulae that differ only on low-probability signals are treated as equivalent.
  - Robustness is sensitive to syntax.
- Report both as properties, with that citation, and keep them out of the paper's "more consistent"
  claim.

**MC-J is the cleanest competitor:**
- It measures the same notion as G.
- With uniform sampling on [−D, D] and ε = 0, its **expectation is exactly VolJ**, the paper's existing
  ablation, which the paper computes exactly.

## 4. Faithful specification (every value traced to a source)

Agreed choices: μ0 stays at [S]'s default everywhere (RQ3 included), and MC-J samples uniformly on
[−D, D].

| Item | Value | Source |
|---|---|---|
| μ0 | 100 points, Δ = 1; ξ0 ~ N(0,1); total variation ~ N(0,1)²; sorted uniform cut points; initial sign ±1 with p = ½; flips with q = 0.1; linear interpolation | [S] App. A; [K] App. A |
| Monte-Carlo size | 10 000 signals | [K] §3 and §5.1: "10 000 provide a very precise approximation" |
| Robustness | min/max recursion; atoms tanh(±(x−c)); evaluated at t = 0 only | [S] §2, App. A, Eq. (1) |
| Until | max over t' of min(ρψ(t'), min over t'' in **[t, t']** of ρφ(t'')): closed interval | [S] §2. **Identical to TABEX's closed-witness U**, so no translation is needed |
| Training set | 1000 formulas from F: root is an operator; p_leaf = 0.5; operators uniform over {¬,∧,∨,G,F,U}; atoms x_i ≤/≥ θ with θ ~ N(0,1); windows [0, b], b uniform in {1..10} | [S] §3.1, App. A. The authors' code defaults differ (leaf_prob 0.3, unbounded windows); the paper wins because it states its values explicitly |
| n | the signal dimension of the experiment: random_suite 2, compare.py 4, timing 5, RQ3 per context | [S]: "the dimension of the signals is a fixed parameter" |
| Kernel | raw Eq. (1): k(φ,ψ) = mean over the signals of ρ(φ,ξ)·ρ(ψ,ξ) | [S] Eq. (1), and §3.1: embeddings are built "via Equation (1)". See gap G1 |
| [K] distance | L2 distance between kernel embeddings, each embedding being the vector [k(φ, φ_j)] over the 1000 training formulas; divided by 2√1000 | [S] §2 (last paragraph) and App. A Fig. 6, the only place either paper turns the kernel into a distance between formulas |
| [S] embedding | centred Gram matrix of the training set, top-d eigenvectors, standard kernel-PCA projection; d = the smallest value with explained variance ≥ 0.95, with 0.98 also reported; distance ‖z(φ) − z(ψ)‖₂ / 2 | [S] §3.1, Fig. 2; the kernel-PCA method [S] cites (Schölkopf et al. 1997, its reference [35]). See gaps G4 and G5 |
| MC-J | N = 10 000 signals, i.i.d. uniform on [−D, D]; D = `resolve_D`; distance 1 − \|a∧b\| / \|a∨b\|; `None` when the estimate is 0/0 | reviewer's definition |
| `==` atoms | rewritten as `v >= c && v <= c` | the repo's precedent, `rq3_mining/sd_matrix.py:rectangular()` |

**Normalisation.**
- tanh robustness keeps every kernel value in [−1, 1].
- So the stl2vec distance is ≤ 2, and the kernel-embedding distance is ≤ 2√1000.
- Dividing by those bounds puts both in [0, 1], as PH/2D already is.
- These are bounds, not tuned constants.

### 4.1 Gaps in the papers, and the rule taken from the text for each

| # | What the papers leave open | Rule | Why this rule comes from the text |
|---|---|---|---|
| G1 | Which kernel to use: raw Eq. (1), [K]'s normalised k0, or [K]'s exponential kernel | **Raw Eq. (1)** | It is the only kernel [S] writes, and [S] §3.1 builds its embeddings "via Equation (1)". The exponential kernel needs σ, which [K] fixes by a sweep or cross-validation on a regression task; our setting has no such task, so it cannot be used without tuning. k0 has no parameter and is defined in [K], so it can appear as a labelled sensitivity row |
| G2 | The set of internal operators in the formula sampler F (neither paper lists it) | **{¬, ∧, ∨, F, G, U}**, chosen uniformly | These are the operators of [S] §2's syntax and of the formulas [S] shows in Table 22. Low impact: [S] §3.1 and App. B show that the principal components barely change across training sets (cosine ≥ 0.95 for the first 5 components) |
| G3 | How μ0 produces signals with several variables (the algorithm is one-dimensional) | **Each variable sampled independently** with the one-dimensional algorithm | Nothing in either paper couples the variables |
| G4 | How kernel-PCA projections are scaled. [S]'s figures disagree with each other: Fig. 1 shows axes of about ±0.07, Fig. 2 distances up to 40 | **Standard kernel PCA** from the paper [S] cites ([35]): coordinates on unit-length principal axes | We follow the cited definition, not values read off a figure |
| G5 | The number of components d when stl2vec is used as a distance | **The smallest d with explained variance ≥ 0.95, with 0.98 also reported** | This is [S] §3.1's selection rule. [S]'s own semantic-distance check (Fig. 2, d = 10 at n = 3) sits at about 0.95 in Table 1. Both thresholds are reported, so neither is picked after seeing results |
| G6 | Robustness of the constant `true` (needed only for the Madsen φ_T formula) | **+∞, which tanh maps to 1** | This is the standard definition in Maler and Nickovic [S, ref. 28], which [S] cites for STL |
| G7 | Atoms outside the papers' syntax: strict `<`/`>` and `==` | `x > c` gets robustness x − c, the same as `x >= c`. `x == c` becomes `x >= c && x <= c`, giving robustness −\|x − c\| | Both keep the papers' predicate form f(x) ≥ 0 and its x_i ≤ θ / x_i ≥ θ atoms. Strictness is invisible to robustness by definition |

Two points worth making in the paper:

- [K] and [S] contradict each other on formula size at p_leaf = 0.5: [K] reports about 6 nodes, [S] App. B
  reports 4.418. This confirms the sampler is under-specified (G2). We do not tune it towards either value.
- Both papers fix the parameter values for μ0, for F and for the sample sizes, so nothing else has to be
  chosen.

## 5. How it would plug in

The integration follows the existing pattern: one new module, plus a column added to each script by
hand, exactly as PH and SD were added.

- **Core module:**
  - Samplers for μ0, uniform signals and F.
  - `robustness()`: a port of the Boolean monitor `rq3_mining/quality.py:evaluate` with min/max and tanh.
  - Batch robustness and satisfaction matrices, using the end-to-end trace trick from
    `rq4_llm/analyze.py:disagreement`.
  - `fit(n)`, cached.
  - Three pair distances.
- **RQ1:**
  - Add columns in `random_suite.py` (`MEASURES`, `distances()`, `tol`). Fit before the `Pool` is
    created, so forked workers inherit the model.
  - Add columns, Spearman rows and `missed` counts in `madsen/compare.py`.
  - Add methods in `timing.py`, with the one-off fit cost reported separately.
  - Use a 7-slot palette in `paper_figures.py`.
- **RQ3:**
  - A `baseline_matrix.py` modelled on `sd_matrix.py`: one fit and one MC-J sample per context, all
    107 072 pairs scored by matrix products.
  - In `quality.py`, leader clustering on 1 − d. The threshold is bisected per context so each baseline
    keeps the same k as G (the same matched-k protocol as top-k and random). If k cannot be reached,
    report the result "as is", as SD is reported now.

## 6. Validation strategy

1. The sign of robustness agrees with TABEX's Boolean semantics wherever ρ ≠ 0.
2. Pairs with identical robustness give exactly 0. Equivalent pairs give MC-J exactly 0.
3. Our kernel PCA matches `sklearn` `KernelPCA(kernel="precomputed")`.
4. MC-J agrees with VolJ(ε = 0) within 3 standard errors.
5. **Checks against [S]'s published numbers.** These are run once, with the parameters already fixed by
   §4, and reported as they come out. They are never used to choose anything.
   - App. B: mean total variation of μ0 (1.008) and mean formula size at p_leaf = 0.5 (4.418 nodes).
   - Table 1: the number of principal components reaching 95% and 98% of the variance, for n = 3..10.
   - Fig. 2: the Pearson correlation between embedding distance and robustness distance (0.9688).
   - If they match, the paper gets the footnote "our reimplementation reproduces [S]'s Table 1 and
     Fig. 2". If they do not, report the gap and point to G1–G7 as the reason.
6. No comparison with the unofficial code, so that only the papers' text is used.

## 7. Expected outcomes (predicted from the algebra; not yet run)

**RQ1, [K] and [S]:**
- `strict` mutants: 100% blind, the same as PH.
- Exact 0 on every rewrite that is a min/max lattice identity: commutativity, idempotence, absorption,
  distributivity, de Morgan, F/∨, G/∧, nested-window collapse, U absorbs its invariant.
- Missed: rewrites that add a tautology, because ρ((y>0)||(y<=0)) = tanh|y| ≠ 1. These are "tautological
  conjunct", "U tautological" and "U with a true invariant", about 100 of the 1000 pairs.
- Missed: the hand-picked overlapping-interval and L-shape equivalents.
- Probably graded on `shift` and `widen`. Compressed on `const` once constants pass about ±3; the
  mutants reach ±7.

**RQ1, MC-J:**
- All equivalences detected, except where the estimate is 0/0.
- `strict` mutants: 100% blind, since the difference has measure zero.
- Grading close to VolJ, plus noise.
- **Undefined on the timing G family.** The box has probability ≈ 0.07^205, so Monte Carlo cannot see it,
  while VolJ is exact. This is a strong rebuttal point.

**RQ3, default μ0 / uniform [−D, D]:**
- Likely degenerate for all three.
- `theta >= 971` saturates to tanh = −1.0 exactly in float64.
- With D ≈ 972, `==` antecedents have probability 0, so the implications are always true and J = 1.
- This mirrors SD (0 on all 107 072 pairs).

**Cost:** milliseconds per pair after a one-off fit of a few seconds; nearly flat in T. All three are
approximate and stochastic.

## 8. Risks

- **RQ3 strawman.** μ0 (about [−3, 3]) does not fit RQ3's scales (constants up to about 970). Mitigation:
  cite [S]'s own remark that a custom measure can be used, and state that we keep the default so as not
  to tune a baseline. The alternative, a labelled extra run on the mined traces, was considered and
  declined.
- **Monte-Carlo variance.** Report seed 0 in the tables and the spread over 3 seeds in the text.
- **The checks against [S]'s published numbers may not match.** The gaps G1–G7 make an exact match
  unlikely to be guaranteed. Report the difference openly. Do not change any parameter to close it,
  because that would be tuning a baseline on the target numbers.
- **Kernel choice (G1).** [K] found its exponential kernel more accurate for regression. A reviewer may
  ask for it. Answer that its σ has to be tuned on a task, and that the parameter-free k0 is shown as a
  sensitivity row.

## 9. Suggested rebuttal text (draft)

> We added the STL kernel [K], stl2vec [S], and a Monte-Carlo Jaccard of satisfaction (MC-J) to RQ1 and
> RQ3. No official implementation of [K] or [S] is publicly available, so we reimplemented both from
> the papers' text alone, with their stated defaults. Where the papers are silent, we followed rules
> stated in the papers (listed in the appendix), and we tuned no parameter. On [S]'s Table 1 and Fig. 2,
> our implementation gives [to fill in]. [K] and
> [S] measure closeness of robustness under a signal distribution, not overlap of languages. We
> therefore compare them on grading and pruning, which is their own claim of semantic similarity, and
> report their equivalence and strictness behaviour as properties of the design ([S] §3.1). MC-J is an
> unbiased estimator of our VolJ ablation, which we compute exactly; it is undefined whenever the
> languages have negligible volume (e.g. our timing families), where VolJ and G remain exact.

(Numbers to be filled in once the runs exist.)

## 10. Alternative: justification for *not* comparing [K] and [S] against G (STLSim)

The arguments are ranked from strongest to weakest. The first three carry the case; the rest support it.

**A1. The stl2vec authors say it is not a similarity measure between formulas.** [S] §5 (Related Work)
contrasts itself with Madsen et al., our PH/SD baseline: *"Differently, our work does not focus on the
(dis)similarity between formulae, but instead aims at finding a semantic-preserving continuous
representation of STL properties."* [K] presents its kernel as a tool for learning model checking, that
is, regression of satisfaction and robustness on stochastic processes. It never proposes a distance
between specifications. Our RQ1 asks how well a measure of similarity between specifications grades
differences. By their own authors' account, neither method is one.

**A2. They measure a different object: robustness profiles, not languages.** G depends only on the sets
of signals that satisfy the two formulas. It equals 1 exactly when the formulas are equivalent.
Anything computed from robustness ρ cannot behave that way, because ρ is not determined by the set of
satisfying signals. Two lines show this, with no implementation:
- **Same language, different representation.** φ and φ ∧ ((y>0) ∨ (y≤0)) are equivalent. But
  ρ(φ ∧ taut) = min(ρφ, tanh|y|), which differs from ρφ whenever |y| is small. So their kernel distance
  is greater than 0.
- **Different language, same representation.** x>0 and x≥0 have identical robustness, so their kernel
  distance is exactly 0.

So [K] and [S] can neither recognise equivalence nor separate formulas that differ only on a boundary.
[S] §3.1 says so itself: formulas that differ only on low-probability signals "are essentially
considered equivalent". Comparing G with them would compare two different notions, not two answers to
the same question.

**A3. Their values are defined relative to a chosen probability distribution, and no neutral choice
exists for our benchmarks.**
- [K] and [S] are defined relative to a measure μ0 on signals. [S] §3.1 says its geometric properties
  "are valid up to this statistical filter", and that the filter changes when a different measure is
  used.
- The default μ0 lives in about [−3, 3]. Our constants reach ±7 in the RQ1 mutants and about 970 in
  RQ3, so the default would saturate and give degenerate results.
- Re-fitting μ0 to our data would mean we tune a competitor.
- Either way, the outcome would reflect the choice of μ0, not the method.
- G needs no probability measure: it is defined on the bounded domain [−D, D].

**A4. They are Monte-Carlo estimates; G is exact.** Kernel values are averages over 10⁴ sampled signals.
A comparison of how consistently the measures grade would mix the estimator's noise with the
behaviour of the measure. G is exact and deterministic, and that exactness is one of our claims.

**A5. Their distance is not a property of the pair alone.** The stl2vec embedding of φ depends on a set
of 1000 random training formulas, on the kernel-PCA truncation and on the random seed. The distance
between φ and ψ therefore changes with unrelated formulas. G is defined from the pair alone.

**A6. No official implementation exists** (§2), contrary to the reviewer's statement. A
reimplementation has to settle seven unspecified details (§4.1, G1–G7). Any poor result could then be
blamed on our reading rather than on the method. PH and SD came with a published table (Madsen et al.,
Table I) that our test reproduces exactly; [K] and [S] offer nothing equivalent.

**A7 (weak, use only in support).** The outputs live on different scales (unbounded embedding distances
versus a score in [0, 1] that is exactly 1 for equivalent formulas). Any normalisation would be ours.

**Counter-arguments a reviewer may raise, with answers:**
- *"[S] claims its embeddings are semantic (Fig. 2)."* It does, but "semantic" there means agreement of
  robustness on high-probability signals, which is the correlation [S] measures. That is A2's object,
  not language similarity. A1's quote shows the authors draw the same line.
- *"You compare against PH/SD, which were not meant to grade either."* PH and SD are defined on the
  languages of formulas, the same object as G (Madsen et al., "Metrics for STL formulae"). So they
  answer the same question as G, even if poorly. [K] and [S] do not answer that question.

**Cheap middle ground (recommended if dropping [K] and [S]):**
- Keep MC-J. It measures the same thing as G, takes about 30 lines, and its expectation equals our VolJ
  ablation. This answers the reviewer's third request at almost no cost.
- Add the two counterexamples of A2 as a short remark, so the reason [K] and [S] are excluded is
  checkable rather than asserted.

**Draft rebuttal text (exclusion variant):**

> We respectfully disagree that [K] and [S] are competing similarity measures. Their authors state that
> stl2vec "does not focus on the (dis)similarity between formulae" ([S], §5), contrasting it with
> Madsen et al., whom we compare against. Both are built on robustness under a chosen signal
> distribution. Robustness is not a function of the language: φ and φ ∧ ((y>0) ∨ (y≤0)) are equivalent
> but have different robustness, so their kernel distance is positive; x>0 and x≥0 differ but have
> identical robustness, so their kernel distance is zero. [S] acknowledges this filtering explicitly
> (§3.1). G is a language-level, distribution-free, exact score. A numerical comparison would therefore
> measure the choice of signal distribution rather than either method. We note also that no official
> implementation of [K] or [S] is publicly available. We added the Monte-Carlo Jaccard baseline, which
> targets the same notion as G; it is an unbiased estimator of our VolJ ablation, and it is undefined
> whenever the satisfying sets have negligible volume, where G remains exact. We discuss [K] and [S] in
> Related Work with the above distinction.

## 11. Related Work rewrite that justifies the missing comparison

Related Work should actually be split in two. "Distances between formulae" contains the measures defined on the languages of formulae:
Madsen et al.'s PH and SD. They ask the same question as G, so they are the baselines. 
"Embeddings of
formulae" contains the methods that map formulae to vectors for learning: the STL kernel, stl2vec,
the learned syntax and automaton embeddings, and their mining and decoding follow-ups. They are
complementary work, not competitors.

The embeddings paragraph then justifies that classification with three pieces of evidence, ordered so
that each would suffice alone:

1. **The authors' own statement.** In stl2vec's Related Work it is stated that: "..., our work does not focus on the (dis)similarity between formulae, but instead aims at finding a semantic-preserving continuous representation of STL properties."
2. **A formal reason a reader can check.** Robustness is not a function of the language: an
   equivalent formula with a tautological conjunct has different robustness, and `x>0` and `x>=0`
   have identical robustness. So no measure built on robustness can be equivalence-invariant, which
   is the property G is designed around. Citing stl2vec §3.1 shows the authors accept the consequence ("formulae that differ only
   on low-probability signals are considered equivalent").
3. **Why a numerical comparison would not be informative.** These scores depend on a signal
   distribution μ0, a sampled set of reference formulae and Monte-Carlo estimation. The outcome would
   therefore reflect how μ0 was chosen, for which our benchmarks offer no neutral choice, rather than
   the method.

The paragraph ends by calling the two lines of work complementary. That keeps the tone fair to the
cited authors, which matters because reviewers may come from that group. The one-sentence "Baselines"
paragraph in the RQ1 setup points back to this section, so the reader meets the justification where
the omission is visible.

Three wording choices protect the argument:
- PH and SD are described as "meant to compare the languages", not as equivalence-invariant. SD
  misses 72 of the 1000 equivalent pairs in our own suite, so the stronger claim would be refutable
  from the paper's own data.
- Hashimoto et al.'s "STL2vec" is cited separately, so a reader cannot confuse the two papers with
  the same name.
- If the reviewer's pruning point (RQ3) also needs an answer, one extra sentence suffices: the
  retrieval-based mining work uses the embeddings to *find* formulae, not to decide whether two mined
  formulae are redundant.

This is the low-cost route to answering W2. It needs no reimplementation and no new runs. The
reviewer's third suggestion can still be met cheaply by keeping the Monte-Carlo Jaccard, which does
measure the same notion as G (§10).

### Proposed content of the rewritten Related Work

**Paragraph 1: distances between STL formulae.**
- Madsen et al. (CDC 2018) define two distances meant to compare the languages of bounded STL
  formulae: the Pompeiu–Hausdorff distance between the sets of satisfying signals, and the symmetric
  difference of their areas of satisfaction.
- They address the same question as G (how far apart are the behaviours two specifications allow?),
  so they are the baselines of RQ1.

**Paragraph 2: embeddings of STL formulae.**
- **What this line of work is.** A separate line of work maps formulae to vectors for use inside
  learning pipelines:
  - Hashimoto et al. (RA-L 2022), also named "STL2vec", learn the vectors from the formula's syntax.
  - Xie et al. (ICRA 2021) learn them from automata built from the formula.
  - The STL kernel of Bortolussi et al. (TACAS 2022) instead compares the robustness of two formulae
    on signals drawn from a fixed probability distribution μ0.
  - stl2vec (Saveri et al., ECAI 2024) compresses that kernel into finite vectors by kernel PCA.
  - Later work by the same group mines formulae from these vectors (Saveri and Bortolussi, ECML PKDD
    2024) or decodes formulae from them (Candussio et al., ECML PKDD 2025).
- **Why it is not a competitor.**
  - *The authors say so.* stl2vec's Related Work contrasts itself with Madsen et al.: it "does not
    focus on the (dis)similarity between formulae, but instead aims at finding a semantic-preserving
    continuous representation".
  - *Robustness is not a function of the language.* It separates equivalent formulae: φ and
    φ ∧ (y>0 ∨ y≤0) have different robustness. It also identifies different ones: `x>0` and `x>=0`
    have the same robustness.
  - *Some differences are filtered out by design.* stl2vec §3.1 states that formulae differing only on
    signals of low μ0-probability are mapped close together.
  - *The scores depend on choices outside the formulae.* They depend on μ0, on a sampled set of
    reference formulae, and on Monte-Carlo estimation.
- **The contrast with G.** G is exact, needs no signal distribution, and equals 1 exactly on
  equivalent formulae.
- **Closing sentence.** The two lines of work are complementary, and G is compared only with measures
  defined on languages.

**One sentence in the RQ1 experimental setup ("Baselines").**
- G is compared with PH and SD, the prior distances defined on the languages of STL formulae.
- It is also compared with VolJ, the exact volume Jaccard of the satisfying sets.
- If kept, add the Monte-Carlo estimate of VolJ over uniformly sampled signals.
- Robustness-based embeddings (STL kernel, stl2vec) target a different notion of similarity, explained
  in Related Work, and are not included.

**References to add.** Check the details against the publishers' pages before submission.
- C. Madsen, P. Vaidyanathan, S. Sadraddini, C.-I. Vasile, N. A. DeLateur, R. Weiss, D. Densmore,
  C. Belta. *Metrics for Signal Temporal Logic Formulae.* CDC 2018, pp. 1542–1547.
- L. Bortolussi, G. M. Gallo, J. Křetínský, L. Nenzi. *Learning Model Checking and the Kernel Trick
  for Signal Temporal Logic on Stochastic Processes.* TACAS 2022, LNCS 13243, pp. 281–300.
- G. Saveri, L. Nenzi, L. Bortolussi, J. Křetínský. *stl2vec: Semantic and Interpretable Vector
  Representation of Temporal Logic.* ECAI 2024, doi:10.3233/FAIA240638.
- G. Saveri, L. Bortolussi. *Retrieval-Augmented Mining of Temporal Logic Specifications from Data.*
  ECML PKDD 2024, LNCS 14947, pp. 315–331.
- S. Candussio, G. Saveri, G. Sarti, L. Bortolussi. *Bridging Logic and Learning: Decoding Temporal
  Logic Embeddings via Transformers.* ECML PKDD 2025, doi:10.1007/978-3-032-06096-9_1.
- W. Hashimoto, K. Hashimoto, S. Takai. *STL2vec: Signal Temporal Logic Embeddings for Control
  Synthesis With Recurrent Neural Networks.* IEEE RA-L 7(2), 2022, pp. 5246–5253.
- Y. Xie, F. Zhou, H. Soh. *Embedding Symbolic Temporal Knowledge into Deep Sequential Models.*
  ICRA 2021, pp. 4267–4273.

## Sources

- [S] Saveri, Nenzi, Bortolussi, Křetínský. *stl2vec*, ECAI 2024. https://arxiv.org/abs/2405.14389
- [K] Bortolussi, Gallo, Křetínský, Nenzi. *Learning model checking and the kernel trick for STL on
  stochastic processes*, TACAS 2022. https://arxiv.org/abs/2201.09928
- Unofficial kernel code: https://github.com/gaoithee/transformers/tree/main/src/transformers/models/stldec
- Candussio et al., ECML 2025 (source of that code): https://arxiv.org/abs/2507.07808
- Lab organisation: https://github.com/ailab-units ; author: https://github.com/GaiaSaveri

## 12. Revised Related Work (structure as in the current paper)

Changes relative to the current version; everything else is verbatim, and no new paper is cited:

1. The kernel and stl2vec are removed from the "Among later work" list of distances.
2. A closing passage in the same paragraph explains why they are not baselines.

```latex
\section{Related Work}
\label{sec:related-work}

\paragraph{Distances between STL formulae.}
Quantifying how similar two \gls{STL} formulae are, as opposed to how well a signal satisfies one formula (robustness~\cite{fainekos2009robustness,donze2010robust}), has a short history; the closest prior work is~\cite{madsen2018metrics}, who define two \emph{language-based} distances. Both project a formula's language onto a value-space region and compare regions rather than syntax: the \gls{PH} distance is the worst-case pointwise gap between the regions, computed by a \gls{MILP}; the \gls{SD} distance is the Lebesgue measure of the region on which the formulae disagree, computed over the syntax tree.
\ezio{Our construction is also recursive over the syntax, but it retains the region's \emph{decomposition} into boxes and canonicalises it, so that equivalent formulae are represented identically and the boxes remain available for a box-to-box comparison (Section~\ref{sec:MetricDefinition}); \gls{PH} and \gls{SD} provide neither, while \gls{PH} admits linear atoms over several variables, which we do not. Among later work, \cite{linard2020active} use \gls{SD} as a convergence criterion in active learning, and \cite{romero2018ltl} define an analogous distance for \gls{LTL} on finite traces.
The \gls{STL} kernel~\cite{bortolussi2020kernel,bortolussi2022kernel} and \textsc{stl2vec}~\cite{saveri2024stl2vec} lie instead on the robustness side of the distinction above: they represent a formula by its robustness on signals sampled from a fixed distribution, compared through a kernel and compressed by kernel PCA, as features for learning, and their authors state that \textsc{stl2vec} ``does not focus on the (dis)similarity between formulae''~\cite[Sec.~5]{saveri2024stl2vec}. Robustness is not determined by the language: $\varphi$ and $\varphi \wedge (y>0 \vee y\le 0)$ are equivalent but have different robustness, while $x>0$ and $x\ge 0$ differ but have the same. Their scores therefore give no identity guarantee, and depend on the sampling distribution, on a sampled set of reference formulae and on Monte-Carlo estimation; we regard them as complementary representations rather than as baselines.}

\noindent \textbf{Decision diagrams and trace representations.}
\ezio{Section~\ref{sec:method} stores a signal space as a hash-consed diagram with a unique table and an \texttt{apply} operator, as reduced ordered \glspl{BDD} do~\cite{bryant1986graph,vandijk2017sylvan}; with intervals on the edges it is an Interval Decision Diagram~\cite{strehl1999interval}, and a special case of the Linear Decision Diagrams of~\cite{chaki2009ldd}. Proposition~\ref{prop:canon-diag} is the usual canonicity of a reduced diagram for a fixed order and atom partition; Theorem~\ref{can:thm:B} adds canonicity \emph{independently of the partition}, since Definition~\ref{def:canonicalization} coarsens each axis to the runs of the region itself, so two formulae with different constants need no joint order, and the similarity is then defined on the canonical boxes, which no diagram operation provides. For \gls{MLTL}, the propositional counterpart of our fragment, the WEST tool~\cite{elwing2023west,wang2025west} represents the satisfying traces as a set of ``trace regular expressions'', one wildcard-able character per instant and proposition, a shorter string being padded with wildcards: a trace regex is a box over the instant--proposition grid, the set is a decomposition and the padding is our trimming. WEST validates specifications and decides equivalence; our boxes carry intervals rather than bits, so canonicalisation must discover the breakpoints, and we grade non-equivalent formulae rather than decide equivalence. Satisfiability checking for \gls{MLTL}~\cite{li2019mltlsat} and bounded \gls{STL}~\cite{stlsat} underlies implication-based pruning, a baseline in Section~\ref{sec:results}.}

\noindent \textbf{Specification mining and requirements validation.}
\ezio{Miners return many candidate formulae, by template instantiation~\cite{asarin2011parametric,jin2015mining,hoxha2018mining}, decision trees~\cite{bombara2016decision}, logical clustering~\cite{vazquezchanlatte2017logical}, enumeration of \gls{LTL} fragments~\cite{raha2022scalable} or hybrid-system mining~\cite{nicoletti2024mining,bartocci2022survey}; redundancy is usually removed by pairwise implication checks, which are binary and expensive, whereas a graded similarity allows ranking and clustering (Section~\ref{sec:results}). Requirements validation~\cite{cimatti2011formalizing,cimatti2012validation} checks consistency and entailment among formalised requirements when a reference exists; the drift check of Section~\ref{sec:results} targets \gls{LLM}-produced formalisations~\cite{cosler2023nl2spec,HeBNIG22}, where no candidate is known to be correct.}
```
