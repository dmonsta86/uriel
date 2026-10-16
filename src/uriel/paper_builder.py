"""Paper Builder: a canonical, checkable manuscript directory.

The manuscript source lives in ``paper/`` beside the project record::

    paper/
      paper.json            section order, kinds, number policy, word limits
      sections/*.md         prose with three kinds of inline markup
      datapoints.json       every reported number, bound to hashed bytes
      references.json       every cited work, with its verification status
      build/                generated output (ignored by the source inventory)

Markup:

- ``{{dp:ID}}`` renders a verified datapoint; result numbers are never typed.
- ``{{lit:TEXT}}`` marks a deliberate literal (for example a protocol
  constant) so the number policy does not ask for a datapoint.
- ``[@key]`` / ``[@a; @b, p. 4]`` cites entries in ``references.json``.
- ``[claim:C1]`` ties a sentence to a claim in ``uriel.project.json``; the
  anchor is removed from the built text.

``paper check`` is read-only.  It verifies datapoints against their artifacts,
resolves citations, verifies quotations against held source text, ties claim
anchors to the project record, enforces the per-section number policy,
recomputes reported statistics, lints assistant residue and filler, and
checks the analysis-plan lock.  ``paper build`` refuses unless the check
passes for the chosen profile, then writes a deterministic manuscript, a
number-trace supplement, and a receipt binding every input digest.

None of this decides whether the science is right.  It removes the most
common ways a manuscript drifts away from its own evidence.
"""
from __future__ import annotations

import bisect
import datetime as _dt
import functools
import json
import re
import unicodedata
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from . import datapoints as dp
from . import framing
from . import model_check
from . import plan_lock
from . import prose_lint
from . import stat_check
from .core import (
    Refusal,
    append_ledger,
    atomic_write,
    atomic_write_json,
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

PAPER_SCHEMA = "uriel.paper.v1"
REFERENCES_SCHEMA = "uriel.references.v1"
PAPER_CHECK_SCHEMA = "uriel.paper_check.v1"
PAPER_BUILD_SCHEMA = "uriel.paper_build.v1"
PAPER_DIR = "paper"
PAPER_FILE = "paper/paper.json"
REFERENCES_FILE = "paper/references.json"
BUILD_DIR = "paper/build"
MANUSCRIPT_OUTPUT = "paper/build/manuscript.md"
TRACE_OUTPUT = "paper/build/NUMBER_TRACE.md"
RECEIPT_OUTPUT = "paper/build/BUILD_RECEIPT.json"
CHECK_PROFILES = ("draft", "submission")
SECTION_KINDS = (
    "abstract",
    "introduction",
    "methods",
    "results",
    "discussion",
    "limitations",
    "conclusion",
    "statements",
    "other",
)
NUMBER_POLICIES = ("bound", "cited_or_bound", "free")
DEFAULT_NUMBER_POLICY = {
    "abstract": "bound",
    "results": "bound",
    "conclusion": "bound",
    "introduction": "cited_or_bound",
    "discussion": "cited_or_bound",
    "limitations": "cited_or_bound",
    "methods": "free",
    "statements": "free",
    "other": "cited_or_bound",
}
ARTICLE_TYPES = ("empirical", "replication", "negative_result", "methods", "resource", "review")
VERIFICATION_STATUSES = ("held", "metadata_checked", "unverified")
TEXT_SOURCE_SUFFIXES = (".txt", ".md", ".markdown", ".tex", ".csv", ".tsv", ".json", ".html", ".htm", ".xml")
MAX_SECTION_BYTES = 2 * 1024 * 1024
MAX_SECTIONS = 40
MAX_REFERENCES = 2000
MIN_SECTION_WORDS = 20
MIN_QUOTE_WORDS = 6

_DP_MARKER = re.compile(r"\{\{dp:([A-Za-z][A-Za-z0-9_.-]{0,63})\}\}")
_LIT_MARKER = re.compile(r"\{\{lit:([^{}\n]{1,200})\}\}")
_ANY_BRACES = re.compile(r"\{\{[^{}\n]*\}\}")
_OPEN_BRACES = re.compile(r"\{\{|\}\}")
_CITATION = re.compile(r"\[@([^\]\n]+)\]")
_CITE_PART = re.compile(r"^@([A-Za-z0-9][A-Za-z0-9_:.\-]{0,63})(?:\s*,\s*(.{1,40}))?$")
_CLAIM_ANCHOR = re.compile(r"\[claim:([A-Za-z0-9][A-Za-z0-9._-]{0,63})\]")
_ANY_ANCHOR = re.compile(r"[ \t]?\[(?:claim|alt|model):[^\]\n]*\]")
_ALT_OR_MODEL_ANCHOR = re.compile(r"\[(?:alt|model):[A-Za-z0-9][A-Za-z0-9._-]{0,63}\]")
_QUOTE = re.compile(
    r"(?:(?<=^)|(?<=[\s(\[\u2014:]))[\"\u201c]"
    r"([^\s\"\u201c\u201d][^\"\u201c\u201d\n]{10,798}[^\s\"\u201c\u201d])"
    r"[\"\u201d](?=[\s.,;:!?)\]\u2014]|$)",
    re.MULTILINE,
)
_DOI = re.compile(r"^10\.\d{4,9}/\S+$")
_KEY = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_:.\-]{0,63}$")
_SECTION_ID = re.compile(r"^[a-z][a-z0-9_-]{0,47}$")
_NUMBER = re.compile(r"(?<![\w.\-\u2212])[-\u2212]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w])%?|(?<![\w.])\.\d+(?![\w])%?")
_NUMBER_LABEL = re.compile(
    r"(?:Figure|Fig\.|Figs\.|Table|Tables|Section|Sect\.|Appendix|Supplement(?:ary)?(?: (?:Table|Figure|Material))?|"
    r"Eq\.|Equation|Hypothes[ie]s|Study|Studies|Experiment|Claim|Step|Phase|Stage|Wave|Part|Chapter|Item|Model|"
    r"Version|Footnote|Note|Criterion|Aim|Question|Panel|Box|Listing|Algorithm|Line|Lines|Page|Pages|pp?\.)\s*$",
    re.IGNORECASE,
)
_CONFIDENCE_LEVEL = re.compile(r"^\s*%?\s*(?:CI|C\.I\.|CrI|confidence|credible|HDI|prediction interval)", re.IGNORECASE)
_NUMERIC_CITATION = re.compile(r"\[\d+(?:\s*[,\u2013-]\s*\d+)*\]")
_CAUSAL = re.compile(
    r"\b(?:causes?|caused|causal(?:ly)?|leads? to|led to|results? in|resulted in|produces?|produced|prevents?|prevented|"
    r"drives?|drove|is responsible for|effect of [\w\s-]{1,40} on)\b",
    re.IGNORECASE,
)
_STATEMENT_TOPICS: Sequence[Tuple[str, str, re.Pattern]] = (
    ("data_availability", "data availability", re.compile(r"\bdata (?:availability|are available|is available|will be (?:made )?available|access)", re.I)),
    ("code_availability", "code availability", re.compile(r"\b(?:code|software|scripts?) (?:availability|are available|is available|will be (?:made )?available)", re.I)),
    ("funding", "funding", re.compile(r"\bfund(?:ing|ed)\b|\bno (?:specific )?funding\b|\bgrant\b", re.I)),
    ("conflicts", "competing interests", re.compile(r"\b(?:conflicts? of interest|competing interests?)\b", re.I)),
    ("ethics", "ethics", re.compile(r"\bethic|\binstitutional review board\b|\bIRB\b|\bethics committee\b", re.I)),
    ("ai_use", "use of AI tools", re.compile(r"\b(?:artificial intelligence|language models?|generative|AI(?:-assisted| tools?| assistance| use)?)\b", re.I)),
)


# ---------------------------------------------------------------------------
# Scaffold
# ---------------------------------------------------------------------------

_SECTION_GUIDE: Dict[str, List[str]] = {
    "abstract": [
        "One sentence of context, then the question exactly as recorded in uriel.project.json.",
        "Design and sample (sample size as {{dp:ID}}).",
        "Main result with effect size and uncertainty, every number as {{dp:ID}}.",
        "The most important limitation.",
        "A conclusion no stronger than the Results section supports.",
        "No citations, no hype words, stay within the word limit in paper.json.",
    ],
    "introduction": [
        "The problem and why it matters; every factual claim about prior work carries [@key].",
        "The closest prior work (see /novelty_review/nearest_prior_work) and exactly what this study adds.",
        "The question, hypothesis, and falsifier as locked by `uriel plan lock` (keep the recorded wording).",
        "No results here. No 'first ever' or 'groundbreaking' wording unless the recorded search supports it.",
    ],
    "methods": [
        "Design, population, sampling rule, and sample-size justification (see /methods).",
        "Measures with their operational definitions (see /hypothesis/operational_definitions).",
        "The analysis plan as locked; list every deviation from the lock with its reason.",
        "Every model or equation, tagged [model:ID], with its role (descriptive fit, predictive, or mechanistic), domain, and assumptions.",
        "Exclusions and missing data, with counts as {{dp:ID}}.",
        "Software, versions, and the reproduction command (see /methods/reproducibility_command).",
        "Ethics approval or the reason none was needed.",
    ],
    "results": [
        "Report in the order of the hypotheses. Tag each claim sentence with [claim:ID].",
        "Every number is a {{dp:ID}} marker registered with `uriel paper dp-add`; never type a result.",
        "Give estimates with intervals; give test statistics with df and exact p (format apa_p).",
        "Report null, adverse, and unexpected results with the same care as supportive ones.",
        "Describe; do not interpret. Interpretation belongs in the Discussion.",
    ],
    "discussion": [
        "Restate the principal finding at exactly the strength the Results support.",
        "Compare with prior work, citing each comparison with [@key].",
        "Weigh each recorded alternative explanation and tag it [alt:ID]: what the data can and cannot tell apart.",
        "Discuss each piece of counterevidence recorded in the project ([claim:ID] where relevant).",
        "Do not call an alternative ruled out unless the project links the evidence or passed test that rules it out.",
        "Say what the result does not show; keep implications inside the sample and design.",
        "Keep speculation in sentences explicitly labelled as speculation.",
    ],
    "limitations": [
        "Each limitation recorded in /limitations, and how it could change the interpretation.",
        "Generalizability limits: population, setting, timeframe, measurement.",
        "Do not write limitations designed to be dismissed.",
    ],
    "conclusion": [
        "One short paragraph. No claim that is not reported in Results.",
        "Same strength as the evidence; numbers, if any, as {{dp:ID}}.",
    ],
    "statements": [
        "Data availability: where the data are and how to access them.",
        "Code availability: repository and the exact reproduction command.",
        "Funding, and the role of funders.",
        "Competing interests.",
        "Ethics approval (committee and reference) or why none was required.",
        "Use of AI tools: which tools, for what, and how output was verified by the authors.",
    ],
}

