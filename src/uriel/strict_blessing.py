"""Strict Blessing of Uriel (STRICT_BLESSING_CONTRACT.md 1, 12, 14).

The Blessing predicate is a strict logical AND over Gate 0-3 PASS, an
independent verifier PASS, certificate binding PASS, and zero unresolved
blockers.  Only deterministic Uriel code writes authoritative gate decisions;
the issuer recomputes the complete binding before any certificate exists.
"""
from __future__ import annotations

import json
import os
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .audit import audit_project
from .core import (
    IntegrityError,
    Refusal,
    append_ledger,
    atomic_write,
    atomic_write_json,
    build_manifest,
    canonical_json,
    canonical_root,
    guard_path,
    paths_for,
    read_json,
    safe_relative_path,
    sha256_file,
    sha256_text,
    verify_source_manifest,
    utc_now,
)
from .gate_contract import (
    GATE_SPECS,
    GATE_NAMES,
    decide_gate,
    gate_0_from_readiness,
    load_gate_decisions,
    latest_gate_decision,
    write_gate_decision,
)
from .gate_failures import AUDIT_TO_FAILURE, classify_failure
from .independent_verify import compute_binding_digest, independent_verify, latest_verifier
from .qr import qr_svg
from .repair_packet import verify_repair_packet

STRICT_BLESSING_SCHEMA = "URIEL-STRICT-BLESSING-v1"
STRICT_POLICY = "uriel-strict-blessing-1.0.0"

_CORE_KEYS = (
    "schema",
    "schema_version",
    "project_id",
    "project_title",
    "issued_at_utc",
    "policy",
    "binding_digest",
    "gate_decision_sha256s",
    "readiness_receipt_sha256",
    "claim_evidence_map_sha256",
    "source_manifest_sha256",
    "source_records_sha256",
    "verifier_sha256",
    "audit_id",
    "verification_payload",
    "scope",
    "non_claims",
)


def _core_payload(value: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: value.get(key) for key in _CORE_KEYS}


def _strict_blessing_id(value: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(_core_payload(value)))


def strict_gates_from_audit(root: Union[str, Path]) -> List[Dict[str, Any]]:
    """Run the deterministic audit and project its findings onto the mandatory
    check lists, producing authoritative gate decisions for Gates 1-3.

    Gate 0 is derived from the Data Readiness receipts.  A missing mandatory
    check, an exception, or an inaccessible artifact can never become PASS.
    """
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    binding = compute_binding_digest(root_path)
    digest = binding["binding_digest"]
    gate0 = gate_0_from_readiness(root_path, binding_digest=digest)
    decisions: List[Dict[str, Any]] = [gate0]
    report = audit_project(paths.root, profile="submission")
    for gate_number, (name, check_ids) in GATE_SPECS.items():
        if gate_number == 0:
            continue
        gate_findings = [finding for finding in report.gates if finding.gate == gate_number]
        flat = [finding for gate in gate_findings for finding in gate.findings]
        blocked_codes = {finding.code for finding in flat if finding.severity == "blocker" and finding.status == "FAIL"}
        checks = []
        for check_id in check_ids:
            status = "PASS"
            evidence: List[str] = ["No contradicting finding in the deterministic audit output."]
            for finding in flat:
                failure = classify_failure(finding.code)
                if failure["status"] == "PASS":
                    continue
                if _check_owns(finding, check_id):
                    status = failure["status"]
                    evidence = [finding.message, *finding.evidence]
                    break
            checks.append({
                "check_id": check_id,
                "status": status,
                "evidence": evidence,
                "applicability_predicate": None,
            })
        decision = decide_gate(gate_number, checks, binding_digest=digest)
        decision["audit_id"] = report.audit_id
        decisions.append(decision)
    return decisions


