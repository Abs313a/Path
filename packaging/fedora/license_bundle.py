#!/usr/bin/env python3
"""Produce an offline RPM license inventory from Cargo's filtered dependency graph."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

SUPPLEMENTS = {
    ("delegate", "0.13.5"): ("b129d4cbf4cc499eff7743365dcb0fe5d8d2e820", "delegate"),
    ("lazy-regex-proc_macros", "3.6.1"): ("39a459c01e1ba2488075be50a821e2d72e466241", "lazy-regex"),
    ("russh", "0.52.1"): ("5e913966780dc226f52367be1a6666ddfcee81dc", "russh-0.52.1"),
    ("russh-cryptovec", "0.52.0"): ("3d09c20c52a542ffa327723d3a44cb1edd9b0ca4", "russh-0.52.0"),
    ("russh-util", "0.52.0"): ("3d09c20c52a542ffa327723d3a44cb1edd9b0ca4", "russh-0.52.0"),
    ("suppaftp", "6.3.0"): ("96cb46417e65ccb0f9f0b7ec8613c141c151c6b5", "suppaftp"),
}
# Expressions inspected in this lockfile. A new expression needs review, not a guessed license.
KNOWN = {
    "MIT", "Apache-2.0", "ISC", "Zlib", "BSD-3-Clause", "CDLA-Permissive-2.0",
    "MIT OR Apache-2.0", "Apache-2.0 OR MIT", "Unlicense OR MIT",
    "0BSD OR MIT OR Apache-2.0", "Zlib OR Apache-2.0 OR MIT",
    "Apache-2.0 WITH LLVM-exception OR Apache-2.0 OR MIT",
    "MIT OR Zlib OR Apache-2.0", "BSD-3-Clause OR Apache-2.0", "Apache-2.0 AND ISC",
    "Apache-2.0 OR ISC OR MIT", "Apache-2.0 WITH LLVM-exception",
    "(MIT OR Apache-2.0) AND Unicode-3.0", "BSD-2-Clause OR Apache-2.0 OR MIT",
    "MIT OR Apache-2.0 OR Zlib",
}


def bundle(metadata, vendor, out):
    vendor = Path(vendor).resolve()
    out = Path(out)
    if out.exists():
        raise ValueError("license output already exists")
    nodes = {node["id"]: node for node in metadata["resolve"]["nodes"]}
    pending = list(metadata["workspace_default_members"])
    reachable = set()
    while pending:
        ident = pending.pop()
        if ident in reachable:
            continue
        reachable.add(ident)
        for dep in nodes[ident]["deps"]:
            if any(kind["kind"] != "dev" for kind in dep["dep_kinds"]):
                pending.append(dep["pkg"])
    entries = []
    copies = []
    for package in sorted(metadata["packages"], key=lambda p: (p["name"], p["version"])):
        if package["id"] not in reachable or not package["source"]:
            continue
        name, version = package["name"], package["version"]
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name) or not re.fullmatch(r"[A-Za-z0-9.+-]+", version):
            raise ValueError("unsafe package identity")
        crate = Path(package["manifest_path"]).resolve().parent
        if not crate.is_relative_to(vendor):
            raise ValueError(f"{name} {version}: manifest outside vendor")
        declared = package["license"] or ""
        expression = re.sub(r"\s*/\s*", " OR ", declared).strip()
        if expression not in KNOWN:
            raise ValueError(f"{name} {version}: unreviewed license expression: {declared}")
        files = [(p, p.relative_to(crate)) for p in sorted(crate.rglob("*"))
                 if p.is_file() and p.name.lower().startswith(("license", "licence", "copying", "notice", "copyright"))]
        if package.get("license_file"):
            p = crate / package["license_file"]
            if (p, p.relative_to(crate)) not in files:
                files.append((p, p.relative_to(crate)))
        supplement = None
        if not files and (name, version) in SUPPLEMENTS:
            revision, directory = SUPPLEMENTS[name, version]
            vcs = json.loads((crate / ".cargo_vcs_info.json").read_text())
            if vcs["git"]["sha1"] != revision:
                raise ValueError(f"{name} {version}: supplement revision mismatch")
            supplement = revision
            source = Path(__file__).parent / "license-supplements" / directory
            files = [(p, Path(p.name)) for p in sorted(source.iterdir()) if p.is_file()]
        if not files:
            raise ValueError(f"{name} {version}: missing license text")
        notices = []
        for source, relative in files:
            if source.is_symlink() or ".." in relative.parts or relative.is_absolute():
                raise ValueError(f"{name} {version}: unsafe license path")
            source.read_text(encoding="utf-8")  # Fail on unreadable or binary notice files.
            destination = Path(f"{name}-{version}") / relative
            notices.append({"file": destination.as_posix(), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})
            copies.append((source, destination))
        entries.append({"name": name, "version": version, "declared_license": declared,
                        "license_expression": expression, "supplement_revision": supplement, "notices": notices})
    out.mkdir(parents=True)
    for source, destination in copies:
        target = out / destination
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    (out / "BUNDLED-LICENSES.json").write_text(json.dumps(entries, indent=2) + "\n")
    expressions = sorted({p["license_expression"] for p in entries} | {"MIT"})
    (out / "LICENSE-EXPRESSION").write_text(" AND ".join(f"({e})" if " " in e else e for e in expressions) + "\n")
    (out / "BUNDLED-PROVIDES.inc").write_text("".join(
        "Provides: bundled(crate({})) = {}\n".format(p["name"], p["version"].replace("-", "~")) for p in entries))
    return entries


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path)
    parser.add_argument("vendor", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    inventory = bundle(json.loads(args.metadata.read_text()), args.vendor, args.output)
    print(f"license bundle: {len(inventory)} build dependencies with preserved notices")
