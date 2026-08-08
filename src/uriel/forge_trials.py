"""Truthful validation and adjudicated scoring for the synthetic Forge Trial.

The bundled answer key can prove that the fixture is internally consistent. It
cannot prove that Uriel, an AI, or any other detector found the seeded issues.
Precision and recall are therefore calculated only from explicitly supplied,
human-adjudicated issue identifiers.
"""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from statistics import mean
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union


FORGE_TRIAL_VALIDATION_SCHEMA = "uriel.forge_trial_fixture_validation.v1"
FORGE_TRIAL_SCORE_SCHEMA = "uriel.forge_trial_detector_score.v1"
DEFAULT_CASE_ID = "synthetic-001"

REQUIRED_FILES = (
    "START_HERE.md",
    "TRIAL_PROMPT.txt",
    "INPUT/ANALYSIS_PLAN.md",
    "INPUT/ARTICLE.md",
    "INPUT/OUTCOMES.csv",
    "INPUT/PARTICIPANTS.csv",
    "INPUT/ROOM_CONDITIONS.csv",
    "INPUT/SOURCE_NOTES.md",
    "ANSWER_KEY/CLEAN_SUMMARY.json",
    "ANSWER_KEY/EXPECTED_FINDINGS.md",
    "ANSWER_KEY/REPAIR_TARGET.md",
    "ANSWER_KEY/SCORECARD.csv",
    "ANSWER_KEY/SEEDED_ISSUES.json",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _stable_digest(value: Any) -> str:
    payload = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _load_json(path: Path) -> Any:
    def reject_duplicates(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key {key!r} in {path}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)


def _average(values: Iterable[Optional[float]]) -> float:
    present = [value for value in values if value is not None]
    if not present:
        raise ValueError("cannot average an empty series")
    return round(mean(present), 4)


def recompute_clean_summary(case_root: Path) -> Dict[str, Any]:
    """Recompute the answer-key summary from the supplied synthetic CSV files."""

    input_root = case_root / "INPUT"
    with (input_root / "PARTICIPANTS.csv").open(encoding="utf-8", newline="") as handle:
        participants = {row["participant_id"]: row for row in csv.DictReader(handle)}

    rows: List[Dict[str, Any]] = []
    with (input_root / "OUTCOMES.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["notes"] == "duplicate export row from manual correction sheet":
                continue
            participant_id = "P021" if row["participant_id"] == "P201" else row["participant_id"]
            task_time = float(row["task_time_seconds"])
            if participant_id == "P008" and row["week"] == "3":
                task_time = 144.0
            rows.append(
                {
                    "participant_id": participant_id,
                    "week": int(row["week"]),
                    "accuracy": (
                        None
                        if row["accuracy_percent"] == ""
                        else float(row["accuracy_percent"])
                    ),
                    "task_time": task_time,
                    "stress": float(row["stress_score_1_to_7"]),
                }
            )

    week_four = [row for row in rows if row["week"] == 4]

    def condition_rows(condition: str) -> List[Dict[str, Any]]:
        return [
            row
            for row in week_four
            if participants[row["participant_id"]]["condition"] == condition
        ]

    result: Dict[str, Any] = {}
    for condition in ("plant", "control"):
        group = condition_rows(condition)
        result[condition] = {
            "accuracy_n": sum(row["accuracy"] is not None for row in group),
            "week4_accuracy_mean": _average(row["accuracy"] for row in group),
            "accuracy_change_mean": _average(
                None
                if row["accuracy"] is None
                else row["accuracy"]
                - float(participants[row["participant_id"]]["baseline_accuracy_percent"])
                for row in group
            ),
            "week4_task_time_mean_seconds": _average(row["task_time"] for row in group),
            "task_time_improvement_mean_seconds": _average(
                float(participants[row["participant_id"]]["baseline_task_time_seconds"])
                - row["task_time"]
                for row in group
            ),
            "week4_stress_mean": _average(row["stress"] for row in group),
        }

        novice = [
            row
            for row in group
            if int(participants[row["participant_id"]]["experience_years"]) <= 2
        ]
        result[f"{condition}_novice"] = {
            "n": len(novice),
            "accuracy_change_mean": _average(
                None
                if row["accuracy"] is None
                else row["accuracy"]
                - float(participants[row["participant_id"]]["baseline_accuracy_percent"])
                for row in novice
            ),
            "task_time_improvement_mean_seconds": _average(
                float(participants[row["participant_id"]]["baseline_task_time_seconds"])
                - row["task_time"]
                for row in novice
            ),
        }
    return result


def validate_forge_trial_fixture(
    root: Union[str, Path],
    *,
    case_id: str = DEFAULT_CASE_ID,
) -> Dict[str, Any]:
    """Validate the sealed fixture without claiming any defect detection."""

    repository = Path(root).expanduser().resolve()
    case_root = repository / "benchmarks" / "forge_trials" / case_id
    checks: List[Dict[str, Any]] = []
    errors: List[str] = []

    def record(check_id: str, passed: bool, detail: str) -> None:
        checks.append(
            {
                "check_id": check_id,
                "status": "PASS" if passed else "FAIL",
                "detail": detail,
            }
        )
        if not passed:
            errors.append(f"{check_id}: {detail}")

    missing = [relative for relative in REQUIRED_FILES if not (case_root / relative).is_file()]
    record(
        "required_files",
        not missing,
        "all required fixture files are present"
        if not missing
        else "missing: " + ", ".join(missing),
    )
    if missing:
        return {
            "schema": FORGE_TRIAL_VALIDATION_SCHEMA,
            "case_id": case_id,
            "status": "FAIL",
            "checks": checks,
            "seeded_issue_count": 0,
            "scorecard_total_points": 0,
            "input_manifest": {},
            "answer_key_manifest": {},
            "recomputed_clean_summary": None,
            "detector_status": "NOT_RUN",
            "fixture_digest": None,
            "errors": errors,
        }

    manifest = {relative: _sha256(case_root / relative) for relative in REQUIRED_FILES}
    input_manifest = {
        relative: digest
        for relative, digest in manifest.items()
        if relative.startswith("INPUT/") or relative == "TRIAL_PROMPT.txt"
    }
    answer_key_manifest = {
        relative: digest
        for relative, digest in manifest.items()
        if relative.startswith("ANSWER_KEY/")
    }

    issues = _load_json(case_root / "ANSWER_KEY" / "SEEDED_ISSUES.json")
    issue_rows = issues.get("issues", [])
    issue_ids = [str(item.get("id", "")) for item in issue_rows if isinstance(item, Mapping)]
    issue_count_ok = (
        issues.get("schema") == "forge.synthetic_trial_ground_truth.v1"
        and isinstance(issue_rows, list)
        and issues.get("issue_count") == len(issue_rows)
        and len(issue_ids) == len(set(issue_ids))
        and all(issue_ids)
    )
    record(
        "answer_key_issue_index",
        issue_count_ok,
        f"{len(issue_rows)} unique seeded issues"
        if issue_count_ok
        else "issue count, schema, or identifiers are inconsistent",
    )

    with (case_root / "ANSWER_KEY" / "SCORECARD.csv").open(
        encoding="utf-8", newline=""
    ) as handle:
        score_rows = list(csv.DictReader(handle))
    try:
        score_total = sum(int(row["points"]) for row in score_rows)
    except (KeyError, TypeError, ValueError):
        score_total = -1
    scorecard_ok = (
        score_total == 100
        and bool(score_rows)
        and len({row.get("criterion") for row in score_rows}) == len(score_rows)
        and all(row.get("scoring_rule") for row in score_rows)
    )
    record(
        "scorecard",
        scorecard_ok,
        "scorecard totals 100 points"
        if scorecard_ok
        else f"invalid scorecard total or rows ({score_total})",
    )

    expected_summary = _load_json(case_root / "ANSWER_KEY" / "CLEAN_SUMMARY.json")
    recomputed_summary = recompute_clean_summary(case_root)
    summary_ok = recomputed_summary == expected_summary
    record(
        "clean_summary_recomputation",
        summary_ok,
        "recomputed clean summary matches the sealed answer key"
        if summary_ok
        else "recomputed clean summary differs from the sealed answer key",
    )

    fixture_digest = _stable_digest(
        {
            "case_id": case_id,
            "manifest": manifest,
            "issue_ids": issue_ids,
            "scorecard_total_points": score_total,
            "clean_summary": recomputed_summary,
        }
    )
    return {
        "schema": FORGE_TRIAL_VALIDATION_SCHEMA,
        "case_id": case_id,
        "status": "PASS" if not errors else "FAIL",
        "checks": checks,
        "seeded_issue_count": len(issue_rows),
        "scorecard_total_points": score_total,
        "input_manifest": input_manifest,
        "answer_key_manifest": answer_key_manifest,
        "recomputed_clean_summary": recomputed_summary,
        "detector_status": "NOT_RUN",
        "fixture_digest": fixture_digest,
        "errors": errors,
    }


def score_adjudicated_findings(
    root: Union[str, Path],
    observed_issue_ids: Sequence[str],
    *,
    case_id: str = DEFAULT_CASE_ID,
) -> Dict[str, Any]:
    """Score issue IDs after a blind report has been mapped to the answer key."""

    validation = validate_forge_trial_fixture(root, case_id=case_id)
    if validation["status"] != "PASS":
        raise ValueError("cannot score an invalid Forge Trial fixture")

    repository = Path(root).expanduser().resolve()
    answer = _load_json(
        repository
        / "benchmarks"
        / "forge_trials"
        / case_id
        / "ANSWER_KEY"
        / "SEEDED_ISSUES.json"
    )
    expected = {str(item["id"]) for item in answer["issues"]}
    observed = {str(item).strip() for item in observed_issue_ids if str(item).strip()}
    true_positives = sorted(expected & observed)
    false_positives = sorted(observed - expected)
    false_negatives = sorted(expected - observed)
    precision = (
        len(true_positives) / len(observed)
        if observed
        else None
    )
    recall = len(true_positives) / len(expected) if expected else None
    f1 = (
        (2 * precision * recall / (precision + recall))
        if precision is not None and recall is not None and precision + recall
        else None
    )
    return {
        "schema": FORGE_TRIAL_SCORE_SCHEMA,
        "case_id": case_id,
        "status": "SCORED",
        "adjudication": "Issue IDs must be assigned after the blind report; this function does not detect issues.",
        "expected_issue_count": len(expected),
        "observed_issue_count": len(observed),
        "true_positive_count": len(true_positives),
        "false_positive_count": len(false_positives),
        "false_negative_count": len(false_negatives),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "true_positive_ids": true_positives,
        "false_positive_ids": false_positives,
        "false_negative_ids": false_negatives,
        "fixture_digest": validation["fixture_digest"],
    }


def run_forge_trials(
    root: Union[str, Path],
    observed_findings: Optional[Sequence[str]] = None,
) -> Dict[str, Any]:
    """Validate the fixture and optionally score adjudicated observed findings."""

    validation = validate_forge_trial_fixture(root)
    if observed_findings is None:
        evaluation: Dict[str, Any] = {
            "schema": FORGE_TRIAL_SCORE_SCHEMA,
            "case_id": DEFAULT_CASE_ID,
            "status": "NOT_RUN",
            "adjudication": "No observed issue IDs were supplied; no detector metric was calculated.",
            "precision": None,
            "recall": None,
            "f1": None,
            "fixture_digest": validation.get("fixture_digest"),
        }
    else:
        evaluation = score_adjudicated_findings(root, observed_findings)
    return {
        "fixture_validation": validation,
        "detector_evaluation": evaluation,
    }
