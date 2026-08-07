"""Strict Blessing contract decision engine (STRICT_BLESSING_CONTRACT.md).

Deterministic, immutable, content-addressed gate decisions.  The only
authoritative gate states are the literal ``PASS`` status plus the enumerated
failure/blocked taxonomy.  AI output, user override, and manual edits can never
write authority here; only these functions can.
"""
from __future__ import annotations

import csv
import io
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .core import Refusal, atomic_write_json, canonical_json, canonical_root, guard_path, paths_for, sha256_text, utc_now
from .data_readiness import REQUIRED_CHECKS, readiness_status

GATE_DECISION_SCHEMA = "uriel.gate_decision.v1"
GATE_FINDING_SCHEMA = "uriel.gate_finding.v1"

# Section 3: required machine-readable decision statuses.
PASS = "PASS"
FAIL_STATUSES = (
    "FAIL_REFUTED",
    "FAIL_INCOMPLETE",
    "FAIL_CONTRADICTORY",
    "FAIL_UNTESTABLE",
    "FAIL_UNSUPPORTED",
    "FAIL_STALE",
    "FAIL_TAMPERED",
    "FAIL_DATA_NOT_READY",
    "FAIL_ADVERSARIAL",
    "FAIL_SCOPE_MISMATCH",
    "FAIL_NOVELTY_NOT_ESTABLISHED",
    "FAIL_REPRODUCIBILITY",
)
BLOCKED_STATUSES = (
    "BLOCKED_MISSING_ACCESS",
    "BLOCKED_MISSING_ARTIFACT",
    "BLOCKED_AMBIGUOUS_IDENTITY",
    "BLOCKED_AMBIGUOUS_DEFINITION",
    "BLOCKED_EXTERNAL_VERIFICATION_REQUIRED",
)
NEEDS_CLARIFICATION = "NEEDS_CLARIFICATION"
NOT_APPLICABLE = "NOT_APPLICABLE"
GATE_STATUSES = (
    PASS,
    *FAIL_STATUSES,
    *BLOCKED_STATUSES,
    NEEDS_CLARIFICATION,
    NOT_APPLICABLE,
)
FAIL_CLASSES = frozenset(FAIL_STATUSES)
BLOCKED_CLASSES = frozenset(BLOCKED_STATUSES)
NON_PASS_CLASSES = frozenset(GATE_STATUSES) - {PASS}

# Section 4: required finding severity.
FATAL = "FATAL"
BLOCKING = "BLOCKING"
SCOPE_LIMITING = "SCOPE_LIMITING"
NONBLOCKING = "NONBLOCKING"
INFORMATIONAL = "INFORMATIONAL"
FINDING_SEVERITIES = (FATAL, BLOCKING, SCOPE_LIMITING, NONBLOCKING, INFORMATIONAL)
FATAL_SEVERITIES = frozenset({FATAL, BLOCKING})

# Gate 1 check IDs (contract 6.1).
GATE1_CHECKS = (
    "question_stated",
    "strongest_defensible_interpretation",
    "operational_definitions",
    "scope_explicit",
    "testable_falsifiable",
    "no_circular_definition",
    "internally_consistent",
    "no_assumed_conclusion",
    "conclusion_within_question",
    "novelty_established_or_not_claimed",
    "modular_subclaims",
    "material_ambiguity_resolved",
    "disconfirming_evidence_identifiable",
    "exact_version_clarified",
)
# Gate 2 check IDs (contract 7.2).
GATE2_CHECKS = (
    "gate0_passed_for_data_claims",
    "claim_map_complete",
    "exact_artifact_mapping",
    "artifact_hashes_match",
    "exact_supporting_locations",
    "primary_sources_used",
    "no_conclusion_substitution",
    "exact_bounded_quotes",
    "generation_bound_artifacts",
    "completeness_records",
    "conflicting_null_evidence",
    "controls_and_comparisons",
    "no_association_causation_conflation",
    "honest_effect_uncertainty_scope",
    "reproducible_from_artifacts",
    "no_stale_inaccessible_dependency",
    "no_double_counting",
    "no_secondary_promotion",
)
# Gate 3 check IDs (contract 8.1).
GATE3_CHECKS = (
    "alternative_explanations",
    "confounders",
    "control_mismatches",
    "boundary_cases",
    "contradictory_observations",
    "sensitivity_to_analytical_choices",
    "missing_data_handling",
    "no_leakage",
    "no_overfitting",
    "no_nondeterminism_platform_variation",
    "no_proxy_misuse",
    "subgroup_distributional_failures",
    "reviewer_objections",
    "material_limitations",
    "ethics_privacy_security",
    "plausible_counterexamples",
    "failure_under_changed_assumptions",
    "independent_reproducibility",
)

