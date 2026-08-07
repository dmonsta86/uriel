"""Submission decision import and classification.

Implements the ``uriel.decision_import.v1`` contract. Decision classes are
inferred from explicit status language by deterministic keyword rules; the
inference is always recorded as a proposal (``proposed_unconfirmed``) until
the language is explicit or the user confirms the class. No inference ever
changes publication authority by itself.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from .checkpoints import GenerationRefusal
from .core import Refusal, atomic_write_text, canonical_json, read_json, sha256_bytes, sha256_file, sha256_text, utc_now

DECISION_SCHEMA = "uriel.decision_import.v1"

DECISION_CLASSES = (
    "acknowledged",
    "submitted",
    "administrative_check",
    "under_review",
    "review_invitation",
    "major_revision",
    "minor_revision",
    "revise_and_resubmit",
    "conditional_acceptance",
    "accepted",
    "accepted_in_production",
    "proofs_received",
    "published",
    "desk_rejection",
    "rejected_with_feedback",
    "rejected_resubmit_elsewhere",
    "withdrawn",
    "unknown",
)

CONFIRMATION_STATES = ("explicit", "user_confirmed", "proposed_unconfirmed")

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

_AMBIGUITY_MARKERS = (
    "pending",
    "subject to",
    "may be",
    "will be in touch",
    "awaiting",
    "tentative",
    "conditional upon",
)

_RULES: Sequence[Tuple[re.Pattern[str], str, float]] = (
    (re.compile(r"invit(?:e|ed|ation).{0,40}to review", re.IGNORECASE), "review_invitation", 0.9),
    (re.compile(r"desk reject", re.IGNORECASE), "desk_rejection", 0.92),
    (re.compile(r"revise\s*(?:and|&)\s*resubmit", re.IGNORECASE), "revise_and_resubmit", 0.95),
    (re.compile(r"minor revision", re.IGNORECASE), "minor_revision", 0.95),
    (re.compile(r"major revision", re.IGNORECASE), "major_revision", 0.95),
    (re.compile(r"conditionally accepted|conditional acceptance", re.IGNORECASE), "conditional_acceptance", 0.95),
    (re.compile(r"resubmit.{0,60}(?:elsewhere|another (?:journal|venue))", re.IGNORECASE), "rejected_resubmit_elsewhere", 0.9),
    (re.compile(r"pleased to (?:inform|accept|announce)|congratulations.{0,60}accept", re.IGNORECASE), "accepted", 0.95),
    (re.compile(r"\baccept(?:ed|ance)?\b", re.IGNORECASE), "accepted", 0.8),
    (re.compile(r"in production", re.IGNORECASE), "accepted_in_production", 0.9),
    (re.compile(r"\bproofs?\b", re.IGNORECASE), "proofs_received", 0.85),
    (re.compile(r"\bpublished\b", re.IGNORECASE), "published", 0.9),
    (re.compile(r"under review", re.IGNORECASE), "under_review", 0.9),
    (re.compile(r"administrative check|technical check|quality check", re.IGNORECASE), "administrative_check", 0.85),
    (re.compile(r"reject(?:ed|ion)?", re.IGNORECASE), "rejected_with_feedback", 0.7),
    (re.compile(r"withdraw(?:n|al)?", re.IGNORECASE), "withdrawn", 0.9),
    (re.compile(r"\bsubmitted\b", re.IGNORECASE), "submitted", 0.8),
    (re.compile(r"acknowledge", re.IGNORECASE), "acknowledged", 0.6),
)

_EXPLICIT_THRESHOLD = 0.85


class DecisionRefusal(Refusal):
    """Raised when a decision record is invalid or would be overwritten."""


def infer_decision(text: str) -> Tuple[str, float, List[str]]:
    """Infer a decision class from explicit status language.

    Returns (decision_class, confidence, matched_phrases). The result is a
    proposal only; it never changes publication authority by itself.
    """
    lowered = text.lower()
    matches: List[str] = []
    for pattern, decision_class, confidence in _RULES:
        found = pattern.search(lowered)
        if found:
            matches.append(found.group(0))
            return decision_class, confidence, matches
    return "unknown", 0.0, []


def _ambiguities(text: str) -> List[str]:
    lowered = text.lower()
    return [marker for marker in _AMBIGUITY_MARKERS if marker in lowered]


def validate_decision_import(record: Mapping[str, Any]) -> List[str]:
    errors: List[str] = []
    if record.get("schema") != DECISION_SCHEMA:
        errors.append("schema must be uriel.decision_import.v1")
    for field in ("decision_id", "source_sha256"):
        value = record.get(field)
        if not isinstance(value, str) or not value:
            errors.append(f"{field} must be non-empty text")
    digest = record.get("source_sha256")
    if not (isinstance(digest, str) and _HEX64.fullmatch(digest)):
        errors.append("source_sha256 must be a SHA-256 hex digest")
    if record.get("decision_class") not in DECISION_CLASSES:
        errors.append("decision_class must be a known decision class")
    if record.get("confirmation_state") not in CONFIRMATION_STATES:
        errors.append("confirmation_state must be explicit, user_confirmed, or proposed_unconfirmed")
    confidence = record.get("inference_confidence")
    if confidence is not None and not (isinstance(confidence, (int, float)) and 0 <= confidence <= 1):
        errors.append("inference_confidence must be between 0 and 1 or null")
    for field in ("venue", "manuscript_id", "deadline", "explicit_status_text"):
        value = record.get(field)
        if value is not None and not isinstance(value, str):
            errors.append(f"{field} must be text or null")
    ambiguities = record.get("unresolved_ambiguity")
    if ambiguities is not None and not isinstance(ambiguities, list):
        errors.append("unresolved_ambiguity must be an array")
    return errors


def decision_id_for(source_sha256: str, decision_class: str, confirmation_state: str) -> str:
    identity = canonical_json(
        {"source_sha256": source_sha256, "decision_class": decision_class, "confirmation_state": confirmation_state}
    )
    return "dec-" + sha256_text(identity)[:16]


def build_decision_import(
    source_text: str,
    *,
    source_sha256: Optional[str] = None,
    venue: Optional[str] = None,
    manuscript_id: Optional[str] = None,
    deadline: Optional[str] = None,
    decision_class: Optional[str] = None,
    user_confirmed: bool = False,
    created_at_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """Build a validated decision-import record.

    When ``decision_class`` is supplied, the class is taken verbatim and the
    confirmation state is ``user_confirmed`` (or ``explicit`` when
    ``user_confirmed`` is also False and the caller asserts explicit
    language). Without it, the class is inferred and recorded as a proposal
    unless the inferred confidence clears the explicit threshold.
    """
    if not source_text.strip():
        raise DecisionRefusal("source_text must not be empty")
    digest = source_sha256 or sha256_text(source_text)
    if decision_class is not None and decision_class not in DECISION_CLASSES:
        raise DecisionRefusal(f"unknown decision class: {decision_class}")
    if decision_class is not None:
        inferred, confidence, matches = decision_class, None, []
        if user_confirmed:
            confirmation = "user_confirmed"
        else:
            confirmation = "explicit"
    else:
        inferred, confidence, matches = infer_decision(source_text)
        confirmation = "explicit" if confidence >= _EXPLICIT_THRESHOLD else "proposed_unconfirmed"
    record: Dict[str, Any] = {
        "schema": DECISION_SCHEMA,
        "decision_id": decision_id_for(digest, inferred, confirmation),
        "source_sha256": digest,
        "decision_class": inferred,
        "confirmation_state": confirmation,
        "inference_confidence": confidence,
        "venue": venue,
        "manuscript_id": manuscript_id,
        "deadline": deadline,
        "explicit_status_text": source_text.strip()[:500],
        "unresolved_ambiguity": _ambiguities(source_text),
        "created_at_utc": created_at_utc or utc_now(),
    }
    if matches:
        record["inference_matches"] = matches
    violations = validate_decision_import(record)
    if violations:
        raise DecisionRefusal("invalid decision import: " + "; ".join(violations))
    return record


def write_decision(store_dir: Path, record: Mapping[str, Any]) -> Path:
    """Atomically write one immutable decision-import record."""
    violations = validate_decision_import(record)
    if violations:
        raise DecisionRefusal("invalid decision import: " + "; ".join(violations))
    target = store_dir / f"{record['decision_id']}.json"
    if target.exists():
        existing = read_json(target)
        if existing == dict(record):
            return target
        raise DecisionRefusal(f"decision {record['decision_id']} already exists with different content")
    store_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(target, canonical_json(record))
    return target


def load_decision(path: Path) -> Dict[str, Any]:
    record = read_json(path)
    violations = validate_decision_import(record)
    if violations:
        raise DecisionRefusal(f"{path.name} failed validation: " + "; ".join(violations))
    return record


def confirm_decision(record: Mapping[str, Any], decision_class: str) -> Dict[str, Any]:
    """Return a new immutable record with a user-confirmed decision class."""
    if decision_class not in DECISION_CLASSES:
        raise DecisionRefusal(f"unknown decision class: {decision_class}")
    return build_decision_import(
        str(record.get("explicit_status_text", "")),
        source_sha256=record["source_sha256"],
        venue=record.get("venue"),
        manuscript_id=record.get("manuscript_id"),
        deadline=record.get("deadline"),
        decision_class=decision_class,
        user_confirmed=True,
    )
