#!/usr/bin/env python3
"""Assert supplied branding assets and desktop packaging without host mutation."""
import hashlib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class Branding(unittest.TestCase):
    def test_supplied_assets(self):
        expected = {
            "app-images/path-app-list.png": "8d434843f650ceab00a0423efd314a71068d89a76af1972126f69e8a692dd2b8",
            "qml/path/assets/path-about.png": "78112d3b027f282480745c17a748409f8963d64d7ef49d04496d066d0c521c58",
        }
        for name, digest in expected.items():
            with self.subTest(asset=name):
                self.assertEqual(hashlib.sha256((ROOT / name).read_bytes()).hexdigest(), digest)

    def test_desktop_icon_packaging(self):
        source = (ROOT / "packaging/PKGBUILD").read_text()
        self.assertIn('app-images/path-app-list.png', source)
        self.assertIn('hicolor/512x512/apps/pathfm.png', source)
        self.assertNotIn('cat-head-wireframe.svg', source)


if __name__ == "__main__":
    unittest.main()
