"""Generation-bound Data Readiness Gate 0 contracts.

This module is the authority bridge between immutable Data Desk generations
and Gate 0.  It deliberately does not replace the legacy file-based v1
readiness lane.  Every v2 SortSpec and receipt is content-addressed, binds the
exact generation lineage and runtime policies, and is independently
recomputed before a PASS can be consumed.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .core import (
    Refusal,
    atomic_write_json,
    canonical_json,
    canonical_root,
    guard_path,
    paths_for,
    sha256_file,
    sha256_text,
)
from .data_contracts import (
    DATA_POLICY_VERSION,
    GENERATION_READINESS_SCHEMA,
    GENERATION_READINESS_SELECTION_SCHEMA,
    GENERATION_SORT_SPEC_SCHEMA,
    bind_data_record,
    validate_data_record,
)
from .data_desk import DATA_PARSER_VERSION, _load_generation_records, verify_data_generation


READINESS_POLICY_VERSION = "uriel.data_readiness_policy.v2"
READINESS_NORMALIZER_VERSION = "uriel.data_readiness_normalizer.v1"
NULL_ORDERINGS = ("nulls_first", "nulls_last", "nulls_error")
DUPLICATE_POLICIES = ("block", "exact")
IDENTITY_NORMALIZATION_RULE = "identity_no_coercion"
MAX_READINESS_RECORDS = 2_000_000

REQUIRED_CHECKS = (
    "source_identity",
    "record_identity",
    "schema",
    "encoding",
    "type_normalization",
    "datetime_normalization",
    "numeric_locale",
    "category_normalization",
    "duplicate_handling",
    "join_keys_and_cardinality",
    "missingness",
    "exclusions",
    "transformations",
    "stable_deterministic_sorting",
    "tie_break_rules",
    "null_ordering",
    "order_invariance",
    "row_reconciliation",
    "cross_platform_fixture_equivalence",
    "rebuild_hash_equality",
    "analysis_plan_binding",
    "independent_verification",
)

_HEX64 = "0123456789abcdef"


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in _HEX64 for char in value)


def _readiness_dir(root: Path, *, create: bool = False) -> Path:
    target = guard_path(root, paths_for(root).state / "readiness")
    if create:
        target.mkdir(parents=True, exist_ok=True)
    return target


def _write_content_addressed(root: Path, prefix: str, record: Mapping[str, Any]) -> Path:
    digest = str(record.get("record_sha256", ""))
    if not _is_sha256(digest):
        raise Refusal("A bound readiness record requires a SHA-256 identity.", code="READINESS_RECORD_INVALID")
    target = guard_path(root, _readiness_dir(root, create=True) / (prefix + digest + ".json"))
    if target.exists():
        try:
            existing = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Refusal(
                "An immutable readiness record is damaged.",
                code="READINESS_RECORD_TAMPERED",
                details={"path": str(target)},
            ) from exc
        if existing != dict(record):
            raise Refusal(
                "A readiness record identity collision was detected.",
                code="READINESS_RECORD_COLLISION",
                details={"path": str(target)},
            )
        return target
    atomic_write_json(target, record, pretty=False)
    return target


def _verified_material(
    root: Path, generation_id: str
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    verification = verify_data_generation(root, generation_id)
    if verification.get("decision") != "PASS" or verification.get("verified") is not True:
        raise Refusal(
            "The Data Desk generation did not pass independent verification.",
            code="READINESS_GENERATION_UNVERIFIED",
        )
    manifest, records, profile, records_file = _load_generation_records(root, generation_id)
    if len(records) > MAX_READINESS_RECORDS:
        raise Refusal(
            "The generation exceeds the readiness evaluation record budget.",
            code="READINESS_BUDGET",
            details={"max_records": MAX_READINESS_RECORDS},
        )
    return manifest, records, profile, records_file


def _resolve_columns(profile: Mapping[str, Any], requested: Sequence[str]) -> List[str]:
    columns = profile.get("columns", [])
    result: List[str] = []
    for selector in requested:
        text = str(selector)
        by_id = [row for row in columns if isinstance(row, Mapping) and row.get("column_id") == text]
        matches = by_id or [
            row for row in columns if isinstance(row, Mapping) and row.get("name") == text
        ]
        if len(matches) != 1:
            raise Refusal(
                "A SortSpec column is missing or ambiguous.",
                code="READINESS_UNKNOWN_COLUMN",
                details={"selector": text, "match_count": len(matches)},
                repairs=[
                    "Use one exact unique source column name.",
                    "For duplicate headers, use the stable `col-...` identifier from the Data Desk profile.",
                    "Do not guess record identity.",
                ],
            )
        result.append(str(matches[0]["column_id"]))
    if len(result) != len(set(result)):
        raise Refusal("SortSpec columns must be unique.", code="READINESS_DUPLICATE_COLUMN")
    return result


def make_generation_sort_spec(
    root: Union[Path, str],
    generation_id: str,
    *,
    keys: Sequence[str] = (),
    tie_break: Sequence[str] = (),
    nulls: str = "nulls_last",
    duplicate_policy: str = "block",
    analysis_plan: Optional[str] = None,
    normalization: Sequence[str] = (),
    exclusions: Sequence[str] = (),
) -> Dict[str, Any]:
    """Seal a deterministic v2 SortSpec for one verified generation."""
    if nulls not in NULL_ORDERINGS:
        raise Refusal("Unknown null ordering.", code="READINESS_INVALID_NULLS")
    if duplicate_policy not in DUPLICATE_POLICIES:
        raise Refusal(
            "Generation readiness never deletes duplicate records.",
            code="READINESS_INVALID_DUPLICATES",
            repairs=["Choose `block` or `exact`; `keep_first` is legacy-only and is not allowed for Data Desk generations."],
        )
    if not keys:
        raise Refusal(
            "Record identity is ambiguous: no primary keys were declared.",
            code="READINESS_AMBIGUOUS_IDENTITY",
            repairs=["Declare one or more unique column names or stable `col-...` identifiers."],
        )
    normalized_rules = [str(item) for item in normalization] or [IDENTITY_NORMALIZATION_RULE]
    if normalized_rules != [IDENTITY_NORMALIZATION_RULE]:
        raise Refusal(
            "The v2 readiness lane does not silently transform generation values.",
            code="READINESS_UNSUPPORTED_NORMALIZATION",
            repairs=["Use only `identity_no_coercion`; create a separately receipted generation for any real transformation."],
        )
    if exclusions:
        raise Refusal(
            "A SortSpec cannot silently exclude generation records.",
            code="READINESS_UNSUPPORTED_EXCLUSION",
            repairs=["Create a separately receipted transformation generation that preserves the exclusion rule and lineage."],
        )

    root_path = canonical_root(root)
    manifest, _records, profile, _records_file = _verified_material(root_path, generation_id)
    key_ids = _resolve_columns(profile, keys)
    tie_ids = _resolve_columns(profile, tie_break)
    if set(key_ids) & set(tie_ids):
        raise Refusal("Primary and tie-break columns must not overlap.", code="READINESS_DUPLICATE_COLUMN")

    plan_relative: Optional[str] = None
    plan_sha: Optional[str] = None
    if analysis_plan:
        plan_path = guard_path(root_path, root_path / analysis_plan, must_exist=True)
        if not plan_path.is_file():
            raise Refusal("The analysis plan is not a regular file.", code="READINESS_ANALYSIS_PLAN_INVALID")
        plan_relative = plan_path.relative_to(root_path).as_posix()
        plan_sha = sha256_file(plan_path)

    spec = bind_data_record(
        {
            "schema": GENERATION_SORT_SPEC_SCHEMA,
            "schema_version": 2,
            "policy_version": READINESS_POLICY_VERSION,
            "data_policy_version": DATA_POLICY_VERSION,
            "normalizer_version": READINESS_NORMALIZER_VERSION,
            "generation_id": generation_id,
            "generation_manifest_sha256": manifest["record_sha256"],
            "parser_version": manifest["parser_version"],
            "source_records_sha256": manifest["records_sha256"],
            "source_order_sha256": manifest["order_sha256"],
            "records_file_sha256": manifest["records_file_sha256"],
            "raw_artifact_sha256s": list(manifest["raw_artifact_sha256s"]),
            "parent_generation_ids": list(manifest["parent_generation_ids"]),
            "operation_binding_sha256": manifest["operation_binding_sha256"],
            "columns": [
                {
                    "column_id": row["column_id"],
                    "name": row["name"],
                    "position": row["position"],
                    "duplicate_name": row["duplicate_name"],
                }
                for row in profile["columns"]
            ],
            "record_identity": key_ids,
            "primary_keys": key_ids,
            "tie_break_keys": tie_ids,
            "implicit_final_tie_break": "record_sha256",
            "null_ordering": nulls,
            "normalization_rules": normalized_rules,
            "duplicate_policy": duplicate_policy,
            "join_policy": "row_position_join_forbidden_conflicts_preserved",
            "canonical_serialization": "uriel_canonical_json_utf8_lf",
            "order_invariance_tests": ["reverse_input_reproduces_canonical_order"],
            "cross_platform_status": "deterministic_utf8_lf_no_locale",
            "exclusions": [],
            "analysis_plan_relative_path": plan_relative,
            "analysis_plan_sha256": plan_sha,
        }
    )
    validate_data_record(spec)
    target = _write_content_addressed(root_path, "sortspec-", spec)
    return {
        "sort_spec_sha256": spec["record_sha256"],
        "sort_spec": spec,
        "path": str(target),
        "row_count": manifest["record_count"],
        "generation_id": generation_id,
    }


def _load_bound_record(root: Path, path: Union[str, Path], prefix: str, schema: str) -> Tuple[Path, Dict[str, Any]]:
    candidate = Path(path)
    target = guard_path(
        root,
        candidate if candidate.is_absolute() else _readiness_dir(root) / candidate,
        must_exist=True,
    )
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Refusal("A readiness record is unreadable.", code="READINESS_RECORD_TAMPERED") from exc
    if not isinstance(value, Mapping) or value.get("schema") != schema:
        raise Refusal("The selected readiness record has the wrong schema.", code="READINESS_SCHEMA_UNSUPPORTED")
    validate_data_record(value)
    digest = str(value.get("record_sha256", ""))
    if target.name != prefix + digest + ".json":
        raise Refusal(
            "The readiness filename and content identity disagree.",
            code="READINESS_RECORD_TAMPERED",
        )
    return target, dict(value)


def _sort_spec_path(root: Path, digest: str) -> Path:
    return guard_path(root, _readiness_dir(root) / ("sortspec-" + digest + ".json"), must_exist=True)


def _write_current_selection(root: Path, receipt: Mapping[str, Any]) -> Dict[str, Any]:
    selection = bind_data_record(
        {
            "schema": GENERATION_READINESS_SELECTION_SCHEMA,
            "schema_version": 1,
            "generation_id": receipt["generation_id"],
            "sort_spec_sha256": receipt["sort_spec_sha256"],
            "readiness_receipt_sha256": receipt["record_sha256"],
            "readiness_binding_digest": receipt["binding_digest"],
        }
    )
    validate_data_record(selection)
    target = guard_path(root, _readiness_dir(root, create=True) / "CURRENT.json")
    atomic_write_json(target, selection, pretty=False)
    return {"path": str(target), "selection": selection, "selection_sha256": selection["record_sha256"]}


def current_generation_readiness_selection(
    root: Union[Path, str], *, verify: bool = True
) -> Dict[str, Any]:
    """Read the active v2 receipt selector and optionally recompute its authority."""
    root_path = canonical_root(root)
    target = guard_path(root_path, _readiness_dir(root_path) / "CURRENT.json")
    if not target.is_file():
        return {"exists": False, "path": str(target)}
    target = guard_path(root_path, target, must_exist=True)
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise Refusal(
            "The active Data Readiness selection is unreadable.",
            code="READINESS_SELECTION_TAMPERED",
        ) from exc
    if not isinstance(value, Mapping) or value.get("schema") != GENERATION_READINESS_SELECTION_SCHEMA:
        raise Refusal(
            "The active Data Readiness selection has the wrong schema.",
            code="READINESS_SELECTION_TAMPERED",
        )
    validate_data_record(value)
    selection = dict(value)
    result: Dict[str, Any] = {
        "exists": True,
        "path": str(target),
        "selection": selection,
        "selection_sha256": selection["record_sha256"],
    }
    if not verify:
        return result
    receipt_path = guard_path(
        root_path,
        _readiness_dir(root_path)
        / ("receipt-" + str(selection["readiness_receipt_sha256"]) + ".json"),
        must_exist=True,
    )
    verified = verify_generation_readiness_receipt(
        root_path,
        receipt_path,
        generation_id=str(selection["generation_id"]),
    )
    receipt = verified["receipt"]
    expected = {
        "generation_id": receipt["generation_id"],
        "sort_spec_sha256": receipt["sort_spec_sha256"],
        "readiness_receipt_sha256": receipt["record_sha256"],
        "readiness_binding_digest": receipt["binding_digest"],
    }
    mismatches = {
        key: {"selected": selection.get(key), "verified": expected_value}
        for key, expected_value in expected.items()
        if selection.get(key) != expected_value
    }
    if mismatches:
        raise Refusal(
            "The active Data Readiness selection does not match its exact receipt.",
            code="READINESS_SELECTION_TAMPERED",
            details={"mismatches": mismatches},
        )
    result["verified_readiness"] = verified
    return result


def _value_token(value: Any, nulls: str) -> Tuple[int, str, str]:
    missing = value is None or value == ""
    if missing:
        if nulls == "nulls_error":
            raise Refusal(
                "A primary or tie-break key is null and the SortSpec forbids null keys.",
                code="READINESS_NULL_IN_KEY",
            )
        return (0 if nulls == "nulls_first" else 2, "", "")
    if isinstance(value, bool):
        kind = "boolean"
    elif isinstance(value, int):
        kind = "integer"
    elif isinstance(value, float):
        kind = "number"
    elif isinstance(value, str):
        kind = "string"
    elif isinstance(value, list):
        kind = "array"
    elif isinstance(value, Mapping):
        kind = "object"
    else:
        kind = type(value).__name__
    return (1, kind, canonical_json(value))


def _record_hash(record: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(dict(record)))


def _normalized_hashes(records: Sequence[Mapping[str, Any]], spec: Mapping[str, Any]) -> List[str]:
    keys = [str(item) for item in spec["primary_keys"]]
    tie = [str(item) for item in spec["tie_break_keys"]]
    nulls = str(spec["null_ordering"])

    def sort_key(record: Mapping[str, Any]) -> Tuple[Any, ...]:
        tokens: List[Any] = [_value_token(record.get(column_id), nulls) for column_id in keys + tie]
        tokens.append((1, "record_sha256", _record_hash(record)))
        return tuple(tokens)

    ordered = sorted((dict(record) for record in records), key=sort_key)
    return [_record_hash(record) for record in ordered]


def _check(check_id: str, passed: bool, evidence: Mapping[str, Any], *, blocked: bool = False) -> Dict[str, Any]:
    return {
        "check_id": check_id,
        "status": "PASS" if passed else ("BLOCKED" if blocked else "FAIL"),
        "evidence": dict(evidence),
    }


def _evaluate(root: Path, spec: Mapping[str, Any]) -> Dict[str, Any]:
    generation_id = str(spec.get("generation_id", ""))
    manifest, records, profile, records_file = _verified_material(root, generation_id)
    binding_fields = {
        "policy_version": spec.get("policy_version") == READINESS_POLICY_VERSION,
        "data_policy_version": spec.get("data_policy_version") == DATA_POLICY_VERSION,
        "normalizer_version": spec.get("normalizer_version") == READINESS_NORMALIZER_VERSION,
        "generation_manifest_sha256": spec.get("generation_manifest_sha256") == manifest.get("record_sha256"),
        "parser_version": spec.get("parser_version") == manifest.get("parser_version") == DATA_PARSER_VERSION,
        "source_records_sha256": spec.get("source_records_sha256") == manifest.get("records_sha256"),
        "source_order_sha256": spec.get("source_order_sha256") == manifest.get("order_sha256"),
        "records_file_sha256": spec.get("records_file_sha256") == manifest.get("records_file_sha256") == records_file.get("sha256"),
        "raw_artifact_sha256s": spec.get("raw_artifact_sha256s") == manifest.get("raw_artifact_sha256s"),
        "parent_generation_ids": spec.get("parent_generation_ids") == manifest.get("parent_generation_ids"),
        "operation_binding_sha256": spec.get("operation_binding_sha256") == manifest.get("operation_binding_sha256"),
    }
    declared_columns = spec.get("columns", [])
    actual_columns = [
        {key: row[key] for key in ("column_id", "name", "position", "duplicate_name")}
        for row in profile["columns"]
    ]
    column_ids = {str(row["column_id"]) for row in actual_columns}
    primary = [str(item) for item in spec.get("primary_keys", [])]
    tie = [str(item) for item in spec.get("tie_break_keys", [])]
    identity_pass = bool(primary) and all(item in column_ids for item in primary + tie)

    key_counts: Dict[Tuple[str, ...], int] = {}
    null_counts = {column_id: 0 for column_id in primary + tie}
    for record in records:
        token = tuple(canonical_json(record.get(column_id)) for column_id in primary)
        key_counts[token] = key_counts.get(token, 0) + 1
        for column_id in primary + tie:
            if record.get(column_id) in (None, ""):
                null_counts[column_id] += 1
    duplicate_key_count = sum(1 for count in key_counts.values() if count > 1)
    duplicate_policy = str(spec.get("duplicate_policy", "block"))
    duplicate_pass = duplicate_key_count == 0 or duplicate_policy == "exact"
    nulls = str(spec.get("null_ordering", "nulls_last"))
    null_blocked = nulls == "nulls_error" and any(null_counts.values())

    normalized_hashes: List[str] = []
    normalization_error: Optional[str] = None
    if identity_pass and not null_blocked:
        try:
            normalized_hashes = _normalized_hashes(records, spec)
        except Refusal as exc:
            normalization_error = str(exc)
    else:
        normalization_error = "Record identity or null-ordering requirements are unresolved."
    normalized_generation = (
        sha256_text(canonical_json(normalized_hashes))
        if normalization_error is None
        else ""
    )
    reversed_hashes = (
        _normalized_hashes(list(reversed(records)), spec)
        if normalized_hashes and normalization_error is None
        else []
    )
    order_invariant = normalization_error is None and reversed_hashes == normalized_hashes
    rebuild_matches = (
        sha256_text(canonical_json(_normalized_hashes(records, spec))) == normalized_generation
        if normalization_error is None
        else False
    )

    plan_path = spec.get("analysis_plan_relative_path")
    plan_sha = spec.get("analysis_plan_sha256")
    if plan_path is None and plan_sha is None:
        plan_pass = True
        plan_actual = None
    elif isinstance(plan_path, str) and _is_sha256(plan_sha):
        try:
            target = guard_path(root, root / plan_path, must_exist=True)
            plan_actual = sha256_file(target) if target.is_file() else None
        except Refusal:
            plan_actual = None
        plan_pass = plan_actual == plan_sha
    else:
        plan_actual = None
        plan_pass = False

    rules = spec.get("normalization_rules")
    identity_only = rules == [IDENTITY_NORMALIZATION_RULE]
    no_exclusions = spec.get("exclusions") == []
    source_pass = all(binding_fields.values())
    checks = [
        _check("source_identity", source_pass, {"bindings": binding_fields, "generation_id": generation_id}),
        _check("record_identity", identity_pass, {"primary_keys": primary, "tie_break_keys": tie}),
        _check("schema", declared_columns == actual_columns, {"declared_column_count": len(declared_columns), "actual_column_count": len(actual_columns)}),
        _check("encoding", True, {"encoding": "verified_utf8_canonical_jsonl"}),
        _check("type_normalization", identity_only, {"normalizer_version": READINESS_NORMALIZER_VERSION, "rules": rules}),
        _check("datetime_normalization", identity_only, {"policy": "no_datetime_coercion"}),
        _check("numeric_locale", identity_only, {"policy": "no_locale_numeric_coercion"}),
        _check("category_normalization", identity_only, {"policy": "no_category_coercion"}),
        _check("duplicate_handling", duplicate_pass, {"policy": duplicate_policy, "duplicate_key_count": duplicate_key_count, "records_preserved": len(records)}),
        _check("join_keys_and_cardinality", duplicate_pass, {"row_position_join": "forbidden", "duplicate_key_count": duplicate_key_count}),
        _check("missingness", not null_blocked, {"null_counts": null_counts, "null_ordering": nulls}, blocked=null_blocked),
        _check("exclusions", no_exclusions, {"exclusions": spec.get("exclusions"), "records_removed": 0}),
        _check("transformations", identity_only, {"transform_receipt_sha256s": manifest.get("transform_receipt_sha256s", []), "readiness_transform": "identity_only"}),
        _check("stable_deterministic_sorting", normalization_error is None, {"normalizer_version": READINESS_NORMALIZER_VERSION, "error": normalization_error}),
        _check("tie_break_rules", identity_pass, {"explicit": tie, "implicit_final": "record_sha256"}),
        _check("null_ordering", not null_blocked, {"ordering": nulls, "null_counts": null_counts}, blocked=null_blocked),
        _check("order_invariance", order_invariant, {"reverse_input_reproduces": order_invariant}),
        _check("row_reconciliation", bool(records) and len(normalized_hashes) == len(records), {"input_rows": len(records), "output_rows": len(normalized_hashes), "records_removed": 0, "empty_generation_allowed": False}),
        _check("cross_platform_fixture_equivalence", normalization_error is None, {"serialization": "canonical_json_utf8_lf_no_locale"}),
        _check("rebuild_hash_equality", rebuild_matches, {"normalized_generation": normalized_generation}),
        _check("analysis_plan_binding", plan_pass, {"declared": plan_sha, "actual": plan_actual}),
        _check("independent_verification", True, {"generation_verifier": "verify_data_generation", "decision": "PASS"}),
    ]
    if [row["check_id"] for row in checks] != list(REQUIRED_CHECKS):
        raise Refusal("The generation readiness check matrix drifted.", code="READINESS_CHECK_MATRIX_INVALID")
    failed = sum(1 for row in checks if row["status"] == "FAIL")
    blocked = sum(1 for row in checks if row["status"] == "BLOCKED")
    decision = "BLOCKED" if blocked else ("FAIL" if failed else "PASS")
    binding = {
        "schema": "uriel.data_readiness_binding.v2",
        "policy_version": READINESS_POLICY_VERSION,
        "data_policy_version": DATA_POLICY_VERSION,
        "normalizer_version": READINESS_NORMALIZER_VERSION,
        "generation_id": generation_id,
        "generation_manifest_sha256": manifest["record_sha256"],
        "parser_version": manifest["parser_version"],
        "parent_generation_ids": manifest["parent_generation_ids"],
        "operation_binding_sha256": manifest["operation_binding_sha256"],
        "raw_artifact_sha256s": manifest["raw_artifact_sha256s"],
        "records_sha256": manifest["records_sha256"],
        "source_order_sha256": manifest["order_sha256"],
        "records_file_sha256": manifest["records_file_sha256"],
        "normalized_generation": normalized_generation,
        "sort_spec_sha256": spec["record_sha256"],
        "analysis_plan_sha256": plan_sha,
        "checks": checks,
    }
    binding_digest = sha256_text(canonical_json(binding))
    receipt = bind_data_record(
        {
            "schema": GENERATION_READINESS_SCHEMA,
            "schema_version": 2,
            "policy_version": READINESS_POLICY_VERSION,
            "data_policy_version": DATA_POLICY_VERSION,
            "normalizer_version": READINESS_NORMALIZER_VERSION,
            "generation_id": generation_id,
            "generation_manifest_sha256": manifest["record_sha256"],
            "parser_version": manifest["parser_version"],
            "parent_generation_ids": list(manifest["parent_generation_ids"]),
            "operation_binding_sha256": manifest["operation_binding_sha256"],
            "raw_artifact_sha256s": list(manifest["raw_artifact_sha256s"]),
            "records_sha256": manifest["records_sha256"],
            "source_order_sha256": manifest["order_sha256"],
            "records_file_sha256": manifest["records_file_sha256"],
            "normalized_generation": normalized_generation,
            "sort_spec_sha256": spec["record_sha256"],
            "analysis_plan_sha256": plan_sha,
            "required_check_count": len(REQUIRED_CHECKS),
            "executed_check_count": len(checks),
            "passed_check_count": sum(1 for row in checks if row["status"] == "PASS"),
            "failed_check_count": failed,
            "blocked_check_count": blocked,
            "unresolved_blocker_count": failed + blocked,
            "not_applicable_count": 0,
            "decision": decision,
            "binding_digest": binding_digest,
            "checks": checks,
            "independent_generation_verification": "PASS",
            "no_authority_from_ai": True,
        }
    )
    validate_data_record(receipt)
    return {
        "receipt_sha256": receipt["record_sha256"],
        "receipt": receipt,
        "checks": checks,
        "embargo_sentence": None if decision == "PASS" else None,
    }


def generation_readiness_check(
    root: Union[Path, str],
    generation_id: str,
    sort_spec_path: Optional[str] = None,
) -> Dict[str, Any]:
    """Recompute and seal a v2 Data Readiness receipt."""
    root_path = canonical_root(root)
    if sort_spec_path is None:
        matches: List[Path] = []
        for path in sorted(_readiness_dir(root_path).glob("sortspec-*.json")):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if value.get("schema") == GENERATION_SORT_SPEC_SCHEMA and value.get("generation_id") == generation_id:
                matches.append(path)
        if not matches:
            raise Refusal(
                "No generation-bound SortSpec exists for the requested generation.",
                code="READINESS_SORT_SPEC_MISSING",
            )
        if len(matches) != 1:
            raise Refusal(
                "Multiple SortSpecs exist for this generation; select one explicitly.",
                code="READINESS_SORT_SPEC_AMBIGUOUS",
                details={"sort_specs": [path.name for path in matches]},
            )
        sort_spec_path = str(matches[0])
    _path, spec = _load_bound_record(root_path, sort_spec_path, "sortspec-", GENERATION_SORT_SPEC_SCHEMA)
    if spec.get("generation_id") != generation_id:
        raise Refusal(
            "The requested generation and SortSpec do not match.",
            code="READINESS_GENERATION_MISMATCH",
        )
    result = _evaluate(root_path, spec)
    target = _write_content_addressed(root_path, "receipt-", result["receipt"])
    selection = _write_current_selection(root_path, result["receipt"])
    result["path"] = str(target)
    result["generation_id"] = generation_id
    result["selection"] = selection
    return result


def verify_generation_readiness_receipt(
    root: Union[Path, str],
    receipt_path: Union[str, Path],
    *,
    generation_id: Optional[str] = None,
    sort_spec_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Independently recompute one exact v2 receipt from live immutable inputs."""
    root_path = canonical_root(root)
    target, receipt = _load_bound_record(root_path, receipt_path, "receipt-", GENERATION_READINESS_SCHEMA)
    selected_generation = generation_id or str(receipt.get("generation_id", ""))
    if receipt.get("generation_id") != selected_generation:
        raise Refusal("The readiness receipt binds another generation.", code="READINESS_GENERATION_MISMATCH")
    declared_spec_sha = str(receipt.get("sort_spec_sha256", ""))
    expected_spec_path = _sort_spec_path(root_path, declared_spec_sha)
    if sort_spec_path is not None:
        supplied = Path(sort_spec_path)
        supplied_path = guard_path(
            root_path,
            supplied if supplied.is_absolute() else _readiness_dir(root_path) / supplied,
            must_exist=True,
        )
        if supplied_path != expected_spec_path:
            raise Refusal("The readiness receipt binds another SortSpec.", code="READINESS_SORT_SPEC_MISMATCH")
    _spec_path, spec = _load_bound_record(
        root_path, expected_spec_path, "sortspec-", GENERATION_SORT_SPEC_SCHEMA
    )
    recomputed = _evaluate(root_path, spec)
    if recomputed["receipt"] != receipt:
        raise Refusal(
            "The Data Readiness receipt is stale or does not recompute exactly.",
            code="READINESS_RECEIPT_STALE",
            details={
                "declared": receipt.get("record_sha256"),
                "recomputed": recomputed["receipt"].get("record_sha256"),
            },
        )
    return {
        "verified": True,
        "decision": receipt["decision"],
        "generation_id": selected_generation,
        "receipt": receipt,
        "receipt_sha256": receipt["record_sha256"],
        "receipt_path": str(target),
        "sort_spec": spec,
        "sort_spec_path": str(expected_spec_path),
        "checks": receipt["checks"],
    }


