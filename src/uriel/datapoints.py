"""Datapoint registry: every reported number re-extracted from hashed bytes.

A manuscript should not contain a result number that a person (or a model)
typed from memory.  Instead, each reported value is registered once in
``paper/datapoints.json`` with:

- the exact project-local artifact and its SHA-256;
- a deterministic locator (one CSV cell, one JSON Pointer, or one regular
  expression match with a single capture group);
- the value the author believes is there; and
- optional sanity constraints (kind, bounds, GRIM inputs) and cross-datapoint
  relations (sums, ratios, interval ordering, equality across artifacts).

Verification re-reads the artifact, refuses changed bytes, re-extracts the
token, compares it with the declared value, and applies the sanity rules.  The
Paper Builder renders ``{{dp:ID}}`` markers only from verified tokens, so a
stale or mistyped number cannot reach a built manuscript.

The registry proves which bytes a number came from and that it was copied
exactly.  It does not prove that the analysis producing those bytes was
correct, appropriate, or complete.
"""
from __future__ import annotations

import csv
import io
import json
import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Dict, List, Mapping, MutableMapping, Optional, Sequence, Tuple, Union

from .core import (
    Refusal,
    append_ledger,
    atomic_write_json,
    guard_path,
    is_reparse_or_link,
    latest_receipts,
    load_project,
    paths_for,
    read_json,
    safe_relative_path,
    sha256_bytes,
    utc_now,
    verify_receipt,
)
from .stat_check import grim_consistent

DATAPOINTS_SCHEMA = "uriel.datapoints.v1"
REGISTRY_RELATIVE_PATH = "paper/datapoints.json"
LOCATOR_TYPES = ("csv_cell", "json_pointer", "text_regex")
KINDS = (
    "count",
    "proportion",
    "percent",
    "p_value",
    "correlation",
    "mean",
    "median",
    "sd",
    "se",
    "variance",
    "estimate",
    "ci_bound",
    "statistic",
    "ratio",
    "text",
    "other",
)
RELATION_TYPES = ("sum", "ratio", "ci", "le", "equal")
STRUCTURAL_CODES = frozenset({
    "DATAPOINT_REGISTRY_INVALID",
    "DATAPOINT_LOCATOR_INVALID",
    "DATAPOINT_FORMAT_INVALID",
    "DATAPOINT_ARTIFACT_CIRCULAR",
    "DATAPOINT_ID_DUPLICATE",
})
MAX_ARTIFACT_BYTES = 64 * 1024 * 1024
MAX_PATTERN_LENGTH = 512
MAX_DATAPOINTS = 5000
_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_FORMAT_RE = re.compile(r"^(?P<comma>,)?\.(?P<places>\d{1,2})(?P<type>[f%])(?P<nolead>~)?$")
_NUMERIC_TOKEN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_KIND_BOUNDS: Dict[str, Tuple[Optional[Decimal], Optional[Decimal]]] = {
    "count": (Decimal(0), None),
    "proportion": (Decimal(0), Decimal(1)),
    "percent": (Decimal(0), Decimal(100)),
    "p_value": (Decimal(0), Decimal(1)),
    "correlation": (Decimal(-1), Decimal(1)),
    "sd": (Decimal(0), None),
    "se": (Decimal(0), None),
    "variance": (Decimal(0), None),
}


class DatapointError(Refusal):
    """A datapoint could not be located or verified."""


# ---------------------------------------------------------------------------
# Numbers and formatting
# ---------------------------------------------------------------------------

def to_decimal(token: Any) -> Optional[Decimal]:
    """Return a finite Decimal for a strictly numeric token, else None."""
    if isinstance(token, bool):
        return None
    if isinstance(token, Decimal):
        return token if token.is_finite() else None
    if isinstance(token, int):
        return Decimal(token)
    if isinstance(token, float):
        text = repr(token)
    elif isinstance(token, str):
        text = token.strip().replace("\u2212", "-")
    else:
        return None
    if not _NUMERIC_TOKEN.match(text):
        return None
    try:
        value = Decimal(text)
    except InvalidOperation:
        return None
    return value if value.is_finite() else None


def _quantize(value: Decimal, places: int) -> Decimal:
    result = value.quantize(Decimal(1).scaleb(-places), rounding=ROUND_HALF_UP)
    return abs(result) if result == 0 else result


def valid_format(fmt: Optional[str]) -> bool:
    if fmt in (None, "", "raw", "d", ",d", "apa_p"):
        return True
    return bool(_FORMAT_RE.match(str(fmt)))


def render_token(token: str, fmt: Optional[str]) -> str:
    """Render one verified source token under a restricted format grammar.

    Formats: ``raw`` (exact source token, the default), ``d`` / ``,d``
    (integers), ``.Nf`` / ``,.Nf`` (fixed decimals, half-up), ``.N%`` (value
    times 100 with a percent sign), a trailing ``~`` to drop the leading zero
    (APA style for r or p), and ``apa_p`` (``p = .023`` or ``p < .001``).
    """
    clean = token.strip()
    if fmt in (None, "", "raw"):
        return clean
    value = to_decimal(clean)
    if value is None:
        raise DatapointError(
            "A numeric format was requested for a non-numeric value.",
            code="DATAPOINT_FORMAT_NOT_NUMERIC",
            details={"token": clean[:80], "format": fmt},
            repairs=[
                "Use the default raw format for text values.",
                "Point the locator at the numeric cell or capture group.",
                "Register the text as a separate datapoint with kind 'text'.",
            ],
        )
    if fmt == "apa_p":
        if value < Decimal("0.001"):
            return "p < .001"
        rounded = _quantize(value, 3)
        if rounded >= 1:
            return "p > .999"
        return "p = " + format(rounded, "f").replace("0.", ".", 1)
    if fmt in ("d", ",d"):
        if value != value.to_integral_value():
            raise DatapointError(
                "An integer format was requested for a non-integer value.",
                code="DATAPOINT_FORMAT_NOT_INTEGER",
                details={"token": clean[:80], "format": fmt},
                repairs=[
                    "Use a fixed-decimal format such as .2f.",
                    "Point the locator at the integer count instead of a derived value.",
                    "Check whether the artifact stores the value with unexpected decimals.",
                ],
            )
        return format(int(value), fmt)
    match = _FORMAT_RE.match(str(fmt))
    if not match:
        raise DatapointError(
            "Unknown datapoint format.",
            code="DATAPOINT_FORMAT_INVALID",
            details={"format": fmt},
            repairs=[
                "Use raw, d, ,d, .Nf, ,.Nf, .N%, an optional trailing ~, or apa_p.",
                "Omit format to render the exact source token.",
                "See docs/PAPER_BUILDER.md for the format grammar.",
            ],
        )
    places = int(match.group("places"))
    scaled = value * 100 if match.group("type") == "%" else value
    rounded = _quantize(scaled, places)
    text = format(rounded, ",f" if match.group("comma") else "f")
    if match.group("nolead"):
        text = re.sub(r"^(-?)0\.", r"\1.", text)
    if match.group("type") == "%":
        text += "%"
    return text


