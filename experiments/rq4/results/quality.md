# RQ4 — pruning quality on the traces

Coverage = fraction of the trace instants activated by some candidate of the context that are still activated by a kept candidate; pooled over contexts, weighted by active instants. Same number of kept candidates for every method at a given τ.

| τ | kept / candidates | coverage G | coverage top-k (Slam rank) | coverage random | fidelity G (Act Jaccard, pruned vs rep) |
|---|---|---|---|---|---|
| 0.5 | 54/951 | 0.973 | 0.921 | 0.579 | 0.307 |
| 0.6 | 70/951 | 0.978 | 0.921 | 0.655 | 0.319 |
| 0.7 | 110/951 | 0.988 | 0.921 | 0.709 | 0.347 |
| 0.8 | 166/951 | 0.988 | 0.921 | 0.878 | 0.375 |
| 0.85 | 224/951 | 0.988 | 0.921 | 0.922 | 0.390 |
| 0.9 | 308/951 | 0.988 | 0.933 | 0.949 | 0.465 |
| 0.95 | 487/951 | 1.000 | 1.000 | 0.974 | 0.455 |
| 0.99 | 755/951 | 1.000 | 1.000 | 0.998 | 0.378 |
| 1 | 951/951 | 1.000 | 1.000 | 1.000 | 1.000 |

SD keeps 1 candidate per context at every threshold (SD = 0 on all pairs): 9/951 kept, coverage 0.658.
