#!/usr/bin/env bash
set -euo pipefail

root="${1:-target/fixtures}"
clean="${2:-}"

if [[ "$clean" == "--clean" ]]; then
  rm -rf -- "$root"
elif [[ -n "$clean" ]]; then
  echo "usage: $0 [ROOT] [--clean]" >&2
  exit 2
fi

python3 - "$root" <<'PY'
import os
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
root.mkdir(parents=True, exist_ok=True)

extensions = ("txt", "rs", "md", "json", "png", "log")
for count in (1_000, 10_000, 100_000):
    directory = root / str(count)
    directory.mkdir(parents=True, exist_ok=True)
    print(f"Generating {count:,} deterministic entries in {directory}", flush=True)
    for index in range(count):
        if index % 20 == 0:
            (directory / f"directory-{index:06d}").mkdir(exist_ok=True)
        else:
            extension = extensions[index % len(extensions)]
            path = directory / f"entry-{index:06d}.{extension}"
            if not path.exists():
                path.touch()

# A deterministic deep tree for path and cancellation testing.
deep = root / "deep"
current = deep
for depth in range(256):
    current = current / f"level-{depth:03d}"
    current.mkdir(parents=True, exist_ok=True)
    marker = current / "marker.txt"
    if not marker.exists():
        marker.touch()

edge = root / "edge-cases"
edge.mkdir(exist_ok=True)
broken = edge / "broken-link"
if not broken.exists() and not broken.is_symlink():
    broken.symlink_to("missing-target")

# Native-path test case; bytes paths preserve the intentionally invalid UTF-8 byte.
edge_bytes = os.fsencode(edge)
invalid_name = edge_bytes + b"/invalid-utf8-\xff"
try:
    descriptor = os.open(invalid_name, os.O_CREAT | os.O_WRONLY, 0o644)
    os.close(descriptor)
except FileExistsError:
    pass

print(f"Fixtures ready under {root}")
PY
