"""Workspace onboarding: entry files, consent, preflight, and workspace modes.

Implements the phase-4A/4B contracts:

- provider-neutral AI entry files (URIEL_AI_ENTRY.md, COPY_THIS_TO_YOUR_AI.txt,
  AGENTS.md, NEXT_PROMPT.txt) with no model authority;
- immutable consent records (``uriel.workspace_consent.v1``) with permission
  levels metadata_only / read_only / safe_copy / in_place;
- metadata-only preflight (root hash, counts, VCS, links, cloud-sync
  indicators, sensitive-name indications, copy estimate);
- read-only review workspace outside the source root;
- safe-copy workflow with original-project invariance receipt;
- in-place dry-run/verification with explicit consent gates.

Nothing here reads file contents unless the recorded consent allows it.
"""
from __future__ import annotations

import fnmatch
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .core import (
    STATE_DIR_NAME,
    Refusal,
    atomic_write,
    atomic_write_json,
    canonical_json,
    canonical_root,
    guard_path,
    is_reparse_or_link,
    paths_for,
    sha256_file,
    sha256_text,
    utc_now,
)

ENTRY_KINDS = (
    "new_idea",
    "existing_project",
    "manuscript",
    "submission_form",
    "submission_decision",
    "resume",
    "read_only_review",
)
MODES = ("metadata_only", "read_only", "safe_copy", "in_place")
CONSENT_SCHEMA = "uriel.workspace_consent.v1"
ONBOARDING_SCHEMA = "uriel.onboarding.v1"
PREFLIGHT_SCHEMA = "uriel.preflight.v1"
AI_ENTRY_SCHEMA = "uriel.ai_entry.v1"
COPY_RECEIPT_SCHEMA = "uriel.copy_receipt.v1"
INVARIANCE_SCHEMA = "uriel.invariance_receipt.v1"
INPLACE_PLAN_SCHEMA = "uriel.inplace_plan.v1"

SENSITIVE_NAME_PATTERNS = (
    ".env",
    ".env.*",
    "credentials*",
    "secrets*",
    "*.pem",
    "*.key",
    "*.p12",
    "*.pfx",
    "id_rsa*",
    "id_ed25519*",
    "auth.json",
    "cookies*",
    "*.kdbx",
    "*password*",
    "*.browser_profile",
    "client_secret*",
    "service_account*",
)
CLOUD_SYNC_MARKERS = (
    "onedrive",
    "icloud",
    "dropbox",
    "google drive",
    "googledrive",
    "library/mobile documents",
    "amazon drive",
    "box sync",
)
VCS_DIRS = (".git", ".hg", ".svn")
SUPPORTED_EXTENSIONS = {
    ".md", ".txt", ".json", ".jsonl", ".csv", ".tsv", ".py", ".tex", ".bib",
    ".csl", ".yml", ".yaml", ".toml", ".html", ".css", ".js", ".c", ".h",
    ".cpp", ".rs", ".go", ".java", ".ipynb", ".sql", ".r", ".do", ".log",
    ".pdf", ".docx",
}
ENTRY_FILE_NAMES = (
    "URIEL_START_HERE.md",
    "URIEL_AI_ENTRY.md",
    "COPY_THIS_TO_YOUR_AI.txt",
    "AGENTS.md",
)
HANDOFF_PHRASE = "Ask one numbered batch of questions. Then write the exact next instruction to NEXT_PROMPT.txt before stopping."


def _walk_entries(root: Path) -> List[Dict[str, Any]]:
    """Metadata-only walk: relative path, kind, size, link flag. Skips .uriel."""
    entries: List[Dict[str, Any]] = []
    for current, directories, files in os.walk(root, topdown=True, followlinks=False):
        current_path = Path(current)
        guard_path(root, current_path, must_exist=True)
        kept: List[str] = []
        for name in sorted(directories, key=str.casefold):
            child = current_path / name
            if name == STATE_DIR_NAME or child == root / STATE_DIR_NAME:
                continue
            if is_reparse_or_link(child):
                entries.append(
                    {
                        "path": str(child.relative_to(root).as_posix()),
                        "kind": "link_dir",
                        "size": 0,
                        "sha256": "",
                    }
                )
                continue
            guard_path(root, child, must_exist=True)
            kept.append(name)
        directories[:] = kept
        for name in sorted(files, key=str.casefold):
            path = current_path / name
            relative = str(path.relative_to(root).as_posix())
            if is_reparse_or_link(path):
                entries.append({"path": relative, "kind": "link_file", "size": 0, "sha256": ""})
                continue
            guard_path(root, path, must_exist=True)
            try:
                entries.append(
                    {
                        "path": relative,
                        "kind": "file",
                        "size": path.stat().st_size,
                        "sha256": sha256_file(path),
                    }
                )
            except OSError:
                entries.append({"path": relative, "kind": "unreadable", "size": 0, "sha256": ""})
    entries.sort(key=lambda row: row["path"])
    return entries


