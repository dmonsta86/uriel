"""Independent verification (STRICT_BLESSING_CONTRACT.md 12.20, 12.30, 14).

The verifier recomputes the complete binding digest from the live project
state - never from cached "PASS" text - and records a receipt.  A failed
independent verification invalidates all dependent passes; no certificate may
be created before the verifier recomputes the binding.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

from .core import (
    Refusal,
    atomic_write_json,
    canonical_json,
    canonical_root,
    guard_path,
    is_reparse_or_link,
    iter_project_files,
    load_current_manifest,
    media_type,
    paths_for,
    read_json,
    sha256_file,
    sha256_text,
    verify_source_manifest,
    utc_now,
)
from .data_contracts import GENERATION_READINESS_SCHEMA, validate_data_record
from .generation_readiness import (
    current_generation_readiness_selection,
)
from .gate_contract import (
    GATE_SPECS,
    load_gate_decisions,
    latest_gate_decision,
)

VERIFIER_SCHEMA = "uriel.verifier_receipt.v1"
MAX_VERIFIER_RECEIPTS = 4_096
SOURCE_VERIFY_MAX_FILES = 10_000
SOURCE_VERIFY_MAX_TOTAL_BYTES = 512 * 1024 * 1024
SOURCE_VERIFY_MAX_FILE_BYTES = 256 * 1024 * 1024
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _bounded_ephemeral_source_inventory(root: Path) -> Dict[str, Any]:
    """Hash an unsealed source tree within verifier ceilings, without writes."""
    records: List[Dict[str, Any]] = []
    total_bytes = 0
    for path in iter_project_files(root):
        if len(records) >= SOURCE_VERIFY_MAX_FILES:
            raise Refusal(
                "The live source tree exceeds the verifier file-count ceiling.",
                code="SOURCE_VERIFY_BUDGET",
            )
        size = path.stat().st_size
        if size > SOURCE_VERIFY_MAX_FILE_BYTES:
            raise Refusal(
                "A live source file exceeds the verifier per-file ceiling.",
                code="SOURCE_VERIFY_BUDGET",
                details={"path": path.relative_to(root).as_posix(), "size_bytes": size},
            )
        total_bytes += size
        if total_bytes > SOURCE_VERIFY_MAX_TOTAL_BYTES:
            raise Refusal(
                "The live source tree exceeds the verifier total-byte ceiling.",
                code="SOURCE_VERIFY_BUDGET",
            )
        records.append(
            {
                "relative_path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "size": size,
                "media_type": media_type(path),
            }
        )
    records.sort(key=lambda item: str(item["relative_path"]).casefold())
    return {
        "manifest_sha256": None,
        "records_sha256": sha256_text(canonical_json(records)),
        "records": records,
    }


def compute_binding_digest(root: Union[str, Path]) -> Dict[str, Any]:
    """Recompute the complete exact-version binding from live project state.

    The binding covers: project manifest, source manifest + records, data
    readiness receipts, gate decisions, and the limitation register.
    """
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    try:
        source = load_current_manifest(paths.root)
    except Refusal as exc:
        if exc.code != "PROJECT_PATH_MISSING":
            raise
        source = _bounded_ephemeral_source_inventory(paths.root)
        source_check = {"verified": False}
    else:
        source_check = verify_source_manifest(
            paths.root,
            source,
            max_files=SOURCE_VERIFY_MAX_FILES,
            max_total_bytes=SOURCE_VERIFY_MAX_TOTAL_BYTES,
            max_file_bytes=SOURCE_VERIFY_MAX_FILE_BYTES,
        )
    project_hash = sha256_file(paths.project)
    readiness_hashes: List[str] = []
    readiness_dir = paths.state / "readiness"
    if readiness_dir.exists():
        for path in sorted(readiness_dir.glob("receipt-*.json")):
            try:
                receipt = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise Refusal(
                    "A Data Readiness receipt is unreadable.",
                    code="READINESS_RECORD_TAMPERED",
                    details={"path": str(path)},
                ) from exc
            if not isinstance(receipt, Mapping):
                raise Refusal(
                    "A Data Readiness receipt is not a JSON object.",
                    code="READINESS_RECORD_TAMPERED",
                    details={"path": str(path)},
                )
            if receipt.get("schema") == GENERATION_READINESS_SCHEMA:
                # Historical v2 receipts remain immutable evidence even after
                # their inputs become stale.  Validate their content identity;
                # only CURRENT receives live recomputation and authority below.
                validate_data_record(receipt)
                declared = str(receipt.get("record_sha256", ""))
                if path.name != "receipt-" + declared + ".json":
                    raise Refusal(
                        "A generation readiness receipt filename and identity disagree.",
                        code="READINESS_RECORD_TAMPERED",
                        details={"path": str(path)},
                    )
                readiness_hashes.append(declared)
                continue
            declared = receipt.get("receipt_sha256")
            if declared:
                readiness_hashes.append(str(declared))
            elif path.name.startswith("receipt-") and path.name.endswith(".json"):
                readiness_hashes.append(path.name[len("receipt-"):-len(".json")])
        active = current_generation_readiness_selection(root_path, verify=True)
        if active.get("exists"):
            # Bind which immutable receipt is authoritative, not merely the set
            # of receipts that happens to exist in the project store.
            readiness_hashes.append(str(active["selection_sha256"]))
    execution_hashes: List[str] = []
    if paths.receipts.exists():
        for path in sorted(paths.receipts.rglob("receipt.json")):
            try:
                receipt = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if isinstance(receipt, Mapping) and receipt.get("receipt_sha256"):
                execution_hashes.append(str(receipt["receipt_sha256"]))
    limitations: List[str] = []
    project = read_json(paths.project)
    for row in project.get("limitations", []):
        if isinstance(row, Mapping) and str(row.get("statement", "")).strip():
            limitations.append(str(row["statement"]).strip())
    binding = {
        "policy": "uriel-strict-blessing-1.0.0",
        "gate_specification_versions": "uriel-strict-blessing-1.0.0",
        "project_manifest_sha256": project_hash,
        "source_manifest_sha256": source.get("manifest_sha256"),
        "source_records_sha256": source.get("records_sha256"),
        "source_manifest_verified": bool(source_check.get("verified")),
        "data_readiness_receipt_sha256s": sorted(set(readiness_hashes)),
        "execution_receipt_sha256s": sorted(set(execution_hashes)),
        "limitation_register": sorted(limitations),
    }
    digest = sha256_text(canonical_json(binding))
    binding["binding_digest"] = digest
    return binding


def _verifier_core(record: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "schema": record.get("schema"),
        "schema_version": record.get("schema_version"),
        "decision": record.get("decision"),
        "expected_binding_digest": record.get("expected_binding_digest"),
        "recomputed_binding_digest": record.get("recomputed_binding_digest"),
        "binding": record.get("binding"),
        "errors": record.get("errors"),
    }


def verifier_sha256(record: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(_verifier_core(record)))


def _validated_verifier_record(
    record: Mapping[str, Any],
    *,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Rehash and semantically validate one persisted verifier receipt."""
    if not isinstance(record, Mapping):
        raise Refusal("A verifier receipt is not a JSON object.", code="VERIFIER_RECEIPT_TAMPERED")
    decision = record.get("decision")
    expected = record.get("expected_binding_digest")
    recomputed = record.get("recomputed_binding_digest")
    binding = record.get("binding")
    errors = record.get("errors")
    if (
        record.get("schema") != VERIFIER_SCHEMA
        or record.get("schema_version") != 1
        or decision not in {"PASS", "FAIL"}
        or not isinstance(record.get("created_at_utc"), str)
        or (expected is not None and (not isinstance(expected, str) or _HEX64.fullmatch(expected) is None))
        or (recomputed is not None and (not isinstance(recomputed, str) or _HEX64.fullmatch(recomputed) is None))
        or not isinstance(binding, Mapping)
        or not isinstance(errors, list)
        or any(not isinstance(error, str) for error in errors)
    ):
        raise Refusal(
            "A verifier receipt has an invalid sealed structure.",
            code="VERIFIER_RECEIPT_TAMPERED",
            details={"path": str(path) if path else None},
        )
    if (decision == "PASS") != (not errors):
        raise Refusal(
            "A verifier receipt's decision disagrees with its errors.",
            code="VERIFIER_RECEIPT_TAMPERED",
            details={"path": str(path) if path else None},
        )
    if decision == "PASS" and (
        recomputed is None
        or binding.get("binding_digest") != recomputed
        or binding.get("source_manifest_verified") is not True
        or (expected is not None and expected != recomputed)
    ):
        raise Refusal(
            "A PASS verifier receipt does not bind one exact verified source generation.",
            code="VERIFIER_RECEIPT_TAMPERED",
            details={"path": str(path) if path else None},
        )
    declared = record.get("verifier_sha256")
    digest = verifier_sha256(record)
    if not isinstance(declared, str) or _HEX64.fullmatch(declared) is None or declared != digest:
        raise Refusal(
            "A verifier receipt's content identity is invalid.",
            code="VERIFIER_RECEIPT_TAMPERED",
            details={"path": str(path) if path else None},
        )
    if path is not None and path.name != "verifier-receipt-{0}.json".format(declared):
        raise Refusal(
            "A verifier receipt filename and content identity disagree.",
            code="VERIFIER_RECEIPT_TAMPERED",
            details={"path": str(path)},
        )
    return dict(record)


