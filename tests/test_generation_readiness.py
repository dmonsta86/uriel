"""Generation-bound Gate 0 readiness and exact-selector adversity tests."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from uriel.core import Refusal, canonical_json, initialize_project
from uriel.data_contracts import plan_data_import
from uriel.data_desk import inspect_data_artifact, project_verified_data_generation
from uriel.data_ingress import import_data_artifact
from uriel.data_readiness import (
    make_generation_sort_spec,
    readiness_check,
    readiness_status,
)
from uriel.gate_contract import gate_0_from_readiness
from uriel.independent_verify import compute_binding_digest
from uriel.strict_blessing import strict_gates_from_audit


class GenerationReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.root = self.base / "project"
        initialize_project(self.root, title="Generation readiness", question="Can exact generations fail closed?")
        self.serial = 0

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _generation(self, content: str) -> dict:
        self.serial += 1
        source = self.base / ("selected-{0}.csv".format(self.serial))
        source.write_text(content, encoding="utf-8")
        plan = plan_data_import(self.root, source, label="selected-{0}".format(self.serial))["plan"]
        plan_path = self.root / "artifacts" / ("plan-{0}.json".format(self.serial))
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        plan_path.write_text(canonical_json(plan), encoding="utf-8")
        imported = import_data_artifact(
            self.root,
            source,
            plan_path.relative_to(self.root).as_posix(),
        )
        return inspect_data_artifact(self.root, imported["receipt_relative_path"])

    def test_v2_sortspec_and_receipt_are_deterministic_and_gate_zero_passes(self) -> None:
        generation = self._generation("id,value\na,1\nb,2\n")
        first_spec = make_generation_sort_spec(
            self.root, generation["generation_id"], keys=["id"]
        )
        second_spec = make_generation_sort_spec(
            self.root, generation["generation_id"], keys=["id"]
        )
        self.assertEqual(first_spec["sort_spec_sha256"], second_spec["sort_spec_sha256"])
        self.assertEqual("uriel.sort_spec.v2", first_spec["sort_spec"]["schema"])

        first = readiness_check(
            self.root,
            first_spec["path"],
            generation=generation["generation_id"],
        )
        second = readiness_check(
            self.root,
            first_spec["path"],
            generation=generation["generation_id"],
        )
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])
        self.assertEqual("uriel.data_readiness.v2", first["receipt"]["schema"])
        self.assertEqual("PASS", first["receipt"]["decision"])
        self.assertEqual(22, len(first["checks"]))
        self.assertTrue(all(row["status"] == "PASS" for row in first["checks"]))

        status = readiness_status(
            self.root,
            generation=generation["generation_id"],
            sort_spec_path=first_spec["path"],
            receipt_path=first["path"],
        )
        self.assertEqual("PASS", status["decision"])
        gate = gate_0_from_readiness(
            self.root,
            generation_id=generation["generation_id"],
            sort_spec_path=first_spec["path"],
            receipt_path=first["path"],
        )
        self.assertEqual("PASS", gate["decision"])
        self.assertEqual(22, gate["passed_check_count"])
        strict = strict_gates_from_audit(self.root, generation_id=generation["generation_id"])
        binding = compute_binding_digest(self.root)["binding_digest"]
        self.assertEqual("PASS", strict[0]["decision"])
        self.assertTrue(all(row["binding_digest"] == binding for row in strict))

    def test_duplicate_policy_never_deletes_and_exact_is_explicit(self) -> None:
        generation = self._generation("id,value\na,1\na,2\n")
        blocked_spec = make_generation_sort_spec(
            self.root, generation["generation_id"], keys=["id"], duplicate_policy="block"
        )
        blocked = readiness_check(
            self.root, blocked_spec["path"], generation=generation["generation_id"]
        )
        self.assertEqual("FAIL", blocked["receipt"]["decision"])
        duplicate = next(row for row in blocked["checks"] if row["check_id"] == "duplicate_handling")
        self.assertEqual("FAIL", duplicate["status"])
        self.assertEqual(2, duplicate["evidence"]["records_preserved"])

        exact_spec = make_generation_sort_spec(
            self.root, generation["generation_id"], keys=["id"], duplicate_policy="exact"
        )
        exact = readiness_check(
            self.root, exact_spec["path"], generation=generation["generation_id"]
        )
        self.assertEqual("PASS", exact["receipt"]["decision"])
        self.assertEqual(2, next(
            row for row in exact["checks"] if row["check_id"] == "row_reconciliation"
        )["evidence"]["output_rows"])
        active = readiness_status(self.root, generation=generation["generation_id"])
        self.assertEqual("PASS", active["decision"])
        self.assertEqual(exact["receipt_sha256"], active["receipt_sha256"])
        historical = readiness_status(
            self.root,
            generation=generation["generation_id"],
            receipt_path=blocked["path"],
        )
        self.assertEqual("STALE", historical["decision"])

    def test_empty_generation_cannot_pass_gate_zero(self) -> None:
        generation = self._generation("id,value\n")
        spec = make_generation_sort_spec(self.root, generation["generation_id"], keys=["id"])
        receipt = readiness_check(self.root, spec["path"], generation=generation["generation_id"])
        self.assertEqual("FAIL", receipt["receipt"]["decision"])
        reconciliation = next(
            row for row in receipt["checks"] if row["check_id"] == "row_reconciliation"
        )
        self.assertEqual("FAIL", reconciliation["status"])
        self.assertFalse(reconciliation["evidence"]["empty_generation_allowed"])

    def test_changed_records_and_tampered_receipt_fail_closed(self) -> None:
        generation = self._generation("id,value\na,1\nb,2\n")
        spec = make_generation_sort_spec(self.root, generation["generation_id"], keys=["id"])
        receipt = readiness_check(self.root, spec["path"], generation=generation["generation_id"])
        receipt_path = Path(receipt["path"])
        original_receipt = receipt_path.read_bytes()
        value = json.loads(original_receipt.decode("utf-8"))
        value["decision"] = "FAIL"
        receipt_path.write_text(canonical_json(value), encoding="utf-8")
        tampered = readiness_status(
            self.root,
            generation=generation["generation_id"],
            receipt_path=receipt_path,
        )
        self.assertEqual("TAMPERED", tampered["decision"])
        receipt_path.write_bytes(original_receipt)

        records_path = self.root / generation["manifest"]["records_relative_path"]
        records_path.write_bytes(records_path.read_bytes().replace(b'"1"', b'"9"', 1))
        changed = readiness_status(
            self.root,
            generation=generation["generation_id"],
            receipt_path=receipt_path,
        )
        self.assertEqual("TAMPERED", changed["decision"])
        gate = gate_0_from_readiness(
            self.root,
            generation_id=generation["generation_id"],
            receipt_path=receipt_path,
        )
        self.assertEqual("FAIL_TAMPERED", gate["decision"])

    def test_wrong_generation_and_changed_analysis_plan_are_stale(self) -> None:
        first = self._generation("id,value\na,1\n")
        second = self._generation("id,value\nb,2\n")
        plan = self.root / "artifacts" / "analysis.md"
        plan.write_text("# frozen analysis\n", encoding="utf-8")
        spec = make_generation_sort_spec(
            self.root,
            first["generation_id"],
            keys=["id"],
            analysis_plan="artifacts/analysis.md",
        )
        receipt = readiness_check(self.root, spec["path"], generation=first["generation_id"])

        wrong = readiness_status(
            self.root,
            generation=second["generation_id"],
            receipt_path=receipt["path"],
        )
        self.assertEqual("STALE", wrong["decision"])
        plan.write_text("# changed analysis\n", encoding="utf-8")
        stale = readiness_status(
            self.root,
            generation=first["generation_id"],
            receipt_path=receipt["path"],
        )
        self.assertEqual("STALE", stale["decision"])

        replacement_spec = make_generation_sort_spec(
            self.root,
            first["generation_id"],
            keys=["id"],
            analysis_plan="artifacts/analysis.md",
        )
        replacement = readiness_check(
            self.root, replacement_spec["path"], generation=first["generation_id"]
        )
        self.assertEqual("PASS", replacement["receipt"]["decision"])
        # The stale historical receipt remains preserved, while only the new
        # active selection is live-recomputed and grants Gate 0 authority.
        binding = compute_binding_digest(self.root)
        self.assertEqual(64, len(binding["binding_digest"]))
        self.assertIn(receipt["receipt_sha256"], binding["data_readiness_receipt_sha256s"])
        self.assertIn(replacement["receipt_sha256"], binding["data_readiness_receipt_sha256s"])

    def test_policy_version_mutation_invalidates_receipt(self) -> None:
        generation = self._generation("id,value\na,1\n")
        spec = make_generation_sort_spec(self.root, generation["generation_id"], keys=["id"])
        receipt = readiness_check(self.root, spec["path"], generation=generation["generation_id"])
        with mock.patch(
            "uriel.generation_readiness.READINESS_POLICY_VERSION",
            "uriel.data_readiness_policy.mutated",
        ):
            status = readiness_status(
                self.root,
                generation=generation["generation_id"],
                receipt_path=receipt["path"],
            )
        self.assertNotEqual("PASS", status["decision"])

    def test_active_selection_changes_binding_without_changing_receipt_inventory(self) -> None:
        generation = self._generation("id,value\na,1\na,2\n")
        blocked_spec = make_generation_sort_spec(
            self.root, generation["generation_id"], keys=["id"], duplicate_policy="block"
        )
        blocked = readiness_check(
            self.root, blocked_spec["path"], generation=generation["generation_id"]
        )
        exact_spec = make_generation_sort_spec(
            self.root, generation["generation_id"], keys=["id"], duplicate_policy="exact"
        )
        exact = readiness_check(
            self.root, exact_spec["path"], generation=generation["generation_id"]
        )
        exact_binding = compute_binding_digest(self.root)
        self.assertIn(
            exact["selection"]["selection_sha256"],
            exact_binding["data_readiness_receipt_sha256s"],
        )

        readiness_check(
            self.root, blocked_spec["path"], generation=generation["generation_id"]
        )
        blocked_binding = compute_binding_digest(self.root)
        self.assertNotEqual(exact_binding["binding_digest"], blocked_binding["binding_digest"])
        self.assertEqual(
            "FAIL", readiness_status(self.root, generation=generation["generation_id"])["decision"]
        )

        readiness_check(self.root, exact_spec["path"], generation=generation["generation_id"])
        restored = compute_binding_digest(self.root)
        self.assertEqual(exact_binding["binding_digest"], restored["binding_digest"])
        self.assertNotEqual(blocked["receipt_sha256"], exact["receipt_sha256"])

    def test_tampered_active_selection_fails_closed(self) -> None:
        generation = self._generation("id,value\na,1\n")
        spec = make_generation_sort_spec(self.root, generation["generation_id"], keys=["id"])
        readiness_check(self.root, spec["path"], generation=generation["generation_id"])
        current = self.root / ".uriel" / "readiness" / "CURRENT.json"
        value = json.loads(current.read_text(encoding="utf-8"))
        value["readiness_binding_digest"] = "0" * 64
        current.write_text(canonical_json(value), encoding="utf-8")

        status = readiness_status(self.root, generation=generation["generation_id"])
        self.assertEqual("TAMPERED", status["decision"])
        gate = gate_0_from_readiness(self.root, generation_id=generation["generation_id"])
        self.assertEqual("FAIL_TAMPERED", gate["decision"])

    def test_missing_active_selection_cannot_be_bypassed_with_exact_receipt(self) -> None:
        generation = self._generation("id,value\na,1\n")
        spec = make_generation_sort_spec(self.root, generation["generation_id"], keys=["id"])
        receipt = readiness_check(self.root, spec["path"], generation=generation["generation_id"])
        (self.root / ".uriel" / "readiness" / "CURRENT.json").unlink()

        status = readiness_status(
            self.root,
            generation=generation["generation_id"],
            sort_spec_path=spec["path"],
            receipt_path=receipt["path"],
        )
        self.assertEqual("TAMPERED", status["decision"])
        self.assertEqual("READINESS_SELECTION_MISSING", status["error_code"])
        gate = gate_0_from_readiness(
            self.root,
            generation_id=generation["generation_id"],
            sort_spec_path=spec["path"],
            receipt_path=receipt["path"],
        )
        self.assertEqual("FAIL_TAMPERED", gate["decision"])

    def test_read_only_status_does_not_create_readiness_state(self) -> None:
        readiness_dir = self.root / ".uriel" / "readiness"
        self.assertFalse(readiness_dir.exists())
        status = readiness_status(self.root)
        self.assertFalse(status["exists"])
        self.assertFalse(readiness_dir.exists())

    def test_verified_projection_requires_exact_rows_columns_and_hard_budgets(self) -> None:
        generation = self._generation("id,value,private\na,1,secret-a\nb,2,secret-b\n")
        projection = project_verified_data_generation(
            self.root,
            generation["generation_id"],
            columns=["id", "value"],
            row_indices=[1],
            row_limit=1,
            byte_limit=4096,
        )
        self.assertEqual([1], projection["selected_row_indices"])
        self.assertEqual(1, projection["row_count"])
        self.assertEqual(2, len(projection["records"][0]["values"]))
        self.assertNotIn("secret-b", canonical_json(projection))
        self.assertTrue(projection["no_authority"])
        self.assertFalse(projection["gate_0_authority_granted"])

        redacted = project_verified_data_generation(
            self.root,
            generation["generation_id"],
            columns=["private"],
            row_indices=[0],
            row_limit=1,
            byte_limit=4096,
            redact=True,
        )
        self.assertNotIn("values", redacted["records"][0])
        self.assertTrue(redacted["records"][0]["values_redacted"])
        with self.assertRaises(Refusal) as missing_rows:
            project_verified_data_generation(
                self.root,
                generation["generation_id"],
                columns=["id"],
                row_indices=[],
                row_limit=1,
                byte_limit=4096,
            )
        self.assertEqual("DATA_SURFACE_ROWS_REQUIRED", missing_rows.exception.code)
        with self.assertRaises(Refusal) as too_small:
            project_verified_data_generation(
                self.root,
                generation["generation_id"],
                columns=["id"],
                row_indices=[0],
                row_limit=1,
                byte_limit=16,
            )
        self.assertEqual("DATA_SURFACE_BYTE_BUDGET", too_small.exception.code)


if __name__ == "__main__":
    unittest.main()
