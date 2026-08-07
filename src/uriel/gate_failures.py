"""Failure taxonomy and constructive response templates (STRICT_BLESSING_CONTRACT.md 3, 4, 7).

Maps deterministic audit finding codes onto the contract's strict failure
statuses and severity classes, and renders the constructive failure responses
required by sections 7.3 (refutation), 7.4 (incomplete), and 7.5 (contradiction).
"""
from __future__ import annotations

from typing import Any, Dict, Mapping, Optional

# Audit finding codes -> strict failure status.
AUDIT_TO_FAILURE: Mapping[str, str] = {
    # Gate 1 — Novelty & Clarity
    "QUESTION_UNDERSPECIFIED": "FAIL_INCOMPLETE",
    "HYPOTHESIS_UNDERSPECIFIED": "FAIL_INCOMPLETE",
    "FALSIFIER_MISSING": "FAIL_UNTESTABLE",
    "OPERATIONAL_DEFINITIONS_MISSING": "FAIL_INCOMPLETE",
    "SUCCESS_CRITERIA_MISSING": "FAIL_UNTESTABLE",
    "SCOPE_BOUNDARIES_MISSING": "FAIL_INCOMPLETE",
    "LOADED_FRAMING": "FRAMING_PREDETERMINES_RESULT",
    "COMPETING_FRAME_MISSING": "FAIL_INCOMPLETE",
    "NEUTRAL_FRAME_MISSING": "FAIL_INCOMPLETE",
    "NOVELTY_SEARCH_NOT_STARTED": "FAIL_NOVELTY_NOT_ESTABLISHED",
    "NOVELTY_SEARCH_INCOMPLETE": "FAIL_NOVELTY_NOT_ESTABLISHED",
    "NOVELTY_SEARCH_THIN": "FAIL_NOVELTY_NOT_ESTABLISHED",
    "NEGATIVE_SEARCH_MISSING": "FAIL_NOVELTY_NOT_ESTABLISHED",
    "GLOBAL_NOVELTY_OVERCLAIM": "FAIL_SCOPE_MISMATCH",
    "UNBOUNDED_CERTAINTY": "FAIL_SCOPE_MISMATCH",
    "VAGUE_EVALUATIVE_TERM": "FAIL_INCOMPLETE",
    "DUPLICATE_CLAIM": "FAIL_CONTRADICTORY",
    "PLACEHOLDER_LANGUAGE": "FAIL_INCOMPLETE",
    "SCHEMA_STRUCTURE": "BLOCKED_MISSING_ARTIFACT",
    "POPULARITY_AS_EVIDENCE": "FRAMING_PREDETERMINES_RESULT",
    "AUTHORITY_AS_PROOF": "FRAMING_PREDETERMINES_RESULT",
    "AD_HOMINEM": "FRAMING_PREDETERMINES_RESULT",
    "FALSE_DILEMMA": "FRAMING_PREDETERMINES_RESULT",
    "CIRCULAR_SUPPORT": "FRAMING_PREDETERMINES_RESULT",
    "ABSENCE_AS_PROOF": "FRAMING_PREDETERMINES_RESULT",
    # Gate 2 — Evidence & Citation
    "CLAIMS_MISSING": "FAIL_INCOMPLETE",
    "CLAIM_INCOMPLETE": "FAIL_INCOMPLETE",
    "CLAIM_UNSUPPORTED": "FAIL_UNSUPPORTED",
    "CLAIM_SCOPE_INCOMPLETE": "FAIL_SCOPE_MISMATCH",
    "CLAIM_FALSIFIER_MISSING": "FAIL_UNTESTABLE",
    "EVIDENCE_MISSING": "FAIL_INCOMPLETE",
    "EVIDENCE_ARTIFACT_MISSING": "FAIL_INCOMPLETE",
    "EVIDENCE_HASH_MISMATCH": "FAIL_TAMPERED",
    "EVIDENCE_DECLARED_DIGEST_MISMATCH": "FAIL_TAMPERED",
    "EVIDENCE_NOT_MANIFESTED": "FAIL_TAMPERED",
    "EVIDENCE_PATH_INVALID": "FAIL_INCOMPLETE",
    "UNKNOWN_EVIDENCE_REFERENCE": "FAIL_INCOMPLETE",
    "UNRECONCILED_EVIDENCE_ROLE": "FAIL_INCOMPLETE",
    "MAJOR_CLAIM_LACKS_DIRECT_PRIMARY_EVIDENCE": "FAIL_UNSUPPORTED",
    "SECONDARY_ONLY_SUPPORT": "FAIL_UNSUPPORTED",
    "CAUSAL_CLAIM_FROM_OBSERVATIONAL_EVIDENCE": "FAIL_UNSUPPORTED",
    "DUPLICATE_CITATION_SOURCE": "FAIL_CONTRADICTORY",
    "ATTESTATION_ALL_KNOWN_MATERIAL_DATA_DECLARED": "FAIL_INCOMPLETE",
    "ATTESTATION_CITATIONS_CHECKED_AGAINST_SOURCES": "FAIL_INCOMPLETE",
    "ATTESTATION_NO_CLAIM_RELIES_ONLY_ON_ANOTHER_AUTHORS_CONCLUSION": "FAIL_UNSUPPORTED",
    "SOURCE_LOCATOR_MISSING": "FAIL_INCOMPLETE",
    "DATA_LOCATION_MISSING": "FAIL_INCOMPLETE",
    "DIRECT_EXTRACTION_MISSING": "FAIL_INCOMPLETE",
    "INTERPRETATION_MISSING": "FAIL_INCOMPLETE",
    "EVIDENCE_LIMITATIONS_MISSING": "FAIL_INCOMPLETE",
    "FRESH_PASS_RECEIPT_MISSING": "FAIL_STALE",
    "RECEIPT_DAMAGED": "FAIL_TAMPERED",
    "REPRODUCIBILITY_COMMAND_MISSING": "FAIL_REPRODUCIBILITY",
    # Gate 3 — Adversarial Integrity
    "ADVERSARIAL_TEST_INCOMPLETE": "FAIL_ADVERSARIAL",
    "ADVERSARIAL_TEST_NOT_RESOLVED": "FAIL_ADVERSARIAL",
    "CONTRADICTION_UNRESOLVED": "FAIL_CONTRADICTORY",
    "COUNTEREVIDENCE_UNRECONCILED": "FAIL_CONTRADICTORY",
    "CONTROLS_MISSING": "FAIL_ADVERSARIAL",
    "SAMPLE_SIZE_MISSING": "FAIL_ADVERSARIAL",
    "ALTERNATIVE_EXPLANATIONS_MISSING": "FAIL_ADVERSARIAL",
    "ADVERSARIAL_TESTS_MISSING": "FAIL_ADVERSARIAL",
    "REVIEWER_OBJECTIONS_MISSING": "FAIL_INCOMPLETE",
    "LIMITATIONS_MISSING": "FAIL_INCOMPLETE",
    "STUDY_DESIGN_MISSING": "FAIL_INCOMPLETE",
    "POPULATION_MISSING": "FAIL_INCOMPLETE",
    "SAMPLING_MISSING": "FAIL_INCOMPLETE",
    "ANALYSIS_PLAN_MISSING": "FAIL_INCOMPLETE",
    "EFFECT_SIZE_MISSING": "FAIL_INCOMPLETE",
    "UNCERTAINTY_METHOD_MISSING": "FAIL_INCOMPLETE",
    "MISSING_DATA_PLAN": "FAIL_INCOMPLETE",
    "ASSUMPTIONS_UNDECLARED": "FAIL_INCOMPLETE",
    "ASSUMPTION_INCOMPLETE": "FAIL_INCOMPLETE",
    "EXCLUSIONS_UNDECLARED": "FAIL_INCOMPLETE",
    "ETHICS_STATUS_MISSING": "FAIL_INCOMPLETE",
    "ETHICS_RISK_UNMITIGATED": "FAIL_ADVERSARIAL",
    "NEGATIVE_RESULTS_ATTESTATION_MISSING": "FAIL_INCOMPLETE",
    "SUBMISSION_METADATA_INCOMPLETE": "FAIL_INCOMPLETE",
    "MANDATORY_GATE_WAIVER_REFUSED": "BLOCKED_MISSING_ACCESS",
    "TOTAL_EVIDENCE_ROLE_CONFLICT": "FAIL_CONTRADICTORY",
}

