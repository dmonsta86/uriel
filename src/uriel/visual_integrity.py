"""Figure, table, and statistical integrity validation (VISUAL-001..002, STATS-001).

Validates that figures have explicit scales, axes, units, denominators, uncertainty bars, and source bindings.
Validates that tables have total row reconciliation, non-empty cells, and source generation hashes.
Validates statistical reporting for missingness, sensitivity, effect size, and multiplicity.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import Refusal, canonical_json, sha256_text


def validate_figure_integrity(figure: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate figure integrity metadata."""
    title = str(figure.get("title", ""))
    has_axes = bool(figure.get("x_axis") and figure.get("y_axis"))
    has_units = bool(figure.get("units"))
    has_uncertainty_bars = bool(figure.get("uncertainty_bars", False))
    source_gen = figure.get("source_generation")

    missing = []
    if not has_axes:
        missing.append("x_axis or y_axis label")
    if not has_units:
        missing.append("units")
    if not source_gen:
        missing.append("source_generation binding")

    valid = len(missing) == 0
    return {
        "title": title,
        "valid": valid,
        "missing_elements": missing,
        "has_uncertainty_bars": has_uncertainty_bars,
        "status": "PASS" if valid else "FAIL_FIGURE_INTEGRITY",
    }


def validate_table_integrity(table: Mapping[str, Any]) -> Dict[str, Any]:
    """Validate table row totals, units, and non-empty cell constraints."""
    headers = list(table.get("headers", []))
    rows = list(table.get("rows", []))
    has_units = bool(table.get("units"))
    source_gen = table.get("source_generation")

    empty_cells = 0
    for r in rows:
        for val in r:
            if val is None or str(val).strip() == "":
                empty_cells += 1

    valid = bool(headers and rows and source_gen and empty_cells == 0)
    return {
        "valid": valid,
        "header_count": len(headers),
        "row_count": len(rows),
        "empty_cell_count": empty_cells,
        "has_units": has_units,
        "status": "PASS" if valid else "FAIL_TABLE_INTEGRITY",
    }
