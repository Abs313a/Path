#!/usr/bin/env python3
"""Reject Wayland/Hyprland runtime dependencies and assert pure X11 contract."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

FORBIDDEN_RUNTIME_PATTERNS = [
    (re.compile(r"\bhyprctl\b"), "hyprctl invocation"),
    (re.compile(r"\bwl-copy\b"), "wl-copy invocation"),
    (re.compile(r"\bwl-paste\b"), "wl-paste invocation"),
]

RUNTIME_DIRS = ("qml", "pathd", "crates", "plugins", "packaging/bin")


def tracked_runtime_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files", "-z", *RUNTIME_DIRS],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    return [name for name in result.stdout.decode().split("\0") if name and (ROOT / name).is_file()]


def main() -> int:
    failures: list[str] = []
    files = tracked_runtime_files()

    for rel_path in files:
        content = (ROOT / rel_path).read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(content.splitlines(), start=1):
            for pattern, desc in FORBIDDEN_RUNTIME_PATTERNS:
                if pattern.search(line):
                    failures.append(f"{rel_path}:{line_no} contains {desc}: {line.strip()}")

    # Assert X11 contracts in Shell.qml and Breadcrumb.qml
    shell_qml = ROOT / "qml/path/Shell.qml"
    if shell_qml.is_file():
        shell_text = shell_qml.read_text(encoding="utf-8")
        if "xclip" not in shell_text:
            failures.append("qml/path/Shell.qml must use xclip for clipboard operations")
        if "xdotool" not in shell_text:
            failures.append("qml/path/Shell.qml must use xdotool for window activation (raise)")
    else:
        failures.append("qml/path/Shell.qml not found")

    breadcrumb_qml = ROOT / "qml/path/ui/Breadcrumb.qml"
    if breadcrumb_qml.is_file():
        bc_text = breadcrumb_qml.read_text(encoding="utf-8")
        if "xclip" not in bc_text:
            failures.append("qml/path/ui/Breadcrumb.qml must use xclip for clipboard operations")
    else:
        failures.append("qml/path/ui/Breadcrumb.qml not found")

    if failures:
        print("pure X11 verification failed:", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1

    print("pure X11 verification passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
