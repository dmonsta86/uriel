"""R1.3 deterministic Data Desk and conflict-preserving generation tests."""
from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from uriel.core import Refusal, canonical_json, initialize_project
from uriel.data_contracts import bind_data_record, plan_data_import
from uriel.data_desk import (
    diff_data_generations,
    inspect_data_artifact,
    reconcile_data_generations,
    verify_data_generation,
)
from uriel.data_ingress import import_data_artifact


class DataDeskTests(unittest.TestCase):
    def setUp(self) -> None:
        self._serial = 0

    def _project(self, base: Path) -> Path:
        root = base / "project"
        initialize_project(root, title="Data Desk", question="Can structure be preserved without overclaiming?")
        return root

    def _seal(
        self,
        base: Path,
        root: Path,
        filename: str,
        content: str,
        **budget: int,
    ) -> dict:
        self._serial += 1
        source_dir = base / "private-source-name"
        source_dir.mkdir(exist_ok=True)
        source = source_dir / (str(self._serial) + "-" + filename)
        source.write_text(content, encoding="utf-8")
        planned = plan_data_import(
            root,
            source,
            label="sealed-{0}".format(self._serial),
            **budget,
        )["plan"]
        plan_path = root / "artifacts" / ("plan-{0}.json".format(self._serial))
        plan_path.write_text(canonical_json(planned), encoding="utf-8")
        return import_data_artifact(root, source, plan_path.relative_to(root).as_posix())

    def _generation(
        self,
        base: Path,
        root: Path,
        filename: str,
        content: str,
        **budget: int,
    ) -> dict:
        imported = self._seal(base, root, filename, content, **budget)
        return inspect_data_artifact(root, imported["receipt_relative_path"])

    def test_csv_profile_preserves_duplicate_headers_rows_and_formula_text(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self._project(base)
            imported = self._seal(
                base,
                root,
                "records.csv",
                "id,value,value\n1,=SUM(A1),@literal\n1,=SUM(A1),@literal\n",
            )

            first = inspect_data_artifact(root, imported["receipt_relative_path"])
            self.assertEqual("GENERATED", first["status"])
            self.assertEqual(2, first["record_count"])
            self.assertEqual(3, first["column_count"])
            self.assertFalse(first["gate_0_authority_granted"])
            self.assertFalse(first["scientific_findings_created"])
            profile = first["profile"]
            self.assertEqual("EXPLICIT_DUPLICATE_PRESERVED", profile["header_decision"])
            self.assertEqual(1, profile["exact_duplicate_row_count"])
            self.assertEqual(3, len({row["column_id"] for row in profile["columns"]}))
            self.assertEqual([False, True, True], [row["duplicate_name"] for row in profile["columns"]])
            codes = {row["code"] for row in profile["anomaly_queue"]}
            self.assertIn("DUPLICATE_HEADERS_PRESERVED", codes)
            self.assertIn("EXACT_DUPLICATE_ROWS", codes)
            self.assertIn("FORMULA_LIKE_TEXT_PRESERVED", codes)
            self.assertTrue(all(row["classification"] in {"LEAD", "CANDIDATE"} for row in profile["anomaly_queue"]))

            repeated = inspect_data_artifact(root, imported["receipt_relative_path"])
            self.assertEqual("EXISTING_GENERATION", repeated["status"])
            self.assertEqual(first["generation_id"], repeated["generation_id"])
            verified = verify_data_generation(root, first["generation_id"])
            self.assertTrue(verified["verified"])
            self.assertEqual("PASS", verified["decision"])
            self.assertEqual("DERIVED_NONAUTHORITATIVE", verified["derived_index"]["role"])
            index_path = root / verified["derived_index"]["relative_path"]
            self.assertTrue(index_path.is_file())
            index_path.unlink()
            with self.assertRaises(Refusal) as missing_index:
                verify_data_generation(root, first["generation_id"])
            self.assertEqual("DATA_INDEX_INVALID", missing_index.exception.code)
            repaired = inspect_data_artifact(root, imported["receipt_relative_path"])
            self.assertEqual("EXISTING_GENERATION", repaired["status"])
            self.assertTrue(verify_data_generation(root, first["generation_id"])["verified"])

            with self.assertRaises(Refusal) as ambiguous:
                diff_data_generations(root, first["generation_id"], first["generation_id"], ["value"])
            self.assertEqual("DATA_RECONCILIATION_KEY_INVALID", ambiguous.exception.code)

    def test_supported_formats_produce_independently_verifiable_generations(self) -> None:
        cases = [
            ("records.tsv", "id\tvalue\n1\ta\n2\tb\n", "TSV", 2),
            ("records.json", '[{"id":1,"value":"a"},{"id":2,"value":"b"}]', "JSON", 2),
            ("records.jsonl", '{"id":1,"value":"a"}\n{"id":2,"value":"b"}\n', "JSONL", 2),
            ("notes.txt", "one\ntwo\n", "UTF8_TEXT", 2),
            ("notes.md", "# Heading\nBody\n", "MARKDOWN", 2),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self._project(base)
            for filename, content, format_name, rows in cases:
                with self.subTest(format=format_name):
                    generation = self._generation(base, root, filename, content)
                    self.assertEqual(format_name, generation["manifest"]["format"])
                    self.assertEqual(rows, generation["record_count"])
                    self.assertTrue(verify_data_generation(root, generation["generation_id"])["verified"])

    def test_units_and_semantic_types_are_explicit_user_annotations_not_inference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self._project(base)
            imported = self._seal(base, root, "measurements.csv", "id,mass\na,1.2\nb,2.3\n")
            unannotated = inspect_data_artifact(root, imported["receipt_relative_path"])
            self.assertEqual([], unannotated["profile"]["user_confirmed_annotations"])

            annotated = inspect_data_artifact(
                root,
                imported["receipt_relative_path"],
                units=["mass=kg"],
                semantic_types=["id=specimen identifier"],
            )
            self.assertNotEqual(unannotated["generation_id"], annotated["generation_id"])
            self.assertTrue(annotated["annotations_are_user_confirmed_only"])
            values = {
                (row["annotation_kind"], row["value"], row["confirmation"])
                for row in annotated["profile"]["user_confirmed_annotations"]
            }
            self.assertEqual(
                {
                    ("UNIT", "kg", "USER_CONFIRMED"),
                    ("SEMANTIC_TYPE", "specimen identifier", "USER_CONFIRMED"),
                },
                values,
            )
            self.assertTrue(verify_data_generation(root, annotated["generation_id"])["verified"])

            with self.assertRaises(Refusal) as malformed:
                inspect_data_artifact(root, imported["receipt_relative_path"], units=["mass"])
            self.assertEqual("DATA_ANNOTATION_INVALID", malformed.exception.code)

    def test_adversarial_inputs_fail_closed_or_remain_explicit_leads(self) -> None:
        refusals = [
            ("wide.csv", "a,b\n1\n", {}, "DATA_ROW_WIDTH_MISMATCH"),
            ("duplicate.json", '[{"id":1,"id":2}]', {}, "DATA_DUPLICATE_JSON_KEY"),
            ("deep.json", '[{"a":{"b":{"c":1}}}]', {"max_nesting_depth": 2}, "DATA_NESTING_BUDGET"),
            ("field.csv", "a\n12345\n", {"max_field_bytes": 4}, "DATA_FIELD_BUDGET"),
            ("number.json", '[{"id":12345}]', {"max_field_bytes": 4}, "DATA_NUMERIC_TOKEN_BUDGET"),
            ("spoof.csv", '[{"id":1}]', {}, "DATA_FORMAT_SPOOFED"),
        ]
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self._project(base)
            for filename, content, budget, code in refusals:
                with self.subTest(code=code):
                    imported = self._seal(base, root, filename, content, **budget)
                    with self.assertRaises(Refusal) as refused:
                        inspect_data_artifact(root, imported["receipt_relative_path"])
                    self.assertEqual(code, refused.exception.code)

            case_collision = self._generation(base, root, "case.csv", "ID,id\n1,2\n")
            codes = {row["code"] for row in case_collision["profile"]["anomaly_queue"]}
            self.assertIn("CASE_COLLISION_HEADERS", codes)

    def test_record_multiset_and_source_order_have_separate_identities(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self._project(base)
            first = self._generation(base, root, "first.csv", "id,value\n1,a\n2,b\n")
            reordered = self._generation(base, root, "reordered.csv", "id,value\n2,b\n1,a\n")

            self.assertEqual(first["records_sha256"], reordered["records_sha256"])
            self.assertNotEqual(first["order_sha256"], reordered["order_sha256"])
            self.assertNotEqual(first["generation_id"], reordered["generation_id"])

    def test_low_disk_and_interrupted_manifest_publish_retry_without_false_authority(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self._project(base)
            low_disk_import = self._seal(base, root, "low-disk.csv", "id,value\n1,a\n")
            with mock.patch("uriel.data_desk.shutil.disk_usage", return_value=SimpleNamespace(free=0)):
                with self.assertRaises(Refusal) as low_disk:
                    inspect_data_artifact(root, low_disk_import["receipt_relative_path"])
            self.assertEqual("DATA_DISK_SPACE", low_disk.exception.code)
            generations = root / ".uriel" / "data" / "generations"
            self.assertFalse(generations.exists())

            recovered = inspect_data_artifact(root, low_disk_import["receipt_relative_path"])
            self.assertTrue(verify_data_generation(root, recovered["generation_id"])["verified"])
            authoritative_before = list(generations.glob("*/manifest.json"))

            interrupted_import = self._seal(base, root, "interrupted.csv", "id,value\n2,b\n")
            original_link = os.link
            link_calls = 0

            def interrupt_manifest(source: str, destination: str) -> None:
                nonlocal link_calls
                link_calls += 1
                if link_calls == 4:
                    raise OSError("injected manifest interruption")
                original_link(source, destination)

            with mock.patch("uriel.data_ingress.os.link", side_effect=interrupt_manifest):
                with self.assertRaises(Refusal) as interrupted:
                    inspect_data_artifact(root, interrupted_import["receipt_relative_path"])
            self.assertEqual("DATA_STORAGE_WRITE_FAILED", interrupted.exception.code)
            self.assertEqual(authoritative_before, list(generations.glob("*/manifest.json")))
            self.assertFalse(any(".tmp." in path.name for path in generations.rglob("*")))

            retried = inspect_data_artifact(root, interrupted_import["receipt_relative_path"])
            self.assertEqual("GENERATED", retried["status"])
            self.assertTrue(verify_data_generation(root, retried["generation_id"])["verified"])

    def test_diff_reconcile_preserves_every_record_conflict_and_retry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self._project(base)
            left = self._generation(
                base,
                root,
                "left.csv",
                "id,value\n1,a\n2,b\n3,c\n4,exact\n7,x\n",
            )
            right = self._generation(
                base,
                root,
                "right.csv",
                "id,value\n1,a\n2,b2\n4,exact\n6,new\n7,y\n7,z\n",
            )

            preview = diff_data_generations(root, left["generation_id"], right["generation_id"], ["id"])
            self.assertFalse(preview["writes_performed"])
            self.assertFalse(preview["gate_0_authority_granted"])
            self.assertFalse(preview["scientific_findings_created"])
            self.assertEqual(11, len(preview["delta_ledger"]))
            self.assertTrue(all(row["preserved"] for row in preview["delta_ledger"]))
            self.assertEqual(
                {"LEFT", "RIGHT"},
                {row["side"] for row in preview["delta_ledger"]},
            )
            self.assertEqual(
                {
                    "exact_duplicate_count": 2,
                    "candidate_duplicate_count": 1,
                    "conflict_count": 2,
                    "preserved_conflict_count": 2,
                    "added_count": 1,
                    "absent_count": 1,
                    "modified_count": 1,
                    "unchanged_count": 2,
                    "unknown_count": 1,
                },
                preview["summary"],
            )

            with mock.patch("uriel.data_desk.shutil.disk_usage", return_value=SimpleNamespace(free=0)):
                with self.assertRaises(Refusal) as low_disk:
                    reconcile_data_generations(root, left["generation_id"], right["generation_id"], ["id"])
            self.assertEqual("DATA_DISK_SPACE", low_disk.exception.code)
            reconciliations = root / ".uriel" / "data" / "reconciliations"
            self.assertFalse(reconciliations.exists())

            reconciled = reconcile_data_generations(root, left["generation_id"], right["generation_id"], ["id"])
            self.assertEqual("RECONCILED", reconciled["status"])
            self.assertEqual(11, reconciled["record_count"])
            self.assertTrue(reconciled["all_input_records_preserved"])
            self.assertEqual(2, reconciled["summary"]["conflict_count"])
            self.assertEqual(11, reconciled["delta_entry_count"])
            delta_path = root / reconciled["delta_ledger_relative_path"]
            self.assertTrue(delta_path.is_file())
            verified = verify_data_generation(root, reconciled["generation_id"])
            self.assertTrue(verified["verified"])
            self.assertEqual(
                [left["generation_id"], right["generation_id"]],
                verified["manifest"]["parent_generation_ids"],
            )

            repeated = reconcile_data_generations(root, left["generation_id"], right["generation_id"], ["id"])
            self.assertEqual(reconciled["generation_id"], repeated["generation_id"])
            self.assertEqual(reconciled["reconciliation_relative_path"], repeated["reconciliation_relative_path"])

            delta_bytes = delta_path.read_bytes()
            delta_path.write_bytes(delta_bytes.replace(b'"preserved":true', b'"preserved":false', 1))
            with self.assertRaises(Refusal) as delta_tampered:
                verify_data_generation(root, reconciled["generation_id"])
            self.assertEqual("DATA_GENERATION_VERIFICATION_FAILED", delta_tampered.exception.code)
            delta_path.write_bytes(delta_bytes)

            records_path = root / verified["manifest"]["records_relative_path"]
            original = records_path.read_text(encoding="utf-8")
            records_path.write_text(original.replace('"a"', '"tampered"', 1), encoding="utf-8")
            with self.assertRaises(Refusal) as tampered:
                verify_data_generation(root, reconciled["generation_id"])
            self.assertEqual("DATA_GENERATION_RECORDS_INVALID", tampered.exception.code)

            left_records_path = root / left["manifest"]["records_relative_path"]
            left_text = left_records_path.read_text(encoding="utf-8")
            left_records_path.write_text(left_text.replace('"b"', '"stale-parent"', 1), encoding="utf-8")
            with self.assertRaises(Refusal) as stale_parent:
                diff_data_generations(root, left["generation_id"], right["generation_id"], ["id"])
            self.assertEqual("DATA_GENERATION_RECORDS_INVALID", stale_parent.exception.code)

    def test_reconciliation_identity_binds_both_ordered_parents(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self._project(base)
            left_import = self._seal(base, root, "left.csv", "id,value\n1,a\n")
            right_import = self._seal(base, root, "right.csv", "id,value\n2,b\n")
            left = inspect_data_artifact(
                root,
                left_import["receipt_relative_path"],
                semantic_types=["id=record identifier"],
            )
            right_plain = inspect_data_artifact(root, right_import["receipt_relative_path"])
            right_annotated = inspect_data_artifact(
                root,
                right_import["receipt_relative_path"],
                semantic_types=["id=record identifier"],
            )

            first = reconcile_data_generations(
                root, left["generation_id"], right_plain["generation_id"], ["id"]
            )
            second = reconcile_data_generations(
                root, left["generation_id"], right_annotated["generation_id"], ["id"]
            )
            self.assertNotEqual(first["generation_id"], second["generation_id"])
            self.assertEqual(first["records_sha256"], second["records_sha256"])
            self.assertNotEqual(
                first["manifest"]["operation_binding_sha256"],
                second["manifest"]["operation_binding_sha256"],
            )
            self.assertEqual(
                [left["generation_id"], right_plain["generation_id"]],
                first["manifest"]["parent_generation_ids"],
            )
            self.assertEqual(
                [left["generation_id"], right_annotated["generation_id"]],
                second["manifest"]["parent_generation_ids"],
            )
            self.assertTrue(verify_data_generation(root, first["generation_id"])["verified"])
            self.assertTrue(verify_data_generation(root, second["generation_id"])["verified"])

    def test_verifier_rejects_forged_reconciliation_keys_and_raw_union(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self._project(base)
            left = self._generation(base, root, "left.csv", "id,value\n1,a\n")
            right = self._generation(base, root, "right.csv", "id,value\n2,b\n")
            result = reconcile_data_generations(root, left["generation_id"], right["generation_id"], ["id"])
            manifest_path = root / result["manifest_relative_path"]
            original_manifest_bytes = manifest_path.read_bytes()
            original_manifest = json.loads(original_manifest_bytes)

            reconciliation_path = root / result["reconciliation_relative_path"]
            forged_reconciliation = json.loads(reconciliation_path.read_bytes())
            forged_reconciliation["key_columns"] = ["col-ffffffffffffffff"]
            forged_reconciliation = bind_data_record(forged_reconciliation)
            forged_path = reconciliation_path.parent / (forged_reconciliation["record_sha256"] + ".json")
            forged_path.write_bytes(canonical_json(forged_reconciliation).encode("utf-8"))
            forged_manifest = bind_data_record(
                {**original_manifest, "reconciliation_sha256": forged_reconciliation["record_sha256"]}
            )
            manifest_path.write_bytes(canonical_json(forged_manifest).encode("utf-8"))
            with self.assertRaises(Refusal) as forged_key:
                verify_data_generation(root, result["generation_id"])
            self.assertEqual("DATA_RECONCILIATION_KEY_INVALID", forged_key.exception.code)

            manifest_path.write_bytes(original_manifest_bytes)
            missing_union = bind_data_record(
                {**original_manifest, "raw_artifact_sha256s": left["manifest"]["raw_artifact_sha256s"]}
            )
            manifest_path.write_bytes(canonical_json(missing_union).encode("utf-8"))
            with self.assertRaises(Refusal) as forged_union:
                verify_data_generation(root, result["generation_id"])
            self.assertEqual("DATA_GENERATION_VERIFICATION_FAILED", forged_union.exception.code)

    def test_records_file_exact_bytes_are_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self._project(base)
            generation = self._generation(base, root, "records.csv", "id,value\n1,a\n")
            records_path = root / generation["manifest"]["records_relative_path"]
            original = records_path.read_bytes()
            records_path.write_bytes(original + b"\n")
            with self.assertRaises(Refusal) as blank_byte:
                verify_data_generation(root, generation["generation_id"])
            self.assertEqual("DATA_GENERATION_RECORDS_INVALID", blank_byte.exception.code)
            records_path.write_bytes(original)
            self.assertTrue(verify_data_generation(root, generation["generation_id"])["verified"])

    def test_one_sided_duplicate_groups_remain_candidate_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self._project(base)
            anchor = self._generation(base, root, "anchor.csv", "id,value\n1,a\n")
            duplicates = self._generation(base, root, "duplicates.csv", "id,value\n2,x\n2,x\n")

            added_side = diff_data_generations(root, anchor["generation_id"], duplicates["generation_id"], ["id"])
            self.assertEqual(1, added_side["summary"]["candidate_duplicate_count"])
            self.assertEqual(1, added_side["summary"]["unknown_count"])
            self.assertEqual(0, added_side["summary"]["added_count"])
            right_entries = [row for row in added_side["delta_ledger"] if row["side"] == "RIGHT"]
            self.assertEqual({"CANDIDATE_DUPLICATE"}, {row["classification"] for row in right_entries})
            self.assertTrue(all(not row["conflict"] for row in right_entries))

            absent_side = diff_data_generations(root, duplicates["generation_id"], anchor["generation_id"], ["id"])
            self.assertEqual(1, absent_side["summary"]["candidate_duplicate_count"])
            self.assertEqual(1, absent_side["summary"]["unknown_count"])
            self.assertEqual(0, absent_side["summary"]["absent_count"])
            left_entries = [row for row in absent_side["delta_ledger"] if row["side"] == "LEFT"]
            self.assertEqual({"CANDIDATE_DUPLICATE"}, {row["classification"] for row in left_entries})

    def test_verifier_hard_resource_and_lineage_budgets_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = self._project(base)
            left = self._generation(base, root, "left.csv", "id,value\n1,a\n")
            right = self._generation(base, root, "right.csv", "id,value\n2,b\n")
            result = reconcile_data_generations(root, left["generation_id"], right["generation_id"], ["id"])

            with mock.patch("uriel.data_desk._MAX_GENERATION_FILE_BYTES", 1):
                with self.assertRaises(Refusal) as file_budget:
                    verify_data_generation(root, left["generation_id"])
            self.assertEqual("DATA_GENERATION_BUDGET", file_budget.exception.code)

            with mock.patch("uriel.data_desk._MAX_IMPORT_RECEIPTS", 0):
                with self.assertRaises(Refusal) as receipt_budget:
                    verify_data_generation(root, left["generation_id"])
            self.assertEqual("DATA_GENERATION_RECEIPT_BUDGET", receipt_budget.exception.code)

            with mock.patch("uriel.data_desk._MAX_LINEAGE_GENERATIONS", 2):
                with self.assertRaises(Refusal) as lineage_budget:
                    verify_data_generation(root, result["generation_id"])
            self.assertEqual("DATA_GENERATION_LINEAGE_BUDGET", lineage_budget.exception.code)


if __name__ == "__main__":
    unittest.main()
