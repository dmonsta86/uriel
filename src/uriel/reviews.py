"""Hash-bound import format for optional human or AI adversarial reviews."""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import (
    IntegrityError,
    Refusal,
    append_ledger,
    atomic_write_json,
    build_manifest,
    canonical_json,
    guard_path,
    load_project,
    paths_for,
    read_json,
    sha256_file,
    sha256_text,
)

REVIEW_SCHEMA = "uriel.external_review.v1"
REVIEW_TASKS = (
    "clarity",
    "field-map",
    "primary-evidence",
    "contradiction-review",
    "adversarial-review",
    "repair-review",
    "submission-review",
)
_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
MAX_REVIEW_FILE_BYTES = 128 * 1024
MAX_REVIEW_FINDINGS = 100
MAX_REVIEW_LIST_ITEMS = 100
MAX_REVIEW_TEXT_CHARACTERS = 16 * 1024
_REVIEW_KEYS = {
    "schema",
    "review_id",
    "task",
    "reviewer_type",
    "provider",
    "model",
    "created_at_utc",
    "source_manifest_sha256",
    "project_manifest_sha256",
    "scope",
    "findings",
    "limitations",
    "conclusion",
}
_FINDING_KEYS = {
    "id",
    "severity",
    "statement",
    "evidence_refs",
    "source_locators",
    "repair_options",
}


def _read_bounded_review_json(source: Path) -> Dict[str, Any]:
    try:
        with source.open("rb") as handle:
            payload = handle.read(MAX_REVIEW_FILE_BYTES + 1)
    except OSError as exc:
        raise Refusal(
            "Uriel could not read the external review safely.",
            code="INVALID_JSON",
            details={"file": source.name, "error": str(exc)},
        ) from exc
    if len(payload) > MAX_REVIEW_FILE_BYTES:
        raise Refusal(
            "The external review exceeds Uriel's hard import budget.",
            code="EXTERNAL_REVIEW_TOO_LARGE",
            details={"review_bytes": len(payload), "maximum_bytes": MAX_REVIEW_FILE_BYTES},
            repairs=[
                "Ask the reviewer for one compact JSON object covering only the declared task.",
                "Split separate claims into separately bound review tasks.",
                "Review the oversized material manually and import only bounded findings with exact locators.",
            ],
        )
    try:
        value = json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Refusal(
            "Uriel could not read valid UTF-8 JSON from the external review.",
            code="INVALID_JSON",
            details={"file": source.name, "error": str(exc)},
        ) from exc
    if not isinstance(value, dict):
        raise Refusal("External review must contain one JSON object.", code="JSON_OBJECT_REQUIRED")
    return value


def review_template(
    *,
    task: str,
    source_manifest_sha256: str,
    project_manifest_sha256: str,
) -> Dict[str, Any]:
    if task not in REVIEW_TASKS:
        raise Refusal("Unknown review task: {0}".format(task), code="INVALID_REVIEW_TASK")
    return {
        "schema": REVIEW_SCHEMA,
        "review_id": "replace-with-portable-id",
        "task": task,
        "reviewer_type": "ai",
        "provider": "",
        "model": "",
        "created_at_utc": "",
        "source_manifest_sha256": source_manifest_sha256,
        "project_manifest_sha256": project_manifest_sha256,
        "scope": "State exactly what files, searches, dates, and claim ids were reviewed.",
        "findings": [
            {
                "id": "F1",
                "severity": "blocker",
                "statement": "Describe one precise problem without inventing facts.",
                "evidence_refs": ["/claims/C1"],
                "source_locators": [],
                "repair_options": [
                    "Repair path one.",
                    "Repair path two.",
                    "Repair path three.",
                ],
            }
        ],
        "limitations": [
            "The reviewer did not independently verify any locator not present in the supplied artifacts."
        ],
        "conclusion": "needs-repair",
    }


