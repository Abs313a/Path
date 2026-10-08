
QMLTESTRUNNER ?= /usr/lib/qt6/bin/qmltestrunner
CARGO ?= cargo
QS ?= qs
ROOT := $(shell pwd)

.PHONY: all build test clippy test-rust test-qml test-e2e scroll-perf scroll-history coverage run daemon shell dev-clean fmt lint clean

all: build

## Build the default members: pathd, the share and service plugins, and the location kinds in
## plugin::LOCATION_KINDS. Other location plugins build with `cargo build -p …`.
build:
	$(CARGO) build --release
	@ln -sf path-plugin-gio target/release/path-plugin-smb

test: clippy test-rust test-qml test-e2e

clippy:
	$(CARGO) clippy --all-targets -- -D warnings

test-rust:
	$(CARGO) test

## Leaf and interaction tests: no compositor, about five seconds. Offscreen, so the developer's
## own pointer and windows cannot make a test flaky. Only an explicit make command-line
## override (make test-qml QT_QPA_PLATFORM=wayland) opts into a desktop platform.
test-qml: export QT_QPA_PLATFORM = offscreen
test-qml: export LANGUAGE = en
test-qml:
	@# tst_LocationImage writes its swatch under target/, which only a cargo build makes.
	@mkdir -p target
	$(QMLTESTRUNNER) -import tests/qml/stubs -input tests/qml
	@# Real drags: `offscreen` ends every drag the moment it starts, `minimal` performs one.
	QT_QPA_PLATFORM=minimal $(QMLTESTRUNNER) -import tests/qml/stubs -input tests/qml-drag

## End to end against a real daemon and a real tree. Without cage it runs the daemon-only flows
## and says which it skipped.
# The remote flows want real servers — `sudo pacman -S openssh vsftpd` — and skip, by name, the
# pairs whose server is not installed.
test-e2e: build
	tests/e2e/run.sh

## 100,000 files scrolled in each view, timed, and recorded per build in bench/scroll-history.jsonl.
scroll-perf: build
	PATHFM_DAEMON=$(ROOT)/target/release/pathd tests/e2e/run.sh --flow scroll_perf

scroll-history:
	@tests/e2e/scroll_history.py

# The checkout's daemon and window keep to themselves: a socket of their own (the installed
# path of the same version would otherwise be found first — the socket is named for the
# version) and folders of their own for everything path writes — config, state, data, cache,
# thumbnails, the search index — so a build under way never rewrites the installed path's
# settings, locations or journal, and Settings › DWM-Titus's Apply edits a scratch home rather
# than the real home directory.
# What is NOT separate: the trash — a file trashed is trashed — and the desktop's own dirs.
DEV_SOCKET ?= $(or $(XDG_RUNTIME_DIR),/tmp)/pathfm-dev.sock
DEV_HOME ?= $(or $(XDG_STATE_HOME),$(HOME)/.local/state)/path-dev
DEV_ENV = PATHFM_SOCKET=$(DEV_SOCKET) PATHFM_CONFIG_DIR=$(DEV_HOME)/config PATHFM_STATE_DIR=$(DEV_HOME)/state PATHFM_DATA_DIR=$(DEV_HOME)/data \
	PATHFM_CACHE_DIR=$(DEV_HOME)/cache PATHFM_THUMB_DIR=$(DEV_HOME)/cache/thumbnails PATHFM_INTEGRATE_HOME=$(DEV_HOME)/home

run: build
	@mkdir -p $(DEV_HOME)/home; rm -f $(DEV_SOCKET)
	$(DEV_ENV) PATHFM_PLUGIN_DIR=$(ROOT)/target/release ./target/release/pathd & \
	sleep 0.5; $(DEV_ENV) $(QS) -p qml/shell.qml

daemon: build
	@mkdir -p $(DEV_HOME)/home; rm -f $(DEV_SOCKET)
	$(DEV_ENV) PATHFM_PLUGIN_DIR=$(ROOT)/target/release ./target/release/pathd

shell:
	$(DEV_ENV) $(QS) -p qml/shell.qml

# The checkout's own folders, gone: the next `make run` starts as a first run.
dev-clean:
	rm -rf $(DEV_HOME) $(DEV_SOCKET)

fmt:
	$(CARGO) fmt --all

lint: clippy
	$(CARGO) fmt --all -- --check
	python3 tests/identity_check.py
	python3 tests/branding_check.py
	python3 tests/packaging_hooks_check.py
	python3 tests/fedora_packaging_check.py
	python3 tests/fedora_license_check.py
	python3 tests/i18n_check.py
	@# One version in Cargo.toml, the window and the packages: the socket is named for it.
	python3 tests/version_check.py

clean:
	$(CARGO) clean
	rm -rf tests/e2e/out

# Line coverage for the daemon, with the LLVM tools that ship with the system toolchain
# (no cargo-llvm-cov needed). Writes a summary and leaves the profile data for `llvm-cov show`.
coverage:
	@rm -rf target/coverage && mkdir -p target/coverage
	@RUSTFLAGS="-C instrument-coverage" LLVM_PROFILE_FILE="$(PWD)/target/coverage/k-%p-%m.profraw" \
		$(CARGO) test -p pathd --tests --no-run --message-format=json 2>/dev/null \
		| python3 -c "import json,sys;[print(m['executable']) for m in (json.loads(l) for l in sys.stdin if l.startswith('{')) if m.get('profile',{}).get('test') and m.get('executable')]" \
		> target/coverage/bins.txt
	@LLVM_PROFILE_FILE="$(PWD)/target/coverage/k-%p-%m.profraw" PATHFM_PLUGIN_DIR="$(PWD)/target/debug" \
		sh -c 'while read b; do "$$b" --include-ignored >/dev/null 2>&1; done < target/coverage/bins.txt'
	@llvm-profdata merge -sparse target/coverage/*.profraw -o target/coverage/all.profdata
	@llvm-cov report --instr-profile=target/coverage/all.profdata \
		$$(sed 's/^/-object /' target/coverage/bins.txt | tr '\n' ' ') \
		--ignore-filename-regex='(/\.cargo/|/rustc/|/tests?\.rs$$)'
