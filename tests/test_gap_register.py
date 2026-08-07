"""Gap register + repair packet tests (regressions 27-29 + completeness)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, initialize_project
from uriel.gap_register import (
    GAP_ACTIONS,
    build_gap,
    render_gap_register_csv,
    write_gap_register,
)
from uriel.repair_packet import (
    PACKET_FILES,
    build_repair_packet,
    verify_repair_packet,
)


def _gap(gate=2, code="FAIL_INCOMPLETE"):
    return build_gap(
        gate=gate,
        failure_code=code,
        severity="BLOCKING",
        observed_fact="Required evidence artifact is missing.",
        why_it_matters="The material claim depends on it.",
        affected_claims=["C1"],
        affected_artifacts=["artifacts/raw.csv"],
        what_remains_valid="The unaffected claims remain valid.",
        minimum_repair="Supply the missing artifact.",
        preferred_repair="Collect the primary source artifact.",
        completion_condition="The claim maps to an exact artifact with a matching hash.",
        verification_command="uriel audit --profile submission",
    )


class GapRegisterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        initialize_project(self.root, title="t", question="q", privacy="public")

    def tearDown(self):
        self.tmp.cleanup()

    def test_gap_has_all_contract_fields(self):
        row = _gap()
        for field in ("gap_id", "gate", "failure_code", "severity", "observed_fact",
                      "why_it_matters", "affected_claims", "affected_artifacts",
                      "what_remains_valid", "minimum_repair", "preferred_repair",
                      "alternative_repairs", "best_sorting_or_collection_method",
                      "evidence_needed", "user_action_needed", "uriel_action_available",
                      "external_action_needed", "completion_condition",
                      "verification_command", "status", "action"):
            self.assertIn(field, row)

    def test_unknown_action_refused(self):
        with self.assertRaises(Refusal) as context:
            build_gap(gate=1, failure_code="FAIL_INCOMPLETE", severity="BLOCKING",
                      observed_fact="x", why_it_matters="y", action="MAYBE_LATER")
        self.assertEqual(context.exception.code, "GAP_UNKNOWN_ACTION")

    def test_register_write_is_content_addressed(self):
        first = write_gap_register(self.root, [_gap()], label="a")
        second = write_gap_register(self.root, [_gap()], label="b")
        self.assertEqual(first["register_sha256"], second["register_sha256"])

    def test_empty_register_refused(self):
        with self.assertRaises(Refusal) as context:
            write_gap_register(self.root, [])
        self.assertEqual(context.exception.code, "GAP_REGISTER_EMPTY")

    def test_csv_export_includes_all_rows(self):
        text = render_gap_register_csv([_gap(), _gap(gate=3, code="FAIL_ADVERSARIAL")])
        self.assertEqual(text.count("\n") - 1, 2)
        self.assertIn("failure_code,severity", text.splitlines()[0])


class RepairPacketTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        initialize_project(self.root, title="t", question="q", privacy="public")

    def tearDown(self):
        self.tmp.cleanup()

    def _packet(self):
        return build_repair_packet(
            self.root,
            gate=2,
            gate_name="Evidence & Citation",
            decision="FAIL_INCOMPLETE",
            failure_summary="A required evidence artifact is missing.",
            gates_results={"status": "FAIL_INCOMPLETE", "counts": {"failed": 1}},
            blockers=[{"failure_code": "FAIL_INCOMPLETE", "severity": "BLOCKING",
                       "subject": "EVIDENCE_MISSING", "message": "Missing artifact.",
                       "evidence": ["artifacts/raw.csv"]}],
            gaps=[_gap()],
            sorting_plan="SortSpec with primary key id.",
            repair_plan="Collect the primary source artifact and rerun.",
            pivot_options=["Narrow the claim", "Pilot study"],
            evidence_requests=["Primary source artifact"],
            updated_project_spec="Exact version clarified.",
            completion_checklist=["Claim maps to exact artifact with matching hash"],
            recheck_instructions="Run `uriel audit --profile submission`.",
            next_prompt="Continue from the completion checklist.",
            what_was_inspected="The audit report and evidence map.",
            what_remains_valid="Unaffected claims.",
            what_uriel_filled="Sorting plan and evidence requests.",
            what_cannot_be_filled="The artifact itself.",
            prefer_repair="Collect the artifact.",
            alternatives=["Narrow scope"],
            rerun_gates=[2],
            new_generation_required=False,
        )

    def test_packet_contains_all_14_files(self):
        result = self._packet()
        directory = Path(result["path"])
        for name in PACKET_FILES:
            self.assertTrue((directory / name).is_file(), name)

    def test_packet_verifies(self):
        result = self._packet()
        verification = verify_repair_packet(result["path"])
        self.assertTrue(verification["verified"], verification["errors"])

    def test_packet_detects_tamper(self):
        result = self._packet()
        (Path(result["path"]) / "06_REPAIR_PLAN.md").write_text("changed", encoding="utf-8")
        verification = verify_repair_packet(result["path"])
        self.assertFalse(verification["verified"])
        self.assertTrue(any("Hash mismatch" in error for error in verification["errors"]))

    def test_placeholder_packet_refused(self):
        with self.assertRaises(Refusal) as context:
            build_repair_packet(
                self.root,
                gate=1,
                gate_name="Novelty & Clarity",
                decision="FAIL_INCOMPLETE",
                failure_summary="A required definition is missing.",
                gates_results={"status": "FAIL_INCOMPLETE"},
                blockers=[],
                gaps=[],
                sorting_plan="TODO sort",
                repair_plan="TODO repair",
                pivot_options=["TODO"],
                evidence_requests=[],
                updated_project_spec="TODO",
                completion_checklist=["TODO"],
                recheck_instructions="TODO",
                next_prompt="TODO continue",
            )
        self.assertEqual(context.exception.code, "PACKET_PLACEHOLDER")

    def test_packet_detects_placeholder_in_verify(self):
        result = self._packet()
        (Path(result["path"]) / "06_REPAIR_PLAN.md").write_text(
            "Repair plan with a TODO marker.", encoding="utf-8")
        verification = verify_repair_packet(result["path"])
        self.assertFalse(verification["verified"])
        self.assertTrue(any("Placeholder" in error for error in verification["errors"]))


if __name__ == "__main__":
    unittest.main()
