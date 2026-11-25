from __future__ import annotations

import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from uriel import adversarial
from uriel import paper_builder as pb
from uriel.cli import main
from uriel.core import Refusal, _path_key, canonical_root, load_project, save_project, sha256_text
from uriel.framing import text_issues
from uriel.research_protocol import next_step

from tests.paper_fixture import append_section, make_paper_project


def codes(report):
    return {row["code"] for row in report["findings"] if row["severity"] == "blocker"}


def harden(root: Path) -> None:
    """Bring the fixture up to the adversarial standard, honestly."""
    project = load_project(root)
    project["alternative_explanations"][0]["claim_ids"] = ["C1"]
    project["alternative_explanations"].append({
        "id": "X2",
        "statement": "A stale manifest left over from an earlier run, not live comparison, produced the [b] result.",
        "claim_ids": ["C1"],
        "status": "open",
        "discriminating_observation": "Deleting the recorded manifest and rerunning would change the result if it were stale.",
    })
    project["assumptions"][0]["result"] = "Checked: both fixture lists contain only normalized POSIX paths."
    save_project(root, project, event="test.harden", details={})
    append_section(root, "00_abstract.md", "Within this fixture the result is consistent with the claim [claim:C1].\n")
    abstract = root / "paper" / "sections" / "00_abstract.md"
    abstract.write_text(abstract.read_text(encoding="utf-8").replace(
        "{{dp:p_main}} [claim:C1].", "{{dp:p_main}}, consistent with the claim within this fixture [claim:C1]."), encoding="utf-8")
    append_section(root, "02_methods.md",
                   "Because the unit test ran before the plan was locked, all analyses here are exploratory.\n")
    append_section(root, "05_limitations.md",
                   "A hard-coded answer could pass the positive fixture [alt:X1]. A stale manifest could also produce "
                   "the result [alt:X2]; rerunning without it would tell the two apart.\n")


class AdversarialModeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template_dir = tempfile.TemporaryDirectory(prefix="uriel-adv-template-")
        cls.template = make_paper_project(Path(cls.template_dir.name) / "project")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.template_dir.cleanup()

    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="uriel-adv-")
        self.root = Path(self.temporary.name) / "project"
        shutil.copytree(self.template, self.root)
        config = self.root / ".uriel" / "config.json"
        value = json.loads(config.read_text(encoding="utf-8"))
        value["allowed_root_sha256"] = sha256_text(_path_key(canonical_root(self.root)))
        config.write_text(json.dumps(value), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_mode_is_recorded_and_disabling_needs_a_reason(self) -> None:
        self.assertEqual("standard", adversarial.mode(load_project(self.root)))
        self.assertTrue(adversarial.set_mode(self.root, enabled=True)["changed"])
        self.assertEqual("adversarial", load_project(self.root)["assurance_mode"])
        with self.assertRaises(Refusal) as caught:
            adversarial.set_mode(self.root, enabled=False, reason="tired")
        self.assertEqual("ADVERSARIAL_DISABLE_REASON_REQUIRED", caught.exception.code)
        result = adversarial.set_mode(self.root, enabled=False, reason="Switching to a venue-specific checklist instead.")
        self.assertEqual("standard", result["mode"])
        ledger = (self.root / ".uriel" / "ledger.jsonl").read_text(encoding="utf-8")
        self.assertIn("Switching to a venue-specific checklist instead.", ledger)

    def test_submission_ready_fixture_is_not_adversarially_ready(self) -> None:
        self.assertEqual("PASS", pb.check_paper(self.root, profile="submission")["status"])
        report = pb.check_paper(self.root, profile="adversarial")
        self.assertEqual("FAIL", report["status"])
        for code in (
            "ADV_CLAIM_NEEDS_TWO_RIVALS",
            "ADV_ASSUMPTION_UNTESTED",
            "ADV_RIVAL_NOT_IN_LIMITATIONS",
            "ADV_CONFIRMATORY_FRAMING_NOT_EARNED",
            "ADV_CONCLUSION_SILENT_ON_OPEN_RIVAL",
        ):
            self.assertIn(code, codes(report), code)
        self.assertTrue(all(len(row["repairs"]) == 3 for row in report["findings"]))

    def test_the_standard_can_be_met(self) -> None:
        harden(self.root)
        report = pb.check_paper(self.root, profile="adversarial")
        self.assertEqual("PASS", report["status"], sorted(codes(report)))

    def test_submission_build_is_held_to_adversarial_standard_in_adversarial_mode(self) -> None:
        adversarial.set_mode(self.root, enabled=True)
        with self.assertRaises(Refusal) as caught:
            pb.build_paper(self.root, profile="submission")
        self.assertIn("adversarial", str(caught.exception))
        harden(self.root)
        built = pb.build_paper(self.root, profile="submission")
        self.assertEqual("adversarial", built["profile"])
        self.assertEqual("submission", built["requested_profile"])
        receipt = json.loads((self.root / pb.RECEIPT_OUTPUT).read_text(encoding="utf-8"))
        self.assertEqual("adversarial", receipt["assurance_mode"])

    def test_next_defaults_to_adversarial_target_in_adversarial_mode(self) -> None:
        self.assertEqual("submission", next_step(self.root)["target"])
        adversarial.set_mode(self.root, enabled=True)
        result = next_step(self.root)
        self.assertEqual("adversarial", result["target"])
        challenge = [row["code"] for row in result["checklist"]["challenge"]]
        self.assertIn("ADV_CLAIM_NEEDS_TWO_RIVALS", challenge)
        self.assertNotIn("ADV_CLAIM_NEEDS_TWO_RIVALS", [row["code"] for row in result["checklist"]["manuscript"]])

    def test_goalpost_checks(self) -> None:
        append_section(self.root, "03_results.md", "A one-tailed test was used for the main comparison.\n")
        self.assertIn("ADV_ONE_TAILED_NOT_PLANNED", codes(pb.check_paper(self.root, profile="adversarial")))

    def test_causal_claim_needs_a_confound_rival(self) -> None:
        project = load_project(self.root)
        project["claims"][0]["statement"] = "Exact membership verification causes reliable detection in the fixture."
        save_project(self.root, project, event="test.causal", details={})
        report = pb.check_paper(self.root, profile="adversarial")
        self.assertIn("ADV_CAUSAL_CLAIM_WITHOUT_CONFOUND_RIVAL", codes(report))

    def test_cli_mode_and_adversarial_lint(self) -> None:
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(["adversarial", "on", "--root", str(self.root)]))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, main(["adversarial", "off", "--root", str(self.root)]))
        (self.root / "draft.md").write_text("The effect was marginally significant (p = .07).\n", encoding="utf-8")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(0, main(["paper", "lint", "--root", str(self.root), "--file", "draft.md"]))
            self.assertEqual(2, main(["paper", "lint", "--root", str(self.root), "--file", "draft.md", "--adversarial"]))


class NullSpinTests(unittest.TestCase):
    def test_spin_phrases(self) -> None:
        for text in ("The effect was marginally significant (p = .07).",
                     "Scores showed a trend toward significance.",
                     "There was a non-significant trend toward an improvement."):
            self.assertIn("NULL_SPUN_AS_EFFECT", [row["code"] for row in text_issues(text, document_level=False)], text)
        self.assertEqual([], text_issues("The difference was significant.", document_level=False))


if __name__ == "__main__":
    unittest.main()