# Contract failure codes -> (severity, failure class group).
FAILURE_TAXONOMY: Mapping[str, Dict[str, Any]] = {
    "FAIL_REFUTED": {"severity": "FATAL", "group": "refuted"},
    "FAIL_INCOMPLETE": {"severity": "BLOCKING", "group": "incomplete"},
    "FAIL_CONTRADICTORY": {"severity": "BLOCKING", "group": "contradictory"},
    "FAIL_UNTESTABLE": {"severity": "BLOCKING", "group": "untestable"},
    "FAIL_UNSUPPORTED": {"severity": "BLOCKING", "group": "unsupported"},
    "FAIL_STALE": {"severity": "BLOCKING", "group": "stale"},
    "FAIL_TAMPERED": {"severity": "FATAL", "group": "tampered"},
    "FAIL_DATA_NOT_READY": {"severity": "BLOCKING", "group": "incomplete"},
    "FAIL_ADVERSARIAL": {"severity": "BLOCKING", "group": "adversarial"},
    "FAIL_SCOPE_MISMATCH": {"severity": "SCOPE_LIMITING", "group": "incomplete"},
    "FAIL_NOVELTY_NOT_ESTABLISHED": {"severity": "BLOCKING", "group": "incomplete"},
    "FAIL_REPRODUCIBILITY": {"severity": "BLOCKING", "group": "incomplete"},
    "FRAMING_PREDETERMINES_RESULT": {"severity": "BLOCKING", "group": "framing"},
    "BLOCKED_MISSING_ACCESS": {"severity": "BLOCKING", "group": "blocked"},
    "BLOCKED_MISSING_ARTIFACT": {"severity": "BLOCKING", "group": "blocked"},
    "BLOCKED_AMBIGUOUS_IDENTITY": {"severity": "BLOCKING", "group": "blocked"},
    "BLOCKED_AMBIGUOUS_DEFINITION": {"severity": "BLOCKING", "group": "blocked"},
    "BLOCKED_EXTERNAL_VERIFICATION_REQUIRED": {"severity": "BLOCKING", "group": "blocked"},
    "NEEDS_CLARIFICATION": {"severity": "NONBLOCKING", "group": "clarification"},
    "NOT_APPLICABLE": {"severity": "NONBLOCKING", "group": "not_applicable"},
}

