"""Hash-bound import format for optional human or AI adversarial reviews."""
from __future__ import annotations

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
    value: Mapping[str, Any],
    *,
    expected_source_manifest_sha256: Optional[str] = None,
    expected_project_manifest_sha256: Optional[str] = None,
) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []

    def add(path: str, message: str) -> None:
        errors.append({"path": path, "message": message})

    if value.get("schema") != REVIEW_SCHEMA:
        add("/schema", "must equal {0}".format(REVIEW_SCHEMA))
    review_id = value.get("review_id")
    if not isinstance(review_id, str) or not _ID_RE.fullmatch(review_id):
        add("/review_id", "must be a portable identifier")
    if value.get("task") not in REVIEW_TASKS:
        add("/task", "must be a supported review task")
    if value.get("reviewer_type") not in {"human", "ai", "hybrid"}:
        add("/reviewer_type", "must be human, ai, or hybrid")
    for field in (
        "created_at_utc",
        "source_manifest_sha256",
        "project_manifest_sha256",
        "scope",
        "conclusion",
    ):
        if not isinstance(value.get(field), str) or not str(value.get(field)).strip():
            add("/" + field, "must be non-empty text")
    if expected_source_manifest_sha256 and value.get("source_manifest_sha256") != expected_source_manifest_sha256:
        add("/source_manifest_sha256", "does not match the current source manifest")
    if expected_project_manifest_sha256 and value.get("project_manifest_sha256") != expected_project_manifest_sha256:
        add("/project_manifest_sha256", "does not match the current project manifest")

    findings = value.get("findings")
    if not isinstance(findings, list):
        add("/findings", "must be an array")
        findings = []
    seen = set()
    for index, finding in enumerate(findings):
        base = "/findings/{0}".format(index)
        if not isinstance(finding, Mapping):
            add(base, "must be an object")
            continue
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
        for field in ("evidence_refs", "source_locators", "repair_options"):
            if not isinstance(finding.get(field), list) or not all(isinstance(item, str) for item in finding.get(field, [])):
                add(base + "/" + field, "must be an array of strings")
        repairs = finding.get("repair_options") if isinstance(finding.get("repair_options"), list) else []
        if len(repairs) != 3:
            add(base + "/repair_options", "must contain exactly three repair options")
    limitations = value.get("limitations")
    if not isinstance(limitations, list) or not limitations or not all(isinstance(item, str) and item.strip() for item in limitations):
        add("/limitations", "must be a non-empty array of explicit limitations")
    return errors


def import_review(root: Union[str, Path], review_path: Union[str, Path]) -> Dict[str, Any]:
    paths = paths_for(root)
    current = build_manifest(paths.root, persist=True)
    project_hash = sha256_file(paths.project)
    source = guard_path(paths.root, review_path, must_exist=True)
    value = read_json(source)
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