def _check_owns(finding: Any, check_id: str) -> bool:
    """Deterministic audit finding -> mandatory check mapping by code."""
    code = str(getattr(finding, "code", ""))
    gate = int(getattr(finding, "gate", 0) or 0)
    if gate == 1 and code in {
        "QUESTION_UNDERSPECIFIED", "HYPOTHESIS_UNDERSPECIFIED", "SCHEMA_STRUCTURE",
    }:
        return check_id == "question_stated"
    if gate == 1 and code in {"OPERATIONAL_DEFINITIONS_MISSING", "VAGUE_EVALUATIVE_TERM"}:
        return check_id == "operational_definitions"
    if gate == 1 and code in {"SUCCESS_CRITERIA_MISSING", "FALSIFIER_MISSING"}:
        return check_id == "testable_falsifiable"
    if gate == 1 and code in {"SCOPE_BOUNDARIES_MISSING", "UNBOUNDED_CERTAINTY", "GLOBAL_NOVELTY_OVERCLAIM"}:
        return check_id == "scope_explicit"
    if gate == 1 and code in {"LOADED_FRAMING", "NEUTRAL_FRAME_MISSING", "COMPETING_FRAME_MISSING"}:
        return check_id == "no_assumed_conclusion"
    if gate == 1 and code in {"NOVELTY_SEARCH_NOT_STARTED", "NOVELTY_SEARCH_INCOMPLETE", "NOVELTY_SEARCH_THIN", "NEGATIVE_SEARCH_MISSING"}:
        return check_id == "novelty_established_or_not_claimed"
    if gate == 1 and code == "DUPLICATE_CLAIM":
        return check_id == "internally_consistent"
    if gate == 1 and code in {"PLACEHOLDER_LANGUAGE", "HYPOTHESIS_UNDERSPECIFIED"}:
        return check_id == "strongest_defensible_interpretation"
    if gate == 2 and code in {
        "CLAIMS_MISSING", "CLAIM_INCOMPLETE", "CLAIM_UNSUPPORTED", "CLAIM_SCOPE_INCOMPLETE",
        "CLAIM_FALSIFIER_MISSING", "UNKNOWN_EVIDENCE_REFERENCE", "UNRECONCILED_EVIDENCE_ROLE",
        "TOTAL_EVIDENCE_ROLE_CONFLICT",
    }:
        return check_id == "claim_map_complete"
    if gate == 2 and code in {"EVIDENCE_MISSING", "EVIDENCE_ARTIFACT_MISSING", "EVIDENCE_PATH_INVALID", "MAJOR_CLAIM_LACKS_DIRECT_PRIMARY_EVIDENCE"}:
        return check_id == "exact_artifact_mapping"
    if gate == 2 and code in {"EVIDENCE_HASH_MISMATCH", "EVIDENCE_DECLARED_DIGEST_MISMATCH", "EVIDENCE_NOT_MANIFESTED"}:
        return check_id == "artifact_hashes_match"
    if gate == 2 and code in {"SECONDARY_ONLY_SUPPORT", "CAUSAL_CLAIM_FROM_OBSERVATIONAL_EVIDENCE"}:
        return check_id == "primary_sources_used"
    if gate == 2 and code == "FRESH_PASS_RECEIPT_MISSING":
        return check_id == "no_stale_inaccessible_dependency"
    if gate == 2 and code == "RECEIPT_DAMAGED":
        return check_id == "no_stale_inaccessible_dependency"
    if gate == 2 and code == "REPRODUCIBILITY_COMMAND_MISSING":
        return check_id == "reproducible_from_artifacts"
    if gate == 3 and code in {"ADVERSARIAL_TEST_INCOMPLETE", "ADVERSARIAL_TEST_NOT_RESOLVED", "CONTROLS_MISSING", "SAMPLE_SIZE_MISSING"}:
        return check_id == "alternative_explanations"
    if gate == 3 and code in {"CONTRADICTION_UNRESOLVED", "COUNTEREVIDENCE_UNRECONCILED"}:
        return check_id == "contradictory_observations"
    if gate == 3 and code in {"ASSUMPTIONS_UNDECLARED", "ASSUMPTION_INCOMPLETE", "EXCLUSIONS_UNDECLARED"}:
        return check_id == "sensitivity_to_analytical_choices"
    if gate == 3 and code in {"ETHICS_STATUS_MISSING", "ETHICS_RISK_UNMITIGATED"}:
        return check_id == "ethics_privacy_security"
    if gate == 3 and code == "NEGATIVE_RESULTS_ATTESTATION_MISSING":
        return check_id == "contradictory_observations"
    if gate == 3 and code == "MANDATORY_GATE_WAIVER_REFUSED":
        return check_id == "reviewer_objections"
    return False


