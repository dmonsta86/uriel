"""Argparse command-line interface for Uriel (no runtime dependencies)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from . import __version__
from .adapters import run_opencode
from .audit import PROFILES, audit_project
from .blessing import issue_blessing, verify_blessing
from .broker import create_request
from .core import (
    IntegrityError,
    PROJECT_FILE_NAME,
    Refusal,
    add_evidence,
    append_ledger,
    atomic_write_json,
    build_index,
    build_manifest,
    doctor,
    guard_path,
    initialize_project,
    list_reminders,
    load_project,
    paths_for,
    pretty_json,
    project_status,
    read_json,
    run_workload,
    save_project,
    sha256_file,
    sha256_text,
    update_reminder,
    utc_now,
    verify_project,
    verify_source_manifest,
)
from .data_readiness import data_readiness_state, make_sort_spec, readiness_check, readiness_status
from .decisions import DECISION_CLASSES
from .intake import intake_idea
from .lens import lens_names, lens_prompt, write_lens
from .onboarding import (
    ENTRY_KINDS,
    consent_set,
    consent_status,
    inplace_dryrun,
    inplace_verify,
    preflight,
    review_workspace,
    safe_copy,
    start as start_workspace,
)
from .prompts import build_prompt
from .reviews import REVIEW_TASKS, import_review, list_reviews, review_template
from .schema import validate_project
from .seed import seed_project, write_seed_brief
from .submission import (
    archive_submission,
    build_response,
    import_decision,
    submit_guide,
    submit_init,
    submit_next_prompt,
    submit_plan,
    submission_status,
    submit_verify,
)
from .surfaces import burst_init, verify_burst
from .workbench import workbench_init, workbench_next, workbench_plan, workbench_status


class _Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise Refusal(
            "Command-line input error: {0}".format(message),
            code="CLI_USAGE",
            repairs=[
                "Run `uriel --help` or `uriel COMMAND --help` and copy the shown syntax.",
                "Place workload arguments after `--`, for example `uriel run -- python -m unittest`.",
                "Use `--json` before the command when machine-readable output is needed.",
            ],
        )


def _root_argument(parser: argparse.ArgumentParser, *, optional: bool = False) -> None:
    parser.add_argument(
        "--root",
        default="." if optional else ".",
        help="Uriel project root (default: current directory)",
    )


def parser() -> argparse.ArgumentParser:
    top = _Parser(prog="uriel", description="Offline-first research integrity harness and provenance ledger")
    top.add_argument("--json", action="store_true", dest="json_output", help="emit one machine-readable JSON object")
    top.add_argument("--version", action="version", version="%(prog)s {0}".format(__version__))
    commands = top.add_subparsers(dest="command", required=True)

    init = commands.add_parser("init", help="initialize a confined Uriel project")
    init.add_argument("path", nargs="?", default=".")
    init.add_argument("--title", default="Untitled research question")
    init.add_argument("--question", default="")
    init.add_argument("--privacy", choices=("public", "internal", "confidential", "restricted"), default="public")
    init.add_argument("--force", action="store_true")

    start_cmd = commands.add_parser("start", help="scaffold a Uriel workspace: entry files, consent, and mode")
    _root_argument(start_cmd)
    start_cmd.add_argument("--kind", choices=ENTRY_KINDS, default=None,
                           help="explicit entry kind; never inferred from file contents")
    start_cmd.add_argument("--current-task", default="")
    start_cmd.add_argument("--title", default="")
    start_cmd.add_argument("--question", default="")
    start_cmd.add_argument("--privacy", choices=("public", "internal", "confidential", "restricted"), default="public")
    start_cmd.add_argument("--force", action="store_true")

    preflight_cmd = commands.add_parser("preflight", help="metadata-only preflight of a workspace root")
    _root_argument(preflight_cmd)

    consent = commands.add_parser("consent", help="create or inspect immutable workspace consent records")
    consent_actions = consent.add_subparsers(dest="consent_action", required=True)
    consent_status_cmd = consent_actions.add_parser("status", help="show the latest consent record")
    _root_argument(consent_status_cmd)
    consent_set_cmd = consent_actions.add_parser("set", help="create a new consent record (records are immutable)")
    _root_argument(consent_set_cmd)
    consent_set_cmd.add_argument("--mode", required=True, choices=("metadata_only", "read_only", "safe_copy", "in_place"))
    consent_set_cmd.add_argument("--confirm", choices=("explicit_user", "installer_default_read_only"), default="explicit_user")
    consent_set_cmd.add_argument("--cloud-sync-acknowledged", action="store_true")
    consent_set_cmd.add_argument("--sensitive-acknowledged", action="store_true")
    consent_set_cmd.add_argument("--network", action="store_true")
    consent_set_cmd.add_argument("--external-dir", action="store_true")
    consent_set_cmd.add_argument("--copy", action="store_true")

    workspace = commands.add_parser("workspace", help="workspace modes: review, safe copy, in-place")
    workspace_actions = workspace.add_subparsers(dest="workspace_action", required=True)
    ws_review = workspace_actions.add_parser("review", help="create a read-only review workspace outside the source root")
    _root_argument(ws_review)
    ws_review.add_argument("--output", default="")
    ws_copy = workspace_actions.add_parser("copy", help="build a verified safe working copy")
    _root_argument(ws_copy)
    ws_copy.add_argument("--destination", default="")
    ws_inplace = workspace_actions.add_parser("inplace-dryrun", help="record an in-place plan without any source write")
    _root_argument(ws_inplace)
    ws_inplace_verify = workspace_actions.add_parser("inplace-verify", help="verify the source generation is unchanged")
    _root_argument(ws_inplace_verify)

    readiness = commands.add_parser("readiness", help="Data Readiness Gate 0: SortSpec, checks, and receipts")
    readiness_actions = readiness.add_subparsers(dest="readiness_action", required=True)
    rd_init = readiness_actions.add_parser("init-sort-spec", help="generate a versioned SortSpec (identity must be declared)")
    _root_argument(rd_init)
    rd_init.add_argument("--dataset", required=True)
    rd_init.add_argument("--keys", nargs="+", default=[])
    rd_init.add_argument("--tie-break", nargs="+", default=[])
    rd_init.add_argument("--nulls", choices=("nulls_first", "nulls_last", "nulls_error"), default="nulls_last")
    rd_init.add_argument("--dup-policy", choices=("block", "exact", "keep_first"), default="block")
    rd_init.add_argument("--analysis-plan", default="")
    rd_check = readiness_actions.add_parser("check", help="run the Gate 0 check matrix and write a receipt")
    _root_argument(rd_check)
    rd_check.add_argument("--sort-spec", default="")
    rd_check.add_argument("--dataset", default="")
    rd_check.add_argument("--analysis-plan", default="")
    rd_status = readiness_actions.add_parser("status", help="latest receipt and staleness against current data")
    _root_argument(rd_status)
    rd_status.add_argument("--dataset", default="")

    intake = commands.add_parser("intake", help="preserve a rough question and create or update a project")
    intake.add_argument("question")
    _root_argument(intake)
    intake.add_argument("--title", default="")
    intake.add_argument("--privacy", choices=("public", "internal", "confidential", "restricted"), default="public")

    lens = commands.add_parser("lens", help="print a verified zero-install advisory Lens/Seed prompt")
    lens.add_argument("--which", choices=("compact", "full", "seed", "skill", "example"), default="compact")
    lens.add_argument("--output", default="", help="write the prompt to a file instead of stdout")

    seed = commands.add_parser("seed", help="turn a rough question into a researchable project")
    seed.add_argument("question")
    _root_argument(seed)
    seed.add_argument("--title", default="")
    seed.add_argument("--privacy", choices=("public", "internal", "confidential", "restricted"), default="public")
    seed.add_argument("--output", default="", help="write the human-readable seed brief to a file")

    workbench = commands.add_parser("workbench", help="maintain research plans, claims, controls, and decisions")
    workbench_actions = workbench.add_subparsers(dest="workbench_action", required=True)
    wb_init = workbench_actions.add_parser("init", help="create the first workbench generation")
    _root_argument(wb_init)
    wb_init.add_argument("--question", required=True)
    wb_plan = workbench_actions.add_parser("plan", help="apply a validated plan file as a new generation")
    _root_argument(wb_plan)
    wb_plan.add_argument("--file", required=True, dest="plan_file", help="path to a uriel.workbench_plan.v1 JSON file")
    wb_status = workbench_actions.add_parser("status", help="summarize the current generation and its gaps")
    _root_argument(wb_status)
    wb_next = workbench_actions.add_parser("next", help="show the exact next action and write a durable next prompt")
    _root_argument(wb_next)
    wb_next.add_argument("--output", default="", help="path to write NEXT_PROMPT.txt")

    burst = commands.add_parser("burst", help="create or verify bounded resumable free-model packets")
    burst_actions = burst.add_subparsers(dest="burst_action", required=True)
    burst_init_cmd = burst_actions.add_parser("init", help="create the next bounded burst packet")
    _root_argument(burst_init_cmd)
    burst_init_cmd.add_argument("--records", nargs="+", default=[], help="project-relative record files to include")
    burst_init_cmd.add_argument("--next-task", required=True)
    burst_init_cmd.add_argument("--budget-bytes", type=int, default=32000)
    burst_init_cmd.add_argument("--redact", action="store_true", help="expose metadata and hashes only")
    burst_verify_cmd = burst_actions.add_parser("verify", help="re-hash a burst packet against its manifest")
    burst_verify_cmd.add_argument("--packet", required=True, dest="packet_dir")

    validate = commands.add_parser("validate", help="validate uriel.project.json structure")
    _root_argument(validate)

    add_evidence_cmd = commands.add_parser("add-evidence", help="hash and register a project-local evidence artifact")
    _root_argument(add_evidence_cmd)
    add_evidence_cmd.add_argument("path", help="project-relative artifact path")
    add_evidence_cmd.add_argument("--id", required=True, dest="evidence_id")
    add_evidence_cmd.add_argument("--claim", action="append", default=[], dest="claim_ids", help="claim ID supported; repeat as needed")
    add_evidence_cmd.add_argument("--kind", default="artifact")
    add_evidence_cmd.add_argument("--description", default="")
    add_evidence_cmd.add_argument("--source-locator", default="")
    add_evidence_cmd.add_argument("--source-type", default="primary")
    add_evidence_cmd.add_argument("--directness", default="direct")
    add_evidence_cmd.add_argument("--extraction", default="")
    add_evidence_cmd.add_argument("--data-location", default="")
    add_evidence_cmd.add_argument("--interpretation", default="")
    add_evidence_cmd.add_argument("--limitations", default="")
    add_evidence_cmd.add_argument("--secondary", action="store_true", help="mark this evidence as non-primary")

    snapshot = commands.add_parser("snapshot", help="hash every confined project source file")
    _root_argument(snapshot)
    snapshot.add_argument("--index", action="store_true", help="also build the SQLite source index")


    run = commands.add_parser("run", help="run an explicit command without a shell and preserve a receipt")
    _root_argument(run)
    run.add_argument("--timeout", type=int, default=600)
    run.add_argument("--id", dest="workload_id")
    run.add_argument("workload", nargs=argparse.REMAINDER, help="command after --")

    audit = commands.add_parser("audit", help="evaluate all Three Gates")
    _root_argument(audit)
    audit.add_argument("--profile", choices=PROFILES, default="standard")

    blessing = commands.add_parser("blessing", help="issue a Blessing after a submission-profile PASS")
    _root_argument(blessing)

    verify_b = commands.add_parser("verify-blessing", help="verify a Blessing package, optionally against a live project")
    verify_b.add_argument("package")
    verify_b.add_argument("--root", help="optional live project root")

    verify = commands.add_parser("verify", help="verify source, ledger, and execution receipts")
    _root_argument(verify)

    status = commands.add_parser("status", help="show project and current-audit status")
    _root_argument(status)

    prompt = commands.add_parser("prompt", help="create an optional AI/human review prompt")
    _root_argument(prompt)
    prompt.add_argument("task", choices=REVIEW_TASKS)
    prompt.add_argument("--provider", choices=("generic", "local", "opencode", "chatgpt-web", "deepseek-web"), default="generic")
    prompt.add_argument("--acknowledge-external", action="store_true")
    prompt.add_argument("--include-sensitive", action="store_true", help="include non-public project text; prefer a verified local model")
    prompt.add_argument("--show", action="store_true", help="print the full prompt")

    assist = commands.add_parser("assist", help="run one bounded review through OpenCode")
    _root_argument(assist)
    assist.add_argument("task", choices=REVIEW_TASKS)
    assist.add_argument("--model", required=True, help="OpenCode provider/model identifier")
    assist.add_argument("--timeout", type=int, default=900)
    assist.add_argument("--acknowledge-external", action="store_true")

    template = commands.add_parser("review-template", help="write a hash-bound review JSON template")
    _root_argument(template)
    template.add_argument("task", choices=REVIEW_TASKS)
    template.add_argument("--output", default=".uriel/review-inbox/review.json")

    review_import = commands.add_parser("review-import", help="validate and import a completed review JSON")
    _root_argument(review_import)
    review_import.add_argument("path")

    reviews = commands.add_parser("reviews", help="list imported optional reviews")
    _root_argument(reviews)

    capability = commands.add_parser("capability", help="record a default-deny request for optional external help")
    _root_argument(capability)
    capability.add_argument("name", help="bounded capability, for example literature-search")
    capability.add_argument("purpose", help="why this capability is needed")
    capability.add_argument("--exposure", choices=("none", "hashes_only", "redacted_metadata", "sanitized_content"), default="redacted_metadata")

    reminders = commands.add_parser("reminders", help="list, resolve, or reopen durable blockers")
    _root_argument(reminders)
    reminders.add_argument("action", choices=("list", "resolve", "reopen"), nargs="?", default="list")
    reminders.add_argument("reminder_id", nargs="?")
    reminders.add_argument("--note", default="")
    reminders.add_argument("--all", action="store_true", dest="include_resolved")

    doctor_cmd = commands.add_parser("doctor", help="check local runtime health without using the network")
    _root_argument(doctor_cmd)

    submit = commands.add_parser("submit", help="guide a submission through decisions, revision, and production")
    submit_commands = submit.add_subparsers(dest="submit_action", required=True)

    submit_init = submit_commands.add_parser("init", help="initialize the submission lifecycle store")
    _root_argument(submit_init)
    submit_init.add_argument("--dry-run", action="store_true")

    submit_import = submit_commands.add_parser("import-decision", help="import an editor email, decision letter, or reviewer comments")
    _root_argument(submit_import)
    submit_import.add_argument("--text", help="decision source text (or use --source)")
    submit_import.add_argument("--source", help="path to the decision artifact (hashed as the source)")
    submit_import.add_argument("--venue", default=None)
    submit_import.add_argument("--manuscript-id", default=None)
    submit_import.add_argument("--deadline", default=None)
    submit_import.add_argument("--decision-class", choices=DECISION_CLASSES, default=None, help="confirm the decision class")
    submit_import.add_argument("--dry-run", action="store_true")

    submit_plan = submit_commands.add_parser("plan", help="build the revision, acceptance, or rejection plan")
    _root_argument(submit_plan)
    submit_plan.add_argument("--dry-run", action="store_true")

    submit_response = submit_commands.add_parser("build-response", help="create an immutable response packet generation")
    _root_argument(submit_response)
    submit_response.add_argument("--fields", default=None, help="path to a submission-fields JSON (array of uriel.submission_field.v1)")
    submit_response.add_argument("--dry-run", action="store_true")

    submit_guide = submit_commands.add_parser("guide", help="render a field-by-field form walkthrough")
    _root_argument(submit_guide)
    submit_guide.add_argument("--fields", default=None, help="path to a submission-fields JSON")
    submit_guide.add_argument("--dry-run", action="store_true")

    submit_verify = submit_commands.add_parser("verify", help="verify decisions, authority, and the current packet")
    _root_argument(submit_verify)

    submit_archive = submit_commands.add_parser("archive", help="create a deterministic ZIP archive of the current packet")
    _root_argument(submit_archive)
    submit_archive.add_argument("--dry-run", action="store_true")

    submit_status = submit_commands.add_parser("status", help="show the submission state summary")
    _root_argument(submit_status)

    submit_prompt = submit_commands.add_parser("next-prompt", help="produce the exact next-prompt file for the next AI session")
    _root_argument(submit_prompt)
    submit_prompt.add_argument("--output", default=None, help="write the next prompt to this project-relative path")
    submit_prompt.add_argument("--dry-run", action="store_true")
    return top


def _envelope(status: str, command: str, result: Optional[Any] = None, error: Optional[Any] = None) -> Dict[str, Any]:
    value: Dict[str, Any] = {
        "schema": "uriel.cli_result.v1",
        "status": status,
        "command": command,
        "engine_version": __version__,
    }
    if result is not None:
        value["result"] = result
    if error is not None:
        value["error"] = error
    return value


def _print_human(command: str, result: Any, args: Optional[argparse.Namespace] = None) -> None:
    if command == "audit" and isinstance(result, Mapping):
        print("Uriel audit: {0} ({1})".format(result.get("status"), result.get("profile")))
        print("Audit ID: {0}".format(result.get("audit_id")))
        for gate in result.get("gates", []):
            if not isinstance(gate, Mapping):
                continue
            blockers = sum(
                1
                for finding in gate.get("findings", [])
                if isinstance(finding, Mapping) and finding.get("severity") == "blocker" and finding.get("status") == "FAIL"
            )
            warnings = sum(
                1
                for finding in gate.get("findings", [])
                if isinstance(finding, Mapping) and finding.get("severity") == "warning"
            )
            print("  Gate {0} {1}: {2} · {3} blocker(s), {4} warning(s)".format(
                gate.get("gate"), gate.get("name"), gate.get("status"), blockers, warnings
            ))
        if result.get("status") != "PASS":
            print("Repair record: .uriel/REMINDERS.md")
        else:
            print("The declared state passed this profile. Only the submission profile can earn a Blessing.")
        return
    if command == "blessing" and isinstance(result, Mapping):
        print("Blessing verified: {0}".format(result.get("verified")))
        print("Blessing ID: {0}".format(result.get("blessing_id")))
        print("Package: {0}".format(result.get("package")))
        print("Certificate: {0}".format(result.get("certificate_svg")))
        return
    if command == "seed" and isinstance(result, Mapping):
        print("Uriel Seed record: {0}".format(result.get("seed_id")))
        print("Status: {0}".format(result.get("status")))
        print("Clarification batch: {0} question(s) — answer only the ones that change the design".format(
            len(result.get("clarification_questions", []))
        ))
        if result.get("brief"):
            print("Brief saved to: {0} (SHA-256 {1})".format(result["brief"].get("output"), result["brief"].get("sha256")))
        print("Next: fill the minimal-design scaffolds, then `uriel audit --profile exploratory`.")
        return
    if command == "workbench" and isinstance(result, Mapping):
        if args.workbench_action == "init":
            print("Workbench created: {0}".format(result.get("workbench_id")))
            print("Generation: {0}".format(result.get("generation_id")))
            print("Next: `uriel workbench plan --file plan.json` to add claims and design.")
            return
        if args.workbench_action == "plan":
            print("Workbench updated: {0}".format(result.get("workbench_id")))
            print("New generation: {0}".format(result.get("generation_id")))
            return
        if args.workbench_action == "status":
            if not result.get("exists"):
                print("No workbench yet. " + str(result.get("next_action", "")))
                return
            print("Workbench {0} · generation {1} · status {2}".format(
                result.get("workbench_id"), result.get("generation_id"), result.get("status")
            ))
            counts = result.get("item_counts", {})
            if counts:
                print("Items: " + ", ".join("{0}={1}".format(key, value) for key, value in sorted(counts.items())))
            else:
                print("Items: none yet — label the material first.")
            print("Rival explanations: {0} · Pivots: {1}".format(
                result.get("rival_explanation_count"), ", ".join(result.get("pivots", [])) or "none"
            ))
            gaps = result.get("design_gaps", [])
            if gaps:
                print("Design gaps: {0}".format(", ".join(gaps)))
            else:
                print("Design: complete.")
            return
        if args.workbench_action == "next":
            if not result.get("exists"):
                print("No workbench yet. " + str(result.get("next_action", "")))
                return
            print("Next action: {0}".format(result.get("next_action")))
            if result.get("next_prompt_path"):
                print("Next prompt: {0} (SHA-256 {1})".format(result.get("next_prompt_path"), result.get("next_prompt_sha256")))
            return
    if command == "burst" and isinstance(result, Mapping):
        if args.burst_action == "init":
            print("Burst packet: {0}".format(result.get("packet")))
            print("Records selected: {0} · bytes: {1} · redacted: {2}".format(
                result.get("selected_records"), result.get("bytes"), result.get("redacted")
            ))
            print("Next prompt written; packet carries no authority.")
            return
        if args.burst_action == "verify":
            print("Burst verify: {0} files checked".format(result.get("checked")))
            if result.get("verified"):
                print("PASS — all hashes match.")
            else:
                print("FAIL — missing: {0} · mismatched: {1} · unknown: {2}".format(
                    result.get("missing"), result.get("mismatched"), result.get("unknown_files")
                ))
            return
    if command == "lens" and isinstance(result, Mapping):
        print("Uriel Lens advisory prompt: {0}".format(result.get("asset")))
        print("Advisory only; cannot issue a Blessing.")
        if result.get("output"):
            print("Saved to: {0}".format(result.get("output")))
            print("SHA-256: {0}".format(result.get("sha256")))
        else:
            print()
            print(result.get("text", ""))
        return
    if command == "prompt" and isinstance(result, Mapping):
        print("Prompt saved: {0}".format(result.get("prompt_path")))
        print("Prompt SHA-256: {0}".format(result.get("prompt_sha256")))
        if result.get("show"):
            print()
            print(result.get("prompt", ""))
        return
    if command == "start" and isinstance(result, Mapping):
        print("Workspace: {0} · {1} · mode {2}".format(
            result.get("workspace_id"), result.get("entry_kind"), result.get("mode")))
        print("Consent record: {0}".format(result.get("consent_sha256")))
        print("Files written: {0}".format(", ".join(result.get("files_written", []))))
        print("Next: {0}".format(result.get("next_step")))
        return
    if command == "preflight" and isinstance(result, Mapping):
        print("Preflight: {0} files, {1} bytes · root hash {2}".format(
            result.get("file_count"), result.get("byte_count"), result.get("root_hash")))
        print("VCS: {0} · Uriel state: {1} · links: {2}".format(
            ", ".join(result.get("detected_vcs", [])) or "none",
            result.get("detected_uriel_state"), len(result.get("link_paths", []))))
        print("Cloud-sync indicators: {0} · sensitive-name indications: {1}".format(
            ", ".join(result.get("cloud_sync_indicators", [])) or "none",
            len(result.get("sensitive_file_indications", []))))
        return
    if command == "consent" and isinstance(result, Mapping):
        if args.consent_action == "status":
            if not result.get("exists"):
                print("No consent record yet. Run `uriel consent set --mode read_only`.")
                return
            latest = result.get("latest", {})
            print("Consent: {0} records · latest mode {1} · record {2}".format(
                result.get("records"), latest.get("mode"), latest.get("record_sha256")))
            permissions = latest.get("permissions", {})
            print("Permissions: " + ", ".join("{0}={1}".format(key, value) for key, value in sorted(permissions.items())))
            return
        print("Consent record: {0} · mode {1}{2}".format(
            result.get("record_sha256"), result.get("mode"),
            "" if result.get("created") else " (unchanged)"))
        return
    if command == "workspace" and isinstance(result, Mapping):
        if args.workspace_action == "review":
            print("Review workspace: {0}".format(result.get("review_workspace")))
            print("Files: {0}".format(", ".join(result.get("files", []))))
            return
        if args.workspace_action == "copy":
            print("Safe copy: {0} · files copied {1}".format(
                result.get("destination"), result.get("files_copied")))
            print("Original generation unchanged: {0}".format(result.get("same_original_generation")))
            print("Copy manifest: {0}".format(result.get("copy_manifest_sha256")))
            return
        if args.workspace_action == "inplace-dryrun":
            print("In-place dry run recorded: {0}".format(result.get("path")))
            print(result.get("note"))
            return
        if args.workspace_action == "inplace-verify":
            print("In-place verify: unchanged = {0} · generation {1}".format(
                result.get("unchanged"), result.get("source_generation")))
            return
    if command == "readiness" and isinstance(result, Mapping):
        if args.readiness_action == "init-sort-spec":
            print("SortSpec: {0} · rows seen: {1}".format(
                result.get("sort_spec_sha256"), result.get("row_count")))
            print("Record identity: {0} · duplicate policy: {1}".format(
                ", ".join(result["sort_spec"].get("primary_keys", [])),
                result["sort_spec"].get("duplicate_policy")))
            return
        if args.readiness_action == "check":
            receipt = result.get("receipt", {})
            print("Data Readiness: {0} · receipt {1}".format(
                receipt.get("decision"), result.get("receipt_sha256")))
            failed = [check["check"] for check in result.get("checks", []) if check["status"] == "FAIL"]
            print("Checks: {0} executed · {1} failed".format(
                receipt.get("executed_check_count"), receipt.get("failed_check_count")))
            if failed:
                print("Failed: {0}".format(", ".join(failed)))
            if result.get("embargo_sentence"):
                print(result["embargo_sentence"])
            return
        if args.readiness_action == "status":
            if not result.get("exists"):
                print("No receipt yet. " + str(result.get("embargo_sentence")))
                return
            print("Data Readiness: {0} · receipt {1}".format(
                result.get("decision"), result.get("receipt_sha256")))
            if result.get("embargo_sentence"):
                print(result["embargo_sentence"])
            return
    if command == "reminders" and isinstance(result, list):
        if not result:
            print("No matching reminders.")
            return
        for row in result:
            finding = row.get("finding", {}) if isinstance(row, Mapping) else {}
            print("{0} [{1}] Gate {2} · {3}".format(
                row.get("reminder_id"), str(row.get("status")).upper(), finding.get("gate"), finding.get("subject") or finding.get("code")
            ))
            print("  " + str(finding.get("message", "")))
        return
    print(pretty_json(result).rstrip())


def _intake(args: argparse.Namespace) -> Dict[str, Any]:
    seed = intake_idea(
        args.root,
        args.question,
        title=args.title,
        privacy=args.privacy,
    )
    report = audit_project(args.root, profile="exploratory")
    return {
        "intake": seed,
        "project": str(paths_for(args.root).root),
        "audit": report.as_dict(),
        "message": "The question was preserved exactly. Findings describe what the record needs; they do not dismiss the idea or its author.",
    }


def dispatch(args: argparse.Namespace) -> Any:
    command = args.command
    if command == "init":
        return initialize_project(args.path, title=args.title, question=args.question, privacy=args.privacy, force=args.force)
    if command == "intake":
        return _intake(args)
    if command == "lens":
        if args.output:
            return write_lens(Path("."), args.which, Path(args.output))
        return {
            "asset": args.which,
            "advisory_only": True,
            "text": lens_prompt(args.which),
            "available": lens_names(),
        }
    if command == "seed":
        value = seed_project(
            args.root,
            args.question,
            title=args.title,
            privacy=args.privacy,
        )
        if args.output:
            value["brief"] = write_seed_brief(args.root, Path(args.output))
        return value
    if command == "workbench":
        if args.workbench_action == "init":
            return workbench_init(args.root, args.question)
        if args.workbench_action == "plan":
            plan_target = guard_path(args.root, args.plan_file, must_exist=True)
            try:
                plan_value = json.loads(plan_target.read_text(encoding="utf-8"))
            except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise Refusal(
                    "Could not parse workbench plan file: {0}".format(exc),
                    code="WORKBENCH_PLAN_UNREADABLE",
                ) from exc
            if not isinstance(plan_value, Mapping):
                raise Refusal("Workbench plan file must contain a JSON object.", code="WORKBENCH_PLAN_UNREADABLE")
            return workbench_plan(args.root, plan_value)
        if args.workbench_action == "status":
            return workbench_status(args.root)
        if args.workbench_action == "next":
            return workbench_next(args.root, output=args.output or None)
    if command == "burst":
        if args.burst_action == "init":
            return burst_init(
                args.root,
                args.records,
                next_task=args.next_task,
                budget_bytes=args.budget_bytes,
                redact=args.redact,
            )
        if args.burst_action == "verify":
            return verify_burst(args.packet_dir)
    if command == "start":
        return start_workspace(
            args.root,
            args.kind,
            current_task=args.current_task,
            title=args.title,
            question=args.question,
            privacy=args.privacy,
            force=args.force,
        )
    if command == "preflight":
        return preflight(args.root)
    if command == "consent":
        if args.consent_action == "status":
            return consent_status(args.root)
        return consent_set(
            args.root,
            args.mode,
            confirmation=args.confirm,
            cloud_sync_acknowledged=args.cloud_sync_acknowledged,
            sensitive_data_acknowledged=args.sensitive_acknowledged,
            network=args.network,
            external_directory=args.external_dir,
            copy=args.copy or None,
        )
    if command == "workspace":
        if args.workspace_action == "review":
            return review_workspace(args.root, output=args.output or None)
        if args.workspace_action == "copy":
            return safe_copy(args.root, destination=args.destination or None)
        if args.workspace_action == "inplace-dryrun":
            return inplace_dryrun(args.root)
        if args.workspace_action == "inplace-verify":
            return inplace_verify(args.root)
    if command == "readiness":
        if args.readiness_action == "init-sort-spec":
            return make_sort_spec(
                args.root,
                args.dataset,
                keys=args.keys,
                tie_break=args.tie_break,
                nulls=args.nulls,
                duplicate_policy=args.dup_policy,
                analysis_plan=args.analysis_plan or None,
            )
        if args.readiness_action == "check":
            return readiness_check(
                args.root,
                args.sort_spec or None,
                dataset=args.dataset or None,
                analysis_plan=args.analysis_plan or None,
            )
        if args.readiness_action == "status":
            return readiness_status(args.root, dataset=args.dataset or None)
    if command == "validate":
        return validate_project(args.root)
    if command == "add-evidence":
        return add_evidence(
            args.root,
            args.path,
            evidence_id=args.evidence_id,
            claim_ids=args.claim_ids,
            kind=args.kind,
            description=args.description,
            source_locator=args.source_locator,
            source_type=args.source_type,
            directness=args.directness,
            extraction=args.extraction,
            data_location=args.data_location,
            interpretation=args.interpretation,
            limitations=args.limitations,
            primary=not args.secondary,
        )
    if command == "snapshot":
        manifest = build_manifest(args.root, persist=True)
        verification = verify_source_manifest(args.root, manifest)
        result: Dict[str, Any] = {"manifest": manifest, "verification": verification}
        if args.index:
            result["index"] = build_index(args.root, manifest)
        return result
    if command == "run":
        parts = list(args.workload)
        if parts and parts[0] == "--":
            parts = parts[1:]
        return run_workload(args.root, parts, timeout=args.timeout, workload_id=args.workload_id)
    if command == "audit":
        return audit_project(args.root, profile=args.profile).as_dict()
    if command == "blessing":
        return issue_blessing(args.root)
    if command == "verify-blessing":
        return verify_blessing(args.package, project_root=args.root)
    if command == "verify":
        return verify_project(args.root)
    if command == "status":
        return project_status(args.root)
    if command == "prompt":
        result = build_prompt(
            args.root,
            task=args.task,
            provider=args.provider,
            acknowledge_external=args.acknowledge_external,
            include_sensitive=args.include_sensitive,
        )
        result["show"] = bool(args.show)
        if not args.show:
            result = {key: value for key, value in result.items() if key != "prompt"}
        return result
    if command == "assist":
        return run_opencode(
            args.root,
            task=args.task,
            model=args.model,
            timeout=args.timeout,
            acknowledge_external=args.acknowledge_external,
        )
    if command == "review-template":
        paths = paths_for(args.root)
        source = build_manifest(paths.root, persist=True)
        value = review_template(
            task=args.task,
            source_manifest_sha256=str(source["manifest_sha256"]),
            project_manifest_sha256=sha256_file(paths.project),
        )
        destination = paths.root / args.output
        destination.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_json(destination, value)
        return {"output": destination.relative_to(paths.root).as_posix(), "template": value}
    if command == "review-import":
        return import_review(args.root, args.path)
    if command == "reviews":
        return list_reviews(args.root)
    if command == "capability":
        return create_request(args.root, args.name, args.purpose, exposure=args.exposure)
    if command == "reminders":
        if args.action == "list":
            return list_reminders(args.root, include_resolved=args.include_resolved)
        if not args.reminder_id:
            raise Refusal("A reminder id is required for resolve or reopen.", code="REMINDER_ID_REQUIRED")
        status = "resolved" if args.action == "resolve" else "open"
        return update_reminder(args.root, args.reminder_id, status=status, note=args.note)
    if command == "doctor":
        return doctor(args.root)
    if command == "submit":
        if args.submit_action == "init":
            return submit_init(args.root, dry_run=args.dry_run)
        if args.submit_action == "import-decision":
            if args.source:
                source_path = Path(args.source)
                source_text = source_path.read_text(encoding="utf-8")
            elif args.text:
                source_text = args.text
            else:
                raise Refusal("Provide decision text with --text or an artifact path with --source.", code="DECISION_SOURCE_REQUIRED")
            return import_decision(
                args.root,
                source_text,
                venue=args.venue,
                manuscript_id=args.manuscript_id,
                deadline=args.deadline,
                decision_class=args.decision_class,
                user_confirmed=bool(args.decision_class),
                dry_run=args.dry_run,
            )
        if args.submit_action == "plan":
            return submit_plan(args.root, dry_run=args.dry_run)
        if args.submit_action == "build-response":
            fields = None
            if args.fields:
                fields_target = guard_path(args.root, args.fields, must_exist=True)
                try:
                    fields_value = json.loads(fields_target.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
                    raise Refusal(f"Could not parse submission fields file: {exc}", code="INVALID_FIELDS") from exc
                if isinstance(fields_value, Mapping):
                    fields_value = fields_value.get("fields", [])
                if not isinstance(fields_value, list):
                    raise Refusal("Submission fields file must contain an array of uriel.submission_field.v1 records.", code="INVALID_FIELDS")
                fields = fields_value
            return build_response(args.root, fields=fields, dry_run=args.dry_run)
        if args.submit_action == "guide":
            return submit_guide(args.root, fields_path=args.fields, dry_run=args.dry_run)
        if args.submit_action == "verify":
            return submit_verify(args.root)
        if args.submit_action == "archive":
            return archive_submission(args.root, dry_run=args.dry_run)
        if args.submit_action == "status":
            return submission_status(args.root)
        if args.submit_action == "next-prompt":
            return submit_next_prompt(args.root, output=args.output, dry_run=args.dry_run)
    raise Refusal("Unknown command.", code="UNKNOWN_COMMAND")


def main(argv: Optional[Sequence[str]] = None) -> int:
    command = "unknown"
    json_output = False
    try:
        args = parser().parse_args(list(argv) if argv is not None else None)
        command = args.command
        json_output = bool(args.json_output)
        result = dispatch(args)
        envelope = _envelope("OK", command, result=result)
        if json_output:
            print(json.dumps(envelope, ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        else:
            _print_human(command, result, args)
        if command == "audit" and isinstance(result, Mapping) and result.get("status") != "PASS":
            return 2
        if command == "verify" and isinstance(result, Mapping) and not result.get("verified"):
            return 2
        if command == "verify-blessing" and isinstance(result, Mapping) and not result.get("verified"):
            return 2
        return 0
    except Refusal as exc:
        error = exc.as_dict()
        if json_output:
            print(json.dumps(_envelope("REFUSED", command, error=error), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        else:
            print("Uriel refusal [{0}]: {1}".format(exc.code, exc), file=sys.stderr)
            print("Repair options:", file=sys.stderr)
            for index, repair in enumerate(exc.repairs, start=1):
                print("  {0}. {1}".format(index, repair), file=sys.stderr)
            if exc.details:
                print("Details: " + json.dumps(exc.details, ensure_ascii=False, sort_keys=True), file=sys.stderr)
        return 2
    except Exception as exc:  # fail closed while preserving a machine-readable boundary
        error = {"type": type(exc).__name__, "message": str(exc)}
        if json_output:
            print(json.dumps(_envelope("ERROR", command, error=error), ensure_ascii=False, sort_keys=True, separators=(",", ":")))
        else:
            print("Uriel internal error: {0}: {1}".format(type(exc).__name__, exc), file=sys.stderr)
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