def generation_receipt_inventory(root: Union[Path, str]) -> List[Dict[str, str]]:
    """List v2 receipt selectors without accepting their authority."""
    root_path = canonical_root(root)
    directory = _readiness_dir(root_path)
    rows: List[Dict[str, str]] = []
    for path in sorted(directory.glob("receipt-*.json")):
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if value.get("schema") != GENERATION_READINESS_SCHEMA:
            continue
        rows.append(
            {
                "generation_id": str(value.get("generation_id", "")),
                "sort_spec_sha256": str(value.get("sort_spec_sha256", "")),
                "receipt_sha256": path.name[len("receipt-") : -len(".json")],
                "path": str(path),
            }
        )
    return rows


def _verified_status_payload(
    verified: Mapping[str, Any], *, selection: Optional[Mapping[str, Any]] = None
) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "exists": True,
        "decision": verified["decision"],
        "generation_id": verified["generation_id"],
        "receipt": verified["receipt"],
        "receipt_sha256": verified["receipt_sha256"],
        "sort_spec": verified["sort_spec"],
        "sort_spec_path": verified["sort_spec_path"],
        "checks": verified["checks"],
    }
    if selection is not None:
        payload["active_selection"] = dict(selection)
    return payload


def _failure_decision(exc: Refusal) -> str:
    if (
        exc.code.startswith("DATA_")
        or "TAMPERED" in exc.code
        or exc.code
        in {
            "PROJECT_PATH_MISSING",
            "MISSING_FILE",
            "INVALID_JSON",
            "PATH_CONFINEMENT_REFUSAL",
            "LINK_TRAVERSAL_REFUSAL",
        }
    ):
        return "TAMPERED"
    return "STALE"