def run_strict_gates(root: Union[str, Path], *, persist: bool = True) -> Dict[str, Any]:
    """Compute and (optionally) persist all four strict gate decisions."""
    decisions = strict_gates_from_audit(root)
    if persist:
        for decision in decisions:
            write_gate_decision(root, decision)
    return {"gates": [decision for decision in decisions],
            "decisions": {str(decision["gate"]): decision["decision"] for decision in decisions}}


def _all_gates_pass(decisions: Sequence[Mapping[str, Any]]) -> bool:
    return all(str(decision.get("decision")) == "PASS" for decision in decisions)


def blessing_eligibility(root: Union[str, Path]) -> Dict[str, Any]:
    """Report why issuance is blocked.  Never creates a certificate."""
    root_path = canonical_root(root)
    decisions = {int(record.get("gate")): record for record in load_gate_decisions(root_path)}
    missing_gates = [number for number in GATE_SPECS if number not in decisions]
    blockers: List[str] = []
    for number in GATE_SPECS:
        record = decisions.get(number)
        if record is None:
            blockers.append("Gate {0} ({1}) has no decision record.".format(number, GATE_NAMES[number]))
            continue
        if str(record.get("decision")) != "PASS":
            blockers.append("Gate {0} ({1}) decision is {2}.".format(
                number, GATE_NAMES[number], record.get("decision")))
    if missing_gates:
        blockers.append("Missing gate decisions: {0}.".format(", ".join(str(g) for g in missing_gates)))
    unresolved = sum(int(record.get("unresolved_blocker_count", 0)) for record in decisions.values())
    if unresolved:
        blockers.append("{0} unresolved blockers across the gate decisions.".format(unresolved))
    verifier = latest_verifier(root_path)
    if verifier is None or verifier.get("decision") != "PASS":
        blockers.append("The independent verifier has no PASS receipt for the current binding.")
    else:
        binding = compute_binding_digest(root_path)
        if verifier.get("recomputed_binding_digest") != binding["binding_digest"]:
            blockers.append("The latest verifier receipt binds a different project generation.")
    eligible = not blockers
    return {
        "eligible": eligible,
        "blockers": blockers,
        "gates": {str(number): (decisions.get(number, {}).get("decision") if decisions.get(number) else "not_run")
                  for number in GATE_SPECS},
        "binding_digest": compute_binding_digest(root_path)["binding_digest"],
        "verifier_decision": verifier.get("decision") if verifier else "not_run",
    }


def _strict_certificate_text(core: Mapping[str, Any]) -> str:
    border = "+" + "-" * 76 + "+"
    digest = str(core.get("blessing_id", ""))
    rows = [
        border,
        "|" + " THE STRICT BLESSING OF URIEL ".center(76) + "|",
        "|" + " Deterministic fail-closed research-integrity audit ".center(76) + "|",
        border,
        "Project: {0}".format(core.get("project_title", "Untitled")),
        "Issued:  {0}".format(core.get("issued_at_utc", "")),
        "Policy:  {0}".format(core.get("policy", "")),
        "Strict Blessing SHA-256:",
        "  {0}".format(digest),
        "",
        "PASSED: Gate 0 - Data Readiness",
        "PASSED: Gate 1 - Novelty & Clarity",
        "PASSED: Gate 2 - Evidence & Citation",
        "PASSED: Gate 3 - Adversarial Integrity",
        "PASSED: Independent verifier recomputation",
        "PASSED: Certificate binding (zero unresolved blockers)",
        "",
        "Binding digest:",
        "  {0}".format(core.get("binding_digest", "")),
        "",
        "This certificate binds the exact hash-bound project generation, data,",
        "evidence, receipts, audit profile, and limitations presented to Uriel.",
        "It is not eternal truth, perfect measurement, universal applicability,",
        "peer review, or immunity from later evidence.",
        border,
    ]
    return "\n".join(rows) + "\n"


