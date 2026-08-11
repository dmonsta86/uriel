from __future__ import annotations

import hashlib
import json
import re
import unittest
from importlib import resources
from pathlib import Path
from typing import Any, Dict, Iterable, Set


ROOT = Path(__file__).resolve().parents[1]
RUN_SCHEMA_NAME = "uriel.forge_run.v1.schema.json"
EXPORT_SCHEMA_NAME = "uriel.forge_sanitized_export.v1.schema.json"
DEFERRAL_SCHEMA_NAME = "uriel.forge_deferral.v1.schema.json"
CONTINUATION_SCHEMA_NAME = "uriel.forge_continuation.v1.schema.json"
PUBLIC_SUMMARY_SCHEMA_NAME = "uriel.forge_public_summary.v1.schema.json"

STATES = [
    "DRAFT",
    "SCOPED",
    "AUDITED",
    "IMPLEMENTING",
    "VERIFYING",
    "READY_FOR_INDEPENDENT_VERIFY",
    "COMPLETE",
    "COMPLETE_WITH_DEFERRED_SOFT_GATES",
    "BLOCKED",
    "FAILED",
    "STALE",
    "SUPERSEDED",
    "ABORTED",
]

TRANSITIONS = {
    "DRAFT": ["SCOPED", "BLOCKED", "FAILED", "STALE", "SUPERSEDED", "ABORTED"],
    "SCOPED": ["AUDITED", "BLOCKED", "FAILED", "STALE", "SUPERSEDED", "ABORTED"],
    "AUDITED": ["IMPLEMENTING", "BLOCKED", "FAILED", "STALE", "SUPERSEDED", "ABORTED"],
    "IMPLEMENTING": ["VERIFYING", "BLOCKED", "FAILED", "STALE", "SUPERSEDED", "ABORTED"],
    "VERIFYING": [
        "IMPLEMENTING",
        "READY_FOR_INDEPENDENT_VERIFY",
        "BLOCKED",
        "FAILED",
        "STALE",
        "SUPERSEDED",
        "ABORTED",
    ],
    "READY_FOR_INDEPENDENT_VERIFY": [
        "IMPLEMENTING",
        "VERIFYING",
        "COMPLETE",
        "COMPLETE_WITH_DEFERRED_SOFT_GATES",
        "BLOCKED",
        "FAILED",
        "STALE",
        "SUPERSEDED",
        "ABORTED",
    ],
    "COMPLETE": ["STALE", "SUPERSEDED"],
    "COMPLETE_WITH_DEFERRED_SOFT_GATES": ["STALE", "SUPERSEDED"],
    "BLOCKED": [
        "DRAFT",
        "SCOPED",
        "AUDITED",
        "IMPLEMENTING",
        "VERIFYING",
        "READY_FOR_INDEPENDENT_VERIFY",
        "FAILED",
        "STALE",
        "SUPERSEDED",
        "ABORTED",
    ],
    "FAILED": [],
    "STALE": [],
    "SUPERSEDED": [],
    "ABORTED": [],
}

REFERENCE_ROLES = [
    "PROJECT_MANIFEST",
    "SOURCE_MANIFEST",
    "WORKBENCH_GENERATION",
    "DATA_GENERATION",
    "READINESS_SELECTION",
    "AUDIT",
    "GATE_DECISION",
    "GAP_REGISTER",
    "TEST_PLAN",
    "TEST_RECEIPT",
    "DECISION",
    "DEFERRAL",
    "PUBLICATION_AUTHORITY",
    "PACKET_MANIFEST",
    "VERIFIER_RECEIPT",
    "BLESSING",
    "EVIDENCE",
    "RESULT",
    "RESUME_PACKET",
]

FORBIDDEN_AUTHORITY_FIELDS = {
    "blessed",
    "blessing_status",
    "gate_pass",
    "gate_status",
    "publication_ready",
    "publication_status",
    "verified",
    "verifier_status",
}


def _load_editor_schema(name: str) -> Dict[str, Any]:
    return json.loads((ROOT / "schemas" / name).read_text(encoding="utf-8"))


def _property_names(value: Any) -> Set[str]:
    names: Set[str] = set()
    if isinstance(value, dict):
        properties = value.get("properties")
        if isinstance(properties, dict):
            names.update(properties)
        for child in value.values():
            names.update(_property_names(child))
    elif isinstance(value, list):
        for child in value:
            names.update(_property_names(child))
    return names


