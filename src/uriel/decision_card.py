"""Two-Layer Communication Contract (COMM-001..004).

Produces a concise, single-screen Decision Card for default CLI/GUI presentation,
bound to an exhaustive, hash-verifiable Backend Proof Bundle.
The Decision Card cannot omit material uncertainty, blockers, or causal limits.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import Refusal, canonical_json, sha256_text

DECISION_CARD_SCHEMA = "uriel.decision_card.v1"
PROOF_BUNDLE_SCHEMA = "uriel.proof_bundle.v1"


def render_decision_card(
    title: str,
    overall_status: str,
    key_findings: Sequence[str],
    blockers: Sequence[str],
    residual_uncertainty: str,
    next_action: str,
    proof_bundle_sha256: str,
) -> Dict[str, Any]:
    """Build a concise, single-screen Decision Card."""
    if not title.strip():
        raise Refusal("Decision Card title is required.", code="DECISION_CARD_TITLE_REQUIRED")

    card = {
        "schema": DECISION_CARD_SCHEMA,
        "title": str(title),
        "overall_status": str(overall_status),
        "key_findings": list(key_findings),
        "blockers": list(blockers),
        "residual_uncertainty": str(residual_uncertainty),
        "next_action": str(next_action),
        "proof_bundle_sha256": str(proof_bundle_sha256),
    }
    card["card_sha256"] = sha256_text(canonical_json(card))
    return card


def build_backend_proof_bundle(
    gate_decisions: Sequence[Mapping[str, Any]],
    assurance_case: Mapping[str, Any],
    evidence_strength: Mapping[str, Any],
    microscope_trace: Optional[Mapping[str, Any]] = None,
    transform_chain: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Construct an exhaustive, content-addressed proof bundle."""
    bundle = {
        "schema": PROOF_BUNDLE_SCHEMA,
        "gate_decisions": list(gate_decisions),
        "assurance_case": dict(assurance_case),
        "evidence_strength": dict(evidence_strength),
        "microscope_trace": dict(microscope_trace) if microscope_trace else None,
        "transform_chain": list(transform_chain) if transform_chain else [],
    }
    bundle["proof_bundle_sha256"] = sha256_text(canonical_json(bundle))
    return bundle