# Gate 0 check IDs come from the Data Readiness engine (22 mandatory checks).
GATE_SPECS: Mapping[int, Tuple[str, Tuple[str, ...]]] = {
    0: ("Data Readiness", REQUIRED_CHECKS),
    1: ("Novelty & Clarity", GATE1_CHECKS),
    2: ("Evidence & Citation", GATE2_CHECKS),
    3: ("Adversarial Integrity", GATE3_CHECKS),
}
GATE_NAMES = {number: name for number, (name, _) in GATE_SPECS.items()}


def _check(
    check_id: str,
    status: str,
    evidence: Sequence[str] = (),
    *,
    applicability_predicate: Optional[str] = None,
) -> Dict[str, Any]:
    return {
        "check_id": check_id,
        "status": status,
        "evidence": list(evidence),
        "applicability_predicate": applicability_predicate,
    }


def _status_error(status: str) -> str:
    return "Unknown gate status {0!r}; expected one of {1}".format(status, ", ".join(GATE_STATUSES))


def _validate_statuses(checks: Sequence[Mapping[str, Any]]) -> None:
    for check in checks:
        status = check.get("status")
        if status not in GATE_STATUSES:
            raise Refusal(_status_error(status), code="GATE_UNKNOWN_STATUS")
        if status == NOT_APPLICABLE and not check.get("applicability_predicate"):
            raise Refusal(
                "A check cannot self-declare NOT_APPLICABLE; a machine-checkable "
                "applicability predicate is required.",
                code="NOT_APPLICABLE_WITHOUT_PREDICATE",
                repairs=["Provide applicability_predicate or set a FAIL/BLOCKED status."],
            )


def _validate_check_ids(gate: int, checks: Sequence[Mapping[str, Any]]) -> List[str]:
    """Return the check IDs present in the gate spec but missing from the run."""
    required = GATE_SPECS[gate][1]
    seen = set(str(check.get("check_id")) for check in checks)
    return [check_id for check_id in required if check_id not in seen]


def _counts(gate: int, checks: Sequence[Mapping[str, Any]]) -> Dict[str, int]:
    return {
        "required_check_count": len(GATE_SPECS[gate][1]),
        "executed_check_count": len(checks),
        "passed_check_count": sum(1 for check in checks if check["status"] == PASS),
        "failed_check_count": sum(1 for check in checks if check["status"] in FAIL_CLASSES),
        "blocked_check_count": sum(1 for check in checks if check["status"] in BLOCKED_CLASSES),
        "not_applicable_count": sum(1 for check in checks if check["status"] == NOT_APPLICABLE),
        "unresolved_blocker_count": sum(
            1
            for check in checks
            if check["status"] in FAIL_CLASSES or check["status"] in BLOCKED_CLASSES
        ),
    }


def _decision_from_counts(checks: Sequence[Mapping[str, Any]], counts: Mapping[str, int]) -> str:
    if counts["blocked_check_count"] > 0:
        return _first_status(checks, BLOCKED_CLASSES)
    if counts["unresolved_blocker_count"] > 0:
        return _first_status(checks, FAIL_CLASSES)
    if any(check["status"] == NEEDS_CLARIFICATION for check in checks):
        return NEEDS_CLARIFICATION
    return PASS


