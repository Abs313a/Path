# COPR SCM builds must select the full reviewed commit in the SCM committish field.
repo := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
commit ?=
spec ?= packaging/fedora/path.spec
outdir ?= $(repo)/target/srpm

.PHONY: srpm
srpm:
	@set -eu; \
	for tool in cargo rpmbuild python3 git tar gzip; do \
		if ! command -v "$$tool" >/dev/null; then \
			dnf -y install cargo rpm-build python3 git tar gzip; \
			break; \
		fi; \
	done; \
	source_commit="$(commit)"; \
	if test -z "$$source_commit"; then \
		source_commit="$$(git -C "$(repo)" rev-parse HEAD)"; \
	fi; \
	python3 "$(repo)/packaging/fedora/make_srpm.py" --commit "$$source_commit" --outdir "$(outdir)" --spec "$(spec)"
