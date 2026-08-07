"""Uncertainty budget and certainty ceiling (UNCERT-001..003).

Calculates explicit uncertainty budgets, enforces certainty ceilings based on the weakest
link, and refuses uncalibrated confidence percentages.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import Refusal, canonical_json, sha256_text

CERTAINTY_LEVELS = ("high", "moderate", "low", "unquantified")


def compute_uncertainty_budget(
    claim: Mapping[str, Any],
    sources_uncertainty: Sequence[float],
    measurement_uncertainty: Optional[float] = None,
    unquantified_sources: Sequence[str] = (),
) -> Dict[str, Any]:
    """Calculate the uncertainty budget for a claim."""
    known_components = list(sources_uncertainty)
    if measurement_uncertainty is not None:
        known_components.append(measurement_uncertainty)

    total_known_variance = sum(u ** 2 for u in known_components)
    combined_standard_uncertainty = total_known_variance ** 0.5

    has_unquantified = len(unquantified_sources) > 0
    certainty_ceiling = "unquantified" if has_unquantified else ("high" if combined_standard_uncertainty < 0.05 else ("moderate" if combined_standard_uncertainty < 0.20 else "low"))

    return {
        "schema": "uriel.uncertainty_budget.v1",
        "combined_standard_uncertainty": combined_standard_uncertainty,
        "known_components": known_components,
        "unquantified_sources": list(unquantified_sources),
        "certainty_ceiling": certainty_ceiling,
        "blocks_strong_claim": certainty_ceiling in ("low", "unquantified"),
    }


def validate_confidence_percentage(
    percentage: float,
    has_calibration_evidence: bool = False,
) -> Dict[str, Any]:
    """Refuse uncalibrated confidence percentages."""
    if not (0.0 <= percentage <= 100.0):
        raise Refusal("Confidence percentage must be between 0 and 100.", code="CONFIDENCE_OUT_OF_RANGE")

    if not has_calibration_evidence:
        raise Refusal(
            "Uncalibrated confidence percentage ({0}%) refused without calibration evidence.".format(percentage),
            code="UNCALIBRATED_CONFIDENCE_REFUSED",
            repairs=[
                "Provide empirical calibration evidence or empirical frequency data.",
                "Express certainty using qualitative certainty ceilings (high/moderate/low/unquantified).",
            ],
        )

    return {
        "percentage": percentage,
        "calibrated": True,
        "status": "PASS",
    }