def issue_strict_blessing(root: Union[str, Path]) -> Dict[str, Any]:
    """Issue a strict Blessing.  The verifier must recompute the binding
    BEFORE any certificate exists, and every referenced file must verify."""
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    eligibility = blessing_eligibility(root_path)
    if not eligibility["eligible"]:
        raise Refusal(
            "Uriel cannot issue a strict Blessing; the binding has unresolved blockers.",
            code="STRICT_BLESSING_NOT_EARNED",
            details={"blockers": eligibility["blockers"][:20],
                     "gates": eligibility["gates"]},
            repairs=[
                "Repair each blocker listed above, then rerun `uriel blessing eligibility`.",
                "Run `uriel audit gaps` and follow the failure packet.",
                "Narrow the scope honestly rather than weakening a gate.",
            ],
        )
    verifier = independent_verify(root_path, expected_binding_digest=eligibility["binding_digest"])
    if verifier.get("decision") != "PASS":
        raise IntegrityError(
            "The independent verifier did not recompute the exact binding; no certificate may be created.",
            code="STRICT_VERIFIER_FAILED",
            details={"errors": verifier.get("errors")},
        )
    source = build_manifest(paths.root, persist=True)
    source_check = verify_source_manifest(paths.root, source)
    if not source_check.get("verified"):
        raise IntegrityError("The source changed before Blessing issuance.", code="STRICT_SOURCE_CHANGED")
    project = read_json(paths.project)
    claim_evidence = canonical_json({
        "claims": project.get("claims", []),
        "evidence": project.get("evidence", []),
    })
    decisions = load_gate_decisions(root_path)
    gate_hashes = {str(record.get("gate")): str(record.get("decision_sha256")) for record in decisions}
    readiness = _latest_readiness_receipt(root_path)
    core: Dict[str, Any] = {
        "schema": STRICT_BLESSING_SCHEMA,
        "schema_version": 1,
        "project_id": project.get("project_id"),
        "project_title": project.get("title"),
        "issued_at_utc": utc_now(),
        "policy": STRICT_POLICY,
        "binding_digest": eligibility["binding_digest"],
        "gate_decision_sha256s": gate_hashes,
        "readiness_receipt_sha256": readiness,
        "claim_evidence_map_sha256": sha256_text(claim_evidence),
        "source_manifest_sha256": source.get("manifest_sha256"),
        "source_records_sha256": source.get("records_sha256"),
        "verifier_sha256": verifier.get("verifier_sha256"),
        "audit_id": _latest_audit_id(decisions),
        "verification_payload": "URIEL-STRICT-BLESSING-v1:{0}:{1}".format(
            eligibility["binding_digest"][:16], str(source.get("records_sha256", ""))[:16]),
        "scope": "The exact hash-bound project, data, evidence, code, receipts, audit profile, and limitations presented to Uriel.",
        "non_claims": [
            "not eternal truth",
            "not perfect measurements",
            "not universal applicability",
            "not a replacement for peer review",
            "not immunity from later evidence",
        ],
    }
    blessing_id = _strict_blessing_id(core)
    package_dir = paths.blessings / blessing_id
    if package_dir.exists():
        result = verify_strict_blessing(package_dir, project_root=paths.root)
        if result.get("verified"):
            return result
        raise IntegrityError(
            "An existing content-addressed strict Blessing package is damaged.",
            code="STRICT_BLESSING_PACKAGE_DAMAGED",
            details={"errors": result.get("errors")},
        )
    temporary = paths.blessings / ".candidate-{0}".format(uuid.uuid4().hex)
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        files: Dict[str, str] = {}
        for decision in decisions:
            atomic_write_json(temporary / "gate-decision-{0}.json".format(decision.get("gate")), decision)
            files["gate-decision-{0}.json".format(decision.get("gate"))] = decision.get("decision_sha256", "")
        atomic_write_json(temporary / "verifier-receipt.json", verifier)
        atomic_write_json(temporary / "source-manifest.json", source)
        atomic_write(temporary / "verification-qr.svg", qr_svg(str(core["verification_payload"])))
        provisional = {**core, "blessing_id": blessing_id}
        atomic_write(temporary / "certificate.txt", _strict_certificate_text(provisional))
        verification_instructions = _verification_instructions(provisional)
        atomic_write(temporary / "verification-instructions.md", verification_instructions)
        verification_payload = {
            "blessing_id": blessing_id,
            "binding_digest": core["binding_digest"],
            "files": {},
        }
        file_hashes: Dict[str, str] = {}
        for path in sorted(temporary.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file():
                rel = path.relative_to(temporary).as_posix()
                file_hashes[rel] = sha256_file(path)
                verification_payload["files"][rel] = file_hashes[rel]
        blessing = {
            **core,
            "blessing_id": blessing_id,
            "files": file_hashes,
            "package_sha256": sha256_text(canonical_json({"blessing_id": blessing_id, "files": file_hashes})),
        }
        atomic_write_json(temporary / "blessing.json", blessing)
        os.replace(str(temporary), str(package_dir))
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    event = append_ledger(
        paths.root,
        "blessing.strict_issued",
        {
            "blessing_id": blessing_id,
            "package_sha256": read_json(package_dir / "blessing.json").get("package_sha256"),
            "binding_digest": core["binding_digest"],
            "verifier_sha256": verifier.get("verifier_sha256"),
        },
    )
    result = verify_strict_blessing(package_dir, project_root=paths.root)
    result["ledger_event_sha256"] = event.get("event_sha256")
    return result


def _latest_readiness_receipt(root: Path) -> str:
    receipt_dir = root / ".uriel" / "readiness"
    if not receipt_dir.exists():
        return ""
    candidates = sorted(receipt_dir.glob("receipt-*.json"))
    if not candidates:
        return ""
    try:
        receipt = json.loads(candidates[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return ""
    return str(receipt.get("receipt_sha256", ""))


def _latest_audit_id(decisions: Sequence[Mapping[str, Any]]) -> str:
    for decision in decisions:
        audit_id = decision.get("audit_id")
        if audit_id:
            return str(audit_id)
    return ""


def _verification_instructions(core: Mapping[str, Any]) -> str:
    return """# Verify this strict Blessing

1. Place the package in a fresh directory (the package is self-contained).
2. Recomputed binding digest: {binding}
3. Expected strict Blessing SHA-256: {id}
4. Run `uriel blessing verify --package <dir> --root <project-root>` against the
   live project, or verify the packaged files with the packaged SHA-256 sums.

A Blessing means every mandatory check passed for the exact bound version.
It does not mean eternal truth, perfect measurements, universal
applicability, replacement of peer review, or immunity from later evidence.
""".format(binding=core.get("binding_digest", ""), id=core.get("blessing_id", ""))


def verify_strict_blessing(
    package: Union[str, Path],
    *,
    project_root: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    candidate = Path(package).expanduser()
    if candidate.is_file():
        package_dir = candidate.parent
        blessing_path = candidate
    else:
        package_dir = candidate
        blessing_path = package_dir / "blessing.json"
    errors: List[str] = []
    try:
        value = read_json(blessing_path)
    except Refusal as exc:
        return {"verified": False, "errors": [str(exc)], "package": str(package_dir)}
    if value.get("schema") != STRICT_BLESSING_SCHEMA:
        errors.append("Strict Blessing schema mismatch")
    calculated_id = _strict_blessing_id(value)
    if calculated_id != value.get("blessing_id"):
        errors.append("Strict Blessing id mismatch")
    files = value.get("files")
    if not isinstance(files, Mapping):
        errors.append("Strict Blessing file manifest is missing")
        files = {}
    for name, expected in files.items():
        try:
            rel = safe_relative_path(str(name))
            path = package_dir / rel
            if not path.is_file() or sha256_file(path) != expected:
                errors.append("File hash mismatch: {0}".format(name))
        except Refusal:
            errors.append("Unsafe package path: {0}".format(name))
    package_sha = sha256_text(canonical_json({"blessing_id": value.get("blessing_id"), "files": dict(files)}))
    if package_sha != value.get("package_sha256"):
        errors.append("Package digest mismatch")
    expected_names = sorted(str(name) for name in files)
    actual_names = sorted(
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file() and path.name != "blessing.json"
    )
    if actual_names != expected_names:
        errors.append("Package membership mismatch")
    if project_root is not None:
        try:
            eligibility = blessing_eligibility(project_root)
            live = {"eligible": eligibility["eligible"], "binding": eligibility["binding_digest"]}
            if not eligibility["eligible"]:
                errors.append("Live project is not eligible: {0}".format("; ".join(eligibility["blockers"][:5])))
            if eligibility["binding_digest"] != value.get("binding_digest"):
                errors.append("Live binding differs from the blessed binding")
        except (Refusal, IntegrityError, OSError, json.JSONDecodeError) as exc:
            errors.append("Live project verification failed: {0}".format(exc))
    return {
        "verified": not errors,
        "blessing_id": value.get("blessing_id"),
        "package_sha256": value.get("package_sha256"),
        "binding_digest": value.get("binding_digest"),
        "verification_payload": value.get("verification_payload"),
        "package": str(package_dir.resolve()),
        "errors": errors,
    }
