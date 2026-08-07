"""Deterministic Three Gates audit engine for Uriel.

The engine is intentionally conservative and inspectable.  It does not decide
whether an author, institution, or question is worthy.  It decides whether the
*current project record* contains enough explicit, content-bound material to
support the claims made at the selected audit profile.
"""
from __future__ import annotations

import datetime as _dt
import difflib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from .core import (
    IntegrityError,
    Refusal,
    append_ledger,
    atomic_write,
    atomic_write_json,
    build_index,
    build_manifest,
    canonical_json,
    guard_path,
    latest_receipts,
    load_project,
    paths_for,
    read_json,
    safe_relative_path,
    sha256_file,
    sha256_text,
    sync_reminders,
    utc_now,
    verify_receipt,
    verify_source_manifest,
)
from .findings import AuditReport, Finding, GateResult
from .schema import validate_manifest

AUDIT_SCHEMA = "uriel.audit.v1"
POLICY_VERSION = "uriel-three-gates-1.0.0"
PROFILES = ("exploratory", "standard", "strict", "submission")
SECONDARY_SOURCE_TYPES = {
    "secondary",
    "secondary_conclusion",
    "review_article",
    "commentary",
    "news_summary",
    "model_summary",
}

_PLACEHOLDER_RE = re.compile(
    r"(?:\b(?:todo|tbd|fixme|lorem\s+ipsum|fill\s+this|replace\s+me|example\s+only)\b|"
    r"10\.0000/(?:replace|example)|<[^>]*(?:insert|replace)[^>]*>)",
    re.IGNORECASE,
)
_VAGUE_RE = re.compile(
    r"\b(?:better|improved|significant|robust|scalable|effective|efficient|"
    r"state[- ]of[- ]the[- ]art|good|bad|large|small|normal|obvious)\b",
    re.IGNORECASE,
)
_ABSOLUTE_RE = re.compile(
    r"\b(?:always|never|everyone|nobody|all cases|no exceptions|guarantee[sd]?|"
    r"undeniably|unquestionably|conclusively proves?|100\s*%)\b",
    re.IGNORECASE,
)
_GLOBAL_NOVELTY_RE = re.compile(
    r"\b(?:first[- ]ever|world'?s first|unprecedented|revolutionary|best in the world|"
    r"entirely novel|no one has ever)\b",
    re.IGNORECASE,
)
_CAUSAL_RE = re.compile(
    r"\b(?:causes?|caused|causal|leads? to|produces?|prevents?|drives?|because of)\b",
    re.IGNORECASE,
)
_LOADED_RE = re.compile(
    r"\b(?:obviously|merely|just|dumb|stupid|lazy|corrupt|fraudulent|fake|"
    r"agenda|propaganda|common sense)\b",
    re.IGNORECASE,
)
_FALLACIES: Sequence[Tuple[str, re.Pattern[str], str]] = (
    (
        "POPULARITY_AS_EVIDENCE",
        re.compile(r"\b(?:everyone (?:knows|agrees?)|most people agree|widely believed|common knowledge)\b.{0,100}\b(?:therefore|proves?|must be true)\b", re.I | re.S),
        "Popularity or familiarity is not direct evidence for a claim.",
    ),
    (
        "AUTHORITY_AS_PROOF",
        re.compile(r"\b(?:experts say|a famous|the consensus says)\b.{0,100}\b(?:therefore|proves?)\b", re.I | re.S),
        "An authority statement may guide a search, but it does not replace the underlying data or method.",
    ),
    (
        "ABSENCE_AS_PROOF",
        re.compile(r"\bno evidence\b.{0,120}\b(?:therefore|proves?|means)\b", re.I | re.S),
        "Not observing evidence is not automatically evidence of the opposite unless detection power is established.",
    ),
    (
        "FALSE_DILEMMA",
        re.compile(r"\b(?:either\b.{0,100}\bor\b.{0,100}\bno other|only two possibilities|if not .{0,80} then)\b", re.I | re.S),
        "The wording appears to exclude alternatives without documenting why they are impossible.",
    ),
    (
        "AD_HOMINEM",
        re.compile(r"\b(?:idiot|stupid|ignorant|dishonest)\s+(?:reviewer|author|critic|researcher)s?\b", re.I),
        "A person's character does not resolve the evidence question.",
    ),
    (
        "CIRCULAR_SUPPORT",
        re.compile(r"\b(?:true because it is true|works because it works|valid because it is valid)\b", re.I),
        "The conclusion is being used as its own support.",
    ),
)


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _items(value: Any) -> List[Any]:
    return list(value) if isinstance(value, list) else []


def _objects(value: Any) -> List[Mapping[str, Any]]:
    return [item for item in _items(value) if isinstance(item, Mapping)]


def _is_na(value: str) -> bool:
    return value.casefold().startswith(("not_applicable:", "not applicable:", "n/a:")) and len(value.split(":", 1)[-1].strip()) >= 8


def _enough(value: Any, minimum: int) -> bool:
    return len(_text(value)) >= minimum


def _repairs(*values: str) -> List[str]:
    result = [value for value in values if value]
    while len(result) < 3:
        result.append("Narrow the affected claim, record the missing evidence, and rerun the audit.")
    return result[:3]


def _finding(
    gate: int,
    code: str,
    subject: str,
    message: str,
    *,
    severity: str = "blocker",
    status: str = "FAIL",
    evidence: Optional[Iterable[str]] = None,
    repairs: Optional[Sequence[str]] = None,
) -> Finding:
    return Finding(
        code=code,
        gate=gate,
        severity=severity,
        status=status,
        subject=subject,
        message=message,
        evidence=list(evidence or []),
        repairs=_repairs(*(repairs or [])),
    )


def _walk_strings(value: Any, pointer: str = "") -> Iterable[Tuple[str, str]]:
    if isinstance(value, str):
        yield pointer or "/", value
    elif isinstance(value, Mapping):
        for key, child in value.items():
            escaped = str(key).replace("~", "~0").replace("/", "~1")
            for item in _walk_strings(child, pointer + "/" + escaped):
                yield item
    elif isinstance(value, list):
        for index, child in enumerate(value):
            for item in _walk_strings(child, pointer + "/" + str(index)):
                yield item


