#!/usr/bin/env python3
"""Exercise source-builder bootstrapping when Git is initially unavailable."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class SourceBootstrap(unittest.TestCase):
    def test_git_is_resolved_after_installing_tools(self):
        with tempfile.TemporaryDirectory() as temp:
            temp = Path(temp)
            tools = temp / "bin"
            tools.mkdir()
            result = temp / "arguments.json"
            commit = "a" * 40
            def script(name, content):
                p = tools / name
                p.write_text(content)
                p.chmod(0o755)
            for name in ("cargo", "rpmbuild", "tar", "gzip"):
                script(name, "#!/bin/sh\nexit 0\n")
            script("dnf", f"#!{sys.executable}\nfrom pathlib import Path\np=Path({str(tools / 'git')!r})\np.write_text('#!/bin/sh\\nprintf \\\"%s\\\\n\\\" {commit}\\n')\np.chmod(0o755)\n")
            script("python3", f"#!{sys.executable}\nimport json,sys\nfrom pathlib import Path\nPath({str(result)!r}).write_text(json.dumps(sys.argv[1:]))\n")
            subprocess.run([shutil.which("make"), "-f", str(ROOT / ".copr/Makefile"),
                            "srpm", f"outdir={temp / 'out'}"], cwd=ROOT,
                           env=dict(os.environ, PATH=str(tools)), check=True, capture_output=True)
            args = json.loads(result.read_text())
            self.assertEqual(args[args.index("--commit") + 1], commit)


if __name__ == "__main__":
    unittest.main()
