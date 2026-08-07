"""Submission lifecycle orchestration.

Deterministic, standard-library implementation of the submission workflow:
init, import-decision, plan, build-response, guide, verify, archive, status,
and next-prompt. All state lives under ``<root>/.uriel/lifecycle/`` and every
record is written immutably through the checkpoint conventions.
"""
from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .checkpoints import GenerationRefusal
from .core import (
    Refusal,
    atomic_write_json,
    atomic_write_text,
    canonical_json,
    canonical_root,
    guard_path,
    paths_for,
    read_json,
    sha256_bytes,
    sha256_file,
    sha256_text,
    utc_now,
)
from .decisions import (
    DECISION_CLASSES,
    build_decision_import,
    confirm_decision,
    load_decision,
    validate_decision_import,
    write_decision,
)
from .packet import (
    PACKET_TYPES,
    preflight_packet,
    validate_packet_manifest,
    verify_packet,
    write_packet_generation,
)
from .publication import (
    AUTHORITY_IS_EXCLUSIVE,
    authority_source_for,
    build_authority,
    transition_for_decision,
    validate_authority,
    write_authority,
)

SUBMISSION_STATE_SCHEMA = "uriel.submission_state.v1"

REVISION_CLASSES = frozenset({"major_revision", "minor_revision", "revise_and_resubmit"})
ACCEPTANCE_CLASSES = frozenset({"accepted", "accepted_in_production", "proofs_received"})
REJECTION_CLASSES = frozenset({"desk_rejection", "rejected_with_feedback", "rejected_resubmit_elsewhere"})
STATUS_ONLY_CLASSES = frozenset(
    {"acknowledged", "submitted", "administrative_check", "under_review", "review_invitation", "withdrawn", "unknown"}
)

_ITEM_SPLIT = re.compile(r"^\s*(?:reviewer\s*\d+[:\-]?|comment\s*\d+[:\-]?|[Rr]\d+[.:\-]|#\d+|\(\d+\)|\d+[.)])\s*", re.MULTILINE)

_CSV_FORMULA = re.compile(r"^[=+\-@]")


def _sanitize_csv_cell(value: Any) -> str:
    text = str(value)
    if _CSV_FORMULA.match(text):
        return "'" + text
    return text


def _csv(rows: Sequence[Sequence[Any]]) -> str:
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    for row in rows:
        writer.writerow([_sanitize_csv_cell(cell) for cell in row])
    return buffer.getvalue()


class SubmissionPaths:
    def __init__(self, root: Path) -> None:
        self.root = canonical_root(root)
        self.lifecycle = self.root / ".uriel" / "lifecycle"
        self.index_path = self.lifecycle / "submission.json"
        self.decisions = self.lifecycle / "decisions"
        self.authority = self.lifecycle / "authority"
        self.plans = self.lifecycle / "plans"
        self.packets = self.lifecycle / "packets"
        self.archive = self.lifecycle / "archive"


def submission_paths(root: Any) -> SubmissionPaths:
    return SubmissionPaths(root)


def load_index(paths: SubmissionPaths) -> Dict[str, Any]:
    if not paths.index_path.is_file():
        raise Refusal(
            "Submission lifecycle is not initialized.",
            code="SUBMISSION_NOT_INITIALIZED",
            repairs=["Run `uriel submit init --root <root>` first."],
        )
    return read_json(paths.index_path)


def _default_index() -> Dict[str, Any]:
    return {
        "schema": SUBMISSION_STATE_SCHEMA,
        "created_at_utc": utc_now(),
        "manuscript_id": None,
        "venue": None,
        "current_decision_id": None,
        "authority_state": "not_assessed",
        "authority_id": None,
        "plan_id": None,
        "packet_id": None,
        "packet_dir": None,
        "archives": [],
    }


