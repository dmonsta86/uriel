"""Portable, hash-bound prompts for optional human or AI review.

Prompt export is outside Uriel's deterministic trust boundary.  The module
never chooses or endorses a provider, and it defaults to minimization for
non-public projects.  Review output remains untrusted until its citations and
content bindings are verified and imported.
"""
from __future__ import annotations

import copy
from pathlib import Path
from typing import Any, Dict, Mapping, Union

from .core import (
    Refusal,
    atomic_write,
    build_manifest,
    load_project,
    paths_for,
    pretty_json,
    sha256_file,
    sha256_text,
)
from .reviews import REVIEW_TASKS, review_template

_TASK_PURPOSES = {
    "clarity": "Turn a rough question into several faithful, testable formulations without dismissing the underlying idea.",
    "field-map": "Map the current field, nearest prior work, terminology changes, replications, failures, and unresolved gaps.",
    "primary-evidence": "Replace conclusion-on-conclusion citation chains with the earliest accessible primary data, methods, code, or archival records.",
    "contradiction-review": "Locate incompatible data, scope mismatches, control mismatches, exclusions, and interpretations that cannot all be true as written.",
    "adversarial-review": "Attack the strongest claims, assumptions, controls, edge cases, causal language, and missingness decisions in good faith.",
    "repair-review": "Convert current Uriel blockers into the smallest honest sequence of repairs without inflating any claim.",
    "submission-review": "Perform a final submission-level review of novelty scope, direct evidence, limitations, reproducibility, and likely reviewer objections.",
}

_PROVIDER_NOTES = {
    "generic": (
        "Use this with a human reviewer, an offline model, or a service you select. Uriel does not know where you will paste it; "
        "review privacy, retention, training use, jurisdiction, security, and cost before exporting it."
    ),
    "local": (
        "Use a model running on hardware you control. Confirm the runtime has no telemetry, cloud fallback, remote embeddings, or automatic sharing "
        "before treating it as offline."
    ),
    "opencode": (
        "Run through OpenCode only after selecting a provider/model yourself. Free availability and data-use terms can change. "
        "Run `opencode models`, read current provider terms, and never assume that a free endpoint is private."
    ),
    "chatgpt-web": (
        "Paste into ChatGPT Web only after reviewing current data controls and project authorization. For the strongest optional final pass, "
        "GPT-5.6 Sol at Very High reasoning, or GPT-5.6 Sol Pro is recommended when available; this is a capability suggestion, not a provider endorsement."
    ),
    "deepseek-web": (
        "Paste into a DeepSeek web session or another free service only after reviewing its current privacy terms. Break the work into one claim or "
        "one source at a time when the context or usage pool is small."
    ),
}

_EXTERNAL_PROVIDERS = {"opencode", "chatgpt-web", "deepseek-web"}
_SENSITIVE_CLASSIFICATIONS = {"internal", "confidential", "restricted"}


def _redacted_project(project: Mapping[str, Any], *, classification: str, include_sensitive: bool) -> Dict[str, Any]:
    value: Dict[str, Any] = copy.deepcopy(dict(project))
    if include_sensitive or classification == "public":
        return value

    value["title"] = "[withheld: non-public project]"
    value["question"] = "[withheld: use a local model or create an authorized sanitized copy]"
    hypothesis = value.get("hypothesis")
    if isinstance(hypothesis, dict):
        hypothesis["statement"] = "[withheld]"
        definitions = hypothesis.get("operational_definitions")
        if isinstance(definitions, dict):
            hypothesis["operational_definitions"] = {key: "[withheld]" for key in definitions}
    framing = value.get("framing_review")
    if isinstance(framing, dict):
        framing["neutral_restatement"] = "[withheld]"
        framing["competing_frames"] = ["[withheld]"] if framing.get("competing_frames") else []
    for field in ("claims", "assumptions", "alternative_explanations", "contradictions", "reviewer_objections", "limitations"):
        rows = value.get(field)
        if isinstance(rows, list):
            for row in rows:
                if not isinstance(row, dict):
                    continue
                for key in ("statement", "description", "reasoning", "reconciliation", "response", "mitigation", "implication", "test"):
                    if row.get(key):
                        row[key] = "[withheld]"
    evidence_rows = value.get("evidence")
    if isinstance(evidence_rows, list):
        for row in evidence_rows:
            if not isinstance(row, dict):
                continue
            for key in ("artifact_path", "source_locator", "description", "extraction", "data_location", "interpretation"):
                if row.get(key):
                    row[key] = "[withheld]"
    submission = value.get("submission")
    if isinstance(submission, dict):
        submission["author_names"] = ["[withheld]"] if submission.get("author_names") else []
        if submission.get("corresponding_author"):
            submission["corresponding_author"] = "[withheld]"
    value["privacy_export_note"] = (
        "Non-public research content was removed. Use a genuinely offline model or create a separately reviewed sanitized copy for useful assistance."
    )
    return value


