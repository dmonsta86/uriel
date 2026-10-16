from __future__ import annotations

import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path

from uriel import paper_builder as pb
from uriel.cli import main
from uriel.core import Refusal, initialize_project, load_project, save_project

from tests.paper_fixture import append_section, make_paper_project


def codes(report):
    return {row["code"] for row in report["findings"] if row["severity"] == "blocker"}


def all_codes(report):
    return {row["code"] for row in report["findings"]}


class PaperBuilderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.template_dir = tempfile.TemporaryDirectory(prefix="uriel-paper-template-")
        cls.template = make_paper_project(Path(cls.template_dir.name) / "project")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.template_dir.cleanup()

    def setUp(self) -> None:
        import shutil

        self.temporary = tempfile.TemporaryDirectory(prefix="uriel-paper-")
        self.root = Path(self.temporary.name) / "project"
        shutil.copytree(self.template, self.root)
        # Root binding is path-specific; rebind the copy as a fresh project location.
        config = self.root / ".uriel" / "config.json"
        value = json.loads(config.read_text(encoding="utf-8"))
        from uriel.core import _path_key, canonical_root, sha256_text

        value["allowed_root_sha256"] = sha256_text(_path_key(canonical_root(self.root)))
        config.write_text(json.dumps(value), encoding="utf-8")

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_complete_fixture_passes_and_builds_deterministically(self) -> None:
        draft = pb.check_paper(self.root, profile="draft")
        submission = pb.check_paper(self.root, profile="submission")
        self.assertEqual("PASS", draft["status"], [row["code"] for row in draft["findings"]])
        self.assertEqual("PASS", submission["status"], [row["code"] for row in submission["findings"]])
        self.assertEqual(6, submission["datapoints"]["verified"])
        self.assertEqual(["smith2020"], submission["references"]["cited"])
        self.assertEqual(0, submission["boundaries"]["writes"])
        built = pb.build_paper(self.root, profile="submission")
        self.assertEqual("BUILT", built["status"])
        manuscript = (self.root / pb.MANUSCRIPT_OUTPUT).read_text(encoding="utf-8")
        self.assertIn("t(38) = 2.20, p = .034", manuscript)
        self.assertIn("Across 40 comparisons (18 in arm A and 22 in arm B)", manuscript)
        self.assertIn("[1]", manuscript)
        self.assertIn("1. Smith, J., & Lee, K. (2020).", manuscript)
        for leftover in ("{{", "[claim:", "[@", "<!--", "Uriel section guide"):
            self.assertNotIn(leftover, manuscript)
        trace = (self.root / pb.TRACE_OUTPUT).read_text(encoding="utf-8")
        self.assertIn("| p_main | p = .034 | 0.0339 | artifacts/summary.csv", trace)
        self.assertIn("written_by_run", trace)
        self.assertTrue(pb.verify_build(self.root)["current"])
        first = (self.root / pb.MANUSCRIPT_OUTPUT).read_bytes()
        pb.build_paper(self.root, profile="submission")
        self.assertEqual(first, (self.root / pb.MANUSCRIPT_OUTPUT).read_bytes())

    def test_init_refuses_to_overwrite(self) -> None:
        with self.assertRaises(Refusal) as caught:
            pb.init_paper(self.root)
        self.assertEqual("PAPER_ALREADY_EXISTS", caught.exception.code)

    def test_init_scaffold_carries_project_context_and_fails_submission_until_written(self) -> None:
        temporary = tempfile.TemporaryDirectory(prefix="uriel-paper-init-")
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name) / "fresh"
        initialize_project(root, title="Fresh paper", question="Does a nap shorten reaction time in adults?")
        result = pb.init_paper(root, article_type="review")
        self.assertIn("paper/sections/03_synthesis.md", result["files_written"])
        intro = (root / "paper" / "sections" / "01_introduction.md").read_text(encoding="utf-8")
        self.assertIn("Recorded question: Does a nap shorten reaction time in adults?", intro)
        draft = pb.check_paper(root, profile="draft")
        self.assertEqual("PASS", draft["status"])
        self.assertIn("SECTION_EMPTY", all_codes(draft))
        self.assertIn("SECTION_EMPTY", codes(pb.check_paper(root, profile="submission")))
        with self.assertRaises(Refusal):
            pb.init_paper(root, article_type="poem")

    def test_typed_result_numbers_block_submission(self) -> None:
        append_section(self.root, "03_results.md", "The mean difference was 4.5 ms in 12 participants.\n")
        draft = pb.check_paper(self.root, profile="draft")
        self.assertEqual("PASS", draft["status"])
        self.assertIn("UNBOUND_NUMBER", all_codes(draft))
        submission = pb.check_paper(self.root, profile="submission")
        self.assertIn("UNBOUND_NUMBER", codes(submission))
        finding = next(row for row in submission["findings"] if row["code"] == "UNBOUND_NUMBER")
        self.assertEqual(["4.5", "12"], finding["detail"]["tokens"])
        self.assertIsNotNone(finding["location"]["line"])
        self.assertEqual(3, len(finding["repairs"]))

    def test_allowed_numbers_are_not_flagged(self) -> None:
        append_section(
            self.root, "03_results.md",
            "Table 2 and Figure 3 summarize the 2024 data; the 95% CI is shown. A {{lit:30}}-second window applied.\n",
        )
        self.assertNotIn("UNBOUND_NUMBER", all_codes(pb.check_paper(self.root, profile="submission")))

    def test_numbers_in_the_introduction_need_a_source(self) -> None:
        append_section(self.root, "01_introduction.md", "Roughly 70% of builds use such checks.\n")
        self.assertIn("UNSOURCED_NUMBER", codes(pb.check_paper(self.root, profile="submission")))
        append_section(self.root, "01_introduction.md", "Roughly 70% of builds use such checks [@smith2020].\n")
        report = pb.check_paper(self.root, profile="submission")
        lines = [row["location"]["line"] for row in report["findings"] if row["code"] == "UNSOURCED_NUMBER"]
        self.assertEqual(1, len(lines))

    def test_integrity_failures_block_even_drafts(self) -> None:
        append_section(
            self.root, "01_introduction.md",
            "As reported, \"exact checks are perfect in every build system ever made\" [@smith2020]. "
            "See [@nobody2021]. Builds matter [claim:C9]. {{dp:missing_one}} {{weird}}\n",
        )
        append_section(self.root, "03_results.md", "Certainly! Here is the revised results section. Also t(38) = 2.20, p = .34.\n")
        draft = pb.check_paper(self.root, profile="draft")
        self.assertEqual("FAIL", draft["status"])
        for code in (
            "QUOTE_NOT_IN_SOURCE",
            "CITATION_KEY_UNKNOWN",
            "CLAIM_ANCHOR_UNKNOWN",
            "DATAPOINT_MARKER_UNKNOWN",
            "MARKUP_INVALID",
            "ASSISTANT_RESIDUE",
            "STAT_DECISION_INCONSISTENT",
        ):
            self.assertIn(code, codes(draft), code)
        with self.assertRaises(Refusal) as caught:
            pb.build_paper(self.root, profile="draft")
        self.assertEqual("PAPER_CHECK_FAILED", caught.exception.code)

    def test_changed_data_blocks_until_refreshed(self) -> None:
        summary = self.root / "artifacts" / "summary.csv"
        summary.write_text(summary.read_text(encoding="utf-8").replace("n_b,22", "n_b,23"), encoding="utf-8")
        draft = pb.check_paper(self.root, profile="draft")
        self.assertIn("DATAPOINT_ARTIFACT_STALE", codes(draft))

    def test_causal_wording_needs_identification_and_overclaim_blocks_submission(self) -> None:
        project = load_project(self.root)
        project["methods"]["causal_identification"] = ""
        save_project(self.root, project, event="test.edit", details={})
        append_section(self.root, "03_results.md", "Training causes faster detection [claim:C1]. This proves the groundbreaking idea.\n")
        submission = pb.check_paper(self.root, profile="submission")
        for code in ("CAUSAL_LANGUAGE_WITHOUT_IDENTIFICATION", "PROOF_LANGUAGE", "HYPE_LANGUAGE"):
            self.assertIn(code, codes(submission))

    def test_reference_hygiene(self) -> None:
        path = self.root / "paper" / "references.json"
        refs = json.loads(path.read_text(encoding="utf-8"))
        refs["references"].append({
            "key": "ghost2031", "authors": ["Ghost, A."], "year": 2091, "title": "A future paper",
            "venue": "Nowhere", "doi": "10.0000/example", "verification": {"status": "unverified"},
        })
        refs["references"].append({"key": "smith2020", "authors": ["X"], "year": 2000, "title": "Dup", "venue": "V"})
        path.write_text(json.dumps(refs), encoding="utf-8")
        append_section(self.root, "04_discussion.md", "A later study disagreed [@ghost2031].\n")
        submission = pb.check_paper(self.root, profile="submission")
        for code in ("REFERENCE_YEAR_IMPLAUSIBLE", "REFERENCE_DOI_INVALID", "REFERENCE_UNVERIFIED", "REFERENCE_KEY_DUPLICATE"):
            self.assertIn(code, codes(submission), code)

    def test_matching_file_without_human_attestation_is_not_verified(self) -> None:
        # Regression: an assistant can write a plausible source file and cite it; a matching hash
        # alone must not turn the reference into a verified one.
        path = self.root / "paper" / "references.json"
        refs = json.loads(path.read_text(encoding="utf-8"))
        refs["references"][0]["verification"] = {"status": "held"}
        path.write_text(json.dumps(refs), encoding="utf-8")
        report = pb.check_paper(self.root, profile="submission")
        self.assertEqual("unverified", report["references"]["status"]["smith2020"])
        self.assertIn("REFERENCE_UNVERIFIED", codes(report))
        self.assertNotIn("QUOTE_NOT_IN_SOURCE", all_codes(report))  # the held copy still verifies quotes
        unverified = [row for row in report["findings"] if row["code"] == "REFERENCE_UNVERIFIED"]
        self.assertEqual(1, len(unverified))  # reported once per key, not once per citation

    def test_verify_build_confines_receipt_paths_and_survives_bad_receipts(self) -> None:
        pb.build_paper(self.root, profile="draft")
        receipt_path = self.root / pb.RECEIPT_OUTPUT
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["outputs"]["../../outside.txt"] = "0" * 64
        receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
        result = pb.verify_build(self.root)
        self.assertFalse(result["current"])
        self.assertIn("the build receipt does not list exactly the generated outputs", result["reasons"])
        receipt_path.write_text("{not json", encoding="utf-8")
        self.assertEqual(["the build receipt is not valid JSON"], pb.verify_build(self.root)["reasons"])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_linked_section_is_refused(self) -> None:
        outside = Path(self.temporary.name) / "outside.md"
        outside.write_text("Text from outside the project root.\n", encoding="utf-8")
        section = self.root / "paper" / "sections" / "05_limitations.md"
        section.unlink()
        try:
            os.symlink(str(outside), str(section))
        except (OSError, NotImplementedError):
            self.skipTest("symlink creation not permitted")
        with self.assertRaises(Refusal) as caught:
            pb.check_paper(self.root, profile="draft")
        self.assertEqual("LINK_TRAVERSAL_REFUSAL", caught.exception.code)
        with self.assertRaises(Refusal):
            pb.build_paper(self.root, profile="draft")

    def test_quote_with_ellipsis_and_curly_marks_verifies(self) -> None:
        append_section(
            self.root, "01_introduction.md",
            "They wrote that \u201cExact membership checks are a standard part \u2026 They compare recorded file sets\u201d [@smith2020].\n",
        )
        self.assertNotIn("QUOTE_NOT_IN_SOURCE", all_codes(pb.check_paper(self.root, profile="draft")))

    def test_straight_quotes_do_not_pair_across_separate_quotations(self) -> None:
        # Regression: the gap between two short straight-quoted words must not be read as a quotation.
        append_section(
            self.root, "01_introduction.md",
            'They used the word "set" and then a phrase about many other unrelated things here "and" [@smith2020].\n',
        )
        self.assertNotIn("QUOTE_NOT_IN_SOURCE", all_codes(pb.check_paper(self.root, profile="draft")))

    def test_held_source_change_is_detected(self) -> None:
        (self.root / "sources" / "smith2020.txt").write_text("Different words now.\n", encoding="utf-8")
        self.assertIn("REFERENCE_SOURCE_STALE", codes(pb.check_paper(self.root, profile="draft")))

    def test_unreported_major_claim_and_missing_statements(self) -> None:
        for name in ("00_abstract.md", "03_results.md", "04_discussion.md"):
            path = self.root / "paper" / "sections" / name
            path.write_text(path.read_text(encoding="utf-8").replace("[claim:C1]", ""), encoding="utf-8")
        path = self.root / "paper" / "sections" / "07_statements.md"
        path.write_text("Data availability: in the repository. Nothing else is declared here at all today.\n", encoding="utf-8")
        submission = pb.check_paper(self.root, profile="submission")
        self.assertIn("CLAIM_NOT_REPORTED", codes(submission))
        topics = {row["detail"].get("topic") for row in submission["findings"] if row["code"] == "STATEMENT_MISSING"}
        self.assertEqual({"code_availability", "funding", "conflicts", "ethics", "ai_use"}, topics)

    def test_verify_build_detects_edits_and_tampering(self) -> None:
        pb.build_paper(self.root, profile="submission")
        append_section(self.root, "06_conclusion.md", "An extra sentence about scope limits remains.\n")
        stale = pb.verify_build(self.root)
        self.assertFalse(stale["current"])
        self.assertIn("the sources now render a different manuscript", stale["reasons"])
        pb.build_paper(self.root, profile="submission")
        output = self.root / pb.MANUSCRIPT_OUTPUT
        output.write_text(output.read_text(encoding="utf-8") + "\nInjected.\n", encoding="utf-8")
        self.assertIn("paper/build/manuscript.md differs from the build receipt", pb.verify_build(self.root)["reasons"])

    def test_lint_file_reports_residue_and_statistics(self) -> None:
        (self.root / "draft.md").write_text(
            "Certainly! Studies have shown benefits. We found t(28) = 2.20, p = .36.\n", encoding="utf-8"
        )
        result = pb.lint_file(self.root, "draft.md")
        found = {row["code"] for row in result["findings"]}
        self.assertEqual("FAIL", result["status"])
        self.assertTrue({"ASSISTANT_RESIDUE", "UNSOURCED_ATTRIBUTION", "STAT_DECISION_INCONSISTENT"} <= found)
        self.assertTrue(all(len(row["repairs"]) == 3 for row in result["findings"]))

    def test_check_is_read_only(self) -> None:
        def snapshot():
            return {
                path.relative_to(self.root).as_posix(): path.read_bytes()
                for path in self.root.rglob("*") if path.is_file()
            }

        before = snapshot()
        pb.check_paper(self.root, profile="submission")
        pb.verify_build(self.root)
        self.assertEqual(before, snapshot())

    def test_cli_exit_codes_and_json(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(["--json", "paper", "check", "--root", str(self.root), "--profile", "submission"])
        self.assertEqual(0, status)
        self.assertEqual("PASS", json.loads(output.getvalue())["result"]["status"])
        append_section(self.root, "03_results.md", "The effect was 4.5 ms.\n")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(2, main(["paper", "check", "--root", str(self.root), "--profile", "submission"]))
            self.assertEqual(0, main(["paper", "check", "--root", str(self.root), "--profile", "draft"]))
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(2, main(["paper", "build", "--root", str(self.root), "--profile", "submission"]))
            self.assertEqual(0, main(["paper", "build", "--root", str(self.root), "--profile", "draft"]))
            self.assertEqual(0, main(["paper", "verify-build", "--root", str(self.root)]))

    def test_cli_dp_add_registers_extracted_value(self) -> None:
        (self.root / "artifacts" / "extra.json").write_text('{"model": {"r2": 0.4310}}', encoding="utf-8")
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main([
                "--json", "paper", "dp-add", "--root", str(self.root), "--id", "r2", "--artifact", "artifacts/extra.json",
                "--json-pointer", "/model/r2", "--kind", "proportion", "--format", ".2f", "--description", "Model R squared",
            ])
        self.assertEqual(0, status)
        saved = json.loads(output.getvalue())["result"]["datapoint"]
        self.assertEqual("0.4310", saved["source_token"])


if __name__ == "__main__":
    unittest.main()
