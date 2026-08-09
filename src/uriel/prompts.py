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
    guard_path,
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
    "generic-web": (
        "Paste into a compatible web model session after reviewing its current privacy and retention terms. "
        "Never assume an unverified third-party endpoint is private."
    ),
    "sol-mode": (
        "Paste into the explicitly selected compatible web model session. This legacy provider label is an optional handoff mode, not a dependency, "
        "exclusive integration, privacy endorsement, capability guarantee, or permission to bypass the project's external-AI policy."
    ),
}

_EXTERNAL_PROVIDERS = {"generic-web", "sol-mode"}
_SENSITIVE_CLASSIFICATIONS = {"internal", "confidential", "restricted"}
MAX_PROMPT_BYTES = 128 * 1024
MAX_PROMPT_SOURCE_PROJECT_BYTES = 1024 * 1024
MAX_REVIEW_OUTPUT_BYTES = 128 * 1024


def _redacted_project(project: Mapping[str, Any], *, classification: str, include_sensitive: bool) -> Dict[str, Any]:
    if include_sensitive or classification == "public":
        return copy.deepcopy(dict(project))

    # This is intentionally an allowlist projection, not field-by-field
    # replacement inside a copy. New manifest fields therefore remain private
    # until they are deliberately classified and added here.
    def count_rows(name: str) -> int:
        rows = project.get(name)
        return len(rows) if isinstance(rows, list) else 0

    hypothesis = project.get("hypothesis")
    methods = project.get("methods")
    novelty = project.get("novelty_review")
    submission = project.get("submission")
    privacy = project.get("privacy")
    return {
        "schema": "uriel.redacted_project_projection.v1",
        "source_schema": project.get("schema"),
        "source_schema_version": project.get("schema_version"),
        "title": "[withheld: non-public project]",
        "question": "[withheld: use an authorized sanitized copy or explicitly include sensitive content]",
        "privacy": {
            "classification": classification,
            "external_ai": privacy.get("external_ai", "ask") if isinstance(privacy, Mapping) else "ask",
            "redaction_note_count": len(privacy.get("redaction_notes", []))
            if isinstance(privacy, Mapping) and isinstance(privacy.get("redaction_notes"), list)
            else 0,
        },
        "redacted_inventory": {
            "hypothesis_present": bool(hypothesis.get("statement")) if isinstance(hypothesis, Mapping) else False,
            "operational_definition_count": len(hypothesis.get("operational_definitions", {}))
            if isinstance(hypothesis, Mapping) and isinstance(hypothesis.get("operational_definitions"), Mapping)
            else 0,
            "success_criterion_count": len(hypothesis.get("success_criteria", []))
            if isinstance(hypothesis, Mapping) and isinstance(hypothesis.get("success_criteria"), list)
            else 0,
            "novelty_search_started": bool(novelty.get("status") not in (None, "", "not_started"))
            if isinstance(novelty, Mapping)
            else False,
            "claim_count": count_rows("claims"),
            "evidence_count": count_rows("evidence"),
            "assumption_count": count_rows("assumptions"),
            "alternative_explanation_count": count_rows("alternative_explanations"),
            "contradiction_count": count_rows("contradictions"),
            "adversarial_test_count": count_rows("adversarial_tests"),
            "reviewer_objection_count": count_rows("reviewer_objections"),
            "limitation_count": count_rows("limitations"),
            "completed_method_field_count": sum(bool(value) for value in methods.values())
            if isinstance(methods, Mapping)
            else 0,
            "target_venue_count": len(submission.get("target_venues", []))
            if isinstance(submission, Mapping) and isinstance(submission.get("target_venues"), list)
            else 0,
            "author_count": len(submission.get("author_names", []))
            if isinstance(submission, Mapping) and isinstance(submission.get("author_names"), list)
            else 0,
            "workload_count": count_rows("workloads"),
            "external_review_count": count_rows("external_reviews"),
            "waiver_count": count_rows("waivers"),
        },
        "privacy_export_note": (
            "All project free text, identifiers, paths, locators, methods, disclosures, ethics details, submission details, "
            "and unknown fields were omitted. Create and independently review a separate sanitized copy when content is required."
        ),
    }


def build_prompt(
    root: Union[str, Path],
    *,
    task: str,
    provider: str = "generic",
    acknowledge_external: bool = False,
    include_sensitive: bool = False,
    model: str = "",
) -> Dict[str, Any]:
    if task not in REVIEW_TASKS:
        raise Refusal("Unknown prompt task: {0}".format(task), code="INVALID_PROMPT_TASK")
    if provider not in _PROVIDER_NOTES:
        raise Refusal("Unknown prompt provider: {0}".format(provider), code="INVALID_PROMPT_PROVIDER")

    paths = paths_for(root)
    project_path = guard_path(paths.root, paths.project, must_exist=True)
    project_bytes = project_path.stat().st_size
    if project_bytes > MAX_PROMPT_SOURCE_PROJECT_BYTES:
        raise Refusal(
            "The project manifest exceeds Uriel's bounded prompt-source budget.",
            code="PROMPT_SOURCE_PROJECT_TOO_LARGE",
            details={
                "project_bytes": project_bytes,
                "maximum_bytes": MAX_PROMPT_SOURCE_PROJECT_BYTES,
            },
            repairs=[
                "Use `uriel burst` to select only the exact records needed for this task.",
                "Create a smaller sanitized project copy for the review handoff.",
                "Use the deterministic audit and a human reviewer without exporting the full project manifest.",
            ],
        )
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
    if include_sensitive and classification != "public" and provider != "local" and not acknowledge_external:
        raise Refusal(
            "Sensitive prompt export requires an explicit external-risk acknowledgement.",
            code="SENSITIVE_PROMPT_CONFIRMATION_REQUIRED",
        )

    exported = _redacted_project(
        project,
        classification=classification,
        include_sensitive=include_sensitive,
    )
    redacted = exported != project
    source = build_manifest(paths.root, persist=True)
    project_hash = sha256_file(paths.project)
    template = review_template(
        task=task,
        source_manifest_sha256=str(source["manifest_sha256"]),
        project_manifest_sha256=project_hash,
    )
    template["provider"] = provider
    template["model"] = model
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
13. Do not run shell commands, modify files, or access unrelated local data. Use browsing or other tools only when the operator explicitly enabled them for this task.
14. Keep the complete response below {max_output_bytes} UTF-8 bytes.

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
        max_output_bytes=MAX_REVIEW_OUTPUT_BYTES,
    )
    prompt_bytes = len(prompt.encode("utf-8"))
    if prompt_bytes > MAX_PROMPT_BYTES:
        raise Refusal(
            "The generated review prompt exceeds Uriel's hard context budget.",
            code="PROMPT_BUDGET_EXCEEDED",
            details={"prompt_bytes": prompt_bytes, "maximum_bytes": MAX_PROMPT_BYTES},
            repairs=[
                "Use one bounded `uriel burst` packet for the exact rows or records needed by the task.",
                "Create a smaller sanitized project copy containing one claim and its minimum evidence metadata.",
                "Complete the review with Uriel's deterministic audit and a human reviewer without exporting the manifest.",
            ],
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
        "prompt_bytes": prompt_bytes,
        "maximum_prompt_bytes": MAX_PROMPT_BYTES,
        "maximum_review_output_bytes": MAX_REVIEW_OUTPUT_BYTES,
        "prompt_sha256": digest,
        "prompt_path": destination.relative_to(paths.root).as_posix(),
        "source_manifest_sha256": source["manifest_sha256"],
        "project_manifest_sha256": project_hash,
        "prompt": prompt,
    }
