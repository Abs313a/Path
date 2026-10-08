#!/usr/bin/env python3
"""Test the offline license bundle against small, isolated dependency graphs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "packaging/fedora/license_bundle.py"


class LicenseBundle(unittest.TestCase):
    def setUp(self):
        self.assertTrue(SCRIPT.is_file(), "missing offline license bundler")
        spec = importlib.util.spec_from_file_location("license_bundle", SCRIPT)
        self.module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.module)
        self.temp = tempfile.TemporaryDirectory(prefix="path-license-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.vendor = self.root / "vendor"
        self.vendor.mkdir()

    def metadata(self, notice=True):
        crate = self.vendor / "sample-1.0.0"
        crate.mkdir()
        (crate / "Cargo.toml").write_text('[package]\nname="sample"\nversion="1.0.0"\n')
        if notice:
            (crate / "LICENSE-MIT").write_text("Copyright Sample Authors\nMIT terms\n")
        return {"workspace_default_members": ["root"], "packages": [
            {"id": "sample", "name": "sample", "version": "1.0.0", "source": "registry+crates.io",
             "license": "MIT/Apache-2.0", "license_file": None, "manifest_path": str(crate / "Cargo.toml")},
        ], "resolve": {"nodes": [
            {"id": "root", "deps": [{"pkg": "sample", "dep_kinds": [{"kind": None}]}]},
            {"id": "sample", "deps": []},
        ]}}

    def test_inventory_and_exact_license_text(self):
        out = self.root / "out"
        self.module.bundle(self.metadata(), self.vendor, out)
        entries = json.loads((out / "BUNDLED-LICENSES.json").read_text())
        self.assertEqual([(p["name"], p["version"]) for p in entries], [("sample", "1.0.0")])
        self.assertIn("(MIT OR Apache-2.0)", (out / "LICENSE-EXPRESSION").read_text())
        self.assertEqual((out / "sample-1.0.0/LICENSE-MIT").read_text(), "Copyright Sample Authors\nMIT terms\n")
        self.assertNotIn(str(self.root), (out / "BUNDLED-LICENSES.json").read_text())
        self.assertEqual((out / "BUNDLED-PROVIDES.inc").read_text(), "Provides: bundled(crate(sample)) = 1.0.0\n")

    def test_missing_notice_fails_closed(self):
        with self.assertRaisesRegex(ValueError, "sample 1.0.0: missing license text"):
            self.module.bundle(self.metadata(notice=False), self.vendor, self.root / "out")

    def test_unreachable_dev_dependency_is_not_bundled(self):
        m = self.metadata()
        m["resolve"]["nodes"][0]["deps"].append({"pkg": "test-only", "dep_kinds": [{"kind": "dev"}]})
        self.module.bundle(m, self.vendor, self.root / "out")
        self.assertEqual(len(json.loads((self.root / "out/BUNDLED-LICENSES.json").read_text())), 1)

    def test_manifest_outside_vendor_is_rejected(self):
        m = self.metadata()
        m["packages"][0]["manifest_path"] = str(self.root / "Cargo.toml")
        with self.assertRaisesRegex(ValueError, "outside vendor"):
            self.module.bundle(m, self.vendor, self.root / "out")


if __name__ == "__main__":
    unittest.main()
