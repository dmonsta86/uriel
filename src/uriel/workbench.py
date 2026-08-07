"""Uriel Workbench: maintain research plans, claims, controls, limitations,
and decisions as immutable generations.

Implements the Diamond Path record model: recovered question, labeled items
(OBSERVATION / INTERPRETATION / CLAIM / ASSUMPTION / UNKNOWN / PROPOSED TEST),
rival explanations, the minimum viable research design, pivot options, and the
audit path.  Every update creates a new content-addressed generation; history
is immutable and the current pointer is atomically refreshed.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

from .checkpoints import (
    build_checkpoint,
    records_sha256,
    validate_checkpoint,
    write_checkpoint,
)
from .core import (
    Refusal,
    atomic_write_json,
    canonical_json,
    paths_for,
    read_json,
    sha256_text,
    utc_now,
)

WORKBENCH_SCHEMA = "uriel.workbench.v1"
WORKBENCH_PLAN_SCHEMA = "uriel.workbench_plan.v1"

LABELS = (
    "OBSERVATION",
    "INTERPRETATION",
    "CLAIM",
    "ASSUMPTION",
    "UNKNOWN",
    "PROPOSED TEST",
)

PIVOTS = (
    "narrower claim",
    "different outcome",
    "different comparison",
    "observational study",
    "replication",
    "methods paper",
    "dataset/resource paper",
    "negative result",
    "software/tool paper",
    "review or evidence map",
)

DESIGN_FIELDS = (
    "hypothesis",
    "rival_hypothesis",
    "variables",
    "operational_definitions",
    "controls",
    "inclusion_exclusion",
    "minimum_useful_data",
    "falsifying_result",
    "stopping_rule",
    "ethics_privacy",
)

_HEX16 = re.compile(r"^[0-9a-f]{16}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")


class WorkbenchRefusal(Refusal):
    """Raised for invalid workbench records or plan files."""


def validate_workbench(record: Mapping[str, Any]) -> List[str]:
    """Return human-readable violations of the workbench v1 contract."""
    errors: List[str] = []
    if record.get("schema") != WORKBENCH_SCHEMA:
        errors.append("schema must be uriel.workbench.v1")
    for field in ("workbench_id", "created_at_utc", "generation_id"):
        if not isinstance(record.get(field), str) or not record.get(field):
            errors.append("{0} must be non-empty text".format(field))
    if not (isinstance(record.get("question"), str) and record["question"]):
        errors.append("question must be non-empty text")
    if not isinstance(record.get("items"), list):
        errors.append("items must be an array")
    else:
        for index, item in enumerate(record["items"]):
            if not isinstance(item, Mapping):
                errors.append("items[{0}] must be an object".format(index))
                continue
            if item.get("label") not in LABELS:
                errors.append("items[{0}].label must be one of: {1}".format(index, ", ".join(LABELS)))
            if not (isinstance(item.get("text"), str) and item["text"]):
                errors.append("items[{0}].text must be non-empty text".format(index))
    if not isinstance(record.get("design"), Mapping):
        errors.append("design must be an object")
    else:
        for field in DESIGN_FIELDS:
            value = record["design"].get(field)
            if value is not None and not (isinstance(value, str) and value):
                errors.append("design.{0} must be non-empty text or null".format(field))
    if not isinstance(record.get("pivots"), list):
        errors.append("pivots must be an array")
    else:
        for index, pivot in enumerate(record["pivots"]):
            if pivot not in PIVOTS:
                errors.append("pivots[{0}] must be one of: {1}".format(index, ", ".join(PIVOTS)))
    return errors


def _gen_id(workbench_id: str, records_hash: str, parent: Optional[str]) -> str:
    identity = canonical_json(
        {"workbench_id": workbench_id, "records_sha256": records_hash, "parent": parent}
    )
    return "wbgen-" + sha256_text(identity)[:16]


def _store(paths: Any) -> Path:
    store = Path(paths.state) / "workbench"
    store.mkdir(parents=True, exist_ok=True)
    return store


def _current_generation(store: Path) -> Optional[str]:
    pointer = store / "current.json"
    if not pointer.is_file():
        return None
    value = read_json(pointer)
    gen = value.get("generation_id")
    return gen if isinstance(gen, str) and gen else None


def _write_pointer(store: Path, generation_id: str) -> None:
    atomic_write_json(
        store / "current.json",
        {"schema": "uriel.workbench_current.v1", "generation_id": generation_id, "updated_at_utc": utc_now()},
    )


def _blank_record(question: str) -> Dict[str, Any]:
    return {
        "schema": WORKBENCH_SCHEMA,
        "workbench_id": "wb-" + sha256_text(canonical_json({"question": question}))[:16],
        "created_at_utc": utc_now(),
        "generation_id": "",
        "question": question,
        "items": [],
        "rival_explanations": [],
        "design": {field: None for field in DESIGN_FIELDS},
        "pivots": [],
        "audit_path": [
            {
                "gate": "Gate 1 (novelty and clarity)",
                "must_be_true_before_pass": "[PROPOSED] The core question and claim are clear, scoped, and testable as stated.",
            },
            {
                "gate": "Gate 2 (evidence and citation)",
                "must_be_true_before_pass": "[PROPOSED] Every material claim maps to direct, independently inspectable evidence.",
            },
            {
                "gate": "Gate 3 (adversarial integrity)",
                "must_be_true_before_pass": "[PROPOSED] Rival explanations were tested and serious limitations are recorded.",
            },
        ],
        "user_decision": None,
        "status": "open",
    }


def _publish(store: Path, record: Mapping[str, Any], parent: Optional[str]) -> Dict[str, Any]:
    records_hash = records_sha256([record])
    generation_id = _gen_id(record["workbench_id"], records_hash, parent)
    checkpoint = build_checkpoint(
        records_sha256=records_hash,
        record_count=1,
        source_manifest_sha256=sha256_text(canonical_json(record)),
        ephemeral_policy_version="workbench-v1",
        parent_generation_id=parent,
    )
    validate_checkpoint(checkpoint)
    write_checkpoint(store, checkpoint)
    updated = dict(record)
    updated["generation_id"] = generation_id
    violations = validate_workbench(updated)
    if violations:
        raise WorkbenchRefusal("invalid workbench record: " + "; ".join(violations))
    destination = store / (generation_id + ".json")
    atomic_write_json(destination, updated)
    _write_pointer(store, generation_id)
    return updated


def _load_current(store: Path) -> Dict[str, Any]:
    generation_id = _current_generation(store)
    if generation_id is None:
        raise WorkbenchRefusal(
            "No workbench exists in this project.",
            code="WORKBENCH_MISSING",
            repairs=["Run `uriel workbench init --question \"...\"` first."],
        )
    record = read_json(store / (generation_id + ".json"))
    violations = validate_workbench(record)
    if violations:
        raise WorkbenchRefusal(
            "workbench generation {0} failed validation: {1}".format(generation_id, "; ".join(violations)),
            code="WORKBENCH_INVALID",
        )
    return record


def workbench_init(root: Union[str, Path], question: str) -> Dict[str, Any]:
    """Create the first workbench generation for a project."""
    exact = question.strip()
    if not exact:
        raise WorkbenchRefusal("A question is required.", code="WORKBENCH_QUESTION_REQUIRED")
    root_path = Path(root).expanduser()
    paths = paths_for(root_path)
    store = _store(paths)
    if _current_generation(store) is not None:
        raise WorkbenchRefusal(
            "A workbench already exists in this project.",
            code="WORKBENCH_EXISTS",
            repairs=[
                "Run `uriel workbench status` to inspect it.",
                "Run `uriel workbench plan` to extend it in a new generation.",
            ],
        )
    record = _blank_record(exact)
    return _publish(store, record, parent=None)


def workbench_plan(root: Union[str, Path], plan: Mapping[str, Any]) -> Dict[str, Any]:
    """Apply a validated plan file as the next workbench generation."""
    root_path = Path(root).expanduser()
    paths = paths_for(root_path)
    store = _store(paths)
    current = _load_current(store)
    updated = {key: value for key, value in current.items()}

    items = plan.get("items")
    if items is not None:
        if not isinstance(items, list):
            raise WorkbenchRefusal("plan.items must be an array", code="WORKBENCH_PLAN_INVALID")
        kept = []
        for entry in items:
            if not isinstance(entry, Mapping) or entry.get("label") not in LABELS or not (isinstance(entry.get("text"), str) and entry["text"]):
                raise WorkbenchRefusal(
                    "Each plan.items entry needs a valid label and non-empty text.",
                    code="WORKBENCH_PLAN_INVALID",
                )
            kept.append(
                {
                    "id": "item-{0}".format(sha256_text(canonical_json(entry))[:12]),
                    "label": entry["label"],
                    "text": entry["text"],
                }
            )
        existing_ids = {item["id"] for item in updated.get("items", [])}
        for entry in kept:
            if entry["id"] in existing_ids:
                continue
            updated.setdefault("items", []).append(entry)
            existing_ids.add(entry["id"])

    rivals = plan.get("rival_explanations")
    if rivals is not None:
        if not isinstance(rivals, list) or not all(isinstance(text, str) and text for text in rivals):
            raise WorkbenchRefusal("plan.rival_explanations must be an array of texts", code="WORKBENCH_PLAN_INVALID")
        updated["rival_explanations"] = [
            {"id": "rival-{0}".format(sha256_text(text)[:12]), "text": text} for text in rivals
        ]

    design = plan.get("design")
    if design is not None:
        if not isinstance(design, Mapping):
            raise WorkbenchRefusal("plan.design must be an object", code="WORKBENCH_PLAN_INVALID")
        for field, value in design.items():
            if field not in DESIGN_FIELDS:
                raise WorkbenchRefusal("Unknown design field: {0}".format(field), code="WORKBENCH_PLAN_INVALID")
            if not (isinstance(value, str) and value):
                raise WorkbenchRefusal("design.{0} must be non-empty text".format(field), code="WORKBENCH_PLAN_INVALID")
        updated["design"] = dict(design)

    pivots = plan.get("pivots")
    if pivots is not None:
        if not isinstance(pivots, list) or not all(pivot in PIVOTS for pivot in pivots):
            raise WorkbenchRefusal("plan.pivots must be a subset of: {0}".format(", ".join(PIVOTS)), code="WORKBENCH_PLAN_INVALID")
        updated["pivots"] = list(pivots)

    decision = plan.get("user_decision")
    if decision is not None:
        if not (isinstance(decision, str) and decision):
            raise WorkbenchRefusal("plan.user_decision must be non-empty text", code="WORKBENCH_PLAN_INVALID")
        updated["user_decision"] = decision
        updated["status"] = "pivoted" if plan.get("status") == "pivoted" else updated.get("status", "open")

    return _publish(store, updated, parent=current.get("generation_id"))


def workbench_status(root: Union[str, Path]) -> Dict[str, Any]:
    """Summarize the current workbench generation and its gaps."""
    root_path = Path(root).expanduser()
    paths = paths_for(root_path)
    store = _store(paths)
    generation_id = _current_generation(store)
    if generation_id is None:
        return {"exists": False, "next_action": "Run `uriel workbench init --question \"...\"`."}
    record = _load_current(store)
    counts: Dict[str, int] = {}
    for item in record.get("items", []):
        counts[item["label"]] = counts.get(item["label"], 0) + 1
    gaps = [
        field for field in DESIGN_FIELDS
        if not (isinstance(record["design"].get(field), str) and record["design"][field])
    ]
    return {
        "exists": True,
        "workbench_id": record["workbench_id"],
        "generation_id": generation_id,
        "status": record.get("status", "open"),
        "question": record["question"],
        "item_counts": counts,
        "rival_explanation_count": len(record.get("rival_explanations", [])),
        "pivots": record.get("pivots", []),
        "design_gaps": gaps,
        "user_decision": record.get("user_decision"),
    }


def workbench_next(root: Union[str, Path], *, output: Optional[Union[str, Path]] = None) -> Dict[str, Any]:
    """Return the exact next workbench action and write a durable next prompt."""
    root_path = Path(root).expanduser()
    paths = paths_for(root_path)
    store = _store(paths)
    generation_id = _current_generation(store)
    if generation_id is None:
        return {
            "exists": False,
            "next_action": "Initialize the workbench: `uriel workbench init --question \"...\"`.",
            "next_prompt": None,
        }
    record = _load_current(store)
    gaps = [
        field for field in DESIGN_FIELDS
        if not (isinstance(record["design"].get(field), str) and record["design"][field])
    ]
    if gaps:
        next_task = "Fill the minimum viable research design field '{0}' with a [PROPOSED] draft.".format(gaps[0])
    elif not record.get("items"):
        next_task = "Label the material as OBSERVATION, INTERPRETATION, CLAIM, ASSUMPTION, UNKNOWN, or PROPOSED TEST."
    elif not record.get("rival_explanations"):
        next_task = "Record at least one plausible rival explanation and the evidence that would distinguish it."
    elif not record.get("pivots"):
        next_task = "Record the best pivot option when the original claim is unsupported."
    else:
        next_task = "Run `uriel audit --profile submission` and record the audit-path findings."
    prompt = (
        "# Uriel Workbench next prompt\n\n"
        "Read the current workbench generation listed below, perform all non-blocked work, "
        "ask all unavoidable questions in ONE numbered batch, then write NEXT_PROMPT.txt and stop.\n\n"
        "Workbench ID: {0}\nGeneration: {1}\n\n{2}\n\n"
        "Label every new statement [OBSERVED], [INFERRED], [UNKNOWN], or [PROPOSED]. "
        "Never invent citations, data, results, or approvals. "
        "Do not claim a Blessing.\n"
    ).format(record["workbench_id"], generation_id, next_task)
    destination = None
    if output:
        target = Path(output).expanduser()
        if target.exists():
            raise WorkbenchRefusal(
                "Refusing to overwrite existing file {0}.".format(target),
                code="WORKBENCH_OUTPUT_EXISTS",
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_bytes(prompt.encode("utf-8"))
        temporary.replace(target)
        destination = str(target)
    return {
        "exists": True,
        "workbench_id": record["workbench_id"],
        "generation_id": generation_id,
        "next_action": next_task,
        "next_prompt_path": destination,
        "next_prompt_sha256": sha256_text(prompt) if destination else None,
    }
