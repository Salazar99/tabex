# Semantic similarity of STL formulae via canonical signal spaces: artifact

This repository contains the implementation and the experiments of the paper
*Semantic similarity of STL formulae via canonical signal spaces*. It computes
the similarity G of two Signal Temporal Logic formulae: each formula's set of
satisfying signals is built as a union of boxes, reduced to a canonical form, and
the two canonical forms are compared box by box. G = 1 exactly when the two
formulae are equivalent.

- `similarity/` is the definitional pipeline of the paper (evaluate, canonicalise,
  trim, score), kept as the specification of G.
- `fast_similarity/` computes the same score on decision diagrams. Every score reported
  in the paper comes from it.
- `madsen/` reimplements the Pompeiu-Hausdorff (PH) and symmetric-difference (SD)
  distances of Madsen et al. (CDC 2018), the baselines of RQ1.
- `experiments/` holds one script per experiment of the paper.

## Requirements

- Linux. The timing harness limits each run's memory with the `resource` module.
- Python 3.10 or later (tested with 3.10.12 and 3.12.3).
- The Python packages in `requirements.txt`:

```bash
pip install -r requirements.txt
```

RQ1, RQ2 and RQ4 need nothing else. RQ3 runs the Slam specification miner cited
in the paper, bundled in `slam/`. Building it needs a C++17 compiler (gcc 8 or
later), CMake 3.14 or later, git, `uuid-dev`, `pkg-config` and network access to
fetch the antlr4 runtime. Its baseline optionally needs the `stlsat`
satisfiability checker (see [RQ3](#rq3-redundancy-pruning-in-specification-mining)).
The LLM answers used in RQ4 are included, so no API key or language model is needed.

## Quick check (about 1 minute)

```bash
pytest -q                                                    # 225 tests
python -m fast_similarity.engine "F[0,2](x>0)" "G[0,2](x>0)"      # G with the fast engine
python similarity/stl_similarity.py "x>2" "x>5" --D 100      # same metric, definitional pipeline: 0.9694
```

Both command-line tools take two formulae and optionally the domain `--D` (default:
largest absolute constant + 1) and the endpoint precision `--eps` (default 10⁻⁶).

## Reproducing the paper

All commands run from the repository root. Times are approximate, measured on a
32-core Ubuntu machine; scripts that run in parallel accept `--workers`. Each script
writes its results next to it (`experiments/results/`, `experiments/rq3_mining/results/`,
`experiments/rq4_llm/results/`) and states its inputs and outputs in its header.

| Paper | Command | Time | Output |
|---|---|---|---|
| RQ1, Table 1 (generated suites) | `python experiments/random_suite.py` | 20 min | `experiments/results/random_suite.md` |
| RQ1, Table 1 (hand-picked equivalent pairs), App. C.2 | `python -m madsen.compare -o madsen/results.md` | 1 min | `madsen/results.md` |
| RQ1, Fig. 2 and Table 4 (execution time, App. C.3) | `python experiments/timing.py` | 1 h | `experiments/results/timing.{csv,png}` |
| RQ1, boxes versus volume | `python experiments/volume_ablation.py` | 1 min | `experiments/results/volume_ablation.{csv,png}`, `volume_suite.csv` |
| RQ1, ARCH-COMP requirements (App. C.4) | `python experiments/archcomp.py` | 15 min | `experiments/results/archcomp.{csv,md}` |
| RQ2, Fig. 3 and App. D (domain D) | `python experiments/d_sensitivity.py` | 1 min | `experiments/results/d_sensitivity.{csv,png}` |
| Figs. 2 and 3 as PDF; Table 4 and the times quoted in Section 6.2 | `python experiments/paper_figures.py` | seconds | `experiments/results/paper/*.pdf`, `experiments/results/timing.md` |
| RQ3, Table 2 and App. E | see [RQ3](#rq3-redundancy-pruning-in-specification-mining) | 30 min (+ optional baseline) | `experiments/rq3_mining/results/` |
| RQ4, Table 5, App. F.5 and F.6 (oracle check, correlations) | `python experiments/rq4_llm/analyze.py` | 15 min | `experiments/rq4_llm/results/summary.md` |
| RQ4, Table 3, Table 6 and App. F.3 (drift) | `python experiments/rq4_llm/drift.py` | 2 min | `experiments/rq4_llm/results/drift.md`, `drift_pairs.csv` |

`paper_figures.py` reads the CSVs of `timing.py` and `d_sensitivity.py`, so run it
after them. `drift.py` reads the scores of `analyze.py`, so run it after it.

### RQ1: comparison with PH and SD, and computational performance

- `random_suite.py` generates 1000 equivalent pairs (a random formula and a
  meaning-preserving rewrite of it) and 300 base formulae with 11 graded mutants
  each, and scores them with 1 − G, 1 − VolJ, PH/2D and SD. Defaults:
  `--equiv 1000 --bases 300 --workers 24 --seed 11`.
- `timing.py` sweeps four formula families over the horizon T ≤ 40 and 1–5
  signals, with a 60 s / 3 GB limit per run (`--timeout`, `--mem-gb`,
  `--workers 8`). Absolute times depend on the machine. Its CSV also contains the
  scores of the definitional pipeline and of `fast_similarity`, which agree up to
  1.1·10⁻¹⁵ wherever both finish. `--plot-only` redraws the figure from the CSV.
- `archcomp.py` encodes the ARCH-COMP falsification requirements, checks which
  lie in the fragment, and scores each against a perturbed copy (`--timeout 60`).

### RQ2: sensitivity to the domain parameter D

`d_sensitivity.py` sweeps D for pairs of one-sided constraints, their temporal
versions and bounded controls, and checks every value against the closed form
of the paper.

### RQ3: redundancy pruning in specification mining

`slam/` holds Slam, the miner cited in the paper, trimmed to its source and the
six case studies RQ3 uses (`slam/tests/`). Build it once:

```bash
(cd slam/third_party && bash install_antlr.sh)               # antlr4 C++ runtime 4.13.2, a few minutes
cmake -S slam -B slam/build -DCMAKE_BUILD_TYPE=Release && cmake --build slam/build -j
```

Then:

```bash
python experiments/rq3_mining/mine.py                         # candidates.csv (window length capped at --maxd 10)
python experiments/rq3_mining/similarity_matrix.py            # pairwise OWSim and G, pairs.csv.gz (~20 min, --workers 30)
python experiments/rq3_mining/sd_matrix.py                    # SD baseline, sd_pairs.csv.gz (--workers 16)
python experiments/rq3_mining/stlsat_baseline.py              # optional: Slam's implication pruning via stlsat (~54 CPU-h)
python experiments/rq3_mining/prune.py                        # leader clustering, reduction: summary.md, reduction.csv
python experiments/rq3_mining/quality.py                      # trace coverage and fidelity: quality.md (Table 2)
```

`stlsat_baseline.py` expects the `stlsat` binary on the PATH (or `--stlsat PATH`),
built from https://github.com/ZamponiMarco/stlsat at commit 16e5ea6 (Rust and z3;
see the comment in the script), and gives each check 60 s (`--timeout`). It only
adds the STLSat row of Table 2; `prune.py` and `quality.py` run without it.

### RQ4: semantic drift in LLM formalisations

`experiments/rq4_llm/results/` contains the 180 sampled DeepSTL requirements
(`requirements.csv`) and the 965 answers of Gemini 3.8 Flash and Qwen2.5-7B-Instruct
(`samples.jsonl`), which are the only results not regenerated by the scripts.
`analyze.py` parses the answers, scores each against its reference with G, VolJ, PH
and SD, and checks every verdict with an independent sampling oracle. `drift.py`
scores the samples of each model against one another. Every score has a 120 s
budget, so a few counts can differ between runs depending on the speed and load of the
machine. This matters most for `drift.py`: a pair that exceeds the budget drops its whole
group from Table 3, so on a slower machine some groups disappear and the counts shift by a
few, while the pattern (no drift in all-correct groups, drift in every mixed group and in
most all-wrong ones) stays the same. The committed `drift.md` and `drift_pairs.csv` are
the outputs behind the paper, obtained on the machine of Section 6.1.

To regenerate the inputs (not needed to reproduce the paper):

```bash
export DEEPSTL_DIR=~/DeepSTL                                  # a clone of the DeepSTL repository
python experiments/rq4_llm/generate.py select                 # requirements.csv
GOOGLE_API_KEY=... python experiments/rq4_llm/generate.py gemini --budget-usd 3.5   # needs google-genai
python experiments/rq4_llm/generate.py ollama --url http://127.0.0.1:11434          # qwen2.5:7b-instruct via ollama
```

New answers are appended to `samples.jsonl`; delete it first to start from scratch.

## Repository layout

```
similarity/            definitional pipeline: semantics, canonical form, metric (+ CLI)
fast_similarity/       decision-diagram engine (+ CLI); volume.py: VolJ ablation measure
madsen/                PH and SD baselines; compare.py: hand-picked suite
verification/          randomised checks: equivalent formulae score 1, canonical form is lossless
experiments/           RQ1 and RQ2 scripts, paper_figures.py
experiments/rq3_mining/  RQ3: Slam mining, similarity matrix, pruning, baselines
experiments/rq4_llm/     RQ4: DeepSTL requirements, LLM answers, scoring, drift
slam/                  Slam specification miner (C++), source and the six RQ3 case studies
tests/                 pytest suite
```

`python verification/verify_equivalence.py` and `python verification/verify_canon.py`
sample many more random cases than the test suite.

## Supported fragment

```
formula  ::= atom | true | false
           | !formula | formula && formula | formula || formula | formula -> formula
           | F[a,b] formula | G[a,b] formula | formula U[a,b] formula
atom     ::= variable op constant        op ∈ { <  <=  >  >=  ==  != }
constant ::= integer | decimal | rational          e.g. 5, -2, 1.5, 3/2
```

Time is discrete, and `a ≤ b` are integers. Nested windows are relative to the
operator above them. `φ U[a,b] ψ` requires φ up to and including the instant where ψ
holds. Relations between signals (`x > y`), arithmetic terms, unbounded operators
and edge operators are outside the fragment and raise `UnsupportedFormula`; they
are never silently approximated.

## License

MIT, see [LICENSE](LICENSE).