def directory_manifest(root: Union[Path, str]) -> Dict[str, Any]:
    """Deterministic content digest of a tree, recording links instead of refusing."""
    root_path = canonical_root(root)
    if not root_path.is_dir():
        raise Refusal("Preflight requires an existing directory.", code="PREFLIGHT_MISSING",
                      repairs=["Pass --root with a directory that exists."])
    entries = _walk_entries(root_path)
    files = [
        {"path": row["path"], "size": row["size"], "sha256": row["sha256"]}
        for row in entries
        if row["kind"] == "file"
    ]
    links = [row["path"] for row in entries if row["kind"] in ("link_dir", "link_file")]
    unreadable = [row["path"] for row in entries if row["kind"] == "unreadable"]
    digest_source = canonical_json({row["path"]: row["sha256"] for row in files})
    return {
        "root_sha256": sha256_text(digest_source),
        "files": files,
        "file_count": len(files),
        "byte_count": sum(int(row["size"]) for row in files),
        "link_paths": links,
        "unreadable_paths": unreadable,
        "generated_at_utc": utc_now(),
    }


def _is_sensitive_name(relative: str) -> bool:
    name = Path(relative).name
    lowered = name.lower()
    for pattern in SENSITIVE_NAME_PATTERNS:
        if fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(lowered, pattern):
            return True
    return False


def detect_cloud_sync(root: Union[Path, str]) -> List[str]:
    """Detect common cloud-sync indicators in the path. Detection is incomplete."""
    path = Path(root).expanduser().resolve()
    text = str(path).replace("\\", "/").lower()
    hits = [marker for marker in CLOUD_SYNC_MARKERS if marker in text]
    return hits


def preflight(root: Union[Path, str]) -> Dict[str, Any]:
    """Metadata-only preflight. Reads names, sizes, and hashes; never content."""
    root_path = canonical_root(root)
    manifest = directory_manifest(root_path)
    vcs = [name for name in VCS_DIRS if (root_path / name).is_dir()]
    sensitive = sorted(
        row["path"] for row in manifest["files"] if _is_sensitive_name(row["path"])
    )
    extensions: Dict[str, int] = {}
    for row in manifest["files"]:
        suffix = Path(row["path"]).suffix.lower() or "(none)"
        extensions[suffix] = extensions.get(suffix, 0) + 1
    supported = sum(count for suffix, count in extensions.items() if suffix in SUPPORTED_EXTENSIONS)
    unsupported = sum(count for suffix, count in extensions.items() if suffix not in SUPPORTED_EXTENSIONS)
    cloud = detect_cloud_sync(root_path)
    return {
        "schema": PREFLIGHT_SCHEMA,
        "selected_root": str(root_path),
        "root_hash": manifest["root_sha256"],
        "file_count": manifest["file_count"],
        "byte_count": manifest["byte_count"],
        "detected_vcs": vcs,
        "detected_uriel_state": (root_path / STATE_DIR_NAME).is_dir(),
        "link_or_reparse_presence": bool(manifest["link_paths"]),
        "link_paths": manifest["link_paths"],
        "unreadable_paths": manifest["unreadable_paths"],
        "cloud_sync_indicators": cloud,
        "sensitive_file_indications": sensitive,
        "formats": {"supported": supported, "unsupported": unsupported},
        "copy_estimate": {"files": manifest["file_count"], "bytes": manifest["byte_count"]},
        "read_only_feasible": True,
        "generated_at_utc": manifest["generated_at_utc"],
    }


