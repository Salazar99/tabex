# Why equivalent formulas produce the same canonical signal space

The property TABEX needs is

> `φ ≡ θ`  ⟺  `canonicalize(S(φ)) = canonicalize(S(θ))`

and it factors into two theorems:

```
φ ≡ θ  ⟺  ⟦φ⟧ = ⟦θ⟧  ⟺  S(φ) = S(θ)  ⟹  canon(S(φ)) = canon(S(θ))
                          └─ Theorem A ─┘   └───── Theorem B ──────┘
```

**Both are proved below**, under stated assumptions and for the fragment in the
README. Theorem A is an induction on the formula; Theorem B is an argument about
box arrangements that was additionally stress-tested against ~1,800 regions
without finding a counterexample.

The reason Theorem A is provable at all is a deliberate architectural choice,
and it is the thing to understand first.

---

## 1. What is defined, what is proved, what is validated

There are three layers, and only the middle one is the definition:

```
holds()               pointwise:   does THIS signal satisfy φ     verify_semantics.py
reference_semantics   set-valued:  WHICH signals satisfy φ        <- THE DEFINITION
standardize + tableau optimised:   the same set, via stlsat       <- validated, not trusted
```

`S(φ)` is **defined** by `reference_semantics.py`: structural recursion on the
formula, no tableau, no solver. Theorem A relates that definition to the
pointwise semantics, one case per connective.

`parse_graph.standardize()` computes the same region from stlsat's tableau. That
path exists for speed and for satisfiability, and it is an **optimisation**: it
is checked against the definition (§6) rather than believed. This is what keeps
the solver out of the trusted base. A bug in the tableau, or in the
string-parsing that reads its DOT labels, surfaces as a differential-test
failure instead of a silently wrong similarity score.