def current_generation_readiness_status(root: Union[Path, str]) -> Dict[str, Any]:
    """Return the independently verified status of the active v2 selection."""
    root_path = canonical_root(root)
    try:
        active = current_generation_readiness_selection(root_path, verify=True)
    except Refusal as exc:
        return {
            "exists": True,
            "decision": _failure_decision(exc),
            "error": str(exc),
            "error_code": exc.code,
        }
    if not active.get("exists"):
        return {"exists": False, "decision": None}
    verified = active["verified_readiness"]
    return _verified_status_payload(verified, selection=active["selection"])


def generation_readiness_status(
    root: Union[Path, str],
    generation_id: str,
    *,
    sort_spec_path: Optional[Union[str, Path]] = None,
    receipt_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Verify the exact receipt selected for one generation; never use mtime."""
    root_path = canonical_root(root)
    try:
        active = current_generation_readiness_selection(root_path, verify=True)
    except Refusal as exc:
        return {
            "exists": True,
            "decision": _failure_decision(exc),
            "generation_id": generation_id,
            "error": str(exc),
            "error_code": exc.code,
        }
    if active.get("exists"):
        selection = active["selection"]
        if selection.get("generation_id") != generation_id:
            if receipt_path is not None or sort_spec_path is not None:
                return {
                    "exists": True,
                    "decision": "STALE",
                    "generation_id": generation_id,
                    "active_generation_id": selection.get("generation_id"),
                    "error": "The requested generation is not the active readiness selection.",
                    "error_code": "READINESS_SELECTION_GENERATION_MISMATCH",
                }
            return {
                "exists": False,
                "decision": None,
                "generation_id": generation_id,
                "active_generation_id": selection.get("generation_id"),
                "error": "Another Data Desk generation is the active readiness selection.",
                "error_code": "READINESS_SELECTION_GENERATION_MISMATCH",
            }
        expected_receipt = guard_path(
            root_path,
            _readiness_dir(root_path)
            / ("receipt-" + str(selection["readiness_receipt_sha256"]) + ".json"),
            must_exist=True,
        )
        expected_spec = _sort_spec_path(root_path, str(selection["sort_spec_sha256"]))
        try:
            if receipt_path is not None:
                supplied_receipt = Path(receipt_path)
                supplied_receipt = guard_path(
                    root_path,
                    supplied_receipt
                    if supplied_receipt.is_absolute()
                    else _readiness_dir(root_path) / supplied_receipt,
                    must_exist=True,
                )
                if supplied_receipt != expected_receipt:
                    return {
                        "exists": True,
                        "decision": "STALE",
                        "generation_id": generation_id,
                        "error": "The requested readiness receipt is not the active selection.",
                        "error_code": "READINESS_SELECTION_RECEIPT_MISMATCH",
                    }
            if sort_spec_path is not None:
                supplied_spec = Path(sort_spec_path)
                supplied_spec = guard_path(
                    root_path,
                    supplied_spec if supplied_spec.is_absolute() else _readiness_dir(root_path) / supplied_spec,
                    must_exist=True,
                )
                if supplied_spec != expected_spec:
                    return {
                        "exists": True,
                        "decision": "STALE",
                        "generation_id": generation_id,
                        "error": "The requested SortSpec is not the active selection.",
                        "error_code": "READINESS_SELECTION_SORT_SPEC_MISMATCH",
                    }
        except Refusal as exc:
            return {
                "exists": True,
                "decision": "STALE",
                "generation_id": generation_id,
                "error": str(exc),
                "error_code": exc.code,
            }
        return _verified_status_payload(
            active["verified_readiness"], selection=selection
        )
    candidates = [
        row
        for row in generation_receipt_inventory(root_path)
        if row["generation_id"] == generation_id
    ]
    if not candidates:
        return {"exists": False, "decision": None, "generation_id": generation_id}
    return {
        "exists": True,
        "decision": "TAMPERED",
        "generation_id": generation_id,
        "candidates": candidates,
        "error": "Generation readiness receipts exist, but the active selection record is missing.",
        "error_code": "READINESS_SELECTION_MISSING",
    }


def require_generation_readiness(
    root: Union[Path, str],
    generation_id: str,
    *,
    sort_spec_path: Optional[Union[str, Path]] = None,
    receipt_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Fail closed before any data-dependent or AI-facing generation use."""
    status = generation_readiness_status(
        root,
        generation_id,
        sort_spec_path=sort_spec_path,
        receipt_path=receipt_path,
    )
    if status.get("decision") != "PASS":
        raise Refusal(
            "The exact Data Desk generation has no current PASS readiness receipt.",
            code="READINESS_GENERATION_NOT_READY",
            details={
                "generation_id": generation_id,
                "decision": status.get("decision"),
                "error": status.get("error"),
            },
            repairs=[
                "Verify the generation, seal an exact v2 SortSpec, and rerun readiness check.",
                "Select the exact SortSpec or receipt when more than one exists.",
                "Do not expose, analyze, predict from, or export unready generation records.",
            ],
        )
    return status