def consent_defaults(mode: str) -> Dict[str, bool]:
    if mode == "metadata_only":
        return {"content_read": False, "write": False, "network": False,
                "external_directory": False, "copy": False}
    if mode == "read_only":
        return {"content_read": True, "write": False, "network": False,
                "external_directory": False, "copy": False}
    if mode == "safe_copy":
        return {"content_read": True, "write": True, "network": False,
                "external_directory": False, "copy": True}
    return {"content_read": True, "write": True, "network": False,
            "external_directory": False, "copy": True}


def consent_set(
    root: Union[Path, str],
    mode: str,
    *,
    confirmation: str = "explicit_user",
    cloud_sync_acknowledged: bool = False,
    sensitive_data_acknowledged: bool = False,
    network: bool = False,
    external_directory: bool = False,
    copy: Optional[bool] = None,
    allowed_paths: Sequence[str] = (),
    denied_paths: Sequence[str] = (),
    review_after_days: Optional[int] = None,
) -> Dict[str, Any]:
    """Create a new immutable consent record. Changing consent appends; never mutates."""
    if mode not in MODES:
        raise Refusal("Unknown workspace mode.", code="INVALID_MODE",
                      repairs=["Choose one of: " + ", ".join(MODES)])
    if confirmation not in ("explicit_user", "installer_default_read_only"):
        raise Refusal("Unknown consent confirmation source.", code="INVALID_CONFIRMATION")
    if mode == "in_place" and confirmation != "explicit_user":
        raise Refusal(
            "In-place mode requires explicit user confirmation.",
            code="INPLACE_CONSENT_REQUIRED",
            repairs=["Rerun with --confirm explicit_user after reviewing the protections."],
        )
    root_path = canonical_root(root)
    manifest = directory_manifest(root_path)
    cloud = detect_cloud_sync(root_path)
    if cloud and not cloud_sync_acknowledged and mode != "metadata_only":
        raise Refusal(
            "This workspace appears to live inside a cloud-synced folder ({0}). "
            "Generated research artifacts may sync to the provider.".format(", ".join(cloud)),
            code="CLOUD_SYNC_UNACKNOWLEDGED",
            repairs=[
                "Acknowledge with --cloud-sync-acknowledged after reviewing your sync settings.",
                "Choose a local-only workspace directory instead.",
            ],
        )
    sensitive = [row["path"] for row in manifest["files"] if _is_sensitive_name(row["path"])]
    if sensitive and not sensitive_data_acknowledged and mode in ("read_only", "safe_copy", "in_place"):
        raise Refusal(
            "Sensitive-named files are present ({0}). Content access requires "
            "explicit path-specific authorization.".format(", ".join(sensitive[:5])),
            code="SENSITIVE_UNACKNOWLEDGED",
            repairs=[
                "Acknowledge with --sensitive-acknowledged after confirming the files may be read.",
                "Use metadata-only mode instead.",
                "Remove or relocate the sensitive files first.",
            ],
        )
    permissions = consent_defaults(mode)
    permissions["network"] = bool(network)
    permissions["external_directory"] = bool(external_directory)
    if copy is not None:
        permissions["copy"] = bool(copy)
    record = {
        "schema": CONSENT_SCHEMA,
        "workspace_id": "ws-" + manifest["root_sha256"][:16],
        "project_root_hash": manifest["root_sha256"],
        "mode": mode,
        "permissions": permissions,
        "allowed_paths": [str(item) for item in allowed_paths],
        "denied_paths": [str(item) for item in denied_paths],
        "cloud_sync_acknowledged": bool(cloud_sync_acknowledged),
        "sensitive_data_acknowledged": bool(sensitive_data_acknowledged),
        "created_at_utc": _consent_timestamp(),
        "review_at_utc": None if review_after_days is None else _days_from_now(review_after_days),
        "confirmation": confirmation,
    }
    record_bytes = canonical_json(record)
    record_sha = sha256_text(record_bytes)
    paths = paths_for(root_path)
    consent_dir = guard_path(root_path, paths.state / "consent")
    consent_dir.mkdir(parents=True, exist_ok=True)
    target = guard_path(root_path, consent_dir / ("consent-" + record_sha + ".json"))
    created = False
    if not target.exists():
        atomic_write_json(target, record, pretty=False)
        created = True
        _append_ledger(root_path, "consent.created", {
            "record_sha256": record_sha, "mode": mode, "workspace_id": record["workspace_id"],
        })
    return {
        "workspace_id": record["workspace_id"],
        "record_sha256": record_sha,
        "mode": mode,
        "created": created,
        "path": str(target),
    }


