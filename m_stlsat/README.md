# stlsat

A satisfiability checker for Signal Temporal Logic (STL) formulas.

## Installation

1. Install Rust: https://rustup.rs/
2. Install Z3 theorem prover: The program requires Z3 executable to be installed in your system: https://github.com/Z3Prover/z3
3. Install the executables:

## Running

### stlsat

The main STL satisfiability checker. Takes a filename as an argument containing the STL formula to check for satisfiability.

```bash
stlsat <filename>
```

For example: `stlsat resources/formulas.stl`

Run `stlsat --help` for available options.

### scanner

Scans directories for STL files and processes them (e.g., parses and analyzes formulas). The output is a csv file with data about the formulas.

```bash
scanner [options]
```

Run `scanner --help` for available options.

### rb

Random benchmark generator. Generates random STL formulas and saves them to files.

```bash
rb [options]
```

Run `rb --help` for available options.

## Development

For development, clone the repository and use the [justfile](./justfile) for common tasks:

```bash
git clone https://github.com/ZamponiMarco/stlsat.git
cd stlsat
just  # See available tasks
```

The [justfile](./justfile) provides an overview of and easy access to common development tasks
like running linters and tests via the [just](https://github.com/casey/just) command runner.
After [installation](https://github.com/casey/just?tab=readme-ov-file#installation),
for example via `cargo install just`, run `just` to see the available tasks.

## Using as a Library

You can use `stlsat` as a Rust library in your projects for STL formula processing and satisfiability checking.

Add to your `Cargo.toml`:

```toml
[dependencies]
stlsat = { git = "https://github.com/ZamponiMarco/stlsat" }
```

Then in your Rust code:

```rust
use stlsat::formula;
use stlsat::sat;
use stlsat::util;
```

For API details, refer to the source code.