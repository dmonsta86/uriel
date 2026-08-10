"""Immutable, local-only Evidence Ingress managed intake.

The import receipt is the final authority marker. Raw bytes and supporting
records are content addressed and may safely exist as unreferenced recovery
material after an interruption, but no partial operation can produce a valid
receipt. This module performs no analysis and grants no Data Readiness status.
"""
from __future__ import annotations

import json
import os
import shutil
import stat
import uuid
from pathlib import Path
from typing import Any, Dict, Mapping, Tuple, Union

from .core import (
    Refusal,
    canonical_json_bytes,
    guard_path,
    paths_for,
    safe_relative_path,
    sha256_file,
    utc_now,
)
from .data_contracts import (
    DATA_IMPORT_PLAN_SCHEMAS,
    DATA_IMPORT_RECEIPT_SCHEMA,
    DATA_POLICY_VERSION,
    MAX_RECORD_FILE_BYTES,
    RAW_ARTIFACT_SCHEMA,
    bind_data_record,
    inspect_selected_source,
    validate_data_record,
)


DATA_ROOT_RELATIVE = Path(".uriel/data")
_DISK_RESERVE_BYTES = 1024 * 1024
_REPARSE_POINT = 0x400


def _managed_raw_relative(content_sha256: str) -> Path:
    return DATA_ROOT_RELATIVE / "raw" / "sha256" / content_sha256[:2] / content_sha256


def _plan_relative(plan_sha256: str) -> Path:
    return DATA_ROOT_RELATIVE / "plans" / (plan_sha256 + ".json")


def _raw_record_relative(record_sha256: str) -> Path:
    return DATA_ROOT_RELATIVE / "records" / "raw" / (record_sha256 + ".json")


def _receipt_relative(plan_sha256: str) -> Path:
    return DATA_ROOT_RELATIVE / "receipts" / "import" / (plan_sha256 + ".json")


def _regular_file(path: Path) -> bool:
    try:
        observed = os.lstat(str(path))
    except OSError:
        return False
    return bool(
        stat.S_ISREG(observed.st_mode)
        and not stat.S_ISLNK(observed.st_mode)
        and not (getattr(observed, "st_file_attributes", 0) & _REPARSE_POINT)
    )


def _ensure_directory(root: Path, directory: Path) -> Path:
    target = guard_path(root, directory)
    target.mkdir(parents=True, exist_ok=True)
    target = guard_path(root, target, must_exist=True)
    if not target.is_dir():
        raise Refusal(
            "The managed Data Desk path is not a normal directory.",
            code="DATA_STORAGE_PATH_REFUSED",
        )
    return target


def _load_json_record(root: Path, record_path: str) -> Tuple[Path, Dict[str, Any]]:
    relative = safe_relative_path(record_path)
    target = guard_path(root, root / relative, must_exist=True)
    if not _regular_file(target):
        raise Refusal(
            "The selected Data Desk record is not a regular file.",
            code="DATA_RECORD_FILE_REFUSED",
        )
    try:
        size = target.stat().st_size
    except OSError as exc:
        raise Refusal(
            "The selected Data Desk record could not be inspected.",
            code="DATA_RECORD_UNREADABLE",
            details={"error_type": type(exc).__name__},
        ) from exc
    if size > MAX_RECORD_FILE_BYTES:
        raise Refusal(
            "The selected Data Desk record exceeds the bounded JSON limit.",
            code="DATA_RECORD_FILE_REFUSED",
            details={"max_bytes": MAX_RECORD_FILE_BYTES},
        )
    try:
        value = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal(
            "The selected Data Desk record is not valid UTF-8 JSON.",
            code="DATA_RECORD_UNREADABLE",
            details={"error_type": type(exc).__name__},
        ) from exc
    if not isinstance(value, dict):
        raise Refusal(
            "The selected Data Desk record must contain one JSON object.",
            code="DATA_RECORD_OBJECT_REQUIRED",
        )
    return target, value


def _load_import_plan(root: Path, plan_path: str) -> Dict[str, Any]:
    _, value = _load_json_record(root, plan_path)
    if value.get("schema") == "uriel.cli_result.v1":
        result = value.get("result")
        if value.get("status") != "OK" or value.get("command") != "data" or not isinstance(result, Mapping):
            raise Refusal(
                "The saved CLI result does not contain a successful Data Desk plan.",
                code="DATA_PLAN_RECORD_REQUIRED",
            )
        candidate = result.get("plan")
        if not isinstance(candidate, Mapping):
            raise Refusal(
                "The saved CLI result does not contain an import plan record.",
                code="DATA_PLAN_RECORD_REQUIRED",
            )
        plan = dict(candidate)
    else:
        plan = value
    if plan.get("schema") not in DATA_IMPORT_PLAN_SCHEMAS:
        raise Refusal(
            "A versioned Evidence Ingress import plan is required.",
            code="DATA_PLAN_RECORD_REQUIRED",
        )
    validate_data_record(plan)
    return plan


