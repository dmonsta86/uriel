from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, canonical_json, initialize_project, sha256_text
from uriel.paper_preflight import MAX_FINDINGS, MAX_LINES, MAX_TEXT_BYTES, analyze_text, preflight_paper


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp"


class PaperPreflightTests(unittest.TestCase):
    def setUp(self) -> None:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(prefix="uriel-preflight-", dir=str(TMP_ROOT))
        self.project = Path(self.temporary.name) / "project"
        initialize_project(self.project, title="Preflight test", question="What does the evidence support?")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_clean_technical_prose_has_no_blanket_word_flag(self) -> None:
        text = (
            "# Results\n\n"
            "The significant association was estimated in the declared sample; the mechanism remains unresolved [1].\n\n"
            "Figure 1 shows the prespecified comparison.\n\n"
            "Figure 1: Estimates with uncertainty intervals.\n\n"
            "# References\n[1] A direct source with a stable locator.\n"
        )
        report = analyze_text(text)
        self.assertEqual("NO_DETERMINISTIC_LEADS", report["status"])
        self.assertEqual([], report["findings"])
        self.assertTrue(report["manual_review_required"])
        self.assertEqual("NOT_PERFORMED", report["boundaries"]["authorship_inference"])
        self.assertFalse(report["boundaries"]["publication_authority"])

    def test_process_placeholder_and_duplicate_paragraph_leads_are_located(self) -> None:
        paragraph = "The bounded result is reported with its source, uncertainty, and eligibility rule. " * 2
        text = (
            "# Draft\n"
            "assistant: Here is your paper.\n"
            "The citation is citeturn0search0 and sandbox:/mnt/data/paper.pdf.\n"
            "TODO: add the result table.\n"
            "This proves beyond doubt that the mechanism is universal.\n\n"
            + paragraph + "\n\n" + paragraph + "\n"
        )
        report = analyze_text(text)
        kinds = {row["check_id"] for row in report["findings"]}
        self.assertTrue({
            "CHAT_ROLE_RESIDUE", "TOOL_CITATION_RESIDUE", "SANDBOX_LINK_RESIDUE",
            "UNRESOLVED_PLACEHOLDER", "CERTAINTY_OR_HYPE_LEAD", "DUPLICATE_PARAGRAPH",
        }.issubset(kinds))
        self.assertEqual("REVIEW_REQUIRED", report["status"])
        self.assertEqual(2, next(row["line"] for row in report["findings"] if row["check_id"] == "CHAT_ROLE_RESIDUE"))
        self.assertTrue(all(len(row["excerpt"]) <= 160 for row in report["findings"]))

    def test_citation_and_object_checks_require_explicit_local_inventories(self) -> None:
        without_bibliography = analyze_text("The prior report [@unverified] does not establish mechanism.\n")
        self.assertNotIn("UNMATCHED_BIBLIOGRAPHY_KEY", {row["check_id"] for row in without_bibliography["findings"]})
        text = (
            "The comparison cites [@missing] and [3]. Figure 2 is referenced.\\ref{fig:missing}\n"
            "The incomplete citation is [@open and \\cite{broken.\n"
            "Figure 1: The only figure caption.\n"
            "\\label{fig:one}\n"
            "# References\n"
            "[1] The only numbered source.\n"
            "[@known]: The only keyed source.\n"
        )
        report = analyze_text(text)
        kinds = {row["check_id"] for row in report["findings"]}
        self.assertTrue({
            "UNMATCHED_BIBLIOGRAPHY_KEY", "UNMATCHED_NUMERIC_REFERENCE",
            "UNMATCHED_OBJECT_REFERENCE", "UNMATCHED_LATEX_REFERENCE", "MALFORMED_CITATION",
        }.issubset(kinds))
        self.assertFalse(report["boundaries"]["citation_support_decided"])

    def test_display_cap_reports_suppressed_findings(self) -> None:
        report = analyze_text("TODO: review this line.\n" * (MAX_FINDINGS + 7))
        self.assertEqual(MAX_FINDINGS, len(report["findings"]))
        self.assertEqual(7, report["summary"]["suppressed_finding_count"])
        self.assertTrue(report["summary"]["findings_truncated"])

    def test_whole_manuscript_above_old_128k_limit_is_accepted(self) -> None:
        text = "".join(
            "Observation {0} was recorded within the declared population and time window.\n".format(i)
            for i in range(3000)
        )
        self.assertGreater(len(text.encode("utf-8")), 128 * 1024)
        self.assertLess(len(text.encode("utf-8")), MAX_TEXT_BYTES)
        report = analyze_text(text)
        self.assertEqual("NO_DETERMINISTIC_LEADS", report["status"])
        self.assertEqual(3000, report["summary"]["line_count"])
        (self.project / "long.md").write_text(text, encoding="utf-8")
        wrapped = preflight_paper(self.project, "long.md")
        self.assertEqual(len((self.project / "long.md").read_bytes()), wrapped["manuscript"]["size_bytes"])

    def test_large_or_invalid_input_refuses_with_three_repairs(self) -> None:
        for text, code in (
            ("x" * (MAX_TEXT_BYTES + 1), "PREFLIGHT_TEXT_TOO_LARGE"),
            ("x\n" * (MAX_LINES + 1), "PREFLIGHT_LINE_LIMIT"),
            ("\ud800", "PREFLIGHT_UTF8_REQUIRED"),
        ):
            with self.subTest(code=code), self.assertRaises(Refusal) as caught:
                analyze_text(text)
            self.assertEqual(code, caught.exception.code)
            self.assertEqual(3, len(caught.exception.repairs))

    def test_project_wrapper_is_read_only_and_binds_exact_candidate(self) -> None:
        manuscript = self.project / "candidate.md"
        manuscript.write_text("# Findings\n\nThe result remains bounded.\n", encoding="utf-8")
        before = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        first = preflight_paper(self.project, "candidate.md")
        second = preflight_paper(self.project, "candidate.md")
        after = {p.relative_to(self.project).as_posix(): p.read_bytes() for p in self.project.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assertEqual(first, second)
        self.assertEqual("uriel.paper_preflight.v1", first["schema"])
        self.assertEqual("candidate.md", first["manuscript"]["path"])
        expected = dict(first)
        expected.pop("report_sha256")
        self.assertEqual(sha256_text(canonical_json(expected)), first["report_sha256"])

    def test_wrapper_rejects_escape_binary_and_oversize(self) -> None:
        (self.project / "binary.bin").write_bytes(b"\xff")
        (self.project / "large.md").write_bytes(b"x" * (MAX_TEXT_BYTES + 1))
        for path in ("../outside.md", "binary.bin", "large.md"):
            with self.subTest(path=path), self.assertRaises(Refusal):
                preflight_paper(self.project, path)


if __name__ == "__main__":
    unittest.main()