def validate_review(
    value: Any,
    *,
    expected_source_manifest_sha256: Optional[str] = None,
    expected_project_manifest_sha256: Optional[str] = None,
) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []

    def add(path: str, message: str) -> None:
        errors.append({"path": path, "message": message})

    if not isinstance(value, Mapping):
        add("/", "must be one JSON object")
        return errors
    if set(value) != _REVIEW_KEYS:
        add("/", "must contain exactly the published external-review fields")
    if value.get("schema") != REVIEW_SCHEMA:
        add("/schema", "must equal {0}".format(REVIEW_SCHEMA))
    review_id = value.get("review_id")
    if not isinstance(review_id, str) or not _ID_RE.fullmatch(review_id):
        add("/review_id", "must be a portable identifier")
    if value.get("task") not in REVIEW_TASKS:
        add("/task", "must be a supported review task")
    if value.get("reviewer_type") not in {"human", "ai", "hybrid"}:
        add("/reviewer_type", "must be human, ai, or hybrid")
    for field in ("created_at_utc", "scope", "conclusion"):
        if not isinstance(value.get(field), str) or not str(value.get(field)).strip():
            add("/" + field, "must be non-empty text")
        elif len(str(value.get(field))) > MAX_REVIEW_TEXT_CHARACTERS:
            add("/" + field, "exceeds the bounded review text limit")
    for field in ("provider", "model"):
        if not isinstance(value.get(field), str) or len(str(value.get(field))) > 256:
            add("/" + field, "must be text no longer than 256 characters")
    for field in ("source_manifest_sha256", "project_manifest_sha256"):
        if not isinstance(value.get(field), str) or _SHA256_RE.fullmatch(str(value.get(field))) is None:
            add("/" + field, "must be one lowercase SHA-256 digest")
    if expected_source_manifest_sha256 and value.get("source_manifest_sha256") != expected_source_manifest_sha256:
        add("/source_manifest_sha256", "does not match the current source manifest")
    if expected_project_manifest_sha256 and value.get("project_manifest_sha256") != expected_project_manifest_sha256:
        add("/project_manifest_sha256", "does not match the current project manifest")

    findings = value.get("findings")
    if not isinstance(findings, list):
        add("/findings", "must be an array")
        findings = []
    elif len(findings) > MAX_REVIEW_FINDINGS:
        add("/findings", "exceeds the maximum of {0} findings".format(MAX_REVIEW_FINDINGS))
    seen = set()
    for index, finding in enumerate(findings):
        base = "/findings/{0}".format(index)
        if not isinstance(finding, Mapping):
            add(base, "must be an object")
            continue
        if set(finding) != _FINDING_KEYS:
            add(base, "must contain exactly the published finding fields")
        identifier = finding.get("id")
        if not isinstance(identifier, str) or not _ID_RE.fullmatch(identifier):
            add(base + "/id", "must be a portable identifier")
        elif identifier in seen:
            add(base + "/id", "duplicates an earlier finding")
        else:
            seen.add(identifier)
        if finding.get("severity") not in {"info", "warning", "blocker"}:
            add(base + "/severity", "must be info, warning, or blocker")
        if not isinstance(finding.get("statement"), str) or len(str(finding.get("statement")).strip()) < 12:
            add(base + "/statement", "must describe a precise review finding")
        elif len(str(finding.get("statement"))) > MAX_REVIEW_TEXT_CHARACTERS:
            add(base + "/statement", "exceeds the bounded review text limit")
        for field in ("evidence_refs", "source_locators", "repair_options"):
            if not isinstance(finding.get(field), list) or not all(isinstance(item, str) for item in finding.get(field, [])):
                add(base + "/" + field, "must be an array of strings")
            elif len(finding.get(field, [])) > MAX_REVIEW_LIST_ITEMS:
                add(base + "/" + field, "exceeds the bounded review list limit")
            elif any(len(item) > MAX_REVIEW_TEXT_CHARACTERS for item in finding.get(field, [])):
                add(base + "/" + field, "contains text above the bounded review text limit")
        repairs = finding.get("repair_options") if isinstance(finding.get("repair_options"), list) else []
        if len(repairs) != 3:
            add(base + "/repair_options", "must contain exactly three repair options")
    limitations = value.get("limitations")
    if not isinstance(limitations, list) or not limitations or not all(isinstance(item, str) and item.strip() for item in limitations):
        add("/limitations", "must be a non-empty array of explicit limitations")
    elif len(limitations) > MAX_REVIEW_LIST_ITEMS or any(
        len(item) > MAX_REVIEW_TEXT_CHARACTERS for item in limitations
    ):
        add("/limitations", "exceeds the bounded review list or text limit")
    return errors


