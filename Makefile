all: fix fmt check build test

clean:
	cargo clean

check:
	cargo check
	cargo clippy

fmt:
	cargo fmt

build:
	cargo build

test:
	cargo test

cov:
	cargo llvm-cov --html

run:
	cargo run

fix:
	cargo fix --allow-dirty
