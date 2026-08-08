"""Tests for truthful Forge Trial fixture validation and scoring."""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from uriel.forge_trials import (
    run_forge_trials,
    score_adjudicated_findings,
    validate_forge_trial_fixture,
)


class ForgeTrialsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent

    def test_fixture_validation_recomputes_real_artifacts(self) -> None:
        validation = validate_forge_trial_fixture(self.repo_root)
        self.assertEqual(validation["status"], "PASS", validation["errors"])
        self.assertEqual(validation["seeded_issue_count"], 24)
        self.assertEqual(validation["scorecard_total_points"], 100)
        self.assertEqual(validation["detector_status"], "NOT_RUN")
        self.assertEqual(
            validation["recomputed_clean_summary"]["plant"]["accuracy_change_mean"],
            2.9333,
        )

    def test_no_observed_findings_means_no_detector_metrics(self) -> None:
        result = run_forge_trials(self.repo_root)
        evaluation = result["detector_evaluation"]
        self.assertEqual(evaluation["status"], "NOT_RUN")
        self.assertIsNone(evaluation["precision"])
        self.assertIsNone(evaluation["recall"])
        self.assertIsNone(evaluation["f1"])
        self.assertNotIn("verdict", result)

    def test_adjudicated_ids_are_scored_instead_of_seeded_counts(self) -> None:
        answer = json.loads(
            (
                self.repo_root
                / "benchmarks"
                / "forge_trials"
                / "synthetic-001"
                / "ANSWER_KEY"
                / "SEEDED_ISSUES.json"
            ).read_text(encoding="utf-8")
        )
        identifiers = [issue["id"] for issue in answer["issues"]]
        score = score_adjudicated_findings(
            self.repo_root,
            [*identifiers[:-1], "INVENTED"],
        )
        self.assertEqual(score["status"], "SCORED")
        self.assertEqual(score["true_positive_count"], 23)
        self.assertEqual(score["false_positive_ids"], ["INVENTED"])
        self.assertEqual(score["false_negative_ids"], [identifiers[-1]])
        self.assertAlmostEqual(score["precision"], 23 / 24)
        self.assertAlmostEqual(score["recall"], 23 / 24)

    def test_tampered_fixture_fails_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            temporary_root = Path(temporary)
            source = self.repo_root / "benchmarks"
            shutil.copytree(source, temporary_root / "benchmarks")
            scorecard = (
                temporary_root
                / "benchmarks"
                / "forge_trials"
                / "synthetic-001"
                / "ANSWER_KEY"
                / "SCORECARD.csv"
            )
            text = scorecard.read_text(encoding="utf-8")
            scorecard.write_text(text.replace("Seeded findings correctly identified,40", "Seeded findings correctly identified,39"), encoding="utf-8")
            validation = validate_forge_trial_fixture(temporary_root)
            self.assertEqual(validation["status"], "FAIL")
            self.assertTrue(any("scorecard" in error for error in validation["errors"]))


if __name__ == "__main__":
    unittest.main()
