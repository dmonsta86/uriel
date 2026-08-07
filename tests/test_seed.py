"""Tests for Uriel Seed (``uriel seed``)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, initialize_project, paths_for, read_json
from uriel.seed import load_seed, seed_id_for, seed_project, validate_seed, write_seed_brief


class SeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def _project(self) -> Path:
        initialize_project(self.root, title="t", question="q", privacy="public")
        return self.root

    def test_seed_builds_validated_record(self):
        project = self._project()
        record = seed_project(project, "Does caffeine make people write faster?")
        self.assertEqual(record["schema"], "uriel.seed.v1")
        self.assertEqual(validate_seed(record), [])
        self.assertEqual(record["status"], "READY_FOR_SEED_REVIEW")
        self.assertEqual(record["original_question"], "Does caffeine make people write faster?")
        self.assertRegex(record["question_sha256"], r"^[0-9a-f]{64}$")

    def test_seed_preserves_question_exactly(self):
        project = self._project()
        question = "  something about   school grades and sleep??  "
        record = seed_project(project, question)
        self.assertEqual(record["original_question"], "something about   school grades and sleep??")

    def test_clarification_batch_is_bounded_to_three(self):
        project = self._project()
        record = seed_project(project, "Does X cause Y?")
        self.assertLessEqual(len(record["clarification_questions"]), 3)

    def test_three_project_shapes_and_minimal_design_present(self):
        project = self._project()
        record = seed_project(project, "Is running better than walking for mood?")
        shapes = {item["name"] for item in record["three_project_shapes"]}
        self.assertEqual(
            shapes,
            {"small_answerable_question", "best_practical_project", "larger_question"},
        )
        for key in (
            "hypothesis",
            "rival_hypothesis",
            "simple_test",
            "useful_control",
            "result_against",
        ):
            self.assertIn(key, record["minimal_design"])

    def test_next_actions_are_exact(self):
        project = self._project()
        record = seed_project(project, "Why do some plants grow faster at night?")
        self.assertEqual(len(record["next_three_actions"]), 3)
        self.assertIn("uriel audit --profile exploratory", record["next_three_actions"][-1])

    def test_written_record_round_trips(self):
        project = self._project()
        record = seed_project(project, "A rough idea about attention spans.")
        paths = paths_for(project)
        stored = paths.state / "seed" / (record["seed_id"] + ".json")
        self.assertTrue(stored.is_file())
        loaded = load_seed(stored)
        self.assertEqual(loaded["seed_id"], record["seed_id"])
        self.assertEqual(loaded["original_question"], record["original_question"])

    def test_seed_id_is_deterministic_per_question(self):
        self.assertEqual(
            seed_id_for("a" * 64),
            seed_id_for("a" * 64),
        )

    def test_empty_question_refused(self):
        project = self._project()
        with self.assertRaises(Refusal):
            seed_project(project, "   ")

    def test_brief_written_and_contains_next_actions(self):
        project = self._project()
        record = seed_project(project, "Does music help studying?")
        target = Path(self.tmp.name) / "seed-brief.md"
        result = write_seed_brief(project, target)
        self.assertEqual(result["seed_id"], record["seed_id"])
        text = target.read_text(encoding="utf-8")
        self.assertIn("Uriel Seed brief", text)
        self.assertIn("Original question (preserved exactly)", text)
        self.assertIn("not a Blessing", text)

    def test_brief_refuses_overwrite(self):
        project = self._project()
        seed_project(project, "Does music help studying?")
        target = Path(self.tmp.name) / "seed-brief.md"
        target.write_text("existing", encoding="utf-8")
        with self.assertRaises(Refusal):
            write_seed_brief(project, target)

    def test_brief_missing_without_seed(self):
        project = self._project()
        target = Path(self.tmp.name) / "seed-brief.md"
        with self.assertRaises(Refusal):
            write_seed_brief(project, target)


if __name__ == "__main__":
    unittest.main()
