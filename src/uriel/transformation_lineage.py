"""Transformation lineage tracking (TRANSFORM-001..002).

Tracks ordered transformation steps, tool versions, parameters, lossiness disclosure,
and input/output hash bindings.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import Refusal, canonical_json, sha256_text


def build_transform_step(
    step_name: str,
    tool: str,
    version: str,
    parameters: Mapping[str, Any],
    input_sha256: str,
    output_sha256: str,
    *,
    is_lossy: bool = False,
    lossiness_description: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an ordered, hash-bound transformation lineage record."""
    if is_lossy and not lossiness_description:
        raise Refusal("Lossy transformation step requires a lossiness_description.", code="TRANSFORM_LOSSY_DESCR_MISSING")

    step = {
        "step_name": str(step_name),
        "tool": str(tool),
        "version": str(version),
        "parameters": dict(parameters),
        "input_sha256": str(input_sha256),
        "output_sha256": str(output_sha256),
        "lossy": bool(is_lossy),
        "lossiness_description": lossiness_description if is_lossy else None,
    }
    step["step_sha256"] = sha256_text(canonical_json(step))
    return step


def verify_transform_chain(steps: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    """Verify that a chain of transformation steps has matching contiguous input/output hashes."""
    if not steps:
        return {"valid": True, "step_count": 0, "discontinuities": []}

    discontinuities = []
    for i in range(len(steps) - 1):
        curr_out = steps[i].get("output_sha256")
        next_in = steps[i + 1].get("input_sha256")
        if curr_out != next_in:
            discontinuities.append({
                "step_index": i,
                "current_step": steps[i].get("step_name"),
                "next_step": steps[i + 1].get("step_name"),
                "current_output_sha256": curr_out,
                "next_input_sha256": next_in,
            })

    return {
        "valid": len(discontinuities) == 0,
        "step_count": len(steps),
        "discontinuities": discontinuities,
        "status": "PASS" if not discontinuities else "FAIL_TRANSFORM_DISCONTINUITY",
    }
