#!/usr/bin/env python3
"""Reject legacy product identity and assert Path's public identity contract."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LEGACY = b"ki" + b"ki"

REQUIRED_PATHS = (
    "pathd/Cargo.toml",
    "crates/path-json/Cargo.toml",
    "crates/path-plugin-sdk/Cargo.toml",
    "plugins/path-plugin-sftp/Cargo.toml",
    "qml/path/qmldir",
    "packaging/bin/pathfm",
    "packaging/pathfm.desktop",
    "packaging/systemd/pathfm.socket",
    "packaging/systemd/pathd.service",
    "packaging/org.freedesktop.impl.portal.desktop.pathfm.service",
    "packaging/path.portal",
)

REQUIRED_TEXT = {
    "Makefile": ("python3 tests/branding_check.py", "python3 tests/packaging_hooks_check.py"),
    "packaging/fedora/path.spec": ("python3 tests/branding_check.py", "python3 tests/packaging_hooks_check.py"),
    "Cargo.toml": (
        'members = ["pathd",',
        'repository = "https://github.com/Abs313a/Path"',
    ),
    "install.sh": ('repo="Abs313a/Path"', "PATHFM_VERSION", "PATHFM_PACKAGE"),
    "packaging/PKGBUILD": ("pkgname=path", 'url="https://github.com/Abs313a/Path"'),
    "packaging/pathfm.desktop": (
        "Name=Path",
        "Exec=pathfm %U",
        "Icon=pathfm",
    ),
    "packaging/org.freedesktop.impl.portal.desktop.pathfm.service": (
        "Name=org.freedesktop.impl.portal.desktop.pathfm",
        "Exec=/usr/bin/pathd",
        "SystemdService=pathd.service",
    ),
    "packaging/systemd/pathfm.socket": ("ListenStream=%t/pathfm-@VERSION@.sock", "Service=pathd.service"),
    "packaging/systemd/pathd.service": ("Requires=pathfm.socket", "ExecStart=/usr/bin/pathd"),
    "pathd/src/integrate.rs": (
        'DESKTOP_ID: &str = "pathfm.desktop"',
        'PORTAL_NAME: &str = "org.freedesktop.impl.portal.desktop.pathfm"',
    ),
    "plugins/path-plugin-dbus/src/main.rs": ('.name("org.freedesktop.impl.portal.desktop.pathfm")?',),
    "packaging/path.portal": (
        "DBusName=org.freedesktop.impl.portal.desktop.pathfm",
    ),
    "qml/path/qmldir": ("module path",),
    "qml/path/Shell.qml": ('title: "Path"',),
    "qml/path/ui/AboutDialog.qml": ('text: "Path";',),
    "qml/path/ui/IntegrationDialog.qml": ('"Make Path the default"',),
    "tests/e2e/flows/launcher.py": ('os.path.join(HERE, "packaging", "bin", "pathfm")',),
    ".github/workflows/ci.yml": ("path-package-${{ matrix.arch }}",),
    ".github/workflows/release.yml": ("path-package-*", "Abs313a/Path"),
}

DISPLAY_KEYS = (
    "menu.about", "quit.title", "settings.makeDefault", "settings.isDefault",
    "settings.removeFromDwmTitus", "location.verifyNote",
    "integration.title", "daemon.versionMismatch",
)


def tracked_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"], cwd=ROOT, check=True, capture_output=True
    )
    # Historical documentation and README files are outside the shipped identity contract.
    # Include unstaged renames and new files so the check also works before committing.
    return sorted({name for name in result.stdout.decode().split("\0")
                   if name and not name.startswith("docs/")
                   and Path(name).name != "README.md" and (ROOT / name).is_file()})


def main() -> int:
    failures: list[str] = []
    files = tracked_files()

    legacy_paths = [name for name in files if LEGACY in name.lower().encode()]
    if legacy_paths:
        failures.append(f"legacy identity in {len(legacy_paths)} tracked paths")

    legacy_content_files: list[str] = []
    noncanonical_env_files: list[str] = []
    for name in files:
        content = (ROOT / name).read_bytes()
        if LEGACY in content.lower():
            legacy_content_files.append(name)
        if re.search(rb"\bPATHFM[A-Z][A-Z0-9_]*\b", content):
            noncanonical_env_files.append(name)
    if legacy_content_files:
        failures.append(f"legacy identity in {len(legacy_content_files)} tracked files")
    if noncanonical_env_files:
        failures.append("environment names outside PATHFM_*: " + ", ".join(noncanonical_env_files))

    missing_paths = [name for name in REQUIRED_PATHS if name not in files]
    if missing_paths:
        failures.append("missing canonical paths: " + ", ".join(missing_paths))

    for name, needles in REQUIRED_TEXT.items():
        path = ROOT / name
        if not path.is_file():
            failures.append(f"missing canonical contract file: {name}")
            continue
        text = path.read_text(encoding="utf-8")
        missing = [needle for needle in needles if needle not in text]
        if missing:
            failures.append(f"{name} missing canonical text: " + ", ".join(missing))

    for language in ("en", "es", "ja"):
        name = f"qml/path/i18n/{language}.js"
        if not (ROOT / name).is_file():
            failures.append(f"missing display catalog: {name}")
            continue
        text = (ROOT / name).read_text(encoding="utf-8")
        for key in DISPLAY_KEYS:
            entry = re.search(rf'^\s*"{re.escape(key)}":\s*"(.*)"', text, re.MULTILINE)
            if entry is None or "Path" not in entry.group(1):
                failures.append(f"{name}: {key} must display Path")

    if failures:
        print("identity contract failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("identity contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
