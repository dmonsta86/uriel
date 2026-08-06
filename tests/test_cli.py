from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class CliTests(unittest.TestCase):
    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        source = str(Path(__file__).resolve().parents[1] / "src")
        env["PYTHONPATH"] = source + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run(
            [sys.executable, "-m", "uriel", *args],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def test_version_and_json_status(self) -> None:
        version = self._run("--version")
        self.assertEqual(version.returncode, 0)
        self.assertIn("1.0.0", version.stdout)
        with tempfile.TemporaryDirectory() as temporary:
            initialized = self._run("--json", "init", temporary, "--title", "CLI", "--question", "Does it run?")
            self.assertEqual(initialized.returncode, 0, initialized.stderr)
            status = self._run("--json", "status", "--root", temporary)
            self.assertEqual(status.returncode, 0, status.stderr)
            value = json.loads(status.stdout)
            self.assertEqual(value["status"], "OK")

    def test_failed_audit_has_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            self.assertEqual(self._run("init", temporary, "--question", "Why?").returncode, 0)
            audit = self._run("audit", "--root", temporary, "--profile", "exploratory")
            self.assertEqual(audit.returncode, 2)
            self.assertIn("Repair record", audit.stdout)


if __name__ == "__main__":
    unittest.main()
