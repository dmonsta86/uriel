from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, atomic_write_json, build_manifest, initialize_project, paths_for, sha256_file
from uriel.reviews import MAX_REVIEW_FILE_BYTES, import_review, review_template, validate_review


class ReviewTests(unittest.TestCase):
    def test_hash_bound_review_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="Review", question="What needs checking?")
            source = build_manifest(root, persist=True)
            paths = paths_for(root)
            value = review_template(
                task="clarity",
                source_manifest_sha256=source["manifest_sha256"],
                project_manifest_sha256=sha256_file(paths.project),
            )
            value.update(
                {
                    "review_id": "review-1",
                    "reviewer_type": "human",
                    "provider": "manual",
                    "model": "none",
                    "created_at_utc": "2026-08-06T00:00:00Z",
                    "scope": "Reviewed claim C1 and the current project manifest only.",
                }
            )
            inbox = paths.state / "review-inbox" / "review.json"
            atomic_write_json(inbox, value)
            imported = import_review(root, inbox)
            self.assertEqual(imported["review_id"], "review-1")
            self.assertEqual(imported["finding_count"], 1)

    def test_stale_review_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="Review", question="What needs checking?")
            source = build_manifest(root, persist=True)
            paths = paths_for(root)
            value = review_template(
                task="clarity",
                source_manifest_sha256=source["manifest_sha256"],
                project_manifest_sha256=sha256_file(paths.project),
            )
            value.update({"review_id": "review-2", "created_at_utc": "2026-08-06T00:00:00Z"})
            (root / "changed.txt").write_text("changed", encoding="utf-8")
            inbox = paths.state / "review-inbox" / "stale.json"
            atomic_write_json(inbox, value)
            with self.assertRaises(Refusal):
                import_review(root, inbox)

    def test_unknown_review_or_finding_fields_fail_closed(self) -> None:
        value = review_template(
            task="clarity",
            source_manifest_sha256="a" * 64,
            project_manifest_sha256="b" * 64,
        )
        value["hidden_extra"] = "not part of the published contract"
        value["findings"][0]["hidden_extra"] = "not part of the published contract"
        errors = validate_review(value)
        self.assertTrue(any(error["path"] == "/" for error in errors))
        self.assertTrue(any(error["path"] == "/findings/0" for error in errors))

    def test_nonobject_review_roots_return_structured_errors(self) -> None:
        for value in ([{}], None, "x"):
            errors = validate_review(value)
            self.assertEqual([{"path": "/", "message": "must be one JSON object"}], errors)

    def test_oversized_review_is_refused_before_json_parse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="Review", question="Bound output?")
            inbox = paths_for(root).state / "review-inbox" / "oversized.json"
            inbox.parent.mkdir(parents=True, exist_ok=True)
            inbox.write_bytes(b"{" + b" " * MAX_REVIEW_FILE_BYTES + b"}")
            with self.assertRaises(Refusal) as blocked:
                import_review(root, inbox)
            self.assertEqual("EXTERNAL_REVIEW_TOO_LARGE", blocked.exception.code)


if __name__ == "__main__":
    unittest.main()
