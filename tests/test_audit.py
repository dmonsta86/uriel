from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from uriel.audit import audit_project
from uriel.core import initialize_project, list_reminders, load_project, save_project
from uriel.schema import validate_project
from tests.helpers import make_passing_project


class AuditTests(unittest.TestCase):
    def test_rough_question_gets_constructive_three_gate_refusal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="A rough thought", question="Could plants remember weather?")
            report = audit_project(root, profile="exploratory")
            self.assertEqual(report.status, "FAIL")
            self.assertEqual([gate.gate for gate in report.gates], [1, 2, 3])
            findings = [finding for gate in report.gates for finding in gate.findings]
            self.assertTrue(findings)
            self.assertTrue(all(len(finding.repairs) == 3 for finding in findings))
            reminders = list_reminders(root)
            self.assertTrue(reminders)
            self.assertTrue((root / ".uriel" / "REMINDERS.md").is_file())

    def test_fallacy_language_is_flagged_without_insult(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="Reasoning", question="Is this argument valid?")
            project = load_project(root)
            project["hypothesis"]["statement"] = "Everyone agrees this is true, therefore it proves the mechanism."
            save_project(root, project, event="test.fallacy", details={})
            report = audit_project(root, profile="exploratory")
            codes = {finding.code for gate in report.gates for finding in gate.findings}
            self.assertTrue(any(code in {"POPULARITY_AS_EVIDENCE", "AUTHORITY_AS_PROOF"} or "FALLACY" in code for code in codes))
            messages = " ".join(finding.message.lower() for gate in report.gates for finding in gate.findings)
            self.assertNotIn("stupid", messages)
            self.assertNotIn("idiot", messages)

    def test_complete_bounded_fixture_passes_submission_profile(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            make_passing_project(root)
            validation = validate_project(str(root))
            self.assertTrue(validation["valid"], validation["errors"])
            report = audit_project(root, profile="submission")
            self.assertEqual(report.status, "PASS")
            self.assertTrue(report.blessable)
            self.assertEqual(sum(len(gate.findings) for gate in report.gates), 0)


if __name__ == "__main__":
    unittest.main()
