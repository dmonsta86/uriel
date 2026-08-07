from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from uriel.decisions import (
    DECISION_CLASSES,
    DecisionRefusal,
    build_decision_import,
    confirm_decision,
    infer_decision,
    load_decision,
    validate_decision_import,
    write_decision,
)
from uriel.publication import (
    AuthorityRefusal,
    build_authority,
    transition_for_decision,
    validate_authority,
    write_authority,
)


class DecisionTests(unittest.TestCase):
    def test_all_decision_classes_are_supported(self) -> None:
        expected = (
            "acknowledged",
            "submitted",
            "administrative_check",
            "under_review",
            "review_invitation",
            "major_revision",
            "minor_revision",
            "revise_and_resubmit",
            "conditional_acceptance",
            "accepted",
            "accepted_in_production",
            "proofs_received",
            "published",
            "desk_rejection",
            "rejected_with_feedback",
            "rejected_resubmit_elsewhere",
            "withdrawn",
            "unknown",
        )
        self.assertEqual(expected, DECISION_CLASSES)

    def test_inference_recognizes_explicit_language(self) -> None:
        cases = {
            "We are pleased to accept your manuscript": "accepted",
            "We request a major revision": "major_revision",
            "The reviewers recommend a minor revision": "minor_revision",
            "Please revise and resubmit": "revise_and_resubmit",
            "Your paper has been conditionally accepted": "conditional_acceptance",
            "This is a desk rejection": "desk_rejection",
            "We regret to reject your submission": "rejected_with_feedback",
            "We suggest you resubmit to another journal": "rejected_resubmit_elsewhere",
            "Your manuscript is under review": "under_review",
            "We invite you to review": "review_invitation",
            "Your article has been published": "published",
            "The paper has been withdrawn": "withdrawn",
            "We acknowledge receipt": "acknowledged",
        }
        for text, expected in cases.items():
            decision_class, confidence, _ = infer_decision(text)
            self.assertEqual(expected, decision_class, text)
            self.assertGreater(confidence, 0)

    def test_unknown_language_is_proposed_not_authoritative(self) -> None:
        decision_class, confidence, _ = infer_decision("Please find attached some notes.")
        self.assertEqual("unknown", decision_class)
        self.assertEqual(0.0, confidence)
        record = build_decision_import("Please find attached some notes.")
        self.assertEqual("proposed_unconfirmed", record["confirmation_state"])
        self.assertEqual("unknown", record["decision_class"])

    def test_high_confidence_inference_is_explicit(self) -> None:
        record = build_decision_import("The reviewers recommend a minor revision.")
        self.assertEqual("minor_revision", record["decision_class"])
        self.assertEqual("explicit", record["confirmation_state"])

    def test_user_confirmation_overrides_inference(self) -> None:
        record = build_decision_import(
            "Please find attached some notes.", decision_class="accepted", user_confirmed=True
        )
        self.assertEqual("accepted", record["decision_class"])
        self.assertEqual("user_confirmed", record["confirmation_state"])
        self.assertIsNone(record["inference_confidence"])

    def test_immutable_write_and_confirmation_chain(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            record = build_decision_import("Please find attached some notes.")
            first = write_decision(store, record)
            second = write_decision(store, record)
            self.assertEqual(first, second)
            confirmed = confirm_decision(record, "major_revision")
            self.assertEqual("user_confirmed", confirmed["confirmation_state"])
            self.assertNotEqual(record["decision_id"], confirmed["decision_id"])
            third = write_decision(store, confirmed)
            self.assertNotEqual(first, third)
            self.assertEqual(record, load_decision(first))

    def test_validation_catches_bad_class(self) -> None:
        record = build_decision_import("We accept the paper.")
        record["decision_class"] = "published_by_ai"
        self.assertTrue(any("decision_class" in v for v in validate_decision_import(record)))


class PublicationTests(unittest.TestCase):
    def test_transition_map_covers_every_decision_class(self) -> None:
        self.assertIsNone(transition_for_decision("acknowledged"))
        self.assertIsNone(transition_for_decision("review_invitation"))
        self.assertIsNone(transition_for_decision("unknown"))
        self.assertEqual("revision_required", transition_for_decision("major_revision"))
        self.assertEqual("conditionally_accepted", transition_for_decision("conditional_acceptance"))
        self.assertEqual("accepted", transition_for_decision("accepted"))
        self.assertEqual("production_ready", transition_for_decision("proofs_received"))
        self.assertEqual("published", transition_for_decision("published"))
        self.assertEqual("not_ready", transition_for_decision("desk_rejection"))
        self.assertEqual("resubmission_ready", transition_for_decision("rejected_resubmit_elsewhere"))

    def test_exclusive_states_never_come_from_deterministic_rule(self) -> None:
        for state in ("submission_authorized", "accepted", "published"):
            record = {
                "schema": "uriel.publication_authority.v1",
                "project_generation": "gen-x",
                "state": state,
                "authority_source": "deterministic_rule",
                "source_artifact_sha256": None,
                "notes": "",
                "recorded_at_utc": "2026-08-06T00:00:00Z",
            }
            self.assertTrue(any("cannot come from" in v for v in validate_authority(record)))
            with self.assertRaises(AuthorityRefusal):
                write_authority(Path("unused"), record)

    def test_authority_write_is_immutable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary) / "authority"
            record = build_authority(
                project_generation="gen-x",
                state="revision_required",
                authority_source="external_artifact",
                source_artifact_sha256="1" * 64,
            )
            first = write_authority(store, record)
            second = write_authority(store, record)
            self.assertEqual(first, second)
            forged = dict(record)
            forged["notes"] = "tampered"
            with self.assertRaises(AuthorityRefusal):
                write_authority(store, forged)


if __name__ == "__main__":
    unittest.main()
