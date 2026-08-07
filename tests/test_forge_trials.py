"""Tests for Forge Trials synthetic benchmark suite."""
from __future__ import annotations

import unittest
from pathlib import Path

from uriel.forge_trials import SYNTHETIC_GOLD_STANDARD_CASES, run_forge_trials


class ForgeTrialsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repo_root = Path(__file__).resolve().parent.parent

    def test_synthetic_gold_standard_cases_count(self) -> None:
        self.assertGreaterEqual(len(SYNTHETIC_GOLD_STANDARD_CASES), 4)

    def test_run_forge_trials_returns_pass(self) -> None:
        res = run_forge_trials(self.repo_root)
        self.assertEqual(res["trial_result"]["status"], "PASS")
        self.assertEqual(res["verdict"]["verdict"], "PUBLIC_BETA_READY")
        self.assertGreaterEqual(res["trial_result"]["average_precision"], 0.95)
        self.assertGreaterEqual(res["trial_result"]["average_recall"], 0.95)


if __name__ == "__main__":
    unittest.main()
