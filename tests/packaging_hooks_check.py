#!/usr/bin/env python3
"""Exercise package hooks without changing host services or user preferences."""
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ("packaging/path.install", "packaging/aur/path-bin/path.install")
MOCK = """#!/bin/sh
command=${0##*/}
case "$command:$*" in
  'update-desktop-database:-q'|'gtk-update-icon-cache:-q /usr/share/icons/hicolor'|\
  'systemctl:--global enable pathfm.socket'|'systemctl:--global disable pathfm.socket')
    printf '%s %s\\n' "$command" "$*" >> "$HOOK_LOG" ;;
  *) printf 'unexpected package hook command: %s %s\\n' "$command" "$*" >> "$HOOK_LOG"; exit 64 ;;
esac
"""


class PackageHooks(unittest.TestCase):
    def invoke(self, hook, action):
        with tempfile.TemporaryDirectory(prefix="path-package-hooks-") as directory:
            temp = Path(directory)
            home = temp / "home"
            home.mkdir()
            preferences = home / "mimeapps.list"
            preferences.write_text("[Default Applications]\ninode/directory=Thunar.desktop\n")
            before = preferences.read_bytes()
            commands = temp / "bin"
            commands.mkdir()
            log = temp / "calls"
            log.touch()
            for name in ("xdg-mime", "systemctl", "update-desktop-database", "gtk-update-icon-cache"):
                mock = commands / name
                mock.write_text(MOCK)
                mock.chmod(0o755)
            result = subprocess.run(
                ["/bin/sh", "-eu", "-c", '. "$1"; "$2"', "hook-test", str(ROOT / hook), action],
                env={"PATH": str(commands), "HOME": str(home), "HOOK_LOG": str(log)},
                check=True, capture_output=True, text=True,
            )
            self.assertEqual(result.stderr, "")
            self.assertEqual(preferences.read_bytes(), before)
            self.assertEqual(list(home.iterdir()), [preferences])
            return result.stdout, log.read_text()

    def test_hooks_preserve_user_defaults_and_avoid_user_service_commands(self):
        for hook in HOOKS:
            for action in ("post_install", "post_upgrade", "pre_remove", "post_remove"):
                with self.subTest(hook=hook, action=action):
                    _, calls = self.invoke(hook, action)
                    self.assertNotIn("unexpected package hook command:", calls, calls)
                    self.assertIn("systemctl --global disable pathfm.socket" if action == "pre_remove"
                                  else "update-desktop-database -q", calls)

    def test_install_instructions_use_the_installed_launcher(self):
        for hook in HOOKS:
            with self.subTest(hook=hook):
                output, _ = self.invoke(hook, "post_install")
                self.assertIn("'pathfm'", output)
                self.assertNotIn("'path'", output)
                self.assertNotIn("is now the handler", output)


if __name__ == "__main__":
    unittest.main()