def decimals_in_display(display: str) -> int:
    found = re.search(r"\.(\d+)", display)
    return len(found.group(1)) if found else 0


# ---------------------------------------------------------------------------
# Artifact access and locators
# ---------------------------------------------------------------------------

def _artifact_bytes(root: Path, relative: str) -> Tuple[Path, bytes]:
    try:
        safe = safe_relative_path(relative)
        target = guard_path(root, root / safe, must_exist=True)
    except Refusal as exc:
        raise DatapointError(
            "The datapoint artifact is missing or outside the project boundary.",
            code="DATAPOINT_ARTIFACT_MISSING",
            details={"artifact_path": relative, "reason": str(exc)},
            repairs=[
                "Restore the exact artifact at its recorded project-relative path.",
                "Re-run the recorded analysis so it regenerates the artifact, then refresh the datapoint.",
                "Remove the datapoint and every {{dp:ID}} marker that uses it.",
            ],
        ) from exc
    if not target.is_file() or is_reparse_or_link(target):
        raise DatapointError(
            "The datapoint artifact must be one regular project-local file.",
            code="DATAPOINT_ARTIFACT_MISSING",
            details={"artifact_path": relative},
            repairs=[
                "Replace links or directories with the exact regular file.",
                "Copy the artifact bytes into artifacts/ and register that copy.",
                "Remove the datapoint until a stable file exists.",
            ],
        )
    if target.stat().st_size > MAX_ARTIFACT_BYTES:
        raise DatapointError(
            "The datapoint artifact exceeds the bounded extraction ceiling.",
            code="DATAPOINT_ARTIFACT_TOO_LARGE",
            details={"artifact_path": relative, "maximum_bytes": MAX_ARTIFACT_BYTES},
            repairs=[
                "Write a small summary artifact (CSV or JSON) from the analysis and register that.",
                "Split the large output into per-result files.",
                "Bind the large file as evidence and register only summary values as datapoints.",
            ],
        )
    return target, target.read_bytes()


def _decode(data: bytes, relative: str) -> str:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise DatapointError(
            "Datapoint artifacts must be strict UTF-8 text.",
            code="DATAPOINT_ARTIFACT_NOT_UTF8",
            details={"artifact_path": relative},
            repairs=[
                "Export the result table as UTF-8 CSV or JSON.",
                "Keep binary outputs as evidence and write a UTF-8 summary for datapoints.",
                "Do not re-encode silently; regenerate the file from the analysis.",
            ],
        ) from exc
    return text[1:] if text.startswith("\ufeff") else text


def _locator_failure(message: str, relative: str, locator: Mapping[str, Any], **extra: Any) -> DatapointError:
    return DatapointError(
        message,
        code="DATAPOINT_LOCATOR_FAILED",
        details={"artifact_path": relative, "locator": dict(locator), **extra},
        repairs=[
            "Open the artifact and point the locator at exactly one cell, JSON value, or match.",
            "If the analysis output changed shape, update the locator and refresh the datapoint deliberately.",
            "Make the analysis write a stable, keyed summary table so locators stay unambiguous.",
        ],
    )


def _extract_csv(text: str, relative: str, locator: Mapping[str, Any]) -> str:
    delimiter = locator.get("delimiter") or ("\t" if relative.lower().endswith(".tsv") else ",")
    if delimiter not in (",", "\t", ";", "|"):
        raise _locator_failure("Unsupported CSV delimiter.", relative, locator)
    try:
        rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, strict=True))
    except csv.Error as exc:
        raise _locator_failure("The CSV artifact could not be parsed strictly: {0}".format(exc), relative, locator) from exc
    if not rows:
        raise _locator_failure("The CSV artifact has no header row.", relative, locator)
    header = rows[0]
    column = locator.get("column")
    if not isinstance(column, str) or header.count(column) != 1:
        raise _locator_failure(
            "The locator column must name exactly one header cell.", relative, locator,
            matches=header.count(column) if isinstance(column, str) else 0,
        )
    index = header.index(column)
    body = [row for row in rows[1:] if row]
    if "row_index" in locator:
        position = locator.get("row_index")
        if not isinstance(position, int) or isinstance(position, bool) or not 0 <= position < len(body):
            raise _locator_failure("row_index is outside the data rows.", relative, locator, data_rows=len(body))
        selected = [body[position]]
    else:
        criteria = locator.get("row")
        if not isinstance(criteria, Mapping) or not criteria:
            raise _locator_failure("A CSV locator needs row (column/value pairs) or row_index.", relative, locator)
        positions = {}
        for key in criteria:
            if not isinstance(key, str) or header.count(key) != 1:
                raise _locator_failure("Every row-selection column must name exactly one header cell.", relative, locator)
            positions[key] = header.index(key)
        selected = [
            row for row in body
            if all(len(row) > positions[key] and row[positions[key]] == str(value) for key, value in criteria.items())
        ]
    if len(selected) != 1:
        raise _locator_failure("The row selection matched {0} rows; exactly one is required.".format(len(selected)),
                               relative, locator, matched_rows=len(selected))
    row = selected[0]
    if len(row) <= index:
        raise _locator_failure("The selected row has no cell in the locator column.", relative, locator)
    return row[index]


