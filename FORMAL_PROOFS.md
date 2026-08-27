# Formal proofs

`PROOF.md` is the narrative account. This file is the mathematics: complete
statements, explicit hypotheses, and proofs written to be checked rather than
believed.

Two theorems:

- **Theorem A** — the signal space is the formula's semantics:
  `⟦evaluate(φ,t)⟧ = { w : w,t ⊨ φ }`, hence `φ ≡ θ ⟺ S(φ) = S(θ)`.
- **Theorem B** — canonicalisation depends only on the region:
  `⋃P₁ = ⋃P₂ ⟹ canonicalize(P₁) = canonicalize(P₂)`.

Together: `φ ≡ θ ⟺ canon(S(φ)) = canon(S(θ))`.

---

## 0. Preliminaries

### 0.1 Syntax

Fix a finite variable set `V`. Formulas of the fragment:

```
φ ::= v op c                     v ∈ V,  op ∈ {<, <=, >, >=, ==, !=},  c ∈ ℚ ∩ 𝔽
    | true | false
    | φ ∧ φ | φ ∨ φ
    | F[a,b] φ | G[a,b] φ | φ U[a,b] φ        a, b ∈ ℕ,  a ≤ b
```

Negation is deliberately **not** a constructor. It is the operation `negate(·)`
of §1.4, which maps a formula to another formula of the same grammar. The
implementation mirrors this: `reference_semantics.py` has no `Not` node, so
every formula is in negation normal form by construction and `evaluate` has no
negation case to get wrong.

`vars(φ)` is the set of variables occurring in φ.

**Constants (P0).** `𝔽` is the set of reals exactly representable in binary64.
Interval endpoints are binary64, so a constant outside `𝔽` would make the region
denote a *different* set of reals than the formula does, and two distinct
rationals could collapse onto one region — which breaks Corollary A1's (⟸)
direction. `atom_intervals` and `atom_to_pieces` therefore **raise**
`UnsupportedFormula` on such a constant rather than round it: `1/2`, `1.5`, `-3`
pass; `1/3` and integers past `2**53` do not. The restriction is liftable by
carrying `Fraction` endpoints in `Interval`, at the cost of reaching `measure`,
`truncate` and the Jaccard score — a change deliberately not made here.

The operator symbols are written exactly as the code spells them. An earlier
draft wrote `=` and `≠` while the implementation keys on `==` and `!=`; that
drift is why a typo'd operator silently denoted `true` for as long as it did.

### 0.2 Signals and satisfaction

A **signal** is `w : ℕ → V → ℝ`; write `w(t)(v)`. Satisfaction `w,t ⊨ φ`:

| φ | `w,t ⊨ φ` iff |
|---|---|
| `v op c` | `w(t)(v) op c` |
| `true` / `false` | always / never |
| `φ ∧ ψ` | `w,t ⊨ φ` and `w,t ⊨ ψ` |
| `φ ∨ ψ` | `w,t ⊨ φ` or `w,t ⊨ ψ` |
| `F[a,b] φ` | `∃u ∈ [a,b] : w,t+u ⊨ φ` |
| `G[a,b] φ` | `∀u ∈ [a,b] : w,t+u ⊨ φ` |
| `φ U[a,b] ψ` | `∃u ∈ [a,b] : w,t+u ⊨ ψ  and  ∀s ∈ [t, t+u] : w,s ⊨ φ` |

The `U` clause quantifies `s` over the **closed** `[t, t+u]`. This is TABEX's
convention (PROOF.md §2.4); textbook STL uses `[t, t+u)`. Everything below is
stated for this clause, and §1.6 isolates exactly where the choice is used.

### 0.3 Horizon

```
h(v op c) = 0        h(φ ∧ ψ) = h(φ ∨ ψ) = max(h(φ), h(ψ))
h(F[a,b] φ) = h(G[a,b] φ) = b + h(φ)
h(φ U[a,b] ψ) = b + max(h(φ), h(ψ))
```

**Lemma 0 (locality).** *`w,t ⊨ φ` depends only on `w(s)` for `s ∈ [t, t+h(φ)]`.*

