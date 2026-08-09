"""Versioned Evidence Ingress and Data Desk contracts.

This module owns schema discovery, canonical record binding, safe source
inspection, and privacy-preserving no-write plans. Runtime intake and derived
generation behavior remain isolated in ``data_ingress`` and ``data_desk``.
"""
from __future__ import annotations

import codecs
import hashlib
import json
import os
import re
import stat
import time
from importlib import resources
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Mapping, Optional, Tuple, Union

from .core import (
    Refusal,
    canonical_json,
    canonical_root,
    guard_path,
    paths_for,
    safe_relative_path,
    sha256_file,
    sha256_text,
    utc_now,
)


DATA_POLICY_VERSION = "uriel.data_policy.v1"
DATA_IMPORT_PLAN_SCHEMA_V1 = "uriel.data_import_plan.v1"
DATA_IMPORT_PLAN_SCHEMA = "uriel.data_import_plan.v2"
DATA_IMPORT_RECEIPT_SCHEMA = "uriel.data_import_receipt.v1"
RAW_ARTIFACT_SCHEMA = "uriel.raw_artifact.v1"
DATA_DELTA_ENTRY_SCHEMA = "uriel.data_delta_entry.v1"
DATA_GENERATION_SCHEMA_V1 = "uriel.data_generation_manifest.v1"
DATA_GENERATION_SCHEMA = "uriel.data_generation_manifest.v2"
DATA_PROFILE_SCHEMA_V1 = "uriel.data_profile.v1"
DATA_PROFILE_SCHEMA = "uriel.data_profile.v2"
DATA_TRANSFORM_SCHEMA = "uriel.data_transform_receipt.v1"
DATA_RECONCILIATION_SCHEMA_V1 = "uriel.data_reconciliation.v1"
DATA_RECONCILIATION_SCHEMA = "uriel.data_reconciliation.v2"
DATA_REFUSAL_SCHEMA = "uriel.data_refusal.v1"
RESOURCE_BUDGET_SCHEMA_V1 = "uriel.resource_budget.v1"
RESOURCE_BUDGET_SCHEMA = "uriel.resource_budget.v2"
DATA_VERIFICATION_SCHEMA = "uriel.data_verification_receipt.v1"
GENERATION_SORT_SPEC_SCHEMA = "uriel.sort_spec.v2"
GENERATION_READINESS_SCHEMA = "uriel.data_readiness.v2"
GENERATION_READINESS_SELECTION_SCHEMA = "uriel.data_readiness_selection.v1"

DATA_IMPORT_PLAN_SCHEMAS = frozenset({DATA_IMPORT_PLAN_SCHEMA_V1, DATA_IMPORT_PLAN_SCHEMA})

DATA_SCHEMA_FILES: Mapping[str, str] = {
    DATA_IMPORT_PLAN_SCHEMA_V1: "uriel.data_import_plan.v1.schema.json",
    DATA_IMPORT_PLAN_SCHEMA: "uriel.data_import_plan.v2.schema.json",
    DATA_IMPORT_RECEIPT_SCHEMA: "uriel.data_import_receipt.v1.schema.json",
    RAW_ARTIFACT_SCHEMA: "uriel.raw_artifact.v1.schema.json",
    DATA_DELTA_ENTRY_SCHEMA: "uriel.data_delta_entry.v1.schema.json",
    DATA_GENERATION_SCHEMA_V1: "uriel.data_generation_manifest.v1.schema.json",
    DATA_GENERATION_SCHEMA: "uriel.data_generation_manifest.v2.schema.json",
    DATA_PROFILE_SCHEMA_V1: "uriel.data_profile.v1.schema.json",
    DATA_PROFILE_SCHEMA: "uriel.data_profile.v2.schema.json",
    DATA_TRANSFORM_SCHEMA: "uriel.data_transform_receipt.v1.schema.json",
    DATA_RECONCILIATION_SCHEMA_V1: "uriel.data_reconciliation.v1.schema.json",
    DATA_RECONCILIATION_SCHEMA: "uriel.data_reconciliation.v2.schema.json",
    DATA_REFUSAL_SCHEMA: "uriel.data_refusal.v1.schema.json",
    RESOURCE_BUDGET_SCHEMA_V1: "uriel.resource_budget.v1.schema.json",
    RESOURCE_BUDGET_SCHEMA: "uriel.resource_budget.v2.schema.json",
    DATA_VERIFICATION_SCHEMA: "uriel.data_verification_receipt.v1.schema.json",
    GENERATION_SORT_SPEC_SCHEMA: "uriel.sort_spec.v2.schema.json",
    GENERATION_READINESS_SCHEMA: "uriel.data_readiness.v2.schema.json",
    GENERATION_READINESS_SELECTION_SCHEMA: "uriel.data_readiness_selection.v1.schema.json",
}

