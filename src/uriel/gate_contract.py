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
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .core import (
    Refusal,
    atomic_write_json,
    canonical_json,
    canonical_root,
    guard_path,
    is_reparse_or_link,
    paths_for,
    sha256_text,
    utc_now,
)
from .data_readiness import REQUIRED_CHECKS, readiness_status

GATE_DECISION_SCHEMA = "uriel.gate_decision.v1"
GATE_FINDING_SCHEMA = "uriel.gate_finding.v1"
MAX_GATE_DECISION_FILES = 4_096
_HEX64 = re.compile(r"^[0-9a-f]{64}$")

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
    identifiers = [str(check.get("check_id")) for check in checks]
    seen = set(identifiers)
    if len(identifiers) != len(seen):
        raise Refusal(
            "A strict gate decision contains a duplicate check ID.",
            code="GATE_DUPLICATE_CHECK",
        )
    unknown = sorted(seen - set(required))
    if unknown:
        raise Refusal(
            "A strict gate decision contains a check outside the frozen gate specification.",
            code="GATE_UNKNOWN_CHECK",
            details={"gate": gate, "unknown_check_ids": unknown},
        )
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
        "gate_name": record.get("gate_name"),
        "decision": record.get("decision"),
        "policy": record.get("policy"),
        "required_check_count": record.get("required_check_count"),
        "executed_check_count": record.get("executed_check_count"),
        "passed_check_count": record.get("passed_check_count"),
        "failed_check_count": record.get("failed_check_count"),
        "blocked_check_count": record.get("blocked_check_count"),
        "not_applicable_count": record.get("not_applicable_count"),
        "unresolved_blocker_count": record.get("unresolved_blocker_count"),
        "binding_digest": record.get("binding_digest"),
        "independent_verifier_sha256": record.get("independent_verifier_sha256"),
        "checks": [dict(check) for check in record.get("checks", [])],
    }


def decision_sha256(record: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(_decision_core(record)))