_ARTICLE_SECTIONS: Dict[str, List[Tuple[str, str, str]]] = {
    "empirical": [
        ("abstract", "Abstract", "abstract"),
        ("introduction", "Introduction", "introduction"),
        ("methods", "Methods", "methods"),
        ("results", "Results", "results"),
        ("discussion", "Discussion", "discussion"),
        ("limitations", "Limitations", "limitations"),
        ("conclusion", "Conclusion", "conclusion"),
        ("statements", "Declarations", "statements"),
    ],
    "methods": [
        ("abstract", "Abstract", "abstract"),
        ("introduction", "Introduction", "introduction"),
        ("method", "Method", "methods"),
        ("validation", "Validation", "results"),
        ("discussion", "Discussion", "discussion"),
        ("limitations", "Limitations", "limitations"),
        ("conclusion", "Conclusion", "conclusion"),
        ("statements", "Declarations", "statements"),
    ],
    "review": [
        ("abstract", "Abstract", "abstract"),
        ("introduction", "Introduction", "introduction"),
        ("search_methods", "Search and Selection Methods", "methods"),
        ("synthesis", "Evidence Synthesis", "results"),
        ("discussion", "Discussion", "discussion"),
        ("limitations", "Limitations", "limitations"),
        ("conclusion", "Conclusion", "conclusion"),
        ("statements", "Declarations", "statements"),
    ],
}
_ARTICLE_SECTIONS["replication"] = _ARTICLE_SECTIONS["empirical"]
_ARTICLE_SECTIONS["negative_result"] = _ARTICLE_SECTIONS["empirical"]
_ARTICLE_SECTIONS["resource"] = _ARTICLE_SECTIONS["methods"]


def _project_context(project: Mapping[str, Any], kind: str) -> List[str]:
    def text(value: Any) -> str:
        return " ".join(str(value).split()) if isinstance(value, (str, int, float)) else ""

    def rows(name: str) -> List[str]:
        output = []
        for row in project.get(name, []) if isinstance(project.get(name), list) else []:
            if isinstance(row, Mapping):
                label = text(row.get("id"))
                body = text(row.get("statement") or row.get("description") or row.get("text") or row.get("explanation"))
                if body:
                    output.append("{0}: {1}".format(label, body) if label else body)
            elif text(row):
                output.append(text(row))
        return output

    hypothesis = project.get("hypothesis") if isinstance(project.get("hypothesis"), Mapping) else {}
    lines: List[str] = []
    if kind in ("abstract", "introduction"):
        if text(project.get("question")):
            lines.append("Recorded question: " + text(project.get("question")))
        if text(hypothesis.get("statement")):
            lines.append("Recorded hypothesis: " + text(hypothesis.get("statement")))
        if text(hypothesis.get("falsifier")):
            lines.append("Recorded falsifier: " + text(hypothesis.get("falsifier")))
    if kind == "introduction":
        novelty = project.get("novelty_review") if isinstance(project.get("novelty_review"), Mapping) else {}
        for item in novelty.get("nearest_prior_work", []) if isinstance(novelty.get("nearest_prior_work"), list) else []:
            if text(item):
                lines.append("Nearest prior work: " + text(item))
    if kind in ("results", "discussion", "conclusion"):
        for claim in project.get("claims", []) if isinstance(project.get("claims"), list) else []:
            if isinstance(claim, Mapping) and text(claim.get("statement")):
                lines.append("Claim [claim:{0}]: {1}".format(text(claim.get("id")), text(claim.get("statement"))))
    if kind in ("discussion", "limitations"):
        for row in project.get("alternative_explanations", []) if isinstance(project.get("alternative_explanations"), list) else []:
            if isinstance(row, Mapping) and text(row.get("statement")):
                lines.append("Alternative [alt:{0}] ({1}): {2}".format(
                    text(row.get("id")), text(row.get("status")) or "open", text(row.get("statement"))))
    if kind == "methods":
        for row in project.get("models", []) if isinstance(project.get("models"), list) else []:
            if isinstance(row, Mapping) and row.get("id"):
                lines.append("Model [model:{0}] ({1}): {2}".format(
                    text(row.get("id")), text(row.get("role")) or "role undeclared", text(row.get("equation"))))
    if kind == "limitations":
        lines.extend("Recorded limitation " + item for item in rows("limitations"))
    return [line.replace("--", "- -")[:400] for line in lines]


def _scaffold_text(kind: str, title: str, project: Mapping[str, Any]) -> str:
    guide = _SECTION_GUIDE.get(kind, ["Write this section from the project record; bind numbers and cite sources."])
    lines = ["<!--", "Uriel section guide: {0} (kind: {1})".format(title, kind), "", "Checklist:"]
    lines.extend("- [ ] " + item for item in guide)
    context = _project_context(project, kind)
    if context:
        lines.extend(["", "From uriel.project.json when this scaffold was created (re-check the live file):"])
        lines.extend("  " + item for item in context)
    lines.extend([
        "",
        "Rules: never type a result number (use {{dp:ID}}); cite only held or checked sources ([@key]);",
        "quote only text that exists verbatim in a held source; run `uriel paper check` after every edit.",
        "This comment is ignored by checks and removed from the built manuscript.",
        "-->",
        "",
    ])
    return "\n".join(lines)


def init_paper(root: Union[str, Path], *, article_type: str = "empirical", title: str = "") -> Dict[str, Any]:
    """Create the paper/ scaffold; never overwrites an existing manuscript."""
    if article_type not in ARTICLE_TYPES:
        raise Refusal(
            "Unknown article type.",
            code="PAPER_ARTICLE_TYPE_INVALID",
            details={"article_type": article_type, "allowed": list(ARTICLE_TYPES)},
            repairs=[
                "Choose one of: {0}.".format(", ".join(ARTICLE_TYPES)),
                "Use empirical for a standard IMRaD study, including null results.",
                "Edit paper/paper.json after initialization to add or rename sections.",
            ],
        )
    paths = paths_for(root)
    project = load_project(paths.root)
    paper_dir = guard_path(paths.root, paths.root / PAPER_DIR)
    manifest_path = guard_path(paths.root, paths.root / PAPER_FILE)
    if manifest_path.exists():
        raise Refusal(
            "paper/paper.json already exists; Uriel will not overwrite a manuscript.",
            code="PAPER_ALREADY_EXISTS",
            repairs=[
                "Continue with `uriel paper check --root .` on the existing manuscript.",
                "Initialize a separate project for a different paper.",
                "Move the existing paper/ directory aside deliberately before re-initializing.",
            ],
        )
    if paper_dir.exists() and (is_reparse_or_link(paper_dir) or not paper_dir.is_dir()):
        raise Refusal("paper/ must be a regular directory.", code="PAPER_DIRECTORY_INVALID")
    sections = []
    written: List[str] = []
    for index, (section_id, section_title, kind) in enumerate(_ARTICLE_SECTIONS[article_type]):
        relative = "sections/{0:02d}_{1}.md".format(index, section_id)
        target = guard_path(paths.root, paths.root / PAPER_DIR / relative)
        if target.exists():
            raise Refusal("A section file already exists: {0}".format(relative), code="PAPER_ALREADY_EXISTS")
        sections.append({
            "id": section_id,
            "title": section_title,
            "kind": kind,
            "file": relative,
            "required": True,
            "number_policy": DEFAULT_NUMBER_POLICY[kind],
        })
    manifest = {
        "schema": PAPER_SCHEMA,
        "schema_version": 1,
        "title": (title or str(project.get("title", ""))).strip(),
        "article_type": article_type,
        "sections": sections,
        "word_limits": {"abstract": 250},
    }
    for section in sections:
        target = paths.root / PAPER_DIR / section["file"]
        atomic_write(target, _scaffold_text(section["kind"], section["title"], project))
        written.append("{0}/{1}".format(PAPER_DIR, section["file"]))
    for relative, value in (
        (dp.REGISTRY_RELATIVE_PATH, dp.empty_registry()),
        (REFERENCES_FILE, {"schema": REFERENCES_SCHEMA, "schema_version": 1, "references": []}),
    ):
        target = guard_path(paths.root, paths.root / relative)
        if not target.exists():
            atomic_write_json(target, value)
            written.append(relative)
    atomic_write_json(manifest_path, manifest)
    written.append(PAPER_FILE)
    append_ledger(paths.root, "paper.initialized", {
        "article_type": article_type,
        "paper_sha256": sha256_file(manifest_path),
        "section_count": len(sections),
    })
    return {
        "status": "INITIALIZED",
        "article_type": article_type,
        "files_written": sorted(written),
        "next": [
            "Register each reported number: `uriel paper dp-add --root . --id ID --artifact PATH ...`.",
            "Draft one section at a time, then run `uriel paper check --root .`.",
            "Run `uriel next --root .` at any time for the single next research step.",
        ],
    }


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------

def _strict_json(path: Path, label: str) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=dp._reject_duplicates)
    except (ValueError, UnicodeDecodeError) as exc:
        raise Refusal(
            "{0} is not valid strict JSON: {1}".format(label, exc),
            code="PAPER_JSON_INVALID",
            details={"file": label},
            repairs=[
                "Fix the JSON syntax or duplicate key in {0}.".format(label),
                "Restore the file from version control.",
                "Re-create the scaffold in a fresh project with `uriel paper init` and compare.",
            ],
        ) from exc


