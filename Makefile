VERSION := $(shell grep '^version' Cargo.toml | cut -d '"' -f2)

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

release:
	cargo build --release

tag:
	git tag -a v$(VERSION) -m "Release v$(VERSION)"
	@echo "To push the tag to remote, run:"
	@echo "git push origin v$(VERSION)"