def _write_immutable_bytes(root: Path, target: Path, data: bytes) -> bool:
    """Publish fully flushed bytes without replacing an existing target."""

    parent = _ensure_directory(root, target.parent)
    target = guard_path(root, target)
    temporary = guard_path(root, parent / ("." + target.name + ".tmp." + uuid.uuid4().hex))
    descriptor = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(str(temporary), flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(str(temporary), str(target))
            return True
        except FileExistsError:
            existing = guard_path(root, target, must_exist=True)
            if not _regular_file(existing) or existing.read_bytes() != data:
                raise Refusal(
                    "An immutable Data Desk record path already contains different bytes.",
                    code="DATA_IMMUTABLE_COLLISION",
                )
            return False
        except OSError as exc:
            raise Refusal(
                "Uriel could not atomically publish an immutable Data Desk record.",
                code="DATA_STORAGE_WRITE_FAILED",
                details={"error_type": type(exc).__name__},
            ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _write_immutable_record(root: Path, target: Path, record: Mapping[str, Any]) -> bool:
    return _write_immutable_bytes(root, target, canonical_json_bytes(record))


def _verify_managed_bytes(root: Path, relative: Path, expected_hash: str, expected_size: int) -> Path:
    try:
        target = guard_path(root, root / relative, must_exist=True)
    except Refusal as exc:
        if exc.code not in {"PROJECT_PATH_MISSING", "LINK_TRAVERSAL_REFUSAL"}:
            raise
        raise Refusal(
            "The managed raw artifact is missing or no longer a regular confined file.",
            code="DATA_MANAGED_ARTIFACT_TAMPERED",
        ) from exc
    if not _regular_file(target):
        raise Refusal(
            "The managed raw artifact is not a regular immutable file.",
            code="DATA_MANAGED_ARTIFACT_TAMPERED",
        )
    try:
        size = target.stat().st_size
        digest = sha256_file(target)
    except OSError as exc:
        raise Refusal(
            "The managed raw artifact could not be verified.",
            code="DATA_MANAGED_ARTIFACT_TAMPERED",
            details={"error_type": type(exc).__name__},
        ) from exc
    if size != expected_size or digest != expected_hash:
        raise Refusal(
            "The managed raw artifact no longer matches its content address.",
            code="DATA_MANAGED_ARTIFACT_TAMPERED",
            details={"size_matches": size == expected_size, "hash_matches": digest == expected_hash},
        )
    return target


def _assert_observation_matches(plan: Mapping[str, Any], observation: Mapping[str, Any]) -> None:
    source = plan.get("source", {})
    expected = {
        "content_sha256": source.get("content_sha256"),
        "size_bytes": source.get("size_bytes"),
        "format": source.get("format"),
        "media_type": source.get("media_type"),
        "encoding": source.get("encoding"),
    }
    mismatches = sorted(key for key, value in expected.items() if observation.get(key) != value)
    if mismatches:
        raise Refusal(
            "The selected source no longer matches the reviewed import plan.",
            code="DATA_PLAN_STALE",
            details={"mismatched_fields": mismatches},
            repairs=[
                "Stop and preserve both the reviewed plan and the changed source.",
                "Run `uriel data plan` again against the exact source generation you intend to import.",
                "Review the new hash, size, format, and resource budget before retrying import.",
            ],
        )


def _copy_source_to_content_address(
    root: Path,
    source_path: Union[str, Path],
    plan: Mapping[str, Any],
    source_link_peer: Union[str, Path],
) -> Tuple[Path, Dict[str, Any], bool]:
    source = plan["source"]
    budget = plan["resource_budget"]
    content_sha256 = str(source["content_sha256"])
    expected_size = int(source["size_bytes"])
    relative = _managed_raw_relative(content_sha256)
    target = guard_path(root, root / relative)

    if target.exists():
        _verify_managed_bytes(root, relative, content_sha256, expected_size)
        observation = inspect_selected_source(
            source_path,
            int(budget["max_source_bytes"]),
            int(budget["timeout_seconds"]),
            link_peer=source_link_peer,
        )
        _assert_observation_matches(plan, observation)
        return relative, observation, False

    free_bytes = shutil.disk_usage(str(root)).free
    required_bytes = expected_size + _DISK_RESERVE_BYTES
    if free_bytes < required_bytes:
        raise Refusal(
            "The project volume does not have enough free space for an atomic managed copy.",
            code="DATA_DISK_SPACE",
            details={"required_bytes": required_bytes, "available_bytes": free_bytes},
            repairs=[
                "Free enough space for the selected file plus Uriel's one-megabyte safety reserve.",
                "Move the entire project to a volume with sufficient space; do not redirect only `.uriel/data`.",
                "Select a smaller explicit source and create a new reviewed plan.",
            ],
        )

    parent = _ensure_directory(root, target.parent)
    temporary = guard_path(root, parent / ("." + target.name + ".tmp." + uuid.uuid4().hex))
    descriptor = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(str(temporary), flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = None
            observation = inspect_selected_source(
                source_path,
                int(budget["max_source_bytes"]),
                int(budget["timeout_seconds"]),
                destination=handle,
                link_peer=source_link_peer,
            )
            handle.flush()
            os.fsync(handle.fileno())
        _assert_observation_matches(plan, observation)
        try:
            os.link(str(temporary), str(target))
            copied = True
        except FileExistsError:
            _verify_managed_bytes(root, relative, content_sha256, expected_size)
            copied = False
        except OSError as exc:
            raise Refusal(
                "The managed import was interrupted before the content address became authoritative.",
                code="DATA_IMPORT_INTERRUPTED",
                details={"error_type": type(exc).__name__},
                repairs=[
                    "Retry the same reviewed plan; temporary bytes were not made authoritative.",
                    "If the interruption repeats, verify project storage health and available space.",
                    "Keep the original source unchanged until `uriel data verify-import` passes.",
                ],
            ) from exc
    except Refusal:
        raise
    except OSError as exc:
        raise Refusal(
            "The managed import was interrupted while streaming the selected source.",
            code="DATA_IMPORT_INTERRUPTED",
            details={"error_type": type(exc).__name__},
        ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass

    _verify_managed_bytes(root, relative, content_sha256, expected_size)
    return relative, observation, copied


def import_data_artifact(
    root: Union[str, Path],
    source: Union[str, Path],
    plan_path: str,
) -> Dict[str, Any]:
    """Seal one explicitly selected source under a reviewed import plan."""

    lexical_root = Path(root).expanduser()
    if not lexical_root.is_absolute():
        lexical_root = Path.cwd() / lexical_root
    lexical_root = Path(os.path.abspath(str(lexical_root)))
    paths = paths_for(root)
    plan = _load_import_plan(paths.root, plan_path)
    plan_sha256 = str(plan["record_sha256"])
    receipt_relative = _receipt_relative(plan_sha256)
    receipt_target = guard_path(paths.root, paths.root / receipt_relative)
    if receipt_target.exists():
        verified = verify_data_import(paths.root, receipt_relative.as_posix())
        receipt = verified["receipt"]
        return {
            "status": "ALREADY_IMPORTED",
            "outcome": receipt["outcome"],
            "copy_performed": False,
            "reused_existing_receipt": True,
            "managed_relative_path": receipt["managed_relative_path"],
            "receipt_relative_path": receipt_relative.as_posix(),
            "raw_record_relative_path": verified["raw_record_relative_path"],
            "content_sha256": receipt["copied_content_sha256"],
            "source_path_disclosed": False,
            "gate_0_authority_granted": False,
            "verification": {"verified": True, "decision": "PASS"},
        }

    if sha256_file(paths.project) != plan["project_binding_sha256"]:
        raise Refusal(
            "The Uriel project record changed after this import plan was created.",
            code="DATA_PLAN_PROJECT_STALE",
            repairs=[
                "Review the current project record before importing new evidence.",
                "Create and save a fresh `uriel data plan` result for this project generation.",
                "Do not edit the old plan or bypass its project binding.",
            ],
        )

    managed_relative, observation, copied = _copy_source_to_content_address(
        paths.root,
        source,
        plan,
        lexical_root,
    )
    source_record = plan["source"]
    raw_record = bind_data_record(
        {
            "schema": RAW_ARTIFACT_SCHEMA,
            "schema_version": 1,
            "created_at_utc": plan["created_at_utc"],
            "artifact_id": "raw-" + observation["content_sha256"],
            "logical_label": source_record["logical_label"],
            "managed_relative_path": managed_relative.as_posix(),
            "media_type": observation["media_type"],
            "format": observation["format"],
            "size_bytes": observation["size_bytes"],
            "content_sha256": observation["content_sha256"],
            "source_access_condition": source_record["access_condition"],
            "immutable": True,
        }
    )
    validate_data_record(raw_record)

    _write_immutable_record(paths.root, paths.root / _plan_relative(plan_sha256), plan)
    raw_record_relative = _raw_record_relative(str(raw_record["record_sha256"]))
    _write_immutable_record(paths.root, paths.root / raw_record_relative, raw_record)

    receipt = bind_data_record(
        {
            "schema": DATA_IMPORT_RECEIPT_SCHEMA,
            "schema_version": 1,
            "created_at_utc": utc_now(),
            "policy_version": DATA_POLICY_VERSION,
            "import_plan_sha256": plan_sha256,
            "raw_artifact_sha256": raw_record["record_sha256"],
            "source_content_sha256": observation["content_sha256"],
            "copied_content_sha256": observation["content_sha256"],
            "source_size_bytes": observation["size_bytes"],
            "bytes_copied": observation["size_bytes"] if copied else 0,
            "managed_relative_path": managed_relative.as_posix(),
            "outcome": "COPIED" if copied else "REFERENCED",
            "source_mutated": False,
        }
    )
    validate_data_record(receipt)
    _write_immutable_record(paths.root, receipt_target, receipt)

    verified = verify_data_import(paths.root, receipt_relative.as_posix())
    return {
        "status": "SEALED",
        "outcome": receipt["outcome"],
        "copy_performed": copied,
        "reused_existing_receipt": False,
        "managed_relative_path": managed_relative.as_posix(),
        "receipt_relative_path": receipt_relative.as_posix(),
        "raw_record_relative_path": raw_record_relative.as_posix(),
        "content_sha256": observation["content_sha256"],
        "source_path_disclosed": False,
        "gate_0_authority_granted": False,
        "verification": {"verified": verified["verified"], "decision": verified["decision"]},
    }


def verify_data_import(root: Union[str, Path], receipt_path: str) -> Dict[str, Any]:
    """Independently recompute one managed import from its receipt and bytes."""

    paths = paths_for(root)
    _, receipt = _load_json_record(paths.root, receipt_path)
    if receipt.get("schema") != DATA_IMPORT_RECEIPT_SCHEMA:
        raise Refusal(
            "The selected record is not an Evidence Ingress import receipt.",
            code="DATA_IMPORT_RECEIPT_REQUIRED",
        )
    validate_data_record(receipt)

    plan_relative = _plan_relative(str(receipt["import_plan_sha256"]))
    _, plan = _load_json_record(paths.root, plan_relative.as_posix())
    validate_data_record(plan)
    if plan.get("record_sha256") != receipt.get("import_plan_sha256"):
        raise Refusal(
            "The archived import plan does not match the receipt binding.",
            code="DATA_IMPORT_BINDING_INVALID",
        )

    raw_record_relative = _raw_record_relative(str(receipt["raw_artifact_sha256"]))
    _, raw_record = _load_json_record(paths.root, raw_record_relative.as_posix())
    validate_data_record(raw_record)
    if raw_record.get("record_sha256") != receipt.get("raw_artifact_sha256"):
        raise Refusal(
            "The raw artifact record does not match the receipt binding.",
            code="DATA_IMPORT_BINDING_INVALID",
        )

    content_sha256 = str(raw_record["content_sha256"])
    expected_managed = _managed_raw_relative(content_sha256).as_posix()
    checks = {
        "artifact_id": raw_record.get("artifact_id") == "raw-" + content_sha256,
        "logical_label": raw_record.get("logical_label") == plan["source"]["logical_label"],
        "managed_path": raw_record.get("managed_relative_path") == expected_managed
        and receipt.get("managed_relative_path") == expected_managed,
        "content_hash": receipt.get("source_content_sha256") == content_sha256
        and receipt.get("copied_content_sha256") == content_sha256
        and plan["source"]["content_sha256"] == content_sha256,
        "size": receipt.get("source_size_bytes") == raw_record.get("size_bytes")
        and plan["source"]["size_bytes"] == raw_record.get("size_bytes"),
        "format": plan["source"]["format"] == raw_record.get("format"),
        "media_type": plan["source"]["media_type"] == raw_record.get("media_type"),
        "immutable": raw_record.get("immutable") is True and receipt.get("source_mutated") is False,
    }
    failed = sorted(key for key, passed in checks.items() if not passed)
    if failed:
        raise Refusal(
            "The managed import records are internally inconsistent.",
            code="DATA_IMPORT_BINDING_INVALID",
            details={"failed_checks": failed},
        )

    _verify_managed_bytes(
        paths.root,
        Path(expected_managed),
        content_sha256,
        int(raw_record["size_bytes"]),
    )
    return {
        "verified": True,
        "decision": "PASS",
        "receipt": receipt,
        "receipt_relative_path": safe_relative_path(receipt_path).as_posix(),
        "plan_relative_path": plan_relative.as_posix(),
        "raw_record_relative_path": raw_record_relative.as_posix(),
        "managed_relative_path": expected_managed,
        "content_sha256": content_sha256,
        "project_binding_current": sha256_file(paths.project) == plan["project_binding_sha256"],
        "source_path_disclosed": False,
        "gate_0_authority_granted": False,
    }
