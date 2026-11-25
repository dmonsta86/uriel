"""The research protocol driver behind ``uriel next``.

One command answers "what should happen next?" for the whole path from a
rough idea to a submission-ready manuscript.  It evaluates, read-only, the
same deterministic checks the rest of Uriel uses (the Three Gates, the plan
lock, the Paper Builder check, the build receipt, and the recorded audit),
sorts every open item into seven ordered stages, and names exactly one next
action with its reason, a concrete command or file location, and the
condition under which it counts as done.

The ordering is deliberate: a question is framed before prior work is mapped,
the plan is locked before evidence is bound, the result is challenged before
the manuscript is written, and nothing is called ready until a human has done
the parts no software can do.  Items that need human judgment (attestations,
ethics, reference verification, the final read) are marked ``owner: human``
so an assistant stops and asks instead of improvising.

The driver grants no authority and writes nothing, except an optional
create-only prompt file for the next assistant session.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from . import adversarial, framing, model_check, paper_builder, plan_lock
from .datapoints import _run_provenance
from .audit import _gate1, _gate2, _gate3
from .core import (
    Refusal,
    atomic_write,
    build_manifest,
    guard_path,
    load_project,
    paths_for,
    read_json,
    safe_relative_path,
    sha256_file,
    sha256_text,
)
from .schema import validate_manifest

NEXT_SCHEMA = "uriel.next_step.v1"
TARGETS = ("draft", "submission", "adversarial")
_GATE_PROFILE = {"draft": "standard", "submission": "submission", "adversarial": "submission"}
_PAPER_PROFILE = {"draft": "draft", "submission": "submission", "adversarial": "adversarial"}

STAGES: Tuple[Tuple[str, str, str], ...] = (
    ("frame", "Frame the question", "A precise, neutral, falsifiable question with defined terms and decision criteria."),
    ("prior_work", "Map prior work", "A dated, reproducible search with the nearest prior work and honest novelty limits."),
    ("design", "Design and lock the plan", "Method, sample, analysis, controls, exclusions, ethics, and any model's equation, units, role, domain, and assumptions fixed before results, then locked."),
    ("evidence", "Bind evidence and run the analysis", "Every claim mapped to hashed primary evidence and a passing, recorded analysis run."),
    ("challenge", "Challenge the result", "Every claim has a recorded rival explanation and a way to tell them apart; models are validated and compared; counterevidence and limitations are on the record."),
    ("manuscript", "Write the manuscript", "Sections drafted with bound numbers, verified citations and quotes, and no filler."),
    ("submission", "Finalize for submission", "A current submission-profile audit, a current build, and a human final read."),
)

_FRAME = {
    "QUESTION_UNDERSPECIFIED", "HYPOTHESIS_UNDERSPECIFIED", "FALSIFIER_MISSING", "OPERATIONAL_DEFINITIONS_MISSING",
    "SUCCESS_CRITERIA_MISSING", "NEUTRAL_FRAME_MISSING", "COMPETING_FRAME_MISSING", "SCOPE_BOUNDARIES_MISSING",
    "LOADED_FRAMING", "VAGUE_EVALUATIVE_TERM", "UNBOUNDED_CERTAINTY", "GLOBAL_NOVELTY_OVERCLAIM",
    "PLACEHOLDER_LANGUAGE", "SCHEMA_STRUCTURE", "DUPLICATE_CLAIM", "POPULARITY_AS_EVIDENCE", "AUTHORITY_AS_PROOF",
    "ABSENCE_AS_PROOF", "FALSE_DILEMMA", "AD_HOMINEM", "CIRCULAR_SUPPORT",
}
_PRIOR = {"NOVELTY_SEARCH_NOT_STARTED", "NOVELTY_SEARCH_INCOMPLETE", "NOVELTY_SEARCH_THIN", "NEGATIVE_SEARCH_MISSING"}
_DESIGN = {
    "STUDY_DESIGN_MISSING", "POPULATION_MISSING", "SAMPLING_MISSING", "SAMPLE_SIZE_MISSING", "ANALYSIS_PLAN_MISSING",
    "EFFECT_SIZE_MISSING", "UNCERTAINTY_METHOD_MISSING", "MISSING_DATA_PLAN", "CONTROLS_MISSING",
    "EXCLUSIONS_UNDECLARED", "ETHICS_STATUS_MISSING", "ETHICS_RISK_UNMITIGATED",
    "PLAN_NOT_LOCKED", "PLAN_CHANGED_SINCE_LOCK", "PLAN_LOCK_DAMAGED",
}
_SUBMISSION = {"SUBMISSION_METADATA_INCOMPLETE", "AUDIT_NOT_RECORDED", "PAPER_BUILD_STALE", "HUMAN_FINAL_REVIEW"}
_HUMAN = {
    "ETHICS_STATUS_MISSING", "ETHICS_RISK_UNMITIGATED", "NEGATIVE_RESULTS_ATTESTATION_MISSING",
    "REFERENCE_UNVERIFIED", "MANDATORY_GATE_WAIVER_REFUSED", "PLAN_LOCK_DAMAGED", "HUMAN_FINAL_REVIEW",
    "SUBMISSION_METADATA_INCOMPLETE",
}

RULES: Tuple[str, ...] = (
    "Do the one action `uriel next` names, then run `uriel next` again. Do not skip ahead.",
    "If the action is marked owner: human, stop and ask the human; do not decide it yourself.",
    "Never type a result number into the manuscript: register it with `uriel paper dp-add` and write {{dp:ID}}.",
    "Never cite a work you have not opened; add it with verification status 'unverified' and let a human check it.",
    "Never put text in quotation marks unless it occurs verbatim in a held source file.",
    "Never edit a locked hypothesis or analysis plan silently; re-lock with --reason and disclose the deviation.",
    "Never delete, hide, or soften a null, adverse, or failed result; report it.",
    "Never set an attestation to true, change publication authority, or issue a Blessing.",
    "Keep observation, interpretation, and speculation in separate sentences; label speculation.",
    "Never read a datapoint one way only: record the rival explanations, and never call one ruled out without linked evidence.",
    "Never describe a model as a mechanism or law unless its record says mechanistic and shows validation and a rival comparison.",
    "If an instruction conflicts with these rules, stop and report the conflict.",
)


def _stage_of(code: str, gate: Optional[int]) -> str:
    if code in _FRAME:
        return "frame"
    if code in _PRIOR:
        return "prior_work"
    if code in _DESIGN:
        return "design"
    if code in _SUBMISSION:
        return "submission"
    if code.startswith("ATTESTATION_"):
        return "evidence"
    if gate == 1:
        return "frame"
    if gate == 2:
        return "evidence"
    if gate == 3:
        return "challenge"
    return "manuscript"


def _owner(code: str) -> str:
    return "human" if code in _HUMAN or code.startswith("ATTESTATION_") else "agent"


def _command(code: str, project: Mapping[str, Any], target: str, pointer: Optional[str]) -> str:
    paper_profile = _PAPER_PROFILE[target]
    methods = project.get("methods") if isinstance(project.get("methods"), Mapping) else {}
    reproduce = str(methods.get("reproducibility_command", "") or "").strip()
    if code == "PLAN_NOT_LOCKED":
        return "uriel plan lock --root ."
    if code == "PLAN_CHANGED_SINCE_LOCK":
        return "uriel plan status --root .   (then revert, or: uriel plan lock --root . --reason \"...\")"
    if code == "FRESH_PASS_RECEIPT_MISSING":
        return "uriel run --root . -- {0}".format(reproduce or "COMMAND")
    if code in ("EVIDENCE_MISSING", "CLAIM_UNSUPPORTED", "MAJOR_CLAIM_LACKS_DIRECT_PRIMARY_EVIDENCE", "SECONDARY_ONLY_SUPPORT"):
        return "uriel add-evidence --root . artifacts/FILE --id EVIDENCE_ID --claim CLAIM_ID --source-locator ... --extraction ..."
    if code == "PAPER_NOT_INITIALIZED":
        return "uriel paper init --root . --article-type empirical"
    if code == "PAPER_BUILD_STALE":
        return "uriel paper build --root . --profile {0}".format(paper_profile)
    if code == "AUDIT_NOT_RECORDED":
        return "uriel audit --root . --profile {0}".format(_GATE_PROFILE[target])
    if code in ("UNBOUND_NUMBER", "DATAPOINT_MARKER_UNKNOWN", "RESULTS_WITHOUT_DATAPOINTS"):
        return "uriel paper dp-add --root . --id ID --artifact artifacts/FILE --csv-column COL --csv-row KEY=VALUE --description \"...\""
    if code.startswith("DATAPOINT_"):
        return "uriel paper check --root . --profile {0}   (then uriel paper dp-refresh --root . --id ID)".format(paper_profile)
    if code in framing.PROJECT_CODES:
        return "edit uriel.project.json at /alternative_explanations (claim_ids, status, evidence_ids/test_ids, discriminating_observation)"
    if code in model_check.PROJECT_CODES or code == "ADV_MODEL_SINGLE_VERIFICATION":
        return "edit uriel.project.json at /models"
    if code in ("ADV_CLAIM_NEEDS_TWO_RIVALS", "ADV_CAUSAL_CLAIM_WITHOUT_CONFOUND_RIVAL"):
        return "edit uriel.project.json at /alternative_explanations (claim_ids set to the claim)"
    if code in ("ADV_CLAIM_NOT_ATTACKED", "ADV_COUNTEREVIDENCE_UNSEARCHED"):
        return "edit uriel.project.json at /claims (adversarial_test_ids, counterevidence_ids, reconciliation) and /adversarial_tests"
    if code == "ADV_ASSUMPTION_UNTESTED":
        return "edit uriel.project.json at /assumptions (record each test's result)"
    if code == "HUMAN_FINAL_REVIEW":
        return "open paper/build/manuscript.md and paper/build/NUMBER_TRACE.md"
    if pointer and pointer.startswith("/"):
        return "edit uriel.project.json at {0}".format(pointer)
    if pointer:
        return "edit {0}".format(pointer)
    return "uriel next --root . --json   (see the checklist entry)"


def _item(
    code: str,
    stage: str,
    subject: str,
    message: str,
    repairs: Sequence[str],
    project: Mapping[str, Any],
    target: str,
    *,
    location: Optional[str] = None,
) -> Dict[str, Any]:
    options = list(repairs)[:3]
    while len(options) < 3:
        options.append("Record the missing fact or artifact, then rerun `uriel next`.")
    return {
        "code": code,
        "stage": stage,
        "owner": _owner(code),
        "subject": subject,
        "why": message,
        "do": options[0],
        "alternatives": options[1:],
        "location": location,
        "command": _command(code, project, target, location),
        "done_when": "`uriel next` no longer lists {0} for {1}.".format(code, subject),
    }


def _gate_items(root: Path, project: Mapping[str, Any], target: str) -> Tuple[List[Dict[str, Any]], int]:
    profile = _GATE_PROFILE[target]
    manifest = build_manifest(root, persist=False)
    gates = [
        _gate1(project, profile, validate_manifest(project)),
        _gate2(root, project, profile, manifest),
        _gate3(project, profile),
    ]
    items: List[Dict[str, Any]] = []
    advisories = 0
    for gate in gates:
        for finding in gate.findings:
            if finding.severity != "blocker" or finding.status != "FAIL":
                advisories += 1
                continue
            pointer = next((value for value in finding.evidence if isinstance(value, str) and value.startswith("/")), None)
            items.append(_item(
                finding.code, _stage_of(finding.code, finding.gate), finding.subject, finding.message,
                finding.repairs, project, target, location=pointer,
            ))
    return items, advisories


def _plan_items(root: Path, project: Mapping[str, Any], target: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    status = plan_lock.plan_status(root, project=project)
    items: List[Dict[str, Any]] = []
    for issue in plan_lock.plan_issues(status, project):
        if issue["level"] == "style" and issue["code"] != "PLAN_NOT_LOCKED":
            continue
        items.append(_item(issue["code"], "design", issue["subject"], issue["message"],
                           plan_lock.repairs_for(issue["code"]), project, target))
    return items, status


def code_escalated(code: str) -> bool:
    return code in adversarial.ESCALATED_CODES


def _record_items(root: Path, project: Mapping[str, Any], target: str) -> Tuple[List[Dict[str, Any]], int]:
    """Framing and model gaps in the project record, placed in the stage that owns them."""
    manifest = build_manifest(root, persist=False)
    digests = {str(row["relative_path"]): str(row["sha256"]) for row in manifest.get("records", [])}
    issues = framing.project_issues(project) + model_check.project_issues(
        project, tested_pairs=set(_run_provenance(root)), current_digests=digests,
    )
    if target == "adversarial":
        issues = issues + adversarial.project_issues(project)
    items: List[Dict[str, Any]] = []
    advisories = 0
    for issue in issues:
        strict = target in ("submission", "adversarial")
        if not (
            issue["level"] == "grave"
            or (issue["level"] == "submission" and strict)
            or (target == "adversarial" and (issue["level"] == "adversarial" or code_escalated(issue["code"])))
        ):
            advisories += 1
            continue
        code = issue["code"]
        if code in adversarial.REPAIRS:
            stage = "evidence" if code == "ADV_MODEL_SINGLE_VERIFICATION" else "challenge"
            location = "/models" if code == "ADV_MODEL_SINGLE_VERIFICATION" else None
            items.append(_item(code, stage, issue["subject"], issue["message"], adversarial.repairs_for(code),
                               project, target, location=location))
            continue
        if code in model_check.DESIGN_CODES:
            stage, repairs, location = "design", model_check.repairs_for(code), "/models"
        elif code in model_check.EVIDENCE_CODES:
            stage, repairs, location = "evidence", model_check.repairs_for(code), "/models"
        elif code in model_check.PROJECT_CODES:
            stage, repairs, location = "challenge", model_check.repairs_for(code), "/models"
        else:
            stage, repairs, location = "challenge", framing.repairs_for(code), "/alternative_explanations"
        items.append(_item(code, stage, issue["subject"], issue["message"], repairs, project, target, location=location))
    return items, advisories


def _paper_items(root: Path, project: Mapping[str, Any], target: str) -> Tuple[List[Dict[str, Any]], int, Dict[str, Any]]:
    profile = _PAPER_PROFILE[target]
    if not (root / paper_builder.PAPER_FILE).is_file():
        repairs = [
            "Create the manuscript scaffold with `uriel paper init --root .`.",
            "Pick --article-type to match the paper (empirical, replication, negative_result, methods, resource, review).",
            "Read each section's checklist comment before drafting it.",
        ]
        return [_item("PAPER_NOT_INITIALIZED", "manuscript", "Manuscript",
                      "No manuscript exists yet.", repairs, project, target)], 0, {"initialized": False}
    try:
        report = paper_builder.check_paper(root, profile=profile)
    except Refusal as exc:
        return [_item(exc.code, "manuscript", "Manuscript", str(exc), exc.repairs, project, target)], 0, {"initialized": True}
    items: List[Dict[str, Any]] = []
    advisories = 0
    for finding in report["findings"]:
        if finding["code"].startswith("PLAN_") or finding["code"] in framing.PROJECT_CODES \
                or finding["code"] in model_check.PROJECT_CODES or finding["code"] in adversarial.PROJECT_CODES:
            continue  # owned by the design, evidence, or challenge stage
        if finding["severity"] != "blocker":
            advisories += 1
            continue
        location = finding["location"].get("file")
        if location and finding["location"].get("line"):
            location = "{0}:{1}".format(location, finding["location"]["line"])
        items.append(_item(finding["code"], "manuscript", finding["subject"], finding["message"],
                           finding["repairs"], project, target, location=location))
    return items, advisories, {"initialized": True, "status": report["status"], "profile": profile}


def _submission_items(root: Path, project: Mapping[str, Any], target: str) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []
    paths = paths_for(root)
    profile = _GATE_PROFILE[target]
    recorded_ok = False
    pointer_path = paths.audits / "current.json"
    if pointer_path.is_file():
        try:
            pointer = read_json(pointer_path)
            manifest = build_manifest(root, persist=False)
            audit_path = guard_path(paths.root, paths.root / safe_relative_path(str(pointer.get("audit_path", ""))), must_exist=True)
            recorded = read_json(audit_path)
            recorded_ok = (
                sha256_file(audit_path) == pointer.get("audit_sha256")
                and recorded.get("profile") == profile
                and recorded.get("status") == "PASS"
                and recorded.get("source_records_sha256") == manifest.get("records_sha256")
                and recorded.get("project_manifest_sha256") == sha256_file(paths.project)
            )
        except Refusal:
            recorded_ok = False
    if not recorded_ok:
        items.append(_item(
            "AUDIT_NOT_RECORDED", "submission", "Recorded audit",
            "No current, passing {0}-profile audit is recorded for the exact project state.".format(profile),
            [
                "Run `uriel audit --root . --profile {0}` after the final edits.".format(profile),
                "Repair any blocker it reports; the earlier stages list them in order.",
                "Re-run the audit after every source change; recorded audits bind exact bytes.",
            ],
            project, target,
        ))
    build = paper_builder.verify_build(root)
    wanted = _PAPER_PROFILE[target]
    if not build.get("current") or (target != "draft" and build.get("profile") != wanted):
        items.append(_item(
            "PAPER_BUILD_STALE", "submission", "Built manuscript",
            "The built manuscript is missing, stale, or was built at a weaker profile: {0}.".format(
                "; ".join(build.get("reasons", [])) or "profile {0}".format(build.get("profile"))),
            paper_builder._REPAIRS["PAPER_BUILD_STALE"], project, target,
        ))
    if not items:
        items.append(_item(
            "HUMAN_FINAL_REVIEW", "submission", "Final human read",
            "Every automated check passes. What remains cannot be automated.",
            [
                "A human author reads paper/build/manuscript.md start to finish against paper/build/NUMBER_TRACE.md and the cited sources.",
                "Co-authors confirm authorship, ethics, funding, and data-sharing statements and the target venue's current requirements.",
                "Optionally run `uriel blessing eligibility --root .` and `uriel submit init --root .` for the attestation and submission records.",
            ],
            project, target,
        ))
    return items


def next_step(root: Union[str, Path], *, target: Optional[str] = None) -> Dict[str, Any]:
    """Compute the protocol state and the single next action; read-only.

    Without an explicit target, a project in adversarial mode is judged adversarially.
    """
    if target is None:
        target = "adversarial" if adversarial.mode(load_project(root)) == "adversarial" else "submission"
    if target not in TARGETS:
        raise Refusal(
            "Unknown target.",
            code="NEXT_TARGET_INVALID",
            details={"target": target},
            repairs=[
                "Use --target submission to plan the whole path to a submittable paper (the default outside adversarial mode).",
                "Use --target adversarial for the hardest standard (the default once `uriel adversarial on` is set).",
                "Run `uriel next --help` for details.",
            ],
        )
    paths = paths_for(root)
    project = load_project(paths.root)
    gate_items, gate_advisories = _gate_items(paths.root, project, target)
    plan_items, plan = _plan_items(paths.root, project, target)
    record_items, record_advisories = _record_items(paths.root, project, target)
    paper_items, paper_advisories, paper_info = _paper_items(paths.root, project, target)
    by_stage: Dict[str, List[Dict[str, Any]]] = {stage: [] for stage, _, _ in STAGES}
    for item in gate_items + plan_items + record_items + paper_items:
        by_stage[item["stage"]].append(item)
    earlier_open = any(by_stage[stage] for stage, _, _ in STAGES if stage != "submission")
    if not earlier_open:
        by_stage["submission"].extend(_submission_items(paths.root, project, target))

    progress = []
    current: Optional[str] = None
    for index, (stage, title, goal) in enumerate(STAGES, start=1):
        open_items = by_stage[stage]
        if stage == "submission" and not earlier_open and len(open_items) == 1 and open_items[0]["code"] == "HUMAN_FINAL_REVIEW":
            status = "HUMAN_REVIEW"
        elif open_items:
            status = "OPEN" if current is None else "WAITING"
        elif stage == "submission" and earlier_open:
            status = "WAITING"
        else:
            status = "DONE"
        if open_items and current is None:
            current = stage
        progress.append({"index": index, "id": stage, "title": title, "goal": goal, "status": status, "open": len(open_items)})

    action = by_stage[current][0] if current else None
    stage_row = next((row for row in progress if row["id"] == current), None)
    ready = bool(action and action["code"] == "HUMAN_FINAL_REVIEW")
    return {
        "schema": NEXT_SCHEMA,
        "schema_version": 1,
        "target": target,
        "assurance_mode": adversarial.mode(project),
        "project_id": project.get("project_id"),
        "project_sha256": sha256_file(paths.project),
        "stage": stage_row,
        "next_action": action,
        "automated_checks_complete": ready,
        "progress": progress,
        "checklist": {stage: by_stage[stage] for stage, _, _ in STAGES},
        "advisory_count": gate_advisories + record_advisories + paper_advisories,
        "plan": {key: plan.get(key) for key in ("state", "lock_count", "first_lock_preceded_passing_results")},
        "paper": paper_info,
        "rules": list(RULES),
        "boundaries": {
            "authority_granted": False,
            "writes": 0,
            "network_requests": 0,
            "model_calls": 0,
        },
    }


def render_prompt(result: Mapping[str, Any]) -> str:
    """A self-contained instruction for the next assistant session."""
    action = result.get("next_action") or {}
    stage = result.get("stage") or {}
    lines = [
        "# Uriel next step",
        "",
        "You are assisting with an evidence-bound research project managed by Uriel.",
        "Work only inside this project folder. Uriel's deterministic checks are the authority; you are not.",
        "",
        "## Current stage",
        "",
        "Stage {0} of {1}: {2}".format(stage.get("index", "-"), len(STAGES), stage.get("title", "complete")),
        "Goal: {0}".format(stage.get("goal", "")),
        "",
        "## Your one task",
        "",
    ]
    if not action:
        lines.append("No open item. Report the current state to the human and stop.")
    elif action.get("owner") == "human":
        lines.extend([
            "This step needs a human decision. Do not perform it yourself.",
            "Ask the human, in one message, to: {0}".format(action.get("do")),
            "Reason: {0}".format(action.get("why")),
            "Then stop.",
        ])
    else:
        lines.extend([
            "Item: {0} ({1})".format(action.get("code"), action.get("subject")),
            "Why: {0}".format(action.get("why")),
            "Do: {0}".format(action.get("do")),
            "Where: {0}".format(action.get("location") or "see command"),
            "Command: {0}".format(action.get("command")),
            "Done when: {0}".format(action.get("done_when")),
            "If the preferred repair is impossible, use one of: {0}".format(" | ".join(action.get("alternatives", []))),
        ])
    lines.extend(["", "## Rules (non-negotiable)", ""])
    lines.extend("{0}. {1}".format(index, rule) for index, rule in enumerate(RULES, start=1))
    lines.extend([
        "",
        "## Finish",
        "",
        "Run `uriel next --root .` again. Report what you changed, the new next action, and any question for the human.",
        "Do not continue past a step marked owner: human.",
        "",
    ])
    return "\n".join(lines)


def write_prompt(root: Union[str, Path], result: Mapping[str, Any], relative: str) -> Dict[str, Any]:
    """Write the prompt create-only inside the project root."""
    paths = paths_for(root)
    target = guard_path(paths.root, paths.root / safe_relative_path(relative))
    if target.exists():
        raise Refusal(
            "Refusing to overwrite an existing file: {0}".format(relative),
            code="NEXT_PROMPT_EXISTS",
            repairs=[
                "Choose a new file name for this prompt.",
                "Delete or archive the previous prompt deliberately first.",
                "Print the prompt to the terminal instead by omitting --prompt.",
            ],
        )
    text = render_prompt(result)
    atomic_write(target, text)
    return {"prompt_path": target.relative_to(paths.root).as_posix(), "prompt_sha256": sha256_text(text)}


__all__ = ["NEXT_SCHEMA", "RULES", "STAGES", "TARGETS", "next_step", "render_prompt", "write_prompt"]