def _consent_timestamp() -> str:
    from datetime import datetime, timezone

    return (
        datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    )


def _days_from_now(days: int) -> str:
    from datetime import datetime, timedelta, timezone

    return (
        (datetime.now(timezone.utc) + timedelta(days=max(0, int(days))))
        .isoformat()
        .replace("+00:00", "Z")
    )


def _append_ledger(root: Path, event: str, details: Mapping[str, Any]) -> None:
    from .core import append_ledger

    append_ledger(root, event, dict(details))


def consent_status(root: Union[Path, str]) -> Dict[str, Any]:
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    consent_dir = guard_path(root_path, paths.state / "consent")
    if not consent_dir.is_dir():
        return {"exists": False, "records": 0}
    records: List[Dict[str, Any]] = []
    for record_path in sorted(consent_dir.glob("consent-*.json")):
        try:
            import json

            record = json.loads(record_path.read_text(encoding="utf-8"))
            record["record_sha256"] = record_path.name[len("consent-"):-len(".json")]
            records.append(record)
        except (OSError, ValueError):
            continue
    records.sort(key=lambda record: str(record.get("created_at_utc", "")))
    latest = records[-1] if records else None
    return {"exists": bool(latest), "records": len(records), "latest": latest}


def _require_consent(root_path: Path, modes: Sequence[str]) -> Dict[str, Any]:
    status = consent_status(root_path)
    latest = status.get("latest")
    if not latest or latest.get("mode") not in modes:
        raise Refusal(
            "No consent record permits this mode ({0}).".format(" or ".join(modes)),
            code="CONSENT_REQUIRED",
            repairs=[
                "Run `uriel consent set --mode {0} --confirm explicit_user` "
                "after reviewing the permission table.".format(modes[0]),
                "Review the recorded permissions: `uriel consent status`.",
            ],
        )
    return latest  # type: ignore[return-value]


def _render_ai_entry(root_path: Path, onboarding: Mapping[str, Any], consent: Mapping[str, Any]) -> str:
    paths = paths_for(root_path)
    current_state = paths.manifests / "current.json"
    return """# Uriel AI entry

Read the machine-readable workspace state before acting.

## Workspace identity

- workspace id: {workspace_id}
- project type: {entry_kind}
- current mode: {mode}
- allowed root: {root}
- output root: {output_root}
- consent record: {consent_sha}
- source generation: {source_generation}
- data-readiness state: {data_readiness}
- publication-authority state: {publication_authority}
- current lifecycle state: {lifecycle_state}

## Authority

You may propose explanations, plans, code, repairs, and drafts.

You may not:

- mark Data Readiness PASS;
- change publication authority;
- mark a Blessing gate PASS;
- issue a Blessing;
- invent evidence, data, citations, experiments, approvals, or venue rules;
- claim to have read inaccessible files.

## Files

- must read: {required}
- may read: {allowed}
- must not read: {denied}

## Boundaries

- tools allowed: read, glob, grep, question, skill
- network allowed: {network}
- write permissions: {write}
- current task: {task}
- completion conditions: {conditions}
- exact output files: {outputs}

## Default behavior

1. State which required files you can access. Report any file you cannot read.
2. Identify the current workspace mode.
3. Perform all nonblocked work.
4. {handoff}
5. Do not ask whether to continue between ordinary steps.
6. Keep observations, inferences, unknowns, and proposals separate.
7. Before Data Readiness passes, do not offer positive or negative conclusions.
8. Remain inside the allowed root. Do not access external directories,
   secrets, credentials, links, or network resources unless the consent
   record explicitly allows the specific action.
""".format(
        workspace_id=onboarding.get("workspace_id", ""),
        entry_kind=onboarding.get("entry_kind", ""),
        mode=onboarding.get("mode", ""),
        root=str(root_path),
        output_root=onboarding.get("output_root") or "none",
        consent_sha=onboarding.get("consent_record_sha256", ""),
        source_generation=onboarding.get("source_generation") or "none",
        data_readiness=onboarding.get("data_readiness", "not_started"),
        publication_authority=onboarding.get("publication_authority", "none"),
        lifecycle_state=onboarding.get("lifecycle_state", "onboarding"),
        required=", ".join(onboarding.get("files_required", [])) or "URIEL_AI_ENTRY.md, uriel.project.json",
        allowed=", ".join(onboarding.get("files_allowed", [])) or ".uriel/ (state and receipts)",
        denied=", ".join(onboarding.get("files_denied", [])) or "secrets, credentials, external directories",
        network="yes" if consent.get("permissions", {}).get("network") else "no",
        write="yes" if consent.get("permissions", {}).get("write") else "no",
        task=onboarding.get("current_task") or "none recorded",
        conditions=", ".join(onboarding.get("completion_conditions", [])) or "none recorded",
        outputs=", ".join(onboarding.get("output_files", [])) or "NEXT_PROMPT.txt",
        handoff=HANDOFF_PHRASE,
    )


