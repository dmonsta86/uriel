"""Tests for Data Readiness Gate 0: SortSpec, checks, receipts, embargo."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, initialize_project
from uriel.data_readiness import (
    EMBARGO_SENTENCE,
    make_sort_spec,
    readiness_check,
    readiness_status,
)


def _csv(path: Path, header: str, *rows: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes((header + "\n" + "\n".join(rows) + "\n").encode("utf-8"))
    return path


class DataReadinessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        initialize_project(self.root, title="t", question="q", privacy="public")
        self.dataset = _csv(
            self.root / "artifacts" / "data.csv",
            "id,group,value",
            "a,g1,10",
            "b,g1,20",
            "c,g2,30",
        )
        self.plan = self.root / "artifacts" / "plan.md"
        self.plan.write_text("# analysis plan", encoding="utf-8")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_sort_spec_requires_declared_identity(self):
        with self.assertRaises(Refusal) as context:
            make_sort_spec(self.root, "artifacts/data.csv")
        self.assertEqual(context.exception.code, "READINESS_AMBIGUOUS_IDENTITY")

    def test_sort_spec_rejects_unknown_columns(self):
        with self.assertRaises(Refusal):
            make_sort_spec(self.root, "artifacts/data.csv", keys=["nope"])

    def test_sort_spec_created_and_deterministic(self):
        result = make_sort_spec(self.root, "artifacts/data.csv", keys=["id"],
                                analysis_plan="artifacts/plan.md")
        spec = result["sort_spec"]
        self.assertEqual(spec["schema"], "uriel.sort_spec.v1")
        self.assertEqual(spec["primary_keys"], ["id"])
        self.assertEqual(spec["duplicate_policy"], "block")
        self.assertEqual(spec["dataset_identity"], spec["dataset_identity"])
        again = make_sort_spec(self.root, "artifacts/data.csv", keys=["id"],
                               analysis_plan="artifacts/plan.md")
        self.assertEqual(result["sort_spec_sha256"], again["sort_spec_sha256"])

    def test_readiness_check_passes_and_writes_receipt(self):
        spec = make_sort_spec(self.root, "artifacts/data.csv", keys=["id"],
                              analysis_plan="artifacts/plan.md")
        result = readiness_check(self.root)
        self.assertEqual(result["receipt"]["schema"], "uriel.data_readiness.v1")
        self.assertEqual(result["receipt"]["decision"], "PASS")
        self.assertEqual(result["receipt"]["required_check_count"], 22)
        self.assertEqual(result["receipt"]["failed_check_count"], 0)
        self.assertIsNone(result["embargo_sentence"])
        self.assertTrue(Path(result["path"]).is_file())

    def test_duplicate_keys_block_by_default(self):
        _csv(self.root / "artifacts" / "dup.csv", "id,group,value", "a,g1,1", "a,g1,2")
        make_sort_spec(self.root, "artifacts/dup.csv", keys=["id"])
        result = readiness_check(self.root)
        self.assertEqual(result["receipt"]["decision"], "FAIL")
        self.assertEqual(result["embargo_sentence"], EMBARGO_SENTENCE)
        failed = [c["check"] for c in result["checks"] if c["status"] == "FAIL"]
        self.assertIn("duplicate_handling", failed)
        self.assertIn("join_keys_and_cardinality", failed)

    def test_stale_receipt_after_data_change(self):
        make_sort_spec(self.root, "artifacts/data.csv", keys=["id"])
        readiness_check(self.root)
        self.dataset.write_bytes(b"id,group,value\na,g1,10\nb,g1,20\nc,g2,99\n")
        status = readiness_status(self.root, dataset="artifacts/data.csv")
        self.assertEqual(status["decision"], "STALE")

    def test_embargo_before_receipt(self):
        status = readiness_status(self.root)
        self.assertFalse(status["exists"])
        self.assertEqual(status["embargo_sentence"], EMBARGO_SENTENCE)

    def test_order_invariance_under_shuffle(self):
        _csv(self.root / "artifacts" / "shuffled.csv",
             "id,group,value", "c,g2,30", "a,g1,10", "b,g1,20")
        make_sort_spec(self.root, "artifacts/shuffled.csv", keys=["id"])
        result = readiness_check(self.root)
        order = next(c for c in result["checks"] if c["check"] == "order_invariance")
        self.assertEqual(order["status"], "PASS")
        self.assertEqual(result["receipt"]["decision"], "PASS")

    def test_changed_source_generation_fails_source_identity(self):
        make_sort_spec(self.root, "artifacts/data.csv", keys=["id"])
        self.dataset.write_bytes(b"id,group,value\na,g1,10\nb,g1,20\n")
        result = readiness_check(self.root)
        self.assertEqual(result["receipt"]["decision"], "FAIL")
        source = next(c for c in result["checks"] if c["check"] == "source_identity")
        self.assertEqual(source["status"], "FAIL")

    def test_binding_digest_is_recomputable(self):
        spec = make_sort_spec(self.root, "artifacts/data.csv", keys=["id"],
                              analysis_plan="artifacts/plan.md")
        first = readiness_check(self.root)
        second = readiness_check(self.root)
        self.assertEqual(first["receipt"]["binding_digest"], second["receipt"]["binding_digest"])
        self.assertEqual(first["receipt_sha256"], second["receipt_sha256"])

    def test_jsonl_supported(self):
        path = self.root / "artifacts" / "rows.jsonl"
        path.write_bytes('{"id":"a","value":1}\n{"id":"b","value":2}\n'.encode("utf-8"))
        make_sort_spec(self.root, "artifacts/rows.jsonl", keys=["id"])
        result = readiness_check(self.root)
        self.assertEqual(result["receipt"]["decision"], "PASS")

    def test_unsupported_format_blocks(self):
        path = self.root / "artifacts" / "data.xlsx"
        path.write_bytes(b"x")
        with self.assertRaises(Refusal) as context:
            make_sort_spec(self.root, "artifacts/data.xlsx", keys=["id"])
        self.assertEqual(context.exception.code, "READINESS_UNSUPPORTED_FORMAT")

    def test_null_in_key_with_nulls_error_blocks(self):
        _csv(self.root / "artifacts" / "nulls.csv", "id,value", "a,1", ",2")
        make_sort_spec(self.root, "artifacts/nulls.csv", keys=["id"], nulls="nulls_error")
        result = readiness_check(self.root)
        self.assertEqual(result["receipt"]["decision"], "BLOCKED")
        self.assertEqual(result["receipt"]["blocked_check_count"], 1)
        self.assertEqual(result["embargo_sentence"], EMBARGO_SENTENCE)

    def test_missingness_reported(self):
        _csv(self.root / "artifacts" / "missing.csv", "id,value", "a,1", "b,")
        make_sort_spec(self.root, "artifacts/missing.csv", keys=["id"])
        result = readiness_check(self.root)
        missing = next(c for c in result["checks"] if c["check"] == "missingness")
        self.assertEqual(missing["status"], "PASS")
        self.assertEqual(missing["evidence"]["null_counts"]["id"], 0)


if __name__ == "__main__":
    unittest.main()
