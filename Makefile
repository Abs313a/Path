QMLTESTRUNNER ?= /usr/lib/qt6/bin/qmltestrunner
CARGO ?= cargo
QS ?= qs
ROOT := $(shell pwd)
VERSION ?= $(shell sed -n 's/^version = "\(.*\)"/\1/p' Cargo.toml | head -1)

PREFIX ?= /usr
BINDIR ?= $(PREFIX)/bin
LIBDIR ?= $(PREFIX)/lib
DATADIR ?= $(PREFIX)/share
SYSTEMD_USER_DIR ?= $(LIBDIR)/systemd/user

.PHONY: all build install uninstall test clippy test-rust test-qml test-e2e fmt lint clean dev-clean run daemon shell

all: build

## Build pathd daemon, plugins, and helper binaries.
build:
	$(CARGO) build --release
	@ln -sf path-plugin-gio target/release/path-plugin-smb

## Install binaries, QML shell, desktop files, and systemd user services.
install: build
	install -d $(DESTDIR)$(BINDIR)
	install -m 755 target/release/pathd $(DESTDIR)$(BINDIR)/pathd
	install -m 755 packaging/bin/pathfm $(DESTDIR)$(BINDIR)/pathfm
	install -d $(DESTDIR)$(LIBDIR)/path/plugins
	install -m 755 target/release/path-thumber $(DESTDIR)$(LIBDIR)/path/path-thumber
	for plugin in sftp ftps dbus share-mail share-tailscale; do \
		install -m 755 target/release/path-plugin-$$plugin $(DESTDIR)$(LIBDIR)/path/plugins/path-plugin-$$plugin; \
	done
	install -m 755 target/release/path-plugin-gio $(DESTDIR)$(LIBDIR)/path/plugins/path-plugin-smb
	install -d $(DESTDIR)$(DATADIR)/path
	cp -a qml/. $(DESTDIR)$(DATADIR)/path/
	install -d $(DESTDIR)$(SYSTEMD_USER_DIR)
	install -m 644 packaging/systemd/pathd.service $(DESTDIR)$(SYSTEMD_USER_DIR)/pathd.service
	sed 's/@VERSION@/$(VERSION)/g' packaging/systemd/pathfm.socket > $(DESTDIR)$(SYSTEMD_USER_DIR)/pathfm.socket
	chmod 644 $(DESTDIR)$(SYSTEMD_USER_DIR)/pathfm.socket
	install -d $(DESTDIR)$(DATADIR)/applications
	install -m 644 packaging/pathfm.desktop $(DESTDIR)$(DATADIR)/applications/pathfm.desktop
	install -d $(DESTDIR)$(DATADIR)/icons/hicolor/512x512/apps
	install -m 644 app-images/path-app-list.png $(DESTDIR)$(DATADIR)/icons/hicolor/512x512/apps/pathfm.png
	install -d $(DESTDIR)$(DATADIR)/dbus-1/services
	install -m 644 packaging/org.freedesktop.impl.portal.desktop.pathfm.service $(DESTDIR)$(DATADIR)/dbus-1/services/
	install -d $(DESTDIR)$(DATADIR)/xdg-desktop-portal/portals
	install -m 644 packaging/path.portal $(DESTDIR)$(DATADIR)/xdg-desktop-portal/portals/path.portal

## Remove all files installed by make install.
uninstall:
	rm -f $(DESTDIR)$(BINDIR)/pathd
	rm -f $(DESTDIR)$(BINDIR)/pathfm
	rm -rf $(DESTDIR)$(LIBDIR)/path
	rm -rf $(DESTDIR)$(DATADIR)/path
	rm -f $(DESTDIR)$(SYSTEMD_USER_DIR)/pathd.service
	rm -f $(DESTDIR)$(SYSTEMD_USER_DIR)/pathfm.socket
	rm -f $(DESTDIR)$(DATADIR)/applications/pathfm.desktop
	rm -f $(DESTDIR)$(DATADIR)/icons/hicolor/512x512/apps/pathfm.png
	rm -f $(DESTDIR)$(DATADIR)/dbus-1/services/org.freedesktop.impl.portal.desktop.pathfm.service
	rm -f $(DESTDIR)$(DATADIR)/xdg-desktop-portal/portals/path.portal

test: clippy test-rust test-qml test-e2e

clippy:
	$(CARGO) clippy --all-targets -- -D warnings

test-rust:
	$(CARGO) test

## Headless QML interaction tests running under offscreen Qt platform.
test-qml: export QT_QPA_PLATFORM = offscreen
test-qml: export LANGUAGE = en
test-qml:
	@mkdir -p target
	$(QMLTESTRUNNER) -import tests/qml/stubs -input tests/qml
	QT_QPA_PLATFORM=minimal $(QMLTESTRUNNER) -import tests/qml/stubs -input tests/qml-drag

test-e2e: build
	tests/e2e/run.sh

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
	python3 tests/x11_pure_check.py
	python3 tests/version_check.py

clean:
	$(CARGO) clean
	rm -rf tests/e2e/out target

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

dev-clean:
	rm -rf $(DEV_HOME) $(DEV_SOCKET)
