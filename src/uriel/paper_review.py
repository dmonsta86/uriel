"""Read-only paper fidelity, evidence, and change-confirmation review.

The paper-review surface composes existing local Uriel records.  It does not
capture conversation text, discover literature, decide semantic fidelity,
rewrite a manuscript, or grant scientific/publication authority.
"""
from __future__ import annotations

import difflib
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .core import (
    Refusal,
    build_manifest,
    canonical_json,
    guard_path,
    is_reparse_or_link,
    load_project,
    paths_for,
    safe_relative_path,
    sha256_bytes,
    sha256_file,
    sha256_text,
    utc_now,
)
from .research_verbatim import (
    MAX_EXACT_TEXT_BYTES,
    consent_status,
    drift_review,
    review_entries,
    verify_ledger,
)


PAPER_REVIEW_SCHEMA = "uriel.paper_review.v1"
CHANGE_CLASSES = (
    "unspecified",
    "wording_only",
    "title",
    "claim_change",
    "scope_change",
    "structure_change",
    "source_change",
    "conclusion_change",
    "major_revision",
)
MATERIAL_CHANGE_CLASSES = frozenset(CHANGE_CLASSES) - {
    "unspecified",
    "wording_only",
}
MAJOR_LINE_CHANGE_FRACTION = 0.20
MAX_PAPER_LINES = 50_000


