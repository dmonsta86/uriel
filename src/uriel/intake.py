"""Plain-language idea intake that never mistakes polish for merit.

The intake layer is deterministic and intentionally modest.  It preserves the
question exactly, identifies missing choices that would change the research
design, and offers testable templates without pretending to judge novelty or
truth.  A child, student, independent researcher, or senior investigator gets
the same respectful treatment.
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Union

from .core import (
    PROJECT_FILE_NAME,
    append_ledger,
    atomic_write_json,
    initialize_project,
    load_project,
    paths_for,
    save_project,
    sha256_text,
    utc_now,
)

INTAKE_SCHEMA = "uriel.idea_intake.v1"

_CAUSAL = re.compile(r"\b(?:cause|causes|caused|because|lead(?:s)? to|make(?:s)?|affect(?:s)?|impact(?:s)?)\b", re.I)
_COMPARATIVE = re.compile(r"\b(?:better|worse|more|less|than|versus|vs\.?|compare|difference|different)\b", re.I)
_UNIVERSAL = re.compile(r"\b(?:always|never|everyone|nobody|all|none|proves?|definitely|impossible)\b", re.I)
_TIME = re.compile(r"\b(?:today|currently|now|before|after|during|year|month|week|day|century|between\s+\d)\b", re.I)


def _question(text: str, why: str, identifier: str) -> Dict[str, str]:
    return {"id": identifier, "question": text, "why_it_matters": why}


def clarification_questions(question: str) -> List[Dict[str, str]]:
    """Return a small, high-value clarification set for a rough question."""

    text = question.strip()
    rows: List[Dict[str, str]] = []
    rows.append(
        _question(
            "What exact observation would make you say the idea is probably right, and what observation would make you change your mind?",
            "A claim becomes testable only when support and disconfirmation are both recognizable in advance.",
            "outcome-and-falsifier",
        )
    )
    rows.append(
        _question(
            "Who or what is the question about, and in what setting should the answer apply?",
            "Population and setting prevent a result from being stretched farther than the data.",
            "population-and-setting",
        )
    )
    if not _TIME.search(text):
        rows.append(
            _question(
                "What time period matters, and could the answer change across periods?",
                "Time boundaries distinguish a stable relationship from a historical or temporary one.",
                "time-boundary",
            )
        )
    if _COMPARATIVE.search(text):
        rows.append(
            _question(
                "Compared with exactly what baseline or alternative, using the same measurement and conditions?",
                "An undefined comparison can create a control mismatch or a framing-dependent answer.",
                "comparison-baseline",
            )
        )
    else:
        rows.append(
            _question(
                "What comparison, control, prior state, or counterexample would make the observation meaningful?",
                "A baseline helps separate an effect from ordinary variation or selective attention.",
                "control-or-baseline",
            )
        )
    if _CAUSAL.search(text):
        rows.append(
            _question(
                "What else could produce the same outcome, and what evidence would distinguish those alternatives from the proposed cause?",
                "Causal language needs a way to rule out confounding, reverse direction, and shared causes.",
                "causal-alternatives",
            )
        )
    else:
        rows.append(
            _question(
                "Are you trying to describe, predict, compare, or explain a cause?",
                "Those goals require different evidence and should not be silently substituted for one another.",
                "claim-type",
            )
        )
    if _UNIVERSAL.search(text):
        rows.append(
            _question(
                "Would a narrower version of the claim still matter if exceptions exist?",
                "Universal wording is fragile; a bounded claim can remain useful and honest.",
                "scope-narrowing",
            )
        )
    rows.append(
        _question(
            "What direct data, source record, code output, or observation could you realistically access first?",
            "The smallest reachable primary evidence usually reveals the next useful question at the lowest cost.",
            "first-direct-evidence",
        )
    )
    # Keep the intake approachable.  The audit will expose deeper requirements later.
    return rows[:6]


def formulation_templates(question: str) -> List[Dict[str, str]]:
    original = question.strip()
    return [
        {
            "type": "descriptive",
            "template": "Among [population] in [setting] during [time], what is the measured distribution or frequency of [outcome]?",
            "use_when": "The phenomenon itself is not yet measured reliably.",
        },
        {
            "type": "comparative",
            "template": "Under matched conditions, how does [outcome] differ between [group/condition A] and [baseline B]?",
            "use_when": "The question implies better, worse, more, less, or a meaningful contrast.",
        },
        {
            "type": "causal-or-mechanistic",
            "template": "Does changing [factor] alter [outcome] in [population/setting], compared with [control], and what result would favor an alternative explanation?",
            "use_when": "The intended claim is about cause or mechanism rather than association.",
        },
        {
            "type": "faithful-restatement",
            "template": original,
            "use_when": "Keep this untouched while testing clearer versions; editing quality is not evidence quality.",
        },
    ]


def intake_idea(
    root: Union[str, Path],
    question: str,
    *,
    title: str = "",
    privacy: str = "public",
) -> Dict[str, Any]:
    exact = question.strip()
    root_path = Path(root).expanduser()
    if not (root_path / PROJECT_FILE_NAME).exists():
        initialize_project(
            root_path,
            title=title or exact[:80] or "Untitled research question",
            question=exact,
            privacy=privacy,
        )
    paths = paths_for(root_path)
    project = load_project(paths.root)
    project["question"] = exact
    if title.strip():
        project["title"] = title.strip()
    framing = project.get("framing_review")
    if isinstance(framing, dict) and not str(framing.get("neutral_restatement", "")).strip():
        framing["neutral_restatement"] = exact
    save_project(
        paths.root,
        project,
        event="idea.intake_updated",
        details={"question_sha256": sha256_text(exact)},
    )

    intake_id = sha256_text(exact)[:20]
    value: Dict[str, Any] = {
        "schema": INTAKE_SCHEMA,
        "schema_version": 1,
        "intake_id": intake_id,
        "created_at_utc": utc_now(),
        "original_question": exact,
        "assessment": "unassessed-not-rejected",
        "principles": [
            "Writing polish, age, credentials, status, and confidence are not proxies for idea quality.",
            "Clarification is requested only where the answer changes the claim, evidence, control, or test.",
            "Novelty and truth remain open until direct evidence and a documented search support them.",
        ],
        "clarification_questions": clarification_questions(exact),
        "formulation_templates": formulation_templates(exact),
        "minimum_viable_path": [
            "Answer the clarification questions that materially change the design.",
            "Choose the narrowest useful formulation and write one possible falsifier.",
            "Acquire one directly inspectable primary artifact or make one small observation.",
            "Run `uriel audit --profile exploratory` and use the blockers as a research plan.",
        ],
    }
    destination = paths.state / "intake" / (intake_id + ".json")
    atomic_write_json(destination, value)
    append_ledger(
        paths.root,
        "idea.intake_preserved",
        {
            "intake_id": intake_id,
            "question_sha256": sha256_text(exact),
            "clarification_count": len(value["clarification_questions"]),
        },
    )
    return value
