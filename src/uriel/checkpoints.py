"""Immutable generation checkpoints for the research-lifecycle layer.

Implements the ``uriel.checkpoint.v1`` record contract with the standard
library only, following ``core.py`` conventions: canonical JSON, atomic
writes, and SHA-256 content addressing.

Historical generations are immutable. Generation IDs are content-derived
(records hash plus parent link), so identical replay is byte-idempotent and a
colliding generation is refused instead of silently overwritten.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .core import (
    Refusal,
    atomic_write_text,
    canonical_json,
    read_json,
    sha256_text,
    utc_now,
)

CHECKPOINT_SCHEMA = "uriel.checkpoint.v1"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

PUBLICATION_AUTHORITY_STATES = (
    "not_assessed",
    "not_ready",
    "internal_review_ready",
    "submission_ready",
    "submission_authorized",
    "submitted",
    "revision_required",
    "resubmission_ready",
    "conditionally_accepted",
    "accepted",
    "production_ready",
    "published",
    "withdrawn",
)


class GenerationRefusal(Refusal):
    """Raised when a generation write would overwrite or escape its store."""


def validate_checkpoint(record: Mapping[str, Any]) -> List[str]:
    """Return human-readable violations of the checkpoint v1 contract."""
    errors: List[str] = []
    if record.get("schema") != CHECKPOINT_SCHEMA:
        errors.append("schema must be uriel.checkpoint.v1")
    for field in (
        "generation_id",
        "source_manifest_sha256",
        "ephemeral_policy_version",
        "publication_authority",
        "created_at_utc",
    ):
        if not isinstance(record.get(field), str) or not record.get(field):
            errors.append(f"{field} must be non-empty text")
    for field in ("source_manifest_sha256", "records_sha256"):
        value = record.get(field)
        if value is not None and not (isinstance(value, str) and _HEX64.fullmatch(value)):
            errors.append(f"{field} must be a 64-character lowercase hex SHA-256")
    if not isinstance(record.get("record_count"), int) or record.get("record_count", -1) < 0:
        errors.append("record_count must be a non-negative integer")
    parent = record.get("parent_generation_id")
    if parent is not None and not (isinstance(parent, str) and parent):
            errors.append("parent_generation_id must be non-empty text or null")
    if record.get("publication_authority") not in PUBLICATION_AUTHORITY_STATES:
        errors.append("publication_authority must be a known state")
    if not isinstance(record.get("receipt_hashes"), Mapping):
        if "receipt_hashes" in record:
            errors.append("receipt_hashes must be an object")
    else:
        for name, digest in record["receipt_hashes"].items():
            if not (isinstance(digest, str) and _HEX64.fullmatch(digest)):
                errors.append(f"receipt_hashes.{name} must be a SHA-256 hex digest")
    return errors


def records_sha256(records: Iterable[Mapping[str, Any]]) -> str:
    """SHA-256 of the canonical JSON byte stream of records, in order."""
    stream = "".join(canonical_json(record) for record in records)
    return sha256_text(stream)


def generation_id_for(
    records_hash: str, parent_generation_id: Optional[str]
) -> str:
    """Content-derived generation ID that includes the parent link."""
    identity = canonical_json(
        {"records_sha256": records_hash, "parent_generation_id": parent_generation_id}
    )
    return "gen-" + sha256_text(identity)[:16]


def build_checkpoint(
    *,
    records_sha256: str,
    record_count: int,
    source_manifest_sha256: str,
    ephemeral_policy_version: str,
    publication_authority: str = "not_assessed",
    parent_generation_id: Optional[str] = None,
    receipt_hashes: Optional[Mapping[str, str]] = None,
    delta_summary: Optional[Mapping[str, Any]] = None,
    created_at_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a validated ``uriel.checkpoint.v1`` record."""
    generation_id = generation_id_for(records_sha256, parent_generation_id)
    record: Dict[str, Any] = {
        "schema": CHECKPOINT_SCHEMA,
        "generation_id": generation_id,
        "parent_generation_id": parent_generation_id,
        "source_manifest_sha256": source_manifest_sha256,
        "records_sha256": records_sha256,
        "record_count": record_count,
        "ephemeral_policy_version": ephemeral_policy_version,
        "publication_authority": publication_authority,
        "created_at_utc": created_at_utc or utc_now(),
        "receipt_hashes": dict(receipt_hashes or {}),
        "delta_summary": dict(delta_summary or {}),
    }
    violations = validate_checkpoint(record)
    if violations:
        raise GenerationRefusal("invalid checkpoint: " + "; ".join(violations))
    return record


def write_checkpoint(store_dir: Path, record: Mapping[str, Any]) -> Path:
    """Atomically write one immutable checkpoint record.

    Refuses to replace an existing record with different content. An exact
    replay of identical bytes is idempotent and returns the existing path.
    """
    violations = validate_checkpoint(record)
    if violations:
        raise GenerationRefusal("invalid checkpoint: " + "; ".join(violations))
    target = store_dir / f"{record['generation_id']}.json"
    if target.exists():
        existing = read_json(target)
        if existing == dict(record):
            return target
        raise GenerationRefusal(
            f"generation {record['generation_id']} already exists with different content"
        )
    store_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, canonical_json(record))
    return target


def load_checkpoint(path: Path) -> Dict[str, Any]:
    """Read and validate a checkpoint record from disk."""
    record = read_json(path)
    violations = validate_checkpoint(record)
    if violations:
        raise GenerationRefusal(
            f"{path.name} failed validation: " + "; ".join(violations)
        )
    return record
