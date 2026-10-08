#!/usr/bin/env python3
"""Exercise the Fedora RPM install contract without installing on the host."""
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = ROOT / "packaging/fedora/path.spec"


class FedoraPackaging(unittest.TestCase):
    def spec(self):
        self.assertTrue(SPEC.is_file(), "missing Fedora RPM spec")
        return SPEC.read_text()

    def test_version_and_offline_build(self):
        text = self.spec()
        version = tomllib.loads((ROOT / "Cargo.toml").read_text())["workspace"]["package"]["version"]
        self.assertRegex(text, rf"(?m)^Version:\s+{re.escape(version)}$")
        self.assertIn("cargo build --release --frozen", text)
        self.assertIn("cargo test --frozen", text)
        self.assertNotIn("cargo test --release", text)
        self.assertIn('export CARGO_TARGET_DIR="${PATHFM_RPM_TARGET_DIR:-target}"', text)
        self.assertIn('replace-with = "vendored-sources"', text)
        self.assertIn("Source1:", text)
        self.assertNotRegex(text, r"(?m)^\s*(?:curl|wget|sudo)\b")

    def test_runtime_dependencies_and_user_units(self):
        text = self.spec()
        for package in ("quickshell", "qt6-qtdeclarative", "qt6-qtmultimedia",
                        "xdg-desktop-portal", "xdg-desktop-portal-gtk", "libsecret",
                        "gnome-keyring", "bsdtar", "udisks2", "poppler-utils", "gvfs"):
            self.assertRegex(text, rf"(?m)^Requires:\s+{re.escape(package)}(?:\s|$)")
        for tool in ("ffmpeg", "ffprobe"):
            self.assertRegex(text, rf"(?m)^Requires:\s+/usr/bin/{tool}$")
        self.assertIn("%systemd_user_post pathfm.socket", text)
        self.assertIn("%systemd_user_preun pathfm.socket pathd.service", text)
        self.assertNotIn("xdg-mime default", text)
        self.assertNotIn("systemctl --global enable", text)
        self.assertNotIn("%{_sysconfdir}/", text)

    def test_bundled_licenses_are_verified_and_shipped(self):
        text = self.spec()
        self.assertIn("python3 packaging/fedora/license_bundle.py", text)
        self.assertIn("%license LICENSE target/license-bundle", text)
        self.assertIn("%include %{SOURCE2}", text)
        self.assertRegex(text, r"(?m)^License:.*Unicode-3\.0")
        self.assertRegex(text, r"(?m)^License:.*CDLA-Permissive-2\.0")
        self.assertIn("--filter-platform x86_64-unknown-linux-gnu", text)

    def test_install_is_staged_and_preserves_assets(self):
        text = self.spec()
        script = text.split("\n%install\n", 1)[1].split("\n%check\n", 1)[0]
        with tempfile.TemporaryDirectory(prefix="path-rpm-contract-") as temp:
            temp = Path(temp)
            source = temp / "source"
            source.mkdir()
            for name in ("packaging", "qml", "app-images"):
                shutil.copytree(ROOT / name, source / name)
            binaries = ("pathd", "path-thumber", "path-plugin-sftp", "path-plugin-ftps",
                        "path-plugin-gio", "path-plugin-dbus", "path-plugin-share-mail",
                        "path-plugin-share-tailscale")
            release = source / "target/release"
            release.mkdir(parents=True)
            for binary in binaries:
                (release / binary).write_text("#!/bin/sh\nexit 0\n")
            stage = temp / "stage"
            home = temp / "home"
            home.mkdir()
            sentinel = home / "mimeapps.list"
            sentinel.write_text("preserve my defaults\n")
            macros = {"buildroot": str(stage), "_bindir": "/usr/bin", "_datadir": "/usr/share",
                      "_userunitdir": "/usr/lib/systemd/user", "version": "0.2.2"}
            for key, value in macros.items():
                script = script.replace("%{" + key + "}", value)
            self.assertNotIn("%{", script, "unexpanded install macro")
            subprocess.run(["bash", "-eu", "-c", script], cwd=source,
                           env=dict(os.environ, HOME=str(home)), check=True, capture_output=True)
            self.assertEqual(sentinel.read_text(), "preserve my defaults\n")
            self.assertEqual(list(home.iterdir()), [sentinel])
            for name in ("pathd", "pathfm"):
                self.assertTrue(os.access(stage / "usr/bin" / name, os.X_OK))
            for name in ("sftp", "ftps", "smb", "dbus", "share-mail", "share-tailscale"):
                self.assertTrue(os.access(stage / "usr/lib/path/plugins" / f"path-plugin-{name}", os.X_OK))
            self.assertTrue(os.access(stage / "usr/lib/path/path-thumber", os.X_OK))
            for asset, installed in (
                ("app-images/path-app-list.png", "usr/share/icons/hicolor/512x512/apps/pathfm.png"),
                ("qml/path/assets/path-about.png", "usr/share/path/path/assets/path-about.png"),
            ):
                self.assertEqual((ROOT / asset).read_bytes(), (stage / installed).read_bytes())
            socket = (stage / "usr/lib/systemd/user/pathfm.socket").read_text()
            self.assertIn("ListenStream=%t/pathfm-0.2.2.sock", socket)
            self.assertNotIn("@VERSION@", socket)
            self.assertTrue((stage / "usr/share/path/shell.qml").is_file())
            self.assertTrue((stage / "usr/share/xdg-desktop-portal/portals/path.portal").is_file())
            self.assertFalse((stage / "etc").exists())
            self.assertFalse((stage / "usr/bin/path-plugin-stub").exists())


if __name__ == "__main__":
    unittest.main()