def submit_init(root: Any, *, dry_run: bool = False) -> Dict[str, Any]:
    paths = submission_paths(root)
    if paths.index_path.exists() and not dry_run:
        raise Refusal(
            "Submission lifecycle is already initialized.",
            code="SUBMISSION_EXISTS",
            repairs=["Run `uriel submit status --root <root>` to inspect it."],
        )
    index = _default_index()
    if dry_run:
        return {"dry_run": True, "index": index, "message": "would initialize submission lifecycle"}
    paths.lifecycle.mkdir(parents=True, exist_ok=True)
    atomic_write_json(paths.index_path, index)
    return {"initialized": True, "index_path": paths.index_path.relative_to(paths.root).as_posix()}


def _save_index(paths: SubmissionPaths, index: Mapping[str, Any]) -> None:
    atomic_write_json(paths.index_path, index)


def import_decision(
    root: Any,
    source_text: str,
    *,
    venue: Optional[str] = None,
    manuscript_id: Optional[str] = None,
    deadline: Optional[str] = None,
    decision_class: Optional[str] = None,
    user_confirmed: bool = False,
    dry_run: bool = False,
) -> Dict[str, Any]:
    paths = submission_paths(root)
    index = load_index(paths)
    record = build_decision_import(
        source_text,
        venue=venue,
        manuscript_id=manuscript_id,
        deadline=deadline,
        decision_class=decision_class,
        user_confirmed=user_confirmed,
    )
    if dry_run:
        return {"dry_run": True, "decision": record}
    write_decision(paths.decisions, record)
    updated = dict(index)
    updated["current_decision_id"] = record["decision_id"]
    updated["manuscript_id"] = manuscript_id or updated["manuscript_id"]
    updated["venue"] = venue or updated["venue"]
    authority_result: Optional[Dict[str, Any]] = None
    if record["confirmation_state"] in ("explicit", "user_confirmed"):
        state = transition_for_decision(record["decision_class"])
        if state is not None:
            generation = updated["authority_state"] or "not_assessed"
            authority = build_authority(
                project_generation=generation,
                state=state,
                authority_source=authority_source_for(record["confirmation_state"], record["source_sha256"]),
                source_artifact_sha256=record["source_sha256"],
                notes=f"from decision {record['decision_id']} ({record['decision_class']})",
            )
            path = write_authority(paths.authority, authority)
            updated["authority_state"] = state
            updated["authority_id"] = path.stem
            authority_result = authority
    _save_index(paths, updated)
    return {
        "decision": record,
        "authority": authority_result,
        "index": updated,
        "note": (
            "Inferred class is recorded as a proposal and does not change publication authority "
            "until the language is explicit or the user confirms it."
            if record["confirmation_state"] == "proposed_unconfirmed"
            else "Confirmed decision applied to publication authority."
        ),
    }


