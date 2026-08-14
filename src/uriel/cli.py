"""Argparse command-line interface for Uriel (no runtime dependencies)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

from . import __version__
from .adapters import run_external_agent
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
from .data_contracts import (
    DEFAULT_MAX_COLUMNS,
    DEFAULT_MAX_FIELD_BYTES,
    DEFAULT_MAX_NESTING_DEPTH,
    DEFAULT_MAX_RECORDS,
    DEFAULT_MAX_SOURCE_BYTES,
    DEFAULT_TIMEOUT_SECONDS,
    plan_data_import,
    verify_data_record_file,
)
from .data_ingress import import_data_artifact, verify_data_import
from .data_desk import (
    diff_data_generations,
    inspect_data_artifact,
    reconcile_data_generations,
    verify_data_generation,
)
from .data_readiness import (
    data_readiness_state,
    make_generation_sort_spec,
    make_sort_spec,
    propose_sort_spec_plan,
    readiness_check,
    readiness_status,
)
from .decisions import DECISION_CLASSES
from .gate_contract import (
    gate_0_from_readiness,
    gate_state_summary,
    latest_gate_decision,
)
from .gate_failures import (
    AUDIT_TO_FAILURE,
    classify_failure,
    constructive_response,
    nonblocking_conditions_met,
)
from .gap_register import (
    build_gap,
    load_latest_gap_register,
    render_gap_register_csv,
    write_gap_register,
)
from .forge_engine import (
    STATES as FORGE_STATES,
    forge_init,
    forge_transition,
    load_forge_request,
    verify_forge_run,
)
from .forge_forward import (
    forge_continue,
    forge_export,
    load_forward_request,
    verify_forge_continuation,
    verify_forge_export,
)
from .independent_verify import compute_binding_digest, independent_verify, latest_verifier
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
from .repair_packet import build_repair_packet, verify_repair_packet
from .research_verbatim import (
    capture_entry as capture_verbatim_entry,
    consent_status as verbatim_consent_status,
    consider_offer as consider_verbatim_offer,
    decline_offer as decline_verbatim_offer,
    disable_capture as disable_verbatim_capture,
    drift_review as verbatim_drift_review,
    export_ledger as export_verbatim_ledger,
    propose_entry as propose_verbatim_entry,
    remove_entry as remove_verbatim_entry,
    remove_ledger as remove_verbatim_ledger,
    review_entries as review_verbatim_entries,
    search_entries as search_verbatim_entries,
    set_consent_mode as set_verbatim_consent_mode,
    verify_ledger as verify_verbatim_ledger,
)
from .reviews import REVIEW_TASKS, import_review, list_reviews, review_template
from .schema import validate_project
from .scholarly_acquisition import (
    LocalMockTransport,
    execute_scholarly_mock,
    plan_scholarly_mock,
    verify_scholarly_mock,
)
from .seed import seed_project, write_seed_brief
from .strict_blessing import (
    blessing_eligibility,
issue_strict_blessing,
run_strict_gates,
strict_gates_from_audit,
verify_strict_blessing,
)
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


def _verbatim_scope_arguments(parser: argparse.ArgumentParser) -> None:
    _root_argument(parser)
    parser.add_argument(
        "--user",
        required=True,
        help="stable user-scope reference; only its SHA-256 isolation key is stored",
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
    rd_init_input = rd_init.add_mutually_exclusive_group(required=True)
    rd_init_input.add_argument("--dataset", help="legacy project-relative CSV, TSV, or JSONL path")
    rd_init_input.add_argument("--generation", help="exact 64-character Data Desk generation ID")
    rd_init.add_argument("--keys", nargs="+", default=[])
    rd_init.add_argument("--tie-break", nargs="+", default=[])
    rd_init.add_argument("--nulls", choices=("nulls_first", "nulls_last", "nulls_error"), default="nulls_last")
    rd_init.add_argument("--dup-policy", choices=("block", "exact", "keep_first"), default="block")
    rd_init.add_argument("--analysis-plan", default="")
    rd_check = readiness_actions.add_parser("check", help="run the Gate 0 check matrix and write a receipt")
    _root_argument(rd_check)
    rd_check.add_argument("--sort-spec", default="")
    rd_check.add_argument("--dataset", default="")
    rd_check.add_argument("--generation", default="", help="exact Data Desk generation ID")
    rd_check.add_argument("--analysis-plan", default="")
    rd_status = readiness_actions.add_parser("status", help="latest receipt and staleness against current data")
    _root_argument(rd_status)
    rd_status.add_argument("--dataset", default="")
    rd_status.add_argument("--generation", default="", help="exact Data Desk generation ID")
    rd_status.add_argument("--sort-spec", default="", help="exact generation-bound SortSpec path")
    rd_status.add_argument("--receipt", default="", help="exact generation-bound readiness receipt path")

    data = commands.add_parser("data", help="local Evidence Ingress contracts and Data Readiness proposals")
    data_actions = data.add_subparsers(dest="data_action", required=True)
    data_plan = data_actions.add_parser("plan", help="inspect one selected regular file and emit a no-write import plan")
    _root_argument(data_plan)
    data_plan.add_argument("--source", required=True, help="one explicitly selected local regular file")
    data_plan.add_argument("--label", default="", help="path-free logical label; defaults to a hash-derived label")
    data_plan.add_argument("--max-source-bytes", type=int, default=DEFAULT_MAX_SOURCE_BYTES)
    data_plan.add_argument("--max-records", type=int, default=DEFAULT_MAX_RECORDS)
    data_plan.add_argument("--max-columns", type=int, default=DEFAULT_MAX_COLUMNS)
    data_plan.add_argument("--max-nesting-depth", type=int, default=DEFAULT_MAX_NESTING_DEPTH)
    data_plan.add_argument("--max-field-bytes", type=int, default=DEFAULT_MAX_FIELD_BYTES)
    data_plan.add_argument("--timeout-seconds", type=int, default=DEFAULT_TIMEOUT_SECONDS)
    data_import = data_actions.add_parser("import", help="seal one selected source under a reviewed import plan")
    _root_argument(data_import)
    data_import.add_argument("--source", required=True, help="the same explicit local regular file reviewed by the plan")
    data_import.add_argument("--plan", required=True, help="project-relative raw plan or saved `--json data plan` result")
    data_acquire_mock = data_actions.add_parser(
        "acquire-mock",
        help="exercise the disabled scholarly firewall with one confined local fixture",
    )
    _root_argument(data_acquire_mock)
    data_acquire_mock.add_argument(
        "--fixture",
        required=True,
        help="one regular file beneath project sources/ used as opaque mock response bytes",
    )
    data_acquire_mock.add_argument(
        "--term",
        action="append",
        required=True,
        dest="terms",
        help="one structured search term; repeat as needed",
    )
    data_acquire_mock.add_argument("--year-from", type=int, default=None)
    data_acquire_mock.add_argument("--year-to", type=int, default=None)
    data_acquire_mock.add_argument("--max-results", type=int, default=25)
    data_acquire_mock.add_argument(
        "--acknowledge-local-mock",
        action="store_true",
        help="confirm this is a local policy exercise, not live scholarly acquisition",
    )
    data_verify_acquisition = data_actions.add_parser(
        "verify-acquisition",
        help="offline-recompute one local-mock acquisition receipt",
    )
    _root_argument(data_verify_acquisition)
    data_verify_acquisition.add_argument(
        "--receipt",
        required=True,
        help="project-relative scholarly local-mock receipt",
    )
    data_verify_import = data_actions.add_parser("verify-import", help="recompute one managed import from its receipt")
    _root_argument(data_verify_import)
    data_verify_import.add_argument("--receipt", required=True, help="project-relative import receipt path")
    data_inspect = data_actions.add_parser("inspect", help="create a deterministic structural generation from a managed import")
    _root_argument(data_inspect)
    data_inspect.add_argument("--receipt", required=True, help="project-relative verified import receipt path")
    data_inspect.add_argument(
        "--unit",
        action="append",
        default=[],
        metavar="COLUMN=UNIT",
        help="record one explicitly user-confirmed unit; repeat as needed",
    )
    data_inspect.add_argument(
        "--semantic-type",
        action="append",
        default=[],
        metavar="COLUMN=TYPE",
        help="record one explicitly user-confirmed semantic type; repeat as needed",
    )
    data_diff = data_actions.add_parser("diff", help="preview conflict-preserving deltas between two generations")
    _root_argument(data_diff)
    data_diff.add_argument("--left-generation", required=True)
    data_diff.add_argument("--right-generation", required=True)
    data_diff.add_argument("--keys", nargs="+", required=True, help="confirmed column names or stable col- identifiers")
    data_diff.add_argument(
        "--include-delta-ledger",
        action="store_true",
        help="include every local per-record delta entry in JSON output (may be large or sensitive)",
    )
    data_reconcile = data_actions.add_parser("reconcile", help="create a generation that preserves every record and conflict")
    _root_argument(data_reconcile)
    data_reconcile.add_argument("--left-generation", required=True)
    data_reconcile.add_argument("--right-generation", required=True)
    data_reconcile.add_argument("--keys", nargs="+", required=True, help="confirmed column names or stable col- identifiers")
    data_verify_generation = data_actions.add_parser("verify-generation", help="recompute generation, profile, raw, and reconciliation bindings")
    _root_argument(data_verify_generation)
    data_verify_generation.add_argument("--generation", required=True, help="64-character Data Desk generation ID")
    data_verify = data_actions.add_parser("verify-record", help="verify one project-relative versioned Data Desk record")
    _root_argument(data_verify)
    data_verify.add_argument("--record", required=True, help="project-relative JSON record path")
    data_propose = data_actions.add_parser("propose-sort", help="propose the best sorting method from the structure of the data (§9.1)")
    _root_argument(data_propose)
    data_propose.add_argument("--dataset", required=True)
    data_propose.add_argument("--sample", type=int, default=20, help="sample rows used for detection evidence")

    forge = commands.add_parser("forge", help="immutable local Forge runs, transitions, and verification")
    forge_actions = forge.add_subparsers(dest="forge_action", required=True)
    forge_init_cmd = forge_actions.add_parser("init", help="create one immutable DRAFT run from a reviewed JSON request")
    _root_argument(forge_init_cmd)
    forge_init_cmd.add_argument("--request", required=True, help="project-relative uriel.forge_init_request.v1 JSON")
    forge_transition_cmd = forge_actions.add_parser("transition", help="request one validated immutable state transition")
    _root_argument(forge_transition_cmd)
    forge_transition_cmd.add_argument("--snapshot", required=True, help="exact project-relative content-addressed parent snapshot")
    forge_transition_cmd.add_argument("--to-state", required=True, choices=FORGE_STATES)
    forge_transition_cmd.add_argument("--rationale", required=True, help="bounded reason for this exact transition")
    forge_transition_cmd.add_argument(
        "--request",
        default="",
        help="optional project-relative uriel.forge_transition_request.v1 JSON",
    )
    forge_verify_cmd = forge_actions.add_parser("verify", help="independently re-read one exact snapshot, lineage, and live refs")
    _root_argument(forge_verify_cmd)
    forge_verify_cmd.add_argument("--snapshot", required=True, help="exact project-relative content-addressed snapshot")
    forge_continue_cmd = forge_actions.add_parser(
        "continue",
        help="seal one evidence-bound continuation and transparent Next Move ranking",
    )
    _root_argument(forge_continue_cmd)
    forge_continue_cmd.add_argument("--snapshot", required=True, help="exact incomplete Forge snapshot")
    forge_continue_cmd.add_argument("--request", required=True, help="project-relative uriel.forge_forward_request.v1 JSON")
    forge_verify_continuation_cmd = forge_actions.add_parser(
        "verify-continuation",
        help="verify one exact continuation and its live source run",
    )
    _root_argument(forge_verify_continuation_cmd)
    forge_verify_continuation_cmd.add_argument("--packet", required=True, help="exact content-addressed continuation packet")
    forge_export_cmd = forge_actions.add_parser(
        "export",
        help="create a fresh generated metadata-only sanitized export",
    )
    _root_argument(forge_export_cmd)
    forge_export_cmd.add_argument("--snapshot", required=True, help="exact Forge snapshot to project")
    forge_export_cmd.add_argument("--destination", required=True, help="fresh project-relative export directory")
    forge_verify_export_cmd = forge_actions.add_parser(
        "verify-export",
        help="verify closed export membership, hashes, sanitation, and exact source",
    )
    _root_argument(forge_verify_export_cmd)
    forge_verify_export_cmd.add_argument("--manifest", required=True, help="exact project-relative sanitized manifest")
    forge_verify_export_cmd.add_argument("--snapshot", required=True, help="exact source Forge snapshot")

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
    burst_init_cmd.add_argument("--generation", default="", help="exact ready Data Desk generation ID")
    burst_init_cmd.add_argument("--columns", nargs="+", default=[], help="explicit task-needed column names or stable IDs")
    burst_init_cmd.add_argument("--row-index", action="append", type=int, default=[], help="explicit zero-based generation row; repeat as needed")
    burst_init_cmd.add_argument("--row-limit", type=int, default=100, help="hard selected-row ceiling (maximum 1000)")
    burst_init_cmd.add_argument("--readiness-sort-spec", default="", help="exact generation-bound SortSpec path")
    burst_init_cmd.add_argument("--readiness-receipt", default="", help="exact PASS readiness receipt path")
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

    audit = commands.add_parser("audit", help="evaluate all Three Gates; subcommands add strict failure guidance")
    _root_argument(audit)
    audit.add_argument("--profile", choices=PROFILES, default="standard")
    audit_actions = audit.add_subparsers(dest="audit_action")
    audit_explain = audit_actions.add_parser("explain", help="map audit findings onto the strict failure taxonomy and responses")
    _root_argument(audit_explain)
    audit_explain.add_argument("--profile", choices=PROFILES, default="standard")
    audit_gaps = audit_actions.add_parser("gaps", help="write the content-addressed gap register from current findings")
    _root_argument(audit_gaps)
    audit_gaps.add_argument("--profile", choices=PROFILES, default="standard")
    audit_repair = audit_actions.add_parser("repair-plan", help="build the 14-file constructive repair packet")
    _root_argument(audit_repair)
    audit_repair.add_argument("--profile", choices=PROFILES, default="standard")
    audit_recheck = audit_actions.add_parser("recheck", help="re-run strict Gates 0-3 and report eligibility")
    _root_argument(audit_recheck)
    audit_recheck.add_argument("--profile", choices=PROFILES, default="standard")
    audit_recheck.add_argument("--generation", default="", help="exact Data Desk generation ID")
    audit_recheck.add_argument("--sort-spec", default="", help="exact generation-bound SortSpec path")
    audit_recheck.add_argument("--readiness-receipt", default="", help="exact generation-bound readiness receipt path")

    blessing = commands.add_parser("blessing", help="issue a Blessing after a submission-profile PASS, or inspect strict eligibility")
    _root_argument(blessing)
    blessing_actions = blessing.add_subparsers(dest="blessing_action")
    blessing_elig = blessing_actions.add_parser("eligibility", help="report why strict Blessing is or is not eligible (never creates a certificate)")
    _root_argument(blessing_elig)
    blessing_issue = blessing_actions.add_parser("issue", help="issue the strict Blessing after eligibility, verifier recomputation, and zero blockers")
    _root_argument(blessing_issue)
    blessing_legacy = blessing_actions.add_parser("legacy", help="[DEPRECATED] issue a legacy Blessing certificate")
    _root_argument(blessing_legacy)
    blessing_verify = blessing_actions.add_parser("verify", help="verify a strict Blessing package against its records")
    blessing_verify.add_argument("package")
    blessing_verify.add_argument("--root", help="optional live project root")

    verify_b = commands.add_parser("verify-blessing", help="verify a Blessing package, optionally against a live project")
    verify_b.add_argument("package")
    verify_b.add_argument("--root", help="optional live project root")

    verify = commands.add_parser("verify", help="verify source, ledger, and execution receipts")
    _root_argument(verify)

    status = commands.add_parser("status", help="show project and current-audit status")
    _root_argument(status)

    verbatim = commands.add_parser("verbatim", help="opt-in exact-wording ledger for one user and research project")
    verbatim_actions = verbatim.add_subparsers(
        dest="verbatim_action", required=True
    )

    verbatim_status = verbatim_actions.add_parser(
        "status", help="inspect mode, offer preference, and isolated entry count"
    )
    _verbatim_scope_arguments(verbatim_status)

    verbatim_offer = verbatim_actions.add_parser(
        "offer", help="consider one discreet offer; never capture message text"
    )
    _verbatim_scope_arguments(verbatim_offer)
    verbatim_offer.add_argument(
        "--signal",
        action="append",
        default=[],
        choices=(
            "high-detail",
            "accuracy-sensitive",
            "novel",
            "long-lived",
            "project-baseline",
            "formal-prediction",
            "consequential-refinement",
        ),
        help="advisory qualifying signal; repeat as needed",
    )

    verbatim_decline = verbatim_actions.add_parser(
        "decline", help="decline the offer and suppress repeat offers"
    )
    _verbatim_scope_arguments(verbatim_decline)

    verbatim_consent = verbatim_actions.add_parser(
        "consent", help="explicitly select manual, assisted, or project mode"
    )
    _verbatim_scope_arguments(verbatim_consent)
    verbatim_consent.add_argument(
        "--mode", required=True, choices=("manual", "assisted", "project")
    )
    verbatim_consent.add_argument(
        "--confirm",
        action="store_true",
        help="confirm the user's explicit opt-in for this user and project",
    )

    verbatim_disable = verbatim_actions.add_parser(
        "disable", help="disable future capture while preserving reviewable entries"
    )
    _verbatim_scope_arguments(verbatim_disable)

    verbatim_propose = verbatim_actions.add_parser(
        "propose", help="make an assisted in-memory proposal; write no content"
    )
    _verbatim_scope_arguments(verbatim_propose)
    propose_input = verbatim_propose.add_mutually_exclusive_group(required=True)
    propose_input.add_argument("--text", help="exact selected user text")
    propose_input.add_argument(
        "--text-file", help="project-relative UTF-8 file containing exact text"
    )
    verbatim_propose.add_argument("--source-ref", required=True)
    verbatim_propose.add_argument("--label", default=None)

    verbatim_capture = verbatim_actions.add_parser(
        "capture", help="capture one explicitly authorized user research statement"
    )
    _verbatim_scope_arguments(verbatim_capture)
    capture_input = verbatim_capture.add_mutually_exclusive_group(required=True)
    capture_input.add_argument("--text", help="exact selected user text")
    capture_input.add_argument(
        "--text-file", help="project-relative UTF-8 file containing exact text"
    )
    verbatim_capture.add_argument("--source-ref", required=True)
    verbatim_capture.add_argument(
        "--mode", required=True, choices=("manual", "assisted", "project")
    )
    verbatim_capture.add_argument(
        "--confirm-entry",
        action="store_true",
        help="confirm this manual or assisted entry",
    )
    verbatim_capture.add_argument(
        "--project-research",
        action="store_true",
        help="confirm the selected text belongs to this research project",
    )
    verbatim_capture.add_argument(
        "--qualifying",
        action="store_true",
        help="mark a project-mode statement as a qualifying baseline or refinement",
    )
    verbatim_capture.add_argument("--label", default=None)
    verbatim_capture.add_argument("--summary", default=None)
    verbatim_capture.add_argument(
        "--link",
        action="append",
        default=[],
        metavar="RELATION:ENTRY_ID",
        help="REFINES, CORRECTS, or SUPERSEDES link; repeat as needed",
    )

    verbatim_review = verbatim_actions.add_parser(
        "review", help="review all verified entries in this isolated scope"
    )
    _verbatim_scope_arguments(verbatim_review)

    verbatim_search = verbatim_actions.add_parser(
        "search", help="search exact text, labels, and source references"
    )
    _verbatim_scope_arguments(verbatim_search)
    verbatim_search.add_argument("query")

    verbatim_drift = verbatim_actions.add_parser(
        "drift", help="advisory comparison against linked exact entries"
    )
    _verbatim_scope_arguments(verbatim_drift)
    drift_input = verbatim_drift.add_mutually_exclusive_group(required=True)
    drift_input.add_argument("--later-text", help="later manuscript, claim, or summary")
    drift_input.add_argument(
        "--later-text-file", help="project-relative UTF-8 later-text file"
    )
    verbatim_drift.add_argument(
        "--entry", action="append", required=True, dest="entry_ids"
    )

    verbatim_export = verbatim_actions.add_parser(
        "export", help="explicitly export this isolated ledger as JSON"
    )
    _verbatim_scope_arguments(verbatim_export)
    verbatim_export.add_argument(
        "--destination", required=True, help="fresh project-relative JSON path"
    )

    verbatim_verify = verbatim_actions.add_parser(
        "verify", help="verify consent, entries, exact hashes, and ledger hash"
    )
    _verbatim_scope_arguments(verbatim_verify)

    verbatim_remove_entry = verbatim_actions.add_parser(
        "remove-entry", help="remove one selected entry"
    )
    _verbatim_scope_arguments(verbatim_remove_entry)
    verbatim_remove_entry.add_argument("entry_id")
    verbatim_remove_entry.add_argument("--confirm", action="store_true")

    verbatim_remove_ledger = verbatim_actions.add_parser(
        "remove-ledger", help="remove consent and entries for this exact scope"
    )
    _verbatim_scope_arguments(verbatim_remove_ledger)
    verbatim_remove_ledger.add_argument("--confirm", action="store_true")

    prompt = commands.add_parser("prompt", help="create an optional AI/human review prompt")
    _root_argument(prompt)
    prompt.add_argument("task", choices=REVIEW_TASKS)
    prompt.add_argument("--provider", choices=("generic", "local", "sol-mode", "generic-web"), default="generic")
    prompt.add_argument("--acknowledge-external", action="store_true", help="acknowledge current provider/privacy risk for an external prompt")
    prompt.add_argument("--include-sensitive", action="store_true", help="explicitly include non-public project text; local labels are not assumed safe")
    prompt.add_argument("--show", action="store_true", help="print the full prompt")

    assist = commands.add_parser("assist", help="run one bounded review through an external agent")
    _root_argument(assist)
    assist.add_argument("task", choices=REVIEW_TASKS)
    assist.add_argument("--model", required=True, help="bounded provider/model identifier passed to the external agent")
    assist.add_argument("--timeout", type=int, default=900, help="process-tree timeout in seconds (30-900)")
    assist.add_argument("--acknowledge-external", action="store_true", help="required process/provider/privacy/cost acknowledgement")

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
    if command == "forge" and isinstance(result, Mapping):
        action = args.forge_action
        if action == "continue":
            print("Forge continuation: {0} - blocker status {1}".format(result.get("status"), result.get("blocker_status")))
            print("Preferred Next Move: {0}".format(result.get("preferred_move_id")))
            print("Packet: {0}".format(result.get("continuation_relative_path")))
            print("Record SHA-256: {0}".format(result.get("record_sha256")))
            print("Upstream authority: NONE - network/model/subprocess calls: 0/0/0")
            return
        if action == "verify-continuation":
            print("Forge continuation verification: PASS - packet, derivation, source, and bindings checked")
            print("Packet: {0}".format(result.get("continuation_relative_path")))
            print("Record SHA-256: {0}".format(result.get("record_sha256")))
            print("Upstream authority: NONE - network/model/subprocess calls: 0/0/0")
            return
        if action == "export":
            print("Forge sanitized export: EXPORTED - generated metadata only - evidence bodies 0")
            print("Manifest: {0}".format(result.get("manifest_relative_path")))
            print("Upstream authority: NONE - network/model/subprocess calls: 0/0/0")
            return
        if action == "verify-export":
            print("Forge sanitized export verification: PASS - membership, hashes, sanitation, and source checked")
            print("Manifest: {0}".format(result.get("manifest_relative_path")))
            print("Upstream authority: NONE - network/model/subprocess calls: 0/0/0")
            return
        if action == "init":
            print("Forge run: {0} · DRAFT · immutable local snapshot".format(result.get("status")))
        elif action == "transition":
            print("Forge transition: {0} · state {1}".format(result.get("status"), result.get("state")))
        else:
            print("Forge verification: PASS · record, lineage, and bindings checked")
        print("Run: {0} · revision {1}".format(result.get("run_id"), result.get("revision")))
        print("Snapshot: {0}".format(result.get("snapshot_relative_path")))
        print("Record SHA-256: {0}".format(result.get("record_sha256")))
        print("Upstream authority: NONE · network/model/subprocess calls: 0/0/0")
        return
    if command == "data" and isinstance(result, Mapping):
        if args.data_action == "plan":
            plan = result.get("plan", {})
            source = plan.get("source", {}) if isinstance(plan, Mapping) else {}
            print("Evidence Ingress plan: DRY_RUN · no writes · no network")
            print("Source: {0} · {1} · {2} bytes".format(
                source.get("logical_label"), source.get("format"), source.get("size_bytes")))
            print("SHA-256: {0}".format(source.get("content_sha256")))
            print("Source location remained private. Save and review this exact plan before import.")
            return
        if args.data_action == "import":
            print("Evidence Ingress import: {0} · {1}".format(result.get("status"), result.get("outcome")))
            print("Managed artifact: {0}".format(result.get("managed_relative_path")))
            print("Receipt: {0}".format(result.get("receipt_relative_path")))
            print("Gate 0 authority: NOT GRANTED · run Data Readiness separately")
            return
        if args.data_action == "acquire-mock":
            print("Scholarly firewall: {0} - LOCAL MOCK ONLY - no network".format(result.get("status")))
            print("Quarantine: {0}".format(result.get("managed_relative_path")))
            print("Receipt: {0}".format(result.get("receipt_relative_path")))
            print("Raw bytes remain unparsed. Readiness, Gates, publication, and Blessing authority: NOT GRANTED")
            return
        if args.data_action == "verify-acquisition":
            print("Scholarly local-mock receipt: PASS - offline bindings and quarantine verified")
            print("SHA-256: {0}".format(result.get("body_content_sha256")))
            print("Transport invoked: NO - authority: NOT GRANTED")
            return
        if args.data_action == "verify-import":
            print("Managed import: PASS · exact bytes and record bindings verified")
            print("SHA-256: {0}".format(result.get("content_sha256")))
            print("Gate 0 authority: NOT GRANTED")
            return
        if args.data_action == "inspect":
            print("Data Desk generation: PASS · {0}".format(result.get("generation_id")))
            print("Records: {0} · columns: {1}".format(result.get("record_count"), result.get("column_count")))
            profile = result.get("profile", {})
            print("Leads/candidates: {0}".format(len(profile.get("anomaly_queue", [])) if isinstance(profile, Mapping) else 0))
            print("User-confirmed annotations: {0}".format(
                len(profile.get("user_confirmed_annotations", [])) if isinstance(profile, Mapping) else 0
            ))
            print("Derived index: {0} · NONAUTHORITATIVE".format(
                (result.get("derived_index") or {}).get("relative_path")
            ))
            print("Gate 0 authority: NOT GRANTED")
            return
        if args.data_action == "diff":
            summary = result.get("summary", {})
            print("Data Desk diff: DRY_RUN · no writes")
            print("Added {0} · absent {1} · modified {2} · unchanged {3} · unknown {4}".format(
                summary.get("added_count"), summary.get("absent_count"), summary.get("modified_count"),
                summary.get("unchanged_count"), summary.get("unknown_count")))
            print("Conflicts preserved if reconciled: {0}".format(summary.get("conflict_count")))
            print("Per-record delta ledger: {0} entries · SHA-256 {1}".format(
                result.get("delta_entry_count"), result.get("delta_sha256")
            ))
            return
        if args.data_action == "reconcile":
            print("Data Desk reconciliation: PASS · all input records preserved")
            print("Generation: {0}".format(result.get("generation_id")))
            print("Records: {0} · conflicts: {1}".format(result.get("record_count"), result.get("summary", {}).get("conflict_count")))
            print("Delta ledger: {0} · {1} entries".format(
                result.get("delta_ledger_relative_path"), result.get("delta_entry_count")
            ))
            print("Gate 0 authority: NOT GRANTED")
            return
        if args.data_action == "verify-generation":
            print("Data generation: PASS · {0}".format(result.get("generation_id")))
            print("Records SHA-256: {0}".format(result.get("records_sha256")))
            print("Gate 0 authority: NOT GRANTED")
            return
        if args.data_action == "verify-record":
            print("Data record: PASS · {0}".format(result.get("schema")))
            print("Record SHA-256: {0}".format(result.get("record_sha256")))
            return
        if args.data_action == "propose-sort":
            print("Sort proposal: {0} · gate {1}".format(
                result.get("detected_kind") or "blocked", result.get("gate_status")))
            print("Dataset: {0} · SHA-256 {1}".format(
                result.get("dataset"), result.get("dataset_identity")))
            if result.get("blocked_reasons"):
                print("Blocked: {0}".format("; ".join(result.get("blocked_reasons", []))))
                for step in result.get("identity_clarification_plan", []):
                    print("  - {0}".format(step))
                return
            print("Proposed primary keys: {0}".format(", ".join(result.get("proposed_primary_keys", []))))
            print("Proposed tie-break: {0}".format(", ".join(result.get("proposed_tie_break_keys", [])) or "(immutable record ID)"))
            for warning in result.get("warnings", []):
                print("Warning: {0}".format(warning))
            print("Next step: {0}".format(result.get("next_step")))
            print("Proposal only; nothing was sealed.")
            return
    if command == "audit" and isinstance(result, Mapping):
        if args.audit_action == "explain":
            print("Strict failure map: {0} findings · audit {1}".format(
                len(result.get("findings", [])), result.get("audit_id")))
            for finding in result.get("findings", []):
                print("Gate {0} {1} -> {2} ({3})".format(
                    finding.get("gate"), finding.get("code"), finding.get("status"), finding.get("group")))
                print("  {0}".format(finding.get("message", "")))
                response = finding.get("response") or {}
                if response.get("minimum_repair"):
                    print("  Minimum repair: {0}".format(response["minimum_repair"]))
            return
        if args.audit_action == "gaps":
            print("Gap register: {0} rows · register {1}".format(
                result.get("gap_count"), (result.get("register") or {}).get("register_sha256")))
            csv_text = result.get("csv", "")
            if csv_text:
                print(csv_text.rstrip())
            return
        if args.audit_action == "repair-plan":
            packet = result.get("packet", {})
            print("Repair packet: {0}".format(packet.get("packet_dir")))
            print("Digest: {0} · files: {1} · blockers: {2}".format(
                packet.get("digest"), packet.get("file_count"), result.get("blocker_count")))
            return
        if args.audit_action == "recheck":
            eligibility = result.get("eligibility", {})
            print("Strict recheck: eligible = {0}".format(eligibility.get("eligible")))
            gates = eligibility.get("gates", {})
            print("Gates: {0}".format(", ".join(
                "Gate {0}={1}".format(number, status)
                for number, status in sorted(gates.items()))))
            print("Verifier: {0} · binding {1}".format(
                eligibility.get("verifier_decision"), eligibility.get("binding_digest")))
            for blocker in eligibility.get("blockers", []):
                print("  BLOCKER: {0}".format(blocker))
            return
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
        if args.blessing_action == "eligibility":
            print("Strict Blessing eligibility: {0}".format("ELIGIBLE" if result.get("eligible") else "NOT ELIGIBLE"))
            gates = result.get("gates", {})
            print("Gates: {0}".format(", ".join(
                "Gate {0}={1}".format(number, status)
                for number, status in sorted(gates.items()))))
            print("Verifier: {0} · binding {1}".format(
                result.get("verifier_decision"), result.get("binding_digest")))
            for blocker in result.get("blockers", []):
                print("  BLOCKER: {0}".format(blocker))
            if result.get("eligible"):
                print("No certificate was created; run `uriel blessing` to issue after an explicit decision.")
            return
        if args.blessing_action in ("issue", "verify"):
            print("Strict Blessing {0}: {1}".format(
                "issued" if args.blessing_action == "issue" else "verify",
                "PASS" if result.get("verified") else "FAIL"))
            print("Blessing ID: {0}".format(result.get("blessing_id")))
            print("Package SHA-256: {0}".format(result.get("package_sha256")))
            print("Binding digest: {0}".format(result.get("binding_digest")))
            if result.get("ledger_event_sha256"):
                print("Ledger event: {0}".format(result["ledger_event_sha256"]))
            for error in result.get("errors", []):
                print("  ERROR: {0}".format(error))
            return
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
            failed = [
                str(check.get("check") or check.get("check_id"))
                for check in result.get("checks", [])
                if check["status"] == "FAIL"
            ]
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


def _audit_explain(root: str, profile: str) -> Dict[str, Any]:
    """Map audit findings onto the strict failure taxonomy and responses."""
    report = audit_project(root, profile=profile)
    findings = []
    for gate in report.gates:
        for finding in gate.findings:
            meta = classify_failure(finding.code)
            response = constructive_response(
                meta["group"],
                claim=finding.subject,
                evidence="; ".join(finding.evidence[:5]),
            )
            findings.append({
                "code": finding.code,
                "gate": gate.gate,
                "status": meta["status"],
                "severity": meta["severity"],
                "group": meta["group"],
                "subject": finding.subject,
                "message": finding.message,
                "response": response,
            })
    return {
        "audit_id": report.audit_id,
        "status": report.status,
        "profile": profile,
        "findings": findings,
    }


def _audit_gaps(root: str, profile: str) -> Dict[str, Any]:
    """Write the content-addressed gap register from current audit findings."""
    report = audit_project(root, profile=profile)
    rows = []
    for gate in report.gates:
        for finding in gate.findings:
            meta = classify_failure(finding.code)
            if meta["status"] == "PASS":
                continue
            rows.append(build_gap(
                gate=gate.gate,
                failure_code=meta["status"],
                severity=meta["severity"],
                observed_fact=finding.message,
                why_it_matters="Finding {0} blocks the strict gate contract".format(finding.code),
                affected_claims=[finding.subject] if finding.subject else (),
                affected_artifacts=[],
                minimum_repair="; ".join(finding.repairs[:3]) or "Define the exact completion conditions.",
            ))
    written = write_gap_register(root, rows, label="audit-{0}".format(profile))
    return {
        "gap_count": len(rows),
        "register": written,
        "csv": render_gap_register_csv(rows) if rows else "",
    }


def _audit_repair(root: str, profile: str) -> Dict[str, Any]:
    """Build the standalone constructive repair packet from current findings."""
    report = audit_project(root, profile=profile)
    register = load_latest_gap_register(root)
    rows = register.get("gaps", []) if register else []
    blockers = []
    for gate in report.gates:
        for finding in gate.findings:
            meta = classify_failure(finding.code)
            if meta["status"] == "PASS":
                continue
            blockers.append({
                "code": finding.code,
                "gate": gate.gate,
                "status": meta["status"],
                "severity": meta["severity"],
                "subject": finding.subject,
                "message": finding.message,
            })
    worst_gate = blockers[0]["gate"] if blockers else 1
    gate_names = {0: "Data Readiness", 1: "Novelty & Clarity", 2: "Evidence & Citation", 3: "Adversarial Integrity"}
    summary = "; ".join(blocker["message"] for blocker in blockers[:5]) or "No blockers reported."
    packet = build_repair_packet(
        root,
        gate=worst_gate,
        gate_name=gate_names.get(worst_gate, "Unknown"),
        decision=str(report.status),
        failure_summary=summary,
        gates_results=report.as_dict(),
        blockers=blockers,
        gaps=rows,
        sorting_plan="Run `uriel data propose-sort --dataset <path>` and seal a SortSpec before any data-dependent conclusion.",
        repair_plan="Resolve every blocker in 03_BLOCKERS.csv. Narrowing is allowed; weakening a gate is not.",
        pivot_options=["Narrow the claim to what the current evidence supports."],
        evidence_requests=["Provide the missing artifacts listed in 08_EVIDENCE_REQUESTS.md."],
        updated_project_spec="Requires a new generation whenever a claim, plan, or artifact changes.",
        completion_checklist=["Gate {0} PASS against the exact contract check list".format(gate) for gate in (0, 1, 2, 3)],
        recheck_instructions="Run `uriel audit recheck` after every repair; a stale or missing receipt is refused.",
        next_prompt="Resolve the blockers, then rerun `uriel audit recheck`.",
    )
    return {"packet": packet, "blocker_count": len(blockers)}


def _audit_recheck(
    root: str,
    profile: str,
    *,
    generation: Optional[str] = None,
    sort_spec: Optional[str] = None,
    readiness_receipt: Optional[str] = None,
) -> Dict[str, Any]:
    """Re-run strict Gates 0-3 (persisting decisions) and report eligibility."""
    gates = run_strict_gates(
        root,
        persist=True,
        generation_id=generation,
        sort_spec_path=sort_spec,
        receipt_path=readiness_receipt,
    )
    eligibility = blessing_eligibility(root)
    return {"gates": gates, "eligibility": eligibility}


def _read_verbatim_text(
    root: str,
    direct_text: Optional[str],
    text_file: Optional[str],
) -> str:
    if direct_text is not None:
        return direct_text
    if not text_file:
        raise Refusal(
            "Provide exact text or one project-relative UTF-8 text file.",
            code="VERBATIM_TEXT_REQUIRED",
        )
    target = guard_path(root, text_file, must_exist=True)
    try:
        return target.read_bytes().decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refusal(
            "Research Verbatim Ledger text files must be valid UTF-8.",
            code="VERBATIM_TEXT_NOT_UTF8",
            details={"path": str(target), "error": str(exc)},
            repairs=[
                "Save the exact statement as UTF-8 without changing its wording.",
                "Pass the exact Unicode text directly with the matching CLI option.",
                "Cancel capture and leave the isolated ledger unchanged.",
            ],
        ) from exc


def _parse_verbatim_links(values: Sequence[str]) -> List[Dict[str, str]]:
    links: List[Dict[str, str]] = []
    for value in values:
        if ":" not in value:
            raise Refusal(
                "Verbatim links use RELATION:ENTRY_ID syntax.",
                code="VERBATIM_LINK_INVALID",
                repairs=[
                    "Use REFINES:ENTRY_ID, CORRECTS:ENTRY_ID, or SUPERSEDES:ENTRY_ID.",
                    "Review the isolated ledger and copy the exact entry ID.",
                    "Omit the optional link.",
                ],
            )
        relation, entry_id = value.split(":", 1)
        links.append({"relation": relation, "entry_id": entry_id})
    return links


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
                generation_id=args.generation or None,
                generation_columns=args.columns,
                row_indices=args.row_index,
                row_limit=args.row_limit,
                readiness_sort_spec=args.readiness_sort_spec or None,
                readiness_receipt=args.readiness_receipt or None,
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
            if args.generation:
                return make_generation_sort_spec(
                    args.root,
                    args.generation,
                    keys=args.keys,
                    tie_break=args.tie_break,
                    nulls=args.nulls,
                    duplicate_policy=args.dup_policy,
                    analysis_plan=args.analysis_plan or None,
                )
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
                generation=args.generation or None,
            )
        if args.readiness_action == "status":
            return readiness_status(
                args.root,
                dataset=args.dataset or None,
                generation=args.generation or None,
                sort_spec_path=args.sort_spec or None,
                receipt_path=args.receipt or None,
            )
    if command == "data":
        if args.data_action == "plan":
            return plan_data_import(
                args.root,
                args.source,
                label=args.label,
                max_source_bytes=args.max_source_bytes,
                max_records=args.max_records,
                max_columns=args.max_columns,
                max_nesting_depth=args.max_nesting_depth,
                max_field_bytes=args.max_field_bytes,
                timeout_seconds=args.timeout_seconds,
            )
        if args.data_action == "import":
            return import_data_artifact(args.root, args.source, args.plan)
        if args.data_action == "acquire-mock":
            bundle = plan_scholarly_mock(
                args.root,
                args.terms,
                year_from=args.year_from,
                year_to=args.year_to,
                max_results=args.max_results,
                acknowledge_local_mock=args.acknowledge_local_mock,
            )
            transport = LocalMockTransport(
                args.root,
                args.fixture,
                expected_request_sha256=bundle["plan"]["request_descriptor_sha256"],
            )
            return execute_scholarly_mock(args.root, bundle, transport)
        if args.data_action == "verify-acquisition":
            return verify_scholarly_mock(args.root, args.receipt)
        if args.data_action == "verify-import":
            return verify_data_import(args.root, args.receipt)
        if args.data_action == "inspect":
            return inspect_data_artifact(
                args.root,
                args.receipt,
                units=args.unit,
                semantic_types=args.semantic_type,
            )
        if args.data_action == "diff":
            result = diff_data_generations(
                args.root, args.left_generation, args.right_generation, args.keys
            )
            if not args.include_delta_ledger:
                result = dict(result)
                result.pop("delta_ledger", None)
                result["delta_ledger_included"] = False
            else:
                result["delta_ledger_included"] = True
            return result
        if args.data_action == "reconcile":
            return reconcile_data_generations(
                args.root, args.left_generation, args.right_generation, args.keys
            )
        if args.data_action == "verify-generation":
            return verify_data_generation(args.root, args.generation)
        if args.data_action == "verify-record":
            return verify_data_record_file(args.root, args.record)
        if args.data_action == "propose-sort":
            return propose_sort_spec_plan(args.root, args.dataset, sample=args.sample)
    if command == "forge":
        if args.forge_action == "init":
            request = load_forge_request(args.root, args.request, initial=True)
            return forge_init(args.root, request)
        if args.forge_action == "transition":
            request = (
                load_forge_request(args.root, args.request, initial=False)
                if args.request
                else None
            )
            return forge_transition(
                args.root,
                args.snapshot,
                args.to_state,
                args.rationale,
                request,
            )
        if args.forge_action == "verify":
            return verify_forge_run(args.root, args.snapshot)
        if args.forge_action == "continue":
            request = load_forward_request(args.root, args.request)
            return forge_continue(args.root, args.snapshot, request)
        if args.forge_action == "verify-continuation":
            return verify_forge_continuation(args.root, args.packet)
        if args.forge_action == "export":
            return forge_export(args.root, args.snapshot, args.destination)
        if args.forge_action == "verify-export":
            return verify_forge_export(args.root, args.manifest, args.snapshot)
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
        if args.audit_action is None:
            return audit_project(args.root, profile=args.profile).as_dict()
        if args.audit_action == "explain":
            return _audit_explain(args.root, args.profile)
        if args.audit_action == "gaps":
            return _audit_gaps(args.root, args.profile)
        if args.audit_action == "repair-plan":
            return _audit_repair(args.root, args.profile)
        if args.audit_action == "recheck":
            return _audit_recheck(
                args.root,
                args.profile,
                generation=args.generation or None,
                sort_spec=args.sort_spec or None,
                readiness_receipt=args.readiness_receipt or None,
            )
    if command == "blessing":
        if args.blessing_action is None:
            # Bare 'uriel blessing' prints help and eligibility; it NEVER creates a certificate.
            return blessing_eligibility(args.root)
        if args.blessing_action == "eligibility":
            return blessing_eligibility(args.root)
        if args.blessing_action == "issue":
            return issue_strict_blessing(args.root)
        if args.blessing_action == "legacy":
            print("[DEPRECATION WARNING] Legacy Blessing issuance is deprecated. Use 'uriel blessing issue' for strict Blessing certificates.")
            return issue_blessing(args.root)
        if args.blessing_action == "verify":
            return verify_strict_blessing(args.package, project_root=args.root or None)
    if command == "verify-blessing":
        return verify_blessing(args.package, project_root=args.root)
    if command == "verify":
        return verify_project(args.root)
    if command == "status":
        return project_status(args.root)
    if command == "verbatim":
        action = args.verbatim_action
        if action == "status":
            return verbatim_consent_status(args.root, args.user)
        if action == "offer":
            return consider_verbatim_offer(args.root, args.user, args.signal)
        if action == "decline":
            return decline_verbatim_offer(args.root, args.user)
        if action == "consent":
            return set_verbatim_consent_mode(
                args.root,
                args.user,
                args.mode,
                explicit_opt_in=args.confirm,
            )
        if action == "disable":
            return disable_verbatim_capture(args.root, args.user)
        if action == "propose":
            text = _read_verbatim_text(args.root, args.text, args.text_file)
            return propose_verbatim_entry(
                args.root,
                args.user,
                text,
                source_message_ref=args.source_ref,
                label=args.label,
            )
        if action == "capture":
            text = _read_verbatim_text(args.root, args.text, args.text_file)
            return capture_verbatim_entry(
                args.root,
                args.user,
                text,
                source_message_ref=args.source_ref,
                capture_mode=args.mode,
                confirmed=args.confirm_entry,
                project_research_statement=args.project_research,
                qualifying_research_statement=args.qualifying,
                label=args.label,
                summary=args.summary,
                links=_parse_verbatim_links(args.link),
            )
        if action == "review":
            return review_verbatim_entries(args.root, args.user)
        if action == "search":
            return search_verbatim_entries(args.root, args.user, args.query)
        if action == "drift":
            later = _read_verbatim_text(
                args.root, args.later_text, args.later_text_file
            )
            return verbatim_drift_review(
                args.root,
                args.user,
                later,
                entry_ids=args.entry_ids,
            )
        if action == "export":
            return export_verbatim_ledger(
                args.root, args.user, args.destination
            )
        if action == "verify":
            return verify_verbatim_ledger(args.root, args.user)
        if action == "remove-entry":
            return remove_verbatim_entry(
                args.root,
                args.user,
                args.entry_id,
                confirmed=args.confirm,
            )
        if action == "remove-ledger":
            return remove_verbatim_ledger(
                args.root, args.user, confirmed=args.confirm
            )
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
        return run_external_agent(
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
        if command == "audit" and isinstance(result, Mapping) and args.audit_action is None and result.get("status") != "PASS":
            return 2
        if command == "blessing" and isinstance(result, Mapping):
            if (args.blessing_action in ("eligibility", None)) and not result.get("eligible"):
                return 2
            if args.blessing_action == "issue" and not result.get("verified"):
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