*Proof.* Induction on φ. Atom: only `s = t`. Boolean: the two branches need
`[t, t+h(φ)]` and `[t, t+h(ψ)]`, both inside `[t, t+max]`. `F`/`G`: the body is
evaluated at `t+u` with `u ≤ b`, needing `[t+u, t+u+h(φ)] ⊆ [t, t+b+h(φ)]`.
`U`: the witness needs `[t+u, t+u+h(ψ)] ⊆ [t, t+b+h(ψ)]`; the invariant is
evaluated at `s ∈ [t, t+u]`, needing `[s, s+h(φ)] ⊆ [t, t+b+h(φ)]`. Both lie in
`[t, t+h(φ U ψ)]`. ∎

### 0.4 The ambient grid

Fix `H ∈ ℕ` and finite `V`. The **axis set** is `A = {0,…,H} × V`, and a signal
restricted to `A` is a point of `ℝ^A`. Everything below is relative to a fixed
`A`, and Theorem B's hypothesis **H1** is that all decompositions share it.

> **Precondition (P1).** `H ≥ h(φ)` and `V ⊇ vars(φ)`.
>
> Both are needed, and both are now **checked**: `signal_space` raises if the
> ambient variables miss one the formula mentions, or if the horizon is below
> the formula's own. Unchecked, `signal_space(x>0 ∧ y>0, ["x"])` returned the
> region of `x>0` alone — the region of a *different formula*, reported as this
> one's. When comparing two formulas, take `H = max(h(φ), h(θ))` and
> `V ⊇ vars(φ) ∪ vars(θ)`; `calc_similarity_from_formulas()` does exactly that.

### 0.5 Intervals, boxes, regions

An **interval** is `I = ⟨l, r, lo, ro⟩` with `l ≤ r ∈ ℝ ∪ {±∞}` and openness
flags, denoting

```
⟦I⟧ = { x ∈ ℝ : (x > l if lo else x ≥ l) and (x < r if ro else x ≤ r) }
```

`I` is **empty** iff `l > r` or (`l = r` and `lo or ro`) — exactly
`Interval.is_empty`. Infinite endpoints are always open.

A **box** is a partial map `β` from `A` to non-empty intervals, denoting

```
⟦β⟧ = { w ∈ ℝ^A : ∀a ∈ dom β. w(a) ∈ ⟦β(a)⟧ }
```

An axis outside `dom β` is unconstrained. A **region** is a finite list of boxes
`Ρ`, denoting `⟦Ρ⟧ = ⋃_{β∈Ρ} ⟦β⟧`. Note `⟦[]⟧ = ∅` and `⟦[{}]⟧ = ℝ^A`.

**Lemma 1 (interval algebra).** *`⟦I.intersect(J)⟧ = ⟦I⟧ ∩ ⟦J⟧`, and
`I.intersect(J)` is `None` exactly when that set is empty.*

*Proof.* `intersect` takes the larger left endpoint (unioning the open flags on
a tie) and the smaller right endpoint (likewise). For a tie at `l`, the
constraint is `x > l` if either side is open — the conjunction of `x ≥ l` and
`x > l`. Symmetrically at `r`. So membership in the result is the conjunction of
membership in both, which is `⟦I⟧ ∩ ⟦J⟧`. `is_empty` is precisely the condition
for that set to be empty: `l > r` admits nothing, and at `l = r` the single
point survives iff both ends are closed. ∎

**Lemma 2 (box algebra).** *For regions `Ρ, Ρ'`:*

1. `⟦Ρ ++ Ρ'⟧ = ⟦Ρ⟧ ∪ ⟦Ρ'⟧`
2. `⟦intersect(Ρ, Ρ')⟧ = ⟦Ρ⟧ ∩ ⟦Ρ'⟧`

*Proof.* (1) is the definition. (2): `intersect` forms all pairs `(β, β')`,
merging axis-wise via `Interval.intersect` and discarding the pair when some
axis comes back `None`. For a single pair, `w ∈ ⟦β⟧ ∩ ⟦β'⟧` iff `w(a)` lies in
both intervals on every axis of `dom β ∪ dom β'`, which by Lemma 1 is exactly
membership in the merged box; and the pair is discarded exactly when that set is
empty. Taking the union over pairs and distributing `∩` over `∪` gives the
claim. ∎

---

## 1. Theorem A

### 1.1 Atoms

**Lemma 3.** *`⟦atom_intervals(op, c)⟧ = { x ∈ ℝ : x op c }`, as a union of the
returned intervals, for `c ∈ 𝔽`.*

*Proof.* By cases on `op`, comparing with §0.5's denotation:

