# stlcc

A consistency checker for Signal Temporal Logic (STL) formulas.

## Installation

1. Install Rust: https://rustup.rs/
2. Install Z3 theorem prover: The program requires Z3 executable to be installed in your system: https://github.com/Z3Prover/z3
3. Clone the repository: `git clone https://github.com/ZamponiMarco/stlcc.git`
4. Navigate to the directory: `cd stlcc`
5. Build the project: `cargo build --release`

## Running

The program takes a filename as an argument, which should contain the STL formula to process.

Run the main program with:

```bash
cargo run <filename>
```

Or after building:

```bash
./target/release/stlcc <filename>
```

For example: `cargo run resources/formulas.stl`