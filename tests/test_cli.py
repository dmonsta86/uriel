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

    def test_data_plan_and_record_verify_are_real_no_write_cli_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            source = base / "private-source" / "records.csv"
            source.parent.mkdir()
            source.write_text("id,value\na,1\n", encoding="utf-8")
            initialized = self._run("init", str(root), "--question", "Can the source be planned?")
            self.assertEqual(0, initialized.returncode, initialized.stderr)

            planned = self._run(
                "--json",
                "data",
                "plan",
                "--root",
                str(root),
                "--source",
                str(source),
            )
            self.assertEqual(0, planned.returncode, planned.stderr)
            self.assertNotIn(str(source), planned.stdout)
            result = json.loads(planned.stdout)["result"]
            self.assertFalse(result["writes_performed"])
            self.assertFalse((root / ".uriel" / "data").exists())

            record = root / "artifacts" / "import-plan.json"
            record.parent.mkdir(parents=True, exist_ok=True)
            record.write_text(json.dumps(result["plan"]), encoding="utf-8")
            verified = self._run(
                "--json",
                "data",
                "verify-record",
                "--root",
                str(root),
                "--record",
                "artifacts/import-plan.json",
            )
            self.assertEqual(0, verified.returncode, verified.stderr)
            verification = json.loads(verified.stdout)["result"]
            self.assertTrue(verification["valid"])
            self.assertEqual("uriel.data_import_plan.v1", verification["schema"])


if __name__ == "__main__":
    unittest.main()
