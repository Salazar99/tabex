# STL kernel (1 - K) on RQ1's suites  (m = 10000, seed = 0, q = 0.1)

Equivalent pairs scored identical: hand 10/14, generated 919/1000.

Missed hand-picked pairs:

- `(x>=0 || x<0) U[0,2] (y>0)` vs `F[0,2](y>0)`: 0.0539
- `G[0,2]((x>0 && x<2) || (x>1 && x<3))` vs `G[0,2](x>0 && x<3)`: 0.0101
- `F[0,2]((x>0 && x<2) || (x>1 && x<3))` vs `F[0,2](x>0 && x<3)`: 0.00957
- `G[0,2]((x>0 && x<2 && y>0 && y<1) || (x>0 && x<1 && y>0 && y<2))` vs `G[0,2]((x>0 && x<1 && y>0 && y<2) || (x>=1 && x<2 && y>0 && y<1))`: 0.00213

Missed generated pairs by rewrite: tautological conjunct (28), U with a true invariant (27), U tautological (26)

Non-equivalent mutants (2792):

| family | blind (scored identical) | monotone sequences | mean Kendall τ |
|---|---|---|---|
| const | 11/956 | 237/240 | 0.966 |
| shift | 0/804 | 268/268 | 1.000 |
| widen | 0/804 | 268/268 | 1.000 |
| strict | 228/228 | — | — |

Strictness flip scored as a smaller change than a constant shift by 1: 223/225
