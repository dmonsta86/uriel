"""Offline-first project runtime, provenance ledger, and confinement utilities.

Uriel deliberately keeps its trusted core in the Python standard library.  It
can inventory a research project, execute an explicit workload without a
shell, write atomic receipts, maintain a hash-chained ledger, and preserve
constructive reminders for findings that block an audit gate.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import platform
import re
import shlex
import sqlite3
import stat
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, MutableMapping, Optional, Sequence, Tuple, Union

PACKAGE_VERSION = "1.0.0"
PROJECT_SCHEMA = "uriel.project.v1"
CONFIG_SCHEMA = "uriel.config.v1"
MANIFEST_SCHEMA = "uriel.source_manifest.v1"
RECEIPT_SCHEMA = "uriel.execution_receipt.v1"
LEDGER_SCHEMA = "uriel.ledger_event.v1"
REMINDER_SCHEMA = "uriel.reminder.v1"
STATE_DIR_NAME = ".uriel"
PROJECT_FILE_NAME = "uriel.project.json"

DEFAULT_IGNORES = {
    ".git",
    STATE_DIR_NAME,
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "__pycache__",
    "build",
    "dist",
}


class UrielError(RuntimeError):
    """Base class for expected Uriel failures."""


class Refusal(UrielError):
    """A fail-closed decision with a constructive explanation."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "URIEL_REFUSAL",
        gate: Optional[str] = None,
        details: Optional[Mapping[str, Any]] = None,
        repairs: Optional[Sequence[str]] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.gate = gate
        self.details = dict(details or {})
        options = list(repairs or [])
        while len(options) < 3:
            options.append(
                (
                    "Document the missing fact or artifact, rerun the relevant check, "
                    "and keep the resulting receipt with the project."
                )
            )
        self.repairs = options[:3]

    def as_dict(self) -> Dict[str, Any]:
        return {
            "code": self.code,
            "gate": self.gate,
            "message": str(self),
            "details": self.details,
            "repairs": self.repairs,
        }


class IntegrityError(Refusal):
    """Raised when a recorded digest, ledger link, or receipt no longer verifies."""


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    project: Path
    state: Path
    config: Path
    ledger: Path
    index: Path
    manifests: Path
    receipts: Path
    audits: Path
    blessings: Path
    reminders: Path
    prompts: Path


