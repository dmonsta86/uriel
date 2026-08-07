"""Claim types and minimum evidence floors (STRICT_BLESSING_CONTRACT & ASSURANCE ADDENDUM).

Categorizes claims into explicit claim classes and enforces versioned minimum
evidence floors.  When an evidence floor is unmet, Uriel narrows or reclassifies
the claim automatically instead of overclaiming.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import Refusal, canonical_json, canonical_root, sha256_text

CLAIM_CLASSES = (
    "causal",
    "associational",
    "mechanistic",
    "measurement",
    "classification",
    "descriptive",
)

MINIMUM_EVIDENCE_FLOORS: Dict[str, Dict[str, Any]] = {
    "causal": {
        "version": 1,
        "required_evidence_roles": ["primary", "control_comparison", "falsification_test"],
        "minimum_independent_sources": 2,
        "requires_reproducibility_command": True,
        "requires_pre_registration_or_analysis_plan": True,
        "allows_observational_only": False,
    },
    "associational": {
        "version": 1,
        "required_evidence_roles": ["primary", "control_comparison"],
        "minimum_independent_sources": 1,
        "requires_reproducibility_command": True,
        "requires_pre_registration_or_analysis_plan": False,
        "allows_observational_only": True,
    },
    "mechanistic": {
        "version": 1,
        "required_evidence_roles": ["primary", "step_verification"],
        "minimum_independent_sources": 1,
        "requires_reproducibility_command": True,
        "requires_pre_registration_or_analysis_plan": False,
        "allows_observational_only": False,
    },
    "measurement": {
        "version": 1,
        "required_evidence_roles": ["primary", "calibration_record"],
        "minimum_independent_sources": 1,
        "requires_reproducibility_command": True,
        "requires_pre_registration_or_analysis_plan": False,
        "allows_observational_only": True,
    },
    "classification": {
        "version": 1,
        "required_evidence_roles": ["primary", "taxonomy_definition"],
        "minimum_independent_sources": 1,
        "requires_reproducibility_command": False,
        "requires_pre_registration_or_analysis_plan": False,
        "allows_observational_only": True,
    },
    "descriptive": {
        "version": 1,
        "required_evidence_roles": ["primary"],
        "minimum_independent_sources": 1,
        "requires_reproducibility_command": False,
        "requires_pre_registration_or_analysis_plan": False,
        "allows_observational_only": True,
    },
}


def classify_claim_type(statement: str, declared_type: Optional[str] = None) -> Dict[str, Any]:
    """Determine the claim class, inferring from statement keywords if not declared."""
    statement_clean = str(statement).strip()
    if declared_type:
        declared_clean = str(declared_type).lower().strip()
        if declared_clean not in CLAIM_CLASSES:
            raise Refusal(
                "Unknown claim class '{0}'.".format(declared_type),
                code="CLAIM_CLASS_UNKNOWN",
                repairs=["Choose one of: {0}.".format(", ".join(CLAIM_CLASSES))],
            )
        claim_class = declared_clean
    else:
        lower = statement_clean.lower()
        if any(w in lower for w in ("cause", "causes", "caused", "leads to", "effect of", "impact of")):
            claim_class = "causal"
        elif any(w in lower for w in ("associated with", "correlated with", "linked to", "predicts")):
            claim_class = "associational"
        elif any(w in lower for w in ("mechanism", "pathway", "mediates", "via")):
            claim_class = "mechanistic"
        elif any(w in lower for w in ("measures", "measured", "rate of", "level of", "quantity")):
            claim_class = "measurement"
        elif any(w in lower for w in ("is a", "classified as", "category", "belongs to")):
            claim_class = "classification"
        else:
            claim_class = "descriptive"

    floor = MINIMUM_EVIDENCE_FLOORS[claim_class]
    return {
        "claim_class": claim_class,
        "floor": floor,
        "statement": statement_clean,
    }


def evaluate_claim_evidence_floor(
    claim: Mapping[str, Any],
    evidence_rows: Sequence[Mapping[str, Any]],
    methods: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Check whether a claim satisfies the minimum evidence floor for its class."""
    statement = str(claim.get("statement", ""))
    declared = claim.get("claim_class") or claim.get("type")
    info = classify_claim_type(statement, declared_type=str(declared) if declared else None)
    claim_class = info["claim_class"]
    floor = info["floor"]

    provided_roles = {str(row.get("role", "")).lower() for row in evidence_rows}
    missing_roles = [role for role in floor["required_evidence_roles"] if role not in provided_roles]

    reproducibility = (methods or {}).get("reproducibility_command") if methods else None
    lacks_reproducibility = floor["requires_reproducibility_command"] and not reproducibility

    independent_count = len({(str(r.get("artifact_path")), str(r.get("source_locator"))) for r in evidence_rows if r.get("primary")})
    lacks_sources = independent_count < floor["minimum_independent_sources"]

    met = not (missing_roles or lacks_reproducibility or lacks_sources)

    narrowed_class = claim_class
    narrowing_reason = None
    if not met:
        if claim_class == "causal":
            narrowed_class = "associational"
            narrowing_reason = "Causal evidence floor unmet (missing: {0}); narrowed to associational claim.".format(
                ", ".join(missing_roles or ["reproducibility/sources"])
            )
        elif claim_class == "associational":
            narrowed_class = "descriptive"
            narrowing_reason = "Associational floor unmet; narrowed to descriptive observation."

    return {
        "claim_id": claim.get("id"),
        "declared_class": claim_class,
        "effective_class": narrowed_class if not met else claim_class,
        "met": met,
        "missing_roles": missing_roles,
        "lacks_reproducibility": lacks_reproducibility,
        "independent_sources_count": independent_count,
        "minimum_sources_required": floor["minimum_independent_sources"],
        "narrowed": not met and narrowed_class != claim_class,
        "narrowing_reason": narrowing_reason,
    }
