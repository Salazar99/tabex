# Generated suite: equivalence detection and controlled perturbations

## Part 1 — 1000 random equivalent pairs (28 rewrite rules)

| measure | scored identical | missed | missed pairs by rewrite (top 5) |
|---|---|---|---|
| 1-G | 1000/1000 | 0 | — |
| 1-VolJ | 1000/1000 | 0 | — |
| 1-MCJ | 911/911 | 0 | — |
| PH/2D | 1000/1000 | 0 | — |
| SD | 928/1000 | 72 | nested F collapses (43), U with a true invariant (29) |

## Part 2 — 300 random bases × 11 mutants, D = 8

3300 mutants, 508 equivalent to their base (G = 1) and dropped.

| measure | family | blind (scored identical) | monotone sequences | mean Kendall τ |
|---|---|---|---|---|
| 1-G | const | 0/956 | 235/240 | 0.924 |
| 1-G | shift | 0/804 | 268/268 | 0.991 |
| 1-G | widen | 0/804 | 268/268 | 1.000 |
| 1-G | strict | 0/228 | — | — |
| 1-VolJ | const | 1/956 | 228/240 | 0.932 |
| 1-VolJ | shift | 0/804 | 268/268 | 0.967 |
| 1-VolJ | widen | 0/804 | 268/268 | 1.000 |
| 1-VolJ | strict | 3/228 | — | — |
| 1-MCJ | const | 13/950 | 238/238 | 0.938 |
| 1-MCJ | shift | 1/795 | 226/265 | 0.870 |
| 1-MCJ | widen | 5/794 | 247/264 | 0.909 |
| 1-MCJ | strict | 224/224 | — | — |
| PH/2D | const | 8/956 | 240/240 | 0.954 |
| PH/2D | shift | 0/804 | 255/268 | 0.006 |
| PH/2D | widen | 0/804 | 252/268 | 0.047 |
| PH/2D | strict | 228/228 | — | — |
| SD | const | 299/956 | 240/240 | 0.687 |
| SD | shift | 205/804 | 157/268 | 0.346 |
| SD | widen | 431/804 | 268/268 | 0.466 |
| SD | strict | 228/228 | — | — |

Strictness flip scored as a smaller change than a constant shift by 1:

- 1-G: 221/225
- 1-VolJ: 221/225
- 1-MCJ: 220/222
- PH/2D: 225/225
- SD: 158/225

PH/SD errors (excluded): 0
MCJ undefined (excluded): 89 in part 1, 29 in part 2
