#!/usr/bin/env python3
"""Install/upgrade/remove Path only inside a disposable Fedora 44 container."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import tempfile


def check_environment(container, uid, release):
    if not container or uid != 0 or release.get("ID") != "fedora" or release.get("VERSION_ID") != "44":
        raise ValueError("Fedora 44 disposable container required (root inside container only)")


def run(*command):
    return subprocess.run(command, check=True, text=True, capture_output=True).stdout


def lifecycle(old, new):
    release = dict(line.split("=", 1) for line in Path("/etc/os-release").read_text().splitlines() if "=" in line)
    release = {k: v.strip('"') for k, v in release.items()}
    check_environment(Path("/.dockerenv").is_file() or Path("/run/.containerenv").is_file(), os.geteuid(), release)
    if platform.machine() != "x86_64":
        raise ValueError("x86_64 container required")
    for rpm in (old, new):
        if run("rpm", "-qp", "--qf", "%{NAME}", str(rpm)) != "path":
            raise ValueError("only the Path package may be tested")
    if subprocess.run(["rpm", "-q", "path"], capture_output=True).returncode == 0:
        raise ValueError("container already has Path installed; refusing to alter it")
    with tempfile.TemporaryDirectory(prefix="path-lifecycle-") as tmp:
        home = Path(tmp)
        sentinels = {
            ".config/mimeapps.list": "[Default Applications]\ninode/directory=thunar.desktop\n",
            ".config/xdg-desktop-portal/portals.conf": "[preferred]\ndefault=gtk\n",
            ".config/dwm-titus/hotkeys.toml": "preserve hotkeys\n",
            ".config/dwm-titus/window-rules.toml": "preserve window rules\n",
            ".config/path/settings.toml": "[view]\nshowHidden=true\n",
            ".config/path/integration.toml": "[mime]\ninode/directory=\"thunar.desktop\"\n",
            ".local/share/dbus-1/services/org.freedesktop.FileManager1.service": "preserve activation\n",
        }
        for name, text in sentinels.items():
            target = home / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text)
        # HOME is scoped to the test subprocesses, never the invoking host environment.
        def transaction(*command):
            result = subprocess.run(command, env=dict(os.environ, HOME=str(home)), check=True, text=True, capture_output=True)
            for name, text in sentinels.items():
                if (home / name).read_text() != text:
                    raise AssertionError(f"transaction changed user file: {name}")
            return result.stdout
        transaction("rpm", "-Uvh", "--nosignature", str(old))
        run("rpm", "-V", "path")
        transaction("rpm", "-Uvh", "--nosignature", str(new))
        run("rpm", "-V", "path")
        installed = run("rpm", "-q", "--qf", "%{VERSION}-%{RELEASE}", "path")
        expected = run("rpm", "-qp", "--qf", "%{VERSION}-%{RELEASE}", str(new))
        if installed != expected:
            raise AssertionError("upgrade did not install the expected release")
        bundle = Path("/usr/share/licenses/path/license-bundle")
        inventory = json.loads((bundle / "BUNDLED-LICENSES.json").read_text())
        if not inventory:
            raise AssertionError("empty bundled-license inventory")
        for package in inventory:
            for notice in package["notices"]:
                if hashlib.sha256((bundle / notice["file"]).read_bytes()).hexdigest() != notice["sha256"]:
                    raise AssertionError("installed license notice differs from the inventory")
        files = [line.split(" ", 1)[0] for line in run("rpm", "-q", "--qf", "[%{FILENAMES} %{FILEMODES:perms}\\n]", "path").splitlines()
                 if not line.split(" ", 1)[1].startswith("d")]
        transaction("rpm", "-e", "path")
        if subprocess.run(["rpm", "-q", "path"], capture_output=True).returncode == 0:
            raise AssertionError("package remains installed after removal")
        for name in files:
            if Path(name).exists() or Path(name).is_symlink():
                raise AssertionError(f"owned file remains after removal: {name}")
        print(f"lifecycle passed: install, upgrade to {installed}, verify {len(inventory)} licensed dependencies, remove, preserve user files")
        print("Container has no live user manager: desktop user-unit/runtime behavior is a separate VM gate.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("old", type=Path)
    parser.add_argument("new", type=Path)
    args = parser.parse_args()
    lifecycle(args.old.resolve(), args.new.resolve())
