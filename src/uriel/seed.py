"""Uriel Seed: turn a rough question into a researchable project.

Deterministic companion to the copy-paste Seed prompt.  ``seed_project``
preserves the question exactly (via the intake layer), returns one combined
clarification batch, and scaffolds the three project shapes, minimal design,
first source targets, ethics flags, and next actions.  Every scaffold is
explicitly [PROPOSED]; nothing here judges novelty, truth, or the author.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

from .core import (
    Refusal,
    append_ledger,
    atomic_write_json,
    canonical_json,
    paths_for,
    read_json,
    sha256_text,
    utc_now,
)
from .intake import (
    clarification_questions,
    formulation_templates,
    intake_idea,
)

SEED_SCHEMA = "uriel.seed.v1"

_HEX64 = re.compile(r"^[0-9a-f]{64}$")

FINAL_STATUSES = (
    "READY_FOR_SEED_REVIEW",
    "WORTH_EXPLORING",
    "NEEDS_ONE_CLARIFICATION",
    "PROMISING_BUT_NEEDS_EVIDENCE",
    "BETTER_AS_A_DIFFERENT_QUESTION",
    "NOT_TESTABLE_YET",
)


def validate_seed(record: Mapping[str, Any]) -> List[str]:
    """Return human-readable violations of the seed v1 contract."""
    errors: List[str] = []
    if record.get("schema") != SEED_SCHEMA:
        errors.append("schema must be uriel.seed.v1")
    for field in ("seed_id", "intake_id", "original_question", "created_at_utc"):
        if not isinstance(record.get(field), str) or not record.get(field):
            errors.append("{0} must be non-empty text".format(field))
    if not isinstance(record.get("question_sha256"), str) or not _HEX64.fullmatch(record.get("question_sha256", "")):
        errors.append("question_sha256 must be a 64-character lowercase hex SHA-256")
    if not isinstance(record.get("clarification_questions"), list):
        errors.append("clarification_questions must be an array")
    if record.get("status") not in FINAL_STATUSES:
        errors.append("status must be one of: " + ", ".join(FINAL_STATUSES))
    return errors


def seed_id_for(question_sha256: str) -> str:
    identity = canonical_json({"schema": SEED_SCHEMA, "question_sha256": question_sha256})
    return "seed-" + sha256_text(identity)[:16]


def _seed_brief(record: Mapping[str, Any]) -> str:
    lines: List[str] = []
    lines.append("# Uriel Seed brief")
    lines.append("")
    lines.append("## Original question (preserved exactly)")
    lines.append(record["original_question"])
    lines.append("")
    lines.append("## Clarification batch (answer only the ones that change the design)")
    for index, item in enumerate(record["clarification_questions"], start=1):
        lines.append("{0}. {1}".format(index, item["question"]))
    lines.append("")
    lines.append("## Three project shapes [PROPOSED]")
    for shape in record["three_project_shapes"]:
        lines.append("- {0}: {1}".format(shape["name"], shape["proposed"]))
    lines.append("")
    lines.append("## Minimal design scaffolds [PROPOSED]")
    design = record["minimal_design"]
    for key in ("hypothesis", "rival_hypothesis", "simple_test", "useful_control", "result_against"):
        lines.append("- {0}: {1}".format(key.replace("_", " "), design.get(key, "")))
    lines.append("")
    lines.append("## First primary sources [PROPOSED]")
    for item in record["first_primary_sources"]:
        lines.append("- " + item)
    lines.append("")
    lines.append("## Next three actions")
    for index, action in enumerate(record["next_three_actions"], start=1):
        lines.append("{0}. {1}".format(index, action))
    lines.append("")
    lines.append("Status: {0}".format(record["status"]))
    lines.append("Seed ID: {0}".format(record["seed_id"]))
    lines.append("This is an early Uriel Lens review, not a Blessing.")
    return "\n".join(lines)


def seed_project(
    root: Union[str, Path],
    question: str,
    *,
    title: str = "",
    privacy: str = "public",
) -> Dict[str, Any]:
    """Preserve a rough question and build the deterministic Seed record."""
    exact = question.strip()
    if not exact:
        raise Refusal("A question is required.", code="SEED_QUESTION_REQUIRED")
    intake = intake_idea(root, exact, title=title, privacy=privacy)
    root_path = Path(root).expanduser()
    paths = paths_for(root_path)

    clarifications = clarification_questions(exact)[:3]
    templates = formulation_templates(exact)
    by_type = {item["type"]: item["template"] for item in templates}

    value: Dict[str, Any] = {
        "schema": SEED_SCHEMA,
        "schema_version": 1,
        "seed_id": seed_id_for(intake["intake_id"]),
        "intake_id": intake["intake_id"],
        "created_at_utc": utc_now(),
        "original_question": exact,
        "question_sha256": sha256_text(exact),
        "assessment": "unassessed-not-rejected",
        "restatement_note": (
            "The question is preserved exactly; a neutral restatement without added "
            "certainty belongs to the advisory Seed review ([PROPOSED] material only)."
        ),
        "clarification_questions": clarifications,
        "three_project_shapes": [
            {
                "name": "small_answerable_question",
                "proposed": by_type.get("descriptive", ""),
                "note": "[PROPOSED] smallest narrow version that keeps the intent.",
            },
            {
                "name": "best_practical_project",
                "proposed": by_type.get("comparative", ""),
                "note": "[PROPOSED] strongest balance of value, evidence, time, and cost.",
            },
            {
                "name": "larger_question",
                "proposed": by_type.get("causal-or-mechanistic", ""),
                "note": "[PROPOSED] larger question this may point toward, if testable.",
            },
        ],
        "key_terms_and_variables": [
            "[PROPOSED] Define each key term operationally before choosing measurements.",
            "[PROPOSED] List the variables the claim actually depends on.",
        ],
        "minimal_design": {
            "hypothesis": "[PROPOSED] Write one testable hypothesis as: among [population] in [setting], [factor] changes [outcome].",
            "rival_hypothesis": "[PROPOSED] Write one plausible alternative explanation for the same observation.",
            "simple_test": "[PROPOSED] Smallest experiment or comparison that could produce a signal.",
            "useful_control": "[PROPOSED] Matched baseline or counterexample that makes the observation meaningful.",
            "result_against": "[PROPOSED] Exact result that would count against the idea.",
        },
        "first_primary_sources": [
            "[PROPOSED] Identify the smallest directly inspectable primary artifact or original dataset.",
            "[PROPOSED] Choose exact primary-source search targets rather than inherited summaries.",
        ],
        "ethics_flags": [
            "Safety, privacy, cost, and feasibility are checked by the advisory review; the deterministic layer records but does not waive them.",
        ],
        "next_three_actions": [
            "Answer the clarification questions that materially change the design.",
            "Fill the minimal-design scaffolds with the narrowest useful version and one falsifier.",
            "Acquire one directly inspectable primary artifact, then run `uriel audit --profile exploratory`.",
        ],
        "status": "READY_FOR_SEED_REVIEW",
        "truth_boundary": [
            "Uriel may scaffold but never invent data, citations, experiments, approvals, novelty, or validation.",
        ],
    }
    violations = validate_seed(value)
    if violations:
        raise Refusal("invalid seed record: " + "; ".join(violations), code="SEED_INVALID")

    destination = paths.state / "seed" / (value["seed_id"] + ".json")
    atomic_write_json(destination, value)
    append_ledger(
        paths.root,
        "seed.created",
        {
            "seed_id": value["seed_id"],
            "intake_id": value["intake_id"],
            "question_sha256": value["question_sha256"],
            "clarification_count": len(value["clarification_questions"]),
        },
    )
    value["_destination"] = str(destination)
    return value


def load_seed(path: Path) -> Dict[str, Any]:
    """Read and validate a seed record from disk."""
    record = read_json(path)
    violations = validate_seed(record)
    if violations:
        raise Refusal(
            "{0} failed validation: {1}".format(path.name, "; ".join(violations)),
            code="SEED_INVALID",
        )
    return record


def write_seed_brief(root: Union[str, Path], output: Path) -> Dict[str, Any]:
    """Write the human-readable seed brief for the most recent seed record."""
    root_path = Path(root).expanduser()
    paths = paths_for(root_path)
    store = paths.state / "seed"
    records = sorted(store.glob("seed-*.json")) if store.is_dir() else []
    if not records:
        raise Refusal(
            "No seed record exists in this project.",
            code="SEED_MISSING",
            repairs=["Run `uriel seed \"your question\"` first."],
        )
    record = load_seed(records[-1])
    brief = _seed_brief(record)
    target = Path(output).expanduser()
    if target.exists():
        raise Refusal(
            "Refusing to overwrite existing file {0}.".format(target),
            code="SEED_OUTPUT_EXISTS",
        )
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_bytes(brief.encode("utf-8"))
    temporary.replace(target)
    return {
        "seed_id": record["seed_id"],
        "output": str(target),
        "sha256": sha256_text(brief),
    }