def _reject_duplicates(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    result: Dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key: {0}".format(key))
        result[key] = value
    return result


def _reject_constant(name: str) -> Any:
    raise ValueError("non-finite JSON constant: {0}".format(name))


def _extract_json(text: str, relative: str, locator: Mapping[str, Any]) -> str:
    pointer = locator.get("pointer")
    if not isinstance(pointer, str) or (pointer and not pointer.startswith("/")):
        raise _locator_failure("A JSON locator needs an RFC 6901 pointer such as /results/mean.", relative, locator)
    try:
        document = json.loads(
            text,
            parse_float=Decimal,
            object_pairs_hook=_reject_duplicates,
            parse_constant=_reject_constant,
        )
    except ValueError as exc:
        raise _locator_failure("The JSON artifact could not be parsed strictly: {0}".format(exc), relative, locator) from exc
    current: Any = document
    for raw in pointer.split("/")[1:] if pointer else []:
        part = raw.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict) and part in current:
            current = current[part]
        elif isinstance(current, list) and re.fullmatch(r"0|[1-9]\d*", part) and int(part) < len(current):
            current = current[int(part)]
        else:
            raise _locator_failure("The JSON Pointer does not resolve.", relative, locator, missing_segment=part)
    if isinstance(current, bool) or current is None or isinstance(current, (dict, list)):
        raise _locator_failure("The JSON Pointer must resolve to a number or string.", relative, locator)
    return str(current)


def _extract_text(text: str, relative: str, locator: Mapping[str, Any]) -> str:
    pattern = locator.get("pattern")
    if not isinstance(pattern, str) or not pattern or len(pattern) > MAX_PATTERN_LENGTH:
        raise _locator_failure("A text locator needs a pattern of at most {0} characters.".format(MAX_PATTERN_LENGTH), relative, locator)
    try:
        compiled = re.compile(pattern)
    except re.error as exc:
        raise _locator_failure("The text pattern is not a valid regular expression: {0}".format(exc), relative, locator) from exc
    if compiled.groups != 1:
        raise _locator_failure("The text pattern must contain exactly one capture group.", relative, locator)
    scope = text
    line = locator.get("line")
    if line is not None:
        lines = text.splitlines()
        if not isinstance(line, int) or isinstance(line, bool) or not 1 <= line <= len(lines):
            raise _locator_failure("The text locator line is outside the artifact.", relative, locator, line_count=len(lines))
        scope = lines[line - 1]
    matches = list(compiled.finditer(scope))
    if len(matches) != 1:
        raise _locator_failure("The text pattern matched {0} times; exactly one match is required.".format(len(matches)),
                               relative, locator, matches=len(matches))
    value = matches[0].group(1)
    if value is None:
        raise _locator_failure("The capture group did not participate in the match.", relative, locator)
    return value


def extract_token(root: Union[str, Path], datapoint: Mapping[str, Any]) -> Dict[str, Any]:
    """Re-read the artifact and return the exact source token and its digest."""
    paths = paths_for(root)
    relative = str(datapoint.get("artifact_path", "")).strip()
    locator = datapoint.get("locator")
    if not isinstance(locator, Mapping) or locator.get("type") not in LOCATOR_TYPES:
        raise DatapointError(
            "The datapoint locator type is missing or unknown.",
            code="DATAPOINT_LOCATOR_INVALID",
            details={"datapoint": datapoint.get("id"), "allowed": list(LOCATOR_TYPES)},
            repairs=[
                "Use csv_cell (column plus row or row_index), json_pointer (pointer), or text_regex (pattern).",
                "Register the datapoint with `uriel paper dp-add` so the locator is validated as it is written.",
                "See docs/PAPER_BUILDER.md for locator examples.",
            ],
        )
    target, data = _artifact_bytes(paths.root, relative)
    text = _decode(data, relative)
    kind = locator["type"]
    if kind == "csv_cell":
        token = _extract_csv(text, relative, locator)
    elif kind == "json_pointer":
        token = _extract_json(text, relative, locator)
    else:
        token = _extract_text(text, relative, locator)
    if "\n" in token or "\r" in token:
        raise _locator_failure("The extracted value spans lines; datapoints must be single-line values.", relative, locator)
    return {
        "artifact_path": target.relative_to(paths.root).as_posix(),
        "sha256": sha256_bytes(data),
        "token": token.strip(),
    }


# ---------------------------------------------------------------------------
# Registry I/O and validation
# ---------------------------------------------------------------------------

def empty_registry() -> Dict[str, Any]:
    return {"schema": DATAPOINTS_SCHEMA, "schema_version": 1, "datapoints": [], "relations": []}


def registry_path(root: Union[str, Path]) -> Path:
    paths = paths_for(root)
    return guard_path(paths.root, paths.root / REGISTRY_RELATIVE_PATH)


def load_registry(root: Union[str, Path]) -> Dict[str, Any]:
    """Load the registry; a missing file is an empty registry."""
    path = registry_path(root)
    if not path.exists():
        return empty_registry()
    if is_reparse_or_link(path) or not path.is_file():
        raise DatapointError("The datapoint registry must be a regular file.", code="DATAPOINT_REGISTRY_INVALID")
    try:
        value = json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_reject_duplicates)
    except (ValueError, UnicodeDecodeError) as exc:
        raise DatapointError(
            "The datapoint registry is not valid strict JSON: {0}".format(exc),
            code="DATAPOINT_REGISTRY_INVALID",
            repairs=[
                "Fix the JSON syntax or duplicate key in paper/datapoints.json.",
                "Restore the registry from version control.",
                "Re-register datapoints with `uriel paper dp-add`.",
            ],
        ) from exc
    if not isinstance(value, dict):
        raise DatapointError("The datapoint registry must be a JSON object.", code="DATAPOINT_REGISTRY_INVALID")
    return value