def _validated_gate_record(
    record: Mapping[str, Any],
    *,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Recompute one persisted gate record; never trust its PASS text or hash."""
    if not isinstance(record, Mapping):
        raise Refusal("A gate decision is not a JSON object.", code="GATE_DECISION_TAMPERED")
    gate = record.get("gate")
    checks = record.get("checks")
    binding = record.get("binding_digest")
    verifier = record.get("independent_verifier_sha256")
    if (
        not isinstance(gate, int)
        or isinstance(gate, bool)
        or gate not in GATE_SPECS
        or not isinstance(checks, list)
        or any(not isinstance(check, Mapping) for check in checks)
        or not isinstance(binding, str)
        or _HEX64.fullmatch(binding) is None
        or (verifier is not None and (not isinstance(verifier, str) or _HEX64.fullmatch(verifier) is None))
        or record.get("schema") != GATE_DECISION_SCHEMA
        or record.get("schema_version") != 1
        or record.get("policy") != "uriel-strict-blessing-1.0.0"
        or not isinstance(record.get("created_at_utc"), str)
    ):
        raise Refusal(
            "A gate decision has an invalid sealed structure.",
            code="GATE_DECISION_TAMPERED",
            details={"path": str(path) if path else None},
        )
    try:
        recomputed = decide_gate(
            gate,
            checks,
            binding_digest=binding,
            independent_verifier_sha256=verifier,
        )
    except Refusal as exc:
        raise Refusal(
            "A gate decision cannot be reproduced from its sealed checks.",
            code="GATE_DECISION_TAMPERED",
            details={"path": str(path) if path else None, "reason": exc.code},
        ) from exc
    substantive_fields = set(_decision_core(recomputed))
    if any(record.get(field) != recomputed.get(field) for field in substantive_fields):
        raise Refusal(
            "A gate decision's fields disagree with deterministic recomputation.",
            code="GATE_DECISION_TAMPERED",
            details={"path": str(path) if path else None},
        )
    declared = record.get("decision_sha256")
    expected = decision_sha256(record)
    if not isinstance(declared, str) or _HEX64.fullmatch(declared) is None or declared != expected:
        raise Refusal(
            "A gate decision's content identity is invalid.",
            code="GATE_DECISION_TAMPERED",
            details={"path": str(path) if path else None},
        )
    if path is not None and path.name != "gate-{0}.json".format(declared):
        raise Refusal(
            "A gate decision filename and content identity disagree.",
            code="GATE_DECISION_TAMPERED",
            details={"path": str(path)},
        )
    return dict(record)


def validate_gate_decision(
    record: Mapping[str, Any],
    *,
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Recompute and validate a gate decision without trusting its PASS label."""
    return _validated_gate_record(record, path=path)


def write_gate_decision(root: Union[str, Path], record: Mapping[str, Any]) -> Path:
    """Immutable content-addressed gate decision under .uriel/gates/."""
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    store = guard_path(root_path, paths.state / "gates")
    guard_path(root_path, store.parent, must_exist=True)
    store.mkdir(parents=False, exist_ok=True)
    guard_path(root_path, store, must_exist=True)
    if is_reparse_or_link(store):
        raise Refusal("The gate decision store may not be a link.", code="GATE_DECISION_TAMPERED")
    validated = _validated_gate_record(record)
    digest = str(validated["decision_sha256"])
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
        _validated_gate_record(existing, path=destination)
        return destination
    atomic_write_json(destination, validated)
    return destination


def load_gate_decisions(root: Union[str, Path]) -> List[Dict[str, Any]]:
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    store = paths.state / "gates"
    if not store.exists():
        return []
    guard_path(root_path, store, must_exist=True)
    if is_reparse_or_link(store):
        raise Refusal("The gate decision store may not be a link.", code="GATE_DECISION_TAMPERED")
    candidates = sorted(store.glob("gate-*.json"))
    if len(candidates) > MAX_GATE_DECISION_FILES:
        raise Refusal(
            "The gate decision store exceeds its bounded history ceiling.",
            code="GATE_DECISION_BUDGET",
            details={"count": len(candidates), "maximum": MAX_GATE_DECISION_FILES},
        )
    records: List[Tuple[Dict[str, Any], int]] = []
    for path in candidates:
        try:
            guard_path(root_path, path, must_exist=True)
            if is_reparse_or_link(path):
                raise Refusal("A gate decision may not be a link.", code="GATE_DECISION_TAMPERED")
            record = json.loads(path.read_text(encoding="utf-8"))
            mtime = path.stat().st_mtime_ns
        except Refusal:
            raise
        except (OSError, json.JSONDecodeError) as exc:
            raise Refusal(
                "A gate decision file is unreadable.",
                code="GATE_DECISION_TAMPERED",
                details={"path": str(path)},
            ) from exc
        records.append((_validated_gate_record(record, path=path), mtime))
    latest_by_gate: Dict[int, Dict[str, Any]] = {}
    for record, mtime in sorted(records, key=lambda pair: (str(pair[0].get("created_at_utc", "")), pair[1])):
        gate = int(record.get("gate"))
        latest_by_gate[gate] = record
    return [latest_by_gate[gate] for gate in sorted(latest_by_gate)]


def latest_gate_decision(root: Union[str, Path], gate: int) -> Optional[Dict[str, Any]]:
    candidates = [record for record in load_gate_decisions(root) if record.get("gate") == gate]
    if not candidates:
        return None
    return candidates[-1]


def gate_state_summary(root: Union[str, Path]) -> Dict[str, Any]:
    """Short deterministic state surface used by the AI entry and CLI."""
    return {
        gate: (record.get("decision") if record else "not_run")
        for gate, record in {
            number: latest_gate_decision(root, number) for number in GATE_SPECS
        }.items()
    }


def gate_0_from_readiness(
    root: Union[str, Path],
    *,
    binding_digest: Optional[str] = None,
    generation_id: Optional[str] = None,
    sort_spec_path: Optional[Union[str, Path]] = None,
    receipt_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Derive the Gate 0 decision record from the Data Readiness receipt store.

    No substantive gate may pass while the exact generation lacks a valid
    matching receipt; a missing/stale/FAIL receipt is FAIL_DATA_NOT_READY.
    ``binding_digest`` overrides the receipt-bound digest when the strict
    flow re-binds Gate 0 to the full generation binding.
    """
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    readiness_dir = guard_path(root_path, paths.state / "readiness")
    dataset: Optional[str] = None
    if generation_id is None and readiness_dir.is_dir():
        candidates = sorted(readiness_dir.glob("sortspec-*.json"), key=lambda p: (p.stat().st_mtime_ns, p.name))
        if candidates:
            try:
                spec = json.loads(candidates[-1].read_text(encoding="utf-8"))
            except (OSError, ValueError):
                spec = {}
            if spec.get("schema") == "uriel.sort_spec.v1":
                dataset = str(spec.get("dataset_path", "")).strip() or None
    status = readiness_status(
        root,
        dataset=dataset,
        generation=generation_id,
        sort_spec_path=sort_spec_path,
        receipt_path=receipt_path,
    )
    receipt = status.get("receipt")
    if not status.get("exists"):
        decision = "FAIL_DATA_NOT_READY"
        evidence = ["No Data Readiness receipt exists for this generation."]
        failing_status = "FAIL_DATA_NOT_READY"
    elif status.get("decision") == "STALE":
        decision = "FAIL_STALE"
        evidence = ["The data generation changed after the receipt was written."]
        failing_status = "FAIL_STALE"
    elif status.get("decision") == "TAMPERED":
        decision = "FAIL_TAMPERED"
        evidence = ["The exact generation or readiness receipt failed integrity verification."]
        failing_status = "FAIL_TAMPERED"
    elif status.get("decision") == "AMBIGUOUS":
        decision = "BLOCKED_AMBIGUOUS_IDENTITY"
        evidence = ["Multiple generation receipts match; select one exact generation and SortSpec."]
        failing_status = "BLOCKED_AMBIGUOUS_IDENTITY"
    elif receipt is None:
        decision = "FAIL_DATA_NOT_READY"
        evidence = ["No independently verified Data Readiness receipt is available."]
        failing_status = "FAIL_DATA_NOT_READY"
    elif status.get("decision") != "PASS":
        decision = "FAIL_DATA_NOT_READY"
        evidence = ["The Data Readiness receipt decision is {0}.".format(status.get("decision"))]
        failing_status = "FAIL_DATA_NOT_READY"
    else:
        decision = PASS
        evidence = [
            "Data Readiness receipt {0} is PASS for the exact generation.".format(
                status.get("receipt_sha256")
            )
        ]
        failing_status = "FAIL_DATA_NOT_READY"
    binding = binding_digest or (receipt.get("binding_digest") if isinstance(receipt, Mapping) else "")
    receipt_checks = receipt.get("checks") if isinstance(receipt, Mapping) else None
    checks = []
    if decision == PASS and isinstance(receipt_checks, list):
        by_id = {
            str(row.get("check_id")): row
            for row in receipt_checks
            if isinstance(row, Mapping)
        }
        for check_id in REQUIRED_CHECKS:
            row = by_id.get(check_id, {})
            readiness_check_status = str(row.get("status", ""))
            if readiness_check_status == "PASS":
                gate_status = PASS
            elif readiness_check_status == "BLOCKED":
                gate_status = "BLOCKED_AMBIGUOUS_IDENTITY"
            else:
                gate_status = "FAIL_DATA_NOT_READY"
            checks.append(
                _check(
                    check_id,
                    gate_status,
                    [
                        "Generation readiness receipt {0}; evidence {1}.".format(
                            status.get("receipt_sha256"),
                            json.dumps(row.get("evidence", {}), ensure_ascii=False, sort_keys=True),
                        )
                    ],
                )
            )
    else:
        checks = [
            _check(check_id, PASS if decision == PASS else failing_status, evidence)
            for check_id in REQUIRED_CHECKS
        ]
    return decide_gate(0, checks, binding_digest=binding)
