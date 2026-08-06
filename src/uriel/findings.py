"""Typed, serializable findings used by Uriel's deterministic audit engine."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


@dataclass(frozen=True)
class Finding:
    """One constructive audit observation.

    ``subject``/``message`` are the canonical v1 field names.  Read-only
    aliases keep early preview integrations and human-facing templates working.
    """

    code: str
    gate: int
    severity: str
    status: str
    subject: str
    message: str
    evidence: List[str] = field(default_factory=list)
    repairs: List[str] = field(default_factory=list)

    @property
    def title(self) -> str:
        return self.subject

    @property
    def reason(self) -> str:
        return self.message

    @property
    def repair_options(self) -> List[str]:
        return list(self.repairs)

    def as_dict(self) -> Dict[str, Any]:
        options = list(self.repairs[:3])
        if self.status != "PASS":
            while len(options) < 3:
                options.append(
                    "Add the missing direct evidence or narrower language, then rerun this Gate."
                )
        return {
            "code": self.code,
            "gate": self.gate,
            "severity": self.severity,
            "status": self.status,
            "subject": self.subject,
            "message": self.message,
            # Human-template aliases are deliberately serialized too.
            "title": self.subject,
            "reason": self.message,
            "evidence": list(self.evidence),
            "repairs": options,
            "repair_options": options,
        }


@dataclass(frozen=True)
class GateResult:
    gate: int
    name: str
    status: str
    scope_note: str
    findings: List[Finding] = field(default_factory=list)

    @property
    def blocker_count(self) -> int:
        return sum(
            1
            for item in self.findings
            if item.severity == "blocker" and item.status == "FAIL"
        )

    @property
    def warning_count(self) -> int:
        return sum(
            1
            for item in self.findings
            if item.severity == "warning" or item.status == "WARN"
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "gate": self.gate,
            "name": self.name,
            "status": self.status,
            "scope_note": self.scope_note,
            "blocker_count": self.blocker_count,
            "warning_count": self.warning_count,
            "findings": [item.as_dict() for item in self.findings],
        }


@dataclass(frozen=True)
class AuditReport:
    audit_id: str
    profile: str
    status: str
    created_at_utc: str
    source_manifest_sha256: str
    source_records_sha256: str
    project_manifest_sha256: str
    policy_version: str
    gates: List[GateResult]
    audit_path: str
    limitations: List[str] = field(default_factory=list)

    @property
    def blessable(self) -> bool:
        return self.profile in {"strict", "submission"} and self.status == "PASS" and all(
            gate.status == "PASS" for gate in self.gates
        )

    def as_dict(self) -> Dict[str, Any]:
        return {
            "schema": "uriel.audit.v1",
            "schema_version": 1,
            "audit_id": self.audit_id,
            "profile": self.profile,
            "status": self.status,
            "created_at_utc": self.created_at_utc,
            "source_manifest_sha256": self.source_manifest_sha256,
            "source_records_sha256": self.source_records_sha256,
            "project_manifest_sha256": self.project_manifest_sha256,
            "policy_version": self.policy_version,
            "gates": [gate.as_dict() for gate in self.gates],
            "audit_path": self.audit_path,
            "blessable": self.blessable,
            "limitations": list(self.limitations),
        }
