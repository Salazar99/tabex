# RQ4 — redundancy pruning of Slam candidates

Reduction rate = 1 − kept/candidates, leader clustering on G in Slam's rank order (`prune.py`). STLSat = Slam's `--remove-impl` (`stlsat_baseline.py`).

| case | candidates | G≥0.5 | G≥0.6 | G≥0.7 | G≥0.8 | G≥0.85 | G≥0.9 | G≥0.95 | G≥0.99 | G≥1 | STLSat |
|---|---|---|---|---|---|---|---|---|---|---|---|
| WaterTanks | 46 | 6 (87%) | 6 (87%) | 8 (83%) | 11 (76%) | 14 (70%) | 19 (59%) | 31 (33%) | 40 (13%) | 46 (0%) | 43 (7%) |
| Heater | 12 | 7 (42%) | 8 (33%) | 8 (33%) | 9 (25%) | 9 (25%) | 10 (17%) | 11 (8%) | 11 (8%) | 12 (0%) | 6 (50%) |
| Gearbox | 166 | 8 (95%) | 10 (94%) | 17 (90%) | 24 (86%) | 29 (83%) | 33 (80%) | 49 (70%) | 63 (62%) | 166 (0%) | 161 (3%) |
| ControlledPU | 350 | 15 (96%) | 25 (93%) | 41 (88%) | 60 (83%) | 84 (76%) | 116 (67%) | 171 (51%) | 274 (22%) | 350 (0%) | 341 (3%) |
| EngineTiming | 6 | 3 (50%) | 3 (50%) | 3 (50%) | 3 (50%) | 3 (50%) | 3 (50%) | 5 (17%) | 5 (17%) | 6 (0%) | 6 (0%) |
| FuelControl | 371 | 15 (96%) | 18 (95%) | 33 (91%) | 59 (84%) | 85 (77%) | 127 (66%) | 220 (41%) | 362 (2%) | 371 (0%) | 363 (2%) |
| **all** | 951 | 54 (94%) | 70 (93%) | 110 (88%) | 166 (83%) | 224 (76%) | 308 (68%) | 487 (49%) | 755 (21%) | 951 (0%) | 920 (3%) |

## G on the pairs STLSat decided (same propositions)

| stlsat verdict (b ⇒ a) | ordered pairs | mean G | min G | max G | G = 1 |
|---|---|---|---|---|---|
| implied | 79 | 0.6495 | 0.0834 | 0.9412 | 0 |
| timeout | 3211 | 0.6628 | 0.0303 | 0.9841 | 0 |

Mutually implied (equivalent) ordered pairs: 36; of those, G = 1: 0.

## Pairs

- 107072 unordered pairs scored, 0 with G = 1 (semantically identical canonical forms), 2 ordered pairs with OWSim = 1.
- Cost (sum of per-call CPU-seconds): TABEX WaterTanks 43s, Heater 0s, Gearbox 625s, ControlledPU 995s, EngineTiming 0s, FuelControl 11291s | STLSat WaterTanks 31927s, Heater 860s, Gearbox 12145s, ControlledPU 97620s, FuelControl 51609s ({'implied': 79, 'timeout': 3211})
- 951 candidates in 9 contexts.