FAILURE_GROUPS = (
    "refuted",
    "incomplete",
    "contradictory",
    "untestable",
    "unsupported",
    "stale",
    "tampered",
    "adversarial",
    "blocked",
    "framing",
    "clarification",
    "not_applicable",
)


def classify_failure(finding_code: str) -> Dict[str, str]:
    """Map an audit finding code to (status, severity, group) deterministically."""
    status = AUDIT_TO_FAILURE.get(finding_code)
    if status is None:
        status = "FAIL_UNSUPPORTED"
    meta = FAILURE_TAXONOMY.get(status, {"severity": "BLOCKING", "group": "unsupported"})
    return {"status": status, "severity": meta["severity"], "group": meta["group"]}


def constructive_response(group: str, *, claim: str = "", evidence: str = "") -> Dict[str, Any]:
    """Section 7.3/7.4/7.5 constructive response scaffolding for a failure."""
    claim_text = claim or "[the declared claim]"
    evidence_text = evidence or "[the exact refuting or missing evidence]"
    if group == "refuted":
        items = [
            "exact refuting evidence: " + evidence_text,
            "why it refutes the declared claim",
            "whether any subclaim remains supported",
            "whether a measurement or sorting defect is still plausible",
            "tests needed to distinguish refutation from a data defect",
            "the smallest honest claim that survives",
            "the best pivot options",
            "the new evidence or experiment required",
        ]
        narrowing = (
            "A refuted claim must not be relabeled, averaged away, relabeled as an "
            "outlier, silently narrowed, or cherry-picked. Any narrowed claim becomes "
            "a new version and must restart the relevant gates."
        )
    elif group == "incomplete":
        items = [
            "missing item",
            "why it is required",
            "whether it is obtainable",
            "minimum acceptable replacement",
            "exact collection, import, or sorting method",
            "what Uriel can prepare automatically",
            "what only the user or researcher can provide",
            "completion condition",
            "recheck command",
        ]
        narrowing = "'Not provided' may not be treated as 'probably fine'."
    elif group == "contradictory":
        items = [
            "the verified data preparation or sorting error",
            "different declared scopes for the conflicting sources",
            "a predeclared synthesis method",
            "a narrower honest claim that incorporates the contradiction",
            "rejection of the claim with the contradiction recorded",
        ]
        narrowing = "Uriel must not collapse a contradiction into a vague average or prose compromise."
    else:
        items = [
            "observed fact",
            "why it matters for the declared claim",
            "what remains valid",
            "minimum repair",
            "preferred repair",
            "completion condition",
            "verification command",
        ]
        narrowing = "The failure is a project state, not a judgment of the person."
    return {"group": group, "required_items": items, "minimum_repair": items[0],
            "governance_note": narrowing, "claim": claim_text, "evidence": evidence_text}


def nonblocking_conditions_met(limitations: Any) -> bool:
    """Section 1 five-condition gate for a nonblocking limitation."""
    if not isinstance(limitations, list) or not limitations:
        return False
    for row in limitations:
        if not isinstance(row, Mapping):
            return False
        if not row.get("scope_excludes_affected"):
            return False
        if not row.get("recorded_in_payload"):
            return False
        if not row.get("deterministic_rule"):
            return False
        if not row.get("independent_verifier_confirms"):
            return False
    return True