def _issue(code: str, level: str, subject: str, message: str, **detail: Any) -> Dict[str, Any]:
    return {"code": code, "level": level, "subject": subject, "message": message, "detail": detail}


def validate_registry(registry: Mapping[str, Any], project: Optional[Mapping[str, Any]] = None) -> List[Dict[str, Any]]:
    """Structural validation; returns located issues rather than raising."""
    issues: List[Dict[str, Any]] = []
    if registry.get("schema") != DATAPOINTS_SCHEMA:
        issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", "paper/datapoints.json",
                             "The registry schema must be {0}.".format(DATAPOINTS_SCHEMA)))
    rows = registry.get("datapoints")
    if not isinstance(rows, list):
        issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", "paper/datapoints.json", "datapoints must be an array."))
        return issues
    if len(rows) > MAX_DATAPOINTS:
        issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", "paper/datapoints.json",
                             "The registry exceeds {0} datapoints.".format(MAX_DATAPOINTS)))
        return issues
    claims = set()
    evidence = set()
    if project is not None:
        claims = {str(row.get("id")) for row in project.get("claims", []) if isinstance(row, Mapping) and row.get("id")}
        evidence = {str(row.get("id")) for row in project.get("evidence", []) if isinstance(row, Mapping) and row.get("id")}
    seen: Dict[str, int] = {}
    for index, row in enumerate(rows):
        subject = "datapoints[{0}]".format(index)
        if not isinstance(row, Mapping):
            issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", subject, "Each datapoint must be an object."))
            continue
        identifier = row.get("id")
        if not isinstance(identifier, str) or not _ID_RE.match(identifier):
            issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", subject,
                                 "Datapoint id must start with a letter and use letters, digits, '.', '_' or '-'."))
            continue
        subject = identifier
        seen[identifier] = seen.get(identifier, 0) + 1
        artifact = row.get("artifact_path")
        if not isinstance(artifact, str) or not artifact.strip():
            issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", subject, "artifact_path is required."))
        elif artifact.replace("\\", "/").lstrip("./").startswith("paper/"):
            issues.append(_issue("DATAPOINT_ARTIFACT_CIRCULAR", "grave", subject,
                                 "A datapoint cannot be sourced from the manuscript directory itself."))
        if not isinstance(row.get("sha256"), str) or not _HEX64.match(str(row.get("sha256"))):
            issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", subject, "sha256 must be a lowercase 64-hex digest."))
        locator = row.get("locator")
        if not isinstance(locator, Mapping) or locator.get("type") not in LOCATOR_TYPES:
            issues.append(_issue("DATAPOINT_LOCATOR_INVALID", "grave", subject,
                                 "locator.type must be one of {0}.".format(", ".join(LOCATOR_TYPES))))
        if "value" not in row or isinstance(row.get("value"), (dict, list, bool)) or row.get("value") is None:
            issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", subject, "value must be the declared number or string."))
        if not valid_format(row.get("format")):
            issues.append(_issue("DATAPOINT_FORMAT_INVALID", "grave", subject, "format is not in the supported grammar."))
        kind = row.get("kind", "other")
        if kind not in KINDS:
            issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", subject,
                                 "kind must be one of {0}.".format(", ".join(KINDS))))
        for bound in ("min", "max"):
            if row.get(bound) is not None and (isinstance(row.get(bound), str) or to_decimal(row.get(bound)) is None):
                issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", subject, "{0} must be a number.".format(bound)))
        tolerance = row.get("tolerance", 0)
        if to_decimal(tolerance) is None or to_decimal(tolerance) < 0:
            issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", subject, "tolerance must be a non-negative number."))
        if not isinstance(row.get("description"), str) or len(str(row.get("description", "")).strip()) < 8:
            issues.append(_issue("DATAPOINT_DESCRIPTION_MISSING", "submission", subject,
                                 "Describe what the value measures (population, quantity, unit) in at least 8 characters."))
        linked_claims = row.get("claim_ids", [])
        if not isinstance(linked_claims, list) or any(not isinstance(item, str) for item in linked_claims):
            issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", subject, "claim_ids must be an array of claim IDs."))
        elif project is not None:
            for claim_id in linked_claims:
                if claim_id not in claims:
                    issues.append(_issue("DATAPOINT_UNKNOWN_CLAIM", "grave", subject,
                                         "The datapoint links to claim {0}, which is not in uriel.project.json.".format(claim_id)))
        evidence_id = row.get("evidence_id")
        if evidence_id not in (None, "") and project is not None and str(evidence_id) not in evidence:
            issues.append(_issue("DATAPOINT_UNKNOWN_EVIDENCE", "grave", subject,
                                 "The datapoint links to evidence {0}, which is not registered.".format(evidence_id)))
        grim = row.get("grim")
        if grim is not None:
            if kind != "mean" or not isinstance(grim, Mapping):
                issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", subject,
                                     "grim applies only to kind 'mean' and must be an object with n and optional items."))
    for identifier, count in sorted(seen.items()):
        if count > 1:
            issues.append(_issue("DATAPOINT_ID_DUPLICATE", "grave", identifier,
                                 "The datapoint id is registered {0} times.".format(count)))
    relations = registry.get("relations", [])
    if not isinstance(relations, list):
        issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", "relations", "relations must be an array."))
    else:
        for index, relation in enumerate(relations):
            if not isinstance(relation, Mapping) or relation.get("type") not in RELATION_TYPES:
                issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", "relations[{0}]".format(index),
                                     "relation.type must be one of {0}.".format(", ".join(RELATION_TYPES))))
    return issues


# ---------------------------------------------------------------------------
# Provenance through recorded runs
# ---------------------------------------------------------------------------

