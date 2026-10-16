#!/usr/bin/env python3
"""Focused checks for revision-pinned Fedora Poppler license supplements."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "license_bundle", Path(__file__).resolve().parents[1] / "packaging/fedora/license_bundle.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PopplerLicenseTests(unittest.TestCase):
    def metadata(self, vendor, revision):
        packages = []
        nodes = []
        for name in ("poppler-rs", "poppler-sys-rs"):
            crate = vendor / f"{name}-0.26.0"
            crate.mkdir()
            (crate / "Cargo.toml").write_text("")
            (crate / ".cargo_vcs_info.json").write_text(json.dumps({"git": {"sha1": revision}}))
            packages.append({"id": name, "name": name, "version": "0.26.0",
                             "manifest_path": str(crate / "Cargo.toml"),
                             "source": "registry", "license": "MIT"})
            nodes.append({"id": name, "deps": []})
        return {"packages": packages, "resolve": {"nodes": nodes},
                "workspace_default_members": [p["id"] for p in packages]}

    def test_both_crates_receive_mit_text_and_revision_inventory(self):
        with tempfile.TemporaryDirectory() as work:
            vendor = Path(work) / "vendor"
            vendor.mkdir()
            revision = "dabba607b8987245708a06ee08817f3a6923c20c"
            out = Path(work) / "licenses"
            entries = module.bundle(self.metadata(vendor, revision), vendor, out)
            self.assertEqual(len(entries), 2)
            for entry in entries:
                self.assertEqual(entry["supplement_revision"], revision)
                text = (out / f'{entry["name"]}-0.26.0/LICENSE.MIT').read_text()
                self.assertIn("Permission is hereby granted, free of charge", text)
                self.assertIn("THE SOFTWARE IS PROVIDED", text)
            self.assertFalse(any(vendor.rglob("LICENSE*")), "vendor sources must remain intact")

    def test_unknown_revision_is_rejected(self):
        with tempfile.TemporaryDirectory() as work:
            vendor = Path(work) / "vendor"
            vendor.mkdir()
            with self.assertRaisesRegex(ValueError, "supplement revision mismatch"):
                module.bundle(self.metadata(vendor, "0" * 40), vendor, Path(work) / "licenses")


if __name__ == "__main__":
    unittest.main()
