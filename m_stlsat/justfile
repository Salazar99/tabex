[private]
default:
    just --list --unsorted

[group('build')]
[doc('Build the project in release mode')]
release:
    cargo build --release

run *args:
    cargo run -- {{args}}

[group('test')]
test *args:
    cargo test {{args}}

[group('lint')]
[doc('Format code using `cargo fmt`')]
format:
    cargo fmt

[group('lint')]
[doc('Check for errors using `cargo check`')]
check:
    cargo check

[group('lint')]
[doc('Run clippy linter')]
clippy:
    cargo clippy

[group('lint')]
[doc('Run clippy linter and automatically fix issues')]
clippy-fix:
    cargo clippy --fix

[group('lint')]
[doc('Run clippy linter in pedantic mode')]
clippy-pedantic:
    cargo clippy -- -W clippy::pedantic

[group('lint')]
[doc('Run clippy linter in pedantic mode and automatically fix issues')]
clippy-pedantic-fix:
    cargo clippy --fix -- -W clippy::pedantic