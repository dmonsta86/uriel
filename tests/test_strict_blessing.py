"""Strict Blessing contract tests: binding recomputation, eligibility,
verifier independence, certificate issuance, tamper detection, CLI wiring,
and the §9.1 sorting proposal (STRICT_BLESSING_CONTRACT.md 14, 16, 17)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, initialize_project, run_workload
from uriel.data_readiness import make_sort_spec, propose_sort_spec_plan, readiness_check, readiness_status
from uriel.gate_failures import classify_failure, constructive_response, nonblocking_conditions_met
from uriel.gate_contract import load_gate_decisions
from uriel.independent_verify import compute_binding_digest, independent_verify, latest_verifier
from uriel.strict_blessing import (
    blessing_eligibility,
    issue_strict_blessing,
    run_strict_gates,
    strict_gates_from_audit,
    verify_strict_blessing,
)
from tests.helpers import make_passing_project


def _csv(path: Path, header: str, *rows: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((header + "\n" + "\n".join(rows) + "\n").encode("utf-8"))
    return path


def _refresh_fixture_receipt(root: Path) -> None:
    """Re-run the demo workload so a fresh PASS receipt binds the new records."""
    receipt = run_workload(
        root,
        [sys.executable, "-m", "unittest", "discover", "-s", "fixture_tests"],
        timeout=120,
        workload_id="unit-tests",
    )
    if receipt["status"] != "PASS":
        raise AssertionError("fixture workload failed: {0}".format(receipt.get("status")))


class StrictBlessingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        make_passing_project(self.root)
        self.dataset = _csv(
            self.root / "artifacts" / "data.csv",
            "id,group,value",
            "a,g1,10",
            "b,g1,20",
            "c,g2,30",
        )

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _make_ready(self) -> None:
        make_sort_spec(self.root, "artifacts/data.csv", keys=["id"])
        result = readiness_check(self.root)
        self.assertEqual(result["receipt"]["decision"], "PASS")
        _refresh_fixture_receipt(self.root)

    def _make_eligible(self) -> None:
        self._make_ready()
        run_strict_gates(self.root, persist=True)
        verifier = independent_verify(self.root)
        self.assertEqual(verifier["decision"], "PASS", verifier["errors"])

    def test_binding_digest_is_stable_and_content_addressed(self) -> None:
        self._make_ready()
        first = compute_binding_digest(self.root)
        second = compute_binding_digest(self.root)
        self.assertEqual(first["binding_digest"], second["binding_digest"])
        self.assertEqual(first["project_manifest_sha256"], second["project_manifest_sha256"])
        self.assertEqual(first["source_manifest_sha256"], second["source_manifest_sha256"])
        self.assertIn("data_readiness_receipt_sha256s", first)
        self.assertIn("execution_receipt_sha256s", first)

    def test_binding_digest_changes_when_receipt_set_changes(self) -> None:
        self._make_ready()
        first = compute_binding_digest(self.root)["binding_digest"]
        self.dataset.write_bytes(b"id,group,value\na,g1,10\nb,g1,20\nc,g2,99\n")
        make_sort_spec(self.root, "artifacts/data.csv", keys=["id"])
        readiness_check(self.root)
        second = compute_binding_digest(self.root)["binding_digest"]
        self.assertNotEqual(first, second)

    def test_no_receipt_blocks_gate_zero(self) -> None:
        decisions = strict_gates_from_audit(self.root)
        gate0 = next(decision for decision in decisions if decision["gate"] == 0)
        self.assertNotEqual(gate0["decision"], "PASS")

    def test_eligibility_blocked_without_verifier(self) -> None:
        self._make_ready()
        run_strict_gates(self.root, persist=True)
        eligibility = blessing_eligibility(self.root)
        self.assertFalse(eligibility["eligible"])
        self.assertTrue(any("verifier" in blocker.lower() for blocker in eligibility["blockers"]))

    def test_eligibility_blocked_without_gate_decisions(self) -> None:
        self._make_ready()
        independent_verify(self.root)
        eligibility = blessing_eligibility(self.root)
        self.assertFalse(eligibility["eligible"])
        self.assertTrue(any("Gate" in blocker for blocker in eligibility["blockers"]))

    def test_eligibility_never_creates_certificate(self) -> None:
        self._make_eligible()
        blessings = self.root / ".uriel" / "blessings"
        eligibility = blessing_eligibility(self.root)
        self.assertTrue(eligibility["eligible"], eligibility["blockers"])
        certificate_files = list(blessings.rglob("certificate.txt")) if blessings.exists() else []
        self.assertEqual(certificate_files, [])
        events = [json.loads(line) for line in (self.root / ".uriel" / "ledger.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertFalse(any(event.get("event_type") == "blessing.strict_issued" for event in events))

    def test_strict_issue_and_verify_full_pipeline(self) -> None:
        self._make_eligible()
        result = issue_strict_blessing(self.root)
        self.assertTrue(result["verified"], result["errors"])
        package = Path(result["package"])
        self.assertTrue((package / "blessing.json").is_file())
        self.assertTrue((package / "certificate.txt").is_file())
        self.assertTrue((package / "verification-qr.svg").is_file())
        self.assertTrue((package / "verification-instructions.md").is_file())
        self.assertTrue((package / "verifier-receipt.json").is_file())
        for gate in (0, 1, 2, 3):
            self.assertTrue((package / "gate-decision-{0}.json".format(gate)).is_file())
        checked = verify_strict_blessing(package, project_root=self.root)
        self.assertTrue(checked["verified"], checked["errors"])
        self.assertEqual(result["blessing_id"], checked["blessing_id"])

    def test_issue_refuses_when_verifier_fails(self) -> None:
        self._make_eligible()
        (self.root / "artifacts" / "data.csv").write_bytes(
            b"id,group,value\na,g1,10\nb,g1,20\nc,g2,30\nd,g2,40\n")
        with self.assertRaises(Refusal) as context:
            issue_strict_blessing(self.root)
        self.assertEqual(context.exception.code, "STRICT_BLESSING_NOT_EARNED")

    def test_issue_refuses_before_any_verifier(self) -> None:
        self._make_ready()
        with self.assertRaises(Refusal) as context:
            issue_strict_blessing(self.root)
        self.assertEqual(context.exception.code, "STRICT_BLESSING_NOT_EARNED")

    def test_verifier_rejects_wrong_expected_binding(self) -> None:
        self._make_eligible()
        result = independent_verify(self.root, expected_binding_digest="0" * 64)
        self.assertEqual(result["decision"], "FAIL")
        self.assertTrue(result["errors"])

    def test_verifier_rejects_tampered_source(self) -> None:
        self._make_eligible()
        (self.root / "analysis.py").write_text("tampered\n", encoding="utf-8")
        result = independent_verify(self.root)
        self.assertEqual(result["decision"], "FAIL")

    def test_package_tamper_is_detected(self) -> None:
        self._make_eligible()
        result = issue_strict_blessing(self.root)
        package = Path(result["package"])
        (package / "certificate.txt").write_text("tampered\n", encoding="utf-8")
        checked = verify_strict_blessing(package)
        self.assertFalse(checked["verified"])
        self.assertTrue(any("hash" in error.lower() for error in checked["errors"]))

    def test_package_membership_is_exact(self) -> None:
        self._make_eligible()
        result = issue_strict_blessing(self.root)
        package = Path(result["package"])
        (package / "extra.txt").write_text("x\n", encoding="utf-8")
        checked = verify_strict_blessing(package)
        self.assertFalse(checked["verified"])
        self.assertTrue(any("membership" in error.lower() for error in checked["errors"]))

    def test_ledger_event_is_written(self) -> None:
        self._make_eligible()
        result = issue_strict_blessing(self.root)
        self.assertTrue(result.get("ledger_event_sha256"))
        ledger_path = self.root / ".uriel" / "ledger.jsonl"
        self.assertTrue(ledger_path.is_file())
        events = [json.loads(line) for line in ledger_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertTrue(any(event.get("event_type") == "blessing.strict_issued" for event in events))

    def test_failure_taxonomy_mapping(self) -> None:
        mapping = {
            "EVIDENCE_HASH_MISMATCH": "FAIL_TAMPERED",
            "CONTRADICTION_UNRESOLVED": "FAIL_CONTRADICTORY",
            "REPRODUCIBILITY_COMMAND_MISSING": "FAIL_REPRODUCIBILITY",
        }
        for code, expected in mapping.items():
            meta = classify_failure(code)
            self.assertEqual(meta["status"], expected)
            self.assertIn(meta["group"], ("tampered", "contradictory", "incomplete"))
        unknown = classify_failure("NOT_A_REAL_CODE")
        self.assertEqual(unknown["status"], "FAIL_UNSUPPORTED")

    def test_contradictory_response_does_not_collapse(self) -> None:
        response = constructive_response("contradictory", claim="C1", evidence="E1")
        combined = json.dumps(response, sort_keys=True).lower()
        self.assertNotIn("merge both", combined)
        self.assertNotIn("vague average", combined.replace("must not collapse a contradiction into a vague average", ""))
        self.assertTrue(response.get("minimum_repair"))

    def test_refuted_response_narrows_but_does_not_erase(self) -> None:
        response = constructive_response("refuted", claim="C1", evidence="E1")
        self.assertTrue(response.get("minimum_repair"))
        self.assertIn("narrow", json.dumps(response, sort_keys=True).lower())

    def test_nonblocking_conditions_met(self) -> None:
        complete = [{
            "scope_excludes_affected": True,
            "recorded_in_payload": True,
            "deterministic_rule": True,
            "independent_verifier_confirms": True,
        }]
        self.assertTrue(nonblocking_conditions_met(complete))
        self.assertFalse(nonblocking_conditions_met([]))
        self.assertFalse(nonblocking_conditions_met(None))
        partial = [dict(complete[0], deterministic_rule=False)]
        self.assertFalse(nonblocking_conditions_met(partial))

    def test_propose_sort_generic_records(self) -> None:
        plan = propose_sort_spec_plan(self.root, "artifacts/data.csv")
        self.assertEqual(plan["gate_status"], "PROPOSAL")
        self.assertEqual(plan["detected_kind"], "generic_records")
        self.assertEqual(plan["proposed_primary_keys"], ["id"])
        self.assertTrue(plan["proposal_only"])
        self.assertIn("join_by_row_position", plan["refused_operations"])

    def test_propose_sort_time_series(self) -> None:
        _csv(self.root / "artifacts" / "series.csv",
             "entity_id,timestamp,value",
             "a,2026-08-01T10:00:00Z,1",
             "a,2026-08-01T11:00:00Z,2",
             "b,2026-08-01T10:00:00Z,3")
        plan = propose_sort_spec_plan(self.root, "artifacts/series.csv")
        self.assertEqual(plan["detected_kind"], "time_series")
        self.assertEqual(plan["proposed_primary_keys"], ["entity_id", "timestamp"])

    def test_propose_sort_blocked_when_identity_ambiguous(self) -> None:
        _csv(self.root / "artifacts" / "opaque.csv", "value,score", "10,1", "20,2")
        plan = propose_sort_spec_plan(self.root, "artifacts/opaque.csv")
        self.assertEqual(plan["gate_status"], "BLOCKED_AMBIGUOUS_IDENTITY")
        self.assertTrue(plan["identity_clarification_plan"])
        self.assertTrue(
            any("uriel readiness init-sort-spec" in step for step in plan["identity_clarification_plan"]),
            plan["identity_clarification_plan"])
        self.assertIn("Resolve identity first", plan["next_step"])


class StrictBlessingCliTests(unittest.TestCase):
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

    def _eligible_project(self) -> str:
        temporary = tempfile.mkdtemp()
        root = Path(temporary) / "project"
        make_passing_project(root)
        dataset = root / "artifacts" / "data.csv"
        dataset.write_bytes(b"id,group,value\na,g1,10\nb,g1,20\nc,g2,30\n")
        from uriel.core import paths_for
        from uriel.data_readiness import make_sort_spec, readiness_check
        from uriel.strict_blessing import run_strict_gates
        from uriel.independent_verify import independent_verify

        make_sort_spec(root, "artifacts/data.csv", keys=["id"])
        receipt = readiness_check(root)
        if receipt["receipt"]["decision"] != "PASS":
            raise AssertionError(receipt)
        _refresh_fixture_receipt(root)
        run_strict_gates(root, persist=True)
        verifier = independent_verify(root)
        if verifier["decision"] != "PASS":
            raise AssertionError(verifier["errors"])
        return str(root)

    def test_cli_propose_sort(self) -> None:
        temporary = tempfile.mkdtemp()
        root = Path(temporary) / "project"
        initialize_project(root, title="t", question="q", privacy="public")
        (root / "artifacts").mkdir(parents=True, exist_ok=True)
        (root / "artifacts" / "data.csv").write_bytes(
            b"id,group,value\na,g1,10\nb,g1,20\nc,g2,30\n")
        result = self._run("data", "propose-sort", "--root", str(root), "--dataset", "artifacts/data.csv")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Sort proposal", result.stdout)
        self.assertIn("generic_records", result.stdout)
        self.assertIn("nothing was sealed", result.stdout.lower())

    def test_cli_audit_explain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="rough", question="Why?", privacy="public")
            result = self._run("audit", "explain", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Strict failure map", result.stdout)

    def test_cli_audit_recheck_not_eligible_exit_two(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="rough", question="Why?", privacy="public")
            result = self._run("audit", "recheck", "--root", str(root))
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("eligible = False", result.stdout)

    def test_cli_eligibility_exit_code(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="rough", question="Why?", privacy="public")
            result = self._run("blessing", "eligibility", "--root", str(root))
            self.assertEqual(result.returncode, 2)
            self.assertIn("NOT ELIGIBLE", result.stdout)

    def test_bare_blessing_does_not_issue_legacy_certificate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="rough", question="Why?", privacy="public")
            result = self._run("blessing", "--root", str(root))
            self.assertEqual(result.returncode, 2)
            # Ensure no legacy blessing file was created
            blessing_dir = root / ".uriel" / "blessings"
            if blessing_dir.exists():
                self.assertEqual(len(list(blessing_dir.iterdir())), 0)

    def test_absence_of_negative_finding_cannot_produce_pass(self) -> None:
        from uriel.strict_blessing import _evaluate_check
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            eval_res = _evaluate_check(1, "unknown_unmapped_check_id", [], root, "dummy_digest")
            self.assertNotEqual(eval_res["status"], "PASS")
            self.assertEqual(eval_res["status"], "BLOCKED_EXTERNAL_VERIFICATION_REQUIRED")

    def test_cli_issue_verify_round_trip(self) -> None:
        root = self._eligible_project()
        issued = self._run("blessing", "issue", "--root", root)
        self.assertEqual(issued.returncode, 0, issued.stderr)
        self.assertIn("Strict Blessing issued: PASS", issued.stdout)
        package_line = next(line for line in issued.stdout.splitlines() if line.startswith("Blessing ID"))
        blessing_id = package_line.split(":", 1)[1].strip()
        package = str(Path(root) / ".uriel" / "blessings" / blessing_id)
        verified = self._run("blessing", "verify", package, "--root", root)
        self.assertEqual(verified.returncode, 0, verified.stderr)
        self.assertIn("PASS", verified.stdout)


if __name__ == "__main__":
    unittest.main()
