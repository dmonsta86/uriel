"""Bounded, read-only manuscript production and citation preflight.

Findings are mechanical review leads. They do not establish authorship, source
support, scientific validity, Gate status, or publication authority.
"""
from __future__ import annotations

import os
import re
import stat
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple, Union

from .core import (
    Refusal,
    canonical_json,
    guard_path,
    is_reparse_or_link,
    load_project,
    paths_for,
    safe_relative_path,
    sha256_bytes,
    sha256_file,
    sha256_text,
)


PREFLIGHT_SCHEMA = "uriel.paper_preflight.v1"
MAX_TEXT_BYTES = 4 * 1024 * 1024
MAX_LINES = 100_000
MAX_FINDINGS = 200
MAX_EXCERPT_CHARS = 160

_PROCESS_PATTERNS = (
    (re.compile(r"cite[^\n]{0,512}|【turn\d+(?:search|view|fetch)\d+[^】]{0,512}】"), "TOOL_CITATION_RESIDUE", "A tool citation marker remains in the manuscript."),
    (re.compile(r"\bsandbox:/(?:mnt/data/)?\S+|\bfile:///mnt/data/\S+", re.I), "SANDBOX_LINK_RESIDUE", "A local sandbox link remains in the manuscript."),
    (re.compile(r"^\s*(?:#{1,3}\s*)?(?:assistant|system|developer|tool)(?:\s+to=\S+)?\s*[:：]", re.I), "CHAT_ROLE_RESIDUE", "A chat role label appears at the start of a line."),
    (re.compile(r"\b(?:as an AI language model|I (?:cannot|can't) browse the (?:internet|web))\b|:::writing\{", re.I), "ASSISTANT_META_RESIDUE", "Assistant or drafting metadata remains in the manuscript."),
)
_PLACEHOLDER_PATTERNS = (
    (re.compile(r"\b(?:TODO|TBD|FIXME)\s*[:\]\)]|\[(?:citation needed|insert [^\]\n]{1,70})\]|<insert [^>\n]{1,70}>", re.I), "UNRESOLVED_PLACEHOLDER", "An explicit drafting placeholder needs review."),
    (re.compile(r"\bLorem ipsum\b", re.I), "FILLER_TEXT", "Filler text remains in the manuscript."),
    (re.compile(r"^(?:<{7}|={7}|>{7})(?:\s|$)"), "MERGE_CONFLICT_MARKER", "A merge-conflict marker remains in the manuscript."),
)
_CERTAINTY_PATTERN = re.compile(
    r"\b(?:proves? beyond (?:any |all )?doubt|definitively proves?|"
    r"unquestionably establishes?|guarantees? that|first ever to|"
    r"revolutionary breakthrough)\b",
    re.I,
)
_PANDOC_CITATION = re.compile(r"\[[ \t]{0,8}@([A-Za-z0-9:_-]{1,128})[^\]\n]{0,512}\]")
_PANDOC_KEY = re.compile(r"@([A-Za-z0-9:_-]+)")
_LATEX_CITATION = re.compile(r"\\cite[a-zA-Z*]{0,24}\s{0,8}(?:\[[^\]\n]{0,512}\]\s{0,8}){0,2}\{([^}\n]{0,512})\}")
_BIBITEM = re.compile(r"\\bibitem(?:\[[^\]\n]{0,512}\])?\s{0,8}\{([^}\n]{1,128})\}")
_BIBTEX = re.compile(r"^\s*@(?:article|book|inproceedings|misc|phdthesis|mastersthesis|techreport|unpublished)\s*\{\s*([^,\s{}]+)\s*,", re.I)
_PANDOC_DEFINITION = re.compile(r"^\s*\[@([A-Za-z0-9:_-]{1,128})\]\s*:")
_REFERENCE_HEADING = re.compile(r"^\s*(?:#{1,6}\s*)?(?:\d+(?:\.\d+)*\.?\s+)?(?:references|bibliography)\s*$", re.I)
_NUMBERED_REFERENCE = re.compile(r"^\s*\[(\d{1,3})\]\s+\S")
_NUMBERED_CITATION = re.compile(r"\[[ \t]{0,8}(\d{1,3}(?:[ \t]{0,8}[-–,][ \t]{0,8}\d{1,3}){0,64})[ \t]{0,8}\]")
_OBJECT_REF = re.compile(r"\b(Fig(?:ure)?|Table)\.?[ \t]{1,16}(\d{1,3})\b", re.I)
_OBJECT_CAPTION = re.compile(r"^[ \t]*(?:\*\*[ \t]{0,4})?(Fig(?:ure)?|Table)\.?[ \t]{1,16}(\d{1,3})[ \t]{0,8}(?:[.:—–-]|\*\*[ \t]{0,8}[.:—–-])", re.I)
_UNRESOLVED_OBJECT = re.compile(r"\b(?:Fig(?:ure)?|Table)\.?[ \t]{1,16}\?{1,3}(?!\?)", re.I)
_LATEX_LABEL = re.compile(r"\\label\{([^}\n]{1,128})\}")
_LATEX_REF = re.compile(r"\\(?:eq|auto|page|c|C)?ref\{([^}\n]{0,128})\}")


