"""Analysis-plan locking: keep the goalposts where they were before the results.

``uriel plan lock`` freezes the hypothesis, falsifier, success criteria,
definitions, and method/analysis fields of ``uriel.project.json`` into an
immutable, content-addressed record and appends a ``plan.locked`` event to the
hash-chained ledger.  The ledger order then shows whether the plan was fixed
before or after the first passing analysis run.

Later changes are never blocked from being made; they are made visible:

- editing a locked field without re-locking is reported as plan drift;
- re-locking requires a written reason and is flagged as a post-results
  revision when passing results already existed, so the deviation can be
  disclosed in the Methods section;
- a manuscript that calls the study preregistered is checked against either
  a lock that preceded the first passing run or a declared external
  registration.

A lock is local tamper evidence, not a public preregistration, trusted
timestamp, or proof that no analysis happened outside Uriel.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple, Union

from .core import (
    Refusal,
    _read_ledger_events,
    append_ledger,
    atomic_write_json,
    canonical_json,
    guard_path,
    is_reparse_or_link,
    load_project,
    paths_for,
    read_json,
    sha256_file,
    sha256_text,
    utc_now,
    verify_ledger,
)

PLAN_LOCK_SCHEMA = "uriel.plan_lock.v1"
PLAN_FIELDS: Tuple[Tuple[str, str], ...] = (
    ("hypothesis", "statement"),
    ("hypothesis", "falsifier"),
    ("hypothesis", "operational_definitions"),
    ("hypothesis", "success_criteria"),
    ("methods", "design"),
    ("methods", "population"),
    ("methods", "sampling"),
    ("methods", "sample_size"),
    ("methods", "analysis_plan"),
    ("methods", "effect_size_metric"),
    ("methods", "uncertainty_method"),
    ("methods", "causal_identification"),
    ("methods", "controls"),
    ("methods", "exclusions"),
    ("methods", "missing_data_plan"),
)
MIN_REASON = 16
_PREREG_CLAIM = re.compile(r"\b(?:pre-?registered|pre-?registration|registered report)\b", re.IGNORECASE)
_NEGATED = re.compile(r"\b(?:not|no|never|without|neither|nor)\b[^.\n]{0,48}$", re.IGNORECASE)


def _pointer(section: str, field: str) -> str:
    return "/{0}/{1}".format(section, field)


def current_plan(project: Mapping[str, Any]) -> Dict[str, Any]:
    plan: Dict[str, Any] = {}
    for section, field in PLAN_FIELDS:
        container = project.get(section)
        value = container.get(field) if isinstance(container, Mapping) else None
        plan[_pointer(section, field)] = value
    return plan


def plan_sha256(plan: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(dict(plan)))


def _store(root: Path) -> Path:
    paths = paths_for(root)
    store = guard_path(paths.root, paths.state / "plan-locks")
    if store.exists() and (is_reparse_or_link(store) or not store.is_dir()):
        raise Refusal("The plan-lock store must be a regular directory.", code="PLAN_LOCK_STORE_INVALID")
    return store


def _events(root: Path) -> List[Dict[str, Any]]:
    paths = paths_for(root)
    verify_ledger(paths.root)
    return _read_ledger_events(paths.ledger)


def _pass_run_sequences(events: List[Mapping[str, Any]]) -> List[int]:
    return [
        int(event.get("sequence", 0))
        for event in events
        if event.get("event_type") == "workload.executed"
        and isinstance(event.get("payload"), Mapping)
        and event["payload"].get("status") == "PASS"
    ]


def _load_locks(root: Path, events: List[Mapping[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """Return (locks in ledger order, integrity problems)."""
    store = _store(root)
    locks: List[Dict[str, Any]] = []
    problems: List[Dict[str, Any]] = []
    for event in events:
        if event.get("event_type") != "plan.locked":
            continue
        payload = event.get("payload") if isinstance(event.get("payload"), Mapping) else {}
        lock_id = str(payload.get("lock_id", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", lock_id):
            problems.append({"lock_id": lock_id, "reason": "ledger event has an invalid lock id"})
            continue
        path = store / "{0}.json".format(lock_id)
        if not path.is_file() or is_reparse_or_link(path):
            problems.append({"lock_id": lock_id, "reason": "lock record is missing"})
            continue
        if sha256_file(path) != payload.get("record_sha256"):
            problems.append({"lock_id": lock_id, "reason": "lock record bytes do not match the ledger"})
            continue
        record = read_json(path)
        body = dict(record)
        body.pop("lock_id", None)
        if sha256_text(canonical_json(body)) != lock_id or record.get("schema") != PLAN_LOCK_SCHEMA:
            problems.append({"lock_id": lock_id, "reason": "lock record identity does not verify"})
            continue
        record["ledger_sequence"] = int(event.get("sequence", 0))
        locks.append(record)
    return locks, problems


def lock_plan(root: Union[str, Path], *, reason: str = "") -> Dict[str, Any]:
    """Freeze the current plan fields; a re-lock needs a written reason."""
    paths = paths_for(root)
    project = load_project(paths.root)
    plan = current_plan(project)
    hypothesis = plan["/hypothesis/statement"] if isinstance(plan["/hypothesis/statement"], str) else ""
    falsifier = plan["/hypothesis/falsifier"] if isinstance(plan["/hypothesis/falsifier"], str) else ""
    analysis = plan["/methods/analysis_plan"] if isinstance(plan["/methods/analysis_plan"], str) else ""
    if len(hypothesis.strip()) < 24 or len(falsifier.strip()) < 16 or len(analysis.strip()) < 16:
        raise Refusal(
            "The plan is too incomplete to lock: a hypothesis, a falsifier, and an analysis plan are required.",
            code="PLAN_INCOMPLETE",
            details={
                "hypothesis_chars": len(hypothesis.strip()),
                "falsifier_chars": len(falsifier.strip()),
                "analysis_plan_chars": len(analysis.strip()),
            },
            repairs=[
                "Write /hypothesis/statement, /hypothesis/falsifier, and /methods/analysis_plan in uriel.project.json.",
                "Run `uriel next` to see which framing and design items are still open.",
                "Label the project exploratory and lock later, before any confirmatory analysis is run.",
            ],
        )
    events = _events(paths.root)
    locks, problems = _load_locks(paths.root, events)
    if problems:
        raise Refusal(
            "An earlier plan lock no longer verifies; Uriel will not extend a damaged lock history.",
            code="PLAN_LOCK_DAMAGED",
            details={"problems": problems},
            repairs=[
                "Restore the missing or changed lock records under .uriel/plan-locks/ from a backup.",
                "Investigate how the record changed before trusting any later result.",
                "Start a fresh project copy and disclose the lost lock history in the Methods section.",
            ],
        )
    digest = plan_sha256(plan)
    latest = locks[-1] if locks else None
    if latest is not None and latest.get("plan_sha256") == digest:
        return {"status": "UNCHANGED", "lock": latest, "lock_count": len(locks)}
    clean_reason = reason.strip()
    if latest is not None and len(clean_reason) < MIN_REASON:
        raise Refusal(
            "The plan changed since it was locked; a re-lock needs a written reason of at least {0} characters.".format(MIN_REASON),
            code="PLAN_RELOCK_REASON_REQUIRED",
            details={"changed_fields": _changed_fields(latest.get("plan", {}), plan)},
            repairs=[
                "Rerun with --reason explaining what changed and why (it will be shown as a deviation).",
                "Revert the edited fields in uriel.project.json to the locked plan.",
                "Keep the new idea as a separate exploratory analysis instead of changing the locked plan.",
            ],
        )
    pass_runs = _pass_run_sequences(events)
    body: Dict[str, Any] = {
        "schema": PLAN_LOCK_SCHEMA,
        "schema_version": 1,
        "project_id": project.get("project_id"),
        "created_at_utc": utc_now(),
        "plan": plan,
        "plan_sha256": digest,
        "parent_lock_id": latest.get("lock_id") if latest else None,
        "reason": clean_reason,
        "passing_results_existed": bool(pass_runs),
        "changed_fields": _changed_fields(latest.get("plan", {}), plan) if latest else [],
    }
    lock_id = sha256_text(canonical_json(body))
    record = dict(body)
    record["lock_id"] = lock_id
    store = _store(paths.root)
    store.mkdir(parents=True, exist_ok=True)
    path = store / "{0}.json".format(lock_id)
    if path.exists():
        raise Refusal("A plan lock with this identity already exists.", code="PLAN_LOCK_COLLISION")
    atomic_write_json(path, record)
    append_ledger(paths.root, "plan.locked", {
        "lock_id": lock_id,
        "record_sha256": sha256_file(path),
        "plan_sha256": digest,
        "parent_lock_id": body["parent_lock_id"],
        "passing_results_existed": body["passing_results_existed"],
    })
    return {
        "status": "RELOCKED" if latest else "LOCKED",
        "lock": record,
        "lock_count": len(locks) + 1,
        "record_relative_path": path.relative_to(paths.root).as_posix(),
    }


def _changed_fields(old: Mapping[str, Any], new: Mapping[str, Any]) -> List[str]:
    keys = sorted(set(old) | set(new))
    return [key for key in keys if canonical_json(old.get(key)) != canonical_json(new.get(key))]


def plan_status(root: Union[str, Path], *, project: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    """Read-only comparison of the current plan with the lock history."""
    paths = paths_for(root)
    project = load_project(paths.root) if project is None else project
    plan = current_plan(project)
    events = _events(paths.root)
    locks, problems = _load_locks(paths.root, events)
    pass_runs = _pass_run_sequences(events)
    first_pass = min(pass_runs) if pass_runs else None
    latest = locks[-1] if locks else None
    if problems:
        state = "DAMAGED"
    elif latest is None:
        state = "UNLOCKED"
    elif latest.get("plan_sha256") == plan_sha256(plan):
        state = "CURRENT"
    else:
        state = "CHANGED_SINCE_LOCK"
    first_lock_seq = locks[0]["ledger_sequence"] if locks else None
    preceded = bool(first_lock_seq is not None and (first_pass is None or first_lock_seq < first_pass))
    deviations = [
        {
            "lock_id": lock["lock_id"],
            "reason": lock.get("reason", ""),
            "changed_fields": lock.get("changed_fields", []),
            "after_passing_results": bool(lock.get("passing_results_existed")),
            "created_at_utc": lock.get("created_at_utc"),
        }
        for lock in locks[1:]
    ]
    return {
        "state": state,
        "lock_count": len(locks),
        "latest_lock_id": latest.get("lock_id") if latest else None,
        "current_plan_sha256": plan_sha256(plan),
        "changed_fields": _changed_fields(latest.get("plan", {}), plan) if latest else [],
        "passing_runs": len(pass_runs),
        "first_lock_preceded_passing_results": preceded,
        "deviations": deviations,
        "problems": problems,
        "boundaries": {
            "public_preregistration": False,
            "trusted_timestamp": False,
            "writes": 0,
        },
    }


def plan_issues(status: Mapping[str, Any], project: Mapping[str, Any], manuscript_text: str = "") -> List[Dict[str, Any]]:
    """Levelled issues derived from plan status and manuscript wording."""
    issues: List[Dict[str, Any]] = []
    state = status.get("state")
    if state == "DAMAGED":
        issues.append({
            "code": "PLAN_LOCK_DAMAGED", "level": "grave", "subject": "Analysis plan",
            "message": "A recorded plan lock no longer verifies against the ledger.",
            "detail": {"problems": status.get("problems", [])},
        })
    elif state == "UNLOCKED":
        issues.append({
            "code": "PLAN_NOT_LOCKED",
            "level": "submission" if status.get("passing_runs") else "style",
            "subject": "Analysis plan",
            "message": "The hypothesis and analysis plan were never locked, so readers cannot tell which analyses were planned.",
            "detail": {"passing_runs": status.get("passing_runs", 0)},
        })
    elif state == "CHANGED_SINCE_LOCK":
        issues.append({
            "code": "PLAN_CHANGED_SINCE_LOCK", "level": "submission", "subject": "Analysis plan",
            "message": "Locked plan fields were edited without a recorded re-lock and reason.",
            "detail": {"changed_fields": status.get("changed_fields", [])},
        })
    late = [row for row in status.get("deviations", []) if row.get("after_passing_results")]
    if late:
        issues.append({
            "code": "PLAN_REVISED_AFTER_RESULTS", "level": "style", "subject": "Analysis plan",
            "message": "The plan was revised after passing results existed; disclose each deviation and its reason in Methods.",
            "detail": {"deviations": late},
        })
    if manuscript_text:
        methods = project.get("methods") if isinstance(project.get("methods"), Mapping) else {}
        external = str(methods.get("preregistration", "") or "").strip()
        for match in _PREREG_CLAIM.finditer(manuscript_text):
            line_start = manuscript_text.rfind("\n", 0, match.start()) + 1
            sentence_start = max(manuscript_text.rfind(". ", line_start, match.start()) + 1, line_start)
            if _NEGATED.search(manuscript_text[sentence_start:match.start()]):
                continue
            if status.get("first_lock_preceded_passing_results") or len(external) >= 8:
                continue
            issues.append({
                "code": "PREREGISTRATION_CLAIM_UNSUPPORTED", "level": "grave", "subject": "Analysis plan",
                "message": "The manuscript describes the study as preregistered, but no plan lock preceded the first passing "
                           "run and no external registration is recorded in /methods/preregistration.",
                "detail": {"phrase": match.group(0)},
                "offset": match.start(),
            })
    return issues


REPAIRS: Dict[str, List[str]] = {
    "PLAN_LOCK_DAMAGED": [
        "Restore the lock records under .uriel/plan-locks/ from a verified backup.",
        "Investigate the change before trusting results produced after it.",
        "Disclose the lost lock history in Methods and treat affected analyses as exploratory.",
    ],
    "PLAN_NOT_LOCKED": [
        "Run `uriel plan lock --root .` before running confirmatory analyses.",
        "If analyses already ran, lock now and describe all analyses as exploratory in the manuscript.",
        "Record an external registration identifier in /methods/preregistration if one exists.",
    ],
    "PLAN_CHANGED_SINCE_LOCK": [
        "Revert the edited plan fields to the locked values.",
        "Re-lock with `uriel plan lock --reason \"...\"` so the change is recorded as a deviation.",
        "Move the new analysis idea into a separately labelled exploratory analysis.",
    ],
    "PLAN_REVISED_AFTER_RESULTS": [
        "Add a 'Deviations from the plan' paragraph to Methods listing each change and reason.",
        "Report the originally planned analysis alongside the revised one.",
        "Label analyses introduced after results as exploratory.",
    ],
    "PREREGISTRATION_CLAIM_UNSUPPORTED": [
        "Remove the preregistration wording and describe the analyses as planned locally or exploratory.",
        "Record the external registry identifier in /methods/preregistration if the study was registered elsewhere.",
        "State precisely which parts of the plan were fixed before data analysis and how that is evidenced.",
    ],
}


def repairs_for(code: str) -> List[str]:
    return list(REPAIRS.get(code, REPAIRS["PLAN_CHANGED_SINCE_LOCK"]))


__all__ = [
    "PLAN_FIELDS",
    "PLAN_LOCK_SCHEMA",
    "current_plan",
    "lock_plan",
    "plan_issues",
    "plan_sha256",
    "plan_status",
    "repairs_for",
]
