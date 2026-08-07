"""Structured gap register (STRICT_BLESSING_CONTRACT.md section 10).

Every failed or blocked gate produces structured gap rows.  Uriel may fill
schemas, plans, and scaffolding; it may never invent measurements, results,
citations, or approvals.  Each gap action carries one of the seven labels.
"""
from __future__ import annotations

import csv
import io
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import Refusal, atomic_write_json, canonical_json, canonical_root, paths_for, sha256_text, utc_now

GAP_REGISTER_SCHEMA = "uriel.gap_register.v1"

GAP_FIELDS = (
    "gap_id",
    "gate",
    "failure_code",
    "severity",
    "observed_fact",
    "why_it_matters",
    "affected_claims",
    "affected_artifacts",
    "what_remains_valid",
    "minimum_repair",
    "preferred_repair",
    "alternative_repairs",
    "best_sorting_or_collection_method",
    "evidence_needed",
    "user_action_needed",
    "uriel_action_available",
    "external_action_needed",
    "completion_condition",
    "verification_command",
    "status",
)

GAP_ACTIONS = (
    "FILLED_BY_URIEL",
    "REQUIRES_USER_DECISION",
    "REQUIRES_SOURCE_ARTIFACT",
    "REQUIRES_NEW_DATA",
    "REQUIRES_EXPERIMENT",
    "REQUIRES_EXTERNAL_VERIFICATION",
    "UNRESOLVABLE_AS_STATED",
)

# Section 10.1: what Uriel may safely create.
URIEL_MAY_FILL = (
    "schemas",
    "directory structures",
    "data dictionaries",
    "sort specifications",
    "normalization rules",
    "test plans",
    "control plans",
    "analysis plans",
    "search queries",
    "evidence-request lists",
    "code",
    "fixtures",
    "table shells",
    "figure shells",
    "methods templates",
    "limitation language",
    "review-response structure",
    "submission checklists",
    "field drafts based on verified facts",
)
# Section 10.2: what Uriel may not invent.
URIEL_MAY_NOT_FILL = (
    "measurements",
    "participants",
    "results",
    "citations",
    "source text",
    "experiments",
    "approvals",
    "author identities",
    "venue rules",
    "novelty",
    "acceptance",
    "statistical power",
    "external validation",
)


def build_gap(
    *,
    gate: int,
    failure_code: str,
    severity: str,
    observed_fact: str,
    why_it_matters: str,
    affected_claims: Sequence[str] = (),
    affected_artifacts: Sequence[str] = (),
    what_remains_valid: str = "",
    minimum_repair: str = "",
    preferred_repair: str = "",
    alternative_repairs: Sequence[str] = (),
    best_sorting_or_collection_method: str = "",
    evidence_needed: str = "",
    user_action_needed: str = "",
    uriel_action_available: str = "",
    external_action_needed: str = "",
    completion_condition: str = "",
    verification_command: str = "",
    action: str = "REQUIRES_SOURCE_ARTIFACT",
    gap_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Build one gap row.  The default action is honest: gaps need source artifacts."""
    if action not in GAP_ACTIONS:
        raise Refusal("Unknown gap action label.", code="GAP_UNKNOWN_ACTION",
                      repairs=["Choose one of: {0}.".format(", ".join(GAP_ACTIONS))])
    row: Dict[str, Any] = {
        "gap_id": gap_id or sha256_text(canonical_json({
            "gate": gate, "failure_code": failure_code,
            "observed_fact": observed_fact, "created_at_utc": utc_now(),
        }))[:16],
        "gate": gate,
        "failure_code": failure_code,
        "severity": severity,
        "observed_fact": observed_fact,
        "why_it_matters": why_it_matters,
        "affected_claims": list(affected_claims),
        "affected_artifacts": list(affected_artifacts),
        "what_remains_valid": what_remains_valid,
        "minimum_repair": minimum_repair,
        "preferred_repair": preferred_repair,
        "alternative_repairs": list(alternative_repairs),
        "best_sorting_or_collection_method": best_sorting_or_collection_method,
        "evidence_needed": evidence_needed,
        "user_action_needed": user_action_needed,
        "uriel_action_available": uriel_action_available,
        "external_action_needed": external_action_needed,
        "completion_condition": completion_condition,
        "verification_command": verification_command,
        "status": "open",
        "action": action,
    }
    return row


def write_gap_register(root: Union[str, Path], rows: Sequence[Mapping[str, Any]], *, label: str = "latest") -> Dict[str, Any]:
    """Write a content-addressed gap register and return its envelope."""
    if not rows:
        raise Refusal("A gap register cannot be empty; no gate failure means no register.",
                      code="GAP_REGISTER_EMPTY")
    normalized = [dict(row) for row in rows]
    digest = sha256_text(canonical_json(normalized))
    record = {
        "schema": GAP_REGISTER_SCHEMA,
        "schema_version": 1,
        "label": label,
        "created_at_utc": utc_now(),
        "gap_count": len(normalized),
        "register_sha256": digest,
        "gaps": normalized,
    }
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    store = paths.state / "gaps"
    destination = store / "gap-register-{0}.json".format(digest)
    if destination.exists():
        return {"path": str(destination), "register_sha256": digest, "gap_count": len(normalized)}
    atomic_write_json(destination, record)
    return {"path": str(destination), "register_sha256": digest, "gap_count": len(normalized)}


def render_gap_register_csv(rows: Sequence[Mapping[str, Any]]) -> str:
    """CSV export (the 04_BLOCKERS.csv / 04_GAP_REGISTER.csv packet file)."""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(GAP_FIELDS) + ["action"])
    writer.writeheader()
    for row in rows:
        flattened = {key: row.get(key, "") for key in GAP_FIELDS}
        flattened["affected_claims"] = "; ".join(row.get("affected_claims", []))
        flattened["affected_artifacts"] = "; ".join(row.get("affected_artifacts", []))
        flattened["alternative_repairs"] = "; ".join(row.get("alternative_repairs", []))
        flattened["action"] = row.get("action", "")
        writer.writerow(flattened)
    return buffer.getvalue()


def load_latest_gap_register(root: Union[str, Path]) -> Optional[Dict[str, Any]]:
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    store = paths.state / "gaps"
    if not store.exists():
        return None
    candidates = [path for path in store.glob("gap-register-*.json")]
    if not candidates:
        return None
    latest = max(candidates, key=lambda path: path.stat().st_mtime)
    import json

    return json.loads(latest.read_text(encoding="utf-8"))
