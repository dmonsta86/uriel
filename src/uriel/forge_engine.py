"""Deterministic, local-only Forge snapshot engine and independent verifier.

Forge records coordinate work.  They never grant Data Readiness, research
gate, publication, verifier, Blessing, or Earned Wings authority.  Every
write is an immutable content-addressed snapshot beneath ignored `.uriel/`
state; readers enforce bounded strict JSON, lineage, filesystem confinement,
and live reference bindings without invoking a network, model, or process.
"""
from __future__ import annotations

import copy
import datetime as _dt
import hashlib
import json
import math
import os
import re
import stat
import uuid
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, MutableMapping, Optional, Sequence, Set, Tuple, Union

from .core import (
    Refusal,
    canonical_json,
    canonical_json_bytes,
    guard_path,
    is_reparse_or_link,
    load_project,
    paths_for,
    pretty_json,
    sha256_bytes,
    sha256_text,
    utc_now,
)
from .gate_contract import validate_gate_decision


RUN_SCHEMA = "uriel.forge_run.v1"
RUN_SCHEMA_FILE = "uriel.forge_run.v1.schema.json"
DEFERRAL_SCHEMA = "uriel.forge_deferral.v1"
DEFERRAL_SCHEMA_FILE = "uriel.forge_deferral.v1.schema.json"
INIT_REQUEST_SCHEMA = "uriel.forge_init_request.v1"
TRANSITION_REQUEST_SCHEMA = "uriel.forge_transition_request.v1"
FORGE_ROOT = Path(".uriel/forge/runs")
MAX_RUN_BYTES = 4 * 1024 * 1024
MAX_REQUEST_BYTES = 1024 * 1024
MAX_JSON_DEPTH = 64
MAX_LINEAGE_RECORDS = 4096
MAX_TYPED_JSON_BYTES = 16 * 1024 * 1024
MAX_TOTAL_REFERENCE_BYTES = 1024 * 1024 * 1024
_REPARSE_POINT = 0x400
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_RUN_ID = re.compile(r"^forge-[0-9a-f]{16}$")
_SNAPSHOT_NAME = re.compile(r"^(?P<revision>[0-9]{6,7})-(?P<digest>[0-9a-f]{64})[.]json$")
_RELATIVE_PATH = re.compile(
    r"^(?![.]{1,2}(?:/|$))(?!.*(?:/)[.]{1,2}(?:/|$))(?!.*\\)(?!.*:)"
    r"[^/\x00-\x1f\x7f]+(?:/[^/\x00-\x1f\x7f]+)*$"
)

STATES = (
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
)

TRANSITIONS: Dict[str, Tuple[str, ...]] = {
    "DRAFT": ("SCOPED", "BLOCKED", "FAILED", "STALE", "SUPERSEDED", "ABORTED"),
    "SCOPED": ("AUDITED", "BLOCKED", "FAILED", "STALE", "SUPERSEDED", "ABORTED"),
    "AUDITED": ("IMPLEMENTING", "BLOCKED", "FAILED", "STALE", "SUPERSEDED", "ABORTED"),
    "IMPLEMENTING": ("VERIFYING", "BLOCKED", "FAILED", "STALE", "SUPERSEDED", "ABORTED"),
    "VERIFYING": (
        "IMPLEMENTING",
        "READY_FOR_INDEPENDENT_VERIFY",
        "BLOCKED",
        "FAILED",
        "STALE",
        "SUPERSEDED",
        "ABORTED",
    ),
    "READY_FOR_INDEPENDENT_VERIFY": (
        "IMPLEMENTING",
        "VERIFYING",
        "COMPLETE",
        "COMPLETE_WITH_DEFERRED_SOFT_GATES",
        "BLOCKED",
        "FAILED",
        "STALE",
        "SUPERSEDED",
        "ABORTED",
    ),
    "COMPLETE": ("STALE", "SUPERSEDED"),
    "COMPLETE_WITH_DEFERRED_SOFT_GATES": ("STALE", "SUPERSEDED"),
    "BLOCKED": (
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
    ),
    "FAILED": (),
    "STALE": (),
    "SUPERSEDED": (),
    "ABORTED": (),
}

STATE_OUTCOME = {
    "DRAFT": "OPEN",
    "SCOPED": "OPEN",
    "AUDITED": "OPEN",
    "IMPLEMENTING": "OPEN",
    "VERIFYING": "OPEN",
    "READY_FOR_INDEPENDENT_VERIFY": "OPEN",
    "COMPLETE": "FORGE_COMPLETE",
    "COMPLETE_WITH_DEFERRED_SOFT_GATES": "FORGE_COMPLETE_WITH_DEFERRED_SOFT_GATES",
    "BLOCKED": "FORGE_BLOCKED",
    "FAILED": "FORGE_FAILED",
    "STALE": "FORGE_STALE",
    "SUPERSEDED": "FORGE_STALE",
    "ABORTED": "FORGE_ABORTED",
}

EVENT_KIND_FOR_TARGET = {
    "DRAFT": "RESUME",
    "SCOPED": "SCOPE",
    "AUDITED": "AUDIT",
    "IMPLEMENTING": "IMPLEMENTATION",
    "VERIFYING": "VERIFICATION",
    "READY_FOR_INDEPENDENT_VERIFY": "INDEPENDENT_VERIFICATION",
    "COMPLETE": "CLOSE",
    "COMPLETE_WITH_DEFERRED_SOFT_GATES": "CLOSE",
    "BLOCKED": "BLOCK",
    "FAILED": "FAIL",
    "STALE": "STALE",
    "SUPERSEDED": "SUPERSEDE",
    "ABORTED": "ABORT",
}

REFERENCE_ROLES = frozenset(
    {
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
    }
)

FORBIDDEN_AUTHORITY_FIELDS = frozenset(
    {
        "blessed",
        "blessing_status",
        "gate_pass",
        "gate_status",
        "publication_ready",
        "publication_status",
        "verified",
        "verifier_status",
        "earned_wings",
        "authority_granted",
    }
)

WORK_PACKAGE_TRANSITIONS: Dict[str, Set[str]] = {
    "PROPOSED": {"PROPOSED", "READY", "BLOCKED", "DEFERRED", "SUPERSEDED"},
    "READY": {"READY", "IN_PROGRESS", "BLOCKED", "DEFERRED", "SUPERSEDED"},
    "IN_PROGRESS": {"IN_PROGRESS", "VERIFYING", "BLOCKED", "DEFERRED", "SUPERSEDED"},
    "VERIFYING": {"VERIFYING", "IN_PROGRESS", "COMPLETE", "BLOCKED", "DEFERRED", "SUPERSEDED"},
    "COMPLETE": {"COMPLETE", "SUPERSEDED"},
    "BLOCKED": {"BLOCKED", "READY", "IN_PROGRESS", "VERIFYING", "DEFERRED", "SUPERSEDED"},
    "DEFERRED": {"DEFERRED", "READY", "SUPERSEDED"},
    "SUPERSEDED": {"SUPERSEDED"},
}


def _refusal(message: str, code: str, **details: Any) -> Refusal:
    return Refusal(
        message,
        code=code,
        details=details,
        repairs=(
            "Use the exact content-addressed Forge snapshot and project-relative regular files.",
            "Correct the refused record or transition request, then create a new immutable revision.",
            "Run `uriel forge verify` and keep the refusal code with the project evidence.",
        ),
    )


def _json_equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    if isinstance(left, bool) or isinstance(right, bool):
        return isinstance(left, bool) and isinstance(right, bool) and left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return not isinstance(left, bool) and not isinstance(right, bool) and left == right
    if isinstance(left, str) or isinstance(right, str):
        return isinstance(left, str) and isinstance(right, str) and left == right
    if isinstance(left, list) or isinstance(right, list):
        return (
            isinstance(left, list)
            and isinstance(right, list)
            and len(left) == len(right)
            and all(_json_equal(a, b) for a, b in zip(left, right))
        )
    if isinstance(left, Mapping) or isinstance(right, Mapping):
        return (
            isinstance(left, Mapping)
            and isinstance(right, Mapping)
            and set(left) == set(right)
            and all(_json_equal(left[key], right[key]) for key in left)
        )
    return False


def _assert_json_depth(value: Any, maximum: int = MAX_JSON_DEPTH) -> None:
    stack: List[Tuple[Any, int]] = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        if depth > maximum:
            raise _refusal("Forge JSON exceeds the nesting ceiling.", "FORGE_SCHEMA_MISMATCH")
        if isinstance(current, Mapping):
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in current)