def _refusal(message: str, code: str) -> Refusal:
    return Refusal(
        message,
        code=code,
        repairs=[
            "Select one bounded, strict UTF-8 manuscript or extracted-text copy.",
            "Preserve the original and review a smaller section when the paper exceeds the limit.",
            "Fix the input format, then rerun the read-only preflight.",
        ],
    )


def _excerpt(line: str) -> str:
    clean = " ".join(line.strip().split())
    if len(clean) > MAX_EXCERPT_CHARS:
        return clean[: MAX_EXCERPT_CHARS - 1] + "…"
    return clean


def _read_manuscript(root: Path, relative_path: str) -> Tuple[Path, bytes, str]:
    safe = safe_relative_path(relative_path)
    target = guard_path(root, root / safe, must_exist=True)
    if not target.is_file() or is_reparse_or_link(target):
        raise _refusal("Paper preflight requires one regular project-local manuscript.", "PREFLIGHT_FILE_REQUIRED")
    if target.stat().st_size > MAX_TEXT_BYTES:
        raise _refusal("Paper preflight manuscript exceeds the bounded input limit.", "PREFLIGHT_TEXT_TOO_LARGE")
    with target.open("rb") as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):
            raise _refusal("Paper preflight requires a regular manuscript file.", "PREFLIGHT_FILE_REQUIRED")
        raw = stream.read(MAX_TEXT_BYTES + 1)
    if len(raw) > MAX_TEXT_BYTES:
        raise _refusal("Paper preflight manuscript exceeds the bounded input limit.", "PREFLIGHT_TEXT_TOO_LARGE")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _refusal("Paper preflight manuscript is not strict UTF-8.", "PREFLIGHT_UTF8_REQUIRED") from exc
    return target, raw, text


def _paragraphs(lines: Sequence[str]) -> List[Tuple[int, str]]:
    paragraphs: List[Tuple[int, str]] = []
    pieces: List[str] = []
    start = 0
    fenced = False
    for number, line in enumerate(lines, start=1):
        if re.match(r"^\s*(```|~~~)", line):
            if pieces:
                paragraphs.append((start, " ".join(pieces)))
                pieces = []
            fenced = not fenced
            continue
        if fenced or not line.strip() or line.lstrip().startswith(("#", ">", "|")):
            if pieces:
                paragraphs.append((start, " ".join(pieces)))
                pieces = []
            continue
        if not pieces:
            start = number
        pieces.append(line.strip())
    if pieces:
        paragraphs.append((start, " ".join(pieces)))
    return paragraphs


