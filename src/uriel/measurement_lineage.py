"""Measurement lineage and unit validation (MEASURE-001..002).

Records measurement metadata (units, resolution, calibration, uncertainty, collection method)
and detects unit, dimension, timezone, and scale mismatches.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import Refusal, canonical_json, sha256_text

VALID_UNITS = {
    "count": "dimensionless",
    "percent": "ratio",
    "fraction": "ratio",
    "seconds": "time",
    "milliseconds": "time",
    "meters": "length",
    "kilograms": "mass",
    "usd": "currency",
}


def build_measurement_record(
    value: Any,
    unit: str,
    *,
    resolution: Optional[float] = None,
    calibration_date: Optional[str] = None,
    uncertainty: Optional[float] = None,
    timezone_name: Optional[str] = "UTC",
) -> Dict[str, Any]:
    """Create a structured measurement record with explicit unit metadata."""
    unit_clean = str(unit).lower().strip()
    if unit_clean not in VALID_UNITS and not unit_clean.isalnum():
        raise Refusal("Invalid or unrecognized measurement unit '{0}'.".format(unit), code="MEASUREMENT_INVALID_UNIT")

    rec = {
        "value": value,
        "unit": unit_clean,
        "dimension": VALID_UNITS.get(unit_clean, "custom"),
        "resolution": resolution,
        "calibration_date": calibration_date,
        "uncertainty": uncertainty,
        "timezone": timezone_name,
    }
    rec["sha256"] = sha256_text(canonical_json(rec))
    return rec


def check_measurement_compatibility(
    meas1: Mapping[str, Any],
    meas2: Mapping[str, Any],
) -> Dict[str, Any]:
    """Detect unit, dimension, or timezone mismatch between two measurements."""
    u1, u2 = str(meas1.get("unit")), str(meas2.get("unit"))
    d1, d2 = str(meas1.get("dimension")), str(meas2.get("dimension"))
    tz1, tz2 = str(meas1.get("timezone")), str(meas2.get("timezone"))

    unit_mismatch = u1 != u2
    dimension_mismatch = d1 != d2
    tz_mismatch = tz1 != tz2 and (d1 == "time" or d2 == "time")

    # Ratio/percent mismatch check
    ratio_mismatch = (u1 == "percent" and u2 == "fraction") or (u1 == "fraction" and u2 == "percent")

    compatible = not (dimension_mismatch or unit_mismatch or tz_mismatch or ratio_mismatch)
    errors = []
    if dimension_mismatch:
        errors.append("Dimension mismatch: '{0}' vs '{1}'".format(d1, d2))
    elif unit_mismatch and not ratio_mismatch:
        errors.append("Unit mismatch: '{0}' vs '{1}'".format(u1, u2))
    if tz_mismatch:
        errors.append("Timezone mismatch: '{0}' vs '{1}'".format(tz1, tz2))
    if ratio_mismatch:
        errors.append("Percent/Fraction scale mismatch: '{0}' vs '{1}'".format(u1, u2))

    return {
        "compatible": compatible,
        "unit_mismatch": unit_mismatch,
        "dimension_mismatch": dimension_mismatch,
        "timezone_mismatch": tz_mismatch,
        "ratio_mismatch": ratio_mismatch,
        "errors": errors,
        "status": "PASS" if compatible else "FAIL_MEASUREMENT_MISMATCH",
    }