def independent_verify(root: Union[str, Path], *, expected_binding_digest: Optional[str] = None) -> Dict[str, Any]:
    """Run the independent verifier over the live project and record a receipt.

    The verifier recomputes the binding and compares it to the declared
    binding.  Any mismatch, unverified source manifest, or stale artifact
    yields FAIL and invalidates dependent passes.
    """
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    errors: List[str] = []
    if expected_binding_digest is not None and _HEX64.fullmatch(expected_binding_digest) is None:
        errors.append("The declared binding is not a 64-character SHA-256 identity.")
    try:
        binding = compute_binding_digest(root_path)
    except Exception as exc:  # noqa: BLE001 - the verifier must fail closed.
        errors.append("The verifier could not recompute the binding: {0}".format(exc))
        binding = {}
    if expected_binding_digest is not None and binding.get("binding_digest") != expected_binding_digest:
        errors.append("Recomputed binding {0} differs from the declared binding {1}.".format(
            binding.get("binding_digest"), expected_binding_digest))
    if not binding.get("source_manifest_verified"):
        errors.append("The live source manifest does not verify.")
    try:
        gate_records = {int(row["gate"]): row for row in load_gate_decisions(root_path)}
    except (Refusal, OSError, ValueError) as exc:
        errors.append("The gate decision store failed closed: {0}".format(exc))
        gate_records = {}
    for number in GATE_SPECS:
        record = gate_records.get(number)
        if record is None:
            errors.append("Gate {0} has no decision record.".format(number))
            continue
        if str(record.get("decision")) != "PASS":
            errors.append("Gate {0} decision is {1}; dependent passes are invalid.".format(
                number, record.get("decision")))
            continue
        decided_under = record.get("binding_digest")
        if not isinstance(decided_under, str) or _HEX64.fullmatch(decided_under) is None:
            errors.append("Gate {0} has no exact SHA-256 binding.".format(number))
        elif binding.get("binding_digest") != decided_under:
            errors.append(
                "Gate {0} was decided under a different binding ({1}); the generation changed.".format(
                    number, decided_under))
    decision = "PASS" if not errors else "FAIL"
    record = {
        "schema": VERIFIER_SCHEMA,
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "decision": decision,
        "expected_binding_digest": expected_binding_digest,
        "recomputed_binding_digest": binding.get("binding_digest"),
        "binding": binding,
        "errors": errors,
    }
    record["verifier_sha256"] = verifier_sha256(record)
    store = guard_path(root_path, paths.state / "verifier")
    guard_path(root_path, store.parent, must_exist=True)
    store.mkdir(parents=False, exist_ok=True)
    guard_path(root_path, store, must_exist=True)
    if is_reparse_or_link(store):
        raise Refusal("The verifier receipt store may not be a link.", code="VERIFIER_RECEIPT_TAMPERED")
    destination = store / "verifier-receipt-{0}.json".format(record["verifier_sha256"])
    if destination.exists():
        try:
            existing = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Refusal(
                "An existing verifier receipt is unreadable.",
                code="VERIFIER_RECEIPT_TAMPERED",
                details={"path": str(destination)},
            ) from exc
        return _validated_verifier_record(existing, path=destination)
    atomic_write_json(destination, _validated_verifier_record(record))
    return record


