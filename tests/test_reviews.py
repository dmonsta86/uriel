from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, atomic_write_json, build_manifest, initialize_project, paths_for, sha256_file
from uriel.reviews import import_review, review_template


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


if __name__ == "__main__":
    unittest.main()
