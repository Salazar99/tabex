# RQ5 on DeepSTL — LLM formalisations vs reference

180 DeepSTL requirements with answers: 164; 965 answers from gemini-3.8-flash, qwen2.5:7b-instruct.

## Parsing

| model | answers | parsed | failures by reason |
|---|---|---|---|
| gemini-3.8-flash | 425 | 415 | {'UnsupportedFormula': 10} |
| qwen2.5:7b-instruct | 540 | 227 | {'UnsupportedFormula': 309, 'AttributeError': 4} |

Not scored within 120 s per answer (long nested windows, cf. RQ2 timing): 28 — gemini-3.8-flash 18, qwen2.5:7b-instruct 10

## Correctness (G = 1 ⇔ equivalent to the reference)

| model | parsed | G = 1 | exact string match | mean G | mean G when wrong |
|---|---|---|---|---|---|
| gemini-3.8-flash | 397 | 376 | 102 | 0.9904 | 0.8190 |
| qwen2.5:7b-instruct | 217 | 70 | 21 | 0.7023 | 0.5605 |

By DeepSTL requirement type: immediate_response 171/219, invariance_reachability 148/214, temporal_response 127/181

## Independent check (sampling oracle, not TABEX)

- G = 1 and a distinguishing signal found: 0/446 (must be 0).
- G < 1 and a distinguishing signal found: 163/168 (the rest differ on a set too thin for 4000 samples, e.g. one endpoint).

Spearman ρ between each distance and the disagreement rate, over the 168 non-equivalent answers (pairs with PH/SD undefined dropped for those):

- 1 − G: ρ = 0.011 (n = 168); scored as identical although not equivalent: 0
- 1 − VolJ: ρ = 0.320 (n = 168); scored as identical although not equivalent: 20
- PH/2D: ρ = 0.334 (n = 117); scored as identical although not equivalent: 25
- SD: ρ = 0.066 (n = 117); scored as identical although not equivalent: 74

## Drift among the samples of one model

- gemini-3.8-flash: 345 sample pairs, mean pairwise G 0.9962, 337 equivalent; requirements with some disagreement: 5
- qwen2.5:7b-instruct: 138 sample pairs, mean pairwise G 0.7426, 55 equivalent; requirements with some disagreement: 44

Distinct (scored) answer strings over all requirements: 352; at most 285 semantic classes (all answers equivalent to the reference are one class; wrong answers counted as distinct strings).
