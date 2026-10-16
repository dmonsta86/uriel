from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, initialize_project, load_project, run_workload, save_project
from uriel.plan_lock import lock_plan, plan_issues, plan_status


def complete_plan(root: Path) -> None:
    project = load_project(root)
    project["hypothesis"]["statement"] = "A twenty-minute nap shortens mean simple reaction time in rested adults."
    project["hypothesis"]["falsifier"] = "Mean reaction time after the nap is not shorter than after quiet rest."
    project["methods"]["analysis_plan"] = "Paired t-test on mean reaction time, nap versus quiet rest, two-sided alpha .05."
    project["methods"]["preregistration"] = ""
    save_project(root, project, event="test.plan", details={})


class PlanLockTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(prefix="uriel-plan-")
        self.root = Path(self.temporary.name) / "project"
        initialize_project(self.root, title="Plan lock test", question="Does a nap shorten reaction time?")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_incomplete_plan_cannot_be_locked(self) -> None:
        with self.assertRaises(Refusal) as caught:
            lock_plan(self.root)
        self.assertEqual("PLAN_INCOMPLETE", caught.exception.code)
        self.assertEqual(3, len(caught.exception.repairs))

    def test_lock_is_idempotent_and_detects_drift(self) -> None:
        complete_plan(self.root)
        self.assertEqual("LOCKED", lock_plan(self.root)["status"])
        self.assertEqual("UNCHANGED", lock_plan(self.root)["status"])
        status = plan_status(self.root)
        self.assertEqual("CURRENT", status["state"])
        self.assertTrue(status["first_lock_preceded_passing_results"])
        project = load_project(self.root)
        project["methods"]["analysis_plan"] += " Also a Bayesian model."
        save_project(self.root, project, event="test.edit", details={})
        status = plan_status(self.root)
        self.assertEqual("CHANGED_SINCE_LOCK", status["state"])
        self.assertEqual(["/methods/analysis_plan"], status["changed_fields"])
        codes = [row["code"] for row in plan_issues(status, project)]
        self.assertIn("PLAN_CHANGED_SINCE_LOCK", codes)

    def test_relock_requires_reason_and_flags_post_results_revision(self) -> None:
        complete_plan(self.root)
        lock_plan(self.root)
        (self.root / "ok.py").write_text("print('ok')\n", encoding="utf-8")
        self.assertEqual("PASS", run_workload(self.root, [sys.executable, "ok.py"], timeout=60)["status"])
        project = load_project(self.root)
        project["methods"]["exclusions"] = ["Trials faster than 100 ms"]
        save_project(self.root, project, event="test.edit", details={})
        with self.assertRaises(Refusal) as caught:
            lock_plan(self.root, reason="short")
        self.assertEqual("PLAN_RELOCK_REASON_REQUIRED", caught.exception.code)
        result = lock_plan(self.root, reason="Anticipatory responses were not excluded in the original plan.")
        self.assertEqual("RELOCKED", result["status"])
        self.assertTrue(result["lock"]["passing_results_existed"])
        status = plan_status(self.root)
        self.assertEqual("CURRENT", status["state"])
        self.assertEqual(1, len(status["deviations"]))
        self.assertIn("PLAN_REVISED_AFTER_RESULTS", [row["code"] for row in plan_issues(status, project)])

    def test_preregistration_wording_needs_a_prior_lock_or_external_record(self) -> None:
        complete_plan(self.root)
        (self.root / "ok.py").write_text("print('ok')\n", encoding="utf-8")
        run_workload(self.root, [sys.executable, "ok.py"], timeout=60)
        lock_plan(self.root)
        project = load_project(self.root)
        status = plan_status(self.root)
        self.assertFalse(status["first_lock_preceded_passing_results"])
        claimed = plan_issues(status, project, "The study was preregistered before data collection.")
        self.assertIn("PREREGISTRATION_CLAIM_UNSUPPORTED", [row["code"] for row in claimed])
        negated = plan_issues(status, project, "This study was not preregistered.")
        self.assertNotIn("PREREGISTRATION_CLAIM_UNSUPPORTED", [row["code"] for row in negated])
        project["methods"]["preregistration"] = "Registry identifier ABC-123"
        external = plan_issues(status, project, "The study was preregistered.")
        self.assertNotIn("PREREGISTRATION_CLAIM_UNSUPPORTED", [row["code"] for row in external])

    def test_damaged_lock_record_is_reported_and_blocks_relock(self) -> None:
        complete_plan(self.root)
        record_path = self.root / lock_plan(self.root)["record_relative_path"]
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["reason"] = "rewritten later"
        record_path.write_text(json.dumps(record), encoding="utf-8")
        self.assertEqual("DAMAGED", plan_status(self.root)["state"])
        with self.assertRaises(Refusal) as caught:
            lock_plan(self.root, reason="any reason that is long enough")
        self.assertEqual("PLAN_LOCK_DAMAGED", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
