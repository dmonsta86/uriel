"""Adaptive depth policy and stopping rules (DEPTH-001..004).

Determines when deeper review is required (high-stakes, near-threshold, conflicting, weakly
corroborated claims) and enforces stopping rules based on materiality and resource budgets.
Resource exhaustion creates a continuation packet instead of false completion.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import Refusal, canonical_json, sha256_text

DEPTH_LEVELS = ("shallow", "standard", "deep", "microscopic")


def evaluate_adaptive_depth_triggers(
    claim: Mapping[str, Any],
    is_high_stakes: bool = False,
    is_near_threshold: bool = False,
    has_conflicting_observations: bool = False,
    is_weakly_corroborated: bool = False,
) -> Dict[str, Any]:
    """Evaluate whether adaptive triggers deepen the required review level."""
    triggers = []
    if is_high_stakes:
        triggers.append("high_stakes_claim")
    if is_near_threshold:
        triggers.append("near_decision_boundary")
    if has_conflicting_observations:
        triggers.append("conflicting_observations")
    if is_weakly_corroborated:
        triggers.append("weakly_corroborated")

    required_depth = "microscopic" if (is_high_stakes or is_near_threshold) else ("deep" if triggers else "standard")

    return {
        "triggers_fired": triggers,
        "required_depth": required_depth,
        "requires_microscope": required_depth == "microscopic",
    }


def evaluate_depth_stopping_rule(
    current_depth: str,
    required_depth: str,
    discrepancies: Sequence[Mapping[str, Any]],
    resources_exhausted: bool = False,
) -> Dict[str, Any]:
    """Determine whether review depth can stop or requires a continuation packet."""
    material_unresolved = [d for d in discrepancies if bool(d.get("is_material"))]

    if material_unresolved:
        return {
            "can_stop": False,
            "reason": "Material lower-level discrepancy remains unresolved.",
            "action": "DEEPEN_REVIEW",
            "status": "FAIL_MATERIAL_DISCREPANCY_UNRESOLVED",
        }

    if resources_exhausted and current_depth != required_depth:
        return {
            "can_stop": False,
            "reason": "Resource budget exhausted before reaching required depth '{0}'.".format(required_depth),
            "action": "EMIT_CONTINUATION_PACKET",
            "status": "CONTINUATION_REQUIRED",
        }

    return {
        "can_stop": True,
        "reason": "Required depth reached with zero unresolved material discrepancies.",
        "action": "SEAL_DEPTH_RECEIPT",
        "status": "PASS",
    }