| op | returned | denotes |
|---|---|---|
| `>` | `(c, ∞)` | `x > c` |
| `≥` | `[c, ∞)` | `x ≥ c` |
| `<` | `(-∞, c)` | `x < c` |
| `≤` | `(-∞, c]` | `x ≤ c` |
| `==` | `[c, c]` | `x == c` |
| `!=` | `(-∞, c) ∪ (c, ∞)` | `x != c` |

Each row is immediate. The case analysis is **exhaustive and enforced**: any
other operator raises `UnsupportedFormula`, in `atom_intervals` (the definition)
and in `atom_to_pieces` (the tableau path) alike. There is no fall-through — a
catch-all `return (-∞,∞)` used to sit here, turning an unreadable operator into
the widest possible claim. ∎

**Lemma 4.** *`NEGATE` is an involution and denotes complementation:
`{x : x op c}` and `{x : x NEGATE[op] c}` partition `ℝ`.*

*Proof.* The pairs are `(>, <=)`, `(>=, <)`, `(==, !=)`, each swapped by
`NEGATE`, so it is an involution. Each pair partitions `ℝ`: `x > c` and
`x <= c` are complementary, likewise `x >= c` / `x < c` and `x == c` / `x != c`. ∎

This is where endpoint openness earns its keep. With closed-only intervals the
complement of `[c,∞)` would have to be `(-∞,c]`, and the two would share `c`.

The claim is about `NEGATE` only. `parse_graph.complement_of` is a different
function — complementation of a *union of pieces* on the tableau path — and used
to conflate "the complement is empty" with "there is no constraint"; it is fixed
and regression-tested, but nothing in this section depends on it.

### 1.2 Evaluation

`evaluate(φ, t)` is defined in `reference_semantics.py`; recalled here:

```
evaluate(v op c, t)     = [ { (t,v) ↦ I } : I ∈ atom_to_pieces(op, c) ]
evaluate(φ ∧ ψ, t)      = intersect(evaluate(φ,t), evaluate(ψ,t))
evaluate(φ ∨ ψ, t)      = evaluate(φ,t) ++ evaluate(ψ,t)
evaluate(F[a,b] φ, t)   = ⧺_{u=a..b} evaluate(φ, t+u)                    -- from NOTHING
evaluate(G[a,b] φ, t)   = ⋂_{u=a..b} evaluate(φ, t+u)                    -- from EVERYTHING
evaluate(φ U[a,b] ψ, t) = ⧺_{u=a..b} ( evaluate(ψ,t+u) ⊓ ⋂_{s=t..t+u} evaluate(φ,s) )
```

**Theorem A.** *Under (P1), for every φ and every `t` with `t + h(φ) ≤ H`:*

```
⟦evaluate(φ, t)⟧  =  { w ∈ ℝ^A : w, t ⊨ φ }
```

*Proof.* Structural induction on φ. There is no negation case: negation is not a
constructor (§0.1).

**Atom `v op c`.** `evaluate` returns one box per interval of
`atom_to_pieces(op,c)`, each constraining only `(t,v)`. By Lemma 3 the union of
their denotations is `{ w : w(t)(v) op c }`, which is `{w : w,t ⊨ v op c}`.
(P1) guarantees `(t,v) ∈ A`.

**`φ ∧ ψ`.** By Lemma 2(2) and the induction hypothesis,
`⟦intersect(…)⟧ = {w : w,t ⊨ φ} ∩ {w : w,t ⊨ ψ} = {w : w,t ⊨ φ ∧ ψ}`.

**`φ ∨ ψ`.** Lemma 2(1) and the induction hypothesis, likewise with `∪`.

**`F[a,b] φ`.** The fold starts at `NOTHING` (`⟦·⟧ = ∅`, the unit of `∪`) and
concatenates `evaluate(φ, t+u)`. By Lemma 2(1) and the hypothesis,

```
⟦·⟧ = ⋃_{u∈[a,b]} { w : w,t+u ⊨ φ } = { w : ∃u∈[a,b]. w,t+u ⊨ φ }
```

which is `{w : w,t ⊨ F[a,b] φ}`. (P1) with `h(F[a,b]φ) = b + h(φ)` ensures every
`t+u` used stays within the grid.

**`G[a,b] φ`.** The fold starts at `EVERYTHING` (`⟦·⟧ = ℝ^A`, the unit of `∩`)
and intersects. By Lemma 2(2) and the hypothesis, `⟦·⟧ = ⋂_{u∈[a,b]} {w : w,t+u ⊨ φ}`,
i.e. `{w : ∀u∈[a,b]. w,t+u ⊨ φ}`.

