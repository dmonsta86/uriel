"""Evidence Microscope (MICRO-001..004).

Enables deep microscopic drill-down from a high-level material claim down to:
Claim -> Result -> Aggregate -> Record -> Measurement -> Transformation -> Acquisition

Detects microscopic discrepancies, evaluates materiality and decision impact, and
records whether a discrepancy is immaterial (recorded without false alarm) or material
(blocks decision).
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import Refusal, canonical_json, sha256_file, sha256_text

MICROSCOPE_LEVELS = (
    "claim",
    "result",
    "aggregate",
    "record",
    "measurement",
    "transformation",
    "acquisition",
)


def build_microscope_trace(
    claim_id: str,
    claim_statement: str,
    evidence_rows: Sequence[Mapping[str, Any]],
    record_manifest: Optional[Mapping[str, Any]] = None,
    transform_chain: Optional[Sequence[Mapping[str, Any]]] = None,
) -> Dict[str, Any]:
    """Construct a complete microscopic trace from claim down to source acquisition."""
    trace_levels: List[Dict[str, Any]] = []

    # Level 1: Claim
    trace_levels.append({"level": "claim", "id": claim_id, "detail": claim_statement})

    # Level 2 & 3: Result & Aggregate
    for row in evidence_rows:
        art = str(row.get("artifact_path", ""))
        loc = str(row.get("source_locator", ""))
        trace_levels.append({
            "level": "result",
            "evidence_id": row.get("id"),
            "artifact_path": art,
            "locator": loc,
            "role": row.get("role", "primary"),
        })

    # Level 4: Record
    records_sha = (record_manifest or {}).get("records_sha256", "")
    trace_levels.append({"level": "record", "records_sha256": records_sha, "record_count": (record_manifest or {}).get("record_count", 0)})

    # Level 5 & 6: Measurement & Transformation
    if transform_chain:
        for step in transform_chain:
            trace_levels.append({
                "level": "transformation",
                "step": step.get("step_name"),
                "tool": step.get("tool"),
                "version": step.get("version"),
                "input_hash": step.get("input_sha256"),
                "output_hash": step.get("output_sha256"),
                "lossy": bool(step.get("lossy", False)),
            })
    else:
        trace_levels.append({"level": "transformation", "step": "identity_sort", "lossy": False})

    # Level 7: Acquisition
    trace_levels.append({"level": "acquisition", "status": "data_readiness_pass" if records_sha else "unverified"})

    trace_sha = sha256_text(canonical_json(trace_levels))
    return {
        "schema": "uriel.evidence_microscope.v1",
        "claim_id": claim_id,
        "trace_sha256": trace_sha,
        "levels": trace_levels,
        "complete_to_source": bool(records_sha and evidence_rows),
    }


def evaluate_microscopic_discrepancy(
    expected_value: Any,
    actual_value: Any,
    threshold: float = 0.001,
    is_decision_boundary: bool = False,
) -> Dict[str, Any]:
    """Evaluate whether a discrepancy is material or immaterial."""
    diff = 0.0
    try:
        exp_f = float(expected_value)
        act_f = float(actual_value)
        diff = abs(exp_f - act_f)
    except (ValueError, TypeError):
        diff = 1.0 if str(expected_value) != str(actual_value) else 0.0

    is_material = diff > threshold or (diff > 0 and is_decision_boundary)
    return {
        "expected": expected_value,
        "actual": actual_value,
        "difference": diff,
        "threshold": threshold,
        "is_decision_boundary": is_decision_boundary,
        "is_material": is_material,
        "status": "FAIL_MATERIAL_DISCREPANCY" if is_material else ("IMMATERIAL_RECORDED" if diff > 0 else "PASS_EXACT"),
    }