def _load_manifest(root: Path) -> Dict[str, Any]:
    path = guard_path(root, root / PAPER_FILE)
    if not path.is_file() or is_reparse_or_link(path):
        raise Refusal(
            "No manuscript exists yet (paper/paper.json is missing).",
            code="PAPER_NOT_INITIALIZED",
            repairs=[
                "Run `uriel paper init --root .` to create the manuscript scaffold.",
                "Choose --article-type to match the paper (empirical, replication, negative_result, methods, resource, review).",
                "Run `uriel next --root .` to confirm the project is ready for drafting.",
            ],
        )
    value = _strict_json(path, PAPER_FILE)
    if not isinstance(value, dict):
        raise Refusal("paper/paper.json must be a JSON object.", code="PAPER_JSON_INVALID")
    return value


def _load_references(root: Path) -> Dict[str, Any]:
    path = guard_path(root, root / REFERENCES_FILE)
    if not path.exists():
        return {"schema": REFERENCES_SCHEMA, "schema_version": 1, "references": []}
    if not path.is_file() or is_reparse_or_link(path):
        raise Refusal("paper/references.json must be a regular file.", code="PAPER_JSON_INVALID")
    value = _strict_json(path, REFERENCES_FILE)
    if not isinstance(value, dict):
        raise Refusal("paper/references.json must be a JSON object.", code="PAPER_JSON_INVALID")
    return value


def _read_section(root: Path, relative: str) -> Tuple[str, str]:
    safe = safe_relative_path(relative)
    target = guard_path(root, root / PAPER_DIR / safe, must_exist=True)
    if not target.is_file() or is_reparse_or_link(target):
        raise Refusal("A section must be a regular file.", code="PAPER_SECTION_INVALID", details={"file": relative})
    raw = target.read_bytes()
    if len(raw) > MAX_SECTION_BYTES:
        raise Refusal("A section exceeds the bounded size.", code="PAPER_SECTION_TOO_LARGE", details={"file": relative})
    try:
        return raw.decode("utf-8"), sha256_bytes(raw)
    except UnicodeDecodeError as exc:
        raise Refusal("Sections must be strict UTF-8.", code="PAPER_SECTION_NOT_UTF8", details={"file": relative}) from exc


# ---------------------------------------------------------------------------
# Findings
# ---------------------------------------------------------------------------

_REPAIRS: Dict[str, List[str]] = {
    "PAPER_MANIFEST_INVALID": [
        "Correct the named field in paper/paper.json.",
        "Compare with a fresh scaffold from `uriel paper init` in a scratch project.",
        "Keep section files under paper/sections/ and list each exactly once.",
    ],
    "SECTION_FILE_MISSING": [
        "Restore the section file at the path listed in paper/paper.json.",
        "Remove the section from paper/paper.json if it was deleted on purpose.",
        "Create the file with the section guide from a fresh scaffold.",
    ],
    "SECTION_NOT_IN_MANIFEST": [
        "List the file in paper/paper.json if it belongs in the paper.",
        "Move abandoned drafts out of paper/sections/.",
        "Merge the text into an existing section.",
    ],
    "SECTION_EMPTY": [
        "Draft the section following its checklist comment.",
        "Mark the section required: false in paper/paper.json if this article type omits it.",
        "Run `uriel next --root .` to see whether earlier research steps must come first.",
    ],
    "WORD_LIMIT_EXCEEDED": [
        "Cut repetition and filler first; keep every bound number and citation.",
        "Move detail to Methods, a table, or the supplement.",
        "Correct the limit in paper/paper.json if the venue allows more.",
    ],
    "MARKUP_INVALID": [
        "Use only {{dp:ID}} and {{lit:TEXT}} inside double braces.",
        "Close every {{ with }} on the same line.",
        "Escape literal braces by rephrasing; markup is reserved for bound values.",
    ],
    "DATAPOINT_MARKER_UNKNOWN": [
        "Register the value with `uriel paper dp-add --id ID ...` before using {{dp:ID}}.",
        "Correct the spelling of the id to match paper/datapoints.json.",
        "Remove the sentence if the value does not exist in any artifact.",
    ],
    "DATAPOINT_UNUSED": [
        "Report the value where it belongs, or note it in the supplement.",
        "Remove the datapoint from the registry if it is not reported.",
        "Keep it if it supports a relation check; unused values are only advisory.",
    ],
    "UNBOUND_NUMBER": [
        "Register the value with `uriel paper dp-add` and replace the typed number with {{dp:ID}}.",
        "Wrap a deliberate non-result constant as {{lit:VALUE}} (for example a protocol setting).",
        "Move design constants to Methods, where the number policy is free.",
    ],
    "UNSOURCED_NUMBER": [
        "Add the citation [@key] for the source of the number in the same sentence.",
        "Bind the number to a project artifact with {{dp:ID}}.",
        "Delete the number if its source cannot be found.",
    ],
    "CITATION_KEY_UNKNOWN": [
        "Add the work to paper/references.json with verification status 'unverified' until a human checks it.",
        "Correct the key to match an existing reference.",
        "Remove the citation if the source cannot be identified; never invent a reference.",
    ],
    "CITATION_SYNTAX_INVALID": [
        "Write citations as [@key] or [@key1; @key2, p. 4].",
        "Use keys of letters, digits, '_', ':', '.', or '-'.",
        "Put page locators after a comma inside the brackets.",
    ],
    "REFERENCES_INVALID": [
        "Correct the named field in paper/references.json.",
        "Give every reference a unique key, authors, year, and title.",
        "Restore the file from version control if it was damaged.",
    ],
    "REFERENCE_KEY_DUPLICATE": [
        "Merge duplicate entries into one key.",
        "Rename one key if they are genuinely different works.",
        "Update every [@key] citation to the surviving key.",
    ],
    "REFERENCE_INCOMPLETE": [
        "Fill authors, year, title, and venue from the publisher's record.",
        "Copy metadata from the source itself, not from another bibliography.",
        "Remove the reference if its metadata cannot be confirmed.",
    ],
    "REFERENCE_DOI_INVALID": [
        "Copy the DOI exactly from the publisher page (it starts with 10.).",
        "Remove the DOI field rather than guessing one.",
        "Use the url field for works without a DOI.",
    ],
    "REFERENCE_DOI_DUPLICATE": [
        "Merge the entries; one DOI identifies one work.",
        "Correct whichever DOI was copied wrongly.",
        "Check both sources by opening them.",
    ],
    "REFERENCE_YEAR_IMPLAUSIBLE": [
        "Correct the publication year from the source.",
        "Use the year of the version actually read and note preprint status.",
        "Remove the reference if its existence cannot be confirmed.",
    ],
    "REFERENCE_UNVERIFIED": [
        "Open the source, save a permitted copy under sources/, and set artifact_path with status 'held'.",
        "Check metadata against the publisher record and set status 'metadata_checked' with checked_on and a note.",
        "Remove the citation if no human can confirm the work exists and says what the sentence claims.",
    ],
    "REFERENCE_SOURCE_MISSING": [
        "Restore the held source file at artifact_path.",
        "Correct artifact_path to the file's real project-relative location.",
        "Remove artifact_path and downgrade the status if the copy cannot be kept.",
    ],
    "REFERENCE_SOURCE_STALE": [
        "Restore the exact source bytes that were checked.",
        "If a corrected version was obtained, re-check every quote and update sha256 deliberately.",
        "Record the new version as a separate reference key.",
    ],
    "REFERENCE_UNUSED": [
        "Cite the work where it supports a sentence, or remove it from references.json.",
        "Keep background reading out of the reference list.",
        "Unused references are advisory only.",
    ],
    "QUOTE_NOT_IN_SOURCE": [
        "Copy the quotation exactly from the held source, including punctuation.",
        "Paraphrase without quotation marks if exact wording is not needed, and keep the citation.",
        "Check that the citation points to the source the quote actually comes from.",
    ],
    "QUOTE_UNVERIFIABLE": [
        "Save a UTF-8 text excerpt of the cited page under sources/ and set it as the reference's artifact_path.",
        "Paraphrase without quotation marks and keep the citation.",
        "Remove the quotation if the source cannot be opened.",
    ],
    "QUOTE_UNATTRIBUTED": [
        "Add the citation [@key] for the quoted source in the same sentence.",
        "Remove the quotation marks if the wording is your own.",
        "Delete the quote if its origin is unknown.",
    ],
    "CLAIM_ANCHOR_UNKNOWN": [
        "Use an id that exists in /claims of uriel.project.json.",
        "Add the claim to the project record first, with evidence and a falsifier.",
        "Remove the anchor if the sentence is not a claim.",
    ],
    "CLAIM_ANCHOR_UNSUPPORTED": [
        "Link direct evidence to the claim in uriel.project.json (`uriel add-evidence --claim ID`).",
        "Reword the sentence as a hypothesis or planned analysis.",
        "Remove the claim from the manuscript until evidence exists.",
    ],
    "CLAIM_NOT_REPORTED": [
        "Report the claim in Results and tag the sentence with [claim:ID].",
        "Remove or downgrade the claim in uriel.project.json if the paper no longer makes it.",
        "Explain in the Discussion why a planned claim could not be evaluated.",
    ],
    "COUNTEREVIDENCE_NOT_DISCUSSED": [
        "Discuss the recorded counterevidence in Discussion or Limitations and tag it with [claim:ID].",
        "Explain how the conclusion was narrowed because of it.",
        "If the counterevidence was mis-linked, correct /claims/*/counterevidence_ids deliberately.",
    ],
    "CAUSAL_LANGUAGE_WITHOUT_IDENTIFICATION": [
        "Use associational wording ('was associated with', 'predicted') for observational results.",
        "Record a causal identification strategy in /methods/causal_identification with its assumptions.",
        "Move causal interpretation to clearly labelled speculation in the Discussion.",
    ],
    "STATEMENT_MISSING": [
        "Add the missing declaration to the statements section.",
        "Write 'not applicable' with a one-line reason when the item genuinely does not apply.",
        "Check the target venue's required declarations.",
    ],
    "RESULTS_WITHOUT_DATAPOINTS": [
        "Register the reported values and use {{dp:ID}} markers in Results.",
        "If the results are purely qualitative, set number_policy 'free' for the section and explain why in Methods.",
        "Run `uriel paper dp-add` once per reported quantity.",
    ],
    "TITLE_MISSING": [
        "Set a specific, non-promotional title in paper/paper.json.",
        "Name the population, exposure or intervention, and outcome where possible.",
        "Avoid hype and question titles that imply an answer.",
    ],
    "PAPER_BUILD_STALE": [
        "Rebuild with `uriel paper build --root .` after the final edits.",
        "Do not edit paper/build/ files by hand; edit sections and rebuild.",
        "Run `uriel paper check` first to see what changed.",
    ],
}
_STAT_REPAIRS = [
    "Recompute the statistic from the analysis output and register it with `uriel paper dp-add` so text and data cannot diverge.",
    "Check whether the test was one-sided, used corrected df, or reports a different statistic than written.",
    "Correct the typo in the manuscript or the analysis, then rerun `uriel paper check`.",
]
_DATAPOINT_REPAIRS = [
    "Re-run the analysis with `uriel run -- ...` and refresh with `uriel paper dp-refresh --id ID` (add --confirm-change if the value moved).",
    "Correct the locator, declared value, or relation in paper/datapoints.json deliberately.",
    "Remove the datapoint and every sentence that depends on it if the value cannot be reproduced.",
]