**`φ U[a,b] ψ`.** For fixed `u`, the term is
`evaluate(ψ,t+u) ⊓ ⋂_{s=t}^{t+u} evaluate(φ,s)`, whose denotation is, by Lemma 2
and the hypothesis,

```
{ w : w,t+u ⊨ ψ }  ∩  ⋂_{s∈[t,t+u]} { w : w,s ⊨ φ }
    = { w : w,t+u ⊨ ψ  and  ∀s∈[t,t+u]. w,s ⊨ φ }
```

Concatenating over `u ∈ [a,b]` and applying Lemma 2(1) gives

```
{ w : ∃u∈[a,b]. ( w,t+u ⊨ ψ  and  ∀s∈[t,t+u]. w,s ⊨ φ ) }
```

which is precisely §0.2's `U` clause. ∎

The `U` case is the **only** place the convention of §0.2 is used: the code's
inner range `range(instant, witness_at + 1)` is the closed `[t, t+u]`. Replacing
it with `[t, t+u)` proves the textbook variant instead, with no other change —
which is the precise sense in which the two readings are equally hard.

### 1.3 Until as sugar

**Lemma 5 (expansion).**
*`w,t ⊨ φ U[a,b] ψ  ⟺  w,t ⊨ ⋁_{u=a}^{b} ( G[0,u] φ ∧ G[u,u] ψ )`.*

*Proof.* For fixed `u`: `w,t ⊨ G[0,u] φ` iff `∀s' ∈ [0,u]. w,t+s' ⊨ φ`, i.e.
`∀s ∈ [t, t+u]. w,s ⊨ φ` after `s = t + s'`; and `w,t ⊨ G[u,u] ψ` iff
`w,t+u ⊨ ψ`. So the `u`-th disjunct holds iff `u` witnesses the `U` clause.
Disjoining over `u ∈ [a,b]` matches `∃u ∈ [a,b]`. ∎

`Until.expand()` implements exactly this, so the invariant window is `[0,u]` —
closed, because the witness instant is included.

### 1.4 Negation

`negate(·)` is defined structurally, and on `Until` by
`negate(φ U ψ) = negate(expand(φ U ψ))`.

**Lemma 6.** *`w,t ⊨ negate(φ)  ⟺  not (w,t ⊨ φ)`.*

*Proof.* Induction on the pair `(uk(φ), |φ|)` ordered lexicographically, where
`uk(φ)` is the maximum nesting depth of `U` in φ and `|φ|` the number of nodes.

- **Atom.** `negate(v op c) = v NEGATED_OP[op] c`; Lemma 4.
- **`φ ∧ ψ` / `φ ∨ ψ`.** `negate` returns `negate(φ) ∨ negate(ψ)` resp.
  `negate(φ) ∧ negate(ψ)`; De Morgan plus the hypothesis on the strictly
  smaller `φ, ψ` (`uk` does not increase, `|·|` strictly decreases).
- **`F[a,b] φ`.** `negate` returns `G[a,b] negate(φ)`. Now
  `not ∃u. w,t+u ⊨ φ` iff `∀u. not (w,t+u ⊨ φ)`, which by hypothesis is
  `∀u. w,t+u ⊨ negate(φ)`. Dually for `G`.
- **`φ U[a,b] ψ`.** `negate` returns `negate(E)` where `E = expand(φ U ψ)`. By
  Lemma 5, `w,t ⊨ φ U ψ ⟺ w,t ⊨ E`, so it suffices that
  `w,t ⊨ negate(E) ⟺ not (w,t ⊨ E)`. `E` is built from `∧`, `∨`, `G` and copies
  of `φ` and `ψ`, so `uk(E) = max(uk(φ), uk(ψ)) < uk(φ U ψ)` and the induction
  hypothesis applies to `E`. ∎

The measure matters: `expand` *increases* node count, so an induction on `|φ|`
alone would not be well-founded. It strictly decreases `U`-nesting depth, which
is what makes the recursion terminate — in the proof and in the code.

Unwinding, `negate(φ U[a,b] ψ) ≡ ⋀_{u=a}^{b} ( F[0,u] negate(φ) ∨ G[u,u] negate(ψ) )`,
the expected dual: for every candidate witness `u`, either the invariant already
failed somewhere in `[t, t+u]` or `ψ` fails at `t+u`.