def _first_status(checks: Sequence[Mapping[str, Any]], classes: Iterable[str]) -> str:
    by_priority = {status: index for index, status in enumerate(classes)}
    ranked = [check for check in checks if check["status"] in by_priority]
    if not ranked:
        return next(iter(classes))
    return min(ranked, key=lambda check: by_priority[check["status"]])["status"]


def decide_gate(
    gate: int,
    checks: Sequence[Mapping[str, Any]],
    *,
    binding_digest: str,
    independent_verifier_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Compute the strict gate decision.  Missing check IDs prevent PASS.

    This is the only function that produces an authoritative gate state.
    """
    if gate not in GATE_SPECS:
        raise Refusal("Unknown gate {0}".format(gate), code="GATE_UNKNOWN_GATE")
    if not checks:
        raise Refusal("Empty check output is not PASS.", code="EMPTY_CHECK_OUTPUT_NOT_PASS",
                      repairs=["Supply at least one check result per gate."])
    _validate_statuses(checks)
    missing = _validate_check_ids(gate, checks)
    if missing:
        missing_rows = [_check(check_id, "BLOCKED_MISSING_ARTIFACT",
                               ["Check ID declared in the gate specification but not executed."])
                        for check_id in missing]
        checks = [*checks, *missing_rows]
    counts = _counts(gate, checks)
    decision = _decision_from_counts(checks, counts)
    executed_plus_na = counts["executed_check_count"] + counts["not_applicable_count"]
    if executed_plus_na < counts["required_check_count"] and decision == PASS:
        decision = "BLOCKED_MISSING_ARTIFACT"
        counts["blocked_check_count"] += 1
    record: Dict[str, Any] = {
        "schema": GATE_DECISION_SCHEMA,
        "schema_version": 1,
        "gate": gate,
        "gate_name": GATE_NAMES[gate],
        "decision": decision,
        "policy": "uriel-strict-blessing-1.0.0",
        "created_at_utc": utc_now(),
        "required_check_count": len(GATE_SPECS[gate][1]),
        "executed_check_count": counts["executed_check_count"],
        "passed_check_count": counts["passed_check_count"],
        "failed_check_count": counts["failed_check_count"],
        "blocked_check_count": counts["blocked_check_count"],
        "not_applicable_count": counts["not_applicable_count"],
        "unresolved_blocker_count": counts["unresolved_blocker_count"],
        "binding_digest": binding_digest,
        "independent_verifier_sha256": independent_verifier_sha256,
        "checks": [dict(check) for check in checks],
    }
    record["decision_sha256"] = sha256_text(canonical_json(_decision_core(record)))
    return record


def _decision_core(record: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "schema": record.get("schema"),
        "schema_version": record.get("schema_version"),
        "gate": record.get("gate"),
        "decision": record.get("decision"),
        "policy": record.get("policy"),
        "binding_digest": record.get("binding_digest"),
        "check_statuses": [check.get("status") for check in record.get("checks", [])],
    }


def decision_sha256(record: Mapping[str, Any]) -> str:
    return str(record.get("decision_sha256"))


def write_gate_decision(root: Union[str, Path], record: Mapping[str, Any]) -> Path:
    """Immutable content-addressed gate decision under .uriel/gates/."""
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    store = paths.state / "gates"
    digest = str(record.get("decision_sha256"))
    if not digest:
        raise Refusal("Gate decision has no decision_sha256.", code="GATE_DECISION_NOT_SEALED")
    destination = store / "gate-{0}.json".format(digest)
    if destination.exists():
        try:
            existing = json.loads(destination.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise Refusal(
                "An existing gate decision file is damaged; Uriel will not silently repair it.",
                code="GATE_DECISION_TAMPERED",
                details={"path": str(destination), "error": str(exc)},
            ) from exc
        if existing.get("decision_sha256") != digest:
            raise Refusal("A conflicting gate decision already exists.", code="GATE_DECISION_COLLISION")
        return destination
    atomic_write_json(destination, record)
    return destination


def load_gate_decisions(root: Union[str, Path]) -> List[Dict[str, Any]]:
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    store = paths.state / "gates"
    if not store.exists():
        return []
    records: List[Dict[str, Any]] = []
    for path in sorted(store.glob("gate-*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, Mapping) or "decision_sha256" not in record or "gate" not in record:
            continue
        records.append(record)
    return records


def latest_gate_decision(root: Union[str, Path], gate: int) -> Optional[Dict[str, Any]]:
    candidates = [record for record in load_gate_decisions(root) if record.get("gate") == gate]
    if not candidates:
        return None
    return max(candidates, key=lambda record: str(record.get("created_at_utc", "")))


def gate_state_summary(root: Union[str, Path]) -> Dict[str, Any]:
    """Short deterministic state surface used by the AI entry and CLI."""
    return {
        gate: (record.get("decision") if record else "not_run")
        for gate, record in {
            number: latest_gate_decision(root, number) for number in GATE_SPECS
        }.items()
    }


def gate_0_from_readiness(root: Union[str, Path]) -> Dict[str, Any]:
    """Derive the Gate 0 decision record from the Data Readiness receipt store.

    No substantive gate may pass while the exact generation lacks a valid
    matching receipt; a missing/stale/FAIL receipt is FAIL_DATA_NOT_READY.
    """
    status = readiness_status(root)
    receipt = status.get("receipt")
    if not status.get("exists") or receipt is None:
        decision = "FAIL_DATA_NOT_READY"
        evidence = ["No Data Readiness receipt exists for this generation."]
        failing_status = "FAIL_DATA_NOT_READY"
    elif status.get("decision") == "STALE":
        decision = "FAIL_STALE"
        evidence = ["The data generation changed after the receipt was written."]
        failing_status = "FAIL_STALE"
    elif status.get("decision") != "PASS":
        decision = "FAIL_DATA_NOT_READY"
        evidence = ["The Data Readiness receipt decision is {0}.".format(status.get("decision"))]
        failing_status = "FAIL_DATA_NOT_READY"
    else:
        decision = PASS
        evidence = ["Data Readiness receipt {0} is PASS for the exact generation.".format(
            receipt.get("receipt_sha256"))]
        failing_status = "FAIL_DATA_NOT_READY"
    binding = receipt.get("binding_digest") if isinstance(receipt, Mapping) else ""
    checks = [
        _check("source_identity", PASS if decision == PASS else failing_status, evidence),
        _check("record_identity", PASS if decision == PASS else failing_status, evidence),
        _check("schema", PASS if decision == PASS else failing_status, evidence),
        _check("encoding", PASS if decision == PASS else failing_status, evidence),
        _check("type_normalization", PASS if decision == PASS else failing_status, evidence),
        _check("datetime_normalization", PASS if decision == PASS else failing_status, evidence),
        _check("numeric_locale", PASS if decision == PASS else failing_status, evidence),
        _check("category_normalization", PASS if decision == PASS else failing_status, evidence),
        _check("duplicate_handling", PASS if decision == PASS else failing_status, evidence),
        _check("join_keys_and_cardinality", PASS if decision == PASS else failing_status, evidence),
        _check("missingness", PASS if decision == PASS else failing_status, evidence),
        _check("exclusions", PASS if decision == PASS else failing_status, evidence),
        _check("transformations", PASS if decision == PASS else failing_status, evidence),
        _check("stable_deterministic_sorting", PASS if decision == PASS else failing_status, evidence),
        _check("tie_break_rules", PASS if decision == PASS else failing_status, evidence),
        _check("null_ordering", PASS if decision == PASS else failing_status, evidence),
        _check("order_invariance", PASS if decision == PASS else failing_status, evidence),
        _check("row_reconciliation", PASS if decision == PASS else failing_status, evidence),
        _check("cross_platform_fixture_equivalence", PASS if decision == PASS else failing_status, evidence),
        _check("rebuild_hash_equality", PASS if decision == PASS else failing_status, evidence),
        _check("analysis_plan_binding", PASS if decision == PASS else failing_status, evidence),
        _check("independent_verification", PASS if decision == PASS else failing_status, evidence),
    ]
    return decide_gate(0, checks, binding_digest=binding)
