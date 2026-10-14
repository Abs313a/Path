# COPR SCM builds must select the full reviewed commit in the SCM committish field.
repo := $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/..)
commit ?= $(shell git -C "$(repo)" rev-parse HEAD)
spec ?= packaging/fedora/path.spec
outdir ?= $(repo)/target/srpm

.PHONY: srpm
srpm:
	dnf -y install cargo rpm-build python3 git tar gzip
	python3 "$(repo)/packaging/fedora/make_srpm.py" --commit "$(commit)" --outdir "$(outdir)" --spec "$(spec)"
