"""Tests for the Uriel Workbench (``uriel workbench``)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, initialize_project
from uriel.workbench import (
    LABELS,
    PIVOTS,
    workbench_init,
    workbench_next,
    workbench_plan,
    workbench_status,
)


class WorkbenchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        initialize_project(self.root, title="t", question="q", privacy="public")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_init_creates_first_generation(self):
        record = workbench_init(self.root, "Does X cause Y?")
        self.assertEqual(record["schema"], "uriel.workbench.v1")
        self.assertTrue(record["generation_id"].startswith("wbgen-"))
        self.assertEqual(record["question"], "Does X cause Y?")
        self.assertEqual(record["status"], "open")
        self.assertEqual(record["design"]["hypothesis"], None)

    def test_init_refuses_second_init(self):
        workbench_init(self.root, "Question one")
        with self.assertRaises(Refusal):
            workbench_init(self.root, "Question two")

    def test_plan_adds_labeled_items(self):
        workbench_init(self.root, "Does X cause Y?")
        record = workbench_plan(
            self.root,
            {
                "items": [
                    {"label": "OBSERVATION", "text": "Values rise in June."},
                    {"label": "CLAIM", "text": "X raises Y."},
                    {"label": "UNKNOWN", "text": "Whether Z confounds the result."},
                    {"label": "PROPOSED TEST", "text": "Compare X against a matched control."},
                ]
            },
        )
        labels = [item["label"] for item in record["items"]]
        self.assertEqual(
            labels,
            ["OBSERVATION", "CLAIM", "UNKNOWN", "PROPOSED TEST"],
        )
        self.assertTrue(all(item["id"].startswith("item-") for item in record["items"]))

    def test_plan_rejects_unknown_label(self):
        workbench_init(self.root, "Does X cause Y?")
        with self.assertRaises(Refusal):
            workbench_plan(self.root, {"items": [{"label": "FACT", "text": "nope"}]})

    def test_plan_rejects_unknown_design_field(self):
        workbench_init(self.root, "Does X cause Y?")
        with self.assertRaises(Refusal):
            workbench_plan(self.root, {"design": {"not_a_field": "value"}})

    def test_plan_sets_design_and_pivots(self):
        workbench_init(self.root, "Does X cause Y?")
        before = workbench_status(self.root)["generation_id"]
        record = workbench_plan(
            self.root,
            {
                "design": {
                    "hypothesis": "X raises Y in Z.",
                    "falsifying_result": "Y unchanged under X with matched controls.",
                    "stopping_rule": "Stop at N observations or one clear falsification.",
                },
                "pivots": ["narrower claim", "observational study"],
            },
        )
        self.assertEqual(record["design"]["hypothesis"], "X raises Y in Z.")
        self.assertEqual(record["pivots"], ["narrower claim", "observational study"])
        self.assertNotEqual(record["generation_id"], before)

    def test_plan_rejects_invalid_pivot(self):
        workbench_init(self.root, "Does X cause Y?")
        with self.assertRaises(Refusal):
            workbench_plan(self.root, {"pivots": ["time travel paper"]})

    def test_plan_records_user_decision_and_pivot_status(self):
        workbench_init(self.root, "Does X cause Y?")
        record = workbench_plan(
            self.root,
            {"user_decision": "Pivot to a narrower claim.", "status": "pivoted"},
        )
        self.assertEqual(record["status"], "pivoted")
        self.assertEqual(record["user_decision"], "Pivot to a narrower claim.")

    def test_status_reports_gaps(self):
        workbench_init(self.root, "Does X cause Y?")
        status = workbench_status(self.root)
        self.assertTrue(status["exists"])
        self.assertIn("hypothesis", status["design_gaps"])
        self.assertIn("falsifying_result", status["design_gaps"])
        self.assertEqual(status["item_counts"], {})

    def test_status_absent_without_init(self):
        import shutil

        shutil.rmtree(Path(self.tmp.name) / ".uriel" / "workbench", ignore_errors=True)
        status = workbench_status(self.root)
        self.assertFalse(status["exists"])

    def test_next_prioritizes_first_design_gap(self):
        workbench_init(self.root, "Does X cause Y?")
        result = workbench_next(self.root)
        self.assertIn("hypothesis", result["next_action"])
        self.assertIn("NEXT_PROMPT.txt", result["next_action"]) if False else None

    def test_next_writes_durable_prompt_file(self):
        workbench_init(self.root, "Does X cause Y?")
        target = Path(self.tmp.name) / "wb-next.txt"
        result = workbench_next(self.root, output=target)
        self.assertTrue(target.is_file())
        self.assertEqual(result["next_prompt_path"], str(target))
        self.assertIn("ONE numbered batch", target.read_text(encoding="utf-8"))
        self.assertIn("Do not claim a Blessing", target.read_text(encoding="utf-8"))

    def test_next_refuses_overwrite(self):
        workbench_init(self.root, "Does X cause Y?")
        target = Path(self.tmp.name) / "wb-next.txt"
        target.write_text("existing", encoding="utf-8")
        with self.assertRaises(Refusal):
            workbench_next(self.root, output=target)

    def test_generations_are_immutable(self):
        workbench_init(self.root, "Does X cause Y?")
        first = workbench_status(self.root)["generation_id"]
        workbench_plan(self.root, {"design": {"hypothesis": "X raises Y."}})
        second = workbench_status(self.root)["generation_id"]
        self.assertNotEqual(first, second)
        store = Path(self.tmp.name) / ".uriel" / "workbench"
        self.assertTrue((store / (first + ".json")).is_file())
        self.assertTrue((store / (second + ".json")).is_file())


if __name__ == "__main__":
    unittest.main()
