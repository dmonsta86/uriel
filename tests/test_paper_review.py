from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from uriel.cli import main
from uriel.core import Refusal, add_evidence, initialize_project, load_project, save_project
from uriel.paper_review import review_paper
from uriel.research_verbatim import ResearchVerbatimLedger


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp"


class PaperReviewTests(unittest.TestCase):
    def setUp(self) -> None:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(
            prefix="uriel-paper-review-", dir=str(TMP_ROOT)
        )
        self.project = Path(self.temporary.name) / "project"
        initialize_project(
            self.project,
            title="Paper review test",
            question="Does the candidate preserve the research record?",
            privacy="confidential",
        )
        (self.project / "baseline.md").write_text(
            "# Baseline\n\nThe original bounded claim.\n",
            encoding="utf-8",
        )
        (self.project / "candidate.md").write_text(
            "# Candidate\n\nThe original bounded claim.\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def enable_ledger(self) -> ResearchVerbatimLedger:
        ledger = ResearchVerbatimLedger(self.project, "researcher-a")
        ledger.set_mode("MANUAL", explicit_opt_in=True)
        return ledger

    def capture(self, ledger: ResearchVerbatimLedger, text: str, ref: str) -> str:
        saved = ledger.capture(
            text,
            source_message_ref=ref,
            capture_mode="MANUAL",
            confirmed=True,
            project_research_statement=True,
        )
        return str(saved["entry"]["entry_id"])

    def test_no_user_scope_is_read_only_and_literature_stays_incomplete(self) -> None:
        private = self.project / ".uriel" / "research-verbatim"
        before = (self.project / "candidate.md").read_bytes()
        report = review_paper(self.project, "candidate.md")
        self.assertEqual("NOT_REQUESTED", report["author_fidelity"]["status"])
        self.assertEqual(
            "LITERATURE_COVERAGE_INCOMPLETE",
            report["literature_coverage"]["status"],
        )
        self.assertEqual(0, report["boundaries"]["writes"])
        self.assertFalse(report["boundaries"]["automatic_rewrite"])
        self.assertFalse(private.exists())
        self.assertEqual(before, (self.project / "candidate.md").read_bytes())

    def test_all_consenting_entries_are_compared_automatically(self) -> None:
        ledger = self.enable_ledger()
        kept = "The occupational association is a distinct evidence lane."
        omitted = "The mechanism remains unresolved and must not be erased."
        first = self.capture(ledger, kept, "message-1")
        second = self.capture(ledger, omitted, "message-2")
        (self.project / "candidate.md").write_text(
            "# Candidate\n\n{0}\n".format(kept), encoding="utf-8"
        )
        report = review_paper(
            self.project,
            "candidate.md",
            baseline_path="baseline.md",
            user_reference="researcher-a",
            change_class="major_revision",
        )
        matrix = {
            row["entry_id"]: row for row in report["author_fidelity"]["entries"]
        }
        self.assertEqual({first, second}, set(matrix))
        self.assertEqual("PRESERVED_EXACT_TEXT", matrix[first]["status"])
        self.assertIn(
            matrix[second]["status"],
            {"POSSIBLE_OMISSION", "CHANGED_WORDING_REQUIRES_HUMAN_REVIEW"},
        )
        self.assertTrue(report["author_fidelity"]["author_review_required"])
        self.assertEqual(
            "EXPLICIT_USER_CONFIRMATION_REQUIRED",
            report["change_gate"]["status"],
        )

    def test_exact_entry_as_candidate_is_preserved(self) -> None:
        ledger = self.enable_ledger()
        text = "Exact capitalization, punctuation, and spacing remain."
        self.capture(ledger, text, "message-exact")
        (self.project / "candidate.md").write_text(text, encoding="utf-8")
        report = review_paper(
            self.project,
            "candidate.md",
            user_reference="researcher-a",
        )
        self.assertEqual("PRESERVED_EXACTLY", report["author_fidelity"]["status"])
        self.assertFalse(report["author_fidelity"]["author_review_required"])

    def test_lexical_overlap_never_becomes_an_exact_or_semantic_verdict(self) -> None:
        ledger = self.enable_ledger()
        text = "Repeated opportunity can make continued nonoccurrence improbable."
        self.capture(ledger, text, "message-paraphrase")
        (self.project / "candidate.md").write_text(
            "# Candidate\n\nRepeated opportunities may make nonoccurrence improbable.\n",
            encoding="utf-8",
        )
        report = review_paper(
            self.project,
            "candidate.md",
            user_reference="researcher-a",
        )
        row = report["author_fidelity"]["entries"][0]
        self.assertNotIn(row["status"], {"PRESERVED_EXACTLY", "PRESERVED_EXACT_TEXT"})
        self.assertTrue(report["author_fidelity"]["author_review_required"])
        self.assertFalse(report["author_fidelity"]["semantic_fidelity_decided"])

    def test_material_change_requires_confirmation_then_records_intent_only(self) -> None:
        unconfirmed = review_paper(
            self.project,
            "candidate.md",
            baseline_path="baseline.md",
            change_class="title",
        )
        self.assertTrue(unconfirmed["change_gate"]["confirmation_required"])
        self.assertEqual(
            "EXPLICIT_USER_CONFIRMATION_REQUIRED",
            unconfirmed["change_gate"]["status"],
        )
        confirmed = review_paper(
            self.project,
            "candidate.md",
            baseline_path="baseline.md",
            change_class="title",
            user_confirmed_change=True,
        )
        self.assertEqual(
            "USER_CONFIRMED_REVIEWED_CANDIDATE",
            confirmed["change_gate"]["status"],
        )
        self.assertFalse(
            confirmed["change_gate"]["canonical_mutation_authorized_by_uriel"]
        )
        self.assertFalse(confirmed["change_gate"]["canonical_mutation_performed"])

    def test_confirmation_without_exact_baseline_is_refused(self) -> None:
        with self.assertRaises(Refusal) as caught:
            review_paper(
                self.project,
                "candidate.md",
                change_class="major_revision",
                user_confirmed_change=True,
            )
        self.assertEqual("PAPER_REVIEW_BASELINE_REQUIRED", caught.exception.code)

    def test_declared_claim_and_literature_lanes_are_reported_separately(self) -> None:
        evidence = self.project / "sources" / "study.txt"
        evidence.write_text("A source-bound observational result.", encoding="utf-8")
        project = load_project(self.project)
        project["claims"][0]["statement"] = "The declared association exists."
        project["novelty_review"].update(
            {
                "status": "bounded_search_complete",
                "search_date": "2026-08-29",
                "databases": ["Example index"],
                "queries": ["occupational complexity dementia"],
                "nearest_prior_work": ["A 2023 direct association study"],
                "differentiators": ["A separately declared mechanism test"],
                "negative_searches": ["No claimed first discovery"],
                "scope_limitations": ["One declared index; not exhaustive"],
            }
        )
        save_project(
            self.project,
            project,
            event="test.project_updated",
            details={"purpose": "paper review fixture"},
        )
        add_evidence(
            self.project,
            "sources/study.txt",
            evidence_id="E1",
            claim_ids=["C1"],
            description="Closest published test",
            extraction="The study reports the declared association.",
            interpretation="External association evidence; mechanism remains separate.",
            limitations="Observational and not causal.",
        )
        report = review_paper(self.project, "candidate.md")
        self.assertEqual(
            "DECLARED_COVERAGE_PRESENT",
            report["claim_evidence_coverage"]["status"],
        )
        self.assertEqual("DECLARED_BOUNDED", report["literature_coverage"]["status"])
        self.assertFalse(
            report["literature_coverage"]["live_literature_discovery_performed"]
        )
        self.assertIn(
            "local INCONCLUSIVE does not erase declared external support",
            report["literature_coverage"]["evidence_lane_rule"],
        )

    def test_review_token_is_stable_for_unchanged_inputs(self) -> None:
        first = review_paper(
            self.project,
            "candidate.md",
            baseline_path="baseline.md",
            change_class="wording_only",
        )
        second = review_paper(
            self.project,
            "candidate.md",
            baseline_path="baseline.md",
            change_class="wording_only",
        )
        self.assertEqual(first["review_token"], second["review_token"])

    def test_cli_route_returns_hash_bound_advisory_report(self) -> None:
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = main(
                [
                    "--json",
                    "paper",
                    "review",
                    "--root",
                    str(self.project),
                    "--manuscript",
                    "candidate.md",
                    "--baseline",
                    "baseline.md",
                    "--change-class",
                    "title",
                ]
            )
        payload = json.loads(stream.getvalue())
        self.assertEqual(0, code)
        self.assertEqual("OK", payload["status"])
        self.assertEqual("uriel.paper_review.v1", payload["result"]["schema"])
        self.assertTrue(payload["result"]["review_token"].startswith("upr-"))

    def test_public_and_packaged_paper_review_schemas_are_valid_json_mirrors(self) -> None:
        public = ROOT / "schemas" / "uriel.paper_review.v1.schema.json"
        packaged = (
            ROOT / "src" / "uriel" / "schemas" / "uriel.paper_review.v1.schema.json"
        )
        self.assertEqual(public.read_bytes(), packaged.read_bytes())
        parsed = json.loads(public.read_text(encoding="utf-8"))
        self.assertEqual("Uriel Paper Review", parsed["title"])


if __name__ == "__main__":
    unittest.main()