def _object_contracts(value: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(value, dict):
        if value.get("type") == "object":
            yield value
        for child in value.values():
            yield from _object_contracts(child)
    elif isinstance(value, list):
        for child in value:
            yield from _object_contracts(child)


def _canonical_record_sha256(record: Dict[str, Any]) -> str:
    body = dict(record)
    body.pop("record_sha256", None)
    encoded = json.dumps(
        body,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


class ForgeContractTests(unittest.TestCase):
    def test_editor_and_packaged_schemas_are_byte_identical(self) -> None:
        package_root = resources.files("uriel").joinpath("schemas")
        for name in (
            RUN_SCHEMA_NAME,
            EXPORT_SCHEMA_NAME,
            DEFERRAL_SCHEMA_NAME,
            CONTINUATION_SCHEMA_NAME,
            PUBLIC_SUMMARY_SCHEMA_NAME,
        ):
            editor_bytes = (ROOT / "schemas" / name).read_bytes()
            packaged_bytes = package_root.joinpath(name).read_bytes()
            self.assertEqual(editor_bytes, packaged_bytes, name)

    def test_run_contract_freezes_exact_states_transitions_and_roles(self) -> None:
        schema = _load_editor_schema(RUN_SCHEMA_NAME)
        self.assertEqual(STATES, schema["$defs"]["state"]["enum"])
        self.assertEqual(TRANSITIONS, schema["x-uriel-state-transitions"])
        role_contract = schema["properties"]["refs"]["items"]["properties"]["role"]
        self.assertEqual(REFERENCE_ROLES, role_contract["enum"])

    def test_run_contract_is_closed_bounded_and_authority_neutral(self) -> None:
        schema = _load_editor_schema(RUN_SCHEMA_NAME)
        for contract in _object_contracts(schema):
            self.assertIs(False, contract.get("additionalProperties"), contract)
        self.assertEqual("FORGE_WORKFLOW_ONLY", schema["properties"]["authority_scope"]["const"])
        self.assertEqual("NONE", schema["properties"]["upstream_authority_effect"]["const"])
        self.assertFalse(FORBIDDEN_AUTHORITY_FIELDS & _property_names(schema))

        properties = schema["properties"]
        self.assertEqual(256, properties["requirements"]["maxItems"])
        self.assertEqual(2048, properties["refs"]["maxItems"])
        self.assertEqual(256, properties["work_packages"]["maxItems"])
        self.assertEqual(4 * 1024 * 1024, schema["x-uriel-max-record-bytes"])
        self.assertTrue(properties["requirements"]["uniqueItems"])
        self.assertTrue(properties["refs"]["uniqueItems"])
        self.assertTrue(properties["work_packages"]["uniqueItems"])
        self.assertNotIn("PASS", properties["result"]["properties"]["outcome"]["enum"])

    def test_run_contract_contains_one_event_work_packages_and_integrity_manifest(self) -> None:
        schema = _load_editor_schema(RUN_SCHEMA_NAME)
        required = set(schema["required"])
        self.assertTrue({"event", "work_packages", "manifest", "indexes"} <= required)

        event_required = set(schema["properties"]["event"]["required"])
        self.assertEqual(
            {
                "event_id",
                "event_kind",
                "created_at_utc",
                "initiator",
                "from_state",
                "to_state",
                "rationale",
                "changed_work_package_ids",
                "changed_ref_ids",
            },
            event_required,
        )
        work_required = set(schema["properties"]["work_packages"]["items"]["required"])
        self.assertTrue(
            {"depends_on", "requirement_ids", "input_ref_ids", "acceptance_ref_ids"}
            <= work_required
        )
        manifest_required = set(schema["properties"]["manifest"]["required"])
        self.assertTrue(
            {"requirements_sha256", "refs_sha256", "work_packages_sha256", "event_sha256"}
            <= manifest_required
        )

    def test_relative_path_contract_accepts_portable_names_and_refuses_escapes(self) -> None:
        schema = _load_editor_schema(RUN_SCHEMA_NAME)
        pattern = re.compile(schema["$defs"]["relativePath"]["pattern"])
        accepted = [
            "docs/result file.json",
            ".uriel/forge/runs/run-1/index.json",
            "研究/证据.json",
        ]
        refused = [
            "/absolute.json",
            r"C:\private.json",
            "../escape.json",
            "a/../b.json",
            "a/./b.json",
            "a//b.json",
            "a:b.json",
            "a/",
        ]
        self.assertTrue(all(pattern.fullmatch(value) for value in accepted))
        self.assertTrue(all(not pattern.fullmatch(value) for value in refused))

    def test_record_digest_rule_is_canonical_and_tamper_evident(self) -> None:
        schema = _load_editor_schema(RUN_SCHEMA_NAME)
        self.assertEqual(
            {
                "algorithm": "sha256",
                "canonicalization": "uriel.canonical_json.v1",
                "excluded_fields": ["record_sha256"],
            },
            schema["x-uriel-record-digest"],
        )
        record = {"schema": "uriel.forge_run.v1", "mission": "Test", "record_sha256": "0" * 64}
        digest = _canonical_record_sha256(record)
        record["record_sha256"] = "f" * 64
        self.assertEqual(digest, _canonical_record_sha256(record))
        record["mission"] = "Changed"
        self.assertNotEqual(digest, _canonical_record_sha256(record))

    def test_sanitized_export_contract_excludes_private_identity_and_body_fields(self) -> None:
        schema = _load_editor_schema(EXPORT_SCHEMA_NAME)
        for contract in _object_contracts(schema):
            self.assertIs(False, contract.get("additionalProperties"), contract)

        forbidden = set(schema["x-uriel-forbidden-export-fields"])
        self.assertFalse(forbidden & _property_names(schema))
        self.assertNotIn("project_id", schema["properties"])
        self.assertNotIn("run_id", schema["properties"])
        self.assertIn("project_alias", schema["properties"])
        self.assertIn("run_alias", schema["properties"])

        sanitization = schema["properties"]["sanitization"]
        self.assertEqual(set(sanitization["required"]), set(sanitization["properties"]))
        self.assertTrue(all(rule == {"const": True} for rule in sanitization["properties"].values()))
        self.assertEqual(512, schema["properties"]["entries"]["maxItems"])
        self.assertEqual(1024 * 1024, schema["x-uriel-max-record-bytes"])
        self.assertEqual(16 * 1024 * 1024, schema["properties"]["total_bytes"]["maximum"])
        self.assertEqual("NONE", schema["properties"]["upstream_authority_effect"]["const"])

    def test_continuation_contract_freezes_blocker_proof_and_transparent_ranking(self) -> None:
        schema = _load_editor_schema(CONTINUATION_SCHEMA_NAME)
        for contract in _object_contracts(schema):
            self.assertIs(False, contract.get("additionalProperties"), contract)
        self.assertEqual(1024 * 1024, schema["x-uriel-max-record-bytes"])
        self.assertEqual(7, schema["properties"]["blocker_proof"]["properties"]["checks"]["minItems"])
        self.assertEqual(7, schema["properties"]["blocker_proof"]["properties"]["checks"]["maxItems"])
        ratings = schema["$defs"]["ratings"]
        self.assertEqual(12, len(ratings["required"]))
        self.assertEqual(set(ratings["required"]), set(ratings["properties"]))
        next_moves = schema["properties"]["next_moves"]["properties"]
        self.assertEqual("TRANSPARENT_QUALITATIVE_ORDINAL_V1", next_moves["method"]["const"])
        self.assertEqual(
            "ORDINAL_PRIORITY_ONLY_NOT_PROBABILITY_OR_TRUTH",
            next_moves["score_interpretation"]["const"],
        )
        self.assertEqual(3, next_moves["ranked"]["maxItems"])
        self.assertEqual("FORGE_CONTINUATION_ONLY", schema["properties"]["authority_scope"]["const"])
        self.assertEqual("NONE", schema["properties"]["upstream_authority_effect"]["const"])
        self.assertFalse(FORBIDDEN_AUTHORITY_FIELDS & _property_names(schema))

    def test_public_summary_contract_is_metadata_only_and_excludes_private_disclosure(self) -> None:
        schema = _load_editor_schema(PUBLIC_SUMMARY_SCHEMA_NAME)
        for contract in _object_contracts(schema):
            self.assertIs(False, contract.get("additionalProperties"), contract)
        self.assertEqual("METADATA_ONLY", schema["x-uriel-body-policy"])
        self.assertIs(False, schema["properties"]["body_exported"]["const"])
        reference = schema["properties"]["references"]["items"]["properties"]
        self.assertEqual(["SANITIZABLE_METADATA", "PUBLIC"], reference["disclosure"]["enum"])
        self.assertEqual("METADATA_ONLY", reference["body_policy"]["const"])
        self.assertEqual("boolean", reference["typed_record"]["type"])
        self.assertEqual(
            ["JSON", "TEXT", "TABLE", "IMAGE", "AUDIO", "VIDEO", "BINARY", "OTHER"],
            reference["media_family"]["enum"],
        )
        self.assertNotIn("record_schema", reference)
        self.assertNotIn("media_type", reference)
        self.assertNotIn("path", reference)
        self.assertNotIn("ref_id", reference)
        self.assertNotIn("project_id", schema["properties"])
        self.assertNotIn("run_id", schema["properties"])
        self.assertEqual("NONE", schema["properties"]["upstream_authority_effect"]["const"])

    def test_soft_gate_deferral_is_closed_complete_and_authority_neutral(self) -> None:
        schema = _load_editor_schema(DEFERRAL_SCHEMA_NAME)
        self.assertIs(False, schema["additionalProperties"])
        self.assertEqual(64 * 1024, schema["x-uriel-max-record-bytes"])
        self.assertEqual(
            {
                "owner",
                "reason",
                "impact",
                "safe_fallback",
                "next_task",
                "completion_condition",
            },
            {
                key
                for key in schema["required"]
                if key in {"owner", "reason", "impact", "safe_fallback", "next_task", "completion_condition"}
            },
        )
        self.assertEqual("SOFT", schema["properties"]["gate_kind"]["const"])
        self.assertEqual("FORGE_WORKFLOW_ONLY", schema["properties"]["authority_scope"]["const"])
        self.assertEqual("NONE", schema["properties"]["upstream_authority_effect"]["const"])
        for key in ("owner", "reason", "impact", "safe_fallback", "next_task", "completion_condition"):
            self.assertEqual(r"\S", schema["properties"][key]["pattern"])
        self.assertFalse(FORBIDDEN_AUTHORITY_FIELDS & _property_names(schema))


if __name__ == "__main__":
    unittest.main()
