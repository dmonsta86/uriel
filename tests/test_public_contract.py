from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class PublicContractTests(unittest.TestCase):
    def test_readme_explains_record_workflow(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        for phrase in ("# Uriel", "uriel record init", "uriel trilium connect",
                       "uriel check-before-push", "uriel checklist pre-submission",
                       "uriel summary --for-successors"):
            self.assertIn(phrase, text)
        self.assertNotIn("![" , text)

    def test_advanced_features_demoted_and_bounded(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        opening, advanced = text.split("## Advanced and experimental tools")
        self.assertNotIn("Blessing", opening)
        self.assertIn("Blessing", advanced)
        self.assertIn("Gate 0", advanced)
        self.assertIn("not independent scientific validation", text)

    def test_readme_vendor_neutral(self) -> None:
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertNotIn("Maintainer note", text)

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
                "C:" + "\\Users\\" + "Example",
                "uriel-work-20260806",
            ):
                self.assertNotIn(secret, text, f"{relative.name}: {secret}")


if __name__ == "__main__":
    unittest.main()