def _review_items(source_text: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    previous_end = 0
    first = True
    for match in _ITEM_SPLIT.finditer(source_text):
        segment = source_text[previous_end:match.start()].strip()
        previous_end = match.end()
        if first:
            first = False
            continue
        if segment:
            items.append(segment)
    tail = source_text[previous_end:].strip()
    if tail:
        items.append(tail)
    if not items:
        items = [source_text.strip()]
    records: List[Dict[str, Any]] = []
    for index, part in enumerate(items, start=1):
        lowered = part.lower()
        if any(word in lowered for word in ("evidence", "data", "figure", "table", "statistical", "power", "sample")):
            classification = "requested evidence"
        elif any(word in lowered for word in ("method", "control", "design", "bias", "protocol", "reproducib")):
            classification = "methodological concern"
        elif any(word in lowered for word in ("interpret", "conclusion", "overstate", "causal", "generaliz")):
            classification = "interpretation concern"
        elif any(word in lowered for word in ("format", "grammar", "typo", "spelling", "style", "wording", "reference")):
            classification = "formatting/editorial"
        elif any(word in lowered for word in ("impossible", "cannot", "contradict", "conflict", "inconsistent")):
            classification = "conflict or impossible request"
        elif part.endswith("?") or "?" in part:
            classification = "question"
        elif "positive" in lowered or "appreciate" in lowered or "interesting" in lowered:
            classification = "positive observation with no action"
        else:
            classification = "required change"
        records.append(
            {
                "schema": "uriel.review_item.v1",
                "item_id": f"item-{index:02d}",
                "decision_id": None,
                "source_text": part[:1000],
                "classification": classification,
                "status": "open",
                "priority": "high" if classification in ("requested evidence", "methodological concern", "conflict or impossible request") else "medium",
                "proposed_repair": "",
                "evidence_location": None,
            }
        )
    return records


def _action_for(item: Mapping[str, Any], index: int) -> Dict[str, Any]:
    classification = item["classification"]
    if classification == "requested evidence":
        action_type = "add_evidence"
    elif classification == "methodological concern":
        action_type = "add_analysis"
    elif classification in ("question", "positive observation with no action"):
        action_type = "respond_text"
    else:
        action_type = "edit_manuscript"
    return {
        "schema": "uriel.revision_action.v1",
        "action_id": f"action-{index:02d}",
        "review_item_id": item["item_id"],
        "action_type": action_type,
        "description": item["source_text"][:200],
        "status": "open",
        "priority": item["priority"],
        "depends_on": [],
        "manuscript_location": None,
        "notes": "",
    }


def submit_plan(root: Any, *, dry_run: bool = False) -> Dict[str, Any]:
    paths = submission_paths(root)
    index = load_index(paths)
    decision_id = index.get("current_decision_id")
    if not decision_id:
        raise Refusal("No decision imported yet.", code="NO_DECISION", repairs=["Run `uriel submit import-decision` first."])
    decision = load_decision(paths.decisions / f"{decision_id}.json")
    decision_class = decision["decision_class"]
    source_text = str(decision.get("explicit_status_text", ""))
    if decision_class in REVISION_CLASSES:
        items = _review_items(source_text)
        actions = [_action_for(item, idx) for idx, item in enumerate(items, start=1)]
        plan = {
            "schema": "uriel.revision_plan.v1",
            "plan_id": f"plan-{decision_id}",
            "decision_id": decision_id,
            "kind": "revision_response",
            "items": items,
            "actions": actions,
            "unresolved_questions": decision.get("unresolved_ambiguity", []),
        }
    elif decision_class in ACCEPTANCE_CLASSES:
        plan = {
            "schema": "uriel.acceptance_plan.v1",
            "plan_id": f"plan-{decision_id}",
            "decision_id": decision_id,
            "kind": "production",
            "obligations": {
                "scientific": [],
                "editorial": [],
                "administrative": [],
                "production": [],
            },
            "unresolved_questions": decision.get("unresolved_ambiguity", []),
        }
    elif decision_class in REJECTION_CLASSES:
        plan = {
            "schema": "uriel.salvage_plan.v1",
            "plan_id": f"plan-{decision_id}",
            "decision_id": decision_id,
            "kind": "resubmission",
            "what_remains_valuable": "",
            "shortest_repair_path": "",
            "best_supported_claim": "",
            "experiment_evidence_plan": "",
            "venue_selection_criteria": "",
            "venue_requirements_notice": (
                "Official venue requirements were not supplied. Use the exact search/paste request in the "
                "resubmission packet to obtain current instructions before choosing a venue."
            ),
            "unresolved_questions": decision.get("unresolved_ambiguity", []),
        }
    else:
        plan = {
            "schema": "uriel.status_note.v1",
            "plan_id": f"plan-{decision_id}",
            "decision_id": decision_id,
            "kind": "status_only",
            "note": (
                f"Decision class {decision_class} does not require a response packet. "
                "Import a revision, acceptance, or rejection decision when one arrives."
            ),
        }
    if dry_run:
        return {"dry_run": True, "plan": plan}
    paths.plans.mkdir(parents=True, exist_ok=True)
    atomic_write_json(paths.plans / f"{plan['plan_id']}.json", plan)
    updated = dict(index)
    updated["plan_id"] = plan["plan_id"]
    _save_index(paths, updated)
    return {"plan": plan, "plan_id": plan["plan_id"]}


def _load_plan(paths: SubmissionPaths, index: Mapping[str, Any]) -> Dict[str, Any]:
    plan_id = index.get("plan_id")
    if plan_id and (paths.plans / f"{plan_id}.json").is_file():
        return read_json(paths.plans / f"{plan_id}.json")
    return submit_plan(paths.root)["plan"]


def _packet_type_for(decision_class: str) -> str:
    if decision_class in REVISION_CLASSES:
        return "revision_response"
    if decision_class == "conditional_acceptance":
        return "conditional_acceptance"
    if decision_class in ACCEPTANCE_CLASSES:
        return "production"
    if decision_class in REJECTION_CLASSES:
        return "resubmission"
    if decision_class == "withdrawn":
        return "archive"
    return "lens_review"


def _render_readme_first() -> str:
    return (
        "# Read this first\n\n"
        "This packet is a Uriel-generated, generation-bound working packet.\n\n"
        "## Your task\n\n"
        "Read `MANIFEST.json`, then read the numbered files in order. Complete every\n"
        "non-blocked task using only the supplied evidence and clearly labeled\n"
        "inferences.\n\n"
        "Do not:\n\n"
        "- invent citations, data, experiments, approvals, or venue rules;\n"
        "- claim to have inspected an attachment that is absent;\n"
        "- treat another author's conclusion as primary evidence;\n"
        "- alter publication status without explicit support;\n"
        "- issue The Blessing of Uriel;\n"
        "- ask whether to continue between ordinary steps.\n\n"
        "Ask all unavoidable questions in one numbered batch.\n\n"
        "Update the files named in `11_NEXT_INSTRUCTION.md`. Preserve unresolved\n"
        "limitations. Write an exact next prompt before stopping.\n"
    )


def _render_next_instruction() -> str:
    return (
        "# Next instruction\n\n"
        "Paste this into the next AI session:\n\n"
        "```text\n"
        "Read 00_READ_ME_FIRST.md and MANIFEST.json. Continue from the recorded packet\n"
        "state. Complete every non-blocked task, ask all unavoidable questions in one\n"
        "numbered batch, update the required files, verify character limits and\n"
        "attachments, write a new NEXT_INSTRUCTION.md, and stop only when complete or\n"
        "genuinely blocked. Do not invent evidence or issue a Blessing.\n"
        "```\n"
    )


def _decision_summary_md(decision: Mapping[str, Any]) -> str:
    lines = [
        "# Project or decision summary",
        "",
        f"- Decision ID: {decision['decision_id']}",
        f"- Class: {decision['decision_class']} (confidence {decision.get('inference_confidence')})",
        f"- Confirmation: {decision['confirmation_state']}",
        f"- Venue: {decision.get('venue') or 'not supplied'}",
        f"- Manuscript ID: {decision.get('manuscript_id') or 'not supplied'}",
        f"- Deadline: {decision.get('deadline') or 'not supplied'}",
        f"- Source SHA-256: {decision['source_sha256']}",
        "",
        "## Explicit status language",
        "",
        "```text",
        str(decision.get("explicit_status_text", "")),
        "```",
        "",
        "## Unresolved ambiguity",
        "",
    ]
    ambiguities = decision.get("unresolved_ambiguity") or []
    lines.extend(f"- {item}" for item in ambiguities) if ambiguities else lines.append("- none recorded")
    lines.append("")
    lines.append("Missing evidence remains missing. AI output remains advisory unless it is converted into a verified project artifact through Uriel's deterministic workflow.")
    return "\n".join(lines)


def _render_walkthrough(fields: Sequence[Mapping[str, Any]]) -> str:
    total = len(fields)
    sections = ["# Submission form walkthrough", "", "Use one section per field.", ""]
    for index, field in enumerate(fields, start=1):
        required = "Yes" if field.get("required") else "No"
        limit = field.get("maximum_characters")
        words = field.get("maximum_words")
        if limit is not None:
            limit_text = str(limit) + " characters"
        elif words is not None:
            limit_text = str(words) + " words"
        else:
            limit_text = "not supplied"
        answer = str(field.get("proposed_answer", ""))
        sections.extend(
            [
                f"## Field {index} of {total} — {field.get('label', '')}",
                "",
                f"**Required:** {required}",
                f"**Limit:** {limit_text}",
                f"**Requirement source:** {field.get('requirement_source') or 'user-supplied form'}",
                "",
                "### Recommended entry",
                "",
                "```text",
                answer,
                "```",
                "",
                f"**Character count:** {len(answer)}",
                "",
                "### Why this answer is supported",
                "",
            ]
        )
        facts = field.get("supporting_facts") or []
        sections.extend(f"- {fact}" for fact in facts) if facts else sections.append("- no facts supplied")
        sections.extend(["", "### Confirm before pasting", ""])
        placeholders = field.get("unresolved_placeholders") or []
        sections.extend(f"- {placeholder}" for placeholder in placeholders) if placeholders else sections.append("- none")
        sections.extend(["", "### Do not include", ""])
        exclusions = field.get("do_not_include") or []
        sections.extend(f"- {item}" for item in exclusions) if exclusions else sections.append("- none")
        sections.extend(["", "### Associated attachment", "", f"`{field.get('attachment') or 'none'}`", ""])
    return "\n".join(sections)


def build_response(root: Any, *, fields: Optional[Sequence[Mapping[str, Any]]] = None, dry_run: bool = False) -> Dict[str, Any]:
    paths = submission_paths(root)
    index = load_index(paths)
    decision_id = index.get("current_decision_id")
    if not decision_id:
        raise Refusal("No decision imported yet.", code="NO_DECISION")
    decision = load_decision(paths.decisions / f"{decision_id}.json")
    packet_type = _packet_type_for(decision["decision_class"])
    if packet_type == "lens_review":
        raise Refusal(
            f"Decision class {decision['decision_class']} has no response packet yet.",
            code="NO_PACKET_FOR_DECISION",
            repairs=["Import a revision, acceptance, conditional-acceptance, or rejection decision."],
        )
    plan = _load_plan(paths, index)
    summary = _decision_summary_md(decision)
    items = plan.get("items", [])
    actions = plan.get("actions", [])
    walkthrough = _render_walkthrough(fields or [])
    response_lines = ["# Response to reviewers", ""]
    for item in items:
        response_lines.extend(
            [
                f"## {item['item_id']} — {item['classification']}",
                "",
                "**Comment:**",
                "",
                "```text",
                str(item.get("source_text", ""))[:800],
                "```",
                "",
                "**Proposed repair:**",
                "",
                "```text",
                str(item.get("proposed_repair", "")),
                "```",
                "",
            ]
        )
    response_md = "\n".join(response_lines) if items else "# Response to reviewers\n\nNo reviewer items were extracted. Supply the reviewer comments to build a response matrix.\n"
    required_csv = _csv(
        [
            ("action_id", "action_type", "priority", "status", "review_item_id", "description"),
            *[
                (
                    action["action_id"],
                    action["action_type"],
                    action["priority"],
                    action["status"],
                    action["review_item_id"],
                    action["description"],
                )
                for action in actions
            ],
        ]
    )
    evidence_rows: List[Sequence[Any]] = [("claim", "evidence", "evidence_sha256", "status")]
    if not items:
        evidence_rows.append(("not yet supplied", "", "", "open"))
    evidence_csv = _csv(evidence_rows)
    plan_md_lines = [
        "# Revision or completion plan",
        "",
        f"- Plan ID: {plan.get('plan_id')}",
        f"- Decision: {decision['decision_class']}",
        "",
    ]
    if plan.get("kind") == "revision_response":
        plan_md_lines.append(f"- Review items: {len(items)}")
        plan_md_lines.append(f"- Actions: {len(actions)}")
        plan_md_lines.append("")
        plan_md_lines.append("Every action below must trace to evidence or an explicit manuscript location before the revised manuscript is submitted.")
    elif plan.get("kind") == "production":
        plan_md_lines.append("Exhaustive obligations plan: scientific, editorial, administrative, and production obligations are listed; each must be completed or explicitly waived with a reason.")
        for category, obligations in (plan.get("obligations") or {}).items():
            plan_md_lines.append("")
            plan_md_lines.append(f"### {category.capitalize()}")
            plan_md_lines.extend(f"- {obligation}" for obligation in obligations) if obligations else plan_md_lines.append("- none recorded yet")
    elif plan.get("kind") == "resubmission":
        plan_md_lines.extend(
            [
                "### What remains valuable",
                "",
                str(plan.get("what_remains_valuable") or "Not yet supplied."),
                "",
                "### Shortest repair path",
                "",
                str(plan.get("shortest_repair_path") or "Not yet supplied."),
                "",
                "### Best supported claim after revision",
                "",
                str(plan.get("best_supported_claim") or "Not yet supplied."),
                "",
                "### Experiment/evidence plan",
                "",
                str(plan.get("experiment_evidence_plan") or "Not yet supplied."),
                "",
                "### Venue selection criteria",
                "",
                str(plan.get("venue_selection_criteria") or "Not yet supplied."),
                "",
                str(plan.get("venue_requirements_notice") or ""),
                "",
                "Do not recommend a venue without current official requirements. If offline, paste this exact request into a search:",
                "",
                "```text",
                "What are the current official submission requirements, scope, and format for [VENUE]? Quote the instructions page.",
                "```",
                "",
            ]
        )
    else:
        plan_md_lines.append(str(plan.get("note", "")))
    plan_md = "\n".join(plan_md_lines)
    cover_md = (
        "# Cover or response letter\n\n"
        "Draft cover letter for the current decision.\n\n"
        "## To the editors\n\n"
        f"We respond to the decision recorded in `01_PROJECT_OR_DECISION_SUMMARY.md` ({decision['decision_class']}). "
        "Complete this letter with the manuscript title, author list, and any editor-specific request.\n\n"
        "## Point-by-point response\n\n"
        "Refer to `05_RESPONSE_TO_REVIEWERS.md` for the itemized responses.\n\n"
        "## Declarations\n\n"
        "Complete the conflict-of-interest, funding, ethics, and data-availability statements before submission.\n"
    )
    file_checklist = (
        "# File checklist\n\n"
        "Verify before submission:\n\n"
        "- [ ] 00_READ_ME_FIRST.md present\n"
        "- [ ] 01 project/decision summary complete\n"
        "- [ ] 02 required actions all addressed or explicitly deferred\n"
        "- [ ] 03 plan complete\n"
        "- [ ] 04 claim/evidence map links every claim to an artifact hash\n"
        "- [ ] 05 response to reviewers complete\n"
        "- [ ] 06 cover letter complete\n"
        "- [ ] 07 submission fields verified against the official form\n"
        "- [ ] 08 form walkthrough reviewed field by field\n"
        "- [ ] 09 every attachment present and hashed\n"
        "- [ ] 10 limitations and unknowns preserved\n"
        "- [ ] character limits checked; no placeholder text remains\n"
    )
    limitations_md = (
        "# Limitations and unknowns\n\n"
        + "\n".join(f"- {question}" for question in (decision.get("unresolved_ambiguity") or []))
        + ("\n" if decision.get("unresolved_ambiguity") else "- none recorded\n")
        + "\n"
        "Missing evidence remains missing. Nothing in this packet was invented; every inference is labeled.\n"
    )
    files: Dict[str, bytes] = {
        "00_READ_ME_FIRST.md": _render_readme_first().encode("utf-8"),
        "01_PROJECT_OR_DECISION_SUMMARY.md": summary.encode("utf-8"),
        "02_REQUIRED_ACTIONS.csv": required_csv.encode("utf-8"),
        "03_REVISION_OR_COMPLETION_PLAN.md": plan_md.encode("utf-8"),
        "04_CLAIM_EVIDENCE_MAP.csv": evidence_csv.encode("utf-8"),
        "05_RESPONSE_TO_REVIEWERS.md": response_md.encode("utf-8"),
        "06_COVER_OR_RESPONSE_LETTER.md": cover_md.encode("utf-8"),
        "09_FILE_CHECKLIST.md": file_checklist.encode("utf-8"),
        "10_LIMITATIONS_AND_UNKNOWNS.md": limitations_md.encode("utf-8"),
        "11_NEXT_INSTRUCTION.md": _render_next_instruction().encode("utf-8"),
    }
    if fields:
        files["07_SUBMISSION_FIELDS.json"] = canonical_json(list(fields)).encode("utf-8")
        files["08_FORM_WALKTHROUGH.md"] = walkthrough.encode("utf-8")
    warnings = ["Substantive sections are deterministic skeletons; operator-supplied evidence is required before submission."]
    project_generation = "not_assessed"
    try:
        manifest = read_json(paths.root / ".uriel" / "manifest.json")
        project_generation = str(manifest.get("manifest_sha256", "not_assessed"))
    except Exception:
        pass
    if dry_run:
        return {"dry_run": True, "packet_type": packet_type, "files": sorted(files), "manifest_status": "ready"}
    packet_dir, manifest_record = write_packet_generation(
        paths.packets,
        packet_type=packet_type,
        project_generation=project_generation,
        files=files,
        parent_packet_id=index.get("packet_id"),
        warnings=warnings,
    )
    updated = dict(index)
    updated["packet_id"] = manifest_record["packet_id"]
    updated["packet_dir"] = str(packet_dir.relative_to(paths.root))
    _save_index(paths, updated)
    return {
        "packet": manifest_record,
        "packet_dir": updated["packet_dir"],
        "preflight": preflight_packet(packet_dir),
    }


def _load_fields_file(paths: SubmissionPaths, fields_path: str) -> List[Dict[str, Any]]:
    target = guard_path(paths.root, fields_path, must_exist=True)
    try:
        parsed = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal(f"Could not parse submission fields file: {exc}", code="INVALID_FIELDS") from exc
    if isinstance(parsed, Mapping):
        parsed = parsed.get("fields", [])
    if not isinstance(parsed, list):
        raise Refusal("Submission fields file must contain an array of uriel.submission_field.v1 records.", code="INVALID_FIELDS")
    return [field for field in parsed if isinstance(field, Mapping)]


def submit_guide(root: Any, *, fields_path: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
    paths = submission_paths(root)
    index = load_index(paths)
    if fields_path:
        fields = _load_fields_file(paths, fields_path)
    else:
        fields = []
    violations: List[str] = []
    for field in fields:
        if not isinstance(field, Mapping) or field.get("schema") != "uriel.submission_field.v1":
            violations.append(f"field {field!r} is not a uriel.submission_field.v1 record")
    if violations:
        raise Refusal("Invalid submission fields: " + "; ".join(violations[:3]), code="INVALID_FIELDS")
    walkthrough = _render_walkthrough(fields)
    if dry_run:
        return {"dry_run": True, "field_count": len(fields), "walkthrough": walkthrough}
    paths.lifecycle.mkdir(parents=True, exist_ok=True)
    output = paths.lifecycle / "guide" / f"walkthrough-{index.get('current_decision_id', 'pending')}.md"
    output.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(output, walkthrough)
    return {"output": str(output.relative_to(paths.root)), "field_count": len(fields), "walkthrough": walkthrough}


def submit_verify(root: Any) -> Dict[str, Any]:
    paths = submission_paths(root)
    index = load_index(paths)
    result: Dict[str, Any] = {"initialized": True, "decision_ok": False, "authority_ok": False, "packet": None}
    decision_id = index.get("current_decision_id")
    if decision_id:
        decision_path = paths.decisions / f"{decision_id}.json"
        result["decision_ok"] = decision_path.is_file() and not validate_decision_import(
            load_decision(decision_path)
        )
    authority_id = index.get("authority_id")
    if authority_id:
        authority_path = paths.authority / f"{authority_id}.json"
        if authority_path.is_file():
            result["authority_ok"] = not validate_authority(read_json(authority_path))
    packet_dir = index.get("packet_dir")
    if packet_dir:
        packet_path = paths.root / packet_dir
        result["packet"] = verify_packet(packet_path)
        result["packet_preflight"] = preflight_packet(packet_path)
    result["verified"] = bool(result.get("packet") and result["packet"].get("status") == "pass")
    return result


def _deterministic_zip(packet_dir: Path, destination: Path) -> Path:
    with zipfile.ZipFile(str(destination), "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(packet_dir.rglob("*")):
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(path.relative_to(packet_dir).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, path.read_bytes())
    return destination


def archive_submission(root: Any, *, dry_run: bool = False) -> Dict[str, Any]:
    paths = submission_paths(root)
    index = load_index(paths)
    packet_dir = index.get("packet_dir")
    if not packet_dir:
        raise Refusal("No packet to archive.", code="NO_PACKET", repairs=["Run `uriel submit build-response` first."])
    packet_path = paths.root / packet_dir
    packet_id = index["packet_id"]
    destination = paths.archive / f"{packet_id}.zip"
    if destination.exists() and not dry_run:
        raise Refusal(f"Archive already exists: {destination.name}", code="ARCHIVE_EXISTS")
    if dry_run:
        return {"dry_run": True, "archive": str(destination.relative_to(paths.root)), "packet_id": packet_id}
    paths.archive.mkdir(parents=True, exist_ok=True)
    _deterministic_zip(packet_path, destination)
    receipt = {"packet_id": packet_id, "zip_sha256": sha256_file(destination), "created_at_utc": utc_now()}
    updated = dict(index)
    updated["archives"] = [*updated.get("archives", []), receipt]
    _save_index(paths, updated)
    return {"archive": str(destination.relative_to(paths.root)), "receipt": receipt}


def submission_status(root: Any) -> Dict[str, Any]:
    paths = submission_paths(root)
    index = load_index(paths)
    decision = None
    decision_id = index.get("current_decision_id")
    if decision_id:
        decision_path = paths.decisions / f"{decision_id}.json"
        if decision_path.is_file():
            decision = load_decision(decision_path)
    return {
        "initialized": True,
        "decision": decision,
        "authority_state": index.get("authority_state"),
        "plan_id": index.get("plan_id"),
        "packet_id": index.get("packet_id"),
        "archives": index.get("archives", []),
    }


def submit_next_prompt(root: Any, *, output: Optional[str] = None, dry_run: bool = False) -> Dict[str, Any]:
    paths = submission_paths(root)
    index = load_index(paths)
    prompt = _render_next_instruction()
    summary_lines = [
        f"- Project state: {index.get('authority_state')}",
        f"- Current decision: {index.get('current_decision_id') or 'none'}",
        f"- Current packet: {index.get('packet_id') or 'none'}",
    ]
    full = prompt + "\n" + "\n".join(summary_lines) + "\n"
    if dry_run or not output:
        return {"dry_run": bool(dry_run) or not output, "next_prompt": full}
    destination = guard_path(paths.root, output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(destination, full)
    return {"output": str(destination.relative_to(paths.root)), "next_prompt": full}