def _read_text_file(
    root: Path,
    relative_path: str,
    *,
    label: str,
) -> Tuple[Path, bytes, str]:
    safe = safe_relative_path(relative_path)
    target = guard_path(root, root / safe, must_exist=True)
    if not target.is_file() or is_reparse_or_link(target):
        raise Refusal(
            "{0} must be one regular project-local file.".format(label),
            code="PAPER_REVIEW_FILE_REQUIRED",
            details={"path": safe.as_posix(), "label": label},
            repairs=[
                "Select a regular UTF-8 manuscript beneath the initialized project root.",
                "Copy a permitted candidate into a fresh project-local file and review that copy.",
                "Remove links, reparse points, and parent traversal from the selected path.",
            ],
        )
    raw = target.read_bytes()
    if len(raw) > MAX_EXACT_TEXT_BYTES:
        raise Refusal(
            "{0} exceeds the bounded paper-review text ceiling.".format(label),
            code="PAPER_REVIEW_TEXT_TOO_LARGE",
            details={
                "path": safe.as_posix(),
                "size_bytes": len(raw),
                "maximum_bytes": MAX_EXACT_TEXT_BYTES,
            },
            repairs=[
                "Review one bounded manuscript or section at a time.",
                "Remove appendices or binary material from the selected text file.",
                "Keep the complete original unchanged and create a bounded review copy.",
            ],
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refusal(
            "{0} is not strict UTF-8 text.".format(label),
            code="PAPER_REVIEW_UTF8_REQUIRED",
            details={"path": safe.as_posix()},
            repairs=[
                "Save the selected manuscript as strict UTF-8.",
                "Preserve the original bytes and create a separate UTF-8 review copy.",
                "Do not replace undecodable bytes silently.",
            ],
        ) from exc
    if len(text.splitlines()) > MAX_PAPER_LINES:
        raise Refusal(
            "{0} exceeds the bounded paper-review line ceiling.".format(label),
            code="PAPER_REVIEW_LINE_LIMIT",
            details={"maximum_lines": MAX_PAPER_LINES},
        )
    return target, raw, text


def _heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _diff_summary(baseline: str, candidate: str) -> Dict[str, Any]:
    before = baseline.splitlines()
    after = candidate.splitlines()
    matcher = difflib.SequenceMatcher(None, before, after, autojunk=False)
    inserted = 0
    deleted = 0
    replaced_before = 0
    replaced_after = 0
    unchanged = 0
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            unchanged += i2 - i1
        elif tag == "insert":
            inserted += j2 - j1
        elif tag == "delete":
            deleted += i2 - i1
        elif tag == "replace":
            replaced_before += i2 - i1
            replaced_after += j2 - j1
    changed_basis = deleted + replaced_before + inserted + replaced_after
    denominator = max(1, len(before) + len(after))
    fraction = changed_basis / denominator
    return {
        "baseline_lines": len(before),
        "candidate_lines": len(after),
        "unchanged_lines": unchanged,
        "inserted_lines": inserted,
        "deleted_lines": deleted,
        "replaced_baseline_lines": replaced_before,
        "replaced_candidate_lines": replaced_after,
        "changed_line_fraction": round(fraction, 6),
        "first_heading_changed": _heading(baseline) != _heading(candidate),
    }


def _fidelity_status(categories: Sequence[str]) -> str:
    values = set(categories)
    if "PRESERVED_MEANING" in values:
        return "POSSIBLY_PRESERVED_REQUIRES_HUMAN_REVIEW"
    if "CONTRADICTION" in values:
        return "POSSIBLE_CONTRADICTION"
    if "OVERSTATEMENT" in values:
        return "POSSIBLE_OVERSTATEMENT"
    if "OMISSION" in values:
        return "POSSIBLE_OMISSION"
    return "CHANGED_WORDING_REQUIRES_HUMAN_REVIEW"


def _verbatim_review(
    root: Path,
    user_reference: Optional[str],
    candidate: str,
    entry_ids: Sequence[str],
) -> Dict[str, Any]:
    if user_reference is None:
        return {
            "status": "NOT_REQUESTED",
            "entry_count": 0,
            "author_review_required": False,
            "entries": [],
            "privacy_note": "No user scope was supplied; no verbatim state was opened.",
        }
    consent = consent_status(root, user_reference)
    ledger = review_entries(root, user_reference)
    verified_ledger = verify_ledger(root, user_reference)
    rows = list(ledger.get("entries", []))
    by_id = {str(row.get("entry_id")): row for row in rows}
    selected = list(dict.fromkeys(str(value) for value in entry_ids))
    if not selected:
        selected = list(by_id)
    if not selected:
        return {
            "status": "NO_CAPTURED_BASELINES",
            "entry_count": 0,
            "author_review_required": False,
            "entries": [],
            "consent_mode": consent.get("mode"),
            "ledger_store_exists": ledger.get("ledger_store_exists", False),
        }
    drift = drift_review(
        root,
        user_reference,
        candidate,
        entry_ids=selected,
    )
    matrix = []
    for result in drift["entry_results"]:
        entry = by_id[str(result["entry_id"])]
        exact_text = str(entry.get("exact_text", ""))
        status = (
            "PRESERVED_EXACT_TEXT"
            if exact_text and exact_text in candidate
            else _fidelity_status(result["categories"])
        )
        matrix.append(
            {
                "entry_id": result["entry_id"],
                "label": entry.get("label"),
                "source_message_ref": entry.get("source", {}).get("message_ref"),
                "exact_text_sha256": result["exact_text_sha256"],
                "status": status,
                "categories": list(result["categories"]),
                "lexical_evidence": dict(result["lexical_evidence"]),
            }
        )
    review_required = any(
        row["status"] not in {"PRESERVED_EXACTLY", "PRESERVED_EXACT_TEXT"}
        for row in matrix
    )
    return {
        "status": "AUTHOR_REVIEW_REQUIRED" if review_required else "PRESERVED_EXACTLY",
        "entry_count": len(matrix),
        "author_review_required": review_required,
        "entries": matrix,
        "consent_mode": consent.get("mode"),
        "ledger_sha256": verified_ledger.get("ledger_sha256"),
        "semantic_fidelity_decided": False,
        "exact_text_included": False,
    }


def _artifact_status(root: Path, row: Mapping[str, Any]) -> str:
    relative = str(row.get("artifact_path", "")).strip()
    expected = str(row.get("sha256", "")).strip().lower()
    if not relative:
        return "NO_LOCAL_ARTIFACT"
    try:
        safe = safe_relative_path(relative)
        target = guard_path(root, root / safe, must_exist=True)
    except Refusal:
        return "MISSING_OR_UNSAFE_ARTIFACT"
    if not target.is_file() or is_reparse_or_link(target):
        return "MISSING_OR_UNSAFE_ARTIFACT"
    if not expected:
        return "UNHASHED_ARTIFACT"
    return "CURRENT" if sha256_file(target) == expected else "STALE_ARTIFACT"


def _claim_coverage(root: Path, project: Mapping[str, Any]) -> Dict[str, Any]:
    evidence_rows = project.get("evidence", [])
    evidence = {
        str(row.get("id")): row
        for row in evidence_rows
        if isinstance(row, Mapping) and row.get("id")
    } if isinstance(evidence_rows, list) else {}
    claims = project.get("claims", [])
    output = []
    for claim in claims if isinstance(claims, list) else []:
        if not isinstance(claim, Mapping):
            continue
        support_ids = list(dict.fromkeys(str(value) for value in claim.get("evidence_ids", [])))
        counter_ids = list(dict.fromkeys(str(value) for value in claim.get("counterevidence_ids", [])))
        linked = support_ids + [value for value in counter_ids if value not in support_ids]
        unknown = sorted(set(linked) - set(evidence))
        states = {value: _artifact_status(root, evidence[value]) for value in linked if value in evidence}
        stale = sorted(
            value for value, state in states.items()
            if state in {"MISSING_OR_UNSAFE_ARTIFACT", "UNHASHED_ARTIFACT", "STALE_ARTIFACT"}
        )
        if unknown:
            status = "BROKEN_EVIDENCE_LINK"
        elif stale:
            status = "STALE_OR_MISSING_EVIDENCE"
        elif not support_ids:
            status = "NO_SUPPORT_LINKED"
        else:
            status = "DECLARED_COVERAGE_PRESENT"
        output.append(
            {
                "claim_id": str(claim.get("id", "")),
                "importance": str(claim.get("importance", "")),
                "support_evidence_ids": support_ids,
                "counterevidence_ids": counter_ids,
                "unknown_evidence_ids": unknown,
                "artifact_status": states,
                "status": status,
                "semantic_support_decided": False,
            }
        )
    incomplete = [row["claim_id"] for row in output if row["status"] != "DECLARED_COVERAGE_PRESENT"]
    return {
        "status": "INCOMPLETE" if incomplete else "DECLARED_COVERAGE_PRESENT",
        "claim_count": len(output),
        "incomplete_claim_ids": incomplete,
        "claims": output,
        "semantic_support_decided": False,
    }


def _strings(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    return [item.strip() for item in value if isinstance(item, str) and item.strip()]


def _literature_coverage(project: Mapping[str, Any]) -> Dict[str, Any]:
    novelty = project.get("novelty_review")
    novelty = novelty if isinstance(novelty, Mapping) else {}
    databases = _strings(novelty.get("databases"))
    queries = _strings(novelty.get("queries"))
    nearest = _strings(novelty.get("nearest_prior_work"))
    differentiators = _strings(novelty.get("differentiators"))
    negative = _strings(novelty.get("negative_searches"))
    limitations = _strings(novelty.get("scope_limitations"))
    search_date = str(novelty.get("search_date", "")).strip()
    missing = []
    if not databases:
        missing.append("databases")
    if not queries:
        missing.append("queries")
    if not search_date:
        missing.append("search_date")
    if not nearest:
        missing.append("nearest_prior_work")
    if not differentiators:
        missing.append("differentiators")
    if not negative:
        missing.append("negative_searches")
    if not limitations:
        missing.append("scope_limitations")
    return {
        "status": "DECLARED_BOUNDED" if not missing else "LITERATURE_COVERAGE_INCOMPLETE",
        "declared_status": str(novelty.get("status", "not_started")),
        "search_date": search_date,
        "database_count": len(databases),
        "query_count": len(queries),
        "nearest_prior_work_count": len(nearest),
        "differentiator_count": len(differentiators),
        "negative_search_count": len(negative),
        "scope_limitation_count": len(limitations),
        "missing_fields": missing,
        "closest_published_test_status": (
            "DECLARED_FOR_HUMAN_REVIEW" if nearest else "UNRESOLVED"
        ),
        "incremental_value_status": (
            "DECLARED_FOR_HUMAN_REVIEW" if differentiators else "UNRESOLVED"
        ),
        "live_literature_discovery_performed": False,
        "exhaustiveness_claimed": False,
        "evidence_lane_rule": (
            "Local analysis status, external association evidence, mechanism status, "
            "and novelty/incremental value must remain separate; local INCONCLUSIVE "
            "does not erase declared external support."
        ),
    }


def review_paper(
    root: Union[Path, str],
    manuscript_path: str,
    *,
    baseline_path: Optional[str] = None,
    user_reference: Optional[str] = None,
    entry_ids: Sequence[str] = (),
    change_class: str = "unspecified",
    user_confirmed_change: bool = False,
) -> Dict[str, Any]:
    """Review one explicit manuscript candidate without writing any state."""

    if change_class not in CHANGE_CLASSES:
        raise Refusal(
            "Unknown paper change class.",
            code="PAPER_REVIEW_CHANGE_CLASS_INVALID",
            details={"change_class": change_class},
            repairs=[
                "Choose one documented --change-class value.",
                "Use unspecified when no canonical change is proposed.",
                "Use major_revision for a broad coupled rewrite.",
            ],
        )
    paths = paths_for(root)
    project = load_project(paths.root)
    manuscript, manuscript_bytes, manuscript_text = _read_text_file(
        paths.root, manuscript_path, label="Candidate manuscript"
    )
    baseline: Optional[Path] = None
    baseline_bytes: Optional[bytes] = None
    baseline_text: Optional[str] = None
    if baseline_path:
        baseline, baseline_bytes, baseline_text = _read_text_file(
            paths.root, baseline_path, label="Baseline manuscript"
        )
    if user_confirmed_change and baseline is None:
        raise Refusal(
            "A change cannot be confirmed without binding the reviewed baseline.",
            code="PAPER_REVIEW_BASELINE_REQUIRED",
            repairs=[
                "Provide --baseline with the exact current manuscript.",
                "Review the candidate without --confirm-change first.",
                "Keep the canonical manuscript unchanged until the comparison is complete.",
            ],
        )

    comparison: Dict[str, Any]
    if baseline_text is None or baseline_bytes is None or baseline is None:
        comparison = {
            "status": "BASELINE_NOT_SUPPLIED",
            "baseline_path": None,
            "baseline_sha256": None,
            "candidate_path": manuscript.relative_to(paths.root).as_posix(),
            "candidate_sha256": sha256_bytes(manuscript_bytes),
        }
    else:
        comparison = {
            "status": "COMPARED",
            "baseline_path": baseline.relative_to(paths.root).as_posix(),
            "baseline_sha256": sha256_bytes(baseline_bytes),
            "candidate_path": manuscript.relative_to(paths.root).as_posix(),
            "candidate_sha256": sha256_bytes(manuscript_bytes),
            **_diff_summary(baseline_text, manuscript_text),
        }

    explicit_material = change_class in MATERIAL_CHANGE_CLASSES
    scale_material = bool(
        comparison.get("first_heading_changed")
        or float(comparison.get("changed_line_fraction", 0.0))
        >= MAJOR_LINE_CHANGE_FRACTION
    )
    baseline_unknown_for_apply = baseline is None and change_class != "unspecified"
    confirmation_required = bool(
        explicit_material or scale_material or baseline_unknown_for_apply
    )
    if baseline is None:
        apply_status = "BASELINE_REQUIRED_BEFORE_CANONICAL_APPLY"
    elif confirmation_required and not user_confirmed_change:
        apply_status = "EXPLICIT_USER_CONFIRMATION_REQUIRED"
    elif confirmation_required:
        apply_status = "USER_CONFIRMED_REVIEWED_CANDIDATE"
    else:
        apply_status = "NO_MAJOR_CHANGE_DETECTED"

    observed_manifest = build_manifest(paths.root, persist=False)
    fidelity = _verbatim_review(
        paths.root,
        user_reference,
        manuscript_text,
        entry_ids,
    )
    claims = _claim_coverage(paths.root, project)
    literature = _literature_coverage(project)
    action = "READY_FOR_HUMAN_DECISION"
    if fidelity.get("author_review_required"):
        action = "AUTHOR_FIDELITY_REVIEW_REQUIRED"
    if apply_status in {
        "BASELINE_REQUIRED_BEFORE_CANONICAL_APPLY",
        "EXPLICIT_USER_CONFIRMATION_REQUIRED",
    }:
        action = apply_status

    result: Dict[str, Any] = {
        "schema": PAPER_REVIEW_SCHEMA,
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "project_id": project.get("project_id"),
        "project_sha256": sha256_file(paths.project),
        "observed_source_manifest_sha256": observed_manifest["manifest_sha256"],
        "observed_source_records_sha256": observed_manifest["records_sha256"],
        "manuscript": {
            "path": manuscript.relative_to(paths.root).as_posix(),
            "sha256": sha256_bytes(manuscript_bytes),
            "size_bytes": len(manuscript_bytes),
            "first_heading": _heading(manuscript_text),
        },
        "comparison": comparison,
        "change_gate": {
            "change_class": change_class,
            "explicit_material_class": explicit_material,
            "scale_or_title_material_signal": scale_material,
            "confirmation_required": confirmation_required,
            "user_confirmed_change": bool(user_confirmed_change),
            "status": apply_status,
            "canonical_mutation_performed": False,
            "canonical_mutation_authorized_by_uriel": False,
            "meaning": (
                "USER_CONFIRMED_REVIEWED_CANDIDATE records intent only; a separate "
                "caller still owns backup, collision, apply, and verification."
            ),
        },
        "author_fidelity": fidelity,
        "claim_evidence_coverage": claims,
        "literature_coverage": literature,
        "recommended_action": action,
        "boundaries": {
            "advisory_only": True,
            "semantic_fidelity_decided": False,
            "scientific_truth_decided": False,
            "publication_authority": False,
            "network_requests": 0,
            "provider_calls": 0,
            "writes": 0,
            "automatic_rewrite": False,
        },
        "review_token": "",
        "report_sha256": "",
    }
    token_identity = {
        "project_sha256": result["project_sha256"],
        "observed_source_manifest_sha256": result["observed_source_manifest_sha256"],
        "manuscript_sha256": result["manuscript"]["sha256"],
        "comparison": comparison,
        "change_gate": result["change_gate"],
        "author_fidelity": fidelity,
        "claim_evidence_coverage": claims,
        "literature_coverage": literature,
    }
    result["review_token"] = "upr-" + sha256_text(canonical_json(token_identity))[:32]
    digestable = dict(result)
    digestable["report_sha256"] = ""
    result["report_sha256"] = sha256_text(canonical_json(digestable))
    return result


__all__ = [
    "CHANGE_CLASSES",
    "MATERIAL_CHANGE_CLASSES",
    "PAPER_REVIEW_SCHEMA",
    "review_paper",
]
