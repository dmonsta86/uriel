from __future__ import annotations

import unittest
from pathlib import Path

from scripts.check_public_identity import (
    NAMED_RECOMMENDATION_PATTERN,
    PRIVATE_PUBLIC_PATTERNS,
    main as check_public_identity_main,
    recommendation_allowed,
)

ROOT = Path(__file__).resolve().parents[1]


class PublicIdentityTests(unittest.TestCase):
    def test_public_identity_check_passes(self) -> None:
        exit_code = check_public_identity_main()
        self.assertEqual(exit_code, 0, "Public identity check failed.")

    def test_named_recommendation_is_limited_to_core_readmes_and_one_policy_doc(self) -> None:
        self.assertTrue(NAMED_RECOMMENDATION_PATTERN.search("GPT-5.6 Sol with ultra mode"))
        self.assertTrue(recommendation_allowed("README.fr.md"))
        self.assertTrue(recommendation_allowed("docs/AI_USAGE_AND_PRIVACY.md"))
        self.assertFalse(recommendation_allowed("docs/FREE_AI_QUICKSTART.md"))

    def test_private_research_identity_patterns_are_fail_closed(self) -> None:
        examples = {
            "internal research id": "canonical " + "21" + "5",
            "private repository folder": "Scientific" + "-" + "Institutions",
            "private control packet": "URIEL_LUNA" + "_ROADMAP",
            "local user profile": "C:" + "\\Users\\" + "PrivateOperator\\project",
        }
        for label, example in examples.items():
            self.assertRegex(example, PRIVATE_PUBLIC_PATTERNS[label])
