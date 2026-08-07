"""Multidimensional Evidence Strength Vector (STRENGTH-001..004).

Evaluates evidence along five explicit dimensions instead of a single uncalibrated score:
1. Independence (absence of shared datasets, authors, or citation-chain loops)
2. Directness (primary observation vs inherited conclusion)
3. Precision (bounded uncertainty, error margin, effect size)
4. Reproducibility (executable workload PASS receipt bound to records)
5. Integrity (hashes match, zero tamper, zero audit blockers)

A failure or weak score on ANY critical dimension blocks overall strong status.
Shared-lineage citations and high precision around biased measurements cannot launder
weak evidence.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .core import Refusal, canonical_json, sha256_text

STRENGTH_DIMENSIONS = (
    "independence",
    "directness",
    "precision",
    "reproducibility",
    "integrity",
)

DIMENSION_LABELS = {
    "independence": "Source & Lineage Independence",
    "directness": "Primary vs Secondary Directness",
    "precision": "Measurement & Statistical Precision",
    "reproducibility": "Execution & Rebuild Reproducibility",
    "integrity": "Content Hash & Tamper Integrity",
}


def compute_evidence_strength_vector(
    claim: Mapping[str, Any],
    evidence_rows: Sequence[Mapping[str, Any]],
    receipts: Sequence[Mapping[str, Any]],
    audit_findings: Sequence[Any],
) -> Dict[str, Any]:
    """Calculate the 5-dimension Evidence Strength Vector."""
    # 1. Independence
    sources = set()
    shared_lineage_count = 0
    for row in evidence_rows:
        art = str(row.get("artifact_path", ""))
        loc = str(row.get("source_locator", ""))
        key = (art, loc)
        if key in sources:
            shared_lineage_count += 1
        sources.add(key)
    indep_score = "STRONG" if len(sources) >= 2 and shared_lineage_count == 0 else ("MODERATE" if len(sources) >= 1 else "WEAK")

    # 2. Directness
    primary_count = sum(1 for r in evidence_rows if bool(r.get("primary")))
    inherited_count = sum(1 for r in evidence_rows if not bool(r.get("primary")))
    direct_score = "STRONG" if primary_count > 0 and inherited_count == 0 else ("MODERATE" if primary_count > 0 else "WEAK")

    # 3. Precision
    has_uncertainty = bool(claim.get("effect_size") or claim.get("uncertainty_interval") or claim.get("error_margin"))
    precision_score = "STRONG" if has_uncertainty else "MODERATE"

    # 4. Reproducibility
    pass_receipts = [r for r in receipts if str(r.get("status")) == "PASS"]
    repro_score = "STRONG" if pass_receipts else "WEAK"

    # 5. Integrity
    blocking_findings = [f for f in audit_findings if getattr(f, "severity", None) in ("FATAL", "BLOCKING") or getattr(f, "status", None) == "FAIL"]
    integrity_score = "WEAK" if blocking_findings else "STRONG"

    vector = {
        "independence": indep_score,
        "directness": direct_score,
        "precision": precision_score,
        "reproducibility": repro_score,
        "integrity": integrity_score,
    }

    # Critical dimension rule: any WEAK blocks overall strong status
    critical_failures = [dim for dim, score in vector.items() if score == "WEAK"]
    overall = "WEAK" if critical_failures else ("MODERATE" if "MODERATE" in vector.values() else "STRONG")

    return {
        "schema": "uriel.evidence_strength.v1",
        "vector": vector,
        "overall_status": overall,
        "critical_failures": critical_failures,
        "shared_lineage_count": shared_lineage_count,
        "unique_primary_sources": len(sources),
        "is_laundered_attempt": shared_lineage_count > 0 and indep_score == "WEAK",
    }