def start(
    root: Union[Path, str],
    kind: Optional[str] = None,
    *,
    current_task: str = "",
    completion_conditions: Sequence[str] = (),
    title: str = "",
    question: str = "",
    privacy: str = "public",
    force: bool = False,
) -> Dict[str, Any]:
    """Scaffold a Uriel workspace: entry files, consent, and onboarding state.

    Classification is a proposal, never authority: an explicit --kind is
    required unless the workspace already carries Uriel state.
    """
    root_path = Path(root).expanduser()
    if not root_path.is_absolute():
        root_path = Path.cwd() / root_path
    root_path = Path(os.path.abspath(str(root_path)))
    root_path.mkdir(parents=True, exist_ok=True)
    root_path = canonical_root(root_path)
    has_state = (root_path / STATE_DIR_NAME).is_dir()
    if kind is None:
        if has_state:
            kind = "resume"
        else:
            raise Refusal(
                "Uriel does not infer the starting situation from file contents.",
                code="ENTRY_KIND_REQUIRED",
                repairs=["Pass --kind one of: " + ", ".join(ENTRY_KINDS)],
            )
    if kind not in ENTRY_KINDS:
        raise Refusal("Unknown entry kind.", code="INVALID_ENTRY_KIND",
                      repairs=["Choose one of: " + ", ".join(ENTRY_KINDS)])
    if kind == "new_idea":
        from .core import initialize_project

        initialize_project(root_path, title=title or "Untitled research question",
                           question=question, privacy=privacy, force=force)
    elif not has_state and kind != "read_only_review":
        from .core import initialize_project

        initialize_project(root_path, title=title or "Untitled research question",
                           question=question, privacy=privacy, force=force)
    for name in ENTRY_FILE_NAMES:
        candidate = root_path / name
        if candidate.exists() and not force:
            raise Refusal(
                "Entry file already exists: {0}. Uriel will not overwrite it.".format(name),
                code="ENTRY_FILE_EXISTS",
                repairs=[
                    "Run with --force only after reviewing the existing file.",
                    "Work in a fresh directory for a new workspace.",
                ],
            )
    probe = preflight(root_path)
    from .data_readiness import data_readiness_state

    readiness = data_readiness_state(root_path)
    consent = consent_set(
        root_path,
        "read_only",
        confirmation="explicit_user" if kind != "read_only_review" else "installer_default_read_only",
        cloud_sync_acknowledged=bool(probe["cloud_sync_indicators"]),
        sensitive_data_acknowledged=not bool(probe["sensitive_file_indications"]),
    )
    paths = paths_for(root_path)
    onboarding = {
        "schema": ONBOARDING_SCHEMA,
        "workspace_id": consent["workspace_id"],
        "entry_kind": kind,
        "mode": "read_only",
        "allowed_root_hash": probe["root_hash"],
        "consent_record_sha256": consent["record_sha256"],
        "created_at_utc": utc_now(),
        "output_root": str(paths.state),
        "data_readiness": readiness.get("data_readiness", "not_started"),
        "publication_authority": "none",
        "source_generation": probe["root_hash"],
        "current_task": current_task.strip(),
        "completion_conditions": [str(item) for item in completion_conditions],
        "files_required": ["URIEL_AI_ENTRY.md", "uriel.project.json"],
        "files_allowed": [".uriel/ (state and receipts)"],
        "files_denied": ["secrets, credentials, external directories"],
        "output_files": ["NEXT_PROMPT.txt"],
    }
    entry_text = _render_ai_entry(root_path, onboarding, consent)
    start_here = (
        "# Start here\n\nThis is a Uriel workspace.\n\n"
        "## What would you like to do?\n\n"
        "1. Develop a new idea\n2. Review an existing project without changing it\n"
        "3. Create a safe working copy\n4. Prepare or revise a paper\n"
        "5. Respond to an editor or reviewer\n6. Resume prior work\n\n"
        "Run `uriel start --root .` or give `COPY_THIS_TO_YOUR_AI.txt` to an AI "
        "working inside this folder.\n\n"
        "The default is read-only. No data-dependent conclusion is permitted "
        "until Data Readiness passes.\n"
    )
    copy_text = (
        "Work only inside this Uriel workspace.\n\n"
        "Read `URIEL_AI_ENTRY.md`, `uriel.project.json`, and the consent record "
        "first. Report any file you cannot access.\n\n"
        "Follow the recorded safety mode and consent. Do not read secrets, touch "
        "external directories, use the network, or edit source unless explicitly "
        "authorized. Complete every nonblocked task. {handoff}\n\n"
        "Do not offer a data-dependent prediction or conclusion until the exact "
        "data generation has a valid Data Readiness Receipt. You may propose "
        "repairs and drafts. You may not mark data ready, change publication "
        "authority, pass a Blessing gate, or issue a Blessing.\n"
    ).format(handoff=HANDOFF_PHRASE)
    agents_text = (
        "# Uriel workspace instructions\n\n"
        "The authoritative AI orientation is `URIEL_AI_ENTRY.md`.\n\n"
        "All agents must:\n\n"
        "- remain inside the authorized workspace root;\n"
        "- honor `.uriel` consent and state records;\n"
        "- treat read-only as no writes;\n"
        "- deny external-directory and secret access by default;\n"
        "- avoid network access unless explicitly authorized;\n"
        "- block data interpretation until Data Readiness passes;\n"
        "- distinguish observed facts, inferences, unknowns, and proposals;\n"
        "- never change publication authority or Blessing state;\n"
        "- preserve exact next-step instructions.\n"
    )
    next_prompt_text = (
        "Read URIEL_AI_ENTRY.md and review the latest output from `uriel audit` or `uriel workbench`. "
        "Complete the next safe research or repair step without changing authoritative state boundaries.\n"
    )
    written = {
        "URIEL_START_HERE.md": start_here,
        "URIEL_AI_ENTRY.md": entry_text,
        "COPY_THIS_TO_YOUR_AI.txt": copy_text,
        "NEXT_PROMPT.txt": next_prompt_text,
        "AGENTS.md": agents_text,
    }
    for name, text in written.items():
        atomic_write(root_path / name, text)
    atomic_write_json(paths.state / "onboarding.json", onboarding)
    _append_ledger(root_path, "workspace.onboarded", {
        "workspace_id": onboarding["workspace_id"],
        "entry_kind": kind,
        "consent_sha256": consent["record_sha256"],
    })
    return {
        "workspace_id": onboarding["workspace_id"],
        "entry_kind": kind,
        "mode": "read_only",
        "consent_sha256": consent["record_sha256"],
        "files_written": sorted(list(written)),
    }