def utc_now() -> str:
    return (
        _dt.datetime.now(_dt.timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"


def canonical_json_bytes(value: Any) -> bytes:
    return canonical_json(value).encode("utf-8")


def pretty_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{token}")
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    temporary = path.with_name(f".{path.name}.tmp.{os.getpid()}.{token}")
    try:
        with temporary.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(str(temporary), str(path))
    finally:
        if temporary.exists():
            temporary.unlink()


def atomic_write_text(path: Path, data: str) -> None:
    atomic_write(path, data)


def atomic_write_json(path: Path, value: Any, *, pretty: bool = True) -> None:
    atomic_write(path, pretty_json(value) if pretty else canonical_json(value))


def read_json(path: Path) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise Refusal(
            f"Required file is missing: {path.name}",
            code="MISSING_FILE",
            repairs=[
                f"Restore or create {path.name} inside the project root.",
                "Run `uriel init` in a new directory and compare the generated structure.",
                "Recover the file from version control or a verified backup, then rerun the command.",
            ],
        ) from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise Refusal(
            f"Uriel could not read valid JSON from {path.name}.",
            code="INVALID_JSON",
            details={"path": str(path), "error": str(exc)},
            repairs=[
                f"Validate {path.name} with a JSON parser and correct the first syntax error.",
                "Compare the file with `schemas/uriel.project.v1.schema.json`.",
                "Restore the most recent valid version from source control and reapply changes carefully.",
            ],
        ) from exc
    if not isinstance(value, dict):
        raise Refusal(
            f"{path.name} must contain one JSON object at its top level.",
            code="JSON_OBJECT_REQUIRED",
        )
    return value


load_json_object = read_json


def _path_key(path: Path) -> str:
    value = str(path)
    if os.name == "nt":
        value = value.replace("/", "\\").casefold()
    return value


def is_reparse_or_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        info = path.stat()
        flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return bool(getattr(info, "st_file_attributes", 0) & flag)
    except FileNotFoundError:
        return False


def canonical_root(root: Union[Path, str]) -> Path:
    raw = Path(root).expanduser()
    if not raw.is_absolute():
        raw = Path.cwd() / raw
    raw = Path(os.path.abspath(str(raw)))
    if not raw.exists():
        raise Refusal(
            f"Project root does not exist: {raw}",
            code="ROOT_MISSING",
            repairs=[
                "Create the directory, then run `uriel init <directory>`.",
                "Choose an existing project directory and pass it with `--root`.",
                "Correct any spelling or drive-letter mistake in the path.",
            ],
        )
    if not raw.is_dir():
        raise Refusal("Project root must be a directory.", code="ROOT_NOT_DIRECTORY")
    if is_reparse_or_link(raw):
        raise Refusal(
            "Uriel will not use a symlink or reparse point as the project root.",
            code="ROOT_LINK_REFUSED",
            repairs=[
                "Use the real directory path rather than a symlink or junction.",
                "Copy the project into a normal local directory and initialize it there.",
                "Document the storage layout, remove the redirecting link, and retry.",
            ],
        )
    return raw.resolve(strict=True)


def guard_path(root: Union[Path, str], candidate: Union[Path, str], *, must_exist: bool = False) -> Path:
    """Return a confined path, refusing traversal, links, junctions, and volume escapes."""

    root_path = canonical_root(root)
    raw = Path(candidate)
    if not raw.is_absolute():
        raw = root_path / raw
    raw = Path(os.path.abspath(str(raw)))

    try:
        raw_common = os.path.commonpath([str(root_path), str(raw)])
    except ValueError as exc:
        raise Refusal("The path is on a different volume.", code="PATH_VOLUME_ESCAPE") from exc
    if _path_key(Path(raw_common)) != _path_key(root_path):
        raise Refusal(
            "Uriel refused a path outside the project root.",
            code="PATH_CONFINEMENT_REFUSAL",
            details={"candidate": str(raw), "root": str(root_path)},
            repairs=[
                "Move the file or output beneath the project root.",
                "Use a project-relative path without `..` components.",
                "Create an explicit, hashed copy inside `artifacts/` and reference that copy.",
            ],
        )

    try:
        relative = raw.relative_to(root_path)
    except ValueError as exc:
        raise Refusal("Uriel refused a path outside the project root.", code="PATH_CONFINEMENT_REFUSAL") from exc

    current = root_path
    for part in relative.parts:
        current = current / part
        if current.exists() and is_reparse_or_link(current):
            raise Refusal(
                "Uriel refused a symlink, junction, or reparse point inside the project.",
                code="LINK_TRAVERSAL_REFUSAL",
                details={"path": str(current)},
                repairs=[
                    "Replace the link with a real project-local file or directory.",
                    "Copy the referenced artifact into `artifacts/` and hash the copy.",
                    "Remove the link from the audited source set and document why it was excluded.",
                ],
            )

    try:
        resolved = raw.resolve(strict=must_exist)
    except FileNotFoundError as exc:
        raise Refusal(
            f"Project-local path is missing: {raw.name}",
            code="PROJECT_PATH_MISSING",
            details={"path": str(raw)},
        ) from exc
    try:
        common = os.path.commonpath([str(root_path), str(resolved)])
    except ValueError as exc:
        raise Refusal("The resolved path is on a different volume.", code="PATH_VOLUME_ESCAPE") from exc
    if _path_key(Path(common)) != _path_key(root_path):
        raise Refusal(
            "Uriel refused a resolved path outside the project root.",
            code="PATH_CONFINEMENT_REFUSAL",
            details={"candidate": str(raw), "resolved": str(resolved)},
        )
    return resolved


def safe_relative_path(name: str) -> Path:
    candidate = Path(name)
    if not name or candidate.is_absolute() or ".." in candidate.parts or ":" in name:
        raise Refusal("A safe project-relative path is required.", code="INVALID_RELATIVE_PATH")
    return candidate


def paths_for(root: Union[Path, str], *, require_project: bool = True) -> ProjectPaths:
    root_path = canonical_root(root)
    state = root_path / STATE_DIR_NAME
    project = root_path / PROJECT_FILE_NAME
    if require_project and not project.is_file():
        raise Refusal(
            f"{PROJECT_FILE_NAME} was not found in {root_path}.",
            code="PROJECT_NOT_INITIALIZED",
            repairs=[
                f"Run `uriel init {shlex.quote(str(root_path))}` to initialize this directory.",
                "Pass `--root` with the directory that already contains `uriel.project.json`.",
                "Restore the project file from version control and rerun the command.",
            ],
        )
    return ProjectPaths(
        root=root_path,
        project=project,
        state=state,
        config=state / "config.json",
        ledger=state / "ledger.jsonl",
        index=state / "index" / "files.sqlite",
        manifests=state / "manifests",
        receipts=state / "receipts",
        audits=state / "audits",
        blessings=state / "blessings",
        reminders=state / "reminders",
        prompts=state / "prompts",
    )


def _default_project(title: str, question: str, privacy: str) -> Dict[str, Any]:
    """Return a deliberately unfinished, non-judgmental research workspace.

    Empty fields are invitations to specify the idea, not evidence that the
    underlying question is bad.  The audit mentor explains what is missing and
    never treats writing polish, credentials, or age as a quality signal.
    """

    return {
        "schema": PROJECT_SCHEMA,
        "schema_version": 1,
        "project_id": str(uuid.uuid4()),
        "title": title.strip() or "Untitled research question",
        "kind": "research",
        "question": question.strip(),
        "hypothesis": {
            "statement": "",
            "falsifier": "",
            "operational_definitions": {},
            "success_criteria": [],
        },
        "framing_review": {
            "neutral_restatement": question.strip(),
            "competing_frames": [],
            "loaded_terms_reviewed": [],
            "scope_boundaries": [],
        },
        "novelty_review": {
            "status": "not_started",
            "search_date": "",
            "databases": [],
            "queries": [],
            "nearest_prior_work": [],
            "differentiators": [],
            "negative_searches": [],
            "scope_limitations": [],
        },
        "claims": [
            {
                "id": "C1",
                "statement": "",
                "type": "empirical",
                "importance": "major",
                "scope": {"population": "", "setting": "", "timeframe": ""},
                "falsifier": "",
                "reasoning": "",
                "evidence_ids": [],
                "counterevidence_ids": [],
                "assumption_ids": [],
                "adversarial_test_ids": [],
                "reconciliation": "",
            }
        ],
        "evidence": [],
        "methods": {
            "design": "",
            "population": "",
            "sampling": "",
            "sample_size": None,
            "analysis_plan": "",
            "effect_size_metric": "",
            "uncertainty_method": "",
            "causal_identification": "",
            "controls": [],
            "exclusions": [],
            "missing_data_plan": "",
            "preregistration": "",
            "reproducibility_command": "",
        },
        "assumptions": [],
        "alternative_explanations": [],
        "contradictions": [],
        "adversarial_tests": [],
        "reviewer_objections": [],
        "limitations": [],
        "ethics": {"review_status": "not_applicable", "risks": [], "mitigations": []},
        "disclosures": {
            "funding": [],
            "conflicts": [],
            "known_counterevidence": [],
            "omitted_data": [],
            "negative_results": [],
            "attestations": {
                "all_known_material_data_declared": False,
                "null_and_negative_results_declared": False,
                "citations_checked_against_sources": False,
                "no_claim_relies_only_on_another_authors_conclusion": False,
            },
        },
        "submission": {
            "field": "",
            "article_type": "research article",
            "target_venues": [],
            "author_names": [],
            "corresponding_author": "",
            "data_availability": "",
            "code_availability": "",
        },
        "privacy": {
            "classification": privacy,
            "external_ai": "ask",
            "redaction_notes": [],
        },
        "workloads": [],
        "external_reviews": [],
        "waivers": [],
    }


def initialize_project(
    root: Union[Path, str],
    *,
    title: str,
    question: str,
    privacy: str = "public",
    force: bool = False,
) -> Dict[str, Any]:
    root_path = Path(root).expanduser()
    if not root_path.is_absolute():
        root_path = Path.cwd() / root_path
    root_path.mkdir(parents=True, exist_ok=True)
    root_path = canonical_root(root_path)
    project_path = root_path / PROJECT_FILE_NAME
    if project_path.exists() and not force:
        raise Refusal(
            f"{PROJECT_FILE_NAME} already exists; Uriel will not overwrite it silently.",
            code="PROJECT_ALREADY_EXISTS",
            repairs=[
                "Use the existing project and run `uriel status`.",
                "Create a new empty directory for a separate research question.",
                "Use `--force` only after committing or backing up the existing project file.",
            ],
        )
    if privacy not in {"public", "internal", "confidential", "restricted"}:
        raise Refusal("Unknown privacy classification.", code="INVALID_PRIVACY_CLASSIFICATION")

    project = _default_project(title, question, privacy)
    atomic_write_json(project_path, project)
    paths = paths_for(root_path)
    for directory in (
        paths.state,
        paths.index.parent,
        paths.manifests,
        paths.receipts,
        paths.audits,
        paths.blessings,
        paths.reminders,
        paths.prompts,
        root_path / "artifacts",
        root_path / "sources",
    ):
        guard_path(root_path, directory)
        directory.mkdir(parents=True, exist_ok=True)

    gitignore = root_path / ".gitignore"
    if gitignore.exists():
        existing_ignore = gitignore.read_text(encoding="utf-8")
        if ".uriel/" not in existing_ignore.splitlines():
            atomic_write(gitignore, existing_ignore.rstrip() + "\n.uriel/\n")
    else:
        atomic_write(gitignore, ".uriel/\n__pycache__/\n*.pyc\n")
    start_here = root_path / "URIEL-START-HERE.md"
    if not start_here.exists():
        atomic_write(
            start_here,
            """# Start here

1. Put raw or primary-source material in `sources/` and generated evidence in `artifacts/`.
2. Edit `uriel.project.json`. Keep source extraction separate from interpretation.
3. Run `uriel audit --profile exploratory` early; a refusal is a repair plan, not a rejection of the idea.
4. Run explicit analyses with `uriel run -- COMMAND ...` to preserve content-bound receipts.
5. Use optional AI prompts only for bounded help. Verify every locator and never treat model output as evidence by itself.
6. Request `uriel blessing` only after a submission-profile audit passes all Three Gates.

The local `.uriel/REMINDERS.md` file keeps unresolved findings easy to revisit.
""",
        )
    for directory_name, message in (
        ("sources", "Store permitted primary-source excerpts, source records, and access notes here.\n"),
        ("artifacts", "Store data, code outputs, figures, and other claim-bearing artifacts here.\n"),
    ):
        readme = root_path / directory_name / "README.md"
        if not readme.exists():
            atomic_write(readme, "# {0}\n\n{1}".format(directory_name.title(), message))

    config = {
        "schema": CONFIG_SCHEMA,
        "schema_version": 1,
        "project_id": project["project_id"],
        "allowed_root_sha256": sha256_text(_path_key(root_path)),
        "created_at_utc": utc_now(),
        "engine_version": PACKAGE_VERSION,
        "offline_first": True,
        "network_access": "disabled_by_core",
    }
    atomic_write_json(paths.config, config)
    if not paths.ledger.exists():
        atomic_write(paths.ledger, "")
    append_ledger(
        root_path,
        "project.initialized",
        {
            "project_sha256": sha256_file(project_path),
            "title": project["title"],
            "privacy": privacy,
        },
    )
    return {
        "project_id": project["project_id"],
        "root": str(root_path),
        "project_file": PROJECT_FILE_NAME,
        "state_dir": STATE_DIR_NAME,
        "next": [
            "Edit uriel.project.json using the field guide in URIEL-START-HERE.md.",
            "Run `uriel audit --profile exploratory` to receive a gate-by-gate research plan.",
            "Run `uriel prompt clarity --provider generic` for an optional, privacy-aware review prompt.",
        ],
    }


def load_config(root: Union[Path, str]) -> Dict[str, Any]:
    paths = paths_for(root)
    config = read_json(guard_path(paths.root, paths.config, must_exist=True))
    if config.get("schema") != CONFIG_SCHEMA:
        raise Refusal("Uriel configuration schema mismatch.", code="CONFIG_SCHEMA_MISMATCH")
    expected = sha256_text(_path_key(paths.root))
    if config.get("allowed_root_sha256") != expected:
        raise Refusal(
            "The Uriel state is bound to a different project root.",
            code="ROOT_BINDING_MISMATCH",
            repairs=[
                "Move the project back to its initialized path.",
                "Create a fresh Uriel project at the new path and copy only source artifacts into it.",
                "Remove `.uriel` after making a backup, then run `uriel init --force` to establish a new root binding.",
            ],
        )
    return config


def load_project(root: Union[Path, str]) -> Dict[str, Any]:
    paths = paths_for(root)
    load_config(paths.root)
    project = read_json(guard_path(paths.root, paths.project, must_exist=True))
    if project.get("schema") != PROJECT_SCHEMA:
        raise Refusal(
            "Project schema mismatch.",
            code="PROJECT_SCHEMA_MISMATCH",
            details={"expected": PROJECT_SCHEMA, "actual": project.get("schema")},
        )
    return project


def save_project(root: Union[Path, str], project: Mapping[str, Any], *, event: str, details: Mapping[str, Any]) -> None:
    paths = paths_for(root)
    if project.get("schema") != PROJECT_SCHEMA:
        raise Refusal("Refusing to write a project with an unknown schema.", code="PROJECT_SCHEMA_MISMATCH")
    atomic_write_json(paths.project, dict(project))
    append_ledger(paths.root, event, {**dict(details), "project_sha256": sha256_file(paths.project)})



def add_evidence(
    root: Union[Path, str],
    artifact_path: str,
    *,
    evidence_id: str,
    claim_ids: Sequence[str] = (),
    kind: str = "artifact",
    description: str = "",
    source_locator: str = "",
    source_type: str = "primary",
    directness: str = "direct",
    extraction: str = "",
    data_location: str = "",
    interpretation: str = "",
    limitations: str = "",
    primary: bool = True,
) -> Dict[str, Any]:
    """Hash and register one project-local evidence artifact.

    The command computes the digest locally and refuses links, absolute paths,
    parent traversal, duplicate evidence identifiers, and unknown claim IDs.
    Descriptive fields are intentionally not invented; missing analysis remains
    visible to the Gate 2 mentor.
    """

    paths = paths_for(root)
    safe = safe_relative_path(artifact_path)
    artifact = guard_path(paths.root, paths.root / safe, must_exist=True)
    if not artifact.is_file():
        raise Refusal(
            "Evidence must name a regular project-local file.",
            code="EVIDENCE_FILE_REQUIRED",
            repairs=[
                "Provide a regular file under `sources/` or `artifacts/`.",
                "Copy restricted material into a permitted redacted artifact or create a content-hashed access receipt.",
                "Remove the evidence mapping until the underlying bytes can be preserved safely.",
            ],
        )
    if is_reparse_or_link(artifact):
        raise Refusal(
            "Uriel will not register a linked evidence artifact.",
            code="EVIDENCE_LINK_REFUSAL",
            repairs=[
                "Copy the exact bytes into a regular file under the project root.",
                "Use a content-hashed access receipt when policy forbids a local copy.",
                "Keep the evidence unclaimed until an independent reviewer can reach stable bytes.",
            ],
        )
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}", evidence_id):
        raise Refusal(
            "Evidence ID must be a portable identifier.",
            code="EVIDENCE_ID_INVALID",
            details={"evidence_id": evidence_id},
        )

    project = load_project(paths.root)
    evidence_rows = project.get("evidence")
    if not isinstance(evidence_rows, list):
        raise Refusal("Project evidence must be an array.", code="PROJECT_EVIDENCE_INVALID")
    if any(isinstance(row, Mapping) and row.get("id") == evidence_id for row in evidence_rows):
        raise Refusal(
            "That evidence ID already exists; Uriel will not silently replace its provenance.",
            code="EVIDENCE_ID_EXISTS",
            details={"evidence_id": evidence_id},
            repairs=[
                "Choose a new evidence ID for a new artifact version.",
                "Edit the existing record deliberately, then rerun `uriel snapshot` and dependent workloads.",
                "Remove the old record only after preserving its history in version control or another immutable store.",
            ],
        )

    claims = project.get("claims")
    claim_map = {
        str(row.get("id")): row
        for row in claims if isinstance(row, MutableMapping) and row.get("id")
    } if isinstance(claims, list) else {}
    unknown = sorted(set(str(item) for item in claim_ids) - set(claim_map))
    if unknown:
        raise Refusal(
            "Evidence references an unknown claim ID.",
            code="EVIDENCE_UNKNOWN_CLAIM",
            details={"unknown_claim_ids": unknown},
        )

    relative = artifact.relative_to(paths.root).as_posix()
    digest = sha256_file(artifact)
    row: Dict[str, Any] = {
        "id": evidence_id,
        "kind": kind.strip() or "artifact",
        "description": description.strip(),
        "artifact_path": relative,
        "sha256": digest,
        "source_locator": source_locator.strip() or "local:" + relative,
        "source_type": source_type.strip() or "primary",
        "directness": directness.strip() or "direct",
        "primary": bool(primary),
        "extraction": extraction.strip(),
        "data_location": data_location.strip(),
        "interpretation": interpretation.strip(),
        "limitations": limitations.strip(),
        "supports_claims": list(dict.fromkeys(str(item) for item in claim_ids)),
        "counterevidence_for_claims": [],
    }
    evidence_rows.append(row)
    for claim_id in row["supports_claims"]:
        claim = claim_map[claim_id]
        linked = claim.get("evidence_ids")
        if not isinstance(linked, list):
            linked = []
            claim["evidence_ids"] = linked
        if evidence_id not in linked:
            linked.append(evidence_id)

    save_project(
        paths.root,
        project,
        event="evidence.registered",
        details={
            "evidence_id": evidence_id,
            "artifact_path": relative,
            "artifact_sha256": digest,
            "claim_ids": row["supports_claims"],
        },
    )
    manifest = build_manifest(paths.root, persist=True)
    return {
        "evidence": row,
        "source_manifest_sha256": manifest["manifest_sha256"],
        "message": (
            "The artifact digest was computed locally. Empty extraction, interpretation, or limitation fields "
            "remain visible and must be completed before Gate 2 can pass."
        ),
    }

def iter_project_files(root: Union[Path, str]) -> Iterator[Path]:
    root_path = canonical_root(root)
    for current, directories, files in os.walk(root_path, topdown=True, followlinks=False):
        current_path = Path(current)
        guard_path(root_path, current_path, must_exist=True)
        kept: List[str] = []
        for name in sorted(directories, key=str.casefold):
            child = current_path / name
            if name in DEFAULT_IGNORES:
                continue
            guard_path(root_path, child, must_exist=True)
            if is_reparse_or_link(child):
                raise Refusal(
                    "Source inventory encountered a linked directory.",
                    code="SOURCE_LINK_REFUSAL",
                    details={"path": str(child.relative_to(root_path))},
                )
            kept.append(name)
        directories[:] = kept
        for name in sorted(files, key=str.casefold):
            path = current_path / name
            guard_path(root_path, path, must_exist=True)
            if is_reparse_or_link(path):
                raise Refusal(
                    "Source inventory encountered a linked file.",
                    code="SOURCE_LINK_REFUSAL",
                    details={"path": str(path.relative_to(root_path))},
                )
            if path.is_file():
                yield path


def media_type(path: Path) -> str:
    return {
        ".json": "application/json",
        ".jsonl": "application/x-ndjson",
        ".csv": "text/csv",
        ".tsv": "text/tab-separated-values",
        ".md": "text/markdown",
        ".txt": "text/plain",
        ".py": "text/x-python",
        ".ps1": "text/x-powershell",
        ".pdf": "application/pdf",
        ".svg": "image/svg+xml",
    }.get(path.suffix.casefold(), "application/octet-stream")


def _manifest_digest(manifest: Mapping[str, Any]) -> str:
    body = dict(manifest)
    body.pop("manifest_sha256", None)
    return sha256_text(canonical_json(body))


def load_current_manifest(root: Union[Path, str]) -> Dict[str, Any]:
    paths = paths_for(root)
    pointer_path = guard_path(paths.root, paths.manifests / "current.json", must_exist=True)
    pointer = read_json(pointer_path)
    if pointer.get("schema") != "uriel.manifest_pointer.v1":
        raise IntegrityError("Source manifest pointer schema mismatch.")
    name = str(pointer.get("manifest", ""))
    if not re.fullmatch(r"[0-9a-f]{64}\.json", name):
        raise IntegrityError("Source manifest pointer contains an invalid filename.")
    manifest_path = guard_path(paths.root, paths.manifests / name, must_exist=True)
    manifest = read_json(manifest_path)
    digest = _manifest_digest(manifest)
    if digest != manifest.get("manifest_sha256"):
        raise IntegrityError("Source manifest digest mismatch.")
    if digest != pointer.get("manifest_sha256"):
        raise IntegrityError("Source manifest pointer digest mismatch.")
    if manifest.get("records_sha256") != pointer.get("records_sha256"):
        raise IntegrityError("Source manifest pointer record digest mismatch.")
    return manifest


def build_manifest(root: Union[Path, str], *, persist: bool = True) -> Dict[str, Any]:
    """Inventory every non-state project file into a deterministic manifest."""

    paths = paths_for(root)
    project = load_project(paths.root)
    records: List[Dict[str, Any]] = []
    for path in iter_project_files(paths.root):
        rel = path.relative_to(paths.root).as_posix()
        records.append(
            {
                "relative_path": rel,
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
                "media_type": media_type(path),
            }
        )
    records.sort(key=lambda item: str(item["relative_path"]).casefold())
    record_digest = sha256_text(canonical_json(records))

    # Preserve the first observation time when the exact source set is reused.
    generated_at = utc_now()
    if paths.manifests.joinpath("current.json").exists():
        try:
            prior = load_current_manifest(paths.root)
            if (
                prior.get("project_id") == project.get("project_id")
                and prior.get("records_sha256") == record_digest
                and prior.get("root_binding_sha256") == sha256_text(_path_key(paths.root))
            ):
                if persist:
                    return prior
                generated_at = str(prior.get("generated_at_utc", generated_at))
        except (Refusal, IntegrityError):
            # A damaged prior pointer must not prevent producing an in-memory
            # diagnostic, but a persisted write below will establish a new
            # pointer only after all current bytes are inventoried.
            pass

    manifest: Dict[str, Any] = {
        "schema": MANIFEST_SCHEMA,
        "schema_version": 1,
        "project_id": project.get("project_id"),
        "generated_at_utc": generated_at,
        "root_binding_sha256": sha256_text(_path_key(paths.root)),
        "record_count": len(records),
        "records_sha256": record_digest,
        "records": records,
    }
    manifest["manifest_sha256"] = _manifest_digest(manifest)
    if persist:
        destination = paths.manifests / f"{manifest['manifest_sha256']}.json"
        if destination.exists():
            existing = read_json(destination)
            if existing != manifest:
                raise IntegrityError("Immutable source manifest collision.")
        else:
            atomic_write_json(destination, manifest)
        atomic_write_json(
            paths.manifests / "current.json",
            {
                "schema": "uriel.manifest_pointer.v1",
                "manifest": destination.name,
                "manifest_sha256": manifest["manifest_sha256"],
                "records_sha256": record_digest,
            },
        )
        append_ledger(
            paths.root,
            "source.manifested",
            {
                "manifest_sha256": manifest["manifest_sha256"],
                "records_sha256": record_digest,
                "record_count": len(records),
            },
        )
    return manifest


def verify_source_manifest(
    root: Union[Path, str],
    manifest: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Verify schema, digest, membership, metadata, and every recorded byte."""

    paths = paths_for(root)
    expected = dict(manifest or load_current_manifest(paths.root))
    errors: List[Dict[str, Any]] = []
    if expected.get("schema") != MANIFEST_SCHEMA:
        errors.append({"code": "MANIFEST_SCHEMA", "message": "source manifest schema mismatch"})
    if expected.get("project_id") != load_project(paths.root).get("project_id"):
        errors.append({"code": "MANIFEST_PROJECT", "message": "source manifest project binding mismatch"})
    if expected.get("root_binding_sha256") != sha256_text(_path_key(paths.root)):
        errors.append({"code": "MANIFEST_ROOT", "message": "source manifest root binding mismatch"})
    if expected.get("manifest_sha256") != _manifest_digest(expected):
        errors.append({"code": "MANIFEST_DIGEST", "message": "source manifest digest mismatch"})

    rows = expected.get("records")
    if not isinstance(rows, list):
        rows = []
        errors.append({"code": "MANIFEST_RECORDS", "message": "source manifest records must be an array"})
    if expected.get("record_count") != len(rows):
        errors.append({"code": "MANIFEST_COUNT", "message": "source manifest record count mismatch"})
    if expected.get("records_sha256") != sha256_text(canonical_json(rows)):
        errors.append({"code": "MANIFEST_RECORD_DIGEST", "message": "source record-set digest mismatch"})

    by_path: Dict[str, Mapping[str, Any]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping):
            errors.append({"code": "MANIFEST_ROW", "message": "source record is not an object", "index": index})
            continue
        rel = str(row.get("relative_path", ""))
        try:
            safe_relative_path(rel)
        except Refusal:
            errors.append({"code": "MANIFEST_PATH", "message": "unsafe source record path", "path": rel})
            continue
        if rel in by_path:
            errors.append({"code": "MANIFEST_DUPLICATE", "message": "duplicate source record path", "path": rel})
            continue
        by_path[rel] = row

    actual_paths = {path.relative_to(paths.root).as_posix(): path for path in iter_project_files(paths.root)}
    for rel in sorted(set(by_path) - set(actual_paths)):
        errors.append({"code": "SOURCE_MISSING", "message": "recorded source file is missing", "path": rel})
    for rel in sorted(set(actual_paths) - set(by_path)):
        errors.append({"code": "SOURCE_UNEXPECTED", "message": "unrecorded source file is present", "path": rel})
    for rel in sorted(set(by_path) & set(actual_paths)):
        row = by_path[rel]
        path = actual_paths[rel]
        digest = sha256_file(path)
        if row.get("sha256") != digest:
            errors.append({"code": "SOURCE_DIGEST", "message": "source file digest mismatch", "path": rel})
        if row.get("size") != path.stat().st_size:
            errors.append({"code": "SOURCE_SIZE", "message": "source file size mismatch", "path": rel})
        if row.get("media_type") != media_type(path):
            errors.append({"code": "SOURCE_MEDIA_TYPE", "message": "source file media type mismatch", "path": rel})

    return {
        "verified": not errors,
        "manifest_sha256": expected.get("manifest_sha256"),
        "records_sha256": expected.get("records_sha256"),
        "record_count": len(rows),
        "error_count": len(errors),
        "errors": errors,
    }


def build_index(root: Union[Path, str], manifest: Optional[Mapping[str, Any]] = None) -> Dict[str, Any]:
    paths = paths_for(root)
    manifest_value = dict(manifest or build_manifest(paths.root, persist=True))
    paths.index.parent.mkdir(parents=True, exist_ok=True)
    candidate = paths.index.with_name(f".{paths.index.name}.tmp.{os.getpid()}.{uuid.uuid4().hex}")
    connection = sqlite3.connect(str(candidate))
    try:
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute(
            "CREATE TABLE files (relative_path TEXT PRIMARY KEY, sha256 TEXT NOT NULL, "
            "size INTEGER NOT NULL, media_type TEXT NOT NULL)"
        )
        connection.execute("CREATE INDEX files_sha256 ON files(sha256)")
        connection.executemany(
            "INSERT INTO files(relative_path,sha256,size,media_type) VALUES(?,?,?,?)",
            [
                (
                    str(row["relative_path"]),
                    str(row["sha256"]),
                    int(row["size"]),
                    str(row["media_type"]),
                )
                for row in manifest_value.get("records", [])
            ],
        )
        connection.execute(
            "CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.executemany(
            "INSERT INTO metadata(key,value) VALUES(?,?)",
            [
                ("manifest_sha256", str(manifest_value.get("manifest_sha256", ""))),
                ("records_sha256", str(manifest_value.get("records_sha256", ""))),
                ("created_at_utc", utc_now()),
            ],
        )
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise Refusal("SQLite integrity check failed.", code="INDEX_INTEGRITY_FAILURE")
    finally:
        connection.close()
    os.replace(str(candidate), str(paths.index))
    index_sha = sha256_file(paths.index)
    append_ledger(
        paths.root,
        "source.indexed",
        {
            "index_sha256": index_sha,
            "manifest_sha256": manifest_value.get("manifest_sha256"),
            "record_count": manifest_value.get("record_count"),
        },
    )
    return {
        "index": str(paths.index.relative_to(paths.root)),
        "index_sha256": index_sha,
        "record_count": manifest_value.get("record_count", 0),
        "manifest_sha256": manifest_value.get("manifest_sha256"),
    }


def _read_ledger_events(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    events: List[Dict[str, Any]] = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise Refusal(
                "The provenance ledger contains invalid JSON.",
                code="LEDGER_INVALID_JSON",
                details={"line": number},
            ) from exc
        if not isinstance(value, dict):
            raise Refusal("The provenance ledger contains a non-object event.", code="LEDGER_INVALID_EVENT")
        events.append(value)
    return events


def verify_ledger(root: Union[Path, str]) -> Dict[str, Any]:
    paths = paths_for(root)
    events = _read_ledger_events(paths.ledger)
    previous = "0" * 64
    for index, event in enumerate(events):
        supplied = str(event.get("event_sha256", ""))
        body = dict(event)
        body.pop("event_sha256", None)
        if body.get("schema") != LEDGER_SCHEMA:
            raise Refusal("Ledger schema mismatch.", code="LEDGER_SCHEMA_MISMATCH", details={"index": index})
        if body.get("previous_event_sha256") != previous:
            raise Refusal("Ledger chain link mismatch.", code="LEDGER_CHAIN_MISMATCH", details={"index": index})
        calculated = sha256_text(canonical_json(body))
        if supplied != calculated:
            raise Refusal("Ledger event digest mismatch.", code="LEDGER_DIGEST_MISMATCH", details={"index": index})
        previous = supplied
    return {
        "event_count": len(events),
        "head_sha256": previous,
        "verified": True,
    }


def append_ledger(root: Union[Path, str], event_type: str, payload: Mapping[str, Any]) -> Dict[str, Any]:
    paths = paths_for(root, require_project=False)
    paths.state.mkdir(parents=True, exist_ok=True)
    events = _read_ledger_events(paths.ledger)
    previous = "0" * 64
    if events:
        # Verify before extending. A damaged ledger is never silently bypassed.
        verification = verify_ledger(paths.root)
        previous = str(verification["head_sha256"])
    body: Dict[str, Any] = {
        "schema": LEDGER_SCHEMA,
        "sequence": len(events) + 1,
        "event_type": event_type,
        "created_at_utc": utc_now(),
        "previous_event_sha256": previous,
        "payload": dict(payload),
    }
    body["event_sha256"] = sha256_text(canonical_json(body))
    events.append(body)
    atomic_write(paths.ledger, "".join(canonical_json(event) for event in events))
    return body


def _slug(value: str, *, fallback: str = "item") -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", value.strip()).strip("-.").lower()
    return cleaned[:64] or fallback


def run_workload(
    root: Union[Path, str],
    command: Sequence[str],
    *,
    timeout: int = 600,
    workload_id: Optional[str] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    paths = paths_for(root)
    if not command:
        raise Refusal(
            "No workload command was provided.",
            code="WORKLOAD_MISSING",
            repairs=[
                "Run a command after `--`, for example `uriel run -- python -m pytest`.",
                "Add a workload to `uriel.project.json` and invoke it by name.",
                "Use `uriel snapshot` when you only need an artifact manifest, not code execution.",
            ],
        )
    if timeout < 1 or timeout > 86400:
        raise Refusal("Timeout must be between 1 and 86400 seconds.", code="INVALID_TIMEOUT")
    command_list = [str(part) for part in command]
    if any("\x00" in part for part in command_list):
        raise Refusal("Workload command contains a NUL byte.", code="INVALID_COMMAND")
    identifier = _slug(workload_id or Path(command_list[0]).name, fallback="workload")
    pre_manifest = build_manifest(paths.root, persist=True)
    started = utc_now()
    started_monotonic = time.monotonic()
    safe_env = os.environ.copy()
    if env:
        for key, value in env.items():
            if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
                raise Refusal("Invalid environment variable name.", code="INVALID_ENVIRONMENT")
            safe_env[key] = value
    try:
        result = subprocess.run(
            command_list,
            cwd=str(paths.root),
            env=safe_env,
            shell=False,
            capture_output=True,
            text=False,
            timeout=timeout,
            check=False,
        )
        timed_out = False
        stdout = result.stdout or b""
        stderr = result.stderr or b""
        return_code: Optional[int] = result.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        return_code = None
    duration = round(time.monotonic() - started_monotonic, 6)
    post_manifest = build_manifest(paths.root, persist=True)
    receipt_id = sha256_text(
        canonical_json(
            {
                "project_id": load_project(paths.root).get("project_id"),
                "workload_id": identifier,
                "command": command_list,
                "started_at_utc": started,
                "pre_manifest_sha256": pre_manifest["manifest_sha256"],
                "post_manifest_sha256": post_manifest["manifest_sha256"],
                "stdout_sha256": sha256_bytes(stdout),
                "stderr_sha256": sha256_bytes(stderr),
                "return_code": return_code,
                "timed_out": timed_out,
            }
        )
    )[:24]
    receipt_dir = paths.receipts / f"run-{receipt_id}"
    guard_path(paths.root, receipt_dir)
    receipt_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = receipt_dir / "stdout.bin"
    stderr_path = receipt_dir / "stderr.bin"
    stdout_path.write_bytes(stdout)
    stderr_path.write_bytes(stderr)
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "schema_version": 1,
        "receipt_id": receipt_id,
        "workload_id": identifier,
        "project_id": load_project(paths.root).get("project_id"),
        "started_at_utc": started,
        "finished_at_utc": utc_now(),
        "duration_seconds": duration,
        "command": command_list,
        "cwd": ".",
        "shell": False,
        "timeout_seconds": timeout,
        "timed_out": timed_out,
        "return_code": return_code,
        "pre_manifest_sha256": pre_manifest["manifest_sha256"],
        "post_manifest_sha256": post_manifest["manifest_sha256"],
        "pre_records_sha256": pre_manifest["records_sha256"],
        "post_records_sha256": post_manifest["records_sha256"],
        "stdout_relpath": stdout_path.relative_to(paths.root).as_posix(),
        "stdout_sha256": sha256_bytes(stdout),
        "stderr_relpath": stderr_path.relative_to(paths.root).as_posix(),
        "stderr_sha256": sha256_bytes(stderr),
        "platform": {
            "python": sys.version.split()[0],
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "status": "TIMEOUT" if timed_out else ("PASS" if return_code == 0 else "FAIL"),
    }
    receipt["receipt_sha256"] = sha256_text(canonical_json(receipt))
    atomic_write_json(receipt_dir / "receipt.json", receipt)
    append_ledger(
        paths.root,
        "workload.executed",
        {
            "receipt_id": receipt_id,
            "receipt_sha256": receipt["receipt_sha256"],
            "status": receipt["status"],
            "return_code": return_code,
        },
    )
    return receipt


def latest_receipts(root: Union[Path, str]) -> List[Dict[str, Any]]:
    paths = paths_for(root)
    output: List[Dict[str, Any]] = []
    for receipt_path in sorted(paths.receipts.glob("run-*/receipt.json"), key=lambda p: p.as_posix()):
        guard_path(paths.root, receipt_path, must_exist=True)
        output.append(read_json(receipt_path))
    return output


def verify_receipt(root: Union[Path, str], receipt: Mapping[str, Any]) -> Dict[str, Any]:
    paths = paths_for(root)
    value = dict(receipt)
    errors: List[Dict[str, Any]] = []
    supplied = str(value.pop("receipt_sha256", ""))
    calculated = sha256_text(canonical_json(value))
    if supplied != calculated:
        errors.append({"code": "RECEIPT_DIGEST", "message": "execution receipt digest mismatch"})
    if value.get("schema") != RECEIPT_SCHEMA:
        errors.append({"code": "RECEIPT_SCHEMA", "message": "execution receipt schema mismatch"})
    if value.get("project_id") != load_project(paths.root).get("project_id"):
        errors.append({"code": "RECEIPT_PROJECT", "message": "execution receipt project binding mismatch"})
    for stream in ("stdout", "stderr"):
        rel = str(value.get(f"{stream}_relpath", ""))
        try:
            safe_relative_path(rel)
            path = guard_path(paths.root, paths.root / rel, must_exist=True)
        except Refusal as exc:
            errors.append({"code": f"RECEIPT_{stream.upper()}_PATH", "message": str(exc)})
            continue
        if sha256_file(path) != value.get(f"{stream}_sha256"):
            errors.append({"code": f"RECEIPT_{stream.upper()}_DIGEST", "message": f"{stream} digest mismatch"})
    for phase in ("pre", "post"):
        digest = str(value.get(f"{phase}_manifest_sha256", ""))
        if not re.fullmatch(r"[0-9a-f]{64}", digest):
            errors.append({"code": f"RECEIPT_{phase.upper()}_MANIFEST", "message": f"{phase} manifest digest is invalid"})
            continue
        manifest_path = paths.manifests / f"{digest}.json"
        try:
            manifest = read_json(guard_path(paths.root, manifest_path, must_exist=True))
        except Refusal as exc:
            errors.append({"code": f"RECEIPT_{phase.upper()}_MANIFEST", "message": str(exc)})
            continue
        if _manifest_digest(manifest) != digest:
            errors.append({"code": f"RECEIPT_{phase.upper()}_MANIFEST_DIGEST", "message": f"{phase} manifest bytes are damaged"})
        if manifest.get("records_sha256") != value.get(f"{phase}_records_sha256"):
            errors.append({"code": f"RECEIPT_{phase.upper()}_RECORDS", "message": f"{phase} record digest mismatch"})
    return {
        "verified": not errors,
        "receipt_id": value.get("receipt_id"),
        "receipt_sha256": supplied,
        "status": value.get("status"),
        "error_count": len(errors),
        "errors": errors,
    }


def verify_receipts(root: Union[Path, str]) -> Dict[str, Any]:
    rows = []
    for receipt in latest_receipts(root):
        rows.append(verify_receipt(root, receipt))
    return {
        "verified": all(row["verified"] for row in rows),
        "receipt_count": len(rows),
        "receipts": rows,
    }


def _reminder_fingerprint(finding: Mapping[str, Any]) -> str:
    return sha256_text(
        canonical_json(
            {
                "gate": finding.get("gate"),
                "code": finding.get("code"),
                "subject": finding.get("subject"),
                "message": finding.get("message"),
            }
        )
    )


def _write_reminders_markdown(root: Union[Path, str]) -> Path:
    paths = paths_for(root)
    destination = paths.state / "REMINDERS.md"
    rows = list_reminders(paths.root, include_resolved=True)
    lines = [
        "# Uriel repair reminders",
        "",
        "A refusal means the current project state has not earned a Blessing. It is not a dismissal of the person or the underlying question.",
        "Uriel keeps these findings so they can be revisited after wording, data, controls, citations, or scope improve.",
        "",
    ]
    if not rows:
        lines.extend(["No reminders have been recorded.", ""])
    for reminder in rows:
        finding = reminder.get("finding", {})
        lines.extend([
            "## [{0}] Gate {1} · {2} · `{3}`".format(
                str(reminder.get("status", "open")).upper(),
                finding.get("gate", "?"),
                finding.get("subject") or finding.get("title") or finding.get("code", "Finding"),
                reminder.get("reminder_id", "unknown"),
            ),
            "",
            "**Reason:** " + str(finding.get("message") or finding.get("reason") or "No reason recorded."),
            "",
            "**Repair paths:**",
        ])
        repairs = finding.get("repairs") or finding.get("repair_options") or []
        for index, repair in enumerate(list(repairs)[:3], start=1):
            lines.append(f"{index}. {repair}")
        if not repairs:
            lines.append("1. Narrow the claim, add direct evidence, and rerun the audit.")
        evidence = finding.get("evidence") or []
        if evidence:
            lines.extend(["", "**Evidence pointers:** " + ", ".join(f"`{item}`" for item in evidence)])
        if reminder.get("resolution_note"):
            lines.extend(["", "**Resolution note:** " + str(reminder.get("resolution_note"))])
        lines.append("")
    atomic_write(destination, "\n".join(lines).rstrip() + "\n")
    return destination


def sync_reminders(root: Union[Path, str], findings: Iterable[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    paths = paths_for(root)
    paths.reminders.mkdir(parents=True, exist_ok=True)
    active: Dict[str, Mapping[str, Any]] = {}
    created_or_updated: List[Dict[str, Any]] = []
    for finding in findings:
        if finding.get("severity") != "blocker":
            continue
        fingerprint = _reminder_fingerprint(finding)
        active[fingerprint] = finding
        reminder_id = fingerprint[:16]
        path = paths.reminders / f"{reminder_id}.json"
        now = utc_now()
        if path.exists():
            reminder = read_json(path)
            reminder["last_seen_at_utc"] = now
            reminder["finding"] = dict(finding)
            reminder["status"] = "open"
            reminder["resolved_at_utc"] = None
            reminder["resolution_note"] = ""
        else:
            reminder = {
                "schema": REMINDER_SCHEMA,
                "reminder_id": reminder_id,
                "fingerprint_sha256": fingerprint,
                "status": "open",
                "created_at_utc": now,
                "last_seen_at_utc": now,
                "resolved_at_utc": None,
                "resolution_note": "",
                "finding": dict(finding),
            }
        atomic_write_json(path, reminder)
        created_or_updated.append(reminder)

    resolved: List[str] = []
    for path in sorted(paths.reminders.glob("*.json"), key=lambda item: item.name):
        reminder = read_json(path)
        fingerprint = str(reminder.get("fingerprint_sha256", ""))
        if reminder.get("status") == "open" and fingerprint not in active:
            reminder["status"] = "resolved"
            reminder["resolved_at_utc"] = utc_now()
            reminder["resolution_note"] = "Automatically resolved because the latest complete audit no longer reports this blocker."
            atomic_write_json(path, reminder)
            resolved.append(str(reminder.get("reminder_id")))
    if created_or_updated or resolved:
        append_ledger(
            paths.root,
            "audit.reminders_synced",
            {
                "open_reminder_ids": [item["reminder_id"] for item in created_or_updated],
                "resolved_reminder_ids": resolved,
            },
        )
    _write_reminders_markdown(paths.root)
    return created_or_updated


def list_reminders(root: Union[Path, str], *, include_resolved: bool = False) -> List[Dict[str, Any]]:
    paths = paths_for(root)
    reminders: List[Dict[str, Any]] = []
    if not paths.reminders.exists():
        return reminders
    for path in sorted(paths.reminders.glob("*.json"), key=lambda item: item.name):
        reminder = read_json(path)
        if include_resolved or reminder.get("status") != "resolved":
            reminders.append(reminder)
    return reminders


def update_reminder(root: Union[Path, str], reminder_id: str, *, status: str, note: str) -> Dict[str, Any]:
    paths = paths_for(root)
    if status not in {"open", "resolved"}:
        raise Refusal("Reminder status must be open or resolved.", code="INVALID_REMINDER_STATUS")
    if not re.fullmatch(r"[0-9a-f]{16}", reminder_id):
        raise Refusal("Invalid reminder id.", code="INVALID_REMINDER_ID")
    path = guard_path(paths.root, paths.reminders / f"{reminder_id}.json", must_exist=True)
    reminder = read_json(path)
    reminder["status"] = status
    reminder["resolution_note"] = note.strip()
    reminder["resolved_at_utc"] = utc_now() if status == "resolved" else None
    atomic_write_json(path, reminder)
    append_ledger(
        paths.root,
        f"reminder.{status}",
        {"reminder_id": reminder_id, "note_sha256": sha256_text(note)},
    )
    _write_reminders_markdown(paths.root)
    return reminder


def project_status(root: Union[Path, str]) -> Dict[str, Any]:
    paths = paths_for(root)
    project = load_project(paths.root)
    ledger = verify_ledger(paths.root)
    reminders = list_reminders(paths.root)
    current_audit = paths.audits / "current.json"
    audit_pointer = read_json(current_audit) if current_audit.exists() else None
    return {
        "project_id": project.get("project_id"),
        "title": project.get("title"),
        "question": project.get("question"),
        "privacy": project.get("privacy", {}).get("classification", "unknown"),
        "project_sha256": sha256_file(paths.project),
        "ledger": ledger,
        "open_reminders": len(reminders),
        "current_audit": audit_pointer,
        "offline_first": True,
        "external_ai_required": False,
    }


def doctor(root: Union[Path, str]) -> Dict[str, Any]:
    paths = paths_for(root)
    project = load_project(paths.root)
    manifest = build_manifest(paths.root, persist=False)
    ledger = verify_ledger(paths.root)
    writable_probe = paths.state / f".doctor.{uuid.uuid4().hex}.tmp"
    atomic_write(writable_probe, "ok\n")
    writable_probe.unlink()
    return {
        "status": "PASS",
        "engine_version": PACKAGE_VERSION,
        "python": sys.version.split()[0],
        "root": str(paths.root),
        "project_id": project.get("project_id"),
        "project_schema": project.get("schema"),
        "source_record_count": manifest.get("record_count"),
        "ledger": ledger,
        "root_confinement": "PASS",
        "state_writable": True,
        "network_used": False,
    }




def verify_project(root: Union[Path, str]) -> Dict[str, Any]:
    paths = paths_for(root)
    ledger = verify_ledger(paths.root)
    try:
        source = verify_source_manifest(paths.root)
    except (Refusal, IntegrityError):
        manifest = build_manifest(paths.root, persist=True)
        source = verify_source_manifest(paths.root, manifest)
    receipts = verify_receipts(paths.root)
    return {
        "verified": bool(ledger.get("verified") and source.get("verified") and receipts.get("verified")),
        "ledger": ledger,
        "source": source,
        "receipts": receipts,
    }


class UrielProject:
    """Small object-oriented facade for embedders, examples, and tests."""

    def __init__(self, root: Union[Path, str]) -> None:
        self.paths = paths_for(root)
        self.root = self.paths.root

    @classmethod
    def initialize(
        cls,
        root: Union[Path, str],
        *,
        name: str,
        question: str,
        privacy: str = "public",
        force: bool = False,
    ) -> "UrielProject":
        initialize_project(root, title=name, question=question, privacy=privacy, force=force)
        project = cls(root)
        _write_reminders_markdown(project.root)
        return project

    @property
    def ledger(self) -> "UrielProject":
        return self

    def load_manifest(self) -> Dict[str, Any]:
        return load_project(self.root)

    def save_manifest(self, manifest: Mapping[str, Any]) -> None:
        save_project(self.root, manifest, event="project.updated", details={"source": "UrielProject.save_manifest"})

    def snapshot(self) -> Dict[str, Any]:
        return build_manifest(self.root, persist=True)

    def run_declared(self, workload_id: str, *, timeout: Optional[int] = None) -> Dict[str, Any]:
        project = load_project(self.root)
        matches = [item for item in project.get("workloads", []) if isinstance(item, dict) and item.get("id") == workload_id]
        if not matches:
            raise Refusal(f"Unknown declared workload: {workload_id}", code="UNKNOWN_WORKLOAD")
        workload = matches[0]
        command = workload.get("command")
        if not isinstance(command, list) or not command:
            raise Refusal("A declared workload command must be a non-empty JSON array.", code="INVALID_WORKLOAD")
        expanded = [sys.executable if part == "{python}" else str(part) for part in command]
        return run_workload(self.root, expanded, timeout=timeout or int(workload.get("timeout_seconds", 600)), workload_id=workload_id)

    def verify_receipt(self, receipt: Mapping[str, Any]) -> Dict[str, Any]:
        return verify_receipt(self.root, receipt)

    def verify(self) -> Dict[str, Any]:
        return verify_project(self.root)

    def list_reminders(self, status: str = "open") -> List[Dict[str, Any]]:
        rows = list_reminders(self.root, include_resolved=status != "open")
        if status == "open":
            return [row for row in rows if row.get("status") == "open"]
        return [row for row in rows if row.get("status") == status]


# Compatibility aliases for integrations that used the first architectural brief.
ProjectLayout = ProjectPaths
safe_relative = safe_relative_path
init_project = initialize_project
