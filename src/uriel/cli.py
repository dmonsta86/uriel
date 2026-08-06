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
    initialize_project,
    list_reminders,
    load_project,
    paths_for,
    pretty_json,
    project_status,
    run_workload,
    save_project,
    sha256_file,
    sha256_text,
    update_reminder,
    utc_now,
    verify_project,
    verify_source_manifest,
)
from .intake import intake_idea
from .prompts import build_prompt
from .reviews import REVIEW_TASKS, import_review, list_reviews, review_template
from .schema import validate_project


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

    intake = commands.add_parser("intake", help="preserve a rough question and create or update a project")
    intake.add_argument("question")
    _root_argument(intake)
    intake.add_argument("--title", default="")
    intake.add_argument("--privacy", choices=("public", "internal", "confidential", "restricted"), default="public")

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


def _print_human(command: str, result: Any) -> None:
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
    if command == "prompt" and isinstance(result, Mapping):
        print("Prompt saved: {0}".format(result.get("prompt_path")))
        print("Prompt SHA-256: {0}".format(result.get("prompt_sha256")))
        if result.get("show"):
            print()
            print(result.get("prompt", ""))
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
            _print_human(command, result)
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
