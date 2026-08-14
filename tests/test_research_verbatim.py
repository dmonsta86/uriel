from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from typing import Optional

from uriel.cli import main
from uriel.core import (
    Refusal,
    canonical_json,
    initialize_project,
    project_status,
    sha256_text,
)
from uriel.research_verbatim import (
    NORMALIZATION_RULES,
    ResearchVerbatimLedger,
    capture_entry,
    consent_status,
    consider_offer,
    drift_review,
    remove_ledger,
    review_entries,
    verify_ledger,
)


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp"


class ResearchVerbatimLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(
            prefix="uriel-verbatim-", dir=str(TMP_ROOT)
        )
        self.project = Path(self.temporary.name) / "project"
        initialize_project(
            self.project,
            title="Verbatim test",
            question="What changes the result?",
            privacy="confidential",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def ledger(self, user: str = "researcher-a") -> ResearchVerbatimLedger:
        return ResearchVerbatimLedger(self.project, user)

    def enable(self, mode: str = "MANUAL", user: str = "researcher-a") -> None:
        self.ledger(user).set_mode(mode, explicit_opt_in=True)

    def capture(
        self,
        text: str = "My baseline prediction is a five percent increase.",
        *,
        user: str = "researcher-a",
        mode: str = "MANUAL",
        source_ref: str = "message-001",
        summary: str = "A bounded directional prediction.",
        qualifying: bool = False,
    ):
        return self.ledger(user).capture(
            text,
            source_message_ref=source_ref,
            capture_mode=mode,
            confirmed=True,
            project_research_statement=True,
            qualifying_research_statement=qualifying,
            summary=summary,
            captured_at_utc="2026-08-14T15:10:00Z",
        )

    def scope_directory(self, project: Optional[Path] = None) -> Path:
        root = (project or self.project) / ".uriel" / "research-verbatim"
        scopes = list(root.glob("user-*/project-*"))
        self.assertEqual(len(scopes), 1)
        return scopes[0]

    def test_default_off_is_lazy_and_normal_status_is_unchanged(self) -> None:
        before = project_status(self.project)
        status = self.ledger().status()
        after = project_status(self.project)
        self.assertEqual(status["mode"], "OFF")
        self.assertEqual(status["offer_state"], "UNSEEN")
        self.assertFalse(status["consent_store_exists"])
        self.assertFalse(status["ledger_store_exists"])
        self.assertFalse(
            (self.project / ".uriel" / "research-verbatim").exists()
        )
        self.assertEqual(before, after)

    def test_detail_alone_may_offer_but_never_captures(self) -> None:
        no_signal = self.ledger().consider_offer([])
        self.assertEqual(no_signal["decision"], "NO_OFFER")
        self.assertFalse(
            (self.project / ".uriel" / "research-verbatim").exists()
        )

        offered = self.ledger().consider_offer(["high-detail"])
        self.assertEqual(offered["decision"], "OFFER")
        self.assertFalse(offered["verbatim_entry_created"])
        self.assertFalse(offered["message_content_recorded"])
        scope = self.scope_directory()
        self.assertTrue((scope / "consent.json").is_file())
        self.assertFalse((scope / "ledger.json").exists())
        self.assertNotIn(
            "original project baseline",
            (scope / "consent.json").read_text(encoding="utf-8"),
        )

        repeated = self.ledger().consider_offer(["novel"])
        self.assertEqual(repeated["decision"], "SUPPRESSED")
        self.assertEqual(repeated["reason"], "OFFER_ALREADY_RESOLVED")

    def test_decline_is_persistent_and_not_nagged_after_restart(self) -> None:
        self.ledger().consider_offer(["long-lived"])
        declined = self.ledger().decline()
        self.assertEqual(declined["offer_state"], "DECLINED")
        restarted = ResearchVerbatimLedger(self.project, "researcher-a")
        repeated = restarted.consider_offer(["project-baseline"])
        self.assertEqual(repeated["decision"], "SUPPRESSED")
        self.assertEqual(repeated["offer_state"], "DECLINED")
        self.assertFalse((self.scope_directory() / "ledger.json").exists())

    def test_explicit_opt_in_required_and_modes_are_inspectable(self) -> None:
        with self.assertRaises(Refusal) as caught:
            self.ledger().set_mode("MANUAL", explicit_opt_in=False)
        self.assertEqual(caught.exception.code, "VERBATIM_EXPLICIT_OPT_IN_REQUIRED")
        self.assertEqual(self.ledger().status()["mode"], "OFF")

        selected = self.ledger().set_mode("MANUAL", explicit_opt_in=True)
        self.assertEqual(selected["mode"], "MANUAL")
        self.assertEqual(self.ledger().status()["mode"], "MANUAL")
        changed = self.ledger().set_mode("ASSISTED", explicit_opt_in=True)
        self.assertEqual(changed["mode"], "ASSISTED")
        changed = self.ledger().set_mode("PROJECT", explicit_opt_in=True)
        self.assertEqual(changed["mode"], "PROJECT")

    def test_manual_capture_preserves_exact_text_and_distinct_summary(self) -> None:
        self.enable()
        exact = "Prediction:\r\n  Δ will remain ≤ 0.05.\nNo trimming.  "
        result = self.capture(exact)
        entry = result["entry"]
        self.assertEqual(entry["exact_text"], exact)
        self.assertEqual(entry["normalization"], NORMALIZATION_RULES)
        self.assertEqual(entry["source"]["kind"], "USER_MESSAGE")
        self.assertEqual(entry["source"]["message_ref"], "message-001")
        self.assertEqual(entry["capture_mode"], "MANUAL")
        self.assertNotEqual(entry["summary"]["text"], exact)
        self.assertEqual(len(entry["exact_text_sha256"]), 64)
        self.assertEqual(len(entry["entry_record_sha256"]), 64)
        self.assertTrue(entry["entry_id"].startswith("rvl-"))
        self.assertNotEqual(
            entry["user_isolation_key"], entry["project_isolation_key"]
        )

        restarted = ResearchVerbatimLedger(self.project, "researcher-a")
        reviewed = restarted.review()
        self.assertEqual(reviewed["entries"][0]["exact_text"], exact)
        self.assertTrue(restarted.verify()["verified"])

    def test_summary_substitution_is_refused_without_entry(self) -> None:
        self.enable()
        text = "This exact wording must remain in the exact field."
        with self.assertRaises(Refusal) as caught:
            self.capture(text, summary=text)
        self.assertEqual(caught.exception.code, "VERBATIM_SUMMARY_SUBSTITUTION")
        self.assertEqual(self.ledger().status()["entry_count"], 0)

    def test_assisted_proposal_is_ephemeral_and_each_entry_is_confirmed(self) -> None:
        self.enable("ASSISTED")
        proposed = self.ledger().propose(
            "The mechanism depends on boundary condition X.",
            source_message_ref="message-assisted",
            label="mechanism",
        )
        self.assertFalse(proposed["persisted"])
        self.assertTrue(proposed["requires_entry_confirmation"])
        self.assertFalse((self.scope_directory() / "ledger.json").exists())

        with self.assertRaises(Refusal) as caught:
            self.ledger().capture(
                proposed["exact_text"],
                source_message_ref="message-assisted",
                capture_mode="ASSISTED",
                confirmed=False,
                project_research_statement=True,
            )
        self.assertEqual(caught.exception.code, "VERBATIM_ENTRY_CONFIRMATION_REQUIRED")
        saved = self.ledger().capture(
            proposed["exact_text"],
            source_message_ref="message-assisted",
            capture_mode="ASSISTED",
            confirmed=True,
            project_research_statement=True,
        )
        self.assertEqual(saved["status"], "CAPTURED")

    def test_project_mode_requires_qualifying_statement_not_each_confirmation(self) -> None:
        self.enable("PROJECT")
        with self.assertRaises(Refusal) as caught:
            self.ledger().capture(
                "Routine drafting text.",
                source_message_ref="message-routine",
                capture_mode="PROJECT",
                confirmed=False,
                project_research_statement=True,
                qualifying_research_statement=False,
            )
        self.assertEqual(
            caught.exception.code, "VERBATIM_PROJECT_QUALIFICATION_REQUIRED"
        )
        saved = self.ledger().capture(
            "Correction: mechanism M applies only below threshold T.",
            source_message_ref="message-correction",
            capture_mode="PROJECT",
            confirmed=False,
            project_research_statement=True,
            qualifying_research_statement=True,
        )
        self.assertEqual(saved["entry"]["capture_mode"], "PROJECT")

    def test_revoked_consent_blocks_future_capture_and_preserves_review(self) -> None:
        self.enable()
        saved = self.capture()
        disabled = self.ledger().disable()
        self.assertFalse(disabled["future_capture_enabled"])
        self.assertTrue(disabled["ledger_preserved"])
        with self.assertRaises(Refusal) as caught:
            self.capture(
                "A later statement must not be saved.",
                source_ref="message-002",
            )
        self.assertEqual(caught.exception.code, "VERBATIM_CONSENT_REQUIRED")
        reviewed = self.ledger().review()
        self.assertEqual(
            [row["entry_id"] for row in reviewed["entries"]],
            [saved["entry"]["entry_id"]],
        )

    def test_user_and_project_isolation(self) -> None:
        self.enable(user="researcher-a")
        first = self.capture(user="researcher-a")
        other_user = self.ledger("researcher-b")
        self.assertEqual(other_user.status()["entry_count"], 0)
        self.assertFalse(other_user.status()["ledger_store_exists"])
        with self.assertRaises(Refusal) as caught:
            other_user.drift(
                "A later claim.",
                entry_ids=[first["entry"]["entry_id"]],
            )
        self.assertEqual(caught.exception.code, "VERBATIM_DRIFT_ENTRY_MISSING")

        second_project = Path(self.temporary.name) / "project-two"
        initialize_project(
            second_project,
            title="Other project",
            question="A separate question",
        )
        other_project = ResearchVerbatimLedger(second_project, "researcher-a")
        self.assertEqual(other_project.status()["entry_count"], 0)
        other_project.set_mode("MANUAL", explicit_opt_in=True)
        other_project.capture(
            "Only project two should contain this.",
            source_message_ref="project-two-message",
            capture_mode="MANUAL",
            confirmed=True,
            project_research_statement=True,
        )
        self.assertEqual(self.ledger().status()["entry_count"], 1)
        self.assertEqual(other_project.status()["entry_count"], 1)
        self.assertNotEqual(
            self.ledger().status()["project_isolation_key"],
            other_project.status()["project_isolation_key"],
        )

    def test_relationships_are_same_scope_and_survive_target_removal(self) -> None:
        self.enable()
        original = self.capture(
            "Initial prediction P.",
            source_ref="message-original",
            summary="Initial prediction.",
        )
        corrected = self.ledger().capture(
            "Correction: prediction P applies only in region R.",
            source_message_ref="message-correction",
            capture_mode="MANUAL",
            confirmed=True,
            project_research_statement=True,
            links=[
                {
                    "relation": "CORRECTS",
                    "entry_id": original["entry"]["entry_id"],
                }
            ],
            captured_at_utc="2026-08-14T15:11:00Z",
        )
        self.assertEqual(
            corrected["entry"]["links"][0]["relation"], "CORRECTS"
        )
        self.ledger().remove_entry(
            original["entry"]["entry_id"], confirmed=True
        )
        self.assertTrue(self.ledger().verify()["verified"])
        self.assertEqual(self.ledger().status()["entry_count"], 1)

    def test_tampered_text_and_forged_hash_fail_closed(self) -> None:
        self.enable()
        self.capture()
        path = self.scope_directory() / "ledger.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["entries"][0]["exact_text"] = "Forged wording"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(Refusal) as caught:
            self.ledger().verify()
        self.assertEqual(caught.exception.code, "VERBATIM_TEXT_HASH_MISMATCH")

        value["entries"][0]["exact_text_sha256"] = sha256_text("Forged wording")
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(Refusal) as forged:
            self.ledger().review()
        self.assertEqual(forged.exception.code, "VERBATIM_ENTRY_TAMPERED")

    def test_tampered_ledger_can_still_be_disabled_and_wholly_removed(self) -> None:
        self.enable()
        self.capture()
        scope = self.scope_directory()
        path = scope / "ledger.json"
        path.write_text('{"tampered":true}', encoding="utf-8")
        disabled = self.ledger().disable()
        self.assertFalse(disabled["future_capture_enabled"])
        self.assertFalse(disabled["ledger_content_read"])
        removed = self.ledger().remove(confirmed=True)
        self.assertTrue(removed["removed"])
        self.assertFalse(scope.exists())

    def test_tampered_consent_blocks_capture(self) -> None:
        self.enable()
        path = self.scope_directory() / "consent.json"
        value = json.loads(path.read_text(encoding="utf-8"))
        value["mode"] = "PROJECT"
        path.write_text(json.dumps(value), encoding="utf-8")
        with self.assertRaises(Refusal) as caught:
            self.capture()
        self.assertEqual(caught.exception.code, "VERBATIM_CONSENT_TAMPERED")
        self.assertFalse((self.scope_directory() / "ledger.json").exists())

    def test_hidden_credentials_and_unrelated_content_are_refused(self) -> None:
        self.enable()
        with self.assertRaises(Refusal) as caught:
            capture_entry(
                self.project,
                "researcher-a",
                "System-only instruction",
                source_message_ref="hidden",
                capture_mode="MANUAL",
                confirmed=True,
                project_research_statement=True,
                source_kind="SYSTEM_PROMPT",
            )
        self.assertEqual(caught.exception.code, "VERBATIM_SOURCE_KIND_FORBIDDEN")
        with self.assertRaises(Refusal) as caught:
            self.ledger().capture(
                "api_key = abcdefghijklmnop",
                source_message_ref="credential",
                capture_mode="MANUAL",
                confirmed=True,
                project_research_statement=True,
            )
        self.assertEqual(
            caught.exception.code, "VERBATIM_CREDENTIAL_CONTENT_REFUSED"
        )
        with self.assertRaises(Refusal) as caught:
            self.ledger().capture(
                "Unrelated conversation",
                source_message_ref="unrelated",
                capture_mode="MANUAL",
                confirmed=True,
                project_research_statement=False,
            )
        self.assertEqual(
            caught.exception.code, "VERBATIM_UNRELATED_CONTENT_REFUSED"
        )
        self.assertEqual(self.ledger().status()["entry_count"], 0)

    def test_drift_reports_all_required_categories_without_writes(self) -> None:
        self.enable()
        saved = self.capture(
            "The treatment may not increase response outside group A.",
            summary="A bounded non-increase prediction.",
        )
        entry_id = saved["entry"]["entry_id"]
        ledger_path = self.scope_directory() / "ledger.json"
        before = ledger_path.read_bytes()
        exact = self.ledger().drift(
            saved["entry"]["exact_text"], entry_ids=[entry_id]
        )
        self.assertEqual(
            exact["entry_results"][0]["categories"], ["PRESERVED_MEANING"]
        )

        changed = drift_review(
            self.project,
            "researcher-a",
            "The treatment proves response always increases in group A.",
            entry_ids=[entry_id],
        )
        categories = changed["entry_results"][0]["categories"]
        self.assertIn("OMISSION", categories)
        self.assertIn("CONTRADICTION", categories)
        self.assertIn("OVERSTATEMENT", categories)
        self.assertIn("UNRESOLVED_AMBIGUITY", categories)
        self.assertFalse(changed["scientific_proof"])
        self.assertFalse(changed["source_text_modified"])
        self.assertFalse(changed["later_text_modified"])
        self.assertFalse(changed["persisted"])
        self.assertEqual(before, ledger_path.read_bytes())

    def test_search_export_selected_removal_and_whole_removal(self) -> None:
        self.enable()
        first = self.capture(
            "Baseline alpha predicts a bounded increase.",
            source_ref="alpha-message",
            summary="Alpha baseline.",
        )
        second = self.ledger().capture(
            "Correction beta narrows the population.",
            source_message_ref="beta-message",
            capture_mode="MANUAL",
            confirmed=True,
            project_research_statement=True,
            label="beta correction",
            captured_at_utc="2026-08-14T15:12:00Z",
        )
        found = self.ledger().search("beta")
        self.assertEqual(
            [row["entry_id"] for row in found["entries"]],
            [second["entry"]["entry_id"]],
        )

        exported = self.ledger().export("exports/verbatim-ledger.json")
        export_path = self.project / exported["output"]
        export_value = json.loads(export_path.read_text(encoding="utf-8"))
        self.assertEqual(export_value["entry_count"], 2)
        self.assertIn("exact user wording", export_value["privacy_notice"])
        export_body = dict(export_value)
        export_hash = export_body.pop("export_record_sha256")
        self.assertEqual(export_hash, sha256_text(canonical_json(export_body)))

        removed = self.ledger().remove_entry(
            first["entry"]["entry_id"], confirmed=True
        )
        self.assertEqual(removed["entry_count"], 1)
        complete = self.ledger().remove(confirmed=True)
        self.assertTrue(complete["removed"])
        self.assertFalse(self.scope_directory_parent_exists())
        reset = consent_status(self.project, "researcher-a")
        self.assertEqual(reset["mode"], "OFF")
        self.assertEqual(reset["entry_count"], 0)
        self.assertTrue(export_path.is_file())

    def scope_directory_parent_exists(self) -> bool:
        root = self.project / ".uriel" / "research-verbatim"
        return any(root.glob("user-*/project-*")) if root.exists() else False

    def test_whole_removal_refuses_unknown_members_without_deleting(self) -> None:
        self.enable()
        self.capture()
        scope = self.scope_directory()
        unknown = scope / "preserve-me.txt"
        unknown.write_text("preserve", encoding="utf-8")
        with self.assertRaises(Refusal) as caught:
            remove_ledger(self.project, "researcher-a", confirmed=True)
        self.assertEqual(
            caught.exception.code, "VERBATIM_REMOVE_UNKNOWN_MEMBER"
        )
        self.assertTrue(unknown.is_file())
        self.assertTrue((scope / "consent.json").is_file())
        self.assertTrue((scope / "ledger.json").is_file())

    def test_whole_removal_preflights_every_member_before_deleting(self) -> None:
        self.enable()
        self.capture()
        scope = self.scope_directory()
        consent = scope / "consent.json"
        consent.unlink()
        consent.mkdir()
        with self.assertRaises(Refusal) as caught:
            remove_ledger(self.project, "researcher-a", confirmed=True)
        self.assertEqual(
            caught.exception.code, "VERBATIM_REMOVE_MEMBER_INVALID"
        )
        self.assertTrue(consent.is_dir())
        self.assertTrue((scope / "ledger.json").is_file())

    def test_cli_end_to_end_and_exact_text_file_bytes(self) -> None:
        text_path = self.project / "sources" / "selected-statement.txt"
        exact_bytes = b"Line one\r\n  Line two remains exact.\n"
        text_path.write_bytes(exact_bytes)

        consent = self.run_cli(
            "verbatim",
            "consent",
            "--root",
            str(self.project),
            "--user",
            "cli-user",
            "--mode",
            "manual",
            "--confirm",
        )
        self.assertEqual(consent["result"]["mode"], "MANUAL")
        captured = self.run_cli(
            "verbatim",
            "capture",
            "--root",
            str(self.project),
            "--user",
            "cli-user",
            "--text-file",
            "sources/selected-statement.txt",
            "--source-ref",
            "cli-message",
            "--mode",
            "manual",
            "--confirm-entry",
            "--project-research",
        )
        entry = captured["result"]["entry"]
        self.assertEqual(entry["exact_text"], exact_bytes.decode("utf-8"))
        reviewed = self.run_cli(
            "verbatim",
            "review",
            "--root",
            str(self.project),
            "--user",
            "cli-user",
        )
        self.assertEqual(reviewed["result"]["entry_count"], 1)
        verified = self.run_cli(
            "verbatim",
            "verify",
            "--root",
            str(self.project),
            "--user",
            "cli-user",
        )
        self.assertTrue(verified["result"]["verified"])

    def run_cli(self, *arguments: str) -> dict:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            code = main(["--json", *arguments])
        self.assertEqual(code, 0, stderr.getvalue())
        return json.loads(stdout.getvalue())

    def test_refusals_always_return_exactly_three_repairs(self) -> None:
        with self.assertRaises(Refusal) as caught:
            verify_ledger(self.project, "")
        self.assertEqual(len(caught.exception.repairs), 3)


if __name__ == "__main__":
    unittest.main()
