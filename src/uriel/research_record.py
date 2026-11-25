"""Research record operations for the folder and ETAPI backends."""
from __future__ import annotations
import math
import re
from datetime import datetime, timezone
from .record_store import SECTIONS, RecordError, canonical, digest, key, note_body, parse_structured, signature, structured
from .claim_types import validate_evidence_label

MODES = ("exploratory", "evidence-neutral")
CLASSES = ("Closed", "Allowed, not preferred", "Untested", "Upper limit only", "Not yet built")
AUDIT = ("statistic_response", "right_observable", "resolution_smoothing",
         "selection_dust_calibration", "shared_calibration", "equations_units_signs", "covariance")
KINDS = {"lead": "leads", "prediction": "leads", "task": "leads", "result": "conclusions",
         "conclusion": "conclusions", "claim": "manuscript", "source": "sources",
         "decision": "decisions", "gap": "gaps", "ruled-out": "ruled-out", "checklist": "decisions"}

def now():
    return datetime.now(timezone.utc).isoformat()

def required(row, *fields):
    missing = [f for f in fields if f not in row or row[f] in (None, "", [], {})]
    if missing:
        raise RecordError("Missing fields: " + ", ".join(missing))

def finite(value, name, nonnegative=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or (nonnegative and value < 0):
        raise RecordError("Invalid numeric field: " + name)
    return value

def obj(store, identity, kind=None):
    note = store.get(identity)
    if not note:
        raise RecordError("Record not found: " + identity)
    row = parse_structured(note["content"])
    if kind and row.get("kind") != kind:
        raise RecordError("Unexpected record type: " + identity)
    return row

def initialize(store, project, question, mode):
    key(project)
    if mode not in MODES or not question.strip():
        raise RecordError("Verbatim question and declared mode required.")
    initial = {"kind": "project", "project": project, "mode": mode, "question_sha256": digest(question)}
    if store.get("project"):
        if obj(store, "project") != initial:
            raise RecordError("Existing project differs.")
    else:
        store.create("project", "Research record: " + project, structured(initial))
    for identity, title in SECTIONS.items():
        if not store.get(identity):
            store.create(identity, title, question if identity == "question" else "", "project")
    if digest(note_body(store.get("question")["content"])) != initial["question_sha256"]:
        raise RecordError("Verbatim question drift.")
    return initial

def records(store, kind=None, notes=None):
    rows = {}
    for identity, note in (store.list() if notes is None else notes).items():
        if identity in SECTIONS or identity == "project" or identity.startswith(("conflict-", "history-")):
            continue
        if note_body(note["content"]).lstrip().startswith("```json\n"):
            row = parse_structured(note["content"])
            if kind is None or row.get("kind") == kind:
                rows[identity] = row
    return rows

def user_key(identity):
    key(identity)
    if identity in SECTIONS or identity == "project" or identity.startswith(("conflict-", "history-", "task-", "proposal-", "checklist-", "source-alias-", "verbatim-")):
        raise RecordError("Reserved key.")


def add_record(store, identity, row):
    user_key(identity)
    kind = row.get("kind")
    if kind not in ("lead", "claim", "source", "decision", "gap", "ruled-out"):
        raise RecordError("Use the dedicated operation for this kind.")
    if kind == "lead":
        required(row, "idea", "status", "owner")
        if row["status"] not in ("idea", "queued", "waiting on data", "done"):
            raise RecordError("Running leads require a task assignment.")
    elif kind == "claim":
        validate_evidence_label(row)
        if not isinstance(row.get("evidence", []), list) or any(not isinstance(v, str) for v in row.get("evidence", [])):
            raise RecordError("Claim evidence must be a list of record keys.")
    elif kind == "source":
        required(row, "provenance", "sha256")
        if not isinstance(row.get("original_text"), str) or row.get("attachment") or digest(row["original_text"]) != row["sha256"]:
            raise RecordError("Source digest must bind stored exact UTF-8 text; use import for attachments.")
        for k, other in records(store, "source").items():
            if other["sha256"] == row["sha256"]:
                raise RecordError("Exact source already registered: " + k)
    elif kind == "decision":
        required(row, "verbatim", "tried", "workarounds", "result")
    elif kind == "gap":
        required(row, "counter_evidence", "unaddressed", "tension", "discriminating_test")
    else:
        if obj(store, row.get("conclusion", ""), "conclusion")["classification"] != "Closed":
            raise RecordError("Ruled-out record requires a Closed conclusion.")
        required(row, "why")
    return store.create(identity, str(row.get("title") or identity), structured(row), KINDS[kind])

def rewrite(store, identity, body, expected):
    if identity in ("project", "question") or identity not in SECTIONS:
        raise RecordError("Only section prose may be rewritten; structured records are create-only.")
    old = store.get(identity)
    if not old:
        raise RecordError("Missing section.")
    if signature(old) == expected and note_body(old["content"]).strip() and getattr(store, "exclusive_write", True):
        hist = "history-" + digest(canonical(expected))[:24]
        if not store.get(hist):
            store.create(hist, "Superseded: " + identity, structured({"target": identity, "previous": old, "timestamp": now()}), "decisions")
    return store.update(identity, body, expected)

def effective_leads(store, rows=None):
    rows = records(store) if rows is None else rows
    leads = {k: r for k, r in rows.items() if r.get("kind") == "lead"}
    tasks = {k: r for k, r in rows.items() if r.get("kind") == "task"}
    conclusions = {k: r for k, r in rows.items() if r.get("kind") == "conclusion"}
    for k, lead in leads.items():
        lead = dict(lead)
        matches = [(task_id, row) for task_id, row in tasks.items() if row.get("lead") == k]
        if matches:
            lead["task"] = matches[0][0]
            lead["owner"] = matches[0][1]["owner"]
            lead["status"] = "running"
        if any(r.get("lead") == k for r in conclusions.values()):
            lead["status"] = "done"
        leads[k] = lead
    return leads


def check_before_push(store, idea):
    tokens = set(re.findall(r"\w+", idea.casefold())) - {"the", "a", "an", "of", "to", "and", "is", "in"}
    if not tokens:
        raise RecordError("Supply an idea.")
    matches = []
    notes = store.list()
    rows = records(store, notes=notes)
    leads = effective_leads(store, rows)
    for identity, row in rows.items():
        if row.get("kind") not in ("lead", "conclusion", "ruled-out", "task") and row.get("section") not in ("leads", "conclusions", "ruled-out"):
            continue
        if row.get("kind") == "lead":
            row = leads[identity]
        text = canonical(row).casefold()
        linked = row.get("lead") or row.get("conclusion")
        if linked in notes:
            text += " " + notes[linked]["content"].casefold()
        found = sorted(tokens & set(re.findall(r"\w+", text)))
        if not found and idea.casefold() not in text:
            continue
        status = row.get("classification") or row.get("status") or row["kind"]
        if row.get("kind") == "task" and leads.get(row.get("lead"), {}).get("status") == "done":
            status = "done"
        status = {"Closed": "already closed", "running": "already running",
                  "Upper limit only": "tested only as an upper limit"}.get(status, status)
        matches.append({"key": identity, "status": status, "terms": found, "locator": notes[identity]["locator"]})
    for section in ("leads", "conclusions", "ruled-out"):
        if section in notes:
            text = note_body(notes[section]["content"]).casefold()
            found = sorted(tokens & set(re.findall(r"\w+", text)))
            if found:
                matches.append({"key": section, "status": "related section prose; review manually", "terms": found, "locator": notes[section]["locator"]})
    return {"query": idea, "matches": matches, "status": "related records found" if matches else "nothing found",
            "boundary": "Lexical search; not proof of absence."}

def freeze(store, identity, row):
    user_key(identity)
    required(row, "lead", "hypothesis", "control_source", "control_result", "effect_size", "effect_derivation", "unit", "acceptance_criteria")
    obj(store, row["lead"], "lead")
    obj(store, row["control_source"], "source")
    finite(row["effect_size"], "effect_size")
    if any(r.get("lead") == row["lead"] for r in records(store, "result").values()):
        raise RecordError("Results already exist for this lead. Use a new lead for a prospective test.")
    row = dict(row, kind="prediction", mode=obj(store, "project")["mode"], frozen_at=now())
    row.pop("sha256", None)
    row["sha256"] = digest(canonical(row))
    return store.create(identity, "Frozen prediction: " + identity, structured(row), "leads")

def valid_prediction(row):
    return row.get("sha256") == digest(canonical({k: v for k, v in row.items() if k != "sha256"}))

def start_task(store, lead, row):
    lead_row = effective_leads(store).get(lead)
    if not lead_row:
        raise RecordError("Lead not found.")
    required(row, "owner", "question", "inputs", "prediction", "deliverable", "verification", "duplicate_review", "reused", "changes", "missing", "checklist")
    prediction = obj(store, row["prediction"], "prediction")
    if not valid_prediction(prediction) or prediction["lead"] != lead or lead_row["status"] == "done":
        raise RecordError("Task needs an open lead and intact matching prediction.")
    receipt = obj(store, row["checklist"], "checklist")
    search = check_before_push(store, lead_row["idea"])
    current = store.get("current")
    if (receipt.get("stage") != "mid-before" or receipt.get("complete") is not True
            or receipt.get("lead") != lead or receipt.get("prediction") != row["prediction"]
            or receipt.get("current_snapshot") != signature(current)
            or receipt.get("duplicate_search") != search):
        raise RecordError("Complete a fresh mid-before checklist for this lead and prediction.")
    row = dict(row, kind="task", lead=lead, status="running", assigned_at=now(), duplicate_search=search)
    return store.create("task-" + digest(lead)[:24], "Task: " + lead, structured(row), "leads")

def audit_negative(prediction, result):
    findings = []
    if not prediction or not valid_prediction(prediction):
        findings.append("missing or invalid frozen prediction")
    else:
        try:
            size = abs(finite(prediction["effect_size"], "effect_size"))
            sensitivity = finite(result.get("sensitivity"), "sensitivity", True)
            if size <= sensitivity:
                findings.append("predicted size does not exceed sensitivity")
            if result.get("null") is True:
                estimate = finite(result.get("effect_estimate"), "effect_estimate")
                if abs(estimate) > sensitivity:
                    findings.append("reported null exceeds the sensitivity threshold")
                if abs(prediction["effect_size"] - estimate) <= sensitivity:
                    findings.append("observed effect is compatible with the frozen prediction")
            if result.get("unit") != prediction["unit"]:
                findings.append("prediction and sensitivity units differ")
        except (KeyError, RecordError):
            findings.append("invalid predicted size or sensitivity")
    if not isinstance(result.get("effect_estimate"), (int, float)) or isinstance(result.get("effect_estimate"), bool) or not math.isfinite(result["effect_estimate"]):
        findings.append("numeric effect estimate absent")
    if not result.get("sensitivity_basis"):
        findings.append("sensitivity basis absent")
    if result.get("control_reproduced") is not True or not result.get("control_evidence"):
        findings.append("published control not reproduced with evidence")
    if result.get("acceptance_met") is not True or not result.get("acceptance_evidence"):
        findings.append("frozen criteria not evidenced")
    audit = result.get("audit")
    if not isinstance(audit, dict):
        audit = {}
    for item in AUDIT:
        value = audit.get(item, {})
        if not isinstance(value, dict) or value.get("pass") is not True or not isinstance(value.get("reason"), str) or not value["reason"].strip():
            findings.append(item)
    if result.get("null") is not True:
        return {"classification": "Allowed, not preferred", "findings": findings, "disposition": "not a null"}
    if not findings:
        return {"classification": "Closed", "findings": [], "disposition": "powered null under recorded conditions"}
    limit = result.get("upper_limit")
    if isinstance(limit, (int, float)) and not isinstance(limit, bool) and math.isfinite(limit) and limit >= 0 and result.get("limit_scope") and result.get("unit"):
        return {"classification": "Upper limit only", "findings": findings, "disposition": "reported limit; not closed"}
    return {"classification": "Untested", "findings": findings,
            "disposition": "underpowered" if "predicted size does not exceed sensitivity" in findings else "undetermined"}

def add_result(store, identity, row):
    user_key(identity)
    required(row, "lead", "source", "result", "unit", "observed_at", "mode")
    if "effect_estimate" in row:
        finite(row["effect_estimate"], "effect_estimate")
    obj(store, row["lead"], "lead")
    obj(store, row["source"], "source")
    if row["mode"] != obj(store, "project")["mode"] or not isinstance(row.get("null"), bool):
        raise RecordError("Matching mode and boolean null declaration required.")
    task = store.get("task-" + digest(row["lead"])[:24])
    if task:
        assignment = parse_structured(task["content"])
        if row.get("owner") != assignment["owner"] or row.get("prediction") != assignment["prediction"] or not row.get("verification"):
            raise RecordError("Assigned result requires matching owner, frozen prediction and verification.")
    pred = obj(store, row["prediction"], "prediction") if row.get("prediction") else None
    if pred:
        if pred["lead"] != row["lead"] or pred["mode"] != row["mode"]:
            raise RecordError("Prediction lead or mode differs.")
        try:
            observed = datetime.fromisoformat(row["observed_at"])
            frozen = datetime.fromisoformat(pred["frozen_at"])
            if observed.tzinfo is None or observed < frozen or observed > datetime.now(timezone.utc):
                pred = None
        except (ValueError, TypeError):
            pred = None
    row = dict(row, kind="result", recorded_at=now(), exploratory=pred is None or not valid_prediction(pred), negative_audit=audit_negative(pred, row))
    row.pop("record_sha256", None)
    row["record_sha256"] = digest(canonical(row))
    return store.create(identity, "Result: " + identity, structured(row), "conclusions")

def valid_result(row):
    return row.get("record_sha256") == digest(canonical({k: v for k, v in row.items() if k != "record_sha256"}))


def conclude(store, identity, row):
    user_key(identity)
    required(row, "lead", "classification", "logical_steps", "alternatives", "workarounds", "would_change", "thoroughness", "reviewer", "mode")
    if row["classification"] not in CLASSES or row["mode"] != obj(store, "project")["mode"]:
        raise RecordError("Invalid classification or mode.")
    obj(store, row["lead"], "lead")
    if not isinstance(row.get("coincidence"), bool) or not isinstance(row.get("multi_factor"), bool):
        raise RecordError("Declare coincidence and multi_factor as booleans.")
    if row.get("coincidence"):
        required(row, "condition_reached", "local_state_change", "consequence", "recurrence")
    if row.get("multi_factor"):
        required(row, "single_factor_baselines", "add_one", "leave_one_out", "combined_result", "combined_null")
    if row.get("result"):
        result = obj(store, row["result"], "result")
        if not valid_result(result):
            raise RecordError("Result record hash drift.")
        if result["lead"] != row["lead"] or result["mode"] != row["mode"]:
            raise RecordError("Result lead or mode differs.")
        pred = obj(store, result["prediction"], "prediction") if result.get("prediction") and not result["exploratory"] else None
        verified = audit_negative(pred, result)
        if row["classification"] != verified["classification"]:
            raise RecordError("Classification must match audit: " + verified["classification"])
        task = store.get("task-" + digest(row["lead"])[:24])
        if task and parse_structured(task["content"])["owner"] == row["reviewer"]:
            raise RecordError("Task owner cannot supervise own result.")
        row = dict(row, audit=verified, source=result["source"], result_size=result.get("effect_estimate"), sensitivity=result.get("sensitivity"), sensitivity_basis=result.get("sensitivity_basis"), unit=result["unit"], result_text=result["result"], prediction=result.get("prediction"), result_sha256=result["record_sha256"])
    elif row["classification"] not in ("Untested", "Not yet built"):
        raise RecordError("Tested conclusion requires result.")
    row = dict(row, kind="conclusion", concluded_at=now())
    row.pop("record_sha256", None)
    row["record_sha256"] = digest(canonical(row))
    return store.create(identity, "Conclusion: " + identity, structured(row), "conclusions")

def summary(store):
    grouped = {classification: [] for classification in CLASSES}
    rows = records(store)
    for identity, row in rows.items():
        if row.get("kind") == "conclusion":
            if not valid_result(row):
                raise RecordError("Conclusion record hash drift: " + identity)
            grouped[row["classification"]].append({"key": identity, **row})
    leads = effective_leads(store, rows)
    tasks = {k: dict(row, status=leads.get(row.get("lead"), {}).get("status", row["status"])) for k, row in rows.items() if row.get("kind") == "task"}
    return {"conclusions": grouped, "leads": leads, "tasks": tasks,
            "boundary": "Recorded audit, not scientific validation."}