SUPPORTED_LOCAL_FORMATS: Mapping[str, Tuple[str, str]] = {
    ".csv": ("CSV", "text/csv"),
    ".tsv": ("TSV", "text/tab-separated-values"),
    ".json": ("JSON", "application/json"),
    ".jsonl": ("JSONL", "application/x-ndjson"),
    ".txt": ("UTF8_TEXT", "text/plain"),
    ".md": ("MARKDOWN", "text/markdown"),
}

DEFAULT_MAX_SOURCE_BYTES = 100 * 1024 * 1024
DEFAULT_MAX_RECORDS = 1_000_000
DEFAULT_MAX_COLUMNS = 10_000
DEFAULT_MAX_NESTING_DEPTH = 64
DEFAULT_MAX_FIELD_BYTES = 1024 * 1024
DEFAULT_TIMEOUT_SECONDS = 60
MAX_RECORD_FILE_BYTES = 4 * 1024 * 1024
_REPARSE_POINT = 0x400
_LABEL_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def bind_data_record(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Return a content-addressed record using Uriel canonical JSON."""

    value = dict(record)
    value.pop("record_sha256", None)
    value["record_sha256"] = sha256_text(canonical_json(value))
    return value


def _schema_resource(schema_id: str):
    filename = DATA_SCHEMA_FILES.get(schema_id)
    if filename is None:
        raise Refusal(
            "Unknown Data Desk schema: {0}".format(schema_id),
            code="DATA_SCHEMA_UNKNOWN",
            details={"schema": schema_id},
            repairs=[
                "Use one of the versioned schema IDs returned by the Data Desk contract catalog.",
                "Do not guess or silently upgrade an unknown schema version.",
                "Preserve the record and install a Uriel version that explicitly supports it.",
            ],
        )
    return resources.files("uriel.schemas").joinpath(filename)


def load_data_schema(schema_id: str) -> Dict[str, Any]:
    """Load one packaged Data Desk JSON Schema by exact schema ID."""

    try:
        value = json.loads(_schema_resource(schema_id).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal(
            "The packaged Data Desk schema could not be read.",
            code="DATA_SCHEMA_UNREADABLE",
            details={"schema": schema_id, "error": str(exc)},
        ) from exc
    if not isinstance(value, dict):
        raise Refusal("The packaged Data Desk schema is not an object.", code="DATA_SCHEMA_UNREADABLE")
    return value


def data_contract_catalog() -> List[Dict[str, str]]:
    """Return deterministic packaged-schema inventory and byte hashes."""

    rows: List[Dict[str, str]] = []
    for schema_id in sorted(DATA_SCHEMA_FILES):
        resource = _schema_resource(schema_id)
        raw = resource.read_bytes()
        rows.append(
            {
                "schema": schema_id,
                "resource": DATA_SCHEMA_FILES[schema_id],
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
        )
    return rows


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    return False


def _validate_schema_node(value: Any, rule: Mapping[str, Any], pointer: str, errors: List[str]) -> None:
    expected = rule.get("type")
    if expected is not None:
        allowed = [expected] if isinstance(expected, str) else list(expected)
        if not any(_type_matches(value, str(item)) for item in allowed):
            errors.append("{0}: expected {1}".format(pointer, " or ".join(str(item) for item in allowed)))
            return

    if "const" in rule and value != rule["const"]:
        errors.append("{0}: must equal {1!r}".format(pointer, rule["const"]))
    if "enum" in rule and value not in rule["enum"]:
        errors.append("{0}: unsupported value {1!r}".format(pointer, value))

    if isinstance(value, Mapping):
        required = [str(item) for item in rule.get("required", [])]
        for key in required:
            if key not in value:
                errors.append("{0}/{1}: required field is missing".format(pointer, key))
        properties = rule.get("properties", {})
        if isinstance(properties, Mapping):
            if rule.get("additionalProperties") is False:
                for key in value:
                    if key not in properties:
                        errors.append("{0}/{1}: unknown field".format(pointer, key))
            for key, child in properties.items():
                if key in value and isinstance(child, Mapping):
                    _validate_schema_node(value[key], child, "{0}/{1}".format(pointer, key), errors)

    if isinstance(value, list):
        if len(value) < int(rule.get("minItems", 0)):
            errors.append("{0}: too few items".format(pointer))
        if "maxItems" in rule and len(value) > int(rule["maxItems"]):
            errors.append("{0}: too many items".format(pointer))
        if rule.get("uniqueItems"):
            rendered = [canonical_json(item) for item in value]
            if len(rendered) != len(set(rendered)):
                errors.append("{0}: duplicate items are forbidden".format(pointer))
        item_rule = rule.get("items")
        if isinstance(item_rule, Mapping):
            for index, item in enumerate(value):
                _validate_schema_node(item, item_rule, "{0}/{1}".format(pointer, index), errors)

    if isinstance(value, str):
        if len(value) < int(rule.get("minLength", 0)):
            errors.append("{0}: string is too short".format(pointer))
        if "maxLength" in rule and len(value) > int(rule["maxLength"]):
            errors.append("{0}: string is too long".format(pointer))
        pattern = rule.get("pattern")
        if pattern is not None and re.search(str(pattern), value) is None:
            errors.append("{0}: does not match the required pattern".format(pointer))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in rule and value < rule["minimum"]:
            errors.append("{0}: below minimum".format(pointer))
        if "maximum" in rule and value > rule["maximum"]:
            errors.append("{0}: above maximum".format(pointer))


def _hash_error(record: Mapping[str, Any], pointer: str = "$") -> Optional[str]:
    body = dict(record)
    supplied = str(body.pop("record_sha256", ""))
    calculated = sha256_text(canonical_json(body))
    if supplied != calculated:
        return "{0}/record_sha256: digest mismatch".format(pointer)
    return None


def _relative_path_errors(value: Any, pointer: str, errors: List[str]) -> None:
    if isinstance(value, Mapping):
        for key, child in value.items():
            child_pointer = "{0}/{1}".format(pointer, key)
            if key.endswith("_relative_path") and isinstance(child, str):
                try:
                    safe_relative_path(child)
                except Refusal:
                    errors.append("{0}: unsafe project-relative path".format(child_pointer))
            _relative_path_errors(child, child_pointer, errors)
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _relative_path_errors(child, "{0}/{1}".format(pointer, index), errors)


def validate_data_record(record: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate structure, exact version, unknown fields, paths, and hash binding."""

    if not isinstance(record, Mapping):
        raise Refusal("A Data Desk record must be one JSON object.", code="DATA_RECORD_OBJECT_REQUIRED")
    schema_id = str(record.get("schema", ""))
    schema = load_data_schema(schema_id)
    errors: List[str] = []
    _validate_schema_node(record, schema, "$", errors)
    digest_error = _hash_error(record)
    if digest_error:
        errors.append(digest_error)
    _relative_path_errors(record, "$", errors)

    if schema_id in DATA_IMPORT_PLAN_SCHEMAS:
        budget = record.get("resource_budget")
        if isinstance(budget, Mapping):
            budget_schema_id = str(budget.get("schema", ""))
            _validate_schema_node(budget, load_data_schema(budget_schema_id), "$/resource_budget", errors)
            budget_hash_error = _hash_error(budget, "$/resource_budget")
            if budget_hash_error:
                errors.append(budget_hash_error)
    elif schema_id == DATA_IMPORT_RECEIPT_SCHEMA:
        if record.get("source_content_sha256") != record.get("copied_content_sha256"):
            errors.append("$: copied content hash must equal the selected source hash")
        if record.get("outcome") == "COPIED":
            if record.get("source_size_bytes") != record.get("bytes_copied"):
                errors.append("$: a copied artifact must report the selected source size as bytes_copied")
        elif record.get("outcome") == "REFERENCED" and record.get("bytes_copied") != 0:
            errors.append("$: a referenced artifact must report zero newly copied bytes")
    elif schema_id == DATA_RECONCILIATION_SCHEMA:
        if record.get("preserved_conflict_count") != record.get("conflict_count"):
            errors.append("$: every conflicting record must remain preserved")
        has_result = record.get("result_generation_id") is not None
        if has_result != (record.get("result_records_sha256") is not None):
            errors.append("$: result generation and result records hash must be present or absent together")
        if not has_result and record.get("result_record_count") != 0:
            errors.append("$: a read-only reconciliation preview must report zero result records")
        if has_result != (record.get("delta_ledger_relative_path") is not None):
            errors.append("$: only a persisted reconciliation result may bind a delta-ledger path")
    elif schema_id == DATA_DELTA_ENTRY_SCHEMA:
        if record.get("exact_counterpart_count", 0) > record.get("counterpart_count", 0):
            errors.append("$: exact counterpart count cannot exceed total counterpart count")
        if record.get("classification") == "UNKNOWN" and record.get("key_sha256") is not None:
            errors.append("$: a missing-key UNKNOWN entry must not claim a key hash")
    elif schema_id == DATA_GENERATION_SCHEMA:
        decisions = record.get("parser_decisions")
        if isinstance(decisions, Mapping):
            columns = decisions.get("columns")
            if isinstance(columns, list) and record.get("column_count") != len(columns):
                errors.append("$: column_count must equal the parser decision column set")
            if isinstance(columns, list):
                column_ids = [row.get("column_id") for row in columns if isinstance(row, Mapping)]
                positions = [row.get("position") for row in columns if isinstance(row, Mapping)]
                if len(column_ids) != len(set(column_ids)):
                    errors.append("$/parser_decisions/columns: column IDs must be unique")
                if positions != list(range(len(columns))):
                    errors.append("$/parser_decisions/columns: positions must be contiguous source order")
                for annotation in record.get("user_confirmed_annotations", []):
                    if isinstance(annotation, Mapping) and annotation.get("column_id") not in set(column_ids):
                        errors.append("$/user_confirmed_annotations: annotation column is not in the generation")
            expected_decisions = {
                "CSV": "DELIMITED_UTF8_COMMA_QUOTE_DOUBLEQUOTE_STRICT_HEADER_ROW_1",
                "TSV": "DELIMITED_UTF8_TAB_QUOTE_DOUBLEQUOTE_STRICT_HEADER_ROW_1",
                "JSON": "JSON_UTF8_OBJECT_OR_OBJECT_ARRAY_SORTED_COLUMNS_DUPLICATE_KEYS_REFUSED",
                "JSONL": "JSONL_UTF8_OBJECT_PER_NONBLANK_LINE_SORTED_COLUMNS_DUPLICATE_KEYS_REFUSED",
                "UTF8_TEXT": "UTF8_TEXT_ONE_RECORD_PER_PHYSICAL_LINE",
                "MARKDOWN": "UTF8_MARKDOWN_ONE_RECORD_PER_PHYSICAL_LINE_NO_RENDER",
                "RECONCILED": "PRESERVE_LEFT_ORDER_THEN_RIGHT_ORDER_NO_COERCION",
            }
            if decisions.get("format_decision") != expected_decisions.get(record.get("format")):
                errors.append("$/parser_decisions/format_decision: decision does not match the declared format")
        if record.get("format") == "RECONCILED":
            if len(record.get("parent_generation_ids", [])) != 2 or record.get("reconciliation_sha256") is None:
                errors.append("$: a reconciled generation requires two ordered parents and a reconciliation binding")
            if record.get("operation_binding_sha256") is None:
                errors.append("$: a reconciled generation requires an operation identity binding")
        elif record.get("reconciliation_sha256") is not None:
            errors.append("$: only a reconciled generation may carry a reconciliation binding")
        elif record.get("parent_generation_ids") or record.get("operation_binding_sha256") is not None:
            errors.append("$: a source generation must not claim parents or an operation binding")
        expected_index = ".uriel/data/indexes/{0}.sqlite".format(record.get("generation_id"))
        if record.get("derived_index_relative_path") != expected_index:
            errors.append("$/derived_index_relative_path: index path must bind the generation ID")
    elif schema_id == DATA_PROFILE_SCHEMA:
        columns = record.get("columns")
        if isinstance(columns, list):
            column_id_list = [row.get("column_id") for row in columns if isinstance(row, Mapping)]
            column_ids = set(column_id_list)
            positions = [row.get("position") for row in columns if isinstance(row, Mapping)]
            if len(column_id_list) != len(column_ids):
                errors.append("$/columns: column IDs must be unique")
            if positions != list(range(len(columns))):
                errors.append("$/columns: positions must be contiguous source order")
            for candidate in record.get("candidate_keys", []):
                if candidate not in column_ids:
                    errors.append("$/candidate_keys: candidate key is not a profiled column")
            for annotation in record.get("user_confirmed_annotations", []):
                if isinstance(annotation, Mapping) and annotation.get("column_id") not in column_ids:
                    errors.append("$/user_confirmed_annotations: annotation column is not profiled")
            for row in columns:
                if isinstance(row, Mapping) and isinstance(record.get("row_count"), int):
                    if row.get("null_count", 0) > record["row_count"]:
                        errors.append("$/columns: null_count cannot exceed row_count")
    elif schema_id == DATA_VERIFICATION_SCHEMA:
        if record.get("decision") == "PASS" and record.get("errors"):
            errors.append("$: a PASS verification receipt cannot contain errors")
    elif schema_id == GENERATION_SORT_SPEC_SCHEMA:
        columns = record.get("columns", [])
        column_ids = [row.get("column_id") for row in columns if isinstance(row, Mapping)]
        positions = [row.get("position") for row in columns if isinstance(row, Mapping)]
        primary = list(record.get("primary_keys", []))
        tie_break = list(record.get("tie_break_keys", []))
        if len(column_ids) != len(set(column_ids)):
            errors.append("$/columns: stable column IDs must be unique")
        if positions != list(range(len(columns))):
            errors.append("$/columns: positions must be contiguous source order")
        if record.get("record_identity") != primary:
            errors.append("$/record_identity: must exactly equal primary_keys")
        if any(item not in set(column_ids) for item in primary + tie_break):
            errors.append("$: primary and tie-break keys must reference declared stable columns")
        if set(primary) & set(tie_break):
            errors.append("$: primary and tie-break keys must not overlap")
        has_plan_path = record.get("analysis_plan_relative_path") is not None
        has_plan_hash = record.get("analysis_plan_sha256") is not None
        if has_plan_path != has_plan_hash:
            errors.append("$: analysis plan path and hash must be present or absent together")
    elif schema_id == GENERATION_READINESS_SCHEMA:
        checks = record.get("checks", [])
        check_ids = [row.get("check_id") for row in checks if isinstance(row, Mapping)]
        statuses = [row.get("status") for row in checks if isinstance(row, Mapping)]
        passed = sum(1 for value in statuses if value == "PASS")
        failed = sum(1 for value in statuses if value == "FAIL")
        blocked = sum(1 for value in statuses if value == "BLOCKED")
        if record.get("executed_check_count") != len(checks):
            errors.append("$/executed_check_count: must equal the check matrix length")
        if len(check_ids) != len(set(check_ids)):
            errors.append("$/checks: every mandatory check ID must appear exactly once")
        if record.get("passed_check_count") != passed:
            errors.append("$/passed_check_count: does not match checks")
        if record.get("failed_check_count") != failed:
            errors.append("$/failed_check_count: does not match checks")
        if record.get("blocked_check_count") != blocked:
            errors.append("$/blocked_check_count: does not match checks")
        if record.get("unresolved_blocker_count") != failed + blocked:
            errors.append("$/unresolved_blocker_count: must equal failed plus blocked checks")
        expected_decision = "BLOCKED" if blocked else ("FAIL" if failed else "PASS")
        if record.get("decision") != expected_decision:
            errors.append("$/decision: does not match the recomputed check counts")

    if errors:
        raise Refusal(
            "Data contract validation failed.",
            code="DATA_CONTRACT_INVALID",
            details={"schema": schema_id, "errors": errors},
            repairs=[
                "Correct the listed fields without changing the declared schema version.",
                "Recompute record_sha256 over canonical JSON without the record_sha256 field.",
                "Preserve the rejected record and rerun `uriel data verify-record` after repair.",
            ],
        )
    return {
        "valid": True,
        "schema": schema_id,
        "schema_version": record.get("schema_version"),
        "record_sha256": record.get("record_sha256"),
        "schema_resource": DATA_SCHEMA_FILES[schema_id],
    }


def make_resource_budget(
    *,
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    max_records: int = DEFAULT_MAX_RECORDS,
    max_columns: int = DEFAULT_MAX_COLUMNS,
    max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
    max_field_bytes: int = DEFAULT_MAX_FIELD_BYTES,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Build and validate the versioned local resource ceiling."""

    budget = bind_data_record(
        {
            "schema": RESOURCE_BUDGET_SCHEMA,
            "schema_version": 2,
            "policy_version": DATA_POLICY_VERSION,
            "max_source_bytes": max_source_bytes,
            "max_records": max_records,
            "max_columns": max_columns,
            "max_nesting_depth": max_nesting_depth,
            "max_field_bytes": max_field_bytes,
            "timeout_seconds": timeout_seconds,
        }
    )
    validate_data_record(budget)
    return budget


def _same_file_identity(before: os.stat_result, opened: os.stat_result) -> bool:
    before_identity = (getattr(before, "st_dev", 0), getattr(before, "st_ino", 0))
    opened_identity = (getattr(opened, "st_dev", 0), getattr(opened, "st_ino", 0))
    identity_matches = True
    if before_identity != (0, 0) and opened_identity != (0, 0):
        identity_matches = before_identity == opened_identity
    return bool(
        identity_matches
        and before.st_size == opened.st_size
        and before.st_mtime_ns == opened.st_mtime_ns
    )


def _path_contains_indirection(path: Path) -> bool:
    """Return true when any lexical source-path component is a link/reparse point."""

    absolute = Path(os.path.abspath(str(path)))
    parts = absolute.parts
    if not parts:
        return True
    current = Path(parts[0])
    for part in parts[1:]:
        current = current / part
        try:
            observed = os.lstat(str(current))
        except OSError:
            continue
        if stat.S_ISLNK(observed.st_mode):
            return True
        if bool(getattr(observed, "st_file_attributes", 0) & _REPARSE_POINT):
            return True
    return False


def inspect_selected_source(
    source: Union[str, Path],
    max_source_bytes: int,
    timeout_seconds: int,
    destination: Optional[BinaryIO] = None,
) -> Dict[str, Any]:
    """Stream and validate one selected UTF-8 source, optionally copying bytes.

    The source is opened once without following the selected leaf, hashed while
    it is decoded, and checked for identity drift before and after the stream.
    A supplied destination receives the exact blocks included in the digest.
    """

    raw_source = os.fspath(source)
    if raw_source.startswith(("\\\\", "//")) or "://" in raw_source:
        raise Refusal(
            "Evidence Ingress planning accepts a local filesystem path, not a network, device, or URI source.",
            code="DATA_NETWORK_PATH_REFUSED",
        )
    path = Path(raw_source).expanduser()
    if _path_contains_indirection(path):
        raise Refusal(
            "Evidence Ingress refused a link or reparse point in the selected source path.",
            code="DATA_SOURCE_TYPE_REFUSED",
        )
    try:
        observed = os.lstat(str(path))
    except OSError as exc:
        raise Refusal(
            "The selected local source could not be inspected.",
            code="DATA_SOURCE_UNREADABLE",
            details={"error_type": type(exc).__name__},
        ) from exc

    is_reparse = bool(getattr(observed, "st_file_attributes", 0) & _REPARSE_POINT)
    if stat.S_ISLNK(observed.st_mode) or is_reparse or not stat.S_ISREG(observed.st_mode):
        raise Refusal(
            "Evidence Ingress accepts one regular file; links, directories, devices, sockets, and pipes are refused.",
            code="DATA_SOURCE_TYPE_REFUSED",
            details={"regular_file": stat.S_ISREG(observed.st_mode), "link_or_reparse": is_reparse or stat.S_ISLNK(observed.st_mode)},
            repairs=[
                "Select one explicit regular file rather than a directory, link, archive, device, socket, or pipe.",
                "Create a separate immutable regular-file export and select that export explicitly.",
                "Keep the source unchanged and wait for a separately specified adapter with dedicated tests.",
            ],
        )

    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_LOCAL_FORMATS:
        raise Refusal(
            "The selected format is outside the initial local Data Desk contract.",
            code="DATA_FORMAT_UNSUPPORTED",
            details={"suffix": suffix or "<none>"},
            repairs=[
                "Select CSV, TSV, JSON, JSONL, UTF-8 text, or Markdown.",
                "Export the source into one supported lossless text format and preserve that transform separately.",
                "Wait for a separately bounded adapter; do not rename an unsupported file to bypass detection.",
            ],
        )
    if observed.st_size > max_source_bytes:
        raise Refusal(
            "The selected source exceeds the declared resource budget.",
            code="DATA_RESOURCE_BUDGET",
            details={"size_bytes": observed.st_size, "max_source_bytes": max_source_bytes},
        )

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(str(path), flags)
    except OSError as exc:
        raise Refusal(
            "The selected source could not be opened without following unsafe indirection.",
            code="DATA_SOURCE_UNREADABLE",
            details={"error_type": type(exc).__name__},
        ) from exc

    digest = hashlib.sha256()
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    opened: Optional[os.stat_result] = None
    started = time.monotonic()
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode) or not _same_file_identity(observed, opened):
                raise Refusal("The selected source changed while it was being opened.", code="DATA_SOURCE_CHANGED")
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                if time.monotonic() - started > timeout_seconds:
                    raise Refusal(
                        "Source inspection exceeded the declared resource timeout.",
                        code="DATA_RESOURCE_TIMEOUT",
                        details={"timeout_seconds": timeout_seconds},
                    )
                digest.update(block)
                decoder.decode(block)
                if destination is not None:
                    destination.write(block)
            decoder.decode(b"", final=True)
    except UnicodeDecodeError as exc:
        raise Refusal(
            "The selected source is not valid UTF-8.",
            code="DATA_ENCODING_REFUSED",
            details={"error": str(exc)},
            repairs=[
                "Export the file as UTF-8 while preserving the original separately.",
                "Record the encoding conversion as a future transform receipt.",
                "Do not replace undecodable bytes silently.",
            ],
        ) from exc

    assert opened is not None
    try:
        after = os.lstat(str(path))
    except OSError as exc:
        raise Refusal("The selected source disappeared during inspection.", code="DATA_SOURCE_CHANGED") from exc
    if not _same_file_identity(observed, after) or opened.st_size != after.st_size:
        raise Refusal("The selected source changed during inspection.", code="DATA_SOURCE_CHANGED")

    format_name, media_type = SUPPORTED_LOCAL_FORMATS[suffix]
    return {
        "content_sha256": digest.hexdigest(),
        "size_bytes": after.st_size,
        "format": format_name,
        "media_type": media_type,
        "encoding": "utf-8",
    }


def plan_data_import(
    root: Union[str, Path],
    source: Union[str, Path],
    *,
    label: str = "",
    max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES,
    max_records: int = DEFAULT_MAX_RECORDS,
    max_columns: int = DEFAULT_MAX_COLUMNS,
    max_nesting_depth: int = DEFAULT_MAX_NESTING_DEPTH,
    max_field_bytes: int = DEFAULT_MAX_FIELD_BYTES,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Create a no-write plan for one explicit local regular file."""

    root_path = canonical_root(root)
    project_paths = paths_for(root_path)
    budget = make_resource_budget(
        max_source_bytes=max_source_bytes,
        max_records=max_records,
        max_columns=max_columns,
        max_nesting_depth=max_nesting_depth,
        max_field_bytes=max_field_bytes,
        timeout_seconds=timeout_seconds,
    )
    source_observation = inspect_selected_source(source, max_source_bytes, timeout_seconds)
    logical_label = label or "source-{0}".format(source_observation["content_sha256"][:12])
    if _LABEL_PATTERN.fullmatch(logical_label) is None:
        raise Refusal(
            "The logical source label is invalid.",
            code="DATA_LABEL_INVALID",
            repairs=[
                "Use 1-128 ASCII letters, digits, dots, underscores, or hyphens.",
                "Omit --label to use a path-free hash-derived label.",
                "Keep local directory and account names out of public labels.",
            ],
        )

    plan = bind_data_record(
        {
            "schema": DATA_IMPORT_PLAN_SCHEMA,
            "schema_version": 2,
            "created_at_utc": utc_now(),
            "policy_version": DATA_POLICY_VERSION,
            "project_binding_sha256": sha256_file(project_paths.project),
            "operation": "MANAGED_COPY",
            "mode": "DRY_RUN",
            "consent": "EXPLICIT_USER_SELECTION",
            "source": {
                "logical_label": logical_label,
                "content_sha256": source_observation["content_sha256"],
                "size_bytes": source_observation["size_bytes"],
                "media_type": source_observation["media_type"],
                "format": source_observation["format"],
                "encoding": source_observation["encoding"],
                "access_condition": "USER_SELECTED_LOCAL_REGULAR_FILE",
                "location_disclosure": "PRIVATE_EPHEMERAL",
            },
            "resource_budget": budget,
            "planned_raw_artifact_schema": RAW_ARTIFACT_SCHEMA,
            "writes_performed": False,
            "network_permitted": False,
        }
    )
    validation = validate_data_record(plan)
    return {
        "plan": plan,
        "validation": validation,
        "writes_performed": False,
        "source_path_disclosed": False,
        "next_step": "Save the exact plan record, review it, then run `uriel data import` with the same selected source.",
    }


def verify_data_record_file(root: Union[str, Path], record_path: str) -> Dict[str, Any]:
    """Verify one project-relative Data Desk record without changing state."""

    root_path = canonical_root(root)
    paths_for(root_path)
    relative = safe_relative_path(record_path)
    target = guard_path(root_path, root_path / relative, must_exist=True)
    if not target.is_file() or target.stat().st_size > MAX_RECORD_FILE_BYTES:
        raise Refusal(
            "The record must be one bounded regular JSON file.",
            code="DATA_RECORD_FILE_REFUSED",
            details={"max_bytes": MAX_RECORD_FILE_BYTES},
        )
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal(
            "The selected Data Desk record is not valid UTF-8 JSON.",
            code="DATA_RECORD_UNREADABLE",
            details={"error": str(exc)},
        ) from exc
    if not isinstance(value, dict):
        raise Refusal("A Data Desk record must contain one JSON object.", code="DATA_RECORD_OBJECT_REQUIRED")
    result = validate_data_record(value)
    result["record_relative_path"] = relative.as_posix()
    return result