def review_workspace(root: Union[Path, str], output: Optional[Union[Path, str]] = None) -> Dict[str, Any]:
    """Create or refresh a read-only review workspace outside the source root."""
    root_path = canonical_root(root)
    _require_consent(root_path, ("read_only", "safe_copy", "in_place"))
    probe = preflight(root_path)
    if output is None:
        output = root_path.parent / (root_path.name + "-uriel-review-" + uuid.uuid4().hex[:8])
    output_path = Path(output).expanduser()
    if not output_path.is_absolute():
        output_path = Path.cwd() / output_path
    output_path = Path(os.path.abspath(str(output_path)))
    if output_path == root_path or root_path in output_path.parents or output_path in root_path.parents:
        raise Refusal("The review workspace must live outside the source root.",
                      code="REVIEW_WORKSPACE_INSIDE_ROOT",
                      repairs=["Choose a directory outside the project, e.g. ~/Documents/Uriel/Reviews/."])
    output_path.mkdir(parents=True, exist_ok=True)
    head = (
        "# {0}\n\nGenerated by `uriel workspace review` from metadata only.\n"
        "Source root: `{1}`\nSource generation: `{2}`\n"
        "This workspace is separate from the source root; the source was not modified.\n\n"
    ).format(output_path.name, root_path, probe["root_hash"])
    files = {
        "PROJECT_MAP.md": head + "Inventory: {0} files, {1} bytes, VCS: {2}\n".format(
            probe["file_count"], probe["byte_count"], ", ".join(probe["detected_vcs"]) or "none"
        ) + "Links/reparse points recorded: {0}\n".format(len(probe["link_paths"])),
        "FINDINGS.md": head + "No content was read. Findings require a permitted review pass.\n",
        "GAP_REGISTER.csv": "path,kind,note\n" + "".join(
            "{0},link,recorded-not-followed\n".format(path) for path in probe["link_paths"]
        ),
        "DATA_READINESS_PLAN.md": head + "Data Readiness has not started. No receipt exists.\n",
        "REPAIR_OR_INTEGRATION_PLAN.md": head + "No plan yet. Proposals belong here after a permitted review.\n",
        "NEXT_PROMPT.txt": "Continue the review in the separate review workspace {0}.\n{1}\n".format(
            output_path, HANDOFF_PHRASE
        ),
    }
    for name, text in files.items():
        target = guard_path(output_path, output_path / name)
        if not target.exists():
            atomic_write(target, text)
    digest = sha256_text(canonical_json({name: files[name] for name in sorted(files)}))
    return {
        "review_workspace": str(output_path),
        "files": sorted(files),
        "workspace_sha256": digest,
        "source_generation": probe["root_hash"],
    }