That split matters because the tableau route is not *provable* as it stands:
`standardize` parses printed labels (so a proof would need a specification of
stlsat's `Display` impl), it re-derives which rule was applied from the shape of
a branch (so the induction cannot even be stated — "witness" is not a notion
present in its input), and it infers accepted/rejected status rather than being
told. Every extraction bug found in this project — `!=`, rational constants,
nested-window anchoring — was a string-parsing bug, not a logic bug.

---

## 2. Theorem A — `S(φ) = ⟦φ⟧`

### 2.0 Setup

A **signal** assigns a real to every axis of the finite grid

```
A  =  {0 .. H} × variables,        H = horizon(φ)
```

A **box** is a product `∏_{a∈A} I_a` of intervals, one per axis, where an axis
not mentioned is unconstrained. A **region** is a finite set of boxes, read as
their union. Endpoints carry their own openness (`Interval.lo` / `.ro`), so
`x > 0` is `(0,∞)` and `x ≥ 0` is `[0,∞)`.

Everything is evaluated in **negation normal form**: `negate()` pushes `¬` down
to the atoms, where it is one flip of a comparison operator. This is not
cosmetic — complementing a compound region of `k` boxes over `d` axes costs
`d**k`, while complementing an atom costs nothing. NNF is what makes the
evaluator, and hence the proof, cheap.

### 2.1 Lemma R — the target is representable

*For φ in the fragment, `⟦φ⟧` is a finite union of boxes over `A`.*

Induction on φ:

- **atom** `v op c` at instant `t` — constrains one axis; `!=` gives two boxes.
- **∧, ∨** — finite unions of boxes are closed under intersection and union.
- **¬** — closed **because endpoints carry openness**: the complement of
  `(0,∞)` is `(-∞,0]`, itself a box. With closed-only intervals this step fails,
  and `y<0 ∧ y>0` would denote the non-empty point `[0,0]` instead of `∅`.
- **F, G, U** with finite windows — finite boolean combinations of the above. ∎

So no approximation is being forced anywhere: the box representation is exactly
expressive enough for the fragment.

### 2.2 The induction

Write `S(φ, t)` for `evaluate(φ, t)` read as a set of signals. Claim:

```
S(φ, t)  =  { w : w, t ⊨ φ }
```

One case per line of the recursion, each immediate from the induction
hypothesis, since `⊓` is intersection and list concatenation is union:

| case | definition | pointwise semantics |
|---|---|---|
| `v op c` | the box constraining axis `(t,v)` | `w(t)(v) op c` |
| `φ ∧ ψ` | `S(φ,t) ⊓ S(ψ,t)` | both hold at `t` |
| `φ ∨ ψ` | `S(φ,t) ∪ S(ψ,t)` | either holds at `t` |
| `F[a,b] φ` | `⋃_{u∈[a,b]} S(φ, t+u)` | `∃u∈[a,b] : w,t+u ⊨ φ` |
| `G[a,b] φ` | `⋂_{u∈[a,b]} S(φ, t+u)` | `∀u∈[a,b] : w,t+u ⊨ φ` |
| `φ U[a,b] ψ` | `⋃_{u∈[a,b]} ( S(ψ,t+u) ⊓ ⋂_{v∈[t,t+u]} S(φ,v) )` | §2.4 |

Negation needs no case: NNF has already pushed it to the atoms, where
`NEGATED_OP` flips the comparison and `atom_to_pieces` produces the complement
box directly. ∎

The whole proof is six lines because each connective is a *single* box-algebra
operation. That is the payoff of defining `S` denotationally rather than
reconstructing it from a proof search.

### 2.3 Corollary — the biconditional

```
φ ≡ θ   ⟺   ⟦φ⟧ = ⟦θ⟧   ⟺   S(φ) = S(θ)
```

over the common grid `H = max(horizon φ, horizon θ)`. Left-to-right is Theorem
A applied twice; right-to-left is the same, and is what makes the metric
meaningful — distinct semantics cannot collapse to the same region.

Padding to a larger grid multiplies the region by unconstrained axes and changes
nothing, which is why comparing two formulas over the *joint* domain is sound;
`calc_similarity_from_formulas()` does exactly that, and
`trim_trailing_undef()` removes the padding afterwards.

### 2.4 The `until` convention — a definition, not a discovery

TABEX's until requires the invariant **up to and including** the witness:

```
w, t ⊨ φ U[a,b] ψ   ⟺   ∃u ∈ [a,b] :  w, t+u ⊨ ψ
                               ∧  ∀v ∈ [t, t+u] :  w, v ⊨ φ
```

Textbook STL uses the half-open `[t, t+u)` — it does *not* require the invariant
at the witness instant. The two differ exactly there, and

```
φ U_TABEX ψ   ≡   φ U_textbook (φ ∧ ψ)
```

so this is a legitimate variant of the standard operator, not a weaker one.
`U[0,0]` is the discriminator, since the textbook invariant range is then empty:

| formula | TABEX | textbook |
|---|---|---|
| `x>0 U[0,0] y>3` | `x>0 ∧ y>3` | `y>3` |

**Why this one.** In §2.2 the two readings are *equally* easy — the case has the
same shape, only the inner intersection's range differs. So the proof is not the
tiebreaker; downstream cost is, and it is one-sided: this reading is what
stlsat's tableau already computes, so the optimisation in §6 needs no
translation layer to stay valid. The half-open reading would require rewriting
every `U` into `⋁_u (G[0,u-1]φ ∧ G[u,u]ψ)` before the solver sees it.

The obligation this carries is to say so loudly rather than let a reader assume
textbook STL. It is pinned by
`tests/test_reference_semantics.py::test_until_includes_its_witness` and by
`tests/test_stl_similarity.py::test_until_semantics`.

In a bounded, discrete setting `until` is **sugar**:

```
φ U[a,b] ψ   ≡   ⋁_{u=a..b} ( G[0,u] φ  ∧  G[u,u] ψ )
```

`Until.expand()` implements this, and it is how `negate()` is obtained without
needing a `release` operator.

---

## 3. Theorem B — canonicalisation depends only on the region

> **Hypothesis (H1).** Both decompositions live over the same ambient axis set,
> and every path carries every axis. (See §7 — a real hypothesis, unchecked.)
>
> **Theorem.** If `⋃P₁ = ⋃P₂ = R`, then `canonicalize(P₁) = canonicalize(P₂)`.

Theorem A gives `S(φ) = S(θ)` for equivalent formulas; Theorem B lifts that to
the canonical form the metric actually consumes. It is needed because the
*decomposition* is not unique — the same region arrives cut into different boxes
depending on how the tableau branched.

Write `B_a(P)` for the breakpoints on axis `a` (`_breakpoints`), and note the
**atoms** of `a` given `B_a = {b₁ < … < b_k}`:

```
(-∞,b₁),  [b₁,b₁],  (b₁,b₂),  [b₂,b₂],  …,  [b_k,b_k],  (b_k,∞)
```

Point slabs included. This is what makes the atoms a **partition** of `ℝ` rather
than a cover, and it is the most load-bearing detail in `_cut_piece`. Splitting
only into `…,b)` and `[b,…` partitions one box but *not* a union of boxes that
disagree about whether `b` itself is in: `x≥1 ∧ y>-1` and `x>1 ∧ y≥-1` then
overlap on the interior while each owns a different boundary sliver.

`R_u` denotes the cross-section of `R` at atom `u`; `∂_a(R)` the values where it
changes.

### L1 — indivisibility

*A grid atom-product `X` satisfies `X ⊆ R` iff `X ⊆ B` for a **single** box `B ∈ P`.*

On each axis an atom is inside or disjoint from each box's piece, because every
piece endpoint is a breakpoint. If `X ⊄ B_i` then some axis atom of `X` is
disjoint from `B_i` there, so `X ∩ B_i = ∅`. If that held for every `i`, then
`X ∩ R = ∅`, contradicting `X ⊆ R` for non-empty `X`. ∎

**Consequence.** `_fine_cells(P, B) = { atoms X : X ⊆ R }` — a function of `R`
and `B`, with `P` eliminated. Everything downstream inherits this.

### L2 — bends are always breakpoints

*`∂_a(R) ⊆ B_a(P)` for **every** decomposition `P` of `R`.*

`R` is a finite union of products, so its cross-section along `a` is piecewise
constant and can change only at a piece endpoint. A bend is therefore an
endpoint of some box in any cover whatsoever. ∎

No decomposition can *hide* a feature of the region.

### L3 — the merge test is a region-level condition

`_axis_partition` merges adjacent atoms `u, v` when their **fibres** agree,
where the fibre of `u` is the set of off-`a` atom-products `y` with `u × y` in
the fine cells. Both fibres are drawn from the same off-`a` grid, so

```
fibre(u) = fibre(v)   ⟺   R_u = R_v
```

i.e. fibre equality is exactly cross-section equality. ∎

### L4 — refinement invariance

*If `B ⊆ B′`, the per-axis partitions agree.*

Adding a breakpoint `b′` on axis `a` splits an atom `u` into `u₁, {b′}, u₂`; `R`
does not vary within `u`, so all three have cross-section `R_u` and by L3 merge
straight back. Refining `a` also refines the fibres seen by every *other* axis,
but by a bijection on the underlying sets — so fibre **equality** is preserved
in both directions.

By L2 both `B_a(P₁)` and `B_a(P₂)` contain `∂_a(R)`, and their union is a common
refinement, so

```
partition(B_a(P₁)) = partition(B_a(P₁) ∪ B_a(P₂)) = partition(B_a(P₂))
```

The per-axis partition is a function of `R` alone. ∎

### L5 — the product grid stays inside R

*If a fine cell `X ⊆ R` lies in the coarse box `C = ∏_a S_a`, then `C ⊆ R`.*

Change one coordinate at a time. Replace `X`'s atom on axis `a` by any other
atom of the same run `S_a`: since `X ⊆ R`, the projection of `X` off `a` lies in
`fibre(u)`, and same run means the fibres are equal, so the modified cell is
also in `R`. Every cell of `C` is reachable from `X` by finitely many such
single-coordinate steps. ∎

### Corollary

```
canonicalize(P)  =  { coarse-grid boxes ⊆ R },     coarse grid = ∏_a partition(B_a)
```

By L4 the grid depends only on `R`; by L1 and L5 so does the set of boxes inside
it. Hence `canonicalize(P)` depends only on `R = ⋃P`. ∎

---

## 4. What Theorem B does *not* claim: minimality

The canonical form is **not** the smallest box cover. Measured: 191 of 300
random regions contain two cells that agree on every axis but one and touch
there — locally re-mergeable, deliberately left alone.

That looks like a defect. It is the opposite. The region
`(0≤x≤2 ∧ 0≤y≤1) ∪ (0≤x≤1 ∧ 1≤y≤2)` canonicalises to **3** cells:

```
x[0,1] × y[0,1]      x(1,2] × y[0,1]      x[0,1] × y(1,2]
```

Its *minimal* covers have 2 boxes — and there are **two** of them:

```
A:   x[0,2] × y[0,1]   +   x[0,1] × y(1,2]
B:   x[0,1] × y[0,2]   +   x(1,2] × y[0,1]
```

Both cover exactly the same region, so a minimal cover is **not unique** and
cannot be canonical. Minimality and canonicity are incompatible here, and
canonicity is the one the metric needs.

Not hypothetical: an earlier implementation coalesced greedily, and merging
x-first produced A while y-first produced B — the "canonical" form depended on
axis order. Feeding A and B through `canonicalize()` now returns the same
3-cell form for both, which is L4 doing its job.

---

## 5. The counterexample hunt (Theorem B)

The lemmas were not taken on trust. Each was turned into a property and
attacked. **No counterexample was found.**

| probe | scale | result |
|---|---|---|
| L1 — fine cells == atoms inside `R` | 400 regions, 2 axes | 400/400 |
| L5 — coarse cells cover exactly `R` | 400 regions, 2 axes | 400/400 |
| Thm B vs a guaranteed-different refinement | 400 regions, 2 axes | 400/400 |
| all three, 4 axes (2 vars × 2 instants) | 120 regions, 6561 lattice points each | 120/120 |
| Thm B with unbounded (±∞) axes | 250 regions | 250/250 |
| Thm B on adversarial shapes | L, plus, staircase, checkerboard, donut, U, full 3×3 — 150 covers each, up to **141 distinct** decompositions | exactly one canonical form each |
| `verify_canon.py` (checked in) | 15,000 trials × 3 degeneracy settings, 2D and 3D, ~11.7k distinct regions | 0 lossy, 0 ambiguous, 0 collisions |

**Method note.** There are two ways to get "the same region, decomposed
differently". `verify_canon.py` generates random regions and *hopes* two
coincide — it works, but averages ~1.28 decompositions per region, so most
trials never exercise the theorem. The probes above instead take a fixed region
and **re-tile** it, so every trial compares genuinely different decompositions.
The donut and full-3×3 shapes reached 126 and 141 distinct covers respectively,
all collapsing to one form. The second method is the stronger test, and is the
one that would have caught the axis-order bug in §4.

---

## 6. The tableau as an optimisation

`standardize()` extracts the same region from stlsat's tableau. Since the
definition is §2, this path needs no proof of its own — it needs a **check**,
and it gets an exact one: equality of canonical cell sets, not sampling.

`tests/test_reference_semantics.py::test_tableau_agrees_with_the_definition`
runs 17 formulas covering every connective, including `U`, negated `U` (via the
expansion of §2.4) and nested temporal operators. All 17 agree exactly. A
randomised differential probe over 60 further formulas with `U` and nesting also
agreed 60/60.

Two consequences worth stating:

- **stlsat is out of the trusted base for semantics.** It is still used to
  decide satisfiability and to keep the pipeline fast on large formulas, but if
  it disagrees with the definition, the definition wins and the disagreement is
  a test failure.
- The sampling-based `verify_semantics.py` remains useful as an *independent*
  third implementation: it evaluates single signals pointwise, so agreement
  between it and `reference_semantics.py` is evidence for §2.2 that does not
  share any code path.

---

## 7. Assumptions and known gaps

1. **Discrete, bounded time.** `⟦φ⟧` is a set of signals over `{0..H}`.
2. **Atoms are `variable op constant`** — now *enforced*: anything else raises
   `UnsupportedFormula` rather than silently extracting an unconstrained
   region. See the README's "Supported fragment".
3. **`⟦·⟧` is our definition, and departs from textbook STL at `U`** (§2.4).
   Anyone comparing TABEX against a tool with the half-open until will see
   disagreement on formulas whose invariant fails exactly at the witness.
4. **The tableau path is validated, not proved** (§6). Proving it would require
   stlsat to emit structured output with rule-labelled edges and node status,
   plus the tableau paper's adequacy theorem as a premise. §1 is the reason that
   work is not needed.
5. **H1 is unchecked.** `x ∈ [0,1]` and `x ∈ [0,1] ∧ y unconstrained`
   canonicalise to different forms — correctly, they live in different ambient
   spaces — but ragged input, where one path carries an axis another lacks,
   raises `KeyError` inside `_axis_partition`. `standardize()` pads every path
   to the full grid and `calc_similarity_from_formulas()` passes the joint
   variable set and time domain, so the pipeline always satisfies H1; anyone
   calling `canonicalize()` on hand-built paths must honour it themselves.
6. **The canonical form is deliberately non-minimal** (§4).

---

## 8. Summary

| claim | status |
|---|---|
| `S(φ) = ⟦φ⟧` for the definition | **proved** (§2.2), by induction on φ |
| `φ ≡ θ ⟺ S(φ) = S(θ)` | **proved** (§2.3), both directions |
| `canonicalize` depends only on the region | **proved** (§3); no counterexample in ~1,800 attacked regions (§5) |
| the canonical form is unique per region | proved — §3's Corollary |
| `φ ≡ θ ⟺ same canonical signal space` | follows from A + B |
| the tableau computes the same region | **validated** exactly, 17/17 + 60/60 (§6) — not proved, and not on the critical path |
| the canonical form is *minimal* | **false, deliberately** (§4) |
| `U` is textbook STL's until | **false, deliberately** (§2.4) |
