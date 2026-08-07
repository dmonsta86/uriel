from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicContractTests(unittest.TestCase):
    def test_readme_explains_name_blessing_and_three_gates(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        required = (
            "# Uriel Forge",
            "## Current audited capability status",
            "## The Blessing of Uriel",
            "## The Three Gates",
            "Gate 1 — Novelty and Clarity",
            "Gate 2 — Evidence and Citation",
            "Gate 3 — Adversarial Integrity",
            "does **not** mean",
        )
        for phrase in required:
            self.assertIn(phrase, text, phrase)

    def test_readme_describes_lifecycle_flow(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for token in (
            "## The research path",
            "Rough question or existing project",
            "Gate 0",
            "Gate 1",
            "Gate 2",
            "Gate 3",
        ):
            self.assertIn(token, text, token)

    def test_readme_lens_is_advisory_and_cannot_bless(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("The Blessing of Uriel", text)
        self.assertIn("Use Uriel with or without AI", text)
        self.assertIn("Strict Blessing issuance is **experimental and should remain disabled**", text)

    def test_readme_packet_and_budget_sections(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("## Use Uriel with or without AI", text)
        self.assertIn("Compatible local model", text)
        self.assertIn("Maintainer note", text)

    def test_lifecycle_doc_covers_all_planned_surfaces(self) -> None:
        text = (ROOT / "docs" / "LIFECYCLE.md").read_text(encoding="utf-8")
        for token in (
            "Uriel Lens",
            "Uriel Seed",
            "Research Workbench",
            "Data Desk",
            "Paper Builder",
            "Submission Guide",
            "Publication authority",
            "Generation and checkpoint model",
            "AI and privacy boundary",
            "00_READ_ME_FIRST.md",
            "submission_authorized",
            "NEXT_PROMPT.txt",
        ):
            self.assertIn(token, text, token)

    def test_lifecycle_doc_preserves_blessing_boundary(self) -> None:
        text = (ROOT / "docs" / "LIFECYCLE.md").read_text(encoding="utf-8")
        self.assertIn("cannot issue a Blessing", text)
        self.assertIn("deterministic audit and Blessing boundary remain authoritative", text)
        self.assertNotIn("AI can grant", text)

    def test_kit_material_never_entered_public_tree(self) -> None:
        for relative in sorted((ROOT / "docs").glob("*.md")):
            text = relative.read_text(encoding="utf-8", errors="replace")
            for secret in (
                "RESEARCH_LIFECYCLE_UPGRADE_KIT",
                "LOCAL_AI_MASTER_IMPLEMENTATION_PROMPT",
                "C:" + "\\Users\\" + "Taller",
                "uriel-work-20260806",
            ):
                self.assertNotIn(secret, text, f"{relative.name}: {secret}")


if __name__ == "__main__":
    unittest.main()