def safe_copy(root: Union[Path, str], destination: Optional[Union[Path, str]] = None) -> Dict[str, Any]:
    """Mode B: build a uniquely named working copy; never touch the original."""
    root_path = canonical_root(root)
    consent = _require_consent(root_path, ("safe_copy", "in_place"))
    before = directory_manifest(root_path)
    if destination is None:
        destination = root_path.parent / (
            root_path.name + "-uriel-copy-" + before["root_sha256"][:8]
        )
    destination_path = Path(destination).expanduser()
    if not destination_path.is_absolute():
        destination_path = Path.cwd() / destination_path
    destination_path = Path(os.path.abspath(str(destination_path)))
    if destination_path == root_path or root_path in destination_path.parents or destination_path in root_path.parents:
        raise Refusal("The safe copy must live outside the source root.",
                      code="SAFE_COPY_INSIDE_ROOT",
                      repairs=["Choose a directory outside the project."])
    if destination_path.exists():
        raise Refusal("Destination already exists; Uriel will not overwrite it.",
                      code="SAFE_COPY_EXISTS",
                      repairs=["Remove it after review, or pass a new --destination."])
    exclusions = [
        {"path": path, "reason": "link_or_reparse_recorded_not_followed"}
        for path in before["link_paths"]
    ]
    destination_path.mkdir(parents=True, exist_ok=True)
    copied: List[str] = []
    for row in before["files"]:
        source = guard_path(root_path, root_path / row["path"], must_exist=True)
        target = guard_path(destination_path, destination_path / row["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(source, "rb") as source_handle, open(target, "wb") as target_handle:
                while True:
                    chunk = source_handle.read(1 << 20)
                    if not chunk:
                        break
                    target_handle.write(chunk)
        except OSError as exc:
            exclusions.append({"path": row["path"], "reason": "copy_failed: " + str(exc)})
            continue
        copied.append(row["path"])
    after = directory_manifest(root_path)
    same_generation = after["root_sha256"] == before["root_sha256"]
    copy_files = sorted(copied)
    copy_manifest = {
        "schema": COPY_RECEIPT_SCHEMA,
        "source_root_hash": before["root_sha256"],
        "destination": str(destination_path),
        "files": copy_files,
        "exclusions": exclusions,
        "duplicates_deterministic": True,
        "generation": sha256_text(canonical_json({"files": copy_files, "exclusions": exclusions})),
        "created_at_utc": utc_now(),
    }
    receipt = {
        "schema": INVARIANCE_SCHEMA,
        "original_manifest_before": before["root_sha256"],
        "original_manifest_after": after["root_sha256"],
        "same_original_generation": same_generation,
        "copy_destination": str(destination_path),
        "copy_manifest_sha256": copy_manifest["generation"],
        "rollback_path": str(destination_path),
        "consent_sha256": consent.get("record_sha256", "") if isinstance(consent, Mapping) else "",
        "verified_at_utc": utc_now(),
    }
    atomic_write_json(destination_path / "URIEL_COPY_MANIFEST.json", copy_manifest)
    atomic_write_json(destination_path / "ORIGINAL_INVARIANCE.json", receipt)
    _append_ledger(root_path, "workspace.safe_copy", {
        "destination": str(destination_path),
        "source_generation": before["root_sha256"],
        "same_original_generation": same_generation,
    })
    return {
        "destination": str(destination_path),
        "files_copied": len(copy_files),
        "exclusions": exclusions,
        "same_original_generation": same_generation,
        "copy_manifest_sha256": copy_manifest["generation"],
        "receipt": receipt,
    }


def inplace_dryrun(root: Union[Path, str]) -> Dict[str, Any]:
    """Mode C dry run: plan only, no source writes. Requires in-place consent."""
    root_path = canonical_root(root)
    consent = _require_consent(root_path, ("in_place",))
    manifest = directory_manifest(root_path)
    paths = paths_for(root_path)
    inplace_dir = guard_path(root_path, paths.state / "inplace")
    inplace_dir.mkdir(parents=True, exist_ok=True)
    plan = {
        "schema": INPLACE_PLAN_SCHEMA,
        "source_generation": manifest["root_sha256"],
        "proposed_files": [],
        "dry_run": True,
        "consent_sha256": consent.get("record_sha256", "") if isinstance(consent, Mapping) else "",
        "rollback_instructions": [
            "No source write has occurred; the dry run only records the plan.",
            "Before any write: snapshot the generation above and keep a backup.",
            "After any write: run `uriel workspace inplace-verify`; it stops on change.",
        ],
        "created_at_utc": utc_now(),
    }
    plan_path = guard_path(inplace_dir, inplace_dir / "plan-{0}.json".format(manifest["root_sha256"][:8]))
    if not plan_path.exists():
        atomic_write_json(plan_path, plan)
    return {
        "plan": plan,
        "path": str(plan_path),
        "note": "Proposed file set is empty until a permitted review names files; no write occurred.",
    }


def inplace_verify(root: Union[Path, str]) -> Dict[str, Any]:
    """Post-change verification: stop if the source generation moved unexpectedly."""
    root_path = canonical_root(root)
    _require_consent(root_path, ("in_place",))
    manifest = directory_manifest(root_path)
    paths = paths_for(root_path)
    inplace_dir = guard_path(root_path, paths.state / "inplace")
    plans = sorted(inplace_dir.glob("plan-*.json")) if inplace_dir.is_dir() else []
    if not plans:
        raise Refusal("No in-place plan exists; run `uriel workspace inplace-dryrun` first.",
                      code="INPLACE_PLAN_MISSING")
    import json

    plan = json.loads(plans[-1].read_text(encoding="utf-8"))
    planned_generation = str(plan.get("source_generation", ""))
    unchanged = planned_generation == manifest["root_sha256"]
    if not unchanged:
        raise Refusal(
            "The source generation changed since the in-place plan was recorded.",
            code="INPLACE_SOURCE_CHANGED",
            repairs=[
                "Stop. Reconcile the unexpected change before continuing.",
                "Record a new in-place plan after review.",
            ],
        )
    return {
        "unchanged": True,
        "source_generation": manifest["root_sha256"],
        "plan": str(plans[-1]),
        "verified_at_utc": utc_now(),
    }
