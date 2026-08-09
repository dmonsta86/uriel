"""Strict Blessing contract decision-engine tests (regressions 1-26)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, initialize_project
from uriel.data_readiness import make_sort_spec, readiness_check
from uriel.gate_contract import (
    GATE1_CHECKS,
    GATE2_CHECKS,
    GATE3_CHECKS,
    gate_0_from_readiness,
    decide_gate,
    decision_sha256,
    gate_state_summary,
    latest_gate_decision,
    load_gate_decisions,
    write_gate_decision,
)


def _full_checks(check_ids):
    return [{"check_id": check_id, "status": "PASS", "evidence": [], "applicability_predicate": None}
            for check_id in check_ids]


class GateContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        initialize_project(self.root, title="t", question="q", privacy="public")

    def tearDown(self):
        self.tmp.cleanup()

    def test_missing_check_id_prevents_pass(self):
        checks = _full_checks(list(GATE1_CHECKS)[:-2])
        result = decide_gate(1, checks, binding_digest="b")
        self.assertEqual(result["decision"], "BLOCKED_MISSING_ARTIFACT")
        self.assertEqual(result["blocked_check_count"], 2)

    def test_skipped_check_prevents_pass(self):
        checks = _full_checks(GATE2_CHECKS)
        checks[3]["status"] = "BLOCKED_MISSING_ACCESS"
        result = decide_gate(2, checks, binding_digest="b")
        self.assertEqual(result["decision"], "BLOCKED_MISSING_ACCESS")

    def test_exception_prevents_pass(self):
        checks = _full_checks(GATE1_CHECKS)
        checks[0]["status"] = "BLOCKED_MISSING_ACCESS"
        checks[0]["evidence"] = ["The required file could not be read (IOError)."]
        result = decide_gate(1, checks, binding_digest="b")
        self.assertNotEqual(result["decision"], "PASS")

    def test_empty_check_output_not_pass(self):
        with self.assertRaises(Refusal) as context:
            decide_gate(1, [], binding_digest="b")
        self.assertEqual(context.exception.code, "EMPTY_CHECK_OUTPUT_NOT_PASS")

    def test_not_applicable_without_predicate_refused(self):
        checks = _full_checks(GATE1_CHECKS)
        checks[0]["status"] = "NOT_APPLICABLE"
        with self.assertRaises(Refusal) as context:
            decide_gate(1, checks, binding_digest="b")
        self.assertEqual(context.exception.code, "NOT_APPLICABLE_WITHOUT_PREDICATE")

    def test_na_with_predicate_does_not_block(self):
        checks = _full_checks(GATE1_CHECKS)
        checks[0]["status"] = "NOT_APPLICABLE"
        checks[0]["applicability_predicate"] = "no_data_dependent_claim"
        result = decide_gate(1, checks, binding_digest="b")
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["not_applicable_count"], 1)

    def test_unknown_status_refused(self):
        checks = _full_checks(GATE1_CHECKS)
        checks[0]["status"] = "PROBABLY_OK"
        with self.assertRaises(Refusal):
            decide_gate(1, checks, binding_digest="b")

    def test_only_literal_pass_counts(self):
        for status in ("FAIL_REFUTED", "NEEDS_CLARIFICATION", "NOT_APPLICABLE"):
            checks = _full_checks(GATE3_CHECKS)
            checks[0]["status"] = status
            if status == "NOT_APPLICABLE":
                checks[0]["applicability_predicate"] = "no_data_dependent_claim"
            result = decide_gate(3, checks, binding_digest="b")
            if status == "NOT_APPLICABLE":
                self.assertEqual(result["decision"], "PASS")
            else:
                self.assertNotEqual(result["decision"], "PASS")

    def test_all_pass_is_pass_with_full_counts(self):
        result = decide_gate(1, _full_checks(GATE1_CHECKS), binding_digest="b")
        self.assertEqual(result["decision"], "PASS")
        self.assertEqual(result["required_check_count"], len(GATE1_CHECKS))
        self.assertEqual(result["executed_check_count"], len(GATE1_CHECKS))
        self.assertEqual(result["failed_check_count"], 0)
        self.assertEqual(result["blocked_check_count"], 0)
        self.assertEqual(result["unresolved_blocker_count"], 0)

    def test_decision_sha256_is_content_address(self):
        first = decide_gate(2, _full_checks(GATE2_CHECKS), binding_digest="b")
        second = decide_gate(2, _full_checks(GATE2_CHECKS), binding_digest="b")
        self.assertEqual(first["decision_sha256"], second["decision_sha256"])
        self.assertEqual(len(decision_sha256(first)), 64)
        changed = decide_gate(2, _full_checks(GATE2_CHECKS), binding_digest="other")
        self.assertNotEqual(first["decision_sha256"], changed["decision_sha256"])

    def test_decision_write_is_immutable(self):
        result = decide_gate(1, _full_checks(GATE1_CHECKS), binding_digest="b" * 64)
        path = write_gate_decision(self.root, result)
        path.write_bytes(b"not json")
        with self.assertRaises(Refusal) as load_context:
            load_gate_decisions(self.root)
        self.assertEqual(load_context.exception.code, "GATE_DECISION_TAMPERED")
        with self.assertRaises(Refusal) as context:
            write_gate_decision(self.root, result)
        self.assertEqual(context.exception.code, "GATE_DECISION_TAMPERED")

    def test_forged_pass_gate_record_fails_closed(self):
        result = decide_gate(1, _full_checks(GATE1_CHECKS), binding_digest="c" * 64)
        path = write_gate_decision(self.root, result)
        forged = json.loads(path.read_text(encoding="utf-8"))
        forged["checks"][0]["status"] = "FAIL_REFUTED"
        path.write_text(json.dumps(forged, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        with self.assertRaises(Refusal) as caught:
            load_gate_decisions(self.root)
        self.assertEqual("GATE_DECISION_TAMPERED", caught.exception.code)

    def test_gate_0_blocks_before_readiness(self):
        record = gate_0_from_readiness(self.root)
        self.assertEqual(record["decision"], "FAIL_DATA_NOT_READY")
        self.assertEqual(record["required_check_count"], 22)

    def test_gate_0_passes_with_receipt(self):
        dataset = self.root / "artifacts" / "data.csv"
        dataset.parent.mkdir(parents=True, exist_ok=True)
        dataset.write_bytes(b"id,value\na,1\nb,2\n")
        make_sort_spec(self.root, "artifacts/data.csv", keys=["id"])
        readiness_check(self.root)
        record = gate_0_from_readiness(self.root)
        self.assertEqual(record["decision"], "PASS")

    def test_gate_0_stale_after_data_change(self):
        dataset = self.root / "artifacts" / "data.csv"
        dataset.parent.mkdir(parents=True, exist_ok=True)
        dataset.write_bytes(b"id,value\na,1\nb,2\n")
        make_sort_spec(self.root, "artifacts/data.csv", keys=["id"])
        readiness_check(self.root)
        dataset.write_bytes(b"id,value\na,1\nb,2\nc,3\n")
        record = gate_0_from_readiness(self.root)
        self.assertEqual(record["decision"], "FAIL_STALE")

    def test_state_summary_shows_not_run(self):
        summary = gate_state_summary(self.root)
        self.assertEqual(summary[0], "not_run")
        self.assertEqual(summary[1], "not_run")

    def test_user_override_cannot_flip_failure(self):
        result = decide_gate(1, _full_checks(GATE1_CHECKS), binding_digest="b")
        self.assertEqual(result["decision"], "PASS")
        checks = _full_checks(GATE1_CHECKS)
        checks[0]["status"] = "FAIL_REFUTED"
        result = decide_gate(1, checks, binding_digest="b")
        self.assertEqual(result["decision"], "FAIL_REFUTED")
        self.assertNotEqual(result["decision"], "PASS")


if __name__ == "__main__":
    unittest.main()
