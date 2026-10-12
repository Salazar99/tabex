# RQ5 — semantic drift in LLM formalisations

9 independent runs of `prompt.txt` (haiku-1, haiku-2, haiku-3, opus-1, opus-2, opus-3, sonnet-1, sonnet-2, sonnet-3), 12 requirements. Scored by tabex_fast, one D per requirement.

Parse / fragment failures (excluded from scores): 0

| req | D | samples | distinct strings | G=1 classes | largest class | mean pairwise G | min pairwise G | mean G vs ref | min G vs ref | = ref | worst sample |
|---|---|---|---|---|---|---|---|---|---|---|---|
| R1 | 121 | 9 | 2 | 1 | 9 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 9/9 | `G[0,10] (speed < 120)` (haiku-1, 1.0000) |
| R2 | 4751 | 9 | 3 | 2 | 7 | 0.9028 | 0.7500 | 0.9444 | 0.7500 | 7/9 | `G[0,10] (rpm != 4750)` (haiku-2, 0.7500) |
| R3 | 3001 | 9 | 3 | 1 | 9 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 9/9 | `(G[0,8] (rpm < 3000)) -> (G[0,4] (speed < 35))` (haiku-1, 1.0000) |
| R4 | 81 | 9 | 4 | 1 | 9 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 9/9 | `G[0,5] ((temp > 80) -> F[0,3] (fan >= 1))` (haiku-1, 1.0000) |
| R5 | 16.4 | 9 | 2 | 1 | 9 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 9/9 | `G[2,10] ((afr >= 14.0) && (afr <= 15.4))` (haiku-1, 1.0000) |
| R6 | 6 | 9 | 2 | 1 | 9 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 9/9 | `F[0,10] (level >= 5)` (haiku-1, 1.0000) |
| R7 | 3 | 9 | 4 | 1 | 9 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 9/9 | `(valve <= 0) U[0,6] (pressure > 2)` (haiku-1, 1.0000) |
| R8 | 12 | 9 | 4 | 3 | 3 | 0.9142 | 0.8299 | 0.9369 | 0.8299 | 3/9 | `G[0,10] F[0,2] v >= 11` (opus-3, 0.8299) |
| R9 | 2 | 9 | 5 | 2 | 6 | 0.9773 | 0.9545 | 0.9697 | 0.9545 | 3/9 | `(G[0,5] ((pos >= -1) && (pos <= 1))) && (G[5,10] ((pos >= -0.5) && (pos <= 0.5)))` (haiku-1, 0.9545) |
| R10 | 11 | 9 | 5 | 1 | 9 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 9/9 | `G[0,5] ((p > 10) -> G[0,2] (alarm >= 1))` (haiku-1, 1.0000) |
| R11 | 21 | 9 | 2 | 1 | 9 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 9/9 | `F[0,4] ((speed < 20) || (brake >= 0.5))` (haiku-1, 1.0000) |
| R12 | 31 | 9 | 5 | 1 | 9 | 1.0000 | 1.0000 | 1.0000 | 1.0000 | 9/9 | `(G[0,10] (dist > 5)) && (G[0,10] ((dist < 10) -> F[0,2] (speed < 30)))` (haiku-1, 1.0000) |

Mean G vs reference, per model:

- haiku: 0.9823 over 36 formulas, 31 equivalent to the reference
- sonnet: 0.9888 over 36 formulas, 32 equivalent to the reference
- opus: 0.9917 over 36 formulas, 31 equivalent to the reference

Across all requirements: 41 distinct strings collapse to 16 semantic classes (G = 1).
