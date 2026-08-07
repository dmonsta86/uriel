"""Publication-authority state records.

Implements the ``uriel.publication_authority.v1`` contract. Authority changes
only through explicit artifact language or user confirmation; a proposed AI
classification never changes authority by itself.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from .checkpoints import GenerationRefusal
from .core import Refusal, atomic_write_text, canonical_json, read_json, sha256_text, utc_now

PUBLICATION_SCHEMA = "uriel.publication_authority.v1"

PUBLICATION_STATES = (
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

AUTHORITY_SOURCES = ("deterministic_rule", "user_confirmation", "external_artifact")

AUTHORITY_IS_EXCLUSIVE = frozenset(
    {"submission_authorized", "accepted", "published"}
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class AuthorityRefusal(Refusal):
    """Raised when an authority transition is not permitted."""


def validate_authority(record: Mapping[str, Any]) -> List[str]:
    """Return human-readable violations of the publication authority v1 contract."""
    errors: List[str] = []
    if record.get("schema") != PUBLICATION_SCHEMA:
        errors.append("schema must be uriel.publication_authority.v1")
    if not isinstance(record.get("project_generation"), str) or not record.get("project_generation"):
        errors.append("project_generation must be non-empty text")
    if record.get("state") not in PUBLICATION_STATES:
        errors.append("state must be a known publication-authority state")
    if record.get("authority_source") not in AUTHORITY_SOURCES:
        errors.append("authority_source must be a known source")
    digest = record.get("source_artifact_sha256")
    if digest is not None and not (isinstance(digest, str) and _HEX64.fullmatch(digest)):
        errors.append("source_artifact_sha256 must be a SHA-256 hex digest or null")
    if not isinstance(record.get("recorded_at_utc"), str) or not record.get("recorded_at_utc"):
        errors.append("recorded_at_utc must be non-empty text")
    if record.get("state") in AUTHORITY_IS_EXCLUSIVE and record.get("authority_source") == "deterministic_rule":
        errors.append(f"state {record['state']} cannot come from a deterministic rule alone")
    return errors


def authority_id_for(project_generation: str, state: str) -> str:
    identity = canonical_json({"project_generation": project_generation, "state": state})
    return "authority-" + sha256_text(identity)[:16]


def build_authority(
    *,
    project_generation: str,
    state: str,
    authority_source: str,
    source_artifact_sha256: Optional[str] = None,
    notes: str = "",
    recorded_at_utc: Optional[str] = None,
) -> Dict[str, Any]:
    record: Dict[str, Any] = {
        "schema": PUBLICATION_SCHEMA,
        "project_generation": project_generation,
        "state": state,
        "authority_source": authority_source,
        "source_artifact_sha256": source_artifact_sha256,
        "notes": notes,
        "recorded_at_utc": recorded_at_utc or utc_now(),
    }
    violations = validate_authority(record)
    if violations:
        raise AuthorityRefusal("invalid publication authority: " + "; ".join(violations))
    return record


def write_authority(store_dir: Path, record: Mapping[str, Any]) -> Path:
    """Atomically write one immutable publication-authority record."""
    violations = validate_authority(record)
    if violations:
        raise AuthorityRefusal("invalid publication authority: " + "; ".join(violations))
    generation = record["project_generation"]
    target = store_dir / f"{authority_id_for(generation, record['state'])}.json"
    if target.exists():
        existing = read_json(target)
        if existing == dict(record):
            return target
        raise AuthorityRefusal(
            f"authority {target.stem} already exists with different content"
        )
    store_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, canonical_json(record))
    return target


def transition_for_decision(decision_class: str) -> Optional[str]:
    """Deterministic decision-class to authority-state transition map.

    Returns None when a decision does not change authority (acknowledged,
    review invitation, unknown).
    """
    mapping: Dict[str, Optional[str]] = {
        "acknowledged": None,
        "submitted": "submitted",
        "administrative_check": "submitted",
        "under_review": "submitted",
        "review_invitation": None,
        "major_revision": "revision_required",
        "minor_revision": "revision_required",
        "revise_and_resubmit": "revision_required",
        "conditional_acceptance": "conditionally_accepted",
        "accepted": "accepted",
        "accepted_in_production": "production_ready",
        "proofs_received": "production_ready",
        "published": "published",
        "desk_rejection": "not_ready",
        "rejected_with_feedback": "not_ready",
        "rejected_resubmit_elsewhere": "resubmission_ready",
        "withdrawn": "withdrawn",
        "unknown": None,
    }
    return mapping.get(decision_class)


def authority_source_for(confirmation_state: str, source_sha256: Optional[str]) -> str:
    if confirmation_state == "user_confirmed":
        return "user_confirmation"
    if source_sha256:
        return "external_artifact"
    return "deterministic_rule"
