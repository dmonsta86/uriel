"""Independent verification (STRICT_BLESSING_CONTRACT.md 12.20, 12.30, 14).

The verifier recomputes the complete binding digest from the live project
state - never from cached "PASS" text - and records a receipt.  A failed
independent verification invalidates all dependent passes; no certificate may
be created before the verifier recomputes the binding.
"""
from __future__ import annotations

import json
from typing import Any, Dict, List, Mapping, Optional, Union

from .core import (
    Refusal,
    atomic_write_json,
    build_manifest,
    canonical_json,
    canonical_root,
    guard_path,
    paths_for,
    read_json,
    sha256_file,
    sha256_text,
    verify_source_manifest,
    utc_now,
)
from .gate_contract import (
    GATE_SPECS,
    load_gate_decisions,
    latest_gate_decision,
)

VERIFIER_SCHEMA = "uriel.verifier_receipt.v1"


def compute_binding_digest(root: Union[str, Path]) -> Dict[str, Any]:
    """Recompute the complete exact-version binding from live project state.

    The binding covers: project manifest, source manifest + records, data
    readiness receipts, gate decisions, and the limitation register.
    """
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    source = build_manifest(paths.root, persist=True)
    source_check = verify_source_manifest(paths.root, source)
    project_hash = sha256_file(paths.project)
    readiness_hashes: List[str] = []
    readiness_dir = paths.state / "readiness"
    if readiness_dir.exists():
        for path in sorted(readiness_dir.glob("receipt-*.json")):
            try:
                receipt = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(receipt, Mapping):
                continue
            declared = receipt.get("receipt_sha256")
            if declared:
                readiness_hashes.append(str(declared))
            elif path.name.startswith("receipt-") and path.name.endswith(".json"):
                readiness_hashes.append(path.name[len("receipt-"):-len(".json")])
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


def independent_verify(root: Union[str, Path], *, expected_binding_digest: Optional[str] = None) -> Dict[str, Any]:
    """Run the independent verifier over the live project and record a receipt.

    The verifier recomputes the binding and compares it to the declared
    binding.  Any mismatch, unverified source manifest, or stale artifact
    yields FAIL and invalidates dependent passes.
    """
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    errors: List[str] = []
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
    for number in GATE_SPECS:
        record = latest_gate_decision(root_path, number)
        if record is None:
            errors.append("Gate {0} has no decision record.".format(number))
            continue
        if str(record.get("decision")) != "PASS":
            errors.append("Gate {0} decision is {1}; dependent passes are invalid.".format(
                number, record.get("decision")))
            continue
        decided_under = record.get("binding_digest")
        if decided_under and binding.get("binding_digest") != str(decided_under):
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
    record["verifier_sha256"] = sha256_text(canonical_json({
        "decision": decision,
        "expected_binding_digest": expected_binding_digest,
        "recomputed_binding_digest": binding.get("binding_digest"),
    }))
    store = paths.state / "verifier"
    destination = store / "verifier-receipt-{0}.json".format(record["verifier_sha256"])
    if not destination.exists():
        atomic_write_json(destination, record)
    return record


def load_verifier_receipts(root: Union[str, Path]) -> List[Dict[str, Any]]:
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    store = paths.state / "verifier"
    if not store.exists():
        return []
    records: List[Dict[str, Any]] = []
    for path in sorted(store.glob("verifier-receipt-*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(record, Mapping) and record.get("verifier_sha256"):
            records.append(record)
    return records


def latest_verifier(root: Union[str, Path]) -> Optional[Dict[str, Any]]:
    candidates = load_verifier_receipts(root)
    if not candidates:
        return None
    return max(candidates, key=lambda record: str(record.get("created_at_utc", "")))