### 1.5 The signal space, and the biconditional

`signal_space(φ, V, H)` pads every box of `evaluate(φ,0)` to total maps on `A`,
filling absent axes with `(-∞,∞)`. Since `⟦(-∞,∞)⟧ = ℝ`, padding does not change
the denotation, so

```
S(φ)  :=  ⟦signal_space(φ, V, H)⟧  =  ⟦evaluate(φ,0)⟧  =  { w ∈ ℝ^A : w,0 ⊨ φ }
```

by Theorem A. Padding is not cosmetic: it establishes hypothesis **H1** of
Theorem B, which `canonicalize` requires (§2.1).

Write `φ ≡_A θ` for "`w,0 ⊨ φ` iff `w,0 ⊨ θ` for all `w ∈ ℝ^A`".

**Corollary A1.** *Under (P1) for both formulas, `φ ≡_A θ ⟺ S(φ) = S(θ)`.*

*Proof.* `S(φ) = {w : w,0 ⊨ φ}` and `S(θ) = {w : w,0 ⊨ θ}`. Two subsets of
`ℝ^A` defined by predicates are equal iff the predicates agree pointwise. ∎

By Lemma 0, if `H ≥ max(h(φ), h(θ))` then `≡_A` coincides with equivalence over
all signals: no signal outside the grid can distinguish them. So the corollary
is the intended statement and not an artefact of truncation.

### 1.6 What Theorem A rests on, and what runs

Only §0.2, §0.5, (P0) and (P1) — no property of stlsat.

This matters only because the proved path is the one that runs.
`calc_similarity_from_formulas(...)` defaults to `via="definition"`, computing
both regions through `parse` + `signal_space`, i.e. through `evaluate`. Passing
`via="tableau"` selects `standardize()` instead, which is faster on large
formulas and is the only route that can read a hand-written `.dot`; Theorem A
says nothing about it, and `tests/test_reference_semantics.py` cross-checks it
against the definition on every connective.

The cross-check is only worth something because the two sides are **independent**.
They were not: both called one `atom_to_pieces`, so the (P0) violation was
invisible to every differential test in this repository — each side made the same
mistake and agreed. `reference_semantics` now owns its atom layer.

---

## 2. Theorem B

### 2.1 Setting

Fix the axis set `A`. A **decomposition** is a finite list `P` of boxes, each
total on `A` (hypothesis **H1**), denoting the **region** `R = ⟦P⟧`.

> **H1 is required and unchecked.** `_axis_partition` indexes
> `cell.timeline[t][v]` for every axis, so a `P` whose paths carry different
> axis sets raises `KeyError`. `standardize()` and `signal_space()` both pad, so
> the pipeline satisfies H1; a caller building paths by hand must ensure it.

A slot may hold a *list* of intervals, read as their union. Such a box is a
finite union of single-interval boxes obtained by distributing, and both
`_breakpoints` and `_fine_cells` apply `merge_pieces` before use, so we may and
do assume **each box has one interval per axis**. This is without loss of
generality: distributing changes neither `R` nor the breakpoint set.

**Breakpoints.** `B_a(P) ⊆ ℝ` is the set of finite endpoints on axis `a` of the
(merged) intervals of boxes of `P`. Write `B_a = {b₁ < … < b_k}`.

**Atoms.** The atoms of axis `a` are

```
(-∞,b₁), [b₁,b₁], (b₁,b₂), [b₂,b₂], …, [b_k,b_k], (b_k,∞)
```

(and `(-∞,∞)` when `B_a = ∅`). They are non-empty, pairwise disjoint, and cover
`ℝ`, so they **partition** `ℝ`. `_cut_piece` emits exactly the atoms contained
in the piece it is given. An **atom-product** is `X = ∏_{a∈A} α_a` with each
`α_a` an atom of `a`; atom-products partition `ℝ^A`.

**Lemma 7 (dichotomy).** *For an atom `α` of axis `a` and any interval `J` whose
finite endpoints lie in `B_a`: either `⟦α⟧ ⊆ ⟦J⟧` or `⟦α⟧ ∩ ⟦J⟧ = ∅`.*