def _repairs(code: str) -> List[str]:
    if code in _REPAIRS:
        return list(_REPAIRS[code])
    if code in prose_lint.REPAIRS:
        return prose_lint.repairs_for(code)
    if code in plan_lock.REPAIRS:
        return plan_lock.repairs_for(code)
    if code in framing.REPAIRS:
        return framing.repairs_for(code)
    if code in model_check.REPAIRS:
        return model_check.repairs_for(code)
    if code.startswith("STAT_"):
        return list(_STAT_REPAIRS)
    if code.startswith("DATAPOINT_"):
        return list(_DATAPOINT_REPAIRS)
    return [
        "Correct the named item and rerun `uriel paper check`.",
        "Narrow the sentence to what the bound evidence shows.",
        "Ask a co-author to verify the passage against its source.",
    ]


def _finding(
    code: str,
    level: str,
    profile: str,
    subject: str,
    message: str,
    *,
    file: Optional[str] = None,
    line: Optional[int] = None,
    excerpt: str = "",
    detail: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if level == "grave" or (level == "submission" and profile == "submission"):
        severity, status = "blocker", "FAIL"
    else:
        severity, status = "warning", "WARN"
    return {
        "code": code,
        "level": level,
        "severity": severity,
        "status": status,
        "subject": subject,
        "message": message,
        "location": {"file": file, "line": line},
        "excerpt": excerpt,
        "detail": dict(detail or {}),
        "repairs": _repairs(code)[:3],
    }


def _blank(match: "re.Match[str]") -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def _line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _normalize_quote(text: str) -> str:
    value = unicodedata.normalize("NFC", text)
    for source, target in (("\u2018", "'"), ("\u2019", "'"), ("\u201c", '"'), ("\u201d", '"'), ("\u00a0", " ")):
        value = value.replace(source, target)
    return " ".join(value.split())


_SENTENCE_END = re.compile(r"[.!?](?=[\s\])\"'\u201d]|$)|\n[ \t]*\n")


@functools.lru_cache(maxsize=16)
def _sentence_ends(text: str) -> Tuple[int, ...]:
    return tuple(match.end() for match in _SENTENCE_END.finditer(text))


def _sentence_bounds(text: str, start: int, end: int) -> Tuple[int, int]:
    """Offsets of the sentence containing [start, end); newlines alone do not end a sentence."""
    ends = _sentence_ends(text)
    index = bisect.bisect_right(ends, start)
    left = ends[index - 1] if index > 0 else 0
    after = bisect.bisect_left(ends, end)
    right = ends[after] if after < len(ends) else len(text)
    return left, right


# ---------------------------------------------------------------------------
# Manifest validation
# ---------------------------------------------------------------------------

def _validate_manifest(manifest: Mapping[str, Any], profile: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    findings: List[Dict[str, Any]] = []
    sections: List[Dict[str, Any]] = []

    def bad(message: str) -> None:
        findings.append(_finding("PAPER_MANIFEST_INVALID", "grave", profile, PAPER_FILE, message, file=PAPER_FILE))

    if manifest.get("schema") != PAPER_SCHEMA:
        bad("schema must be {0}.".format(PAPER_SCHEMA))
    if manifest.get("article_type") not in ARTICLE_TYPES:
        bad("article_type must be one of {0}.".format(", ".join(ARTICLE_TYPES)))
    title = manifest.get("title")
    if not isinstance(title, str) or len(title.strip()) < 8:
        findings.append(_finding("TITLE_MISSING", "submission", profile, "Title",
                                 "The manuscript has no specific title in paper/paper.json.", file=PAPER_FILE))
    raw_sections = manifest.get("sections")
    if not isinstance(raw_sections, list) or not raw_sections or len(raw_sections) > MAX_SECTIONS:
        bad("sections must be a non-empty array of at most {0} entries.".format(MAX_SECTIONS))
        return findings, sections
    seen_ids: Set[str] = set()
    seen_files: Set[str] = set()
    for index, row in enumerate(raw_sections):
        if not isinstance(row, Mapping):
            bad("sections[{0}] must be an object.".format(index))
            continue
        section_id, file_name, kind = row.get("id"), row.get("file"), row.get("kind")
        if not isinstance(section_id, str) or not _SECTION_ID.match(section_id) or section_id in seen_ids:
            bad("sections[{0}].id must be a unique lowercase identifier.".format(index))
            continue
        if not isinstance(file_name, str) or not file_name.startswith("sections/") or not file_name.endswith(".md") or file_name in seen_files:
            bad("sections[{0}].file must be a unique sections/*.md path.".format(index))
            continue
        try:
            safe_relative_path(file_name)
        except Refusal:
            bad("sections[{0}].file is not a safe relative path.".format(index))
            continue
        if kind not in SECTION_KINDS:
            bad("sections[{0}].kind must be one of {1}.".format(index, ", ".join(SECTION_KINDS)))
            continue
        policy = row.get("number_policy", DEFAULT_NUMBER_POLICY[str(kind)])
        if policy not in NUMBER_POLICIES:
            bad("sections[{0}].number_policy must be one of {1}.".format(index, ", ".join(NUMBER_POLICIES)))
            continue
        seen_ids.add(section_id)
        seen_files.add(file_name)
        sections.append({
            "id": section_id,
            "file": file_name,
            "kind": kind,
            "title": str(row.get("title") or section_id.replace("_", " ").title()),
            "required": row.get("required", True) is not False,
            "number_policy": policy,
        })
    limits = manifest.get("word_limits", {})
    if not isinstance(limits, Mapping) or any(
        not isinstance(value, int) or isinstance(value, bool) or value <= 0 for value in limits.values()
    ):
        bad("word_limits must map section ids to positive integers.")
    return findings, sections


# ---------------------------------------------------------------------------
# References
# ---------------------------------------------------------------------------

def _reference_checks(
    root: Path,
    references: Mapping[str, Any],
    profile: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Dict[str, Any]]]:
    findings: List[Dict[str, Any]] = []
    table: Dict[str, Dict[str, Any]] = {}
    if references.get("schema") != REFERENCES_SCHEMA or not isinstance(references.get("references"), list):
        findings.append(_finding("REFERENCES_INVALID", "grave", profile, REFERENCES_FILE,
                                 "references.json must use schema {0} with a references array.".format(REFERENCES_SCHEMA),
                                 file=REFERENCES_FILE))
        return findings, table
    rows = references["references"]
    if len(rows) > MAX_REFERENCES:
        findings.append(_finding("REFERENCES_INVALID", "grave", profile, REFERENCES_FILE,
                                 "references.json exceeds {0} entries.".format(MAX_REFERENCES), file=REFERENCES_FILE))
        return findings, table
    this_year = _dt.date.today().year
    dois: Dict[str, List[str]] = {}
    for index, row in enumerate(rows):
        if not isinstance(row, Mapping) or not isinstance(row.get("key"), str) or not _KEY.match(row["key"]):
            findings.append(_finding("REFERENCES_INVALID", "grave", profile, "references[{0}]".format(index),
                                     "Each reference needs a portable key.", file=REFERENCES_FILE))
            continue
        key = row["key"]
        if key in table:
            findings.append(_finding("REFERENCE_KEY_DUPLICATE", "grave", profile, key,
                                     "The reference key is defined more than once.", file=REFERENCES_FILE))
            continue
        entry: Dict[str, Any] = {"row": row, "held_text": None, "status": "unverified"}
        table[key] = entry
        authors = row.get("authors")
        year = row.get("year")
        title = row.get("title")
        missing = []
        if not isinstance(authors, list) or not authors or not all(isinstance(item, str) and item.strip() for item in authors):
            missing.append("authors")
        if not isinstance(year, int) or isinstance(year, bool):
            missing.append("year")
        if not isinstance(title, str) or len(title.strip()) < 4:
            missing.append("title")
        if not isinstance(row.get("venue"), str) or not str(row.get("venue")).strip():
            missing.append("venue")
        if missing:
            findings.append(_finding("REFERENCE_INCOMPLETE", "submission", profile, key,
                                     "The reference is missing: {0}.".format(", ".join(missing)), file=REFERENCES_FILE))
        if isinstance(year, int) and not isinstance(year, bool) and not 1400 <= year <= this_year + 1:
            findings.append(_finding("REFERENCE_YEAR_IMPLAUSIBLE", "grave", profile, key,
                                     "The publication year {0} is not plausible.".format(year), file=REFERENCES_FILE))
        doi = str(row.get("doi", "") or "").strip()
        if doi:
            normalized = re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", doi, flags=re.IGNORECASE)
            if not _DOI.match(normalized) or re.search(r"10\.0000|example|xxxx", normalized, re.IGNORECASE):
                findings.append(_finding("REFERENCE_DOI_INVALID", "submission", profile, key,
                                         "The DOI is malformed or a placeholder.", file=REFERENCES_FILE,
                                         detail={"doi": doi}))
            else:
                dois.setdefault(normalized.lower(), []).append(key)
        verification = row.get("verification") if isinstance(row.get("verification"), Mapping) else {}
        status = verification.get("status", "unverified")
        if status not in VERIFICATION_STATUSES:
            findings.append(_finding("REFERENCES_INVALID", "grave", profile, key,
                                     "verification.status must be one of {0}.".format(", ".join(VERIFICATION_STATUSES)),
                                     file=REFERENCES_FILE))
            status = "unverified"
        source_current = False
        artifact = str(row.get("artifact_path", "") or "").strip()
        if artifact:
            try:
                target = guard_path(root, root / safe_relative_path(artifact), must_exist=True)
                if not target.is_file() or is_reparse_or_link(target):
                    raise Refusal("not a regular file", code="REFERENCE_SOURCE_MISSING")
            except Refusal:
                findings.append(_finding("REFERENCE_SOURCE_MISSING", "grave", profile, key,
                                         "The held source file for this reference is missing.", file=REFERENCES_FILE,
                                         detail={"artifact_path": artifact}))
            else:
                digest = sha256_file(target)
                if digest != str(row.get("sha256", "")).lower():
                    findings.append(_finding("REFERENCE_SOURCE_STALE", "grave", profile, key,
                                             "The held source bytes differ from the recorded sha256.", file=REFERENCES_FILE,
                                             detail={"artifact_path": artifact, "current_sha256": digest}))
                else:
                    source_current = True
                    if target.suffix.lower() in TEXT_SOURCE_SUFFIXES and target.stat().st_size <= dp.MAX_ARTIFACT_BYTES:
                        try:
                            entry["held_text"] = _normalize_quote(target.read_bytes().decode("utf-8"))
                        except UnicodeDecodeError:
                            entry["held_text"] = None
        # A verified status is a human attestation (date and note), never inferred from a
        # matching file: an assistant can write a plausible file just as easily as cite one.
        if status in ("held", "metadata_checked"):
            checked = str(verification.get("checked_on", ""))
            note = str(verification.get("note", ""))
            try:
                _dt.date.fromisoformat(checked)
                attested = len(note.strip()) >= 8
            except ValueError:
                attested = False
            if not attested or (status == "held" and not source_current):
                status = "unverified"
        entry["status"] = status
    for doi, keys in sorted(dois.items()):
        if len(keys) > 1:
            findings.append(_finding("REFERENCE_DOI_DUPLICATE", "submission", profile, ", ".join(keys),
                                     "Several keys share one DOI.", file=REFERENCES_FILE, detail={"doi": doi}))
    return findings, table


def _format_reference(number: int, row: Mapping[str, Any]) -> str:
    authors = [str(item).strip() for item in row.get("authors", []) if str(item).strip()]
    if len(authors) > 1:
        author_text = ", ".join(authors[:-1]) + ", & " + authors[-1]
    else:
        author_text = authors[0] if authors else "Anonymous"
    parts = ["{0}. {1} ({2}). {3}.".format(number, author_text, row.get("year", "n.d."), str(row.get("title", "")).strip().rstrip("."))]
    venue = str(row.get("venue", "") or "").strip()
    if venue:
        detail = "*{0}*".format(venue)
        if row.get("volume"):
            detail += ", {0}".format(row["volume"])
        if row.get("issue"):
            detail += "({0})".format(row["issue"])
        if row.get("pages"):
            detail += ", {0}".format(row["pages"])
        parts.append(detail + ".")
    doi = str(row.get("doi", "") or "").strip()
    if doi:
        parts.append("https://doi.org/" + re.sub(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)", "", doi, flags=re.IGNORECASE))
    elif row.get("url"):
        parts.append(str(row["url"]).strip())
    return " ".join(parts)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _parse_citation(inner: str) -> Optional[List[Tuple[str, str]]]:
    output: List[Tuple[str, str]] = []
    for part in ("@" + inner).split(";"):
        match = _CITE_PART.match(part.strip())
        if not match:
            return None
        output.append((match.group(1), (match.group(2) or "").strip()))
    return output


def render_section(
    text: str,
    displays: Mapping[str, str],
    numbers: Optional[Mapping[str, int]] = None,
    *,
    keep_lines: bool = False,
) -> str:
    """Render markup; ``keep_lines`` preserves line numbering for checks."""
    if keep_lines:
        rendered = prose_lint._HTML_COMMENT.sub(_blank, text)
    else:
        rendered = prose_lint._HTML_COMMENT.sub("", text)
    rendered = _DP_MARKER.sub(lambda m: displays.get(m.group(1), "[dp:{0}]".format(m.group(1))), rendered)
    rendered = _LIT_MARKER.sub(lambda m: m.group(1), rendered)

    def citation(match: "re.Match[str]") -> str:
        parsed = _parse_citation(match.group(1))
        if parsed is None:
            return match.group(0)
        labels = []
        for key, locator in parsed:
            number = (numbers or {}).get(key)
            label = str(number) if number is not None else "?"
            labels.append(label + (", " + locator if locator else ""))
        joiner = "; " if any(locator for _, locator in parsed) else ", "
        return "[" + joiner.join(labels) + "]"

    rendered = _CITATION.sub(citation, rendered)
    rendered = _ANY_ANCHOR.sub("", rendered)
    if not keep_lines:
        rendered = re.sub(r"[ \t]+\n", "\n", rendered)
        rendered = re.sub(r"\n{3,}", "\n\n", rendered).strip()
    return rendered


# ---------------------------------------------------------------------------
# Check
# ---------------------------------------------------------------------------

def _scrub_markup(text: str) -> str:
    scrubbed = prose_lint.mask_non_prose(text)
    for pattern in (_DP_MARKER, _LIT_MARKER, _CITATION, _CLAIM_ANCHOR, _ALT_OR_MODEL_ANCHOR, _NUMERIC_CITATION):
        scrubbed = pattern.sub(_blank, scrubbed)
    return scrubbed


def _number_findings(section: Mapping[str, Any], raw: str, profile: str) -> List[Dict[str, Any]]:
    policy = section["number_policy"]
    if policy == "free":
        return []
    scrubbed = _scrub_markup(raw)
    by_line: Dict[int, List[str]] = {}
    for match in _NUMBER.finditer(scrubbed):
        token = match.group(0)
        line_start = scrubbed.rfind("\n", 0, match.start()) + 1
        line_text = scrubbed[line_start: scrubbed.find("\n", match.end()) if scrubbed.find("\n", match.end()) >= 0 else len(scrubbed)]
        if line_text.lstrip().startswith("#"):
            continue
        if re.fullmatch(r"(?:1[89]|20)\d{2}", token):
            continue
        before = scrubbed[max(line_start, match.start() - 40): match.start()]
        if _NUMBER_LABEL.search(before):
            continue
        if _CONFIDENCE_LEVEL.match(scrubbed[match.end(): match.end() + 24]):
            continue  # interval coverage level such as "95% CI"
        if re.match(r"\s*[.)]\s", scrubbed[match.end(): match.end() + 3]) and not scrubbed[line_start: match.start()].strip():
            continue  # list enumerator
        if policy == "cited_or_bound":
            start, end = _sentence_bounds(raw, match.start(), match.end())
            sentence = raw[start:end]
            if _CITATION.search(sentence) or _DP_MARKER.search(sentence) or prose_lint._CITATION_PRESENT.search(sentence):
                continue
        by_line.setdefault(_line_of(scrubbed, match.start()), []).append(token)
    findings = []
    for line, tokens in sorted(by_line.items()):
        if policy == "bound":
            findings.append(_finding(
                "UNBOUND_NUMBER", "submission", profile, "Section {0}".format(section["id"]),
                "Typed numbers in a bound section are not traceable to data: {0}.".format(", ".join(tokens[:8])),
                file="{0}/{1}".format(PAPER_DIR, section["file"]), line=line, detail={"tokens": tokens},
            ))
        else:
            findings.append(_finding(
                "UNSOURCED_NUMBER", "submission", profile, "Section {0}".format(section["id"]),
                "Numbers appear in a sentence with no citation or datapoint: {0}.".format(", ".join(tokens[:8])),
                file="{0}/{1}".format(PAPER_DIR, section["file"]), line=line, detail={"tokens": tokens},
            ))
    return findings


def check_paper(root: Union[str, Path], *, profile: str = "draft") -> Dict[str, Any]:
    """Run every manuscript check; read-only."""
    if profile not in CHECK_PROFILES:
        raise Refusal(
            "Unknown paper check profile.",
            code="PAPER_PROFILE_INVALID",
            details={"profile": profile},
            repairs=[
                "Use --profile draft while writing.",
                "Use --profile submission before building the version you will submit.",
                "Run `uriel paper check --help` for details.",
            ],
        )
    paths = paths_for(root)
    project = load_project(paths.root)
    manifest = _load_manifest(paths.root)
    findings, sections = _validate_manifest(manifest, profile)
    references = _load_references(paths.root)
    ref_findings, ref_table = _reference_checks(paths.root, references, profile)
    findings.extend(ref_findings)

    observed = build_manifest(paths.root, persist=False)
    manifest_paths = {str(row["relative_path"]): str(row["sha256"]) for row in observed.get("records", [])}
    registry = dp.load_registry(paths.root)
    dp_report = dp.verify_registry(paths.root, registry=registry, project=project, manifest_paths=manifest_paths)
    displays = {row["id"]: row["display"] for row in dp_report["datapoints"] if row["status"] == "VERIFIED"}
    for issue in dp_report["issues"]:
        findings.append(_finding(issue["code"], issue["level"], profile, "Datapoint {0}".format(issue["subject"]),
                                 issue["message"], file=dp.REGISTRY_RELATIVE_PATH, detail=issue.get("detail")))
    registered_ids = {
        str(row.get("id")) for row in registry.get("datapoints", []) if isinstance(row, Mapping)
    } if isinstance(registry.get("datapoints"), list) else set()

    claims = {
        str(row.get("id")): row for row in project.get("claims", [])
        if isinstance(row, Mapping) and row.get("id")
    } if isinstance(project.get("claims"), list) else {}
    evidence_ids = {
        str(row.get("id")) for row in project.get("evidence", []) if isinstance(row, Mapping) and row.get("id")
    } if isinstance(project.get("evidence"), list) else set()
    methods = project.get("methods") if isinstance(project.get("methods"), Mapping) else {}
    causal_method = str(methods.get("causal_identification", "") or "").strip()
    causal_declared = len(causal_method) >= 16 and not causal_method.casefold().startswith(("not_applicable", "n/a"))

    used_dps: Set[str] = set()
    cited: List[str] = []
    anchors: Dict[str, Set[str]] = {}
    section_rows: List[Dict[str, Any]] = []
    combined_rendered: List[str] = []
    limits = manifest.get("word_limits") if isinstance(manifest.get("word_limits"), Mapping) else {}
    listed_files = {section["file"] for section in sections}
    sections_dir = paths.root / PAPER_DIR / "sections"
    if sections_dir.is_dir() and not is_reparse_or_link(sections_dir):
        for stray in sorted(sections_dir.glob("*.md")):
            relative = "sections/" + stray.name
            if relative not in listed_files:
                findings.append(_finding("SECTION_NOT_IN_MANIFEST", "style", profile, relative,
                                         "A section file exists but is not listed in paper/paper.json.",
                                         file="{0}/{1}".format(PAPER_DIR, relative)))

    stat_tests = 0
    flagged_unverified: Set[str] = set()
    framing_sections: List[Tuple[Mapping[str, Any], str]] = []
    for section in sections:
        file_label = "{0}/{1}".format(PAPER_DIR, section["file"])
        try:
            raw, digest = _read_section(paths.root, section["file"])
        except Refusal as exc:
            findings.append(_finding("SECTION_FILE_MISSING", "grave", profile, "Section {0}".format(section["id"]),
                                     "The section file cannot be read: {0}".format(exc), file=file_label))
            section_rows.append({**section, "sha256": None, "words": 0, "status": "MISSING"})
            continue
        masked = prose_lint.mask_non_prose(raw)
        words = prose_lint.word_count(raw)
        section_rows.append({**section, "sha256": digest, "words": words, "status": "PRESENT"})
        framing_sections.append(({**section, "file_label": file_label}, masked))
        if section["kind"] not in ("methods", "statements"):
            for issue in framing.text_issues(masked, document_level=False):
                findings.append(_finding(issue["code"], issue["level"], profile, "Section {0}".format(section["id"]),
                                         issue["message"], file=file_label, line=issue["line"],
                                         excerpt=issue["excerpt"], detail=issue.get("detail")))

        for match in _ANY_BRACES.finditer(masked):
            if not (_DP_MARKER.fullmatch(match.group(0)) or _LIT_MARKER.fullmatch(match.group(0))):
                findings.append(_finding("MARKUP_INVALID", "grave", profile, "Section {0}".format(section["id"]),
                                         "Unknown or malformed markup: {0}".format(match.group(0)[:60]),
                                         file=file_label, line=_line_of(masked, match.start())))
        leftover = _ANY_BRACES.sub(_blank, masked)
        for match in _OPEN_BRACES.finditer(leftover):
            findings.append(_finding("MARKUP_INVALID", "grave", profile, "Section {0}".format(section["id"]),
                                     "Unbalanced double braces.", file=file_label, line=_line_of(leftover, match.start())))
        for match in _DP_MARKER.finditer(masked):
            identifier = match.group(1)
            used_dps.add(identifier)
            if identifier not in registered_ids:
                findings.append(_finding("DATAPOINT_MARKER_UNKNOWN", "grave", profile, "Datapoint {0}".format(identifier),
                                         "The manuscript uses a datapoint that is not registered.",
                                         file=file_label, line=_line_of(masked, match.start())))
        for match in _CITATION.finditer(masked):
            parsed = _parse_citation(match.group(1))
            if parsed is None:
                findings.append(_finding("CITATION_SYNTAX_INVALID", "grave", profile, "Section {0}".format(section["id"]),
                                         "Citation markup cannot be parsed: {0}".format(match.group(0)[:60]),
                                         file=file_label, line=_line_of(masked, match.start())))
                continue
            for key, _locator in parsed:
                if key not in cited:
                    cited.append(key)
                if key not in ref_table:
                    findings.append(_finding("CITATION_KEY_UNKNOWN", "grave", profile, "Citation {0}".format(key),
                                             "The cited key is not in paper/references.json.",
                                             file=file_label, line=_line_of(masked, match.start())))
                elif ref_table[key]["status"] == "unverified" and key not in flagged_unverified:
                    flagged_unverified.add(key)
                    findings.append(_finding("REFERENCE_UNVERIFIED", "submission", profile, "Citation {0}".format(key),
                                             "No human has confirmed this cited work against its source.",
                                             file=file_label, line=_line_of(masked, match.start())))
        for match in _CLAIM_ANCHOR.finditer(masked):
            claim_id = match.group(1)
            anchors.setdefault(claim_id, set()).add(section["kind"])
            if claim_id not in claims:
                findings.append(_finding("CLAIM_ANCHOR_UNKNOWN", "grave", profile, "Claim {0}".format(claim_id),
                                         "The anchor names a claim that is not in uriel.project.json.",
                                         file=file_label, line=_line_of(masked, match.start())))
        for match in _QUOTE.finditer(masked):
            quote = match.group(1)
            if len(quote.split()) < MIN_QUOTE_WORDS:
                continue
            start, end = _sentence_bounds(masked, match.start(), match.end())
            nearby = _CITATION.search(masked, match.end(), end + 1) or _CITATION.search(masked, start, match.start())
            parsed = _parse_citation(nearby.group(1)) if nearby else None
            line = _line_of(masked, match.start())
            if not parsed:
                if len(quote.split()) >= 8 and not prose_lint._CITATION_PRESENT.search(masked[start:end]):
                    findings.append(_finding("QUOTE_UNATTRIBUTED", "submission", profile, "Section {0}".format(section["id"]),
                                             "A long quotation has no citation in its sentence.", file=file_label, line=line,
                                             excerpt=quote[:120]))
                continue
            key = parsed[0][0]
            held = ref_table.get(key, {}).get("held_text")
            if key not in ref_table:
                continue
            if held is None:
                findings.append(_finding("QUOTE_UNVERIFIABLE", "submission", profile, "Citation {0}".format(key),
                                         "The quotation cannot be checked because no UTF-8 text copy of the source is held.",
                                         file=file_label, line=line, excerpt=quote[:120]))
                continue
            fragments = [part.strip(" ,;") for part in re.split(r"\.\.\.|\u2026|\[\.\.\.\]", _normalize_quote(quote))]
            fragments = [part for part in fragments if len(part.split()) >= 3] or [_normalize_quote(quote)]
            position = 0
            found = True
            for fragment in fragments:
                index = held.find(fragment, position)
                if index < 0:
                    found = False
                    break
                position = index + len(fragment)
            if not found:
                findings.append(_finding("QUOTE_NOT_IN_SOURCE", "grave", profile, "Citation {0}".format(key),
                                         "The quoted words do not occur verbatim in the held source.",
                                         file=file_label, line=line, excerpt=quote[:120]))

        if section["kind"] in ("abstract", "results", "discussion", "conclusion"):
            for match in _CAUSAL.finditer(masked):
                start, end = _sentence_bounds(masked, match.start(), match.end())
                sentence = masked[start:end]
                if section["kind"] in ("discussion",) and not (_DP_MARKER.search(sentence) or _CLAIM_ANCHOR.search(sentence)):
                    continue
                if not causal_declared:
                    findings.append(_finding(
                        "CAUSAL_LANGUAGE_WITHOUT_IDENTIFICATION", "submission", profile, "Section {0}".format(section["id"]),
                        "Causal wording ('{0}') is used but no causal identification strategy is recorded.".format(match.group(0)),
                        file=file_label, line=_line_of(masked, match.start()), excerpt=" ".join(sentence.split())[:160],
                    ))

        if section["required"] and words < MIN_SECTION_WORDS:
            findings.append(_finding("SECTION_EMPTY", "submission", profile, "Section {0}".format(section["id"]),
                                     "The section has {0} words of text outside guide comments.".format(words), file=file_label))
        limit = limits.get(section["id"]) if isinstance(limits, Mapping) else None
        if isinstance(limit, int) and not isinstance(limit, bool) and words > limit:
            findings.append(_finding("WORD_LIMIT_EXCEEDED", "submission", profile, "Section {0}".format(section["id"]),
                                     "The section has {0} words; the limit is {1}.".format(words, limit), file=file_label))
        if section["kind"] == "results" and words >= MIN_SECTION_WORDS and section["number_policy"] != "free" and not _DP_MARKER.search(masked):
            findings.append(_finding("RESULTS_WITHOUT_DATAPOINTS", "submission", profile, "Section {0}".format(section["id"]),
                                     "The results section reports no bound datapoints.", file=file_label))
        if section["kind"] == "statements" and words >= 1:
            for topic, label, pattern in _STATEMENT_TOPICS:
                if not pattern.search(masked):
                    findings.append(_finding("STATEMENT_MISSING", "submission", profile, "Declarations",
                                             "The declarations do not cover {0}.".format(label), file=file_label,
                                             detail={"topic": topic}))
        findings.extend(_number_findings(section, raw, profile))

        lint = prose_lint.lint_text(raw, section_kind=section["kind"])
        filler: List[Dict[str, Any]] = []
        for issue in lint["issues"]:
            if issue["code"] == "FILLER_WORD":
                filler.append(issue)
                continue
            findings.append(_finding(issue["code"], issue["level"], profile, "Section {0}".format(section["id"]),
                                     issue["message"], file=file_label, line=issue["line"], excerpt=issue["excerpt"],
                                     detail=issue.get("detail")))
        if filler:
            examples = sorted({str(row["detail"].get("term", "")).lower() for row in filler})[:10]
            findings.append(_finding("FILLER_WORD", "style", profile, "Section {0}".format(section["id"]),
                                     "{0} filler words or phrases, including: {1}.".format(len(filler), ", ".join(examples)),
                                     file=file_label, line=filler[0]["line"], detail={"count": len(filler), "examples": examples}))

        rendered = render_section(raw, displays, keep_lines=True)
        combined_rendered.append(rendered)
        stats = stat_check.check_text(rendered)
        stat_tests += stats["reported_tests_found"]
        for issue in stats["issues"]:
            findings.append(_finding(issue["code"], "grave" if issue["grave"] else "submission", profile,
                                     "Section {0}".format(section["id"]), issue["message"], file=file_label,
                                     line=issue["line"], excerpt=issue["excerpt"], detail=issue.get("detail")))

    title = manifest.get("title") if isinstance(manifest.get("title"), str) else ""
    if title:
        for issue in prose_lint.lint_text(title)["issues"]:
            if issue["level"] != "style":
                findings.append(_finding(issue["code"], issue["level"], profile, "Title", issue["message"],
                                         file=PAPER_FILE, excerpt=issue["excerpt"], detail=issue.get("detail")))

    for identifier in sorted(registered_ids - used_dps):
        findings.append(_finding("DATAPOINT_UNUSED", "style", profile, "Datapoint {0}".format(identifier),
                                 "The datapoint is registered but never reported.", file=dp.REGISTRY_RELATIVE_PATH))
    for key in sorted(set(ref_table) - set(cited)):
        findings.append(_finding("REFERENCE_UNUSED", "style", profile, "Reference {0}".format(key),
                                 "The reference is never cited.", file=REFERENCES_FILE))

    for claim_id, claim in sorted(claims.items()):
        statement = str(claim.get("statement", "") or "").strip()
        if claim_id in anchors:
            support = [item for item in claim.get("evidence_ids", []) if str(item) in evidence_ids] if isinstance(claim.get("evidence_ids"), list) else []
            if not support:
                findings.append(_finding("CLAIM_ANCHOR_UNSUPPORTED", "submission", profile, "Claim {0}".format(claim_id),
                                         "The manuscript states this claim, but the project links no existing evidence to it."))
        elif len(statement) >= 16 and claim.get("importance", "major") == "major":
            findings.append(_finding("CLAIM_NOT_REPORTED", "submission", profile, "Claim {0}".format(claim_id),
                                     "A major claim in uriel.project.json is never tagged in the manuscript."))
        counter = claim.get("counterevidence_ids") if isinstance(claim.get("counterevidence_ids"), list) else []
        if counter and len(statement) >= 16 and not (anchors.get(claim_id, set()) & {"discussion", "limitations"}):
            findings.append(_finding("COUNTEREVIDENCE_NOT_DISCUSSED", "submission", profile, "Claim {0}".format(claim_id),
                                     "Recorded counterevidence for this claim is not tied to the Discussion or Limitations.",
                                     detail={"counterevidence_ids": [str(item) for item in counter]}))

    datapoint_claims = {
        str(row.get("id")): [str(item) for item in row.get("claim_ids", []) if isinstance(item, str)]
        for row in registry.get("datapoints", []) if isinstance(row, Mapping) and isinstance(row.get("claim_ids"), list)
    } if isinstance(registry.get("datapoints"), list) else {}
    record_issues = (
        framing.project_issues(project)
        + framing.manuscript_issues(project, framing_sections, datapoint_claims)
        + model_check.project_issues(
            project,
            tested_pairs=set(dp._run_provenance(paths.root)),
            current_digests=manifest_paths,
        )
        + model_check.manuscript_issues(project, framing_sections)
    )
    for issue in record_issues:
        detail = dict(issue.get("detail") or {})
        file_label = detail.pop("file", None)
        findings.append(_finding(issue["code"], issue["level"], profile, issue["subject"], issue["message"],
                                 file=file_label, line=issue.get("line"), excerpt=issue.get("excerpt", ""),
                                 detail=detail))

    plan = plan_lock.plan_status(paths.root, project=project)
    combined = "\n".join(combined_rendered)
    for issue in plan_lock.plan_issues(plan, project, combined):
        findings.append(_finding(issue["code"], issue["level"], profile, issue["subject"], issue["message"],
                                 detail=issue.get("detail")))

    level_order = {"grave": 0, "submission": 1, "style": 2}
    findings.sort(key=lambda row: (
        0 if row["severity"] == "blocker" else 1,
        level_order.get(row["level"], 3),
        str(row["location"].get("file") or ""),
        row["location"].get("line") or 0,
        row["code"],
    ))
    blockers = [row for row in findings if row["severity"] == "blocker"]
    inputs = _input_digests(paths.root, sections)
    report: Dict[str, Any] = {
        "schema": PAPER_CHECK_SCHEMA,
        "schema_version": 1,
        "profile": profile,
        "status": "PASS" if not blockers else "FAIL",
        "created_at_utc": utc_now(),
        "project_id": project.get("project_id"),
        "project_sha256": sha256_file(paths.project),
        "paper": {
            "title": title,
            "article_type": manifest.get("article_type"),
            "sections": [
                {key: row.get(key) for key in ("id", "kind", "file", "number_policy", "words", "sha256", "status")}
                for row in section_rows
            ],
        },
        "inputs": inputs,
        "datapoints": {
            "registered": dp_report["datapoint_count"],
            "verified": dp_report["verified_count"],
            "used": sorted(used_dps),
            "relations": dp_report["relations"],
        },
        "references": {
            "registered": len(ref_table),
            "cited": cited,
            "status": {key: value["status"] for key, value in sorted(ref_table.items())},
        },
        "claims": {
            "anchored": {key: sorted(value) for key, value in sorted(anchors.items())},
        },
        "statistics": {"reported_tests_found": stat_tests},
        "plan": {key: plan[key] for key in ("state", "lock_count", "first_lock_preceded_passing_results", "changed_fields")},
        "blocker_count": len(blockers),
        "warning_count": len(findings) - len(blockers),
        "findings": findings,
        "boundaries": {
            "scientific_truth_decided": False,
            "semantic_support_decided": False,
            "writes": 0,
            "network_requests": 0,
        },
    }
    report["report_sha256"] = _report_digest(report)
    return report


def _report_digest(report: Mapping[str, Any]) -> str:
    body = {key: value for key, value in report.items() if key not in ("created_at_utc", "report_sha256")}
    return sha256_text(canonical_json(body))


def _input_digests(root: Path, sections: Sequence[Mapping[str, Any]]) -> Dict[str, Any]:
    def digest(relative: str) -> Optional[str]:
        try:
            target = guard_path(root, root / safe_relative_path(relative))
        except Refusal:
            return None
        return sha256_file(target) if target.is_file() and not is_reparse_or_link(target) else None

    section_digests = {}
    for section in sections:
        section_digests[section["file"]] = digest("{0}/{1}".format(PAPER_DIR, section["file"]))
    return {
        "paper_json_sha256": digest(PAPER_FILE),
        "datapoints_sha256": digest(dp.REGISTRY_RELATIVE_PATH),
        "references_sha256": digest(REFERENCES_FILE),
        "sections": section_digests,
    }


# ---------------------------------------------------------------------------
# Build
# ---------------------------------------------------------------------------

def _render_manuscript(root: Path) -> Tuple[str, str, Dict[str, Any]]:
    """Return (manuscript, number trace, binding) from current verified inputs."""
    project = load_project(root)
    manifest = _load_manifest(root)
    _, sections = _validate_manifest(manifest, "draft")
    references = _load_references(root)
    _, ref_table = _reference_checks(root, references, "draft")
    registry = dp.load_registry(root)
    dp_report = dp.verify_registry(root, registry=registry, project=project)
    verified = {row["id"]: row for row in dp_report["datapoints"] if row["status"] == "VERIFIED"}
    displays = {key: row["display"] for key, row in verified.items()}
    texts: List[Tuple[Mapping[str, Any], str]] = []
    order: List[str] = []
    used: List[str] = []
    for section in sections:
        raw, _digest = _read_section(root, section["file"])
        texts.append((section, raw))
        masked = prose_lint.mask_non_prose(raw)
        for match in _CITATION.finditer(masked):
            for key, _locator in _parse_citation(match.group(1)) or []:
                if key not in order:
                    order.append(key)
        for match in _DP_MARKER.finditer(masked):
            if match.group(1) not in used:
                used.append(match.group(1))
    numbers = {key: index for index, key in enumerate(order, start=1)}
    parts = ["# " + str(manifest.get("title", "")).strip(), ""]
    for section, raw in texts:
        body = render_section(raw, displays, numbers)
        if not body:
            continue
        parts.extend(["## " + section["title"], "", body, ""])
    if order:
        parts.extend(["## References", ""])
        for key in order:
            row = ref_table.get(key, {}).get("row", {"key": key})
            parts.append(_format_reference(numbers[key], row))
        parts.append("")
    manuscript = "\n".join(parts).rstrip() + "\n"
    rows = {str(row.get("id")): row for row in registry.get("datapoints", []) if isinstance(row, Mapping)}
    trace = [
        "# Number trace",
        "",
        "Every number rendered from a datapoint marker, with the exact bytes it was read from.",
        "Regenerated by `uriel paper build`; do not edit by hand.",
        "",
        "| Datapoint | Rendered | Source token | Artifact | SHA-256 (first 16) | Locator | Run provenance |",
        "|---|---|---|---|---|---|---|",
    ]
    for identifier in used:
        row = rows.get(identifier, {})
        entry = verified.get(identifier, {})
        locator = json.dumps(row.get("locator", {}), sort_keys=True, ensure_ascii=False).replace("|", "\\|")
        trace.append("| {0} | {1} | {2} | {3} | {4} | `{5}` | {6} |".format(
            identifier,
            str(entry.get("display", "")).replace("|", "\\|"),
            str(entry.get("token", "")).replace("|", "\\|"),
            row.get("artifact_path", ""),
            str(row.get("sha256", ""))[:16],
            locator,
            entry.get("provenance", "") + (" ({0})".format(entry["receipt_id"]) if entry.get("receipt_id") else ""),
        ))
    trace_text = "\n".join(trace) + "\n"
    binding = {
        "inputs": _input_digests(root, sections),
        "artifacts": {
            row.get("artifact_path"): row.get("sha256")
            for identifier, row in sorted(rows.items()) if identifier in used
        },
        "reference_sources": {
            key: ref_table[key]["row"].get("sha256")
            for key in order if key in ref_table and ref_table[key]["row"].get("artifact_path")
        },
        "citation_order": order,
        "datapoints_rendered": [{"id": key, "display": displays.get(key)} for key in used],
    }
    return manuscript, trace_text, binding


def _build_dir(root: Path) -> Path:
    target = guard_path(root, root / BUILD_DIR)
    if target.exists() and (is_reparse_or_link(target) or not target.is_dir()):
        raise Refusal("paper/build must be a regular directory.", code="PAPER_BUILD_DIRECTORY_INVALID")
    return target


def build_paper(root: Union[str, Path], *, profile: str = "draft") -> Dict[str, Any]:
    """Build the manuscript only when the check passes for ``profile``."""
    paths = paths_for(root)
    report = check_paper(paths.root, profile=profile)
    if report["status"] != "PASS":
        blockers = [row for row in report["findings"] if row["severity"] == "blocker"]
        raise Refusal(
            "The manuscript has {0} blocking finding(s) at the {1} profile; Uriel will not build it.".format(len(blockers), profile),
            code="PAPER_CHECK_FAILED",
            details={"blockers": [
                {"code": row["code"], "subject": row["subject"], "location": row["location"]} for row in blockers[:20]
            ]},
            repairs=[
                "Run `uriel paper check --root . --profile {0}` and repair each blocker.".format(profile),
                "Build with --profile draft to review a working version while submission blockers remain.",
                "Run `uriel next --root .` for the single most important next step.",
            ],
        )
    manuscript, trace, binding = _render_manuscript(paths.root)
    build = _build_dir(paths.root)
    build.mkdir(parents=True, exist_ok=True)
    for relative, text in ((MANUSCRIPT_OUTPUT, manuscript), (TRACE_OUTPUT, trace)):
        target = guard_path(paths.root, paths.root / relative)
        if target.exists() and is_reparse_or_link(target):
            raise Refusal("Refusing to write through a link.", code="PAPER_BUILD_DIRECTORY_INVALID")
        atomic_write(target, text)
    receipt = {
        "schema": PAPER_BUILD_SCHEMA,
        "schema_version": 1,
        "profile": profile,
        "created_at_utc": utc_now(),
        "project_id": report["project_id"],
        "project_sha256": report["project_sha256"],
        "check_report_sha256": report["report_sha256"],
        "check_warning_count": report["warning_count"],
        "binding": binding,
        "outputs": {
            MANUSCRIPT_OUTPUT: sha256_text(manuscript),
            TRACE_OUTPUT: sha256_text(trace),
        },
        "boundaries": {
            "scientific_truth_decided": False,
            "publication_authority": False,
            "blessing": False,
        },
    }
    receipt["receipt_sha256"] = sha256_text(canonical_json(receipt))
    receipt_path = guard_path(paths.root, paths.root / RECEIPT_OUTPUT)
    atomic_write_json(receipt_path, receipt)
    append_ledger(paths.root, "paper.built", {
        "profile": profile,
        "manuscript_sha256": receipt["outputs"][MANUSCRIPT_OUTPUT],
        "receipt_sha256": receipt["receipt_sha256"],
        "check_report_sha256": report["report_sha256"],
    })
    return {
        "status": "BUILT",
        "profile": profile,
        "manuscript": MANUSCRIPT_OUTPUT,
        "number_trace": TRACE_OUTPUT,
        "receipt": RECEIPT_OUTPUT,
        "manuscript_sha256": receipt["outputs"][MANUSCRIPT_OUTPUT],
        "warning_count": report["warning_count"],
        "datapoints_rendered": len(binding["datapoints_rendered"]),
        "citations_rendered": len(binding["citation_order"]),
    }


def verify_build(root: Union[str, Path]) -> Dict[str, Any]:
    """Check that the built manuscript still matches its sources; read-only."""
    paths = paths_for(root)
    receipt_path = guard_path(paths.root, paths.root / RECEIPT_OUTPUT)
    if not receipt_path.is_file() or is_reparse_or_link(receipt_path):
        return {"status": "NOT_BUILT", "current": False, "reasons": ["no build receipt exists"]}
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (ValueError, UnicodeDecodeError):
        return {"status": "STALE", "current": False, "reasons": ["the build receipt is not valid JSON"],
                "receipt": RECEIPT_OUTPUT}
    if not isinstance(receipt, dict):
        return {"status": "STALE", "current": False, "reasons": ["the build receipt is not a JSON object"],
                "receipt": RECEIPT_OUTPUT}
    reasons: List[str] = []
    body = dict(receipt)
    supplied = body.pop("receipt_sha256", None)
    if supplied != sha256_text(canonical_json(body)):
        reasons.append("the build receipt was edited after it was written")
    outputs = receipt.get("outputs") if isinstance(receipt.get("outputs"), dict) else {}
    if set(outputs) != {MANUSCRIPT_OUTPUT, TRACE_OUTPUT}:
        reasons.append("the build receipt does not list exactly the generated outputs")
    for relative, expected in sorted(outputs.items()):
        if relative not in (MANUSCRIPT_OUTPUT, TRACE_OUTPUT):
            continue
        try:
            target = guard_path(paths.root, paths.root / safe_relative_path(relative))
        except Refusal:
            reasons.append("{0} is not a confined project path".format(relative))
            continue
        if not target.is_file() or is_reparse_or_link(target) or sha256_file(target) != expected:
            reasons.append("{0} differs from the build receipt".format(relative))
    try:
        manuscript, trace, binding = _render_manuscript(paths.root)
    except Refusal as exc:
        reasons.append("the sources can no longer be rendered: {0}".format(exc))
    else:
        if sha256_text(manuscript) != (receipt.get("outputs") or {}).get(MANUSCRIPT_OUTPUT):
            reasons.append("the sources now render a different manuscript")
        if binding != receipt.get("binding"):
            reasons.append("input or artifact digests changed since the build")
    if sha256_file(paths.project) != receipt.get("project_sha256"):
        reasons.append("uriel.project.json changed since the build")
    return {
        "status": "CURRENT" if not reasons else "STALE",
        "current": not reasons,
        "profile": receipt.get("profile"),
        "reasons": reasons,
        "receipt": RECEIPT_OUTPUT,
    }


def lint_file(root: Union[str, Path], relative: str) -> Dict[str, Any]:
    """Prose and statistics lint for one project-local UTF-8 text file; read-only."""
    paths = paths_for(root)
    safe = safe_relative_path(relative)
    target = guard_path(paths.root, paths.root / safe, must_exist=True)
    if not target.is_file() or is_reparse_or_link(target):
        raise Refusal("Lint needs one regular project-local file.", code="PAPER_LINT_FILE_REQUIRED",
                      repairs=[
                          "Pass a UTF-8 text or Markdown file inside the project root.",
                          "Copy pasted text into a file under the project first.",
                          "Remove links and parent traversal from the path.",
                      ])
    raw = target.read_bytes()
    if len(raw) > MAX_SECTION_BYTES:
        raise Refusal("The file exceeds the bounded lint size.", code="PAPER_SECTION_TOO_LARGE")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Refusal("Lint needs strict UTF-8 text.", code="PAPER_SECTION_NOT_UTF8") from exc
    prose = prose_lint.lint_text(text)
    stats = stat_check.check_text(prose_lint.mask_non_prose(text))
    findings = []
    for issue in prose["issues"]:
        findings.append({**issue, "repairs": _repairs(issue["code"])})
    for issue in framing.text_issues(prose_lint.mask_non_prose(text), document_level=prose["word_count"] >= 600):
        findings.append({
            "code": issue["code"], "category": "framing", "level": issue["level"], "line": issue["line"] or 1,
            "excerpt": issue["excerpt"], "message": issue["message"], "detail": issue["detail"],
            "repairs": _repairs(issue["code"]),
        })
    for issue in stats["issues"]:
        findings.append({
            "code": issue["code"], "category": "statistics", "level": "grave" if issue["grave"] else "submission",
            "line": issue["line"], "excerpt": issue["excerpt"], "message": issue["message"],
            "detail": issue["detail"], "repairs": _repairs(issue["code"]),
        })
    findings.sort(key=lambda row: (row["line"], prose_lint.LEVELS.index(row["level"]), row["code"]))
    return {
        "file": target.relative_to(paths.root).as_posix(),
        "sha256": sha256_bytes(raw),
        "word_count": prose["word_count"],
        "filler_per_1000_words": prose["filler_per_1000_words"],
        "reported_tests_found": stats["reported_tests_found"],
        "counts": {level: sum(1 for row in findings if row["level"] == level) for level in prose_lint.LEVELS},
        "status": "FAIL" if any(row["level"] == "grave" for row in findings) else "PASS",
        "findings": findings,
        "boundaries": {"writes": 0, "authorship_detected": False, "scientific_truth_decided": False},
    }


def paper_state(root: Union[str, Path]) -> Dict[str, Any]:
    """Compact state used by the research protocol driver."""
    paths = paths_for(root)
    if not (paths.root / PAPER_FILE).is_file():
        return {"initialized": False}
    return {"initialized": True}


__all__ = [
    "ARTICLE_TYPES",
    "CHECK_PROFILES",
    "PAPER_BUILD_SCHEMA",
    "PAPER_CHECK_SCHEMA",
    "PAPER_SCHEMA",
    "REFERENCES_SCHEMA",
    "build_paper",
    "check_paper",
    "init_paper",
    "lint_file",
    "paper_state",
    "render_section",
    "verify_build",
]
