"""Tests for the zero-install Uriel Lens distribution (``uriel lens``)."""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal
from uriel.lens import asset_hashes, lens_names, lens_prompt, write_lens


class LensAssetTests(unittest.TestCase):
    def test_manifest_covers_all_shipped_assets(self):
        hashes = asset_hashes()
        self.assertEqual(len(hashes), 7)
        for name in (
            "COPY_THIS_ONE.txt",
            "URIEL_LENS_COMPACT.txt",
            "URIEL_LENS_FULL.md",
            "URIEL_SEED_PROMPT.txt",
            "uriel-lens-skill.md",
            "EXAMPLE_REVIEW.md",
            "LICENSE",
        ):
            self.assertIn(name, hashes)
            self.assertRegex(hashes[name], r"^[0-9a-f]{64}$")

    def test_every_named_asset_is_readable_and_verified(self):
        for name in lens_names():
            text = lens_prompt(name)
            self.assertIsInstance(text, str)
            self.assertTrue(text.strip())
            self.assertIn("Blessing", text)

    def test_compact_and_copy_this_one_are_identical(self):
        self.assertEqual(lens_prompt("compact"), lens_prompt("copy_this_one"))

    def test_compact_contains_advisory_boundary(self):
        text = lens_prompt("compact")
        self.assertIn("This is an advisory Uriel Lens review, not The Blessing of Uriel", text)
        self.assertIn("[OBSERVED]", text)
        self.assertIn("[UNKNOWN]", text)
        self.assertIn("[PROPOSED]", text)

    def test_full_prompt_contains_three_gates(self):
        text = lens_prompt("full")
        self.assertIn("GATE 1 — NOVELTY & CLARITY", text)
        self.assertIn("GATE 2 — EVIDENCE & CITATION", text)
        self.assertIn("GATE 3 — ADVERSARIAL INTEGRITY", text)

    def test_seed_prompt_has_required_final_statuses(self):
        text = lens_prompt("seed")
        for status in (
            "WORTH EXPLORING",
            "NEEDS ONE CLARIFICATION",
            "PROMISING BUT NEEDS EVIDENCE",
            "BETTER AS A DIFFERENT QUESTION",
            "NOT TESTABLE YET",
        ):
            self.assertIn(status, text)
        self.assertIn("Do not call this a Blessing", text)

    def test_skill_and_example_are_present(self):
        self.assertIn("uriel-lens", lens_prompt("skill"))
        self.assertIn("Uriel Lens Review", lens_prompt("example"))

    def test_unknown_asset_refused(self):
        with self.assertRaises(Refusal):
            lens_prompt("does-not-exist")

    def test_write_lens_creates_file_with_verified_content(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "lens.txt"
            result = write_lens(Path(tmp), "compact", target)
            self.assertEqual(result["asset"], "compact")
            self.assertTrue(target.is_file())
            self.assertEqual(target.read_text(encoding="utf-8"), lens_prompt("compact"))
            self.assertEqual(result["sha256"], asset_hashes()["URIEL_LENS_COMPACT.txt"])
            self.assertTrue(result["advisory_only"])

    def test_write_lens_refuses_overwrite(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "lens.txt"
            target.write_text("existing", encoding="utf-8")
            with self.assertRaises(Refusal):
                write_lens(Path(tmp), "compact", target)
            self.assertEqual(target.read_text(encoding="utf-8"), "existing")


if __name__ == "__main__":
    unittest.main()