*Proof.* Suppose `x ∈ ⟦α⟧ ∩ ⟦J⟧`. If `α = [bᵢ,bᵢ]` then `⟦α⟧ = {x} ⊆ ⟦J⟧`.
Otherwise `α` is an open interval `(p,q)` (with `p, q` consecutive elements of
`B_a ∪ {±∞}`) containing no point of `B_a`. Take any `y ∈ ⟦α⟧`; the closed
segment between `x` and `y` lies in `(p,q)` and so meets no endpoint of `J`.
Since `J` is an interval containing `x` and its endpoints are in `B_a`, it
cannot exclude `y` without having an endpoint strictly between them. Hence
`y ∈ ⟦J⟧`, and `⟦α⟧ ⊆ ⟦J⟧`. ∎

### 2.2 The fine arrangement

Let `fine(P) = _fine_cells(P, B(P))`.

**Lemma 8 (indivisibility).** *For an atom-product `X`:
`⟦X⟧ ⊆ R ⟺ ⟦X⟧ ⊆ ⟦β⟧` for some single `β ∈ P`.*

*Proof.* (⟸) `⟦β⟧ ⊆ R`. (⟹) By Lemma 7, on each axis `α_a ⊆ β_a` or
`α_a ∩ β_a = ∅`. Hence `⟦X⟧ ⊆ ⟦β⟧` iff `α_a ⊆ β_a` for all `a`; and if that
fails for some `a`, then `α_a ∩ β_a = ∅` and so `⟦X⟧ ∩ ⟦β⟧ = ∅`. If `⟦X⟧ ⊄ ⟦β⟧`
for every `β ∈ P`, then `⟦X⟧ ∩ R = ⋃_β (⟦X⟧ ∩ ⟦β⟧) = ∅`. But `⟦X⟧ ⊆ R` and
`⟦X⟧ ≠ ∅` — contradiction. ∎

**Proposition 9.** *`fine(P) = { X : X an atom-product, ⟦X⟧ ⊆ R }`. In
particular `fine(P)` depends only on `R` and `B(P)`, not otherwise on `P`.*