def _strict_json_loads(raw: bytes, *, code: str = "FORGE_SCHEMA_MISMATCH") -> Dict[str, Any]:
    def pairs(rows: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
        value: Dict[str, Any] = {}
        for key, child in rows:
            if key in value:
                raise ValueError("duplicate JSON key")
            value[key] = child
        return value

    def constant(_: str) -> Any:
        raise ValueError("non-finite JSON number")

    try:
        text = raw.decode("utf-8")
        value = json.loads(text, object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise _refusal("Forge requires strict UTF-8 JSON with unique keys and finite numbers.", code) from exc
    if not isinstance(value, dict):
        raise _refusal("A Forge record or request must contain one JSON object.", code)
    _assert_json_depth(value)
    return value


def _safe_relative(value: Any, *, code: str = "FORGE_REF_PATH_UNSAFE") -> str:
    if not isinstance(value, str) or not _RELATIVE_PATH.fullmatch(value):
        raise _refusal("Forge refused an unsafe or non-portable project-relative path.", code)
    return value


def _same_identity(first: os.stat_result, second: os.stat_result) -> bool:
    first_identity = (getattr(first, "st_dev", None), getattr(first, "st_ino", None))
    second_identity = (getattr(second, "st_dev", None), getattr(second, "st_ino", None))
    if first_identity[1] not in (None, 0) and second_identity[1] not in (None, 0):
        return first_identity == second_identity
    return (
        first.st_mode == second.st_mode
        and first.st_size == second.st_size
        and getattr(first, "st_mtime_ns", None) == getattr(second, "st_mtime_ns", None)
    )


def _read_regular_bounded(
    root: Path,
    relative: str,
    *,
    maximum: int,
    collect: bool,
    missing_code: str = "FORGE_REF_MISSING",
    invalid_code: str = "FORGE_REF_PATH_UNSAFE",
) -> Tuple[bytes, str, int, Tuple[Any, Any]]:
    portable = _safe_relative(relative, code=invalid_code)
    try:
        target = guard_path(root, portable, must_exist=True)
    except Refusal as exc:
        code = missing_code if exc.code in {"PROJECT_PATH_MISSING", "MISSING_FILE"} else invalid_code
        raise _refusal("Forge could not open the confined project-relative regular file.", code) from exc
    try:
        before = os.lstat(str(target))
    except OSError as exc:
        raise _refusal("A Forge reference is missing.", missing_code) from exc
    is_reparse = bool(getattr(before, "st_file_attributes", 0) & _REPARSE_POINT)
    if stat.S_ISLNK(before.st_mode) or is_reparse or not stat.S_ISREG(before.st_mode):
        raise _refusal("Forge references must be regular files, never links or reparse points.", invalid_code)
    if before.st_size > maximum:
        raise _refusal(
            "A Forge file exceeds the bounded operation ceiling.",
            "FORGE_RESOURCE_LIMIT",
            observed_bytes=int(before.st_size),
            maximum_bytes=maximum,
        )

    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(str(target), flags)
    except OSError as exc:
        raise _refusal("Forge could not open a stable regular-file descriptor.", invalid_code) from exc
    digest = hashlib.sha256()
    body = bytearray()
    size = 0
    opened: Optional[os.stat_result] = None
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            opened = os.fstat(handle.fileno())
            if not stat.S_ISREG(opened.st_mode) or not _same_identity(before, opened):
                raise _refusal("A Forge file changed identity while it was opened.", invalid_code)
            while True:
                block = handle.read(min(1024 * 1024, maximum - size + 1))
                if not block:
                    break
                size += len(block)
                if size > maximum:
                    raise _refusal("A Forge file exceeded its read ceiling.", "FORGE_RESOURCE_LIMIT")
                digest.update(block)
                if collect:
                    body.extend(block)
    finally:
        # fdopen owns the descriptor after successful construction.
        pass
    try:
        after = os.lstat(str(target))
    except OSError as exc:
        raise _refusal("A Forge file disappeared during verification.", missing_code) from exc
    if opened is None or not _same_identity(before, after) or not _same_identity(opened, after):
        raise _refusal("A Forge file changed during verification.", invalid_code)
    return bytes(body), digest.hexdigest(), size, (getattr(after, "st_dev", None), getattr(after, "st_ino", None))


@lru_cache(maxsize=1)
def _schema() -> Dict[str, Any]:
    resource = resources.files("uriel").joinpath("schemas").joinpath(RUN_SCHEMA_FILE)
    value = json.loads(resource.read_text(encoding="utf-8"))
    declared = {key: tuple(rows) for key, rows in value["x-uriel-state-transitions"].items()}
    if declared != TRANSITIONS or tuple(value["$defs"]["state"]["enum"]) != STATES:
        raise _refusal("The packaged Forge schema disagrees with the runtime transition contract.", "FORGE_SCHEMA_MISMATCH")
    return value


@lru_cache(maxsize=1)
def _deferral_schema() -> Dict[str, Any]:
    resource = resources.files("uriel").joinpath("schemas").joinpath(DEFERRAL_SCHEMA_FILE)
    return json.loads(resource.read_text(encoding="utf-8"))


def _type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, Mapping)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    return False


def _resolve_ref(root_schema: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        return {}
    current: Any = root_schema
    for raw in reference[2:].split("/"):
        key = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(current, Mapping) or key not in current:
            return {}
        current = current[key]
    return current if isinstance(current, Mapping) else {}


def _schema_issues(
    value: Any,
    rule: Mapping[str, Any],
    root_schema: Mapping[str, Any],
    pointer: str = "$",
) -> List[Tuple[str, str]]:
    issues: List[Tuple[str, str]] = []
    if "$ref" in rule:
        target = _resolve_ref(root_schema, str(rule["$ref"]))
        if not target:
            return [(pointer, "unresolved schema reference")]
        issues.extend(_schema_issues(value, target, root_schema, pointer))

    expected = rule.get("type")
    if expected is not None:
        allowed = [expected] if isinstance(expected, str) else list(expected)
        if not any(_type_matches(value, str(item)) for item in allowed):
            return [(pointer, "wrong JSON type")]
    if "const" in rule and not _json_equal(value, rule["const"]):
        issues.append((pointer, "constant mismatch"))
    if "enum" in rule and not any(_json_equal(value, item) for item in rule["enum"]):
        issues.append((pointer, "unsupported value"))

    if "oneOf" in rule:
        matches = [
            child
            for child in rule["oneOf"]
            if isinstance(child, Mapping) and not _schema_issues(value, child, root_schema, pointer)
        ]
        if len(matches) != 1:
            issues.append((pointer, "oneOf contract mismatch"))
    if "not" in rule and isinstance(rule["not"], Mapping):
        if not _schema_issues(value, rule["not"], root_schema, pointer):
            issues.append((pointer, "forbidden schema branch matched"))

    if isinstance(value, Mapping):
        required = rule.get("required", [])
        if isinstance(required, list):
            for key in required:
                if key not in value:
                    issues.append((pointer + "/" + str(key), "required field missing"))
        properties = rule.get("properties", {})
        if isinstance(properties, Mapping):
            if rule.get("additionalProperties") is False:
                for key in value:
                    if key not in properties:
                        issues.append((pointer + "/" + str(key), "unknown field"))
            for key, child in properties.items():
                if key in value and isinstance(child, Mapping):
                    issues.extend(_schema_issues(value[key], child, root_schema, pointer + "/" + str(key)))

    if isinstance(value, list):
        if len(value) < int(rule.get("minItems", 0)):
            issues.append((pointer, "too few items"))
        if "maxItems" in rule and len(value) > int(rule["maxItems"]):
            issues.append((pointer, "too many items"))
        if rule.get("uniqueItems"):
            rendered = [canonical_json(item) for item in value]
            if len(rendered) != len(set(rendered)):
                issues.append((pointer, "duplicate items"))
        item_rule = rule.get("items")
        if isinstance(item_rule, Mapping):
            for index, child in enumerate(value):
                issues.extend(_schema_issues(child, item_rule, root_schema, pointer + "/" + str(index)))

    if isinstance(value, str):
        if len(value) < int(rule.get("minLength", 0)):
            issues.append((pointer, "string too short"))
        if "maxLength" in rule and len(value) > int(rule["maxLength"]):
            issues.append((pointer, "string too long"))
        if "pattern" in rule and re.search(str(rule["pattern"]), value) is None:
            issues.append((pointer, "pattern mismatch"))
        if rule.get("format") == "date-time":
            try:
                parsed = _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None:
                    raise ValueError("timezone required")
            except ValueError:
                issues.append((pointer, "invalid date-time"))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in rule and value < rule["minimum"]:
            issues.append((pointer, "below minimum"))
        if "maximum" in rule and value > rule["maximum"]:
            issues.append((pointer, "above maximum"))

    for child in rule.get("allOf", []):
        if isinstance(child, Mapping):
            issues.extend(_schema_issues(value, child, root_schema, pointer))
    condition = rule.get("if")
    if isinstance(condition, Mapping) and not _schema_issues(value, condition, root_schema, pointer):
        then = rule.get("then")
        if isinstance(then, Mapping):
            issues.extend(_schema_issues(value, then, root_schema, pointer))
    elif isinstance(condition, Mapping):
        otherwise = rule.get("else")
        if isinstance(otherwise, Mapping):
            issues.extend(_schema_issues(value, otherwise, root_schema, pointer))
    return issues


def _scan_forbidden_fields(value: Any) -> None:
    stack = [value]
    while stack:
        current = stack.pop()
        if isinstance(current, Mapping):
            for key, child in current.items():
                if str(key).casefold() in FORBIDDEN_AUTHORITY_FIELDS:
                    raise _refusal(
                        "Forge refused a field that could impersonate upstream authority.",
                        "FORGE_FORBIDDEN_AUTHORITY_FIELD",
                        field=str(key),
                    )
                stack.append(child)
        elif isinstance(current, list):
            stack.extend(current)


def _record_digest(record: Mapping[str, Any]) -> str:
    body = dict(record)
    body.pop("record_sha256", None)
    return sha256_text(canonical_json(body))


def _component_digest(value: Any) -> str:
    return sha256_text(canonical_json(value))


def _manifest(record: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "requirement_count": len(record["requirements"]),
        "ref_count": len(record["refs"]),
        "work_package_count": len(record["work_packages"]),
        "requirements_sha256": _component_digest(record["requirements"]),
        "refs_sha256": _component_digest(record["refs"]),
        "work_packages_sha256": _component_digest(record["work_packages"]),
        "event_sha256": _component_digest(record["event"]),
    }


def _duplicates(rows: Sequence[Mapping[str, Any]], key: str) -> Set[str]:
    seen: Set[str] = set()
    repeated: Set[str] = set()
    for row in rows:
        value = str(row.get(key, ""))
        if value in seen:
            repeated.add(value)
        seen.add(value)
    return repeated


def _indexes(refs: Sequence[Mapping[str, Any]], closure_ref_ids: Sequence[str]) -> Dict[str, Any]:
    by_role: Dict[str, List[str]] = {}
    for row in refs:
        by_role.setdefault(str(row["role"]), []).append(str(row["ref_id"]))
    for rows in by_role.values():
        rows.sort()
    resume = by_role.get("RESUME_PACKET", [])
    return {
        "gate_ref_ids": by_role.get("GATE_DECISION", []),
        "blocker_ref_ids": by_role.get("GAP_REGISTER", []),
        "test_receipt_ref_ids": by_role.get("TEST_RECEIPT", []),
        "decision_ref_ids": sorted(
            by_role.get("DECISION", [])
            + by_role.get("DEFERRAL", [])
            + by_role.get("PUBLICATION_AUTHORITY", [])
        ),
        "evidence_ref_ids": sorted(
            by_role.get("PROJECT_MANIFEST", [])
            + by_role.get("SOURCE_MANIFEST", [])
            + by_role.get("WORKBENCH_GENERATION", [])
            + by_role.get("DATA_GENERATION", [])
            + by_role.get("READINESS_SELECTION", [])
            + by_role.get("AUDIT", [])
            + by_role.get("EVIDENCE", [])
        ),
        "closure_ref_ids": sorted(str(item) for item in closure_ref_ids),
        "next_ref_ids": resume,
        "resume_packet_ref_id": resume[0] if len(resume) == 1 else None,
    }


def _validate_graph(work_packages: Sequence[Mapping[str, Any]]) -> None:
    identifiers = {str(row["work_package_id"]) for row in work_packages}
    dependencies: Dict[str, Set[str]] = {}
    for row in work_packages:
        identifier = str(row["work_package_id"])
        deps = {str(item) for item in row["depends_on"]}
        if identifier in deps or not deps <= identifiers:
            raise _refusal("A Forge work package has an unknown or self dependency.", "FORGE_DEPENDENCY_UNKNOWN")
        dependencies[identifier] = deps
    remaining = {key: set(value) for key, value in dependencies.items()}
    ready = [key for key, value in remaining.items() if not value]
    visited = 0
    while ready:
        current = ready.pop()
        if current not in remaining:
            continue
        remaining.pop(current)
        visited += 1
        for key, deps in remaining.items():
            deps.discard(current)
            if not deps:
                ready.append(key)
    if visited != len(dependencies):
        raise _refusal("Forge refused a cyclic work-package dependency graph.", "FORGE_DEPENDENCY_CYCLE")


def _validate_relations(record: Mapping[str, Any]) -> None:
    requirements = record["requirements"]
    refs = record["refs"]
    packages = record["work_packages"]
    for rows, key in (
        (requirements, "requirement_id"),
        (refs, "ref_id"),
        (packages, "work_package_id"),
    ):
        if _duplicates(rows, key):
            raise _refusal("Forge identifiers must be unique within one run.", "FORGE_DUPLICATE_ID", field=key)
    paths = [str(row["path"]) for row in refs]
    if len(paths) != len(set(paths)):
        raise _refusal("A Forge snapshot cannot alias one path through multiple references.", "FORGE_DUPLICATE_ID")
    if sum(1 for row in refs if row["role"] == "PROJECT_MANIFEST") != 1:
        raise _refusal("A Forge run requires exactly one bound project-manifest reference.", "FORGE_PROJECT_BINDING_MISMATCH")
    for role in ("SOURCE_MANIFEST", "WORKBENCH_GENERATION", "READINESS_SELECTION", "RESUME_PACKET"):
        if sum(1 for row in refs if row["role"] == role) > 1:
            raise _refusal("A singleton Forge reference role was repeated.", "FORGE_DUPLICATE_ID", role=role)

    requirement_ids = {str(row["requirement_id"]) for row in requirements}
    ref_ids = {str(row["ref_id"]) for row in refs}
    package_ids = {str(row["work_package_id"]) for row in packages}
    for package in packages:
        if not set(package["requirement_ids"]) <= requirement_ids:
            raise _refusal("A work package cites an unknown requirement.", "FORGE_DEPENDENCY_UNKNOWN")
        if not set(package["input_ref_ids"]) <= ref_ids or not set(package["acceptance_ref_ids"]) <= ref_ids:
            raise _refusal("A work package cites an unknown reference.", "FORGE_REF_MISSING")
    event = record["event"]
    if not set(event["changed_work_package_ids"]) <= package_ids:
        raise _refusal("The Forge event cites an unknown changed work package.", "FORGE_DEPENDENCY_UNKNOWN")
    if not set(event["changed_ref_ids"]) <= ref_ids:
        raise _refusal("The Forge event cites an unknown changed reference.", "FORGE_REF_MISSING")
    if not set(record["result"]["closure_ref_ids"]) <= ref_ids:
        raise _refusal("Forge closure cites an unknown bound reference.", "FORGE_REF_MISSING")
    _validate_graph(packages)

    indexes = record["indexes"]
    if indexes != _indexes(refs, record["result"]["closure_ref_ids"]):
        raise _refusal("Forge reference indexes do not recompute from typed references.", "FORGE_SCHEMA_MISMATCH")
    if sorted(record["result"]["closure_ref_ids"]) != sorted(indexes["closure_ref_ids"]):
        raise _refusal("Forge closure references disagree across result and indexes.", "FORGE_SCHEMA_MISMATCH")

    state = str(record["state"])
    if record["result"]["outcome"] != STATE_OUTCOME[state]:
        raise _refusal("Forge state and result outcome disagree.", "FORGE_SCHEMA_MISMATCH")
    if event["to_state"] != state:
        raise _refusal("Forge event target and snapshot state disagree.", "FORGE_SCHEMA_MISMATCH")
    if record["authority_scope"] != "FORGE_WORKFLOW_ONLY" or record["upstream_authority_effect"] != "NONE":
        raise _refusal("Forge cannot claim upstream authority.", "FORGE_FORBIDDEN_AUTHORITY_FIELD")
    if len(record["indexes"]["gate_ref_ids"]) > 4:
        raise _refusal("A Forge run cannot index more than the four existing research gates.", "FORGE_DUPLICATE_ID")

    if state == "BLOCKED" and not indexes["blocker_ref_ids"] and not any(
        row["status"] == "BLOCKED" for row in packages
    ):
        raise _refusal("A BLOCKED Forge snapshot requires a typed blocker reference or blocked work package.", "FORGE_SCHEMA_MISMATCH")
    if state in {"FAILED", "STALE", "SUPERSEDED", "ABORTED"} and not record["result"]["summary"]:
        raise _refusal("A terminal Forge result requires a bounded summary.", "FORGE_SCHEMA_MISMATCH")

    if state in {"READY_FOR_INDEPENDENT_VERIFY", "COMPLETE", "COMPLETE_WITH_DEFERRED_SOFT_GATES"}:
        open_statuses = {"PROPOSED", "READY", "IN_PROGRESS", "VERIFYING", "BLOCKED"}
        if any(row["status"] in open_statuses for row in packages):
            raise _refusal("Forge cannot enter independent verification or closure with open work packages.", "FORGE_TRANSITION_REFUSED")
    deferred = [row for row in packages if row["status"] == "DEFERRED"]
    if deferred:
        ref_contracts = {
            str(row["ref_id"]): (str(row["role"]), row.get("record_schema"))
            for row in refs
        }
        if any(
            not any(
                ref_contracts.get(ref_id) == ("DEFERRAL", DEFERRAL_SCHEMA)
                for ref_id in row["acceptance_ref_ids"]
            )
            for row in deferred
        ):
            raise _refusal("Every deferred work package requires a typed DEFERRAL acceptance reference.", "FORGE_TRANSITION_REFUSED")
    if state == "COMPLETE" and any(row["status"] == "DEFERRED" for row in packages):
        raise _refusal("A COMPLETE Forge result cannot contain deferred work.", "FORGE_TRANSITION_REFUSED")
    if state == "COMPLETE_WITH_DEFERRED_SOFT_GATES":
        if not deferred:
            raise _refusal("Deferred-soft-gate closure requires at least one deferred work package.", "FORGE_TRANSITION_REFUSED")
        deferral_ids = {
            str(row["ref_id"])
            for row in refs
            if row["role"] == "DEFERRAL" and row.get("record_schema") == DEFERRAL_SCHEMA
        }
        if not deferral_ids <= set(record["result"]["closure_ref_ids"]):
            raise _refusal("Deferred-soft-gate closure must index every typed deferral record.", "FORGE_TRANSITION_REFUSED")
    if state in {"COMPLETE", "COMPLETE_WITH_DEFERRED_SOFT_GATES"}:
        covered: Set[str] = set()
        for row in packages:
            if row["status"] != "SUPERSEDED":
                covered.update(str(item) for item in row["requirement_ids"])
        if packages and covered != requirement_ids:
            raise _refusal("Forge closure does not cover every baseline requirement.", "FORGE_TRANSITION_REFUSED")


def _validate_structural(record: Mapping[str, Any]) -> None:
    if not isinstance(record, Mapping):
        raise _refusal("A Forge snapshot must be one JSON object.", "FORGE_SCHEMA_MISMATCH")
    _assert_json_depth(record)
    _scan_forbidden_fields(record)
    issues = _schema_issues(record, _schema(), _schema())
    if issues:
        code = "FORGE_UNKNOWN_FIELD" if any(message == "unknown field" for _, message in issues) else "FORGE_SCHEMA_MISMATCH"
        raise _refusal(
            "Forge snapshot does not satisfy the closed v1 contract.",
            code,
            issue_count=len(issues),
            first_pointer=issues[0][0],
            first_issue=issues[0][1],
        )
    if record["record_sha256"] != _record_digest(record):
        raise _refusal("Forge record digest does not recompute.", "FORGE_RECORD_DIGEST_MISMATCH")
    if record["manifest"] != _manifest(record):
        raise _refusal("Forge component manifest does not recompute.", "FORGE_RECORD_DIGEST_MISMATCH")
    _validate_relations(record)


def _snapshot_relative(record: Mapping[str, Any]) -> str:
    return (FORGE_ROOT / str(record["run_id"]) / ("{0:06d}-{1}.json".format(
        int(record["revision"]), str(record["record_sha256"])
    ))).as_posix()


def _validate_snapshot_location(relative: str, record: Mapping[str, Any]) -> None:
    portable = _safe_relative(relative)
    parts = portable.split("/")
    if len(parts) != 5 or parts[:3] != [".uriel", "forge", "runs"] or parts[3] != record["run_id"]:
        raise _refusal("Forge snapshots must remain in their exact private run directory.", "FORGE_REF_PATH_UNSAFE")
    match = _SNAPSHOT_NAME.fullmatch(parts[4])
    if not match or int(match.group("revision")) != record["revision"] or match.group("digest") != record["record_sha256"]:
        raise _refusal("Forge snapshot filename does not bind revision and record digest.", "FORGE_RECORD_DIGEST_MISMATCH")


def _load_snapshot(root: Path, relative: str) -> Dict[str, Any]:
    raw, _, _, _ = _read_regular_bounded(
        root,
        relative,
        maximum=MAX_RUN_BYTES,
        collect=True,
        missing_code="FORGE_REF_MISSING",
        invalid_code="FORGE_REF_PATH_UNSAFE",
    )
    record = _strict_json_loads(raw)
    _validate_structural(record)
    _validate_snapshot_location(relative, record)
    return record


def _stable_project_record(root: Path) -> Tuple[Dict[str, Any], str, int]:
    raw, digest, size, _ = _read_regular_bounded(
        root,
        "uriel.project.json",
        maximum=MAX_TYPED_JSON_BYTES,
        collect=True,
        missing_code="FORGE_PROJECT_BINDING_MISMATCH",
        invalid_code="FORGE_PROJECT_BINDING_MISMATCH",
    )
    value = _strict_json_loads(raw, code="FORGE_PROJECT_BINDING_MISMATCH")
    # Reuse the existing semantic loader after the stable read; disagreement is refused.
    loaded = load_project(root)
    if value != loaded:
        raise _refusal("The project manifest changed while Forge was binding it.", "FORGE_PROJECT_BINDING_MISMATCH")
    return value, digest, size


def _normalize_requirement(row: Mapping[str, Any], project_sha256: str) -> Dict[str, Any]:
    allowed = {"requirement_id", "statement", "acceptance_condition", "source_kind", "source_sha256"}
    unknown = set(row) - allowed
    if unknown:
        raise _refusal("A Forge requirement request contains an unknown field.", "FORGE_UNKNOWN_FIELD", field=sorted(unknown)[0])
    source_kind = str(row.get("source_kind", "OPERATOR"))
    source_sha = row.get("source_sha256")
    if "source_sha256" not in row:
        source_sha = project_sha256 if source_kind == "PROJECT_MANIFEST" else None
    return {
        "requirement_id": row.get("requirement_id"),
        "statement": row.get("statement"),
        "acceptance_condition": row.get("acceptance_condition"),
        "source_kind": source_kind,
        "source_sha256": source_sha,
    }


def _normalize_reference_descriptor(
    root: Path,
    row: Mapping[str, Any],
    *,
    remaining_bytes: int,
) -> Dict[str, Any]:
    allowed = {"ref_id", "role", "record_schema", "path", "media_type", "record_id", "disclosure"}
    unknown = set(row) - allowed
    if unknown:
        raise _refusal("A Forge reference request contains an unknown field.", "FORGE_UNKNOWN_FIELD", field=sorted(unknown)[0])
    role = str(row.get("role", ""))
    if role not in REFERENCE_ROLES:
        raise _refusal("A Forge reference request uses an unsupported role.", "FORGE_SCHEMA_MISMATCH")
    relative = _safe_relative(row.get("path"))
    maximum = min(
        remaining_bytes,
        MAX_TYPED_JSON_BYTES if row.get("record_schema") is not None else MAX_TOTAL_REFERENCE_BYTES,
    )
    _, digest, size, _ = _read_regular_bounded(
        root,
        relative,
        maximum=maximum,
        collect=False,
    )
    return {
        "ref_id": row.get("ref_id"),
        "role": role,
        "record_schema": row.get("record_schema"),
        "path": relative,
        "sha256": digest,
        "size_bytes": size,
        "media_type": row.get("media_type"),
        "record_id": row.get("record_id"),
        "disclosure": row.get("disclosure", "PRIVATE"),
    }


def _binding_from_refs(
    refs: Sequence[Mapping[str, Any]],
    project_sha256: str,
    project_binding_digest: Any,
) -> Dict[str, Any]:
    by_role: Dict[str, List[Mapping[str, Any]]] = {}
    for row in refs:
        by_role.setdefault(str(row["role"]), []).append(row)
    data_ids = [row.get("record_id") for row in by_role.get("DATA_GENERATION", [])]
    if any(not isinstance(value, str) or not _HEX64.fullmatch(value) for value in data_ids):
        raise _refusal("DATA_GENERATION references require their exact 64-character generation ID.", "FORGE_SCHEMA_MISMATCH")
    source = by_role.get("SOURCE_MANIFEST", [])
    workbench = by_role.get("WORKBENCH_GENERATION", [])
    readiness = by_role.get("READINESS_SELECTION", [])
    return {
        "project_manifest_sha256": project_sha256,
        "source_manifest_sha256": source[0]["sha256"] if source else None,
        "project_binding_digest": project_binding_digest,
        "workbench_generation_id": workbench[0].get("record_id") if workbench else None,
        "data_generation_ids": sorted(str(value) for value in data_ids),
        "readiness_selection_sha256": readiness[0]["sha256"] if readiness else None,
    }


def _validate_request(value: Mapping[str, Any], *, initial: bool) -> None:
    _assert_json_depth(value)
    _scan_forbidden_fields(value)
    if initial:
        allowed = {
            "schema",
            "mission",
            "non_goals",
            "requirements",
            "references",
            "work_packages",
            "project_binding_digest",
        }
        expected = INIT_REQUEST_SCHEMA
        required = {"schema", "mission", "requirements"}
    else:
        allowed = {"schema", "references", "work_packages", "closure_ref_ids", "result_summary"}
        expected = TRANSITION_REQUEST_SCHEMA
        required = {"schema"}
    unknown = set(value) - allowed
    if unknown:
        raise _refusal("A Forge request contains an unknown field.", "FORGE_UNKNOWN_FIELD", field=sorted(unknown)[0])
    if not required <= set(value) or value.get("schema") != expected:
        raise _refusal("Forge request schema or required fields do not match this operation.", "FORGE_SCHEMA_MISMATCH")
    for key in ("requirements", "references", "work_packages", "closure_ref_ids", "non_goals"):
        if key in value and not isinstance(value[key], list):
            raise _refusal("Forge request collections must be JSON arrays.", "FORGE_SCHEMA_MISMATCH", field=key)


def load_forge_request(root: Union[str, Path], relative: str, *, initial: bool) -> Dict[str, Any]:
    """Read one bounded, project-relative strict JSON request for the CLI."""

    paths = paths_for(root)
    raw, _, _, _ = _read_regular_bounded(
        paths.root,
        relative,
        maximum=MAX_REQUEST_BYTES,
        collect=True,
        missing_code="FORGE_REF_MISSING",
        invalid_code="FORGE_REF_PATH_UNSAFE",
    )
    value = _strict_json_loads(raw)
    _validate_request(value, initial=initial)
    return value


def _event(
    run_id: str,
    revision: int,
    created_at_utc: str,
    from_state: Optional[str],
    to_state: str,
    rationale: str,
    changed_package_ids: Sequence[str],
    changed_ref_ids: Sequence[str],
) -> Dict[str, Any]:
    kind = "BASELINE" if revision == 0 else EVENT_KIND_FOR_TARGET[to_state]
    seed = {
        "run_id": run_id,
        "revision": revision,
        "created_at_utc": created_at_utc,
        "from_state": from_state,
        "to_state": to_state,
        "event_kind": kind,
        "rationale": rationale,
        "changed_work_package_ids": sorted(changed_package_ids),
        "changed_ref_ids": sorted(changed_ref_ids),
    }
    return {
        "event_id": "forge-event-" + sha256_text(canonical_json(seed))[:16],
        "event_kind": kind,
        "created_at_utc": created_at_utc,
        "initiator": "URIEL_DETERMINISTIC_CORE",
        "from_state": from_state,
        "to_state": to_state,
        "rationale": rationale,
        "changed_work_package_ids": sorted(changed_package_ids),
        "changed_ref_ids": sorted(changed_ref_ids),
    }


def _seal_record(record: MutableMapping[str, Any]) -> Dict[str, Any]:
    record["manifest"] = _manifest(record)
    record["record_sha256"] = _record_digest(record)
    sealed = copy.deepcopy(dict(record))
    _validate_structural(sealed)
    encoded = pretty_json(sealed).encode("utf-8")
    if len(encoded) > MAX_RUN_BYTES:
        raise _refusal("The Forge snapshot exceeds its 4 MiB pre-parse ceiling.", "FORGE_RESOURCE_LIMIT")
    return sealed


def _ensure_private_run_dir(root: Path, run_id: str) -> Path:
    if not _RUN_ID.fullmatch(run_id):
        raise _refusal("Forge run ID is malformed.", "FORGE_SCHEMA_MISMATCH")
    relative = (FORGE_ROOT / run_id).as_posix()
    try:
        destination = guard_path(root, relative, must_exist=False)
    except Refusal as exc:
        raise _refusal("Forge private-state path is not confined.", "FORGE_REF_PATH_UNSAFE") from exc
    destination.mkdir(parents=True, exist_ok=True)
    if is_reparse_or_link(destination):
        raise _refusal("Forge private-state directories cannot be links or reparse points.", "FORGE_REF_PATH_UNSAFE")
    try:
        checked = guard_path(root, relative, must_exist=True)
    except Refusal as exc:
        raise _refusal("Forge private-state path became unsafe during creation.", "FORGE_REF_PATH_UNSAFE") from exc
    if checked != destination.resolve(strict=True):
        raise _refusal("Forge private-state path changed identity.", "FORGE_REF_PATH_UNSAFE")
    return destination


def _assert_private_run_dir_identity(
    root: Path,
    run_id: str,
    expected: os.stat_result,
) -> Path:
    relative = (FORGE_ROOT / run_id).as_posix()
    try:
        destination = guard_path(root, relative, must_exist=True)
        current = os.lstat(str(destination))
    except (OSError, Refusal) as exc:
        raise _refusal("Forge private-state path became unavailable.", "FORGE_REF_PATH_UNSAFE") from exc
    is_reparse = bool(getattr(current, "st_file_attributes", 0) & _REPARSE_POINT)
    if (
        not stat.S_ISDIR(current.st_mode)
        or stat.S_ISLNK(current.st_mode)
        or is_reparse
        or not _same_identity(expected, current)
    ):
        raise _refusal("Forge private-state directory changed identity.", "FORGE_REF_PATH_UNSAFE")
    return destination


def _write_immutable(root: Path, record: Mapping[str, Any]) -> Tuple[str, bool]:
    relative = _snapshot_relative(record)
    run_dir = _ensure_private_run_dir(root, str(record["run_id"]))
    run_identity = os.lstat(str(run_dir))
    _assert_private_run_dir_identity(root, str(record["run_id"]), run_identity)
    target = run_dir / Path(relative).name
    payload = pretty_json(record).encode("utf-8")
    if target.exists():
        existing, _, _, _ = _read_regular_bounded(root, relative, maximum=MAX_RUN_BYTES, collect=True)
        if existing != payload:
            raise _refusal("An immutable Forge snapshot path already contains different bytes.", "FORGE_RECORD_DIGEST_MISMATCH")
        return relative, False

    temporary = run_dir / (".tmp-" + uuid.uuid4().hex)
    descriptor: Optional[int] = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(str(temporary), flags, 0o600)
        _assert_private_run_dir_identity(root, str(record["run_id"]), run_identity)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = None
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        _assert_private_run_dir_identity(root, str(record["run_id"]), run_identity)
        try:
            os.link(str(temporary), str(target))
        except FileExistsError:
            existing, _, _, _ = _read_regular_bounded(root, relative, maximum=MAX_RUN_BYTES, collect=True)
            if existing != payload:
                raise _refusal("A concurrent Forge writer published a different child revision.", "FORGE_TRANSITION_REFUSED")
            return relative, False
        _assert_private_run_dir_identity(root, str(record["run_id"]), run_identity)
        return relative, True
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _verify_typed_reference(raw: bytes, ref: Mapping[str, Any]) -> Optional[Dict[str, Any]]:
    expected_schema = ref.get("record_schema")
    if expected_schema is None:
        return None
    if len(raw) > MAX_TYPED_JSON_BYTES:
        raise _refusal("A typed JSON reference exceeds the Forge parse ceiling.", "FORGE_RESOURCE_LIMIT")
    value = _strict_json_loads(raw, code="FORGE_SCHEMA_MISMATCH")
    if value.get("schema") != expected_schema:
        raise _refusal("A typed Forge reference contains a different record schema.", "FORGE_SCHEMA_MISMATCH")
    if expected_schema == DEFERRAL_SCHEMA:
        issues = _schema_issues(value, _deferral_schema(), _deferral_schema())
        if issues:
            raise _refusal(
                "A Forge soft-gate deferral does not satisfy its closed v1 contract.",
                "FORGE_SCHEMA_MISMATCH",
                first_pointer=issues[0][0],
                first_issue=issues[0][1],
            )
        if value.get("record_sha256") != _record_digest(value):
            raise _refusal("A Forge deferral digest does not recompute.", "FORGE_RECORD_DIGEST_MISMATCH")
    if expected_schema == "uriel.gate_decision.v1":
        try:
            value = validate_gate_decision(value)
        except Refusal as exc:
            raise _refusal(
                "A Forge gate reference fails deterministic gate recomputation.",
                "FORGE_SCHEMA_MISMATCH",
                gate_failure_code=exc.code,
            ) from exc
    return value


def _verify_references(root: Path, record: Mapping[str, Any], *, allow_stale: bool) -> Dict[str, Any]:
    project, project_digest, project_size = _stable_project_record(root)
    stale: List[Dict[str, str]] = []
    if project.get("project_id") != record["project_id"] or project_digest != record["binding"]["project_manifest_sha256"]:
        stale.append({"ref_id": "ref-project-manifest", "code": "FORGE_PROJECT_BINDING_MISMATCH"})

    total_declared = sum(int(ref["size_bytes"]) for ref in record["refs"])
    if total_declared > MAX_TOTAL_REFERENCE_BYTES:
        raise _refusal("Forge reference verification exceeds the 1 GiB operation budget.", "FORGE_RESOURCE_LIMIT")
    identities: Set[Tuple[Any, Any]] = set()
    gate_numbers: Set[int] = set()
    gate_decisions: List[str] = []
    typed_records: Dict[str, Dict[str, Any]] = {}
    for ref in record["refs"]:
        collect = ref.get("record_schema") is not None
        maximum = MAX_TYPED_JSON_BYTES if collect else 1024 * 1024 * 1024
        try:
            raw, digest, size, identity = _read_regular_bounded(
                root,
                str(ref["path"]),
                maximum=maximum,
                collect=collect,
            )
        except Refusal as exc:
            if allow_stale and exc.code in {"FORGE_REF_MISSING", "FORGE_REF_PATH_UNSAFE"}:
                stale.append({"ref_id": str(ref["ref_id"]), "code": exc.code})
                continue
            raise
        if identity[1] not in (None, 0):
            if identity in identities:
                raise _refusal("Forge refused two reference paths that alias one file identity.", "FORGE_DUPLICATE_ID")
            identities.add(identity)
        if digest != ref["sha256"] or size != ref["size_bytes"]:
            code = "FORGE_PROJECT_BINDING_MISMATCH" if ref["role"] == "PROJECT_MANIFEST" else "FORGE_REF_HASH_MISMATCH"
            if allow_stale:
                stale.append({"ref_id": str(ref["ref_id"]), "code": code})
                continue
            raise _refusal("A Forge reference no longer matches its exact byte binding.", code, ref_id=ref["ref_id"])
        typed = _verify_typed_reference(raw, ref) if collect else None
        if typed is not None:
            typed_records[str(ref["ref_id"])] = typed
        if ref["role"] == "PROJECT_MANIFEST":
            if digest != project_digest or size != project_size or typed != project:
                if allow_stale:
                    stale.append({"ref_id": str(ref["ref_id"]), "code": "FORGE_PROJECT_BINDING_MISMATCH"})
                else:
                    raise _refusal("The Forge project reference does not match the live project.", "FORGE_PROJECT_BINDING_MISMATCH")
        if ref["role"] == "GATE_DECISION":
            if typed is None or typed.get("schema") != "uriel.gate_decision.v1":
                raise _refusal("Gate references must be typed strict gate-decision records.", "FORGE_SCHEMA_MISMATCH")
            gate = typed.get("gate")
            if not isinstance(gate, int) or isinstance(gate, bool) or gate in gate_numbers:
                raise _refusal("Forge gate references must identify each existing gate at most once.", "FORGE_DUPLICATE_ID")
            gate_numbers.add(gate)
            gate_decisions.append(str(typed.get("decision")))

    ref_roles = {str(row["ref_id"]): str(row["role"]) for row in record["refs"]}
    for package in record["work_packages"]:
        if package["status"] != "DEFERRED":
            continue
        matching = [
            typed_records.get(str(ref_id))
            for ref_id in package["acceptance_ref_ids"]
            if ref_roles.get(str(ref_id)) == "DEFERRAL"
        ]
        if not any(
            isinstance(value, Mapping)
            and value.get("schema") == DEFERRAL_SCHEMA
            and value.get("work_package_id") == package["work_package_id"]
            for value in matching
        ):
            raise _refusal(
                "A deferred work package lacks a valid owner/reason/impact/fallback record bound to its ID.",
                "FORGE_TRANSITION_REFUSED",
                work_package_id=package["work_package_id"],
            )

    if record["state"] in {"COMPLETE", "COMPLETE_WITH_DEFERRED_SOFT_GATES"} and any(
        decision != "PASS" for decision in gate_decisions
    ):
        raise _refusal("Forge cannot close while a referenced existing research gate is not PASS.", "FORGE_TRANSITION_REFUSED")
    if stale and not allow_stale:
        first = stale[0]
        raise _refusal("Forge live bindings are stale.", first["code"], ref_id=first["ref_id"])
    return {
        "current": not stale,
        "stale_reference_count": len(stale),
        "stale_references": stale,
        "declared_reference_bytes": total_declared,
        "reference_count": len(record["refs"]),
    }


def _changed_ids(
    before: Sequence[Mapping[str, Any]],
    after: Sequence[Mapping[str, Any]],
    key: str,
) -> List[str]:
    left = {str(row[key]): row for row in before}
    right = {str(row[key]): row for row in after}
    return sorted(identifier for identifier in set(left) | set(right) if left.get(identifier) != right.get(identifier))


def _validate_parent_child(parent: Mapping[str, Any], child: Mapping[str, Any]) -> None:
    if child["revision"] != parent["revision"] + 1 or child["parent_record_sha256"] != parent["record_sha256"]:
        raise _refusal("Forge revision lineage is discontinuous.", "FORGE_RECORD_DIGEST_MISMATCH")
    for field in ("run_id", "project_id", "mission", "non_goals", "requirements", "binding"):
        if child[field] != parent[field]:
            raise _refusal("Forge baseline identity or requirements changed within one lineage.", "FORGE_PROJECT_BINDING_MISMATCH")
    from_state = str(parent["state"])
    to_state = str(child["state"])
    if to_state not in TRANSITIONS[from_state]:
        raise _refusal("Forge refused a transition outside the frozen state map.", "FORGE_TRANSITION_REFUSED")
    if parent["event"]["to_state"] != from_state or child["event"]["from_state"] != from_state:
        raise _refusal("Forge event lineage does not bind the parent state.", "FORGE_TRANSITION_REFUSED")
    if child["event"]["event_kind"] != EVENT_KIND_FOR_TARGET[to_state]:
        raise _refusal("Forge event kind does not match the requested transition.", "FORGE_TRANSITION_REFUSED")
    if from_state == "BLOCKED" and to_state not in {"FAILED", "STALE", "SUPERSEDED", "ABORTED"}:
        if to_state != parent["event"]["from_state"]:
            raise _refusal("A BLOCKED Forge run may resume only at its exactly recorded prior stage.", "FORGE_TRANSITION_REFUSED")

    prior_refs = {str(row["ref_id"]): row for row in parent["refs"]}
    current_refs = {str(row["ref_id"]): row for row in child["refs"]}
    if not set(prior_refs) <= set(current_refs) or any(current_refs[key] != value for key, value in prior_refs.items()):
        raise _refusal("Forge references are append-only within a run.", "FORGE_TRANSITION_REFUSED")
    prior_packages = {str(row["work_package_id"]): row for row in parent["work_packages"]}
    current_packages = {str(row["work_package_id"]): row for row in child["work_packages"]}
    if not set(prior_packages) <= set(current_packages):
        raise _refusal("Forge work packages cannot disappear from a run.", "FORGE_TRANSITION_REFUSED")
    stable_fields = {
        "objective",
        "non_goals",
        "depends_on",
        "requirement_ids",
        "input_ref_ids",
        "completion_condition",
    }
    for identifier, previous in prior_packages.items():
        current = current_packages[identifier]
        if from_state != "DRAFT" and any(current[field] != previous[field] for field in stable_fields):
            raise _refusal("Scoped work-package definitions are immutable.", "FORGE_TRANSITION_REFUSED", work_package_id=identifier)
        if not set(previous["acceptance_ref_ids"]) <= set(current["acceptance_ref_ids"]):
            raise _refusal("Work-package acceptance references are append-only.", "FORGE_TRANSITION_REFUSED")
        if current["status"] not in WORK_PACKAGE_TRANSITIONS[str(previous["status"])]:
            raise _refusal("A work-package status transition was refused.", "FORGE_TRANSITION_REFUSED")
    if to_state in {"COMPLETE", "COMPLETE_WITH_DEFERRED_SOFT_GATES", "STALE", "SUPERSEDED", "ABORTED"}:
        if set(current_packages) != set(prior_packages):
            raise _refusal("Terminal Forge transitions cannot introduce new work packages.", "FORGE_TRANSITION_REFUSED")

    changed_refs = _changed_ids(parent["refs"], child["refs"], "ref_id")
    changed_packages = _changed_ids(parent["work_packages"], child["work_packages"], "work_package_id")
    if child["event"]["changed_ref_ids"] != changed_refs or child["event"]["changed_work_package_ids"] != changed_packages:
        raise _refusal("Forge event change indexes do not recompute.", "FORGE_RECORD_DIGEST_MISMATCH")
    parent_time = _dt.datetime.fromisoformat(str(parent["created_at_utc"]).replace("Z", "+00:00"))
    child_time = _dt.datetime.fromisoformat(str(child["created_at_utc"]).replace("Z", "+00:00"))
    if child_time < parent_time:
        raise _refusal("Forge revision timestamps must be nondecreasing.", "FORGE_TRANSITION_REFUSED")


def _lineage(root: Path, leaf_relative: str, leaf: Mapping[str, Any]) -> List[Tuple[str, Dict[str, Any]]]:
    rows: List[Tuple[str, Dict[str, Any]]] = [(leaf_relative, dict(leaf))]
    current = dict(leaf)
    while current["revision"] > 0:
        if len(rows) >= MAX_LINEAGE_RECORDS:
            raise _refusal("Forge lineage exceeds the bounded verification ceiling.", "FORGE_RESOURCE_LIMIT")
        parent_digest = str(current["parent_record_sha256"])
        parent_relative = (
            FORGE_ROOT
            / str(current["run_id"])
            / ("{0:06d}-{1}.json".format(int(current["revision"]) - 1, parent_digest))
        ).as_posix()
        parent = _load_snapshot(root, parent_relative)
        _validate_parent_child(parent, current)
        rows.append((parent_relative, parent))
        current = parent
    if current["parent_record_sha256"] is not None or current["state"] != "DRAFT":
        raise _refusal("Forge lineage does not terminate at a DRAFT baseline.", "FORGE_RECORD_DIGEST_MISMATCH")
    if current["event"]["event_kind"] != "BASELINE" or current["event"]["from_state"] is not None:
        raise _refusal("Forge baseline event is malformed.", "FORGE_TRANSITION_REFUSED")
    if current["event"]["changed_ref_ids"] != sorted(str(row["ref_id"]) for row in current["refs"]):
        raise _refusal("Forge baseline reference index does not recompute.", "FORGE_RECORD_DIGEST_MISMATCH")
    if current["event"]["changed_work_package_ids"] != sorted(
        str(row["work_package_id"]) for row in current["work_packages"]
    ):
        raise _refusal("Forge baseline work-package index does not recompute.", "FORGE_RECORD_DIGEST_MISMATCH")
    digests = [row[1]["record_sha256"] for row in rows]
    events = [row[1]["event"]["event_id"] for row in rows]
    if len(digests) != len(set(digests)) or len(events) != len(set(events)):
        raise _refusal("Forge lineage repeats a record or event identity.", "FORGE_DUPLICATE_ID")
    return rows


def verify_forge_run(
    root: Union[str, Path],
    snapshot_relative_path: str,
    *,
    verify_references: bool = True,
) -> Dict[str, Any]:
    """Independently re-read and verify one exact Forge snapshot and lineage."""

    paths = paths_for(root)
    portable = _safe_relative(snapshot_relative_path)
    leaf = _load_snapshot(paths.root, portable)
    lineage = _lineage(paths.root, portable, leaf)
    allow_stale = leaf["state"] in {"STALE", "SUPERSEDED"}
    bindings = (
        _verify_references(paths.root, leaf, allow_stale=allow_stale)
        if verify_references
        else {
            "current": None,
            "stale_reference_count": 0,
            "stale_references": [],
            "declared_reference_bytes": sum(int(row["size_bytes"]) for row in leaf["refs"]),
            "reference_count": len(leaf["refs"]),
        }
    )
    return {
        "verified": True,
        "record_verified": True,
        "lineage_verified": True,
        "references_checked": verify_references,
        "bindings_current": bindings["current"],
        "stale_reference_count": bindings["stale_reference_count"],
        "reference_count": bindings["reference_count"],
        "declared_reference_bytes": bindings["declared_reference_bytes"],
        "lineage_records": len(lineage),
        "run_id": leaf["run_id"],
        "revision": leaf["revision"],
        "state": leaf["state"],
        "record_sha256": leaf["record_sha256"],
        "snapshot_relative_path": portable,
        "authority_scope": "FORGE_WORKFLOW_ONLY",
        "upstream_authority_effect": "NONE",
        "authority_granted": False,
        "network_calls": 0,
        "ai_calls": 0,
        "subprocess_calls": 0,
    }


def load_verified_forge_snapshot(
    root: Union[str, Path],
    snapshot_relative_path: str,
) -> Dict[str, Any]:
    """Return a defensive copy of one fully verified exact Forge snapshot.

    This is the application-facing read facade for extensions such as the
    forward-path engine.  It performs the same structural, lineage, and live
    reference checks as :func:`verify_forge_run` before exposing record data;
    callers never need to bypass the Forge verifier or discover a mutable
    "latest" record.
    """

    paths = paths_for(root)
    portable = _safe_relative(snapshot_relative_path)
    leaf = _load_snapshot(paths.root, portable)
    _lineage(paths.root, portable, leaf)
    _verify_references(
        paths.root,
        leaf,
        allow_stale=leaf["state"] in {"STALE", "SUPERSEDED"},
    )
    return copy.deepcopy(leaf)


def forge_init(
    root: Union[str, Path],
    request: Mapping[str, Any],
    *,
    created_at_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """Create the immutable DRAFT baseline for one normalized Forge request."""

    if not isinstance(request, Mapping):
        raise _refusal("Forge init request must be one JSON object.", "FORGE_SCHEMA_MISMATCH")
    _validate_request(request, initial=True)
    paths = paths_for(root)
    project, project_sha, project_size = _stable_project_record(paths.root)
    requirements = [
        _normalize_requirement(row, project_sha)
        for row in request["requirements"]
        if isinstance(row, Mapping)
    ]
    if len(requirements) != len(request["requirements"]):
        raise _refusal("Forge requirements must be JSON objects.", "FORGE_SCHEMA_MISMATCH")
    references = [
        {
            "ref_id": "ref-project-manifest",
            "role": "PROJECT_MANIFEST",
            "record_schema": "uriel.project.v1",
            "path": "uriel.project.json",
            "sha256": project_sha,
            "size_bytes": project_size,
            "media_type": "application/json",
            "record_id": project.get("project_id"),
            "disclosure": "PRIVATE",
        }
    ]
    remaining_reference_bytes = MAX_TOTAL_REFERENCE_BYTES - project_size
    for row in request.get("references", []):
        if not isinstance(row, Mapping):
            raise _refusal("Forge reference descriptors must be JSON objects.", "FORGE_SCHEMA_MISMATCH")
        reference = _normalize_reference_descriptor(
            paths.root,
            row,
            remaining_bytes=remaining_reference_bytes,
        )
        references.append(reference)
        remaining_reference_bytes -= int(reference["size_bytes"])
    packages = copy.deepcopy(request.get("work_packages", []))
    if any(not isinstance(row, Mapping) for row in packages):
        raise _refusal("Forge work packages must be JSON objects.", "FORGE_SCHEMA_MISMATCH")
    binding = _binding_from_refs(references, project_sha, request.get("project_binding_digest"))
    seed = {
        "project_id": project.get("project_id"),
        "mission": request["mission"],
        "non_goals": request.get("non_goals", []),
        "requirements": requirements,
        "refs": references,
        "work_packages": packages,
        "binding": binding,
    }
    run_id = "forge-" + sha256_text(canonical_json(seed))[:16]
    run_dir = paths.root / FORGE_ROOT / run_id
    if run_dir.is_dir():
        candidates = sorted(run_dir.glob("000000-*.json"))
        if len(candidates) == 1:
            existing_relative = candidates[0].relative_to(paths.root).as_posix()
            existing = _load_snapshot(paths.root, existing_relative)
            if all(existing[key] == seed[key] for key in ("project_id", "mission", "non_goals", "requirements", "refs", "work_packages", "binding")):
                verified = verify_forge_run(paths.root, existing_relative)
                return {"status": "ALREADY_SEALED", **verified}
        if candidates:
            raise _refusal("The deterministic Forge run ID already has a different baseline.", "FORGE_DUPLICATE_ID")

    created = created_at_utc or utc_now()
    event = _event(
        run_id,
        0,
        created,
        None,
        "DRAFT",
        "Immutable Forge baseline created from the reviewed local request.",
        [str(row["work_package_id"]) for row in packages],
        [str(row["ref_id"]) for row in references],
    )
    base: Dict[str, Any] = {
        "schema": RUN_SCHEMA,
        "schema_version": 1,
        "run_id": run_id,
        "project_id": project.get("project_id"),
        "revision": 0,
        "parent_record_sha256": None,
        "created_at_utc": created,
        "mission": request["mission"],
        "non_goals": copy.deepcopy(request.get("non_goals", [])),
        "requirements": requirements,
        "binding": binding,
        "state": "DRAFT",
        "event": event,
        "refs": references,
        "work_packages": packages,
        "manifest": {},
        "indexes": _indexes(references, []),
        "result": {"outcome": "OPEN", "summary": None, "closure_ref_ids": []},
        "authority_scope": "FORGE_WORKFLOW_ONLY",
        "upstream_authority_effect": "NONE",
        "record_sha256": "0" * 64,
    }
    record = _seal_record(base)
    _verify_references(paths.root, record, allow_stale=False)
    relative, created_new = _write_immutable(paths.root, record)
    verified = verify_forge_run(paths.root, relative)
    return {"status": "SEALED" if created_new else "ALREADY_SEALED", **verified}


def _acquire_transition_lock(run_dir: Path, parent_digest: str) -> int:
    lock = run_dir / (".transition-" + parent_digest + ".lock")
    flags = os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(str(lock), flags, 0o600)
    except OSError as exc:
        raise _refusal("Forge could not open its transition coordination file.", "FORGE_REF_PATH_UNSAFE") from exc
    try:
        opened = os.fstat(descriptor)
        current = os.lstat(str(lock))
        is_reparse = bool(getattr(current, "st_file_attributes", 0) & _REPARSE_POINT)
        if (
            not stat.S_ISREG(opened.st_mode)
            or not stat.S_ISREG(current.st_mode)
            or stat.S_ISLNK(current.st_mode)
            or is_reparse
            or not _same_identity(opened, current)
        ):
            raise _refusal("Forge transition coordination cannot use a link or replaced file.", "FORGE_REF_PATH_UNSAFE")
        if opened.st_size == 0:
            os.write(descriptor, b"\0")
            os.fsync(descriptor)
        os.lseek(descriptor, 0, os.SEEK_SET)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(descriptor, msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (BlockingIOError, OSError) as exc:
            raise _refusal(
                "Another writer is already transitioning this exact Forge parent.",
                "FORGE_TRANSITION_BUSY",
            ) from exc
        return descriptor
    except Exception:
        os.close(descriptor)
        raise


def _release_transition_lock(descriptor: int) -> None:
    try:
        os.lseek(descriptor, 0, os.SEEK_SET)
        if os.name == "nt":
            import msvcrt

            msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(descriptor, fcntl.LOCK_UN)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def forge_transition(
    root: Union[str, Path],
    snapshot_relative_path: str,
    to_state: str,
    rationale: str,
    request: Optional[Mapping[str, Any]] = None,
    *,
    created_at_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """Request one validated transition through the sole deterministic facade."""

    update: Mapping[str, Any] = request or {"schema": TRANSITION_REQUEST_SCHEMA}
    if not isinstance(update, Mapping):
        raise _refusal("Forge transition request must be one JSON object.", "FORGE_SCHEMA_MISMATCH")
    _validate_request(update, initial=False)
    if not isinstance(to_state, str) or to_state not in STATES or not isinstance(rationale, str) or not rationale.strip():
        raise _refusal("Forge transition target and rationale are required.", "FORGE_TRANSITION_REFUSED")
    paths = paths_for(root)
    parent_relative = _safe_relative(snapshot_relative_path)
    parent = _load_snapshot(paths.root, parent_relative)
    if to_state not in TRANSITIONS[str(parent["state"])]:
        raise _refusal("Forge refused a transition outside the frozen state map.", "FORGE_TRANSITION_REFUSED")
    if parent["state"] == "BLOCKED" and to_state not in {"FAILED", "STALE", "SUPERSEDED", "ABORTED"}:
        if to_state != parent["event"]["from_state"]:
            raise _refusal("A BLOCKED Forge run may resume only at its recorded prior stage.", "FORGE_TRANSITION_REFUSED")
    # A stale/superseded transition is the only operation allowed to acknowledge
    # already-changed live bindings; every other transition requires current refs.
    if to_state in {"STALE", "SUPERSEDED"}:
        _lineage(paths.root, parent_relative, parent)
        binding_status = _verify_references(paths.root, parent, allow_stale=True)
        if to_state == "STALE" and binding_status["current"]:
            raise _refusal(
                "Forge may enter STALE only after an exact live binding is observed stale.",
                "FORGE_TRANSITION_REFUSED",
            )
    else:
        verify_forge_run(paths.root, parent_relative)

    run_dir = _ensure_private_run_dir(paths.root, str(parent["run_id"]))
    lock_descriptor = _acquire_transition_lock(run_dir, str(parent["record_sha256"]))
    try:
        references = copy.deepcopy(parent["refs"])
        remaining_reference_bytes = MAX_TOTAL_REFERENCE_BYTES - sum(
            int(row["size_bytes"]) for row in references
        )
        for row in update.get("references", []):
            if not isinstance(row, Mapping):
                raise _refusal("Forge reference descriptors must be JSON objects.", "FORGE_SCHEMA_MISMATCH")
            reference = _normalize_reference_descriptor(
                paths.root,
                row,
                remaining_bytes=remaining_reference_bytes,
            )
            references.append(reference)
            remaining_reference_bytes -= int(reference["size_bytes"])
        packages = copy.deepcopy(update.get("work_packages", parent["work_packages"]))
        if any(not isinstance(row, Mapping) for row in packages):
            raise _refusal("Forge work packages must be JSON objects.", "FORGE_SCHEMA_MISMATCH")
        closure_ids = copy.deepcopy(update.get("closure_ref_ids", parent["result"]["closure_ref_ids"]))
        if not isinstance(closure_ids, list):
            raise _refusal("Forge closure references must be an array.", "FORGE_SCHEMA_MISMATCH")
        changed_refs = _changed_ids(parent["refs"], references, "ref_id")
        changed_packages = _changed_ids(parent["work_packages"], packages, "work_package_id")
        created = created_at_utc or utc_now()
        event = _event(
            str(parent["run_id"]),
            int(parent["revision"]) + 1,
            created,
            str(parent["state"]),
            to_state,
            rationale.strip(),
            changed_packages,
            changed_refs,
        )
        summary = update.get("result_summary")
        if STATE_OUTCOME[to_state] == "OPEN":
            summary = None if summary is None else summary
        elif summary is None:
            summary = rationale.strip()
        child: Dict[str, Any] = {
            "schema": RUN_SCHEMA,
            "schema_version": 1,
            "run_id": parent["run_id"],
            "project_id": parent["project_id"],
            "revision": int(parent["revision"]) + 1,
            "parent_record_sha256": parent["record_sha256"],
            "created_at_utc": created,
            "mission": parent["mission"],
            "non_goals": copy.deepcopy(parent["non_goals"]),
            "requirements": copy.deepcopy(parent["requirements"]),
            "binding": copy.deepcopy(parent["binding"]),
            "state": to_state,
            "event": event,
            "refs": references,
            "work_packages": packages,
            "manifest": {},
            "indexes": _indexes(references, closure_ids),
            "result": {
                "outcome": STATE_OUTCOME[to_state],
                "summary": summary,
                "closure_ref_ids": sorted(str(item) for item in closure_ids),
            },
            "authority_scope": "FORGE_WORKFLOW_ONLY",
            "upstream_authority_effect": "NONE",
            "record_sha256": "0" * 64,
        }
        record = _seal_record(child)
        _validate_parent_child(parent, record)
        _verify_references(paths.root, record, allow_stale=to_state in {"STALE", "SUPERSEDED"})

        existing_children: List[Dict[str, Any]] = []
        for candidate in run_dir.glob("{0:06d}-*.json".format(record["revision"])):
            relative = candidate.relative_to(paths.root).as_posix()
            existing_children.append(_load_snapshot(paths.root, relative))
        for existing in existing_children:
            if existing["record_sha256"] == record["record_sha256"]:
                relative = _snapshot_relative(existing)
                verified = verify_forge_run(paths.root, relative)
                return {"status": "ALREADY_SEALED", **verified}
            if (
                existing["parent_record_sha256"] == record["parent_record_sha256"]
                and existing["state"] == record["state"]
                and existing["event"]["rationale"] == record["event"]["rationale"]
                and existing["refs"] == record["refs"]
                and existing["work_packages"] == record["work_packages"]
                and existing["result"] == record["result"]
            ):
                relative = _snapshot_relative(existing)
                verified = verify_forge_run(paths.root, relative)
                return {"status": "ALREADY_SEALED", **verified}
        if existing_children:
            raise _refusal("This exact Forge parent already has a different child revision.", "FORGE_TRANSITION_REFUSED")

        relative, created_new = _write_immutable(paths.root, record)
        verified = verify_forge_run(paths.root, relative)
        return {"status": "SEALED" if created_new else "ALREADY_SEALED", **verified}
    finally:
        _release_transition_lock(lock_descriptor)


__all__ = [
    "INIT_REQUEST_SCHEMA",
    "TRANSITION_REQUEST_SCHEMA",
    "STATES",
    "TRANSITIONS",
    "forge_init",
    "forge_transition",
    "load_forge_request",
    "load_verified_forge_snapshot",
    "verify_forge_run",
]