def _claim_map(project: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    return {str(row.get("id")): row for row in _objects(project.get("claims")) if row.get("id")}


def _evidence_map(project: Mapping[str, Any]) -> Dict[str, Mapping[str, Any]]:
    return {str(row.get("id")): row for row in _objects(project.get("evidence")) if row.get("id")}


def _severity(profile: str, exploratory_warning: bool = True) -> Tuple[str, str]:
    if profile == "exploratory" and exploratory_warning:
        return "warning", "WARN"
    return "blocker", "FAIL"


def _valid_iso_date(value: str) -> bool:
    try:
        _dt.date.fromisoformat(value)
        return True
    except (TypeError, ValueError):
        return False


def _gate_status(findings: Sequence[Finding]) -> str:
    return "FAIL" if any(item.severity == "blocker" and item.status == "FAIL" for item in findings) else "PASS"


def _gate1(project: Mapping[str, Any], profile: str, schema_errors: Sequence[Mapping[str, str]]) -> GateResult:
    findings: List[Finding] = []
    for error in schema_errors:
        findings.append(
            _finding(
                1,
                "SCHEMA_STRUCTURE",
                "Project structure",
                "The project record cannot be audited reliably because {0} {1}.".format(
                    error.get("path", "/"), error.get("message", "is invalid")
                ),
                evidence=[str(error.get("path", "/"))],
                repairs=[
                    "Correct the named JSON field while preserving the declared uriel.project.v1 structure.",
                    "Run `uriel validate --root .` after each structural edit to isolate the first remaining error.",
                    "Compare the field with `docs/MANIFEST_REFERENCE.md` and the packaged JSON Schema.",
                ],
            )
        )

    question = _text(project.get("question"))
    hypothesis = project.get("hypothesis") if isinstance(project.get("hypothesis"), Mapping) else {}
    statement = _text(hypothesis.get("statement"))
    falsifier = _text(hypothesis.get("falsifier"))
    definitions = hypothesis.get("operational_definitions") if isinstance(hypothesis.get("operational_definitions"), Mapping) else {}
    criteria = [str(item).strip() for item in _items(hypothesis.get("success_criteria")) if _text(item)]

    if len(question) < 8:
        findings.append(
            _finding(
                1,
                "QUESTION_UNDERSPECIFIED",
                "Research question",
                "The current wording is too short to identify what would be examined. This does not make the idea unserious; it only leaves the object of inquiry ambiguous.",
                evidence=["/question"],
                repairs=[
                    "State what changes, for whom or what, and under which setting.",
                    "Write two plausible interpretations and choose the one the project actually tests.",
                    "Use `uriel prompt clarify` to generate a no-cost clarification worksheet without changing the idea for you.",
                ],
            )
        )
    if len(statement) < 24:
        findings.append(
            _finding(
                1,
                "HYPOTHESIS_UNDERSPECIFIED",
                "Hypothesis",
                "A testable statement is not yet explicit enough for another person to determine what result would count for or against it.",
                evidence=["/hypothesis/statement"],
                repairs=[
                    "Rewrite the hypothesis as a bounded relationship between named, measurable quantities.",
                    "Separate the motivating question from the specific proposition being tested.",
                    "Create a minimal pilot hypothesis and label broader ideas as future work rather than forcing them into one claim.",
                ],
            )
        )
    if len(falsifier) < 16:
        findings.append(
            _finding(
                1,
                "FALSIFIER_MISSING",
                "Falsifiability",
                "The record does not yet say what observation would make the hypothesis fail or require revision.",
                evidence=["/hypothesis/falsifier"],
                repairs=[
                    "Name a concrete observation, threshold, or pattern that would contradict the hypothesis.",
                    "For an exploratory project, state which result would stop escalation to a larger study.",
                    "For a software claim, identify the test or invariant whose failure rejects the claim.",
                ],
            )
        )
    if not definitions:
        severity, status = _severity(profile)
        findings.append(
            _finding(
                1,
                "OPERATIONAL_DEFINITIONS_MISSING",
                "Operational definitions",
                "Key terms are not tied to observable measurements or decision rules, so different readers could test different propositions.",
                severity=severity,
                status=status,
                evidence=["/hypothesis/operational_definitions"],
                repairs=[
                    "Define each central term using a measurement, classification rule, or observable behavior.",
                    "Where no direct measure exists, name the proxy and the ways it may diverge from the intended concept.",
                    "Add a small glossary whose entries can be independently applied to the same data.",
                ],
            )
        )
    if not criteria:
        severity, status = _severity(profile)
        findings.append(
            _finding(
                1,
                "SUCCESS_CRITERIA_MISSING",
                "Decision criteria",
                "No predeclared criterion distinguishes a supportive result from an inconclusive or contrary result.",
                severity=severity,
                status=status,
                evidence=["/hypothesis/success_criteria"],
                repairs=[
                    "Add at least one measurable threshold and its unit before examining final results.",
                    "Declare a qualitative decision rubric with examples if numeric thresholds are not appropriate.",
                    "Mark the project as exploratory and state the rule for deciding whether a confirmatory study is justified.",
                ],
            )
        )

    framing = project.get("framing_review") if isinstance(project.get("framing_review"), Mapping) else {}
    neutral = _text(framing.get("neutral_restatement"))
    competing = [_text(item) for item in _items(framing.get("competing_frames")) if _text(item)]
    boundaries = [_text(item) for item in _items(framing.get("scope_boundaries")) if _text(item)]
    if len(neutral) < 16:
        findings.append(
            _finding(
                1,
                "NEUTRAL_FRAME_MISSING",
                "Framing",
                "The question has not been restated in neutral, outcome-agnostic language. That makes confirmation bias harder to detect.",
                evidence=["/framing_review/neutral_restatement"],
                repairs=[
                    "Restate the question without implying which answer is desirable, foolish, moral, or inevitable.",
                    "Describe the variables before naming a preferred explanation.",
                    "Ask a second reader to rewrite the question from a competing perspective and retain both versions.",
                ],
            )
        )
    if profile in {"strict", "submission"} and not competing:
        findings.append(
            _finding(
                1,
                "COMPETING_FRAME_MISSING",
                "Competing interpretations",
                "No plausible alternative framing is recorded, so hidden assumptions in the preferred wording remain untested.",
                evidence=["/framing_review/competing_frames"],
                repairs=[
                    "Record at least one good-faith alternative framing that could lead to a different design or interpretation.",
                    "Reframe the question from the perspective of an affected group or skeptical reviewer.",
                    "State why the chosen frame is useful without claiming the alternatives are illegitimate.",
                ],
            )
        )
    if profile != "exploratory" and not boundaries:
        findings.append(
            _finding(
                1,
                "SCOPE_BOUNDARIES_MISSING",
                "Scope boundaries",
                "The record does not identify where the claim should stop applying.",
                evidence=["/framing_review/scope_boundaries"],
                repairs=[
                    "Name populations, settings, time periods, or implementations that are outside the claim.",
                    "Separate tested scope from hoped-for generalization.",
                    "Add an explicit non-claim for the nearest tempting overgeneralization.",
                ],
            )
        )

    scan_targets = {
        "/question": question,
        "/hypothesis/statement": statement,
        "/hypothesis/falsifier": falsifier,
        "/framing_review/neutral_restatement": neutral,
    }
    for claim in _objects(project.get("claims")):
        scan_targets["/claims/{0}/statement".format(claim.get("id", "?"))] = _text(claim.get("statement"))
        scan_targets["/claims/{0}/reasoning".format(claim.get("id", "?"))] = _text(claim.get("reasoning"))
    for pointer, text in scan_targets.items():
        if not text:
            continue
        if _PLACEHOLDER_RE.search(text):
            findings.append(
                _finding(
                    1,
                    "PLACEHOLDER_LANGUAGE",
                    "Incomplete wording",
                    "Placeholder text remains in a claim-bearing field, so the current proposition is not final enough to audit.",
                    evidence=[pointer],
                    repairs=[
                        "Replace the placeholder with the intended bounded statement.",
                        "Delete the field and narrow the project if the information is not available.",
                        "Move speculative wording into a clearly labeled future-work note.",
                    ],
                )
            )
        vague = sorted(set(match.group(0).casefold() for match in _VAGUE_RE.finditer(text)))
        if vague and not re.search(r"\b(?:defined as|measured by|threshold|compared with|relative to)\b", text, re.I):
            severity, status = _severity(profile, exploratory_warning=True)
            findings.append(
                _finding(
                    1,
                    "VAGUE_EVALUATIVE_TERM",
                    "Measurement clarity",
                    "The wording uses evaluative terms without an adjacent measurement rule: {0}.".format(", ".join(vague)),
                    severity=severity,
                    status=status,
                    evidence=[pointer],
                    repairs=[
                        "Replace each evaluative term with a metric, comparator, and unit.",
                        "Define the term in `operational_definitions` and cite that definition from the claim.",
                        "Remove the adjective and report the underlying quantity directly.",
                    ],
                )
            )
        if _ABSOLUTE_RE.search(text):
            findings.append(
                _finding(
                    1,
                    "UNBOUNDED_CERTAINTY",
                    "Claim boundary",
                    "Absolute language exceeds what a bounded project can establish without explicit universal coverage.",
                    evidence=[pointer],
                    repairs=[
                        "Replace the absolute with the tested population, setting, and uncertainty.",
                        "Document the complete coverage argument if the domain is genuinely finite and exhaustively checked.",
                        "Split the universal claim into a tested claim plus a separately labeled conjecture.",
                    ],
                )
            )
        if _GLOBAL_NOVELTY_RE.search(text):
            findings.append(
                _finding(
                    1,
                    "GLOBAL_NOVELTY_OVERCLAIM",
                    "Novelty scope",
                    "Global novelty language cannot be earned by a local search record; novelty must be stated within the declared search scope.",
                    evidence=[pointer],
                    repairs=[
                        "Change the wording to `not found in the declared searches as of DATE`.",
                        "Expand the documented search across relevant databases, terminology, dates, and languages.",
                        "Remove the priority claim and state the narrower technical distinction instead.",
                    ],
                )
            )
        if _LOADED_RE.search(text) and pointer != "/question":
            severity, status = _severity(profile)
            findings.append(
                _finding(
                    1,
                    "LOADED_FRAMING",
                    "Framing language",
                    "The field contains language that may smuggle evaluation into the premise instead of testing it.",
                    severity=severity,
                    status=status,
                    evidence=[pointer],
                    repairs=[
                        "Replace labels with observable behavior or measured properties.",
                        "Describe the strongest neutral version of the opposing interpretation.",
                        "Move moral or policy judgments into a separate discussion after the empirical result.",
                    ],
                )
            )
        for code, pattern, explanation in _FALLACIES:
            if pattern.search(text):
                findings.append(
                    _finding(
                        1,
                        code,
                        "Reasoning structure",
                        explanation,
                        evidence=[pointer],
                        repairs=[
                            "Rewrite the sentence so the conclusion follows from an identified datum or valid inference rule.",
                            "Separate the observation, assumption, and conclusion into three explicit statements.",
                            "Add a counterexample that would expose whether the inference is actually necessary.",
                        ],
                    )
                )

    novelty = project.get("novelty_review") if isinstance(project.get("novelty_review"), Mapping) else {}
    status_value = _text(novelty.get("status")).casefold()
    databases = [_text(item) for item in _items(novelty.get("databases")) if _text(item)]
    queries = [_text(item) for item in _items(novelty.get("queries")) if _text(item)]
    prior = [_text(item) for item in _items(novelty.get("nearest_prior_work")) if _text(item)]
    differences = [_text(item) for item in _items(novelty.get("differentiators")) if _text(item)]
    negative = [_text(item) for item in _items(novelty.get("negative_searches")) if _text(item)]
    search_date = _text(novelty.get("search_date"))
    if profile == "exploratory":
        if status_value not in {"complete", "in_progress"}:
            findings.append(
                _finding(
                    1,
                    "NOVELTY_SEARCH_NOT_STARTED",
                    "State of the field",
                    "No prior-work search is recorded yet. The question can still be worth pursuing, but novelty is presently unknown.",
                    severity="warning",
                    status="WARN",
                    evidence=["/novelty_review"],
                    repairs=[
                        "Run a small terminology search and record the exact databases, dates, and queries.",
                        "Collect the nearest contrary and supporting work rather than only papers that use the same framing.",
                        "Use `uriel prompt field-map` with a free model, then independently verify every returned locator.",
                    ],
                )
            )
    else:
        if status_value != "complete" or not _valid_iso_date(search_date):
            findings.append(
                _finding(
                    1,
                    "NOVELTY_SEARCH_INCOMPLETE",
                    "State of the field",
                    "The novelty review is not marked complete with a valid ISO search date, so the novelty claim is not time-bounded or reproducible.",
                    evidence=["/novelty_review/status", "/novelty_review/search_date"],
                    repairs=[
                        "Record the search date as YYYY-MM-DD and mark complete only after reviewing the results.",
                        "Keep an artifact containing the exact query strings and result-selection rules.",
                        "State that novelty is limited to the declared databases and date.",
                    ],
                )
            )
        min_databases = 2 if profile in {"strict", "submission"} else 1
        min_queries = 2 if profile in {"strict", "submission"} else 1
        if len(databases) < min_databases or len(queries) < min_queries or not prior or not differences:
            findings.append(
                _finding(
                    1,
                    "NOVELTY_SEARCH_THIN",
                    "Prior-work coverage",
                    "The search record does not yet contain enough databases, exact queries, nearest work, and explicit distinctions for this audit profile.",
                    evidence=["/novelty_review/databases", "/novelty_review/queries", "/novelty_review/nearest_prior_work", "/novelty_review/differentiators"],
                    repairs=[
                        "Add the exact queries and at least the minimum independent search surfaces required by the profile.",
                        "Record the nearest work even when it weakens the novelty story, then identify the precise difference.",
                        "Search synonyms, earlier terminology, adjacent disciplines, and null/negative results.",
                    ],
                )
            )
        if profile == "submission" and not negative:
            findings.append(
                _finding(
                    1,
                    "NEGATIVE_SEARCH_MISSING",
                    "Disconfirming literature search",
                    "The submission record does not show a search designed to find prior work or evidence that would defeat the novelty claim.",
                    evidence=["/novelty_review/negative_searches"],
                    repairs=[
                        "Add queries built around likely counterclaims, failures, replications, and older terminology.",
                        "Ask an independent reviewer to search for the closest collision and preserve their exact locators.",
                        "Narrow the novelty claim to what survived the documented disconfirming search.",
                    ],
                )
            )

    # Similar near-duplicate claims can conceal circular restatement.
    claims = _objects(project.get("claims"))
    for left_index, left in enumerate(claims):
        left_text = _text(left.get("statement"))
        if not left_text:
            continue
        for right in claims[left_index + 1 :]:
            right_text = _text(right.get("statement"))
            if not right_text:
                continue
            ratio = difflib.SequenceMatcher(None, left_text.casefold(), right_text.casefold()).ratio()
            if ratio >= 0.92:
                findings.append(
                    _finding(
                        1,
                        "DUPLICATE_CLAIM",
                        "Claim modularity",
                        "Claims {0} and {1} are nearly identical, which makes evidence mapping and independent falsification ambiguous.".format(left.get("id"), right.get("id")),
                        severity="warning" if profile == "exploratory" else "blocker",
                        status="WARN" if profile == "exploratory" else "FAIL",
                        evidence=[str(left.get("id")), str(right.get("id"))],
                        repairs=[
                            "Merge the claims and keep one evidence map.",
                            "Rewrite each claim so it has a distinct scope, outcome, or falsifier.",
                            "Make one claim a premise and the other a conclusion, then document the inference between them.",
                        ],
                    )
                )

    return GateResult(
        gate=1,
        name="Novelty & Clarity",
        status=_gate_status(findings),
        scope_note="Checks inspect declared wording, definitions, scope, and the reproducibility of the prior-work search. They do not prove universal novelty.",
        findings=findings,
    )


def _gate2(
    root: Path,
    project: Mapping[str, Any],
    profile: str,
    source_manifest: Mapping[str, Any],
) -> GateResult:
    findings: List[Finding] = []
    claims = _claim_map(project)
    evidence_map = _evidence_map(project)
    source_rows = {
        str(row.get("relative_path")): row
        for row in _objects(source_manifest.get("records"))
        if row.get("relative_path")
    }

    if not claims:
        findings.append(
            _finding(
                2,
                "CLAIMS_MISSING",
                "Claim ledger",
                "No modular claims are declared, so evidence cannot be traced to a specific proposition.",
                repairs=[
                    "Add one bounded claim with its own scope, falsifier, and reasoning.",
                    "Split a broad conclusion into independently testable claim units.",
                    "Keep exploratory observations separate from claims that request publication-level support.",
                ],
            )
        )
    if not evidence_map:
        severity, status = _severity(profile)
        findings.append(
            _finding(
                2,
                "EVIDENCE_MISSING",
                "Evidence ledger",
                "No evidence records are declared. An idea may still deserve investigation, but no result can be certified from an empty evidence chain.",
                severity=severity,
                status=status,
                repairs=[
                    "Add a project-local data, code, protocol, or primary-source artifact and record its exact location.",
                    "For a new project, label proposed measurements as planned and do not state results yet.",
                    "Use `uriel prompt primary-evidence` to produce a search plan, then verify and import the underlying artifacts yourself.",
                ],
            )
        )

    for evidence_id, row in evidence_map.items():
        artifact = _text(row.get("artifact_path"))
        if not artifact:
            findings.append(
                _finding(
                    2,
                    "EVIDENCE_ARTIFACT_MISSING",
                    "Evidence {0}".format(evidence_id),
                    "The evidence record has no project-local artifact path, so the cited bytes are not available for independent inspection.",
                    evidence=[evidence_id],
                    repairs=[
                        "Copy the permissible source data or exact excerpt into `artifacts/` or `sources/` and record the path.",
                        "For restricted data, add a content-hashed access receipt and a precise data-location description without exposing protected content.",
                        "Remove the evidence from supported claims until a reviewer can reach the underlying artifact.",
                    ],
                )
            )
        else:
            try:
                safe_relative_path(artifact)
                path = guard_path(root, root / artifact, must_exist=True)
                if artifact not in source_rows:
                    findings.append(
                        _finding(
                            2,
                            "EVIDENCE_NOT_MANIFESTED",
                            "Evidence {0}".format(evidence_id),
                            "The artifact exists but is not part of the audited source manifest.",
                            evidence=[artifact],
                            repairs=[
                                "Run `uriel snapshot` after placing the artifact under the project root.",
                                "Remove ignored-directory placement and keep the artifact in `artifacts/` or `sources/`.",
                                "Replace the reference with a content-hashed access record if the raw data cannot be stored locally.",
                            ],
                        )
                    )
                else:
                    expected = source_rows[artifact]
                    actual_sha256 = sha256_file(path)
                    if actual_sha256 != expected.get("sha256"):
                        findings.append(
                            _finding(
                                2,
                                "EVIDENCE_HASH_MISMATCH",
                                "Evidence {0}".format(evidence_id),
                                "The artifact bytes no longer match the source manifest used by this audit.",
                                evidence=[artifact],
                                repairs=[
                                    "Treat the change as a new evidence version and create a fresh source snapshot.",
                                    "Restore the exact recorded artifact from a verified source.",
                                    "Document why the bytes changed and rerun every dependent workload before auditing again.",
                                ],
                            )
                        )
                    declared_sha256 = _text(row.get("sha256")).casefold()
                    if not re.fullmatch(r"[0-9a-f]{64}", declared_sha256) or declared_sha256 != actual_sha256:
                        findings.append(
                            _finding(
                                2,
                                "EVIDENCE_DECLARED_DIGEST_MISMATCH",
                                "Evidence {0}".format(evidence_id),
                                "The evidence record does not contain the SHA-256 digest of the exact project-local artifact bytes.",
                                evidence=[artifact, declared_sha256 or "missing"],
                                repairs=[
                                    "Re-add the artifact with `uriel add-evidence` so its digest is computed locally.",
                                    "Restore the artifact version named by the evidence record and verify its digest.",
                                    "Create a new evidence ID when the underlying bytes changed rather than silently reusing the old record.",
                                ],
                            )
                        )
            except Refusal as exc:
                findings.append(
                    _finding(
                        2,
                        "EVIDENCE_PATH_INVALID",
                        "Evidence {0}".format(evidence_id),
                        "The artifact path is unavailable or escapes the project boundary: {0}".format(exc),
                        evidence=[artifact],
                        repairs=[
                            "Use a real project-relative file rather than a symlink, junction, absolute path, or parent traversal.",
                            "Copy the exact evidence bytes into a confined project directory.",
                            "Remove the evidence mapping until the artifact can be preserved safely.",
                        ],
                    )
                )

        for field, minimum, code, label in (
            ("source_locator", 6, "SOURCE_LOCATOR_MISSING", "stable source locator"),
            ("data_location", 4, "DATA_LOCATION_MISSING", "page, table, row, commit, or record locator"),
            ("extraction", 8, "DIRECT_EXTRACTION_MISSING", "verbatim datum, value, or executable observation"),
            ("interpretation", 8, "INTERPRETATION_MISSING", "independent interpretation"),
            ("limitations", 8, "EVIDENCE_LIMITATIONS_MISSING", "evidence-specific limitation"),
        ):
            if not _enough(row.get(field), minimum):
                severity, status = _severity(profile)
                findings.append(
                    _finding(
                        2,
                        code,
                        "Evidence {0}".format(evidence_id),
                        "The record is missing a usable {0}; readers cannot distinguish the underlying datum from the author's interpretation.".format(label),
                        severity=severity,
                        status=status,
                        evidence=[evidence_id, "/evidence/{0}/{1}".format(evidence_id, field)],
                        repairs=[
                            "Record the exact source location and the smallest verbatim excerpt or numeric value needed for the claim.",
                            "Keep the source extraction and your interpretation in separate fields.",
                            "State what this evidence cannot establish and avoid extending the claim beyond it.",
                        ],
                    )
                )

    by_source: Dict[tuple, List[str]] = {}
    for evidence_id, row in evidence_map.items():
        artifact = _text(row.get("artifact_path"))
        locator = _text(row.get("source_locator"))
        if artifact and locator and bool(row.get("primary")):
            by_source.setdefault((artifact, locator), []).append(evidence_id)
    for (artifact, locator), duplicated in sorted(by_source.items()):
        if len(duplicated) < 2:
            continue
        severity, status = _severity(profile)
        findings.append(
            _finding(
                2,
                "DUPLICATE_CITATION_SOURCE",
                "Evidence {0}".format(", ".join(duplicated)),
                "Multiple evidence rows name the same primary artifact and source locator; they cannot be counted as independent evidence.",
                severity=severity,
                status=status,
                evidence=[artifact, locator, *duplicated],
                repairs=[
                    "Remove the duplicate row and keep one canonical evidence record per source location.",
                    "If the rows genuinely differ, give each a distinct source locator (page, row, commit, or record).",
                    "Count citations once when judging how many independent sources support the claim.",
                ],
            )
        )

    for claim_id, claim in claims.items():
        statement = _text(claim.get("statement"))
        if len(statement) < 16:            findings.append(
                _finding(
                    2,
                    "CLAIM_INCOMPLETE",
                    "Claim {0}".format(claim_id),
                    "The claim is too incomplete to map evidence without guessing what the author intended.",
                    evidence=[claim_id],
                    repairs=[
                        "Write one complete proposition with a bounded subject, outcome, and context.",
                        "Move motivations and implications out of the claim statement.",
                        "Delete the claim if it is not part of the result being defended.",
                    ],
                )
            )
        scope = claim.get("scope") if isinstance(claim.get("scope"), Mapping) else {}
        if profile != "exploratory" and any(not _enough(scope.get(key), 3) for key in ("population", "setting", "timeframe")):
            findings.append(
                _finding(
                    2,
                    "CLAIM_SCOPE_INCOMPLETE",
                    "Claim {0}".format(claim_id),
                    "Population, setting, or timeframe is missing, so evidence may be generalized beyond the observations that produced it.",
                    evidence=[claim_id],
                    repairs=[
                        "Fill all three scope fields using the actual evidence-generating context.",
                        "State unknown generalizability as a limitation rather than silently widening the claim.",
                        "Create separate claims for materially different populations or settings.",
                    ],
                )
            )
        if not _enough(claim.get("falsifier"), 12):
            findings.append(
                _finding(
                    2,
                    "CLAIM_FALSIFIER_MISSING",
                    "Claim {0}".format(claim_id),
                    "This individual claim has no recorded disconfirming condition.",
                    evidence=[claim_id],
                    repairs=[
                        "Name a result that would reject or materially narrow this claim.",
                        "Link the claim to a predeclared success criterion.",
                        "Mark the sentence as interpretation rather than a testable claim if it cannot be falsified.",
                    ],
                )
            )
        support_ids = [str(item) for item in _items(claim.get("evidence_ids"))]
        counter_ids = [str(item) for item in _items(claim.get("counterevidence_ids"))]
        unknown = [item for item in support_ids + counter_ids if item not in evidence_map]
        if unknown:
            findings.append(
                _finding(
                    2,
                    "UNKNOWN_EVIDENCE_REFERENCE",
                    "Claim {0}".format(claim_id),
                    "The claim references evidence identifiers that do not exist: {0}.".format(", ".join(sorted(set(unknown)))),
                    evidence=[claim_id] + unknown,
                    repairs=[
                        "Add the missing evidence records with artifact paths and source locations.",
                        "Correct typographical identifiers so each reference resolves exactly once.",
                        "Remove references that no longer support the current claim version.",
                    ],
                )
            )
        known_support = [evidence_map[item] for item in support_ids if item in evidence_map]
        if not known_support:
            severity, status = _severity(profile)
            findings.append(
                _finding(
                    2,
                    "CLAIM_UNSUPPORTED",
                    "Claim {0}".format(claim_id),
                    "No declared evidence record directly supports this claim.",
                    severity=severity,
                    status=status,
                    evidence=[claim_id],
                    repairs=[
                        "Attach direct evidence to the claim and preserve the underlying artifact.",
                        "Downgrade the sentence to a hypothesis or planned analysis rather than a result.",
                        "Remove the claim from the submission until supporting observations exist.",
                    ],
                )
            )
        if claim.get("importance") == "major" and known_support:
            direct_primary = [
                row
                for row in known_support
                if row.get("primary") is True and _text(row.get("directness")).casefold() == "direct"
            ]
            if not direct_primary:
                findings.append(
                    _finding(
                        2,
                        "MAJOR_CLAIM_LACKS_DIRECT_PRIMARY_EVIDENCE",
                        "Claim {0}".format(claim_id),
                        "The major claim is supported only by secondary, derived, or indirect material. Uriel does not let another author's conclusion substitute for the underlying observation when direct evidence is obtainable.",
                        evidence=[claim_id] + support_ids,
                        repairs=[
                            "Locate and cite the primary dataset, protocol, code output, archival record, or first-party measurement.",
                            "Narrow the claim to what the available indirect evidence actually establishes.",
                            "Label the statement as a literature-derived premise and keep it outside the independently verified result chain.",
                        ],
                    )
                )
        overlap = sorted(set(support_ids) & set(counter_ids))
        if overlap and not _enough(claim.get("reconciliation"), 16):
            findings.append(
                _finding(
                    2,
                    "UNRECONCILED_EVIDENCE_ROLE",
                    "Claim {0}".format(claim_id),
                    "The same evidence is listed as supporting and counterevidence without an explanation of which component points in each direction.",
                    evidence=[claim_id] + overlap,
                    repairs=[
                        "Split the evidence record into independently located observations with distinct roles.",
                        "Explain the mixed result and how the final claim was narrowed.",
                        "Mark the claim inconclusive until the contradiction is resolved.",
                    ],
                )
            )
        if known_support and any(_text(row.get("source_type")).casefold() in SECONDARY_SOURCE_TYPES for row in known_support):
            if all(_text(row.get("source_type")).casefold() in SECONDARY_SOURCE_TYPES for row in known_support):
                findings.append(
                    _finding(
                        2,
                        "SECONDARY_ONLY_SUPPORT",
                        "Claim {0}".format(claim_id),
                        "Every supporting record is secondary. This creates a conclusion-on-conclusion chain rather than a modular evidence chain.",
                        severity="warning" if profile == "exploratory" else "blocker",
                        status="WARN" if profile == "exploratory" else "FAIL",
                        evidence=[claim_id] + support_ids,
                        repairs=[
                            "Replace at least one secondary citation with the primary data or original method output.",
                            "State explicitly that the claim is a reported literature conclusion and do not present it as independently verified.",
                            "Document why primary evidence is inaccessible and narrow confidence accordingly.",
                        ],
                    )
                )

        if _CAUSAL_RE.search(statement):
            observational = any(_text(row.get("kind")).casefold() in {"observational", "correlational"} for row in known_support)
            causal_method = _text((project.get("methods") or {}).get("causal_identification")) if isinstance(project.get("methods"), Mapping) else ""
            if observational and not _enough(causal_method, 16):
                findings.append(
                    _finding(
                        2,
                        "CAUSAL_CLAIM_FROM_OBSERVATIONAL_EVIDENCE",
                        "Claim {0}".format(claim_id),
                        "Causal language is paired with observational evidence without a declared identification strategy.",
                        evidence=[claim_id] + support_ids,
                        repairs=[
                            "Change the claim to an association and state the unresolved confounding risk.",
                            "Add a defensible identification design with assumptions and falsification checks.",
                            "Collect randomized, natural-experiment, mechanistic, or other appropriately identifying evidence.",
                        ],
                    )
                )

    attestations = {}
    disclosures = project.get("disclosures")
    if isinstance(disclosures, Mapping) and isinstance(disclosures.get("attestations"), Mapping):
        attestations = disclosures.get("attestations")  # type: ignore[assignment]
    for field, subject, message in (
        ("all_known_material_data_declared", "Completeness attestation", "The author has not attested that all known material data—including inconvenient data—has been declared."),
        ("citations_checked_against_sources", "Citation verification", "The record does not attest that citations were checked against the cited source rather than copied from another bibliography."),
        ("no_claim_relies_only_on_another_authors_conclusion", "Direct evidence policy", "The direct-evidence attestation is not complete, so conclusion-on-conclusion inheritance may remain in the argument."),
    ):
        if attestations.get(field) is not True:
            severity, status = _severity(profile)
            findings.append(
                _finding(
                    2,
                    "ATTESTATION_{0}".format(field.upper()),
                    subject,
                    message,
                    severity=severity,
                    status=status,
                    evidence=["/disclosures/attestations/" + field],
                    repairs=[
                        "Review the evidence inventory and set the attestation true only when it is accurate.",
                        "List known exceptions explicitly and narrow affected claims.",
                        "Ask an independent reviewer to compare claim citations with the underlying artifacts.",
                    ],
                )
            )

    methods = project.get("methods") if isinstance(project.get("methods"), Mapping) else {}
    reproducibility = _text(methods.get("reproducibility_command"))
    receipts = latest_receipts(root)
    verified_receipts: List[Mapping[str, Any]] = []
    for receipt in receipts:
        verification = verify_receipt(root, receipt)
        if verification.get("verified"):
            verified_receipts.append(receipt)
        else:
            findings.append(
                _finding(
                    2,
                    "RECEIPT_DAMAGED",
                    "Execution receipt",
                    "A workload receipt or its captured output no longer verifies: {0}.".format(receipt.get("receipt_id")),
                    evidence=[str(receipt.get("receipt_id"))],
                    repairs=[
                        "Restore the exact captured logs and manifest files, or discard the damaged receipt.",
                        "Rerun the declared workload from the current source state.",
                        "Investigate unexpected modifications before accepting any result produced by the run.",
                    ],
                )
            )
    if profile in {"strict", "submission"} and not reproducibility:
        findings.append(
            _finding(
                2,
                "REPRODUCIBILITY_COMMAND_MISSING",
                "Reproducibility",
                "No executable reproduction command or reasoned not-applicable declaration is recorded.",
                evidence=["/methods/reproducibility_command"],
                repairs=[
                    "Record a shell-free command that rebuilds or tests the claimed result.",
                    "Use `not_applicable: REASON` only for work with no executable component and explain the independent verification route.",
                    "Add a small deterministic validation script even when the primary analysis uses another environment.",
                ],
            )
        )
    elif reproducibility and not _is_na(reproducibility) and profile in {"strict", "submission"}:
        current_records = str(source_manifest.get("records_sha256", ""))
        fresh_pass = [
            row
            for row in verified_receipts
            if row.get("status") == "PASS" and row.get("post_records_sha256") == current_records
        ]
        if not fresh_pass:
            findings.append(
                _finding(
                    2,
                    "FRESH_PASS_RECEIPT_MISSING",
                    "Reproducibility",
                    "No verified passing workload receipt is bound to the current source record set.",
                    evidence=["/methods/reproducibility_command", current_records],
                    repairs=[
                        "Run the declared command through `uriel run -- ...` after the final source changes.",
                        "Fix any failing test or analysis and preserve the new passing receipt.",
                        "Remove stale outputs and rerun from a clean checkout to expose hidden state dependencies.",
                    ],
                )
            )
        elif verified_receipts:
            latest_verified = max(
                verified_receipts,
                key=lambda row: (str(row.get("finished_at_utc", "")), str(row.get("started_at_utc", "")))
            )
            if str(latest_verified.get("status")) != "PASS":
                findings.append(
                    _finding(
                        2,
                        "FRESH_PASS_RECEIPT_MISSING",
                        "Reproducibility",
                        "The latest workload run is {0}; a failing or timed-out run of the current generation cannot satisfy Gate 2.".format(
                            latest_verified.get("status")),
                        evidence=["/methods/reproducibility_command", current_records],
                        repairs=[
                            "Fix the failing analysis or test and rerun the declared command until it passes.",
                            "Treat a timeout as a failed run: investigate the hang before accepting any result.",
                            "Preserve the new passing receipt bound to the current source record set.",
                        ],
                    )
                )

    return GateResult(
        gate=2,
        name="Evidence & Citation",
        status=_gate_status(findings),
        scope_note="Checks bind declared claims to local artifact bytes, exact source locations, and execution receipts. Uriel does not independently validate undisclosed data or the truth of a remote source.",
        findings=findings,
    )


def _gate3(project: Mapping[str, Any], profile: str) -> GateResult:
    findings: List[Finding] = []
    methods = project.get("methods") if isinstance(project.get("methods"), Mapping) else {}
    kind = _text(project.get("kind"))

    method_requirements = (
        ("design", 12, "STUDY_DESIGN_MISSING", "study or validation design"),
        ("population", 8, "POPULATION_MISSING", "population or target system"),
        ("sampling", 8, "SAMPLING_MISSING", "sampling or case-selection rule"),
        ("analysis_plan", 16, "ANALYSIS_PLAN_MISSING", "analysis plan"),
        ("effect_size_metric", 4, "EFFECT_SIZE_MISSING", "effect-size or decision metric"),
        ("uncertainty_method", 8, "UNCERTAINTY_METHOD_MISSING", "uncertainty or error-accounting method"),
        ("missing_data_plan", 8, "MISSING_DATA_PLAN", "missing-data and failed-observation plan"),
    )
    for field, minimum, code, label in method_requirements:
        value = _text(methods.get(field))
        if not _enough(value, minimum) and not _is_na(value):
            severity, status = _severity(profile)
            findings.append(
                _finding(
                    3,
                    code,
                    "Method completeness",
                    "The project does not yet state a usable {0}, leaving a material reviewer question unanswered.".format(label),
                    severity=severity,
                    status=status,
                    evidence=["/methods/" + field],
                    repairs=[
                        "Add the decision rule before interpreting final results.",
                        "Use a reasoned not-applicable declaration only when the concept truly cannot affect the claim.",
                        "Narrow the claim until the available design can answer it without hidden assumptions.",
                    ],
                )
            )

    sample_size = methods.get("sample_size")
    if kind in {"research", "hybrid"} and profile in {"strict", "submission"}:
        if not isinstance(sample_size, int) or isinstance(sample_size, bool) or sample_size <= 0:
            findings.append(
                _finding(
                    3,
                    "SAMPLE_SIZE_MISSING",
                    "Sample adequacy",
                    "No positive sample size is declared for a research or hybrid submission, so uncertainty and exclusion effects cannot be evaluated.",
                    evidence=["/methods/sample_size"],
                    repairs=[
                        "Record the analyzed sample size and the rule that determined it.",
                        "For exhaustive finite data, record the population count and completeness check.",
                        "For a non-sampling design, change the project kind or document why sample-size reasoning is not applicable.",
                    ],
                )
            )

    controls = [_text(item) for item in _items(methods.get("controls")) if _text(item)]
    exclusions = [_text(item) for item in _items(methods.get("exclusions")) if _text(item)]
    if profile != "exploratory" and not controls:
        findings.append(
            _finding(
                3,
                "CONTROLS_MISSING",
                "Controls and comparators",
                "No control, baseline, comparator, negative case, or justified not-applicable condition is recorded.",
                evidence=["/methods/controls"],
                repairs=[
                    "Add a baseline or negative control that would reveal a false positive.",
                    "For software, test a known-invalid and known-valid fixture in addition to the target case.",
                    "Explain why no comparator is possible and narrow the claim to descriptive evidence.",
                ],
            )
        )
    if profile in {"strict", "submission"} and not exclusions:
        findings.append(
            _finding(
                3,
                "EXCLUSIONS_UNDECLARED",
                "Exclusions",
                "No inclusion/exclusion rule is declared, leaving room for outcome-dependent case removal.",
                evidence=["/methods/exclusions"],
                repairs=[
                    "Record all exclusion rules and counts before final interpretation.",
                    "State `none: REASON` when every eligible case is retained and preserve the eligibility rule.",
                    "Report sensitivity results with excluded cases restored where possible.",
                ],
            )
        )

    assumptions = _objects(project.get("assumptions"))
    alternatives = _objects(project.get("alternative_explanations"))
    adversarial = _objects(project.get("adversarial_tests"))
    objections = _objects(project.get("reviewer_objections"))
    limitations = _objects(project.get("limitations"))
    contradictions = _objects(project.get("contradictions"))

    if profile in {"strict", "submission"} and not assumptions:
        findings.append(
            _finding(
                3,
                "ASSUMPTIONS_UNDECLARED",
                "Hidden assumptions",
                "No assumptions are declared. A submission-level argument must expose the conditions on which its inference depends.",
                evidence=["/assumptions"],
                repairs=[
                    "List the strongest assumption that, if false, would change the conclusion.",
                    "Add a test, sensitivity analysis, or observable diagnostic for each assumption.",
                    "Narrow the conclusion so fewer untested assumptions are necessary.",
                ],
            )
        )
    for row in assumptions:
        identifier = str(row.get("id", "?"))
        if not _enough(row.get("statement"), 8) or not _enough(row.get("risk"), 8) or not _enough(row.get("test"), 8):
            findings.append(
                _finding(
                    3,
                    "ASSUMPTION_INCOMPLETE",
                    "Assumption {0}".format(identifier),
                    "The assumption lacks a statement, material risk, or way to probe it.",
                    evidence=[identifier],
                    repairs=[
                        "State the assumption as a proposition that could be false.",
                        "Describe exactly how its failure would alter the claim.",
                        "Add a diagnostic, robustness check, or boundary analysis.",
                    ],
                )
            )

    for collection, code, subject, minimum_message in (
        (alternatives, "ALTERNATIVE_EXPLANATIONS_MISSING", "Alternative explanations", "No plausible competing explanation is recorded."),
        (adversarial, "ADVERSARIAL_TESTS_MISSING", "Adversarial tests", "No test is designed specifically to make the preferred conclusion fail."),
        (objections, "REVIEWER_OBJECTIONS_MISSING", "Reviewer counterarguments", "No strong reviewer objection and response is recorded."),
        (limitations, "LIMITATIONS_MISSING", "Limitations", "No material limitation is stated."),
    ):
        if profile in {"strict", "submission"} and not collection:
            findings.append(
                _finding(
                    3,
                    code,
                    subject,
                    minimum_message,
                    evidence=["/" + {
                        "ALTERNATIVE_EXPLANATIONS_MISSING": "alternative_explanations",
                        "ADVERSARIAL_TESTS_MISSING": "adversarial_tests",
                        "REVIEWER_OBJECTIONS_MISSING": "reviewer_objections",
                        "LIMITATIONS_MISSING": "limitations",
                    }[code]],
                    repairs=[
                        "Add the strongest good-faith countercase, not a weak straw person.",
                        "Describe what observation would make the countercase more likely than the preferred account.",
                        "Narrow the claim where the project cannot presently distinguish the alternatives.",
                    ],
                )
            )

    for row in adversarial:
        identifier = str(row.get("id", "?"))
        required = ("target", "procedure", "failure_condition", "result", "status")
        if any(not _enough(row.get(key), 3) for key in required):
            findings.append(
                _finding(
                    3,
                    "ADVERSARIAL_TEST_INCOMPLETE",
                    "Adversarial test {0}".format(identifier),
                    "The test lacks a target, procedure, failure condition, result, or status.",
                    evidence=[identifier],
                    repairs=[
                        "Specify the exact claim or assumption attacked by the test.",
                        "Predeclare the failure condition and preserve the resulting output artifact.",
                        "Mark unrun tests as pending and do not request a Blessing yet.",
                    ],
                )
            )
        status_value = _text(row.get("status")).casefold()
        if profile == "submission" and status_value not in {"pass", "passed", "complete", "failed_as_expected"}:
            findings.append(
                _finding(
                    3,
                    "ADVERSARIAL_TEST_NOT_RESOLVED",
                    "Adversarial test {0}".format(identifier),
                    "The adversarial probe is not in a completed, interpretable state.",
                    evidence=[identifier, status_value],
                    repairs=[
                        "Run the test and preserve its receipt and result.",
                        "If the test failed, repair or narrow the dependent claim before rerunning.",
                        "If the test is no longer relevant, document the changed scope and remove the stale dependency.",
                    ],
                )
            )

    for row in contradictions:
        identifier = str(row.get("id", "?"))
        status_value = _text(row.get("status")).casefold()
        resolution = _text(row.get("resolution"))
        if status_value not in {"resolved", "explained", "claim_narrowed", "inconclusive"} or len(resolution) < 12:
            findings.append(
                _finding(
                    3,
                    "CONTRADICTION_UNRESOLVED",
                    "Contradiction {0}".format(identifier),
                    "A declared contradiction lacks an explicit resolution, claim narrowing, or inconclusive outcome.",
                    evidence=[identifier],
                    repairs=[
                        "Trace both sides to their exact artifacts and check population, control, and measurement mismatches.",
                        "Narrow or split the claim so each evidence pattern has an honest scope.",
                        "Mark the result inconclusive rather than choosing the preferred datum without a rule.",
                    ],
                )
            )

    # Cross-check evidence roles for contradictions that the author may have missed.
    claims = _claim_map(project)
    for claim_id, claim in claims.items():
        supports = set(str(item) for item in _items(claim.get("evidence_ids")))
        counters = set(str(item) for item in _items(claim.get("counterevidence_ids")))
        if counters and not _enough(claim.get("reconciliation"), 16):
            findings.append(
                _finding(
                    3,
                    "COUNTEREVIDENCE_UNRECONCILED",
                    "Claim {0}".format(claim_id),
                    "Counterevidence is declared but the claim record does not explain whether the result was narrowed, rejected, or left inconclusive.",
                    evidence=[claim_id] + sorted(counters),
                    repairs=[
                        "Explain the decision rule used to weigh supporting and contrary evidence.",
                        "Report subgroup, measurement, or control mismatches rather than averaging them away.",
                        "Mark the claim inconclusive when no predeclared rule resolves the conflict.",
                    ],
                )
            )
        if supports == counters and supports:
            findings.append(
                _finding(
                    3,
                    "TOTAL_EVIDENCE_ROLE_CONFLICT",
                    "Claim {0}".format(claim_id),
                    "Every listed support item is also counterevidence, so the present evidence map cannot justify a directional conclusion.",
                    evidence=[claim_id] + sorted(supports),
                    repairs=[
                        "Split mixed artifacts into exact observations and map each observation separately.",
                        "Change the claim to a null, mixed, or inconclusive result as appropriate.",
                        "Collect a discriminating measurement that predicts different outcomes under competing explanations.",
                    ],
                )
            )

    attestations = {}
    disclosures = project.get("disclosures")
    if isinstance(disclosures, Mapping) and isinstance(disclosures.get("attestations"), Mapping):
        attestations = disclosures.get("attestations")  # type: ignore[assignment]
    if profile in {"strict", "submission"} and attestations.get("null_and_negative_results_declared") is not True:
        findings.append(
            _finding(
                3,
                "NEGATIVE_RESULTS_ATTESTATION_MISSING",
                "Selective reporting",
                "The record does not attest that known null and negative results have been declared.",
                evidence=["/disclosures/attestations/null_and_negative_results_declared"],
                repairs=[
                    "Inventory failed, null, and negative analyses and link them to the affected claims.",
                    "Explain any missing run and preserve its failure receipt when available.",
                    "Set the attestation true only after the inventory is complete; otherwise narrow the claim.",
                ],
            )
        )

    ethics = project.get("ethics") if isinstance(project.get("ethics"), Mapping) else {}
    review_status = _text(ethics.get("review_status"))
    risks = [_text(item) for item in _items(ethics.get("risks")) if _text(item)]
    mitigations = [_text(item) for item in _items(ethics.get("mitigations")) if _text(item)]
    if not review_status:
        findings.append(
            _finding(
                3,
                "ETHICS_STATUS_MISSING",
                "Ethics and harm review",
                "No ethics-review status or reasoned not-applicable determination is recorded.",
                evidence=["/ethics/review_status"],
                repairs=[
                    "Record the applicable review, exemption, or not-applicable reason.",
                    "Identify foreseeable harms from collection, publication, deployment, or misuse.",
                    "Add mitigations and stop conditions for material risks.",
                ],
            )
        )
    if risks and len(mitigations) < len(risks) and profile == "submission":
        findings.append(
            _finding(
                3,
                "ETHICS_RISK_UNMITIGATED",
                "Ethics and harm review",
                "At least one declared risk lacks a corresponding mitigation or explicit acceptance rationale.",
                evidence=["/ethics/risks", "/ethics/mitigations"],
                repairs=[
                    "Pair each material risk with a prevention, reduction, monitoring, or stop mechanism.",
                    "Remove or delay the risky procedure when mitigation is not credible.",
                    "Document residual risk and who is authorized to accept it.",
                ],
            )
        )

    if profile == "submission":
        submission = project.get("submission") if isinstance(project.get("submission"), Mapping) else {}
        missing_submission: List[str] = []
        if not _enough(submission.get("field"), 3):
            missing_submission.append("field")
        if not [item for item in _items(submission.get("target_venues")) if _text(item)]:
            missing_submission.append("target_venues")
        if not [item for item in _items(submission.get("author_names")) if _text(item)]:
            missing_submission.append("author_names")
        if not _enough(submission.get("corresponding_author"), 3):
            missing_submission.append("corresponding_author")
        if not _enough(submission.get("data_availability"), 12):
            missing_submission.append("data_availability")
        if not _enough(submission.get("code_availability"), 12):
            missing_submission.append("code_availability")
        if missing_submission:
            findings.append(
                _finding(
                    3,
                    "SUBMISSION_METADATA_INCOMPLETE",
                    "Submission readiness",
                    "The submission package is missing required author, field, venue, or availability information: {0}.".format(", ".join(missing_submission)),
                    evidence=["/submission/" + item for item in missing_submission],
                    repairs=[
                        "Complete each named field using current, factual submission information.",
                        "For unavailable data or code, state the exact restriction and access route rather than using a placeholder.",
                        "Verify venue scope and instructions on the venue's official site before treating it as a target.",
                    ],
                )
            )

    waivers = _objects(project.get("waivers"))
    for row in waivers:
        if _text(row.get("severity")).casefold() in {"blocker", "critical", "mandatory"}:
            findings.append(
                _finding(
                    3,
                    "MANDATORY_GATE_WAIVER_REFUSED",
                    "Audit waiver",
                    "A mandatory integrity requirement cannot be waived into a Blessing. The waiver remains useful documentation, but it does not convert missing proof into proof.",
                    evidence=[str(row.get("id", "?"))],
                    repairs=[
                        "Satisfy the underlying requirement with evidence or a valid not-applicable argument.",
                        "Narrow the claim so the requirement no longer materially applies.",
                        "Publish without a Uriel Blessing and disclose the unresolved limitation plainly.",
                    ],
                )
            )

    return GateResult(
        gate=3,
        name="Adversarial Integrity",
        status=_gate_status(findings),
        scope_note="Checks expose declared assumptions, controls, exclusions, counterevidence, contradictions, uncertainty, ethics, and reviewer objections. They cannot enumerate every possible future critique.",
        findings=findings,
    )


def _render_report(report: AuditReport, project: Mapping[str, Any]) -> str:
    lines = [
        "# Uriel audit · {0}".format(report.status),
        "",
        "**Project:** {0}".format(project.get("title", "Untitled")),
        "**Profile:** `{0}`".format(report.profile),
        "**Audit ID:** `{0}`".format(report.audit_id),
        "**Source:** `{0}`".format(report.source_manifest_sha256),
        "",
        "> A PASS is a content-bound audit result within the declared scope. It is not peer review, universal truth, or proof that no undiscovered prior work or error exists.",
        "",
    ]
    for gate in report.gates:
        lines.extend([
            "## Gate {0}: {1} — {2}".format(gate.gate, gate.name, gate.status),
            "",
            gate.scope_note,
            "",
        ])
        if not gate.findings:
            lines.extend(["No blocking or warning findings were produced by this policy version.", ""])
            continue
        for finding in gate.findings:
            lines.extend([
                "### {0} · `{1}`".format(finding.subject, finding.code),
                "",
                "**{0}:** {1}".format(finding.status, finding.message),
                "",
            ])
            if finding.evidence:
                lines.append("Evidence: " + ", ".join("`{0}`".format(item) for item in finding.evidence))
                lines.append("")
            lines.append("Repair paths:")
            for index, repair in enumerate(finding.as_dict()["repairs"], start=1):
                lines.append("{0}. {1}".format(index, repair))
            lines.append("")
    lines.extend(["## Audit limitations", ""])
    for limitation in report.limitations:
        lines.append("- " + limitation)
    lines.append("")
    return "\n".join(lines)


def _report_from_dict(value: Mapping[str, Any]) -> AuditReport:
    gates: List[GateResult] = []
    for gate in _objects(value.get("gates")):
        findings = [
            Finding(
                code=str(item.get("code", "UNKNOWN")),
                gate=int(item.get("gate", gate.get("gate", 0))),
                severity=str(item.get("severity", "blocker")),
                status=str(item.get("status", "FAIL")),
                subject=str(item.get("subject", item.get("code", "Finding"))),
                message=str(item.get("message", "")),
                evidence=[str(row) for row in _items(item.get("evidence"))],
                repairs=[str(row) for row in _items(item.get("repairs"))],
            )
            for item in _objects(gate.get("findings"))
        ]
        gates.append(
            GateResult(
                gate=int(gate.get("gate", 0)),
                name=str(gate.get("name", "Unknown")),
                status=str(gate.get("status", "FAIL")),
                scope_note=str(gate.get("scope_note", "")),
                findings=findings,
            )
        )
    return AuditReport(
        audit_id=str(value.get("audit_id", "")),
        profile=str(value.get("profile", "standard")),
        status=str(value.get("status", "FAIL")),
        created_at_utc=str(value.get("created_at_utc", "")),
        source_manifest_sha256=str(value.get("source_manifest_sha256", "")),
        source_records_sha256=str(value.get("source_records_sha256", "")),
        project_manifest_sha256=str(value.get("project_manifest_sha256", "")),
        policy_version=str(value.get("policy_version", POLICY_VERSION)),
        gates=gates,
        audit_path=str(value.get("audit_path", "")),
        limitations=[str(row) for row in _items(value.get("limitations"))],
    )


def audit_project(root: Union[str, Path], *, profile: str = "standard") -> AuditReport:
    """Run all three deterministic Gates and persist the exact result."""

    if profile not in PROFILES:
        raise Refusal(
            "Unknown audit profile: {0}".format(profile),
            code="INVALID_AUDIT_PROFILE",
            repairs=[
                "Choose exploratory, standard, strict, or submission.",
                "Use exploratory for a rough idea and submission only for a complete package.",
                "Run `uriel audit --help` to review profile behavior.",
            ],
        )
    paths = paths_for(root)
    project = load_project(paths.root)
    schema_errors = validate_manifest(project)
    source_manifest = build_manifest(paths.root, persist=True)
    source_verification = verify_source_manifest(paths.root, source_manifest)
    if not source_verification.get("verified"):
        raise IntegrityError(
            "The freshly produced source manifest did not verify.",
            code="SOURCE_MANIFEST_VERIFICATION_FAILED",
            details={"errors": source_verification.get("errors", [])},
        )

    gates = [
        _gate1(project, profile, schema_errors),
        _gate2(paths.root, project, profile, source_manifest),
        _gate3(project, profile),
    ]
    status = "PASS" if all(gate.status == "PASS" for gate in gates) else "FAIL"
    project_hash = sha256_file(paths.project)
    identity = {
        "policy_version": POLICY_VERSION,
        "profile": profile,
        "source_manifest_sha256": source_manifest["manifest_sha256"],
        "source_records_sha256": source_manifest["records_sha256"],
        "project_manifest_sha256": project_hash,
        "status": status,
        "gates": [gate.as_dict() for gate in gates],
    }
    audit_id = sha256_text(canonical_json(identity))[:32]
    audit_path = paths.audits / (audit_id + ".json")
    created = utc_now()
    if audit_path.exists():
        existing = read_json(audit_path)
        existing_report = _report_from_dict(existing)
        created = existing_report.created_at_utc or created

    limitations = [
        "Uriel verifies declared local artifacts, hashes, relationships, and deterministic policy checks; it cannot inspect data that was omitted from the project.",
        "Novelty is bounded by the documented search scope and date, not the whole of human knowledge.",
        "A passing audit is not peer review, ethical approval, legal advice, statistical certification, or a guarantee that the conclusion is true.",
        "Optional AI reviews are untrusted inputs until their citations and artifact references are independently verified.",
    ]
    report = AuditReport(
        audit_id=audit_id,
        profile=profile,
        status=status,
        created_at_utc=created,
        source_manifest_sha256=str(source_manifest["manifest_sha256"]),
        source_records_sha256=str(source_manifest["records_sha256"]),
        project_manifest_sha256=project_hash,
        policy_version=POLICY_VERSION,
        gates=gates,
        audit_path=(Path(".uriel") / "audits" / (audit_id + ".json")).as_posix(),
        limitations=limitations,
    )
    payload = report.as_dict()
    if audit_path.exists():
        existing = read_json(audit_path)
        if existing != payload:
            raise IntegrityError(
                "An immutable audit id resolved to different content.",
                code="AUDIT_COLLISION",
                details={"audit_id": audit_id},
            )
    else:
        atomic_write_json(audit_path, payload)
    atomic_write_json(
        paths.audits / "current.json",
        {
            "schema": "uriel.audit_pointer.v1",
            "audit_id": audit_id,
            "audit_path": report.audit_path,
            "audit_sha256": sha256_file(audit_path),
            "profile": profile,
            "status": status,
            "source_manifest_sha256": report.source_manifest_sha256,
        },
    )
    atomic_write(paths.audits / "current.md", _render_report(report, project))
    blockers = [
        finding.as_dict()
        for gate in gates
        for finding in gate.findings
        if finding.severity == "blocker" and finding.status == "FAIL"
    ]
    sync_reminders(paths.root, blockers)
    append_ledger(
        paths.root,
        "audit.completed",
        {
            "audit_id": audit_id,
            "audit_sha256": sha256_file(audit_path),
            "profile": profile,
            "status": status,
            "source_manifest_sha256": report.source_manifest_sha256,
            "blocker_count": len(blockers),
        },
    )
    return report


def load_current_audit(root: Union[str, Path]) -> AuditReport:
    paths = paths_for(root)
    pointer = read_json(guard_path(paths.root, paths.audits / "current.json", must_exist=True))
    if pointer.get("schema") != "uriel.audit_pointer.v1":
        raise IntegrityError("Audit pointer schema mismatch.", code="AUDIT_POINTER_SCHEMA")
    rel = str(pointer.get("audit_path", ""))
    path = guard_path(paths.root, paths.root / safe_relative_path(rel), must_exist=True)
    if sha256_file(path) != pointer.get("audit_sha256"):
        raise IntegrityError("Audit pointer hash mismatch.", code="AUDIT_POINTER_DIGEST")
    report = _report_from_dict(read_json(path))
    if report.audit_id != pointer.get("audit_id"):
        raise IntegrityError("Audit pointer identity mismatch.", code="AUDIT_POINTER_ID")
    return report


def run_audit(
    root: Union[str, Path],
    *,
    profile: str = "standard",
    persist: bool = True,
    build_sqlite: bool = True,
) -> Dict[str, Any]:
    """Run the audit and return a self-verifying JSON envelope.

    ``audit_project`` always persists immutable audit evidence.  ``persist`` is
    accepted for API compatibility; setting it false suppresses no integrity
    work because an audit without a receipt would be misleading.
    """
    del persist
    report = audit_project(root, profile=profile)
    paths = paths_for(root)
    if build_sqlite:
        manifest = build_manifest(paths.root, persist=True)
        build_index(paths.root, manifest)
    body = report.as_dict()
    body["overall_status"] = report.status
    body["report_sha256"] = sha256_text(canonical_json(body))
    body["report_relpath"] = report.audit_path
    body["markdown_relpath"] = (Path(".uriel") / "audits" / "current.md").as_posix()
    return body