def _run_provenance(root: Path) -> Dict[Tuple[str, str], Dict[str, Any]]:
    """Map (path, sha256) to the newest verified PASS receipt that left those bytes."""
    paths = paths_for(root)
    found: Dict[Tuple[str, str], Dict[str, Any]] = {}
    manifest_cache: Dict[str, Dict[Tuple[str, str], bool]] = {}

    def records(digest: str) -> Dict[Tuple[str, str], bool]:
        if digest not in manifest_cache:
            try:
                manifest = read_json(guard_path(paths.root, paths.manifests / "{0}.json".format(digest), must_exist=True))
                manifest_cache[digest] = {
                    (str(row.get("relative_path")), str(row.get("sha256"))): True
                    for row in manifest.get("records", []) if isinstance(row, Mapping)
                }
            except Refusal:
                manifest_cache[digest] = {}
        return manifest_cache[digest]

    receipts = sorted(latest_receipts(paths.root), key=lambda row: str(row.get("finished_at_utc", "")))
    for receipt in receipts:
        if receipt.get("status") != "PASS" or not verify_receipt(paths.root, receipt).get("verified"):
            continue
        before = records(str(receipt.get("pre_manifest_sha256", "")))
        after = records(str(receipt.get("post_manifest_sha256", "")))
        for key in after:
            relation = "present_before_and_after" if key in before else "written_by_run"
            if key in found and found[key]["relation"] == "written_by_run" and relation != "written_by_run":
                continue  # keep the run that actually produced these bytes
            found[key] = {"receipt_id": receipt.get("receipt_id"), "relation": relation}
    return found


# ---------------------------------------------------------------------------
# Verification
# ---------------------------------------------------------------------------

def _within(value: Decimal, expected: Decimal, tolerance: Decimal) -> bool:
    return abs(value - expected) <= tolerance


