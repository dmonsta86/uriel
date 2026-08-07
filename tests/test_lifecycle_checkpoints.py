from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from uriel.checkpoints import (
    GenerationRefusal,
    build_checkpoint,
    generation_id_for,
    load_checkpoint,
    records_sha256,
    validate_checkpoint,
    write_checkpoint,
)
from uriel.core import canonical_json


class CheckpointTests(unittest.TestCase):
    def test_checkpoint_builds_and_validates(self) -> None:
        record = build_checkpoint(
            records_sha256="a" * 64,
            record_count=3,
            source_manifest_sha256="b" * 64,
            ephemeral_policy_version="ephemeral-policy-2026-08-07",
            publication_authority="internal_review_ready",
        )
        self.assertEqual(record["schema"], "uriel.checkpoint.v1")
        self.assertEqual([], validate_checkpoint(record))
        self.assertTrue(record["generation_id"].startswith("gen-"))

    def test_generation_id_is_content_addressed_and_parent_aware(self) -> None:
        first = generation_id_for("a" * 64, None)
        second = generation_id_for("a" * 64, None)
        self.assertEqual(first, second)
        self.assertNotEqual(first, generation_id_for("b" * 64, None))
        self.assertNotEqual(first, generation_id_for("a" * 64, "gen-parent"))

    def test_records_sha256_is_deterministic_and_order_sensitive(self) -> None:
        rows_a = [{"id": "x"}, {"id": "y"}]
        rows_b = [{"id": "y"}, {"id": "x"}]
        self.assertEqual(records_sha256(rows_a), records_sha256(list(rows_a)))
        self.assertNotEqual(records_sha256(rows_a), records_sha256(rows_b))

    def test_identical_replay_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary) / "generations"
            record = build_checkpoint(
                records_sha256="c" * 64,
                record_count=1,
                source_manifest_sha256="d" * 64,
                ephemeral_policy_version="p1",
            )
            first = write_checkpoint(store, record)
            second = write_checkpoint(store, record)
            self.assertEqual(first, second)
            self.assertEqual(record, load_checkpoint(first))

    def test_collision_with_different_content_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary) / "generations"
            record = build_checkpoint(
                records_sha256="e" * 64,
                record_count=1,
                source_manifest_sha256="f" * 64,
                ephemeral_policy_version="p1",
            )
            write_checkpoint(store, record)
            forged = dict(record)
            forged["record_count"] = 99
            with self.assertRaises(GenerationRefusal):
                write_checkpoint(store, forged)

    def test_validation_catches_bad_hash_and_bad_state(self) -> None:
        record = build_checkpoint(
            records_sha256="1" * 64,
            record_count=0,
            source_manifest_sha256="2" * 64,
            ephemeral_policy_version="p1",
            publication_authority="submission_authorized",
        )
        record["source_manifest_sha256"] = "not-a-hash"
        record["publication_authority"] = "accepted_by_ai"
        violations = validate_checkpoint(record)
        self.assertTrue(any("source_manifest_sha256" in v for v in violations))
        self.assertTrue(any("publication_authority" in v for v in violations))

    def test_canonical_json_matches_core_convention(self) -> None:
        sample = {"b": 1, "a": [2, 3]}
        from uriel.core import canonical_json as core_canonical

        self.assertEqual(canonical_json(sample), core_canonical(sample))


if __name__ == "__main__":
    unittest.main()