def load_verifier_receipts(root: Union[str, Path]) -> List[Dict[str, Any]]:
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    store = paths.state / "verifier"
    if not store.exists():
        return []
    guard_path(root_path, store, must_exist=True)
    if is_reparse_or_link(store):
        raise Refusal("The verifier receipt store may not be a link.", code="VERIFIER_RECEIPT_TAMPERED")
    candidates = sorted(store.glob("verifier-receipt-*.json"))
    if len(candidates) > MAX_VERIFIER_RECEIPTS:
        raise Refusal(
            "The verifier receipt store exceeds its bounded history ceiling.",
            code="VERIFIER_RECEIPT_BUDGET",
            details={"count": len(candidates), "maximum": MAX_VERIFIER_RECEIPTS},
        )
    records: List[Dict[str, Any]] = []
    for path in candidates:
        try:
            guard_path(root_path, path, must_exist=True)
            if is_reparse_or_link(path):
                raise Refusal("A verifier receipt may not be a link.", code="VERIFIER_RECEIPT_TAMPERED")
            record = json.loads(path.read_text(encoding="utf-8"))
        except Refusal:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise Refusal(
                "A verifier receipt file is unreadable.",
                code="VERIFIER_RECEIPT_TAMPERED",
                details={"path": str(path)},
            ) from exc
        records.append(_validated_verifier_record(record, path=path))
    return records


def latest_verifier(root: Union[str, Path]) -> Optional[Dict[str, Any]]:
    candidates = load_verifier_receipts(root)
    if not candidates:
        return None
    return max(candidates, key=lambda record: str(record.get("created_at_utc", "")))