def verify_registry(
    root: Union[str, Path],
    *,
    registry: Optional[Mapping[str, Any]] = None,
    project: Optional[Mapping[str, Any]] = None,
    manifest_paths: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    """Re-extract and check every datapoint; never writes."""
    paths = paths_for(root)
    registry = load_registry(paths.root) if registry is None else registry
    project = load_project(paths.root) if project is None else project
    issues = validate_registry(registry, project)
    structurally_broken = {row["subject"] for row in issues if row["code"] in STRUCTURAL_CODES}
    provenance = _run_provenance(paths.root)
    results: Dict[str, Dict[str, Any]] = {}
    rows = registry.get("datapoints") if isinstance(registry.get("datapoints"), list) else []
    for row in rows:
        if not isinstance(row, Mapping) or not isinstance(row.get("id"), str):
            continue
        identifier = row["id"]
        if identifier in results or identifier in structurally_broken:
            continue
        entry: Dict[str, Any] = {"id": identifier, "status": "UNVERIFIED", "token": None, "display": None}
        results[identifier] = entry
        relative = str(row.get("artifact_path", ""))
        try:
            extracted = extract_token(paths.root, row)
        except DatapointError as exc:
            issues.append(_issue(exc.code, "grave", identifier, str(exc), **exc.details))
            entry["status"] = "FAILED"
            continue
        if extracted["sha256"] != row.get("sha256"):
            issues.append(_issue(
                "DATAPOINT_ARTIFACT_STALE", "grave", identifier,
                "The artifact bytes changed after the datapoint was registered.",
                artifact_path=relative, recorded_sha256=row.get("sha256"), current_sha256=extracted["sha256"],
            ))
            entry["status"] = "STALE"
            continue
        if manifest_paths is not None and manifest_paths.get(extracted["artifact_path"]) != extracted["sha256"]:
            issues.append(_issue(
                "DATAPOINT_ARTIFACT_NOT_MANIFESTED", "grave", identifier,
                "The artifact is not part of the project's audited source inventory (ignored directory or state area).",
                artifact_path=relative,
            ))
            entry["status"] = "FAILED"
            continue
        token = extracted["token"]
        declared = row.get("value")
        declared_number = to_decimal(declared)
        observed_number = to_decimal(token)
        tolerance = to_decimal(row.get("tolerance", 0)) or Decimal(0)
        if declared_number is not None and observed_number is not None:
            matches = _within(observed_number, declared_number, tolerance)
        elif isinstance(declared, str):
            matches = declared.strip() == token
        else:
            matches = False
        if not matches:
            issues.append(_issue(
                "DATAPOINT_VALUE_MISMATCH", "grave", identifier,
                "The value at the locator does not equal the declared value.",
                declared=str(declared), extracted=token, tolerance=str(tolerance),
            ))
            entry["status"] = "MISMATCH"
            entry["token"] = token
            continue
        try:
            display = render_token(token, row.get("format"))
        except DatapointError as exc:
            issues.append(_issue(exc.code, "grave", identifier, str(exc), **exc.details))
            entry["status"] = "FAILED"
            continue
        entry.update({"status": "VERIFIED", "token": token, "display": display, "sha256": extracted["sha256"]})
        kind = row.get("kind", "other")
        number = observed_number
        if kind in ("count",) and number is not None and number != number.to_integral_value():
            issues.append(_issue("DATAPOINT_SANITY_VIOLATION", "grave", identifier,
                                 "A count must be a whole number.", value=token))
        if kind != "text" and kind != "other" and number is None:
            issues.append(_issue("DATAPOINT_SANITY_VIOLATION", "grave", identifier,
                                 "A datapoint of kind '{0}' must be numeric.".format(kind), value=token))
        bounds = list(_KIND_BOUNDS.get(str(kind), (None, None)))
        if row.get("min") is not None:
            bounds[0] = to_decimal(row.get("min"))
        if row.get("max") is not None:
            bounds[1] = to_decimal(row.get("max"))
        if number is not None:
            low, high = bounds
            if (low is not None and number < low) or (high is not None and number > high):
                issues.append(_issue(
                    "DATAPOINT_SANITY_VIOLATION", "grave", identifier,
                    "The value is outside the possible range for its declared kind or bounds.",
                    value=token, kind=kind, minimum=str(low) if low is not None else None,
                    maximum=str(high) if high is not None else None,
                ))
            if number > 0 and re.fullmatch(r"[^1-9]*", display) and row.get("format") not in (None, "", "raw", "apa_p"):
                issues.append(_issue(
                    "DATAPOINT_ROUNDED_TO_ZERO", "submission", identifier,
                    "A non-zero value renders as zero at the chosen precision.",
                    value=token, display=display,
                ))
        grim = row.get("grim")
        if isinstance(grim, Mapping) and kind == "mean" and number is not None:
            n_value = grim.get("n")
            if isinstance(n_value, str) and n_value.startswith("dp:"):
                n_value = None  # resolved after all datapoints are verified
                entry["grim_n_ref"] = grim.get("n")[3:]
            items = grim.get("items", 1)
            if n_value is not None:
                _apply_grim(issues, identifier, token, n_value, items)
        relative_path = extracted["artifact_path"]
        origin = provenance.get((relative_path, extracted["sha256"]))
        entry["provenance"] = origin["relation"] if origin else "no_recorded_run"
        if origin:
            entry["receipt_id"] = origin["receipt_id"]
        declared_provenance = str(row.get("provenance", "")).strip()
        if (
            not origin
            and relative_path.startswith("artifacts/")
            and not (declared_provenance.lower().startswith("external:") and len(declared_provenance) >= 25)
        ):
            issues.append(_issue(
                "DATAPOINT_NOT_FROM_RECORDED_RUN", "submission", identifier,
                "The generated artifact behind this number was not left by any verified passing `uriel run` receipt.",
                artifact_path=relative_path,
            ))

    for identifier, entry in results.items():
        reference = entry.pop("grim_n_ref", None)
        if not reference:
            continue
        source = results.get(reference)
        row = next((item for item in rows if isinstance(item, Mapping) and item.get("id") == identifier), {})
        if not source or source.get("status") != "VERIFIED":
            issues.append(_issue("DATAPOINT_RELATION_UNKNOWN_ID", "grave", identifier,
                                 "The GRIM sample size refers to an unverified or unknown datapoint.", reference=reference))
            continue
        _apply_grim(issues, identifier, str(entry.get("token")), source.get("token"), (row.get("grim") or {}).get("items", 1))

    relation_results = _check_relations(registry.get("relations", []), results, rows, issues)
    issues.sort(key=lambda row: (row["subject"], row["code"]))
    verified = sum(1 for entry in results.values() if entry["status"] == "VERIFIED")
    return {
        "registry_path": REGISTRY_RELATIVE_PATH,
        "datapoint_count": len(results),
        "verified_count": verified,
        "datapoints": [results[key] for key in sorted(results)],
        "relations": relation_results,
        "issues": issues,
        "grave_count": sum(1 for row in issues if row["level"] == "grave"),
        "boundaries": {
            "analysis_correctness_decided": False,
            "writes": 0,
        },
    }


def _apply_grim(issues: List[Dict[str, Any]], identifier: str, token: str, n_value: Any, items: Any) -> None:
    n_number = to_decimal(n_value)
    items_number = to_decimal(items)
    if (
        n_number is None or items_number is None or n_number <= 0 or items_number <= 0
        or n_number != n_number.to_integral_value() or items_number != items_number.to_integral_value()
    ):
        issues.append(_issue("DATAPOINT_REGISTRY_INVALID", "grave", identifier,
                             "GRIM needs a positive whole-number n and items."))
        return
    if not grim_consistent(token, int(n_number), int(items_number)):
        issues.append(_issue(
            "DATAPOINT_GRIM_INCONSISTENT", "grave", identifier,
            "No set of whole-number responses from this sample size can produce this mean at the reported precision.",
            mean=token, n=int(n_number), items=int(items_number),
        ))


def _check_relations(
    relations: Any,
    results: Mapping[str, Mapping[str, Any]],
    rows: Sequence[Any],
    issues: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    output: List[Dict[str, Any]] = []
    if not isinstance(relations, list):
        return output
    displays = {key: str(value.get("display") or "") for key, value in results.items()}

    def number(identifier: Any) -> Optional[Decimal]:
        entry = results.get(str(identifier))
        if not entry or entry.get("status") != "VERIFIED":
            return None
        return to_decimal(entry.get("token"))

    for index, relation in enumerate(relations):
        if not isinstance(relation, Mapping) or relation.get("type") not in RELATION_TYPES:
            continue
        kind = relation["type"]
        subject = "relations[{0}]:{1}".format(index, kind)
        names: List[Any]
        if kind == "sum":
            names = list(relation.get("parts", [])) + [relation.get("total")]
        elif kind == "ratio":
            names = [relation.get("numerator"), relation.get("denominator"), relation.get("result")]
        elif kind == "ci":
            names = [relation.get("lower"), relation.get("estimate"), relation.get("upper")]
        elif kind == "le":
            names = [relation.get("left"), relation.get("right")]
        else:
            names = list(relation.get("ids", []))
        values = [number(name) for name in names]
        if len(names) < 2 or any(value is None for value in values):
            issues.append(_issue("DATAPOINT_RELATION_UNKNOWN_ID", "grave", subject,
                                 "Every datapoint named by a relation must exist, verify, and be numeric.",
                                 ids=[str(name) for name in names]))
            output.append({"index": index, "type": kind, "status": "UNRESOLVED"})
            continue
        numbers = [value for value in values if value is not None]
        tolerance = to_decimal(relation.get("tolerance", 0)) or Decimal(0)
        ok = True
        detail: Dict[str, Any] = {}
        if kind == "sum":
            total = sum(numbers[:-1], Decimal(0))
            ok = _within(total, numbers[-1], tolerance)
            detail = {"sum_of_parts": str(total), "total": str(numbers[-1])}
        elif kind == "ratio":
            numerator, denominator, result = numbers
            scale = to_decimal(relation.get("scale", 1)) or Decimal(1)
            if denominator == 0:
                ok = False
                detail = {"reason": "denominator is zero"}
            else:
                computed = numerator / denominator * scale
                if "tolerance" not in relation:
                    places = decimals_in_display(displays.get(str(names[2]), ""))
                    tolerance = Decimal("0.5").scaleb(-places) if places else Decimal("0.5")
                    if str(displays.get(str(names[2]), "")).endswith("%") and scale == 1:
                        tolerance = tolerance / 100
                ok = _within(computed, result, tolerance)
                detail = {"computed": str(computed.quantize(Decimal("1e-8"))), "reported": str(result), "tolerance": str(tolerance)}
        elif kind == "ci":
            lower, estimate, upper = numbers
            ok = lower <= estimate <= upper
            detail = {"lower": str(lower), "estimate": str(estimate), "upper": str(upper)}
        elif kind == "le":
            ok = numbers[0] <= numbers[1] + tolerance
            detail = {"left": str(numbers[0]), "right": str(numbers[1])}
        else:
            ok = all(_within(value, numbers[0], tolerance) for value in numbers[1:])
            detail = {"values": [str(value) for value in numbers]}
        output.append({"index": index, "type": kind, "status": "PASS" if ok else "FAIL", "detail": detail})
        if not ok:
            issues.append(_issue(
                "DATAPOINT_RELATION_VIOLATED", "grave", subject,
                "Registered values contradict the declared {0} relation.".format(kind),
                ids=[str(name) for name in names], **detail,
            ))
    return output


# ---------------------------------------------------------------------------
# Mutations (create / refresh) with ledger events
# ---------------------------------------------------------------------------

def _json_value(token: str, kind: str) -> Any:
    number = to_decimal(token)
    if number is None or kind == "text":
        return token
    if number == number.to_integral_value() and "." not in token and "e" not in token.lower():
        return int(number)
    return float(number)


def _write_registry(root: Path, registry: Mapping[str, Any]) -> Path:
    path = registry_path(root)
    if path.exists() and (is_reparse_or_link(path) or not path.is_file()):
        raise DatapointError("The datapoint registry must be a regular file.", code="DATAPOINT_REGISTRY_INVALID")
    atomic_write_json(path, dict(registry))
    return path


def add_datapoint(
    root: Union[str, Path],
    *,
    datapoint_id: str,
    artifact_path: str,
    locator: Mapping[str, Any],
    description: str,
    kind: str = "other",
    fmt: Optional[str] = None,
    unit: str = "",
    claim_ids: Sequence[str] = (),
    evidence_id: str = "",
    tolerance: Optional[float] = None,
    grim_n: Optional[str] = None,
    grim_items: int = 1,
    provenance: str = "",
) -> Dict[str, Any]:
    """Register one datapoint; the value is extracted by Uriel, never typed."""
    paths = paths_for(root)
    if not _ID_RE.match(datapoint_id):
        raise DatapointError(
            "Datapoint id must start with a letter and use letters, digits, '.', '_' or '-'.",
            code="DATAPOINT_ID_INVALID",
            details={"id": datapoint_id},
            repairs=[
                "Use a short descriptive id such as n_total or mean_rt_control.",
                "Avoid spaces and punctuation other than '.', '_' and '-'.",
                "Keep ids stable; manuscript markers refer to them.",
            ],
        )
    if kind not in KINDS:
        raise DatapointError("Unknown datapoint kind.", code="DATAPOINT_KIND_INVALID",
                             details={"kind": kind, "allowed": list(KINDS)})
    if not valid_format(fmt):
        render_token("0", fmt)  # raises the descriptive format refusal
    registry = load_registry(paths.root)
    if registry.get("schema") != DATAPOINTS_SCHEMA or not isinstance(registry.get("datapoints"), list):
        raise DatapointError("The existing datapoint registry is invalid; repair it before adding.",
                             code="DATAPOINT_REGISTRY_INVALID")
    if any(isinstance(row, Mapping) and row.get("id") == datapoint_id for row in registry["datapoints"]):
        raise DatapointError(
            "That datapoint id already exists; Uriel will not silently replace a reported number.",
            code="DATAPOINT_ID_EXISTS",
            details={"id": datapoint_id},
            repairs=[
                "Use `uriel paper dp-refresh --id ID` when the same quantity was legitimately recomputed.",
                "Choose a new id for a different quantity.",
                "Remove the old entry deliberately in paper/datapoints.json if it was registered in error.",
            ],
        )
    candidate: Dict[str, Any] = {
        "id": datapoint_id,
        "description": description.strip(),
        "artifact_path": safe_relative_path(artifact_path).as_posix(),
        "locator": dict(locator),
        "kind": kind,
    }
    if candidate["artifact_path"].startswith("paper/"):
        raise DatapointError(
            "A datapoint cannot be sourced from the manuscript directory.",
            code="DATAPOINT_ARTIFACT_CIRCULAR",
            repairs=[
                "Point at the analysis output under artifacts/ or the primary record under sources/.",
                "Write the value from the analysis script into a summary file and register that.",
                "Keep manuscript files as consumers of datapoints, never as their source.",
            ],
        )
    extracted = extract_token(paths.root, candidate)
    candidate["sha256"] = extracted["sha256"]
    candidate["value"] = _json_value(extracted["token"], kind)
    candidate["source_token"] = extracted["token"]
    if fmt:
        candidate["format"] = fmt
        render_token(extracted["token"], fmt)
    if unit.strip():
        candidate["unit"] = unit.strip()
    if claim_ids:
        candidate["claim_ids"] = list(dict.fromkeys(str(item) for item in claim_ids))
    if evidence_id:
        candidate["evidence_id"] = evidence_id
    if tolerance is not None:
        candidate["tolerance"] = tolerance
    if grim_n:
        candidate["grim"] = {"n": int(grim_n) if grim_n.isdigit() else grim_n, "items": int(grim_items)}
    if provenance.strip():
        candidate["provenance"] = provenance.strip()
    candidate["registered_at_utc"] = utc_now()
    project = load_project(paths.root)
    structural = [row for row in validate_registry(
        {"schema": DATAPOINTS_SCHEMA, "datapoints": [candidate], "relations": []}, project
    ) if row["level"] == "grave"]
    if structural:
        raise DatapointError(
            "The datapoint is not valid: {0}".format(structural[0]["message"]),
            code=structural[0]["code"],
            details={"issues": structural},
            repairs=[
                "Correct the named field and run the command again.",
                "Register the claim or evidence first if the link is intended.",
                "Omit optional links until the referenced records exist.",
            ],
        )
    registry["datapoints"].append(candidate)
    registry.setdefault("relations", [])
    _write_registry(paths.root, registry)
    append_ledger(paths.root, "paper.datapoint_registered", {
        "datapoint_id": datapoint_id,
        "artifact_path": candidate["artifact_path"],
        "artifact_sha256": candidate["sha256"],
        "source_token": candidate["source_token"],
    })
    return {"datapoint": candidate, "registry_path": REGISTRY_RELATIVE_PATH}


def refresh_datapoint(root: Union[str, Path], datapoint_id: str, *, confirm_change: bool = False) -> Dict[str, Any]:
    """Re-bind one datapoint to current bytes; a changed value needs confirmation."""
    paths = paths_for(root)
    registry = load_registry(paths.root)
    rows = registry.get("datapoints") if isinstance(registry.get("datapoints"), list) else []
    target: Optional[MutableMapping[str, Any]] = None
    for row in rows:
        if isinstance(row, MutableMapping) and row.get("id") == datapoint_id:
            target = row
            break
    if target is None:
        raise DatapointError(
            "No datapoint has that id.",
            code="DATAPOINT_UNKNOWN",
            details={"id": datapoint_id},
            repairs=[
                "List registered ids with `uriel paper check`.",
                "Register the value with `uriel paper dp-add`.",
                "Check the spelling of the id used in the {{dp:ID}} marker.",
            ],
        )
    extracted = extract_token(paths.root, target)
    old_token = str(target.get("source_token", target.get("value")))
    old_number, new_number = to_decimal(target.get("value")), to_decimal(extracted["token"])
    value_changed = (
        (old_number != new_number) if (old_number is not None and new_number is not None)
        else str(target.get("value")).strip() != extracted["token"]
    )
    if value_changed and not confirm_change:
        raise DatapointError(
            "The reported value would change from {0} to {1}; Uriel will not change a reported number silently.".format(
                old_token, extracted["token"]),
            code="DATAPOINT_VALUE_CHANGED",
            details={"id": datapoint_id, "old": old_token, "new": extracted["token"]},
            repairs=[
                "Confirm the analysis change is intended, then rerun with --confirm-change.",
                "Restore the previous artifact if the change was accidental.",
                "Re-check every sentence that uses this datapoint; the conclusion may need to change too.",
            ],
        )
    previous_sha = target.get("sha256")
    target["sha256"] = extracted["sha256"]
    target["value"] = _json_value(extracted["token"], str(target.get("kind", "other")))
    target["source_token"] = extracted["token"]
    target["refreshed_at_utc"] = utc_now()
    _write_registry(paths.root, registry)
    append_ledger(paths.root, "paper.datapoint_refreshed", {
        "datapoint_id": datapoint_id,
        "previous_artifact_sha256": previous_sha,
        "artifact_sha256": extracted["sha256"],
        "previous_token": old_token,
        "source_token": extracted["token"],
        "value_changed": bool(value_changed),
    })
    return {
        "datapoint": dict(target),
        "value_changed": bool(value_changed),
        "previous_token": old_token,
        "registry_path": REGISTRY_RELATIVE_PATH,
    }


def locator_from_arguments(
    *,
    csv_column: Optional[str] = None,
    csv_row: Sequence[str] = (),
    csv_row_index: Optional[int] = None,
    json_pointer: Optional[str] = None,
    text_regex: Optional[str] = None,
    text_line: Optional[int] = None,
) -> Dict[str, Any]:
    """Build exactly one locator from CLI-style arguments."""
    chosen = [name for name, present in (
        ("csv", csv_column is not None),
        ("json", json_pointer is not None),
        ("text", text_regex is not None),
    ) if present]
    if len(chosen) != 1:
        raise DatapointError(
            "Choose exactly one locator: --csv-column, --json-pointer, or --text-regex.",
            code="DATAPOINT_LOCATOR_INVALID",
            repairs=[
                "For a table cell use --csv-column COL with --csv-row KEY=VALUE (repeatable) or --csv-row-index N.",
                "For JSON use --json-pointer /path/to/value.",
                "For text use --text-regex 'pattern with (one) group' and optionally --text-line N.",
            ],
        )
    if chosen[0] == "csv":
        locator: Dict[str, Any] = {"type": "csv_cell", "column": csv_column}
        if csv_row_index is not None and csv_row:
            raise DatapointError("Use --csv-row or --csv-row-index, not both.", code="DATAPOINT_LOCATOR_INVALID")
        if csv_row_index is not None:
            locator["row_index"] = int(csv_row_index)
        else:
            criteria: Dict[str, str] = {}
            for item in csv_row:
                if "=" not in item:
                    raise DatapointError("--csv-row must be KEY=VALUE.", code="DATAPOINT_LOCATOR_INVALID",
                                         details={"value": item})
                key, value = item.split("=", 1)
                criteria[key] = value
            if not criteria:
                raise DatapointError("A CSV locator needs --csv-row KEY=VALUE or --csv-row-index N.",
                                     code="DATAPOINT_LOCATOR_INVALID")
            locator["row"] = criteria
        return locator
    if chosen[0] == "json":
        return {"type": "json_pointer", "pointer": json_pointer}
    locator = {"type": "text_regex", "pattern": text_regex}
    if text_line is not None:
        locator["line"] = int(text_line)
    return locator


__all__ = [
    "DATAPOINTS_SCHEMA",
    "DatapointError",
    "KINDS",
    "LOCATOR_TYPES",
    "REGISTRY_RELATIVE_PATH",
    "RELATION_TYPES",
    "add_datapoint",
    "empty_registry",
    "extract_token",
    "load_registry",
    "locator_from_arguments",
    "refresh_datapoint",
    "render_token",
    "to_decimal",
    "valid_format",
    "validate_registry",
    "verify_registry",
]
