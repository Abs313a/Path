CARGO ?= cargo
PREFIX ?= /usr/local
DESTDIR ?=
PROFILE ?= release
CARGO_TARGET_DIR ?= target
BINARY = $(CARGO_TARGET_DIR)/$(PROFILE)/pathfm
APP_ID = io.github.christitustech.Path

.PHONY: all build install uninstall test test-rust test-e2e lint fmt chooser
all: build
build:
	$(CARGO) build --locked --profile $(PROFILE)

install:
	install -Dm755 $(BINARY) $(DESTDIR)$(PREFIX)/bin/pathfm
	install -Dm644 data/pathfm.desktop $(DESTDIR)$(PREFIX)/share/applications/pathfm.desktop
	install -Dm644 app-images/path-app-list.png $(DESTDIR)$(PREFIX)/share/icons/hicolor/512x512/apps/pathfm.png
	install -Dm644 app-images/path-app-list.png $(DESTDIR)$(PREFIX)/share/icons/hicolor/512x512/apps/$(APP_ID).png
	install -Dm644 data/$(APP_ID).FileManager1.service $(DESTDIR)$(PREFIX)/share/pathfm/$(APP_ID).FileManager1.service
	sed 's|@PATHFM_EXECUTABLE@|$(PREFIX)/bin/pathfm|g' data/portal/org.freedesktop.impl.portal.desktop.pathfm.service.in > $(CARGO_TARGET_DIR)/pathfm-portal.service
	install -Dm644 $(CARGO_TARGET_DIR)/pathfm-portal.service $(DESTDIR)$(PREFIX)/share/dbus-1/services/org.freedesktop.impl.portal.desktop.pathfm.service
	install -Dm644 data/portal/pathfm.portal $(DESTDIR)$(PREFIX)/share/xdg-desktop-portal/portals/pathfm.portal
	install -Dm644 LICENSE $(DESTDIR)$(PREFIX)/share/licenses/pathfm/LICENSE
	install -Dm644 THIRD_PARTY_LICENSES.md $(DESTDIR)$(PREFIX)/share/licenses/pathfm/THIRD_PARTY_LICENSES.md

uninstall:
	rm -f $(DESTDIR)$(PREFIX)/bin/pathfm
	rm -f $(DESTDIR)$(PREFIX)/share/applications/pathfm.desktop
	rm -f $(DESTDIR)$(PREFIX)/share/icons/hicolor/512x512/apps/pathfm.png
	rm -f $(DESTDIR)$(PREFIX)/share/icons/hicolor/512x512/apps/$(APP_ID).png
	rm -f $(DESTDIR)$(PREFIX)/share/pathfm/$(APP_ID).FileManager1.service
	rm -f $(DESTDIR)$(PREFIX)/share/dbus-1/services/org.freedesktop.impl.portal.desktop.pathfm.service
	rm -f $(DESTDIR)$(PREFIX)/share/xdg-desktop-portal/portals/pathfm.portal
	rm -f $(DESTDIR)$(PREFIX)/share/licenses/pathfm/LICENSE $(DESTDIR)$(PREFIX)/share/licenses/pathfm/THIRD_PARTY_LICENSES.md

test: test-rust test-e2e

test-rust:
	./scripts/quality.sh test

test-e2e:
	./scripts/e2e.sh

lint:
	./scripts/quality.sh fmt
	./scripts/quality.sh clippy
	python3 tests/branding_check.py

fmt:
	$(CARGO) fmt --all

chooser:
	./scripts/chooser-dev.sh