def analyze_text(text: str) -> Dict[str, Any]:
    """Return bounded deterministic review leads for already extracted UTF-8 text.

    The function performs no file, network, subprocess, or model operation.
    Citations are checked against bibliography keys only when explicit keys
    are present in the supplied text; semantic source support is never decided.
    """
    if not isinstance(text, str):
        raise _refusal("Paper preflight requires text, not binary or a parsed object.", "PREFLIGHT_TEXT_REQUIRED")
    try:
        size = len(text.encode("utf-8"))
    except UnicodeEncodeError as exc:
        raise _refusal("Paper preflight requires valid UTF-8 text.", "PREFLIGHT_UTF8_REQUIRED") from exc
    if size > MAX_TEXT_BYTES:
        raise _refusal("Paper preflight text exceeds the bounded input limit.", "PREFLIGHT_TEXT_TOO_LARGE")
    lines = text.splitlines()
    if len(lines) > MAX_LINES:
        raise _refusal("Paper preflight text exceeds the bounded line limit.", "PREFLIGHT_LINE_LIMIT")

    findings: List[Dict[str, Any]] = []
    suppressed = 0
    seen: Set[Tuple[str, int]] = set()

    def add(check_id: str, severity: str, number: int, message: str, line: str) -> None:
        nonlocal suppressed
        key = (check_id, number)
        if key in seen:
            return
        seen.add(key)
        if len(findings) >= MAX_FINDINGS:
            suppressed += 1
            return
        findings.append({
            "check_id": check_id,
            "severity": severity,
            "line": number,
            "message": message,
            "excerpt": _excerpt(line),
        })

    bibliography_keys: Set[str] = set()
    numeric_entries: Set[int] = set()
    bibliography_start: Optional[int] = None
    captions: Dict[str, Set[str]] = {"figure": set(), "table": set()}
    labels: Set[str] = set()
    for number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if bibliography_start is None and len(stripped) <= 128 and _REFERENCE_HEADING.fullmatch(stripped):
            bibliography_start = number
        for pattern in (_BIBITEM, _BIBTEX, _PANDOC_DEFINITION):
            match = pattern.search(line)
            if match:
                bibliography_keys.add(match.group(1))
        if bibliography_start is not None and number > bibliography_start:
            match = _NUMBERED_REFERENCE.match(line)
            if match:
                value = int(match.group(1))
                if value in numeric_entries:
                    add("DUPLICATE_NUMERIC_REFERENCE", "WARNING", number, "This numbered bibliography entry appears more than once.", line)
                numeric_entries.add(value)
        caption = _OBJECT_CAPTION.match(line)
        if caption:
            kind = "table" if caption.group(1).casefold() == "table" else "figure"
            if caption.group(2) in captions[kind]:
                add("DUPLICATE_OBJECT_CAPTION", "WARNING", number, "This {0} caption number appears more than once.".format(kind), line)
            captions[kind].add(caption.group(2))
        for label in _LATEX_LABEL.findall(line):
            labels.add(label)

    for number, line in enumerate(lines, start=1):
        for pattern, check_id, message in _PROCESS_PATTERNS:
            if pattern.search(line):
                add(check_id, "ERROR", number, message, line)
        for pattern, check_id, message in _PLACEHOLDER_PATTERNS:
            if pattern.search(line):
                add(check_id, "WARNING", number, message, line)
        if _CERTAINTY_PATTERN.search(line):
            add("CERTAINTY_OR_HYPE_LEAD", "INFO", number, "Review whether this strong wording is supported and properly scoped.", line)
        if _UNRESOLVED_OBJECT.search(line):
            add("UNRESOLVED_OBJECT_REFERENCE", "WARNING", number, "A figure or table reference still has an unresolved number.", line)

        if "[@" in line and line.count("[@") > len(_PANDOC_CITATION.findall(line)) + len(_PANDOC_DEFINITION.findall(line)):
            add("MALFORMED_CITATION", "WARNING", number, "A bracketed citation appears unclosed or malformed.", line)
        if "\\cite" in line and len(re.findall(r"\\cite[a-zA-Z*]*", line)) > len(_LATEX_CITATION.findall(line)):
            add("MALFORMED_CITATION", "WARNING", number, "A LaTeX citation appears unclosed or malformed.", line)
        if any(not match.group(1).strip() for match in _LATEX_CITATION.finditer(line)):
            add("MALFORMED_CITATION", "WARNING", number, "A LaTeX citation has no key.", line)
        if bibliography_keys:
            cited: Set[str] = set()
            if not _PANDOC_DEFINITION.match(line):
                for match in _PANDOC_CITATION.finditer(line):
                    cited.update(_PANDOC_KEY.findall(match.group(0)))
            for match in _LATEX_CITATION.finditer(line):
                cited.update(part.strip() for part in match.group(1).split(",") if part.strip())
            unknown = sorted(cited - bibliography_keys)
            if unknown:
                add("UNMATCHED_BIBLIOGRAPHY_KEY", "WARNING", number, "Citation key(s) absent from explicit local bibliography: {0}.".format(", ".join(unknown[:5])), line)

        if numeric_entries and (bibliography_start is None or number < bibliography_start):
            cited_numbers: Set[int] = set()
            for match in _NUMBERED_CITATION.finditer(line):
                body = match.group(1).replace("–", "-")
                for part in body.split(","):
                    part = part.strip()
                    if "-" in part:
                        bounds = part.split("-", 1)
                        low, high = int(bounds[0]), int(bounds[1])
                        if low > high or high - low > 100:
                            add("MALFORMED_NUMERIC_CITATION", "WARNING", number, "A numeric citation range is reversed or unusually large.", line)
                        else:
                            cited_numbers.update(range(low, high + 1))
                    else:
                        cited_numbers.add(int(part))
            unknown_numbers = sorted(cited_numbers - numeric_entries)
            if unknown_numbers:
                add("UNMATCHED_NUMERIC_REFERENCE", "WARNING", number, "Citation number(s) absent from the explicit local reference list: {0}.".format(", ".join(map(str, unknown_numbers[:5]))), line)

        if not _OBJECT_CAPTION.match(line):
            for match in _OBJECT_REF.finditer(line):
                kind = "table" if match.group(1).casefold() == "table" else "figure"
                if captions[kind] and match.group(2) not in captions[kind]:
                    add("UNMATCHED_OBJECT_REFERENCE", "WARNING", number, "This {0} number has no matching caption in the supplied text.".format(kind), line)
        for match in _LATEX_REF.finditer(line):
            key = match.group(1)
            if not key or (labels and key not in labels):
                add("UNMATCHED_LATEX_REFERENCE", "WARNING", number, "This LaTeX reference is empty or absent from the explicit local labels.", line)
        if "\\ref{" in line and len(re.findall(r"\\(?:eq|auto|page|c|C)?ref\{", line)) > len(_LATEX_REF.findall(line)):
            add("MALFORMED_LATEX_REFERENCE", "WARNING", number, "A LaTeX reference appears unclosed or malformed.", line)

    first_paragraph: Dict[str, int] = {}
    for number, paragraph in _paragraphs(lines):
        normalized = " ".join(paragraph.casefold().split())
        if len(normalized) < 100:
            continue
        first = first_paragraph.get(normalized)
        if first is None:
            first_paragraph[normalized] = number
        else:
            add("DUPLICATE_PARAGRAPH", "WARNING", number, "This paragraph repeats the text beginning on line {0}.".format(first), paragraph)

    counts = {severity: sum(row["severity"] == severity for row in findings) for severity in ("ERROR", "WARNING", "INFO")}
    return {
        "schema": PREFLIGHT_SCHEMA,
        "schema_version": 1,
        "status": "REVIEW_REQUIRED" if findings or suppressed else "NO_DETERMINISTIC_LEADS",
        "findings": findings,
        "summary": {
            "input_bytes": size,
            "line_count": len(lines),
            "displayed_finding_count": len(findings),
            "suppressed_finding_count": suppressed,
            "findings_truncated": suppressed > 0,
            "displayed_severity_counts": counts,
            "explicit_bibliography_key_count": len(bibliography_keys),
            "explicit_numeric_reference_count": len(numeric_entries),
            "figure_caption_count": len(captions["figure"]),
            "table_caption_count": len(captions["table"]),
        },
        "manual_review_required": True,
        "boundaries": {
            "advisory_only": True,
            "scientific_truth_decided": False,
            "citation_support_decided": False,
            "gate_authority": False,
            "publication_authority": False,
            "authorship_inference": "NOT_PERFORMED",
            "network_requests": 0,
            "provider_calls": 0,
            "writes": 0,
        },
    }


def preflight_paper(root: Union[Path, str], manuscript_path: str) -> Dict[str, Any]:
    """Inspect one confined initialized-project manuscript without writing state."""
    paths = paths_for(root)
    project = load_project(paths.root)
    manuscript, raw, text = _read_manuscript(paths.root, manuscript_path)
    result = analyze_text(text)
    result["project_id"] = project["project_id"]
    result["project_sha256"] = sha256_file(paths.project)
    result["manuscript"] = {
        "path": manuscript.relative_to(paths.root).as_posix(),
        "sha256": sha256_bytes(raw),
        "size_bytes": len(raw),
    }
    result["report_sha256"] = sha256_text(canonical_json(result))
    return result


__all__ = ["PREFLIGHT_SCHEMA", "analyze_text", "preflight_paper"]
