from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from uriel.core import (
    add_evidence,
    build_manifest,
    initialize_project,
    load_project,
    run_workload,
    verify_ledger,
    verify_project,
    verify_source_manifest,
)


class CoreTests(unittest.TestCase):
    def test_snapshot_is_deterministic_and_detects_unexpected_file(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="Determinism", question="Does it detect change?")
            first = build_manifest(root, persist=True)
            second = build_manifest(root, persist=True)
            self.assertEqual(first["manifest_sha256"], second["manifest_sha256"])
            (root / "new.txt").write_text("new", encoding="utf-8")
            verification = verify_source_manifest(root, first)
            self.assertFalse(verification["verified"])
            self.assertIn("SOURCE_UNEXPECTED", {row["code"] for row in verification["errors"]})

    def test_workload_receipt_and_project_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="Run", question="Can output be receipted?")
            receipt = run_workload(root, [sys.executable, "-c", "print('ok')"], workload_id="smoke")
            self.assertEqual(receipt["status"], "PASS")
            self.assertFalse(receipt["shell"])
            verified = verify_project(root)
            self.assertTrue(verified["verified"])
            self.assertEqual(verified["receipts"]["receipt_count"], 1)
            self.assertTrue(verify_ledger(root)["verified"])

    def test_add_evidence_computes_digest_and_links_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            initialize_project(root, title="Evidence", question="What happened?")
            artifact = root / "artifacts" / "observation.json"
            artifact.write_text(json.dumps({"value": 7}) + "\n", encoding="utf-8")
            result = add_evidence(
                root,
                "artifacts/observation.json",
                evidence_id="E1",
                claim_ids=["C1"],
                description="Direct local observation.",
                extraction="value = 7",
                data_location="JSON key value",
                interpretation="The recorded value is seven in this artifact.",
                limitations="This single artifact does not establish generality.",
            )
            self.assertEqual(len(result["evidence"]["sha256"]), 64)
            project = load_project(root)
            self.assertEqual(project["evidence"][0]["id"], "E1")
            self.assertIn("E1", project["claims"][0]["evidence_ids"])


if __name__ == "__main__":
    unittest.main()
