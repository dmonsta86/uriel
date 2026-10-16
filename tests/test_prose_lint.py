from __future__ import annotations

import unittest

from uriel.prose_lint import REPAIRS, lint_text, word_count


def found(text: str, **kwargs):
    return {(row["code"], row["level"]) for row in lint_text(text, **kwargs)["issues"]}


class ProseLintTests(unittest.TestCase):
    def test_assistant_residue_is_always_grave(self) -> None:
        result = lint_text("Certainly! Here is the revised results section.\nI hope this helps.")
        codes = [row for row in result["issues"] if row["code"] == "ASSISTANT_RESIDUE"]
        self.assertEqual(3, len(codes))
        self.assertTrue(all(row["level"] == "grave" for row in codes))
        self.assertEqual(1, codes[0]["line"])

    def test_guide_comments_code_and_urls_are_ignored(self) -> None:
        text = (
            "<!-- TODO: delve into this. As an AI I cannot -->\n"
            "Plain sentence about results.\n"
            "`TODO in code`\n"
            "See https://example.org/TODO for the data.\n"
        )
        self.assertEqual([], lint_text(text)["issues"])

    def test_placeholders_are_submission_level(self) -> None:
        issues = found("We recruited N = XX participants [citation needed]. See Figure X. TODO.")
        self.assertIn(("PLACEHOLDER_TEXT", "submission"), issues)
        self.assertEqual(4, len([row for row in lint_text("N = XX [citation needed]. Figure X. TODO.")["issues"]]))

    def test_unsourced_attribution_requires_a_citation_in_the_same_sentence(self) -> None:
        self.assertIn(("UNSOURCED_ATTRIBUTION", "submission"), found("Studies have shown that naps help."))
        self.assertNotIn(("UNSOURCED_ATTRIBUTION", "submission"), found("Studies have shown that naps help [@lee2020]."))
        self.assertNotIn(("UNSOURCED_ATTRIBUTION", "submission"), found("Studies have shown that naps help (Lee, 2020)."))
        self.assertNotIn(("UNSOURCED_ATTRIBUTION", "submission"), found("Our data show a difference."))

    def test_proof_and_hype_language(self) -> None:
        issues = found("This proves the groundbreaking hypothesis.")
        self.assertIn(("PROOF_LANGUAGE", "submission"), issues)
        self.assertIn(("HYPE_LANGUAGE", "submission"), issues)
        self.assertNotIn(("PROOF_LANGUAGE", "submission"), found("We built a proof-of-concept prototype that proves feasible."))

    def test_proved_to_be_means_turned_out(self) -> None:
        # Regression: "Both these hypotheses proved to be consistent" (Einstein, Relativity) is not proof language.
        self.assertNotIn(("PROOF_LANGUAGE", "submission"), found("Both these hypotheses proved to be consistent."))
        self.assertNotIn(("PROOF_LANGUAGE", "submission"), found("The method proved useful in practice."))
        self.assertIn(("PROOF_LANGUAGE", "submission"), found("The redshift result proved the theory."))

    def test_stock_phrases_and_hedge_stacks(self) -> None:
        issues = found("We delve into the intricate interplay of sleep. The effect may potentially reflect fatigue.")
        self.assertIn(("STOCK_PHRASE", "submission"), issues)
        self.assertIn(("HEDGE_STACK", "style"), issues)

    def test_filler_density_blocks_only_when_dense(self) -> None:
        dense = " ".join(["Sleep plays a crucial role and fosters a holistic, comprehensive, nuanced landscape."] * 20)
        result = lint_text(dense)
        density = [row for row in result["issues"] if row["code"] == "FILLER_DENSITY"]
        self.assertEqual(1, len(density))
        self.assertEqual("submission", density[0]["level"])
        plain = " ".join(["Participants slept for twenty minutes before the second session began."] * 20)
        self.assertFalse([row for row in lint_text(plain)["issues"] if row["code"] == "FILLER_DENSITY"])

    def test_lists_in_prose_sections_and_repetitive_openers(self) -> None:
        text = "- one point\n- two points\n- three points\n\nThe a. The b. The c. The d.\n"
        self.assertIn(("LIST_IN_PROSE_SECTION", "style"), found(text, section_kind="discussion"))
        self.assertNotIn(("LIST_IN_PROSE_SECTION", "style"), found(text, section_kind="methods"))
        self.assertIn(("REPETITIVE_OPENER", "style"), found(text))

    def test_emoji_and_reasoning_patterns(self) -> None:
        self.assertIn(("EMOJI", "submission"), found("Results look great \U0001F680."))
        self.assertIn(("REASONING_PATTERN", "submission"), found("Everyone knows sleep matters, therefore it must be true."))

    def test_word_count_excludes_markup_and_comments(self) -> None:
        self.assertEqual(3, word_count("<!-- many words here -->Mean was {{dp:mean}} [@key] [claim:C1] high."))

    def test_every_code_has_three_repairs(self) -> None:
        for code, options in REPAIRS.items():
            self.assertEqual(3, len(options), code)


if __name__ == "__main__":
    unittest.main()