def build_prompt(
    root: Union[str, Path],
    *,
    task: str,
    provider: str = "generic",
    acknowledge_external: bool = False,
    include_sensitive: bool = False,
) -> Dict[str, Any]:
    if task not in REVIEW_TASKS:
        raise Refusal("Unknown prompt task: {0}".format(task), code="INVALID_PROMPT_TASK")
    if provider not in _PROVIDER_NOTES:
        raise Refusal("Unknown prompt provider: {0}".format(provider), code="INVALID_PROMPT_PROVIDER")

    paths = paths_for(root)
    project = load_project(paths.root)
    privacy = project.get("privacy") if isinstance(project.get("privacy"), Mapping) else {}
    classification = str(privacy.get("classification", "public")).casefold()
    external_policy = str(privacy.get("external_ai", "ask")).casefold()
    external = provider in _EXTERNAL_PROVIDERS

    if external and external_policy == "deny":
        raise Refusal(
            "The project manifest explicitly denies external AI use.",
            code="EXTERNAL_AI_DENIED",
            repairs=[
                "Use Uriel's deterministic offline audit and a human reviewer.",
                "Use a genuinely local model with `--provider local` and verify that it has no remote fallback.",
                "Change the policy only through an authorized project decision and record the reason in version control.",
            ],
        )
    if external and classification in _SENSITIVE_CLASSIFICATIONS and not acknowledge_external:
        raise Refusal(
            "This project is {0}; Uriel will not prepare a prompt for an external service without an explicit acknowledgement.".format(classification),
            code="EXTERNAL_AI_PRIVACY_ACK_REQUIRED",
            repairs=[
                "Use `--provider local` with a verified offline runtime.",
                "Create a sanitized public copy containing only the minimum non-sensitive claim and evidence metadata.",
                "Rerun with `--acknowledge-external` only after reviewing current provider terms and confirming project authorization.",
            ],
        )
    if include_sensitive and classification != "public" and provider not in {"local", "generic"} and not acknowledge_external:
        raise Refusal(
            "Sensitive prompt export requires an explicit external-risk acknowledgement.",
            code="SENSITIVE_PROMPT_CONFIRMATION_REQUIRED",
        )

    exported = _redacted_project(
        project,
        classification=classification,
        include_sensitive=include_sensitive or provider == "local",
    )
    redacted = exported != project
    source = build_manifest(paths.root, persist=True)
    project_hash = sha256_file(paths.project)
    template = review_template(
        task=task,
        source_manifest_sha256=str(source["manifest_sha256"]),
        project_manifest_sha256=project_hash,
    )
    privacy_notice = (
        "Uriel does not endorse any model or provider. Terms, retention, training use, jurisdiction, security, availability, and price can change. "
        "Do not submit personal, confidential, unpublished, regulated, export-controlled, or contract-restricted material unless the chosen deployment "
        "is authorized for it. For sensitive work, prefer a verified offline model or an institutionally approved provider."
    )
    prompt = """# Uriel optional review task: {task}

## Purpose
{purpose}

## Privacy and provider warning

{privacy_notice}

Provider/use note: {provider_note}

## Non-negotiable review rules

1. Preserve the author's original question before proposing clearer alternatives. A rough question may contain a valuable idea; do not judge intelligence, age, status, credentials, or writing polish.
2. Do not declare the work true, globally novel, or submission-ready. Return candidate evidence and bounded findings only.
3. Prefer primary data, original methods, code output, registries, archival records, official standards, and first-party measurements. Use reviews mainly to locate the underlying primary evidence.
4. Keep every claim modular. Separate source extraction, source-author interpretation, independent interpretation, assumption, inference, counterevidence, and limitation.
5. Never invent a quotation, DOI, URL, page, table, value, model output, search result, or experiment. Mark anything not directly inspected as UNVERIFIED.
6. For each external source, provide an exact locator, retrieval date, and the smallest useful verbatim excerpt or datapoint. Do not reproduce long copyrighted passages.
7. Search against the preferred claim with the same care used to search for support. Look for omitted data, null or negative results, control and population mismatches, exclusion changes, contradictions, causal overreach, and framing effects.
8. Treat a logical fallacy as a precise defect in an argument, never as an insult to its author.
9. Give exactly three practical repair options for every blocker, including a minimal-cost path where possible.
10. Never issue a Uriel Blessing or say a Gate passed. Your output is untrusted until its locators and artifacts are independently verified.
11. Return only one JSON object matching the contract below. Do not wrap it in Markdown fences.
12. Separate observation from inference and state uncertainty honestly.

## Content binding

- Source manifest SHA-256: `{source_sha}`
- Source record-set SHA-256: `{records_sha}`
- Project manifest SHA-256: `{project_sha}`
- Privacy classification: `{privacy}`
- Export redacted: `{redacted}`
- External-AI policy: `{external_policy}`

## Project manifest

```json
{project_json}```

## Required output contract

```json
{contract}```
""".format(
        task=task,
        purpose=_TASK_PURPOSES[task],
        privacy_notice=privacy_notice,
        provider_note=_PROVIDER_NOTES[provider],
        source_sha=source["manifest_sha256"],
        records_sha=source["records_sha256"],
        project_sha=project_hash,
        privacy=classification,
        redacted=str(redacted).lower(),
        external_policy=external_policy,
        project_json=pretty_json(exported),
        contract=pretty_json(template),
    )
    digest = sha256_text(prompt)
    destination = paths.prompts / "{0}-{1}.md".format(task, digest[:16])
    atomic_write(destination, prompt)
    return {
        "task": task,
        "provider": provider,
        "provider_endorsement": False,
        "external_service": external,
        "privacy_classification": classification,
        "redacted": redacted,
        "prompt_sha256": digest,
        "prompt_path": destination.relative_to(paths.root).as_posix(),
        "source_manifest_sha256": source["manifest_sha256"],
        "project_manifest_sha256": project_hash,
        "prompt": prompt,
    }