def import_review(root: Union[str, Path], review_path: Union[str, Path]) -> Dict[str, Any]:
    paths = paths_for(root)
    current = build_manifest(paths.root, persist=True)
    project_hash = sha256_file(paths.project)
    source = guard_path(paths.root, review_path, must_exist=True)
    value = _read_bounded_review_json(source)
    errors = validate_review(
        value,
        expected_source_manifest_sha256=str(current.get("manifest_sha256")),
        expected_project_manifest_sha256=project_hash,
    )
    if errors:
        raise Refusal(
            "The external review was not imported because its contract or content binding is invalid.",
            code="INVALID_EXTERNAL_REVIEW",
            details={"errors": errors},
            repairs=[
                "Regenerate the review from the current prompt so both manifest hashes match.",
                "Correct every contract error without deleting unfavorable findings.",
                "Save the result under `.uriel/review-inbox/` so importing it does not change the audited source set.",
            ],
        )
    review_id = str(value["review_id"])
    digest = sha256_text(canonical_json(value))
    review_dir = paths.state / "reviews"
    review_dir.mkdir(parents=True, exist_ok=True)
    destination = review_dir / "{0}-{1}.json".format(review_id, digest[:16])
    if destination.exists() and read_json(destination) != value:
        raise IntegrityError("Immutable external review collision.", code="REVIEW_COLLISION")
    if not destination.exists():
        atomic_write_json(destination, value)
    registry_path = review_dir / "index.json"
    if registry_path.exists():
        registry = read_json(registry_path)
    else:
        registry = {"schema": "uriel.review_index.v1", "reviews": []}
    rows = registry.get("reviews") if isinstance(registry.get("reviews"), list) else []
    entry = {
        "review_id": review_id,
        "task": value.get("task"),
        "reviewer_type": value.get("reviewer_type"),
        "provider": value.get("provider"),
        "model": value.get("model"),
        "review_sha256": digest,
        "relative_path": destination.relative_to(paths.root).as_posix(),
        "source_manifest_sha256": value.get("source_manifest_sha256"),
        "project_manifest_sha256": value.get("project_manifest_sha256"),
        "finding_count": len(value.get("findings", [])),
    }
    existing = [row for row in rows if isinstance(row, Mapping) and row.get("review_sha256") == digest]
    if not existing:
        rows.append(entry)
    registry["reviews"] = sorted(rows, key=lambda item: (str(item.get("task")), str(item.get("review_id"))))
    atomic_write_json(registry_path, registry)
    append_ledger(
        paths.root,
        "review.imported",
        {
            "review_id": review_id,
            "task": value.get("task"),
            "review_sha256": digest,
            "source_manifest_sha256": value.get("source_manifest_sha256"),
        },
    )
    return entry


def list_reviews(root: Union[str, Path]) -> List[Dict[str, Any]]:
    paths = paths_for(root)
    registry_path = paths.state / "reviews" / "index.json"
    if not registry_path.exists():
        return []
    registry = read_json(registry_path)
    rows = registry.get("reviews")
    return [dict(item) for item in rows if isinstance(item, Mapping)] if isinstance(rows, list) else []
