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
            self.assertEqual("uriel.data_import_plan.v2", verification["schema"])

    def test_data_import_and_verify_import_consume_saved_cli_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            source = base / "private-source" / "records.csv"
            source.parent.mkdir()
            source.write_text("id,value\na,1\nb,2\n", encoding="utf-8")
            initialized = self._run("init", str(root), "--question", "Can exact bytes be sealed?")
            self.assertEqual(0, initialized.returncode, initialized.stderr)

            planned = self._run(
                "--json", "data", "plan", "--root", str(root), "--source", str(source), "--label", "cli-records"
            )
            self.assertEqual(0, planned.returncode, planned.stderr)
            plan_path = root / "artifacts" / "cli-import-plan.json"
            plan_path.write_text(planned.stdout, encoding="utf-8")

            imported = self._run(
                "--json",
                "data",
                "import",
                "--root",
                str(root),
                "--source",
                str(source),
                "--plan",
                "artifacts/cli-import-plan.json",
            )
            self.assertEqual(0, imported.returncode, imported.stderr)
            self.assertNotIn(str(source), imported.stdout)
            result = json.loads(imported.stdout)["result"]
            self.assertEqual("SEALED", result["status"])
            self.assertEqual("COPIED", result["outcome"])
            self.assertFalse(result["gate_0_authority_granted"])

            verified = self._run(
                "--json",
                "data",
                "verify-import",
                "--root",
                str(root),
                "--receipt",
                result["receipt_relative_path"],
            )
            self.assertEqual(0, verified.returncode, verified.stderr)
            verification = json.loads(verified.stdout)["result"]
            self.assertTrue(verification["verified"])
            self.assertEqual(result["content_sha256"], verification["content_sha256"])
            self.assertFalse(verification["gate_0_authority_granted"])

    def test_generation_readiness_cli_uses_exact_active_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            source = base / "private" / "records.csv"
            source.parent.mkdir()
            source.write_text("id,value\na,1\nb,2\n", encoding="utf-8")
            initialized = self._run("init", str(root), "--question", "Can exact generation readiness pass?")
            self.assertEqual(0, initialized.returncode, initialized.stderr)

            planned = self._run(
                "--json", "data", "plan", "--root", str(root), "--source", str(source), "--label", "records"
            )
            self.assertEqual(0, planned.returncode, planned.stderr)
            plan_path = root / "artifacts" / "plan.json"
            plan_path.write_text(planned.stdout, encoding="utf-8")
            imported = self._run(
                "--json", "data", "import", "--root", str(root), "--source", str(source),
                "--plan", "artifacts/plan.json",
            )
            self.assertEqual(0, imported.returncode, imported.stderr)
            receipt_path = json.loads(imported.stdout)["result"]["receipt_relative_path"]
            inspected = self._run(
                "--json", "data", "inspect", "--root", str(root), "--receipt", receipt_path,
            )
            self.assertEqual(0, inspected.returncode, inspected.stderr)
            generation_id = json.loads(inspected.stdout)["result"]["generation_id"]

            initialized_spec = self._run(
                "--json", "readiness", "init-sort-spec", "--root", str(root),
                "--generation", generation_id, "--keys", "id",
            )
            self.assertEqual(0, initialized_spec.returncode, initialized_spec.stderr)
            spec = json.loads(initialized_spec.stdout)["result"]
            checked = self._run(
                "--json", "readiness", "check", "--root", str(root),
                "--generation", generation_id, "--sort-spec", spec["path"],
            )
            self.assertEqual(0, checked.returncode, checked.stderr)
            check = json.loads(checked.stdout)["result"]
            self.assertEqual("PASS", check["receipt"]["decision"])

            status = self._run(
                "--json", "readiness", "status", "--root", str(root),
                "--generation", generation_id,
            )
            self.assertEqual(0, status.returncode, status.stderr)
            active = json.loads(status.stdout)["result"]
            self.assertEqual("PASS", active["decision"])
            self.assertEqual(check["receipt_sha256"], active["receipt_sha256"])
            self.assertEqual(
                check["receipt_sha256"], active["active_selection"]["readiness_receipt_sha256"]
            )
            self.assertTrue((root / ".uriel" / "readiness" / "CURRENT.json").is_file())

            burst = self._run(
                "--json", "burst", "init", "--root", str(root),
                "--generation", generation_id, "--columns", "id", "value",
                "--row-index", "0", "--row-index", "1", "--row-limit", "2",
                "--readiness-sort-spec", spec["path"],
                "--readiness-receipt", check["path"],
                "--next-task", "Check only the selected rows for transcription consistency.",
                "--budget-bytes", "4096", "--redact",
            )
            self.assertEqual(0, burst.returncode, burst.stderr)
            packet = json.loads(burst.stdout)["result"]
            self.assertTrue(packet["verify"]["verified"])
            self.assertEqual(2, packet["selected_records"])
            surface = json.loads((Path(packet["packet"]) / "AI_SURFACE.json").read_text(encoding="utf-8"))
            self.assertTrue(surface["no_authority"])
            self.assertEqual("VALUES_REDACTED_METADATA_AND_HASHES_ONLY", surface["redaction_policy"])
            self.assertEqual(check["receipt_sha256"], surface["acceptance_receipt"])

            recheck = self._run(
                "--json", "audit", "recheck", "--root", str(root),
                "--profile", "submission", "--generation", generation_id,
                "--sort-spec", spec["path"], "--readiness-receipt", check["path"],
            )
            self.assertEqual(0, recheck.returncode, recheck.stderr)
            gate_zero = json.loads(recheck.stdout)["result"]["gates"]["gates"][0]
            self.assertEqual("PASS", gate_zero["decision"])

    def test_scholarly_local_mock_cli_is_disabled_then_offline_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / "project"
            initialized = self._run(
                "init",
                str(root),
                "--question",
                "Can the scholarly firewall stay offline?",
            )
            self.assertEqual(0, initialized.returncode, initialized.stderr)
            fixture = root / "sources" / "mock-response.bin"
            fixture.write_bytes(b'{"items":[{"id":"mock-1"}]}')

            refused = self._run(
                "--json",
                "data",
                "acquire-mock",
                "--root",
                str(root),
                "--fixture",
                "sources/mock-response.bin",
                "--term",
                "replication",
            )
            self.assertEqual(2, refused.returncode)
            refusal = json.loads(refused.stdout)
            self.assertEqual("SCHOLARLY_ACQUISITION_DISABLED", refusal["error"]["code"])
            self.assertFalse((root / ".uriel" / "acquisition").exists())

            missing = self._run(
                "--json",
                "data",
                "acquire-mock",
                "--root",
                str(root),
                "--fixture",
                "sources/private-missing-fixture.bin",
                "--term",
                "replication",
                "--acknowledge-local-mock",
            )
            self.assertEqual(2, missing.returncode)
            self.assertNotIn(str(root), missing.stdout)
            self.assertNotIn("private-missing-fixture.bin", missing.stdout)

            acquired = self._run(
                "--json",
                "data",
                "acquire-mock",
                "--root",
                str(root),
                "--fixture",
                "sources/mock-response.bin",
                "--term",
                "replication",
                "--term",
                "evidence integrity",
                "--acknowledge-local-mock",
            )
            self.assertEqual(0, acquired.returncode, acquired.stderr)
            self.assertNotIn(str(fixture), acquired.stdout)
            result = json.loads(acquired.stdout)["result"]
            self.assertEqual("PASS_LOCAL_MOCK", result["decision"])
            self.assertEqual(0, result["network_calls"])
            self.assertFalse(result["parsed"])
            self.assertFalse(result["authority_granted"])

            verified = self._run(
                "--json",
                "data",
                "verify-acquisition",
                "--root",
                str(root),
                "--receipt",
                result["receipt_relative_path"],
            )
            self.assertEqual(0, verified.returncode, verified.stderr)
            verification = json.loads(verified.stdout)["result"]
            self.assertTrue(verification["verified"])
            self.assertFalse(verification["transport_invoked"])
            self.assertFalse(verification["authority_granted"])

    def test_data_desk_cli_inspect_diff_reconcile_and_deep_verify(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            private = base / "private-source-name"
            private.mkdir()
            initialized = self._run("init", str(root), "--question", "Can installed-style CLI generations preserve conflicts?")
            self.assertEqual(0, initialized.returncode, initialized.stderr)

            def generation(name: str, content: str) -> dict:
                source = private / name
                source.write_text(content, encoding="utf-8")
                planned = self._run(
                    "--json", "data", "plan", "--root", str(root), "--source", str(source), "--label", name
                )
                self.assertEqual(0, planned.returncode, planned.stderr)
                plan_path = root / "artifacts" / (name + ".plan.json")
                plan_path.write_text(planned.stdout, encoding="utf-8")
                imported = self._run(
                    "--json", "data", "import", "--root", str(root), "--source", str(source),
                    "--plan", plan_path.relative_to(root).as_posix(),
                )
                self.assertEqual(0, imported.returncode, imported.stderr)
                receipt = json.loads(imported.stdout)["result"]["receipt_relative_path"]
                inspected = self._run(
                    "--json", "data", "inspect", "--root", str(root), "--receipt", receipt,
                    "--semantic-type", "id=record identifier",
                )
                self.assertEqual(0, inspected.returncode, inspected.stderr)
                self.assertNotIn(str(source), inspected.stdout)
                return json.loads(inspected.stdout)["result"]

            left = generation("left.csv", "id,value\n1,a\n2,b\n")
            right = generation("right.csv", "id,value\n1,a\n2,changed\n3,new\n")
            preview = self._run(
                "--json", "data", "diff", "--root", str(root),
                "--left-generation", left["generation_id"],
                "--right-generation", right["generation_id"],
                "--keys", "id",
            )
            self.assertEqual(0, preview.returncode, preview.stderr)
            preview_result = json.loads(preview.stdout)["result"]
            self.assertFalse(preview_result["writes_performed"])
            self.assertFalse(preview_result["delta_ledger_included"])
            self.assertNotIn("delta_ledger", preview_result)
            self.assertEqual(5, preview_result["delta_entry_count"])
            self.assertEqual(1, preview_result["summary"]["modified_count"])
            self.assertEqual(1, preview_result["summary"]["added_count"])

            detailed_preview = self._run(
                "--json", "data", "diff", "--root", str(root),
                "--left-generation", left["generation_id"],
                "--right-generation", right["generation_id"],
                "--keys", "id", "--include-delta-ledger",
            )
            self.assertEqual(0, detailed_preview.returncode, detailed_preview.stderr)
            detailed = json.loads(detailed_preview.stdout)["result"]
            self.assertTrue(detailed["delta_ledger_included"])
            self.assertEqual(5, len(detailed["delta_ledger"]))

            reconciled = self._run(
                "--json", "data", "reconcile", "--root", str(root),
                "--left-generation", left["generation_id"],
                "--right-generation", right["generation_id"],
                "--keys", "id",
            )
            self.assertEqual(0, reconciled.returncode, reconciled.stderr)
            result = json.loads(reconciled.stdout)["result"]
            self.assertEqual(5, result["record_count"])
            self.assertTrue(result["all_input_records_preserved"])
            self.assertFalse(result["gate_0_authority_granted"])

            verified = self._run(
                "--json", "data", "verify-generation", "--root", str(root),
                "--generation", result["generation_id"],
            )
            self.assertEqual(0, verified.returncode, verified.stderr)
            verification = json.loads(verified.stdout)["result"]
            self.assertTrue(verification["verified"])
            self.assertFalse(verification["scientific_findings_created"])


if __name__ == "__main__":
    unittest.main()
