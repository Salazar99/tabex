# Tabex: STL Similarity Metric Calculator

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](./LICENSE.md)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)

**Tabex** is the official repository for the Signal Temporal Logic (STL) similarity metric calculator. It utilizes a modified version of [stlsat](https://github.com/ZamponiMarco/stlsat.git) to extract satisfaction constraints, allowing users to calculate similarity between STL formulas based on those constraints.

---

## 📂 Source Code Structure

```bash
tabex_home/
├── benchmarks/                # Benchmarks folder
│   ├── Manual/                # Manually defined test cases
│   └── Random/                # Randomly generated test cases
├── dotparser/
│   └── input_creator.py       # Formula volume generation
├── figures/                   # Images used in README
├── graph_examples/            # Sample stlsat tableau .dot files (also used as test fixtures)
├── similarity/
│   └── stl_similarity.py      # Similarity calculation script
├── tests/                     # Pytest suite for parse_graph.py
│   ├── conftest.py
│   ├── fixtures/              # Golden standardized-path outputs
│   ├── test_units.py
│   ├── test_dot_examples.py
│   └── test_formula_to_signal_space.py
├── parse_graph.py             # Tableau -> signal space (standardization, Algorithm 1)
├── pytest.ini                 # Pytest markers/config for tests/
├── run_similarity              # Runs the entire similarity pipeline
├── m_stlsat/                  # Modified stlsat source code
├── LICENSE.md                 # Project license
└── README.md                  # Documentation
```

-----

## 🚀 Installation

### Requirements
  * **OS**: Tested on Ubuntu 22.04.5 LTS. 
  * **Python**: Tested with Python \> 3.10.
  * **Rust**: Required for stlsat ([rustup.rs](https://rustup.rs/)).
  * **Z3 Theorem Prover**: Z3 executable must be installed on your system.

> **Note**: It is not necessary to compile `stlsat` beforehand; it is run using `cargo run`, which builds the project automatically.

### Setup

Clone the repository:

```bash
git clone https://github.com/Salazar99/tabex.git
cd tabex
```

-----

## 🛠 Usage

### Define Environment Variable

Before running the tool, you must define the `TABEX_ROOT` variable:

```bash
# If cloned to your home folder:
export TABEX_ROOT=~/tabex
```

### 1\. One-Command Execution

Run the similarity calculation on two formulas directly:

```bash
python run_similarity "First_formula" "Second_formula" [--save-volumes]
```

  * **--save-volumes**: (Optional) Saves the formula volumes in a `.json` file.

### 2\. Manual Steps

You can run the pipeline stages independently:

#### **Volume Generation**

```bash
python dotparser/input_creator.py formula.stl output_file.json 
```

  * `formula.stl`: Contains the formula structure.
  * `output_file.json`: Will contain the generated formula's volume.

#### **Similarity Calculation**

```bash
python similarity/stl_similarity.py volume_1.json volume_2.json
```

### 3\. Signal Space Generation (`parse_graph.py`)

`parse_graph.py` turns a stlsat tableau into a "signal space": a set of
standardized, feasible `Path`s (Algorithm 1). It can either read an
existing tableau `.dot` file, or generate one on the fly by calling
`stlsat` for you.

#### **From an existing tableau**

```bash
python parse_graph.py graph_examples/graph_G.dot
```

#### **From an STL formula string**

```bash
python parse_graph.py --formula "G[0,2] x > 0"
```

This writes the formula to a temp `.stl` file, runs `stlsat` (`cargo run
--release ... --graph-output ...`, same as the volume-generation
pipeline) inside `$TABEX_ROOT/m_stlsat`, then feeds the resulting DOT
tableau through the same tree-building and standardization steps.

Optional flags:

* **--tabex-root**: Override `$TABEX_ROOT` (default: `~/tabex`).
* **--save-dot**: Keep the intermediate tableau `.dot` file for inspection.

As a library:

```python
from parse_graph import generate_signal_space_from_formula

paths = generate_signal_space_from_formula("F[0,2] x >= 0")
```

### Usage Example

Below is a demonstration of the complete pipeline execution:

![til](./figures/TABEX.gif)
-----

## 📊 Benchmarks

Benchmarks are located in the `tabex/benchmarks` folder:

### Manual Benchmarks

Designed to show specific cases of interest.

```bash
cd benchmarks/Manual
bash benchmark_gen.sh
```

*This generates a `results.txt` containing the metric values for each benchmark.*

### Random Benchmarks

*Work in progress...*

-----

## 🧪 Testing

`parse_graph.py` has a `pytest` suite under `tests/`. Requires `pytest`
and `pydot` (`pip install pytest pydot`).

```bash
# Fast: unit tests + golden-output tests over graph_examples/*.dot (no Rust/Z3 needed)
pytest -q

# Integration: calls the real stlsat binary via `cargo run` to verify
# --formula produces the same signal space as the checked-in .dot fixtures
export TABEX_ROOT=~/tabex
pytest -q -m integration

# Slow: full tree build over the ~4.3MB graph_G_U.dot fixture, opt-in
pytest -q -m slow
```

`tests/test_dot_examples.py`/`test_formula_to_signal_space.py` are
regression tests (golden JSON snapshots — they catch *changes*, not
necessarily *bugs*). `tests/test_semantics_examples.py` instead checks
`standardize()`'s output against the actual STL meaning of each formula
(e.g. `G[0,2] x>0` requiring `x>0` at every instant, `F[0,2] x>=0`
partitioning into disjoint earliest-witness paths), with the reasoning
in each test's docstring — that's the file to read if you want to know
*why* a given signal space is correct, not just that it hasn't changed.

-----

## 🤝 Developers & Credits

**Developers**

  * **Daniele Nicoletti**: daniele.nicoletti@univr.it | mr.nicoletti99@gmail.com

**Credits**

  * Original `stlsat` implementation by **@ZamponiMarco**.

-----

## 📄 License

This software is licensed under the **MIT License**.