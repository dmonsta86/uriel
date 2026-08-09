"""R1.1 Evidence Ingress and Data Desk contract tests."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, canonical_json, initialize_project
from uriel.data_contracts import (
    DATA_DELTA_ENTRY_SCHEMA,
    DATA_GENERATION_SCHEMA,
    DATA_GENERATION_SCHEMA_V1,
    DATA_IMPORT_PLAN_SCHEMA,
    DATA_IMPORT_PLAN_SCHEMA_V1,
    DATA_IMPORT_RECEIPT_SCHEMA,
    DATA_POLICY_VERSION,
    DATA_PROFILE_SCHEMA,
    DATA_PROFILE_SCHEMA_V1,
    DATA_RECONCILIATION_SCHEMA,
    DATA_RECONCILIATION_SCHEMA_V1,
    DATA_REFUSAL_SCHEMA,
    DATA_SCHEMA_FILES,
    DATA_TRANSFORM_SCHEMA,
    DATA_VERIFICATION_SCHEMA,
    RAW_ARTIFACT_SCHEMA,
    RESOURCE_BUDGET_SCHEMA,
    RESOURCE_BUDGET_SCHEMA_V1,
    bind_data_record,
    data_contract_catalog,
    load_data_schema,
    make_resource_budget,
    plan_data_import,
    validate_data_record,
    verify_data_record_file,
)


H1 = "1" * 64
H2 = "2" * 64
H3 = "3" * 64
NOW = "2026-08-08T00:00:00Z"
C1 = "col-" + "a" * 16


def _valid_records():
    budget = make_resource_budget()
    records = [budget]
    records.append(bind_data_record({
        "schema": DATA_IMPORT_PLAN_SCHEMA,
        "schema_version": 2,
        "created_at_utc": NOW,
        "policy_version": DATA_POLICY_VERSION,
        "project_binding_sha256": H1,
        "operation": "MANAGED_COPY",
        "mode": "DRY_RUN",
        "consent": "EXPLICIT_USER_SELECTION",
        "source": {
            "logical_label": "source-111111111111",
            "content_sha256": H1,
            "size_bytes": 12,
            "media_type": "text/csv",
            "format": "CSV",
            "encoding": "utf-8",
            "access_condition": "USER_SELECTED_LOCAL_REGULAR_FILE",
            "location_disclosure": "PRIVATE_EPHEMERAL",
        },
        "resource_budget": budget,
        "planned_raw_artifact_schema": RAW_ARTIFACT_SCHEMA,
        "writes_performed": False,
        "network_permitted": False,
    }))
    records.append(bind_data_record({
        "schema": DATA_IMPORT_RECEIPT_SCHEMA,
        "schema_version": 1,
        "created_at_utc": NOW,
        "policy_version": DATA_POLICY_VERSION,
        "import_plan_sha256": H1,
        "raw_artifact_sha256": H2,
        "source_content_sha256": H3,
        "copied_content_sha256": H3,
        "source_size_bytes": 12,
        "bytes_copied": 12,
        "managed_relative_path": "data/raw/33/source.csv",
        "outcome": "COPIED",
        "source_mutated": False,
    }))
    records.append(bind_data_record({
        "schema": RAW_ARTIFACT_SCHEMA,
        "schema_version": 1,
        "created_at_utc": NOW,
        "artifact_id": "raw-" + H1,
        "logical_label": "source-111111111111",
        "managed_relative_path": "data/raw/11/source.csv",
        "media_type": "text/csv",
        "format": "CSV",
        "size_bytes": 12,
        "content_sha256": H1,
        "source_access_condition": "USER_SELECTED_LOCAL_REGULAR_FILE",
        "immutable": True,
    }))
    records.append(bind_data_record({
        "schema": DATA_GENERATION_SCHEMA,
        "schema_version": 2,
        "created_at_utc": NOW,
        "generation_id": H1,
        "parent_generation_ids": [],
        "operation_binding_sha256": None,
        "format": "CSV",
        "parser_version": "uriel.data_parser.v1",
        "parser_decisions": {
            "representation": "COLUMN_ID_OBJECTS",
            "source_order_preserved": True,
            "header_decision": "EXPLICIT_UNIQUE",
            "format_decision": "DELIMITED_UTF8_COMMA_QUOTE_DOUBLEQUOTE_STRICT_HEADER_ROW_1",
            "columns": [{"column_id": C1, "name": "id", "position": 0, "duplicate_name": False}],
        },
        "user_confirmed_annotations": [],
        "raw_artifact_sha256s": [H2],
        "transform_receipt_sha256s": [],
        "reconciliation_sha256": None,
        "record_count": 2,
        "column_count": 1,
        "records_sha256": H3,
        "order_sha256": H2,
        "records_file_sha256": H1,
        "records_file_size_bytes": 128,
        "records_relative_path": ".uriel/data/generations/11/records.jsonl",
        "profile_relative_path": ".uriel/data/generations/11/profile.json",
        "profile_sha256": H1,
        "derived_index_kind": "SQLITE_DERIVED_NONAUTHORITATIVE",
        "derived_index_relative_path": ".uriel/data/indexes/" + H1 + ".sqlite",
    }))
    records.append(bind_data_record({
        "schema": DATA_PROFILE_SCHEMA,
        "schema_version": 2,
        "created_at_utc": NOW,
        "generation_id": H1,
        "format": "CSV",
        "table_count": 1,
        "row_count": 2,
        "records_sha256": H3,
        "order_sha256": H2,
        "header_decision": "EXPLICIT_UNIQUE",
        "exact_duplicate_row_count": 0,
        "candidate_keys": [C1],
        "columns": [{
            "column_id": C1,
            "name": "id",
            "position": 0,
            "duplicate_name": False,
            "observed_type": "STRING",
            "null_count": 0,
            "distinct_count": 2,
        }],
        "user_confirmed_annotations": [],
        "anomaly_queue": [],
        "limitations": ["Structure only; no scientific interpretation."],
    }))
    records.append(bind_data_record({
        "schema": DATA_TRANSFORM_SCHEMA,
        "schema_version": 1,
        "created_at_utc": NOW,
        "input_generation_id": H1,
        "output_generation_id": H2,
        "transform_kind": "SORT",
        "rule_set_sha256": H3,
        "rows_before": 2,
        "rows_after": 2,
        "lossless": True,
        "source_mutated": False,
    }))
    records.append(bind_data_record({
        "schema": DATA_DELTA_ENTRY_SCHEMA,
        "schema_version": 1,
        "side": "LEFT",
        "ordinal": 0,
        "source_record_sha256": H1,
        "key_sha256": H2,
        "classification": "MODIFIED",
        "counterpart_count": 1,
        "exact_counterpart_count": 0,
        "conflict": True,
        "preserved": True,
    }))
    records.append(bind_data_record({
        "schema": DATA_RECONCILIATION_SCHEMA,
        "schema_version": 2,
        "created_at_utc": NOW,
        "left_generation_id": H1,
        "right_generation_id": H2,
        "left_records_sha256": H1,
        "right_records_sha256": H2,
        "key_columns": [C1],
        "exact_duplicate_count": 1,
        "candidate_duplicate_count": 0,
        "conflict_count": 1,
        "preserved_conflict_count": 1,
        "added_count": 0,
        "absent_count": 0,
        "modified_count": 1,
        "unchanged_count": 1,
        "unknown_count": 0,
        "contradiction_policy": "PRESERVE_ALL",
        "result_generation_id": H3,
        "result_record_count": 4,
        "result_records_sha256": H3,
        "delta_sha256": H1,
        "delta_entry_count": 4,
        "delta_ledger_relative_path": ".uriel/data/deltas/" + H1 + ".jsonl",
    }))
    records.append(bind_data_record({
        "schema": DATA_REFUSAL_SCHEMA,
        "schema_version": 1,
        "created_at_utc": NOW,
        "operation": "IMPORT",
        "code": "DATA_FORMAT_UNSUPPORTED",
        "message": "Unsupported source format.",
        "source_logical_label": "source-111111111111",
        "source_identity_sha256": H1,
        "safe_state": "NO_WRITE",
    }))
    records.append(bind_data_record({
        "schema": DATA_VERIFICATION_SCHEMA,
        "schema_version": 1,
        "created_at_utc": NOW,
        "target_schema": RAW_ARTIFACT_SCHEMA,
        "target_record_sha256": H1,
        "verifier_version": "1",
        "decision": "PASS",
        "errors": [],
        "independent_recompute": True,
    }))
    return records


class DataContractTests(unittest.TestCase):
    def test_all_sixteen_packaged_schemas_validate_bound_examples(self) -> None:
        catalog = data_contract_catalog()
        self.assertEqual(16, len(catalog))
        self.assertEqual(set(DATA_SCHEMA_FILES), {row["schema"] for row in catalog})
        for row in catalog:
            self.assertEqual(64, len(row["sha256"]))
            schema = load_data_schema(row["schema"])
            self.assertEqual(row["schema"], schema["$id"])
            self.assertFalse(schema["additionalProperties"])
            self.assertIn("record_sha256", schema["required"])
        for record in _valid_records():
            result = validate_data_record(record)
            self.assertTrue(result["valid"], record["schema"])

    def test_published_v1_contracts_remain_record_valid(self) -> None:
        current_plan = _valid_records()[1]
        current_budget = current_plan["resource_budget"]
        legacy_budget_body = {
            key: value
            for key, value in current_budget.items()
            if key not in {"record_sha256", "max_field_bytes"}
        }
        legacy_budget_body.update({"schema": RESOURCE_BUDGET_SCHEMA_V1, "schema_version": 1})
        legacy_budget = bind_data_record(legacy_budget_body)
        legacy_plan_body = {
            key: value for key, value in current_plan.items() if key != "record_sha256"
        }
        legacy_plan_body.update(
            {
                "schema": DATA_IMPORT_PLAN_SCHEMA_V1,
                "schema_version": 1,
                "resource_budget": legacy_budget,
            }
        )
        legacy_plan = bind_data_record(legacy_plan_body)
        legacy_generation = bind_data_record(
            {
                "schema": DATA_GENERATION_SCHEMA_V1,
                "schema_version": 1,
                "created_at_utc": NOW,
                "generation_id": H1,
                "parent_generation_id": None,
                "raw_artifact_sha256s": [H2],
                "transform_receipt_sha256s": [],
                "reconciliation_sha256": None,
                "record_count": 2,
                "records_sha256": H3,
            }
        )
        legacy_profile = bind_data_record(
            {
                "schema": DATA_PROFILE_SCHEMA_V1,
                "schema_version": 1,
                "created_at_utc": NOW,
                "generation_id": H1,
                "table_count": 1,
                "row_count": 2,
                "columns": [
                    {
                        "name": "id",
                        "observed_type": "STRING",
                        "null_count": 0,
                        "distinct_count": 2,
                    }
                ],
                "limitations": ["Legacy structure only."],
            }
        )
        legacy_reconciliation = bind_data_record(
            {
                "schema": DATA_RECONCILIATION_SCHEMA_V1,
                "schema_version": 1,
                "created_at_utc": NOW,
                "left_generation_id": H1,
                "right_generation_id": H2,
                "exact_duplicate_count": 0,
                "candidate_duplicate_count": 0,
                "conflict_count": 0,
                "preserved_conflict_count": 0,
                "contradiction_policy": "PRESERVE_ALL",
                "result_generation_id": None,
            }
        )
        for record in (
            legacy_budget,
            legacy_plan,
            legacy_generation,
            legacy_profile,
            legacy_reconciliation,
        ):
            self.assertTrue(validate_data_record(record)["valid"], record["schema"])

    def test_plan_is_no_write_and_does_not_disclose_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            source = base / "private-account-name" / "records.csv"
            source.parent.mkdir()
            source.write_text("id,value\na,1\n", encoding="utf-8")
            initialize_project(root, title="Data plan", question="Can this source be planned?")
            result = plan_data_import(root, source)
            rendered = canonical_json(result)
            self.assertFalse(result["writes_performed"])
            self.assertFalse(result["source_path_disclosed"])
            self.assertNotIn(str(source), rendered)
            self.assertNotIn("private-account-name", rendered)
            self.assertFalse((root / ".uriel" / "data").exists())
            self.assertTrue(result["validation"]["valid"])

    def test_unknown_field_version_missing_field_and_tamper_fail(self) -> None:
        plan = _valid_records()[1]
        unknown = bind_data_record({**plan, "source_path": "C:/private/source.csv"})
        wrong_version = bind_data_record({**plan, "schema_version": 1})
        missing = dict(plan)
        missing.pop("project_binding_sha256")
        missing = bind_data_record(missing)
        tampered = copy.deepcopy(plan)
        tampered["source"]["logical_label"] = "changed"
        for candidate in (unknown, wrong_version, missing, tampered):
            with self.assertRaises(Refusal) as caught:
                validate_data_record(candidate)
            self.assertEqual("DATA_CONTRACT_INVALID", caught.exception.code)

    def test_invalid_budget_and_unpreserved_conflict_fail(self) -> None:
        with self.assertRaises(Refusal):
            make_resource_budget(max_source_bytes=0)
        reconciliation = next(
            record for record in _valid_records()
            if record["schema"] == DATA_RECONCILIATION_SCHEMA
        )
        broken = bind_data_record({**reconciliation, "preserved_conflict_count": 0})
        with self.assertRaises(Refusal) as caught:
            validate_data_record(broken)
        self.assertIn("preserved", str(caught.exception.details.get("errors")))

    def test_unsafe_source_types_and_unsupported_formats_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            initialize_project(root, title="Data plan", question="q")
            with self.assertRaises(Refusal) as directory:
                plan_data_import(root, base)
            self.assertEqual("DATA_SOURCE_TYPE_REFUSED", directory.exception.code)
            archive = base / "records.zip"
            archive.write_bytes(b"not-an-archive")
            with self.assertRaises(Refusal) as unsupported:
                plan_data_import(root, archive)
            self.assertEqual("DATA_FORMAT_UNSUPPORTED", unsupported.exception.code)
            with self.assertRaises(Refusal) as network:
                plan_data_import(root, r"\\server\share\records.csv")
            self.assertEqual("DATA_NETWORK_PATH_REFUSED", network.exception.code)

    def test_relative_path_escape_and_record_file_escape_refuse(self) -> None:
        raw = _valid_records()[3]
        escaped = bind_data_record({**raw, "managed_relative_path": "../outside.csv"})
        with self.assertRaises(Refusal):
            validate_data_record(escaped)
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            initialize_project(root, title="Data plan", question="q")
            outside = base / "outside.json"
            outside.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(Refusal) as caught:
                verify_data_record_file(root, "../outside.json")
            self.assertEqual("INVALID_RELATIVE_PATH", caught.exception.code)

    @unittest.skipIf(not hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_source_refuses_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            initialize_project(root, title="Data plan", question="q")
            target = base / "target.csv"
            target.write_text("id\na\n", encoding="utf-8")
            link = base / "link.csv"
            try:
                os.symlink(str(target), str(link))
            except OSError:
                self.skipTest("symlink creation unavailable for this account")
            with self.assertRaises(Refusal) as caught:
                plan_data_import(root, link)
            self.assertEqual("DATA_SOURCE_TYPE_REFUSED", caught.exception.code)

    @unittest.skipIf(not hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_parent_source_refuses_when_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            root = base / "project"
            initialize_project(root, title="Data plan", question="q")
            real = base / "real"
            real.mkdir()
            (real / "records.csv").write_text("id\na\n", encoding="utf-8")
            link = base / "linked"
            try:
                os.symlink(str(real), str(link), target_is_directory=True)
            except OSError:
                self.skipTest("directory symlink creation unavailable for this account")
            with self.assertRaises(Refusal) as caught:
                plan_data_import(root, link / "records.csv")
            self.assertEqual("DATA_SOURCE_TYPE_REFUSED", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