*Proof.* (⊆) Each cell emitted is an atom-product obtained by cutting some
`β ∈ P`, hence contained in `⟦β⟧ ⊆ R`. (⊇) Let `⟦X⟧ ⊆ R`. By Lemma 8,
`⟦X⟧ ⊆ ⟦β⟧` for some `β`. `_fine_cells` cuts `β` axis-wise with `_cut_piece`,
which yields every atom contained in `β_a`, and takes the product — so `X` is
among the cells emitted for `β`. Deduplication by `cell_key` (which records
every axis's endpoints *and* openness) preserves the set. ∎

### 2.3 Cross-sections

For an atom `α` of axis `a`, define the **cross-section**

```
R_a(α) = { y ∈ ℝ^{A∖{a}} : ⟦α⟧ × {y} ⊆ R }
```

**Lemma 10 (constancy).** *`R_a(α)` is well defined, i.e. for `x, x' ∈ ⟦α⟧` the
slices `{y : (x,y) ∈ R}` and `{y : (x',y) ∈ R}` coincide.*

*Proof.* `(x,y) ∈ R` iff `y ∈ ⟦β⟧^{−a}` for some `β` with `x ∈ ⟦β_a⟧`. By
Lemma 7, `x ∈ ⟦β_a⟧ ⟺ ⟦α⟧ ⊆ ⟦β_a⟧ ⟺ x' ∈ ⟦β_a⟧`. So the same set of boxes is
selected for `x` and `x'`, giving the same slice. ∎

This is the precise form of "a decomposition cannot hide a bend": `R` is
constant across each atom, so every place `R` genuinely changes is a breakpoint
of *every* decomposition.

**Lemma 11 (fibres).** *Let `fibre(α) = { Y : Y an atom-product over `A∖{a}`,
α × Y ∈ fine(P) }`. Then `fibre(α) = fibre(α') ⟺ R_a(α) = R_a(α')`.*

*Proof.* By Proposition 9, `α × Y ∈ fine(P)` iff `⟦α × Y⟧ ⊆ R` iff
`⟦Y⟧ ⊆ R_a(α)` (Lemma 10). So `fibre(α) = { Y : ⟦Y⟧ ⊆ R_a(α) }`.

`R_a(α)` is a union of boxes over `A∖{a}` whose endpoints lie in the respective
`B`, so by Lemma 7 applied in `A∖{a}` it is a union of atom-products; hence
`R_a(α) = ⋃ { ⟦Y⟧ : Y ∈ fibre(α) }`. Therefore `fibre` determines `R_a` and
conversely. ∎

Note the quantification: `fibre(α)` ranges over atom-products of the *other*
axes, which depend on `B`; but Lemma 11 shows fibre **equality** is equivalent
to a `B`-free condition. That is what makes the next step work.

### 2.4 Refinement invariance

`_axis_partition(fine, a)` sorts the atoms occurring on axis `a` in `fine` and
merges adjacent ones that *touch* and have equal fibres, returning the maximal
runs.

**Lemma 12 (adjacency).** *Consecutive atoms of an axis touch, in the sense of
`merge_pieces`: they meet at a point at which at least one of them is closed.*

*Proof.* Consecutive atoms are `(p,bᵢ)` and `[bᵢ,bᵢ]`, or `[bᵢ,bᵢ]` and
`(bᵢ,q)`. In both, one side is the closed point `[bᵢ,bᵢ]`. ∎

So a run breaks only where fibres differ or where an atom is **absent** from
`fine` — and an atom `α` is absent exactly when `R_a(α) = ∅`, i.e. `R` has a
genuine hole there. Nothing merges across such a gap, since the surviving atoms
on either side are then not adjacent.

**Proposition 13.** *`_axis_partition(fine(P), a)` depends only on `R`, not on
`P` or `B(P)`.*

*Proof.* By Lemma 11 the merge test is `R_a(α) = R_a(α')`, a condition on `R`
alone; and by Lemma 10 the map `x ↦ {y : (x,y) ∈ R}` is constant on atoms. So
the computed runs are exactly the maximal intervals of `ℝ` on which that map is
constant and non-empty — a description mentioning only `R`.

Concretely, if `B ⊆ B'`: each `B`-atom is a disjoint union of consecutive
`B'`-atoms, all with the same slice by Lemma 10, hence with equal fibres by
Lemma 11, hence merged back by Lemma 12; and two adjacent `B`-atoms with equal
slices remain adjacent with equal slices. The maximal runs, *as subsets of `ℝ`*,
are therefore identical. Since `B_a(P₁) ∪ B_a(P₂)` refines both, the partitions
computed from `P₁` and `P₂` agree. ∎

### 2.5 The coarse grid

The **coarse grid** is `∏_{a∈A} partition_a`, the product of the per-axis
partitions; its cells are the **coarse boxes**. `canonicalize` maps each fine
cell to the coarse box containing it (`_slab_of` on each axis) and deduplicates.

**Lemma 14 (saturation).** *If `X ∈ fine(P)` and `X ⊆ C` for a coarse box `C`,
then `⟦C⟧ ⊆ R`.*

*Proof.* Write `X = ∏ α_a` and `C = ∏ S_a`, so `α_a ⊆ S_a` for every `a`. Let
`Y = ∏ γ_a` be any atom-product with `γ_a ⊆ S_a`. Enumerate the axes
`a₁,…,a_n` and set `X₀ = X`, and `X_i = X_{i−1}` with the `a_i`-component
replaced by `γ_{a_i}`. We show `X_i ∈ fine(P)` by induction on `i`.

`X₀ = X ∈ fine(P)`. For the step, `X_{i−1}` and `X_i` differ only on axis
`a := a_i`, where `α := X_{i−1}(a)` and `γ := γ_a` lie in the same run `S_a`,
so `R_a(α) = R_a(γ)` by Proposition 13's merge criterion. Let `Z` be the common
off-`a` part. From `X_{i−1} ∈ fine(P)` and Lemma 11, `⟦Z⟧ ⊆ R_a(α) = R_a(γ)`,
hence `γ × Z ∈ fine(P)`, i.e. `X_i ∈ fine(P)`.

Thus `X_n = Y ∈ fine(P)`, so `⟦Y⟧ ⊆ R`. As `⟦C⟧` is the union of `⟦Y⟧` over all
such `Y`, `⟦C⟧ ⊆ R`. ∎

The one-coordinate-at-a-time argument is exactly why the coarse form must be a
**product** grid. Merging pairs of cells greedily is not confluent: §2.7.

**Proposition 15.** *`canonicalize(P) = { C : C a coarse box, ⟦C⟧ ⊆ R }`.*

*Proof.* (⊆) The output is `{ coarse(X) : X ∈ fine(P) }`; each is `⊆ R` by
Lemma 14. (⊇) Let `C` be a coarse box with `⟦C⟧ ⊆ R`. `C` is non-empty, and is
a union of atom-products; pick one, `X ⊆ C`. Then `⟦X⟧ ⊆ R`, so `X ∈ fine(P)`
by Proposition 9, and `coarse(X) = C` because `_slab_of` returns the unique run
containing `X`'s atom on each axis. Hence `C` is in the output. ∎

### 2.6 Theorem B

**Theorem B.** *Let `P₁, P₂` be decompositions over the same axis set `A`
(H1) with `⟦P₁⟧ = ⟦P₂⟧ = R`. Then `canonicalize(P₁) = canonicalize(P₂)`.*

*Proof.* By Proposition 13 the per-axis partitions, hence the coarse grid,
depend only on `R`. By Proposition 15 the output is the set of coarse boxes
contained in `R` — again a function of `R` alone. Both decompositions therefore
produce the same set. ∎

**Proposition 16 (losslessness).** *`⟦canonicalize(P)⟧ = R`.*

*Proof.* (⊆) Every output box is contained in `R` by Proposition 15.

(⊇) Let `p ∈ R`. The atom-products partition `ℝ^A` (§2.1), so `p` lies in
exactly one, say `X`. Since `p ∈ R`, there is a `β ∈ P` with `p ∈ ⟦β⟧`; by
Lemma 7 applied on each axis, `X`'s atom there is inside `β`'s interval (it
meets it, at `p`), so `⟦X⟧ ⊆ ⟦β⟧ ⊆ R`. Hence `X ∈ fine(P)` by Proposition 9,
and `canonicalize` emits the coarse box `C ⊇ X ∋ p`. So `p ∈ ⟦canonicalize(P)⟧`. ∎

This is the step Corollary B1's reverse direction needs, and it is worth
isolating: without it, equal canonical forms would say nothing about the regions.

**Corollary B1.** *Under (P1) and H1, `φ ≡_A θ ⟺ canon(S(φ)) = canon(S(θ))`.*

*Proof.* (⟹) By Corollary A1, `S(φ) = S(θ)`; apply Theorem B. (⟸) By
Proposition 16 each canonical form denotes its own region, so
`canon(S(φ)) = canon(S(θ))` gives `S(φ) = S(θ)`, and Corollary A1 gives
`φ ≡_A θ`. ∎

### 2.7 Minimality fails, necessarily

The canonical form is not the smallest box cover, and cannot be. For
`R = ([0,2]×[0,1]) ∪ ([0,1]×[1,2])` the canonical form has three cells, while
two distinct 2-box covers exist:

```
A:  [0,2]×[0,1]  +  [0,1]×(1,2]        B:  [0,1]×[0,2]  +  (1,2]×[0,1]
```

Both denote `R`. A minimal cover is therefore not unique, so no minimal-cover
construction can be canonical. Greedy pairwise merging returns `A` or `B`
depending on axis order — which is exactly the confluence failure Lemma 14
avoids by quantifying over a product grid rather than merging.

---

## 3. Hypotheses in force

| # | hypothesis | where used | checked? |
|---|---|---|---|
| P0 | constants lie in `ℚ ∩ 𝔽` (exact in binary64) | Lemma 3; Corollary A1 (⟸) | **yes** — `UnsupportedFormula` |
| P1 | `H ≥ h(φ)` and `V ⊇ vars(φ)` | Theorem A, atom case | **yes** — `signal_space` raises |
| H1 | all paths share the axis set `A` | Theorem B, §2.1 | **no** — `KeyError` if violated |
| — | atoms are `v op c`, operator in the six | Lemma 3 | **yes** — on both paths |
| — | discrete, bounded time | Lemma 0, §0.4 | by construction |
| — | `U` includes its witness (§0.2) | Theorem A, `U` case only | pinned by tests |

Every hypothesis but H1 is now enforced rather than assumed, and each was
enforced *because* it had been silently violated: P0 collapsed `1/3` onto
`0.3333333333333333`; P1 answered a question about `x>0` when asked about
`x>0 ∧ y>0`; the operator set fell through to `true` on a typo. H1 remains the
one hypothesis a caller can break, and it raises `KeyError` rather than a clear
error — `standardize()` and `signal_space()` both pad, so no pipeline path
reaches it.

Theorem A assumes nothing about `standardize()` or stlsat, and since
`calc_similarity_from_formulas` now defaults to the definition, the theorem
covers what the tool computes. The claim that the *tableau* computes the same
region is validated by `tests/test_reference_semantics.py`, not proved, and no
longer sits on the critical path.
