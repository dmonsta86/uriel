from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from uriel.cli import main
from uriel.core import Refusal, initialize_project, load_project, save_project
from uriel.research_protocol import RULES, STAGES, next_step, render_prompt, write_prompt

from tests.paper_fixture import finalize_for_submission, make_paper_project


def snapshot(root: Path):
    return {path.relative_to(root).as_posix(): path.read_bytes() for path in root.rglob("*") if path.is_file()}


class ResearchProtocolTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="uriel-next-")
        self.base = Path(self.temporary.name)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def fresh(self) -> Path:
        root = self.base / "fresh"
        initialize_project(root, title="Nap study", question="Does a 20-minute nap shorten simple reaction time?")
        return root

    def test_fresh_project_starts_by_framing_the_question(self) -> None:
        root = self.fresh()
        before = snapshot(root)
        result = next_step(root)
        self.assertEqual(before, snapshot(root))
        self.assertEqual("frame", result["stage"]["id"])
        action = result["next_action"]
        self.assertEqual("frame", action["stage"])
        self.assertEqual("agent", action["owner"])
        self.assertTrue(action["command"].startswith("edit uriel.project.json at /"))
        self.assertEqual(2, len(action["alternatives"]))
        self.assertEqual([row[0] for row in STAGES], [row["id"] for row in result["progress"]])
        self.assertEqual("WAITING", result["progress"][-1]["status"])
        self.assertIn("PAPER_NOT_INITIALIZED", [row["code"] for row in result["checklist"]["manuscript"]])
        self.assertFalse(result["automated_checks_complete"])
        self.assertEqual(0, result["boundaries"]["writes"])

    def test_stages_advance_in_order(self) -> None:
        root = self.fresh()
        project = load_project(root)
        project["hypothesis"] = {
            "statement": "A twenty-minute nap shortens mean simple reaction time in healthy adults.",
            "falsifier": "Mean reaction time after the nap is not shorter than after quiet rest.",
            "operational_definitions": {"reaction time": "Milliseconds from stimulus onset to key press."},
            "success_criteria": ["Paired difference below zero with a 95% interval excluding zero."],
        }
        project["framing_review"] = {
            "neutral_restatement": "Compare reaction time after a short nap with reaction time after quiet rest.",
            "competing_frames": ["Any difference may reflect alertness from lying down rather than sleep."],
            "loaded_terms_reviewed": [],
            "scope_boundaries": ["Healthy adults aged 18 to 40 in a laboratory setting."],
        }
        project["claims"][0]["statement"] = "A short nap shortens simple reaction time in the sampled adults."
        save_project(root, project, event="test.frame", details={})
        result = next_step(root)
        self.assertEqual("prior_work", result["stage"]["id"])
        self.assertEqual("DONE", result["progress"][0]["status"])

    def test_attestations_are_human_owned(self) -> None:
        root = make_paper_project(self.base / "paper")
        project = load_project(root)
        project["disclosures"]["attestations"]["citations_checked_against_sources"] = False
        save_project(root, project, event="test.attest", details={})
        items = [item for items in next_step(root)["checklist"].values() for item in items]
        attestation = next(item for item in items if item["code"].startswith("ATTESTATION_"))
        self.assertEqual("human", attestation["owner"])
        prompt = render_prompt({"stage": {"index": 4, "title": "Evidence", "goal": "g"}, "next_action": attestation})
        self.assertIn("This step needs a human decision. Do not perform it yourself.", prompt)

    def test_complete_project_reaches_human_final_review(self) -> None:
        root = make_paper_project(self.base / "paper")
        before = next_step(root)
        # Manuscript edits changed the source set, so the reproduction must be rerun after the final edit.
        self.assertIn("FRESH_PASS_RECEIPT_MISSING", [row["code"] for row in before["checklist"]["evidence"]])
        finalize_for_submission(root)
        result = next_step(root)
        self.assertEqual("submission", result["stage"]["id"])
        self.assertEqual("HUMAN_FINAL_REVIEW", result["next_action"]["code"])
        self.assertEqual("human", result["next_action"]["owner"])
        self.assertTrue(result["automated_checks_complete"])
        self.assertEqual("HUMAN_REVIEW", result["progress"][-1]["status"])
        self.assertEqual("CURRENT", result["plan"]["state"])

    def test_stale_build_and_audit_reopen_submission_stage(self) -> None:
        root = make_paper_project(self.base / "paper")
        finalize_for_submission(root)
        (root / "paper" / "build" / "manuscript.md").write_text("tampered\n", encoding="utf-8")
        codes = [row["code"] for row in next_step(root)["checklist"]["submission"]]
        self.assertIn("PAPER_BUILD_STALE", codes)

    def test_plan_drift_is_a_design_item(self) -> None:
        root = make_paper_project(self.base / "paper")
        project = load_project(root)
        project["methods"]["analysis_plan"] += " Added after seeing the data."
        save_project(root, project, event="test.drift", details={})
        result = next_step(root)
        self.assertEqual("design", result["stage"]["id"])
        self.assertEqual("PLAN_CHANGED_SINCE_LOCK", result["next_action"]["code"])

    def test_model_and_framing_gaps_land_in_their_stages(self) -> None:
        root = make_paper_project(self.base / "paper")
        project = load_project(root)
        project["models"] = [{"id": "M1", "equation": "y = a * t^(-b)",
                              "symbols": {"y": {"meaning": "rate", "unit": "1"}, "a": {"meaning": "scale", "unit": "1"},
                                          "t": {"meaning": "time", "unit": "s"}, "b": {"meaning": "exponent", "unit": "1"}}}]
        project["alternative_explanations"] = []
        save_project(root, project, event="test.records", details={})
        checklist = next_step(root)["checklist"]
        design = [row["code"] for row in checklist["design"]]
        challenge = [row["code"] for row in checklist["challenge"]]
        self.assertIn("MODEL_DIMENSIONS_INCONSISTENT", design)
        self.assertIn("MODEL_ROLE_UNDECLARED", design)
        self.assertIn("CLAIM_WITHOUT_ALTERNATIVE", challenge)
        self.assertNotIn("MODEL_DIMENSIONS_INCONSISTENT", [row["code"] for row in checklist["manuscript"]])

    def test_prompt_file_is_create_only_and_self_contained(self) -> None:
        root = self.fresh()
        result = next_step(root)
        written = write_prompt(root, result, "NEXT_STEP.md")
        text = (root / "NEXT_STEP.md").read_text(encoding="utf-8")
        self.assertEqual("NEXT_STEP.md", written["prompt_path"])
        for rule in RULES:
            self.assertIn(rule, text)
        self.assertIn(result["next_action"]["code"], text)
        with self.assertRaises(Refusal) as caught:
            write_prompt(root, result, "NEXT_STEP.md")
        self.assertEqual("NEXT_PROMPT_EXISTS", caught.exception.code)
        with self.assertRaises(Refusal):
            write_prompt(root, result, "../outside.md")

    def test_cli_next_json_and_invalid_target(self) -> None:
        root = self.fresh()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(0, main(["--json", "next", "--root", str(root)]))
        payload = json.loads(output.getvalue())
        self.assertEqual("uriel.next_step.v1", payload["result"]["schema"])
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, main(["next", "--root", str(root), "--target", "someday"]))
        with self.assertRaises(Refusal):
            next_step(root, target="someday")


if __name__ == "__main__":
    unittest.main()
