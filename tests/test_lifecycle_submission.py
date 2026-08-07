from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal
from uriel.packet import preflight_packet, verify_packet
from uriel.submission import (
    archive_submission,
    build_response,
    import_decision,
    submission_status,
    submit_guide,
    submit_init,
    submit_next_prompt,
    submit_plan,
    submit_verify,
)

REVISION_TEXT = (
    "The reviewers recommend a major revision.\n"
    "Reviewer 1:\n"
    "1. The statistical power analysis needs stronger evidence.\n"
    "2. =HYPERLINK(\"http://example.invalid\",\"x\") please fix this reference.\n"
    "Reviewer 2:\n"
    "3. The conclusion overstates the causal claim.\n"
)


def _full_revision_flow(root: Path, fields: object = None) -> dict:
    submit_init(root)
    imported = import_decision(root, REVISION_TEXT, venue="Test Journal", manuscript_id="MS-42")
    planned = submit_plan(root)
    response = build_response(root, fields=fields)
    return {"imported": imported, "planned": planned, "response": response}


class SubmissionFlowTests(unittest.TestCase):
    def test_revision_flow_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            flow = _full_revision_flow(root)
            decision = flow["imported"]["decision"]
            self.assertEqual("major_revision", decision["decision_class"])
            self.assertEqual("revision_required", flow["imported"]["authority"]["state"])
            self.assertEqual("external_artifact", flow["imported"]["authority"]["authority_source"])
            plan = flow["planned"]["plan"]
            self.assertEqual("revision_response", plan["kind"])
            self.assertEqual(3, len(plan["items"]))
            self.assertEqual(3, len(plan["actions"]))
            self.assertEqual("requested evidence", plan["items"][0]["classification"])
            self.assertEqual("formatting/editorial", plan["items"][1]["classification"])
            self.assertEqual("interpretation concern", plan["items"][2]["classification"])
            packet = flow["response"]["packet"]
            self.assertEqual("revision_response", packet["packet_type"])
            self.assertEqual("ready_with_disclosed_limitations", flow["response"]["preflight"])
            packet_dir = root / flow["response"]["packet_dir"]
            for name in (
                "00_READ_ME_FIRST.md",
                "01_PROJECT_OR_DECISION_SUMMARY.md",
                "02_REQUIRED_ACTIONS.csv",
                "03_REVISION_OR_COMPLETION_PLAN.md",
                "04_CLAIM_EVIDENCE_MAP.csv",
                "05_RESPONSE_TO_REVIEWERS.md",
                "06_COVER_OR_RESPONSE_LETTER.md",
                "09_FILE_CHECKLIST.md",
                "10_LIMITATIONS_AND_UNKNOWNS.md",
                "11_NEXT_INSTRUCTION.md",
                "MANIFEST.json",
                "SHA256SUMS.txt",
            ):
                self.assertTrue((packet_dir / name).is_file(), name)
            actions_csv = (packet_dir / "02_REQUIRED_ACTIONS.csv").read_text(encoding="utf-8")
            self.assertIn("'=HYPERLINK", actions_csv)
            verified = submit_verify(root)
            self.assertTrue(verified["verified"])
            self.assertEqual("pass", verified["packet"]["status"])
            self.assertEqual("ready_with_disclosed_limitations", verified["packet_preflight"])
            status = submission_status(root)
            self.assertEqual("revision_required", status["authority_state"])
            self.assertEqual(decision["decision_id"], status["decision"]["decision_id"])

    def test_import_refuses_before_init(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaises(Refusal) as raised:
                import_decision(Path(temporary), "We accept the paper.")
            self.assertEqual("SUBMISSION_NOT_INITIALIZED", raised.exception.code)

    def test_double_init_refuses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.assertTrue(submit_init(root)["initialized"])
            with self.assertRaises(Refusal) as raised:
                submit_init(root)
            self.assertEqual("SUBMISSION_EXISTS", raised.exception.code)

    def test_proposed_inference_does_not_change_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            submit_init(root)
            imported = import_decision(root, "We have received your manuscript and will be in touch.")
            self.assertEqual("proposed_unconfirmed", imported["decision"]["confirmation_state"])
            self.assertIsNone(imported["authority"])
            self.assertEqual("not_assessed", imported["index"]["authority_state"])
            self.assertIn("does not change publication authority", imported["note"])

    def test_user_confirmed_class_applies_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            submit_init(root)
            imported = import_decision(
                root,
                "We have received your manuscript and will be in touch.",
                decision_class="accepted",
                user_confirmed=True,
            )
            self.assertEqual("accepted", imported["authority"]["state"])
            self.assertEqual("user_confirmation", imported["authority"]["authority_source"])

    def test_conditional_acceptance_builds_conditional_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            submit_init(root)
            import_decision(root, "Your paper has been conditionally accepted.")
            response = build_response(root)
            self.assertEqual("conditional_acceptance", response["packet"]["packet_type"])

    def test_rejection_builds_resubmission_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            submit_init(root)
            import_decision(root, "We regret to reject your submission.")
            plan = submit_plan(root)["plan"]
            self.assertEqual("resubmission", plan["kind"])
            self.assertIn("venue_requirements_notice", plan)
            response = build_response(root)
            self.assertEqual("resubmission", response["packet"]["packet_type"])

    def test_acceptance_builds_production_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            submit_init(root)
            import_decision(root, "We are pleased to accept your manuscript.")
            plan = submit_plan(root)["plan"]
            self.assertEqual("production", plan["kind"])
            self.assertIn("obligations", plan)
            response = build_response(root)
            self.assertEqual("production", response["packet"]["packet_type"])

    def test_status_only_decision_has_no_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            submit_init(root)
            import_decision(root, "Your manuscript is under review.")
            plan = submit_plan(root)["plan"]
            self.assertEqual("status_only", plan["kind"])
            with self.assertRaises(Refusal) as raised:
                build_response(root)
            self.assertEqual("NO_PACKET_FOR_DECISION", raised.exception.code)

    def test_guide_renders_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            submit_init(root)
            fields = [
                {
                    "schema": "uriel.submission_field.v1",
                    "field_id": "title",
                    "label": "Title",
                    "required": True,
                    "maximum_characters": 100,
                    "proposed_answer": "A claim about evidence",
                    "supporting_facts": ["Backed by artifact sha256 prefix"],
                    "do_not_include": ["PII"],
                    "attachment": None,
                }
            ]
            fields_path = root / "fields.json"
            fields_path.write_text(json.dumps(fields), encoding="utf-8")
            result = submit_guide(root, fields_path="fields.json")
            self.assertEqual(1, result["field_count"])
            self.assertIn("Field 1 of 1", result["walkthrough"])
            self.assertTrue((root / result["output"]).is_file())
            bad = root / "bad_fields.json"
            bad.write_text(json.dumps([{"schema": "uriel.wrong.v1"}]), encoding="utf-8")
            with self.assertRaises(Refusal) as raised:
                submit_guide(root, fields_path="bad_fields.json")
            self.assertEqual("INVALID_FIELDS", raised.exception.code)

    def test_fields_add_form_files_to_packet(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            fields = [
                {
                    "schema": "uriel.submission_field.v1",
                    "field_id": "title",
                    "label": "Title",
                    "required": True,
                    "maximum_characters": 100,
                    "proposed_answer": "A claim about evidence",
                    "supporting_facts": ["Backed by artifact sha256 prefix"],
                    "do_not_include": ["PII"],
                    "attachment": None,
                }
            ]
            flow = _full_revision_flow(root, fields=fields)
            packet_dir = root / flow["response"]["packet_dir"]
            self.assertTrue((packet_dir / "07_SUBMISSION_FIELDS.json").is_file())
            self.assertTrue((packet_dir / "08_FORM_WALKTHROUGH.md").is_file())
            parsed = json.loads((packet_dir / "07_SUBMISSION_FIELDS.json").read_text(encoding="utf-8"))
            self.assertEqual("Title", parsed[0]["label"])
            walkthrough = (packet_dir / "08_FORM_WALKTHROUGH.md").read_text(encoding="utf-8")
            self.assertIn("Field 1 of 1", walkthrough)
            self.assertIn("Character count", walkthrough)

    def test_archive_is_deterministic_and_verifiable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            flow = _full_revision_flow(root)
            archived = archive_submission(root)
            zip_path = root / archived["archive"]
            self.assertTrue(zip_path.is_file())
            self.assertEqual(64, len(archived["receipt"]["zip_sha256"]))
            with self.assertRaises(Refusal) as raised:
                archive_submission(root)
            self.assertEqual("ARCHIVE_EXISTS", raised.exception.code)

    def test_next_prompt_contains_instruction(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            submit_init(root)
            prompt = submit_next_prompt(root, dry_run=True)
            self.assertIn("Next instruction", prompt["next_prompt"])
            self.assertIn("Current decision: none", prompt["next_prompt"])

    def test_cli_submit_end_to_end(self) -> None:
        env = os.environ.copy()
        source = str(Path(__file__).resolve().parents[1] / "src")
        env["PYTHONPATH"] = source + os.pathsep + env.get("PYTHONPATH", "")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def run(*args: str) -> subprocess.CompletedProcess[str]:
                return subprocess.run(
                    [sys.executable, "-m", "uriel", "--json", *args],
                    text=True,
                    capture_output=True,
                    env=env,
                    check=False,
                )

            result = run("submit", "init", "--root", str(root))
            self.assertEqual(0, result.returncode, result.stderr)
            envelope = json.loads(result.stdout)
            self.assertEqual("OK", envelope["status"])
            imported = run("submit", "import-decision", "--root", str(root), "--text", REVISION_TEXT)
            self.assertEqual(0, imported.returncode, imported.stderr)
            planned = run("submit", "plan", "--root", str(root))
            self.assertEqual(0, planned.returncode, planned.stderr)
            response = run("submit", "build-response", "--root", str(root))
            self.assertEqual(0, response.returncode, response.stderr)
            verified = run("submit", "verify", "--root", str(root))
            self.assertEqual(0, verified.returncode, verified.stderr)
            value = json.loads(verified.stdout)
            self.assertTrue(value["result"]["verified"])
            status = run("submit", "status", "--root", str(root))
            self.assertEqual(0, status.returncode, status.stderr)


if __name__ == "__main__":
    unittest.main()
