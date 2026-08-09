"""Deterministic Data Desk inspection, generations, and reconciliation.

This module reports structural and lexical observations only. It preserves raw
values, source order, duplicates, and conflicts; it performs no imputation,
scientific interpretation, hidden sorting, or Gate 0 decision.
"""
from __future__ import annotations

import csv
import datetime as _datetime
import hashlib
import json
import math
import os
import re
import shutil
import sqlite3
import time
import uuid
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .core import Refusal, canonical_json, guard_path, paths_for, sha256_bytes, sha256_text
from .data_contracts import (
    DATA_DELTA_ENTRY_SCHEMA,
    DATA_GENERATION_SCHEMA,
    DATA_PROFILE_SCHEMA,
    DATA_RECONCILIATION_SCHEMA,
    bind_data_record,
    validate_data_record,
)
from .data_ingress import (
    DATA_ROOT_RELATIVE,
    _ensure_directory,
    _load_json_record,
    _write_immutable_bytes,
    _write_immutable_record,
    verify_data_import,
)


DATA_PARSER_VERSION = "uriel.data_parser.v1"
_DISK_RESERVE_BYTES = 1024 * 1024
_COLUMN_ID_RE = re.compile(r"^col-[0-9a-f]{16}$")
_INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")
_NUMBER_RE = re.compile(r"^[+-]?(?:[0-9]+\.[0-9]*|[0-9]*\.[0-9]+|[0-9]+)(?:[eE][+-]?[0-9]+)?$")
_MISSING = object()
_MAX_JSON_NUMBER_CHARACTERS = 4096
_MAX_PARSER_RECORDS = 2_000_000
_MAX_PARSER_COLUMNS = 100_000
_MAX_PARSER_FIELD_BYTES = 16 * 1024 * 1024
_MAX_PARSER_NESTING_DEPTH = 256
_MAX_MANAGED_SOURCE_BYTES = 512 * 1024 * 1024
_MAX_JSON_DOCUMENT_BYTES = 256 * 1024 * 1024
_MAX_GENERATION_RECORDS = 2_000_000
_MAX_GENERATION_FILE_BYTES = 512 * 1024 * 1024
_MAX_GENERATION_RECORD_LINE_BYTES = 256 * 1024 * 1024
_MAX_DELTA_ENTRIES = 4_000_000
_MAX_DELTA_LEDGER_BYTES = 1024 * 1024 * 1024
_MAX_SQLITE_INDEX_BYTES = 2 * 1024 * 1024 * 1024
_MAX_RAW_ARTIFACTS_PER_GENERATION = 10_000
_MAX_IMPORT_RECEIPTS = 100_000
_MAX_IMPORT_RECEIPT_INDEX_BYTES = 256 * 1024 * 1024
_MAX_LINEAGE_GENERATIONS = 256
_MAX_LINEAGE_RECORD_WORK = 10_000_000
_MAX_LINEAGE_BYTE_WORK = 4 * 1024 * 1024 * 1024
MAX_AI_SURFACE_ROWS = 1_000
MAX_AI_SURFACE_BYTES = 1024 * 1024
MAX_AI_SURFACE_SOURCE_BYTES = 128 * 1024 * 1024
MAX_AI_SURFACE_SOURCE_RECORDS = 250_000
_FORMAT_DECISIONS = {
    "CSV": "DELIMITED_UTF8_COMMA_QUOTE_DOUBLEQUOTE_STRICT_HEADER_ROW_1",
    "TSV": "DELIMITED_UTF8_TAB_QUOTE_DOUBLEQUOTE_STRICT_HEADER_ROW_1",
    "JSON": "JSON_UTF8_OBJECT_OR_OBJECT_ARRAY_SORTED_COLUMNS_DUPLICATE_KEYS_REFUSED",
    "JSONL": "JSONL_UTF8_OBJECT_PER_NONBLANK_LINE_SORTED_COLUMNS_DUPLICATE_KEYS_REFUSED",
    "UTF8_TEXT": "UTF8_TEXT_ONE_RECORD_PER_PHYSICAL_LINE",
    "MARKDOWN": "UTF8_MARKDOWN_ONE_RECORD_PER_PHYSICAL_LINE_NO_RENDER",
    "RECONCILED": "PRESERVE_LEFT_ORDER_THEN_RIGHT_ORDER_NO_COERCION",
}


class _DuplicateJSONKey(ValueError):
    pass


class _InvalidJSONConstant(ValueError):
    pass


@dataclass
class ParsedTable:
    format: str
    records: List[Dict[str, Any]]
    columns: List[Dict[str, Any]]
    header_decision: str


@dataclass
class _VerificationContext:
    active_generation_ids: List[str] = field(default_factory=list)
    completed: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    generation_count: int = 0
    record_work: int = 0
    byte_work: int = 0
    receipt_index: Optional[Dict[str, str]] = None


def _column_id(name: str, occurrence: int) -> str:
    digest = sha256_text(canonical_json({"name": name, "occurrence": occurrence}))
    return "col-" + digest[:16]


def _column_specs(names: Sequence[str]) -> List[Dict[str, Any]]:
    totals = Counter(names)
    observed: Counter[str] = Counter()
    result: List[Dict[str, Any]] = []
    for position, name in enumerate(names):
        observed[name] += 1
        result.append(
            {
                "column_id": _column_id(name, observed[name]),
                "name": name,
                "position": position,
                "duplicate_name": totals[name] > 1,
            }
        )
    return result


def _strict_json_loads(text: str, max_field_bytes: int = 1024 * 1024) -> Any:
    def object_hook(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for key, value in pairs:
            if key in result:
                raise _DuplicateJSONKey(key)
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise _InvalidJSONConstant(value)

    def parse_integer(value: str) -> int:
        if len(value) > min(max_field_bytes, _MAX_JSON_NUMBER_CHARACTERS):
            raise Refusal(
                "A JSON numeric token exceeds the safe parser budget.",
                code="DATA_NUMERIC_TOKEN_BUDGET",
                details={"max_characters": min(max_field_bytes, _MAX_JSON_NUMBER_CHARACTERS)},
            )
        return int(value)

    def parse_number(value: str) -> float:
        if len(value) > min(max_field_bytes, _MAX_JSON_NUMBER_CHARACTERS):
            raise Refusal(
                "A JSON numeric token exceeds the safe parser budget.",
                code="DATA_NUMERIC_TOKEN_BUDGET",
                details={"max_characters": min(max_field_bytes, _MAX_JSON_NUMBER_CHARACTERS)},
            )
        return float(value)

    try:
        return json.loads(
            text,
            object_pairs_hook=object_hook,
            parse_constant=reject_constant,
            parse_int=parse_integer,
            parse_float=parse_number,
        )
    except _DuplicateJSONKey as exc:
        raise Refusal(
            "JSON contains a duplicate object key and cannot be represented losslessly.",
            code="DATA_DUPLICATE_JSON_KEY",
            details={"key": str(exc)},
            repairs=[
                "Preserve the original file and export JSON with unique object keys.",
                "If repeated fields are intentional, encode them as an explicit array.",
                "Create a new import plan for the corrected exact bytes before inspection.",
            ],
        ) from exc
    except _InvalidJSONConstant as exc:
        raise Refusal(
            "JSON contains a non-standard numeric constant.",
            code="DATA_JSON_CONSTANT_REFUSED",
            details={"constant": str(exc)},
        ) from exc
    except json.JSONDecodeError as exc:
        raise Refusal(
            "The managed JSON content is malformed.",
            code="DATA_PARSE_ERROR",
            details={"line": exc.lineno, "column": exc.colno},
        ) from exc
    except RecursionError as exc:
        raise Refusal(
            "JSON nesting exceeds the safe parser depth.",
            code="DATA_NESTING_BUDGET",
        ) from exc
    except ValueError as exc:
        raise Refusal(
            "The managed JSON content cannot be represented safely.",
            code="DATA_PARSE_ERROR",
        ) from exc


def _check_value_bounds(value: Any, max_depth: int, max_field_bytes: int, depth: int = 0) -> None:
    if depth > max_depth:
        raise Refusal(
            "JSON nesting exceeds the reviewed resource budget.",
            code="DATA_NESTING_BUDGET",
            details={"max_nesting_depth": max_depth},
        )
    if isinstance(value, str):
        if len(value.encode("utf-8")) > max_field_bytes:
            raise Refusal(
                "A field exceeds the reviewed field-size budget.",
                code="DATA_FIELD_BUDGET",
                details={"max_field_bytes": max_field_bytes},
            )
        return
    if isinstance(value, Mapping):
        for key, child in value.items():
            _check_value_bounds(str(key), max_depth, max_field_bytes, depth + 1)
            _check_value_bounds(child, max_depth, max_field_bytes, depth + 1)
        return
    if isinstance(value, list):
        for child in value:
            _check_value_bounds(child, max_depth, max_field_bytes, depth + 1)
        return
    if isinstance(value, float) and not math.isfinite(value):
        raise Refusal("Non-finite numeric values are refused.", code="DATA_JSON_CONSTANT_REFUSED")


def _budget_value(budget: Mapping[str, Any], name: str, fallback: int) -> int:
    value = budget.get(name, fallback)
    if not isinstance(value, int) or isinstance(value, bool) or value < 1:
        raise Refusal("The archived parser resource budget is invalid.", code="DATA_RESOURCE_BUDGET")
    return value


def _bounded_budget_value(
    budget: Mapping[str, Any],
    name: str,
    fallback: int,
    hard_maximum: int,
) -> int:
    value = _budget_value(budget, name, fallback)
    if value > hard_maximum:
        raise Refusal(
            "The archived parser resource budget exceeds this Data Desk implementation's hard safety ceiling.",
            code="DATA_RESOURCE_BUDGET",
            details={"field": name, "requested": value, "hard_maximum": hard_maximum},
            repairs=[
                "Create a new import plan within the reported hard safety ceiling.",
                "Split the source into independently preserved bounded artifacts.",
                "Do not raise an in-memory parser ceiling merely to force an oversized source through.",
            ],
        )
    return value


def _check_managed_size(path: Path, budget: Mapping[str, Any], *, in_memory_json: bool = False) -> int:
    try:
        size = path.stat().st_size
    except OSError as exc:
        raise Refusal("The managed artifact size could not be inspected.", code="DATA_SOURCE_UNREADABLE") from exc
    maximum = _budget_value(budget, "max_source_bytes", 100 * 1024 * 1024)
    if size > maximum:
        raise Refusal(
            "The managed artifact exceeds its archived source-size budget.",
            code="DATA_RESOURCE_BUDGET",
            details={"size_bytes": size, "max_source_bytes": maximum},
        )
    if size > _MAX_MANAGED_SOURCE_BYTES:
        raise Refusal(
            "The managed artifact exceeds the Data Desk parser's hard source-size ceiling.",
            code="DATA_RESOURCE_BUDGET",
            details={"size_bytes": size, "hard_maximum": _MAX_MANAGED_SOURCE_BYTES},
            repairs=[
                "Split the source into independently sealed bounded artifacts.",
                "Use a separately reviewed streaming adapter for larger sources.",
                "Do not raise the ceiling without repeating installed adversity tests.",
            ],
        )
    if in_memory_json and size > _MAX_JSON_DOCUMENT_BYTES:
        raise Refusal(
            "A JSON document exceeds the bounded in-memory parser ceiling.",
            code="DATA_JSON_DOCUMENT_BUDGET",
            details={"size_bytes": size, "hard_maximum": _MAX_JSON_DOCUMENT_BYTES},
            repairs=[
                "Preserve the source and export it as bounded JSONL when one object per line is truthful.",
                "Split the source into independently sealed JSON artifacts.",
                "Do not increase the ceiling without a separately reviewed streaming JSON parser.",
            ],
        )
    return size


def _check_time(started: float, timeout_seconds: int) -> None:
    if time.monotonic() - started > timeout_seconds:
        raise Refusal(
            "Data Desk inspection exceeded the reviewed resource timeout.",
            code="DATA_RESOURCE_TIMEOUT",
            details={"timeout_seconds": timeout_seconds},
        )


def _check_record_limit(count: int, maximum: int) -> None:
    if count > maximum:
        raise Refusal(
            "The parsed record count exceeds the reviewed resource budget.",
            code="DATA_RECORD_BUDGET",
            details={"max_records": maximum},
        )


def _check_columns(names: Sequence[str], maximum: int) -> None:
    if len(names) > maximum:
        raise Refusal(
            "The parsed column count exceeds the reviewed resource budget.",
            code="DATA_COLUMN_BUDGET",
            details={"max_columns": maximum},
        )
    if any(not name for name in names):
        raise Refusal(
            "A table header contains an empty column name.",
            code="DATA_EMPTY_HEADER",
            repairs=[
                "Preserve the source and give every column an explicit non-empty name.",
                "Record that header repair as a separate source generation.",
                "Create and review a new import plan before reinspecting the corrected file.",
            ],
        )


def _refuse_obvious_tabular_spoof(path: Path) -> None:
    with path.open("rb") as handle:
        prefix = handle.read(4096).decode("utf-8", errors="strict").lstrip("\ufeff \t\r\n")
    if prefix.startswith(("{", "[")):
        raise Refusal(
            "The managed bytes look like JSON but were imported as a delimited table.",
            code="DATA_FORMAT_SPOOFED",
            repairs=[
                "Keep the original bytes and use their truthful `.json` or `.jsonl` format.",
                "Do not rename content merely to bypass parser selection.",
                "Create a new reviewed import plan for the correctly identified format.",
            ],
        )


def _parse_delimited(path: Path, format_name: str, budget: Mapping[str, Any]) -> ParsedTable:
    _check_managed_size(path, budget)
    _refuse_obvious_tabular_spoof(path)
    delimiter = "\t" if format_name == "TSV" else ","
    max_records = _bounded_budget_value(budget, "max_records", 1_000_000, _MAX_PARSER_RECORDS)
    max_columns = _bounded_budget_value(budget, "max_columns", 10_000, _MAX_PARSER_COLUMNS)
    max_field_bytes = _bounded_budget_value(
        budget, "max_field_bytes", 1024 * 1024, _MAX_PARSER_FIELD_BYTES
    )
    timeout_seconds = _budget_value(budget, "timeout_seconds", 60)
    started = time.monotonic()
    previous_limit = csv.field_size_limit()
    csv.field_size_limit(max_field_bytes)
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.reader(handle, delimiter=delimiter, strict=True)
            try:
                names = next(reader)
            except StopIteration:
                raise Refusal("The delimited table is empty and has no header.", code="DATA_NO_HEADER")
            except csv.Error as exc:
                raise Refusal("The delimited header is malformed.", code="DATA_PARSE_ERROR") from exc
            if names and names[0].startswith("\ufeff"):
                names[0] = names[0][1:]
            _check_columns(names, max_columns)
            for name in names:
                _check_value_bounds(name, 1, max_field_bytes)
            columns = _column_specs(names)
            records: List[Dict[str, Any]] = []
            try:
                for row_number, row in enumerate(reader, start=2):
                    _check_time(started, timeout_seconds)
                    _check_record_limit(len(records) + 1, max_records)
                    if len(row) != len(columns):
                        raise Refusal(
                            "A delimited row has a different width from the preserved header.",
                            code="DATA_ROW_WIDTH_MISMATCH",
                            details={"row_number": row_number, "expected_fields": len(columns), "actual_fields": len(row)},
                        )
                    record: Dict[str, Any] = {}
                    for column, value in zip(columns, row):
                        _check_value_bounds(value, 1, max_field_bytes)
                        record[column["column_id"]] = value
                    records.append(record)
            except csv.Error as exc:
                if "field larger than field limit" in str(exc).casefold():
                    raise Refusal(
                        "A field exceeds the reviewed field-size budget.",
                        code="DATA_FIELD_BUDGET",
                        details={"max_field_bytes": max_field_bytes},
                    ) from exc
                raise Refusal("The delimited table is malformed.", code="DATA_PARSE_ERROR") from exc
    finally:
        csv.field_size_limit(previous_limit)
    header_decision = "EXPLICIT_DUPLICATE_PRESERVED" if any(row["duplicate_name"] for row in columns) else "EXPLICIT_UNIQUE"
    return ParsedTable(format_name, records, columns, header_decision)


def _objects_to_table(values: Sequence[Mapping[str, Any]], format_name: str, budget: Mapping[str, Any]) -> ParsedTable:
    max_records = _bounded_budget_value(budget, "max_records", 1_000_000, _MAX_PARSER_RECORDS)
    max_columns = _bounded_budget_value(budget, "max_columns", 10_000, _MAX_PARSER_COLUMNS)
    _check_record_limit(len(values), max_records)
    names = sorted({str(key) for value in values for key in value})
    if not values or not names:
        raise Refusal(
            "The JSON table has no records or named fields to profile.",
            code="DATA_JSON_EMPTY_SCHEMA",
        )
    _check_columns(names, max_columns)
    columns = _column_specs(names)
    by_name = {row["name"]: row["column_id"] for row in columns}
    records = [
        {by_name[str(key)]: child for key, child in value.items()}
        for value in values
    ]
    return ParsedTable(format_name, records, columns, "OBJECT_KEYS")


def _parse_jsonl(path: Path, budget: Mapping[str, Any]) -> ParsedTable:
    _check_managed_size(path, budget)
    max_records = _bounded_budget_value(budget, "max_records", 1_000_000, _MAX_PARSER_RECORDS)
    max_depth = _bounded_budget_value(
        budget, "max_nesting_depth", 64, _MAX_PARSER_NESTING_DEPTH
    )
    max_field_bytes = _bounded_budget_value(
        budget, "max_field_bytes", 1024 * 1024, _MAX_PARSER_FIELD_BYTES
    )
    timeout_seconds = _budget_value(budget, "timeout_seconds", 60)
    started = time.monotonic()
    values: List[Mapping[str, Any]] = []
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line_number, line in enumerate(handle, start=1):
            _check_time(started, timeout_seconds)
            if not line.strip():
                continue
            _check_record_limit(len(values) + 1, max_records)
            value = _strict_json_loads(line, max_field_bytes)
            if not isinstance(value, Mapping):
                raise Refusal(
                    "Every JSONL record must be one JSON object.",
                    code="DATA_JSONL_SHAPE",
                    details={"line_number": line_number},
                )
            _check_value_bounds(value, max_depth, max_field_bytes)
            values.append(value)
    return _objects_to_table(values, "JSONL", budget)


def _parse_json(path: Path, budget: Mapping[str, Any]) -> ParsedTable:
    _check_managed_size(path, budget, in_memory_json=True)
    max_depth = _bounded_budget_value(
        budget, "max_nesting_depth", 64, _MAX_PARSER_NESTING_DEPTH
    )
    max_field_bytes = _bounded_budget_value(
        budget, "max_field_bytes", 1024 * 1024, _MAX_PARSER_FIELD_BYTES
    )
    timeout_seconds = _budget_value(budget, "timeout_seconds", 60)
    started = time.monotonic()
    value = _strict_json_loads(path.read_text(encoding="utf-8"), max_field_bytes)
    _check_time(started, timeout_seconds)
    _check_value_bounds(value, max_depth, max_field_bytes)
    if isinstance(value, Mapping):
        values: Sequence[Mapping[str, Any]] = [value]
    elif isinstance(value, list) and all(isinstance(item, Mapping) for item in value):
        values = value
    else:
        raise Refusal(
            "Tabular JSON must be one object or an array of objects.",
            code="DATA_JSON_SHAPE",
        )
    return _objects_to_table(values, "JSON", budget)


def _parse_text(path: Path, format_name: str, budget: Mapping[str, Any]) -> ParsedTable:
    _check_managed_size(path, budget)
    max_records = _bounded_budget_value(budget, "max_records", 1_000_000, _MAX_PARSER_RECORDS)
    max_field_bytes = _bounded_budget_value(
        budget, "max_field_bytes", 1024 * 1024, _MAX_PARSER_FIELD_BYTES
    )
    timeout_seconds = _budget_value(budget, "timeout_seconds", 60)
    column = _column_specs(["text"])[0]
    records: List[Dict[str, Any]] = []
    started = time.monotonic()
    with path.open("r", encoding="utf-8", newline="") as handle:
        for line in handle:
            _check_time(started, timeout_seconds)
            _check_record_limit(len(records) + 1, max_records)
            value = line.rstrip("\r\n")
            _check_value_bounds(value, 1, max_field_bytes)
            records.append({column["column_id"]: value})
    return ParsedTable(format_name, records, [column], "SYNTHETIC_TEXT_COLUMN")


def _parse_managed(path: Path, format_name: str, budget: Mapping[str, Any]) -> ParsedTable:
    if format_name in {"CSV", "TSV"}:
        return _parse_delimited(path, format_name, budget)
    if format_name == "JSONL":
        return _parse_jsonl(path, budget)
    if format_name == "JSON":
        return _parse_json(path, budget)
    if format_name in {"UTF8_TEXT", "MARKDOWN"}:
        return _parse_text(path, format_name, budget)
    raise Refusal("The managed format has no Data Desk parser.", code="DATA_FORMAT_UNSUPPORTED")


def _record_metrics(records: Sequence[Mapping[str, Any]]) -> Tuple[bytes, str, str, List[str]]:
    rendered = [canonical_json(dict(record)) for record in records]
    record_hashes = [sha256_text(value) for value in rendered]
    records_sha256 = sha256_text(canonical_json(sorted(record_hashes)))
    order_sha256 = sha256_text(canonical_json(record_hashes))
    return "".join(rendered).encode("utf-8"), records_sha256, order_sha256, record_hashes


def _value_type(value: Any) -> str:
    if value is None or value == "":
        return "NULL"
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "INTEGER"
    if isinstance(value, float):
        return "NUMBER"
    if isinstance(value, Mapping):
        return "OBJECT"
    if isinstance(value, list):
        return "ARRAY"
    text = str(value)
    if _INTEGER_RE.fullmatch(text):
        return "INTEGER"
    if _NUMBER_RE.fullmatch(text):
        return "NUMBER"
    if text.casefold() in {"true", "false"}:
        return "BOOLEAN"
    candidate = text[:-1] + "+00:00" if text.endswith("Z") else text
    if "-" in candidate or "T" in candidate:
        try:
            _datetime.datetime.fromisoformat(candidate)
            return "DATETIME"
        except ValueError:
            pass
    return "STRING"


def _observed_column_type(values: Iterable[Any]) -> str:
    types = {_value_type(value) for value in values if value is not _MISSING and _value_type(value) != "NULL"}
    if not types:
        return "NULL"
    if types <= {"INTEGER", "NUMBER"}:
        return "INTEGER" if types == {"INTEGER"} else "NUMBER"
    if len(types) == 1:
        return next(iter(types))
    return "MIXED"


def _formula_like(value: Any) -> bool:
    if not isinstance(value, str) or not value:
        return False
    if value[0] in {"+", "-"} and _NUMBER_RE.fullmatch(value):
        return False
    return value[0] in {"=", "+", "-", "@"}


def _build_profile(
    generation_id: str,
    created_at_utc: str,
    format_name: str,
    records: Sequence[Mapping[str, Any]],
    columns: Sequence[Mapping[str, Any]],
    header_decision: str,
    records_sha256: str,
    order_sha256: str,
    user_confirmed_annotations: Sequence[Mapping[str, str]],
) -> Dict[str, Any]:
    rendered = [canonical_json(dict(record)) for record in records]
    duplicates = sum(count - 1 for count in Counter(rendered).values() if count > 1)
    profile_columns: List[Dict[str, Any]] = []
    candidate_keys: List[str] = []
    anomaly_queue: List[Dict[str, str]] = []
    for column in columns:
        column_id = str(column["column_id"])
        values = [record.get(column_id, _MISSING) for record in records]
        nonmissing = [value for value in values if value is not _MISSING and value not in (None, "")]
        distinct = len({canonical_json(value) for value in nonmissing})
        null_count = len(values) - len(nonmissing)
        observed_type = _observed_column_type(values)
        profile_columns.append(
            {
                "column_id": column_id,
                "name": column["name"],
                "position": column["position"],
                "duplicate_name": bool(column["duplicate_name"]),
                "observed_type": observed_type,
                "null_count": null_count,
                "distinct_count": distinct,
            }
        )
        if records and null_count == 0 and distinct == len(records):
            candidate_keys.append(column_id)
        if observed_type == "MIXED":
            anomaly_queue.append(
                {
                    "classification": "CANDIDATE",
                    "code": "MIXED_LEXICAL_TYPES",
                    "message": "One column contains multiple lexical or structural type candidates.",
                }
            )

    duplicate_names = sorted({str(row["name"]) for row in columns if row["duplicate_name"]})
    if duplicate_names:
        anomaly_queue.append(
            {
                "classification": "LEAD",
                "code": "DUPLICATE_HEADERS_PRESERVED",
                "message": "Duplicate header names were preserved as distinct positional columns.",
            }
        )
    folded = Counter(str(row["name"]).casefold() for row in columns)
    if any(count > 1 for count in folded.values()) and not duplicate_names:
        anomaly_queue.append(
            {
                "classification": "LEAD",
                "code": "CASE_COLLISION_HEADERS",
                "message": "Column names differ only by case and require user review.",
            }
        )
    if duplicates:
        anomaly_queue.append(
            {
                "classification": "CANDIDATE",
                "code": "EXACT_DUPLICATE_ROWS",
                "message": "Exact duplicate records are present and remain preserved.",
            }
        )
    if any(_formula_like(value) for record in records for value in record.values()):
        anomaly_queue.append(
            {
                "classification": "LEAD",
                "code": "FORMULA_LIKE_TEXT_PRESERVED",
                "message": "Formula-like text was preserved without execution and requires review before spreadsheet export.",
            }
        )
    if records and not candidate_keys:
        anomaly_queue.append(
            {
                "classification": "LEAD",
                "code": "NO_CANDIDATE_KEY",
                "message": "No single complete unique column was observed; record identity remains user-declared.",
            }
        )
    annotation_values: Dict[Tuple[str, str], set] = {}
    for annotation in user_confirmed_annotations:
        key = (str(annotation["column_id"]), str(annotation["annotation_kind"]))
        annotation_values.setdefault(key, set()).add(str(annotation["value"]))
    if any(len(values) > 1 for values in annotation_values.values()):
        anomaly_queue.append(
            {
                "classification": "CANDIDATE",
                "code": "CONFLICTING_USER_ANNOTATIONS_PRESERVED",
                "message": "Conflicting user-confirmed units or semantic types remain preserved for review.",
            }
        )
    anomaly_queue = sorted(
        {canonical_json(row): row for row in anomaly_queue}.values(),
        key=lambda row: (row["classification"], row["code"], row["message"]),
    )
    profile = bind_data_record(
        {
            "schema": DATA_PROFILE_SCHEMA,
            "schema_version": 2,
            "created_at_utc": created_at_utc,
            "generation_id": generation_id,
            "format": format_name,
            "table_count": 1,
            "row_count": len(records),
            "records_sha256": records_sha256,
            "order_sha256": order_sha256,
            "header_decision": header_decision,
            "exact_duplicate_row_count": duplicates,
            "candidate_keys": sorted(candidate_keys),
            "columns": profile_columns,
            "user_confirmed_annotations": [dict(row) for row in user_confirmed_annotations],
            "anomaly_queue": anomaly_queue,
            "limitations": [
                "Anomaly queue entries are leads or candidates, not scientific findings.",
                "Structural and lexical observations only; no scientific interpretation.",
                "Units and semantic types require explicit user confirmation.",
            ],
        }
    )
    validate_data_record(profile)
    return profile


def _parser_decisions(
    format_name: str,
    columns: Sequence[Mapping[str, Any]],
    header_decision: str,
) -> Dict[str, Any]:
    return {
        "representation": "COLUMN_ID_OBJECTS",
        "source_order_preserved": True,
        "header_decision": header_decision,
        "format_decision": _FORMAT_DECISIONS[format_name],
        "columns": [dict(row) for row in columns],
    }


def _resolve_user_annotations(
    columns: Sequence[Mapping[str, Any]],
    units: Sequence[str],
    semantic_types: Sequence[str],
) -> List[Dict[str, str]]:
    annotations: List[Dict[str, str]] = []
    for annotation_kind, values in (("UNIT", units), ("SEMANTIC_TYPE", semantic_types)):
        for specification in values:
            selector, separator, value = specification.partition("=")
            selector = selector.strip()
            value = value.strip()
            if not separator or not selector or not value or len(value) > 256 or any(ord(char) < 32 or ord(char) == 127 for char in value):
                raise Refusal(
                    "A user-confirmed annotation must be `COLUMN=VALUE` with a bounded printable value.",
                    code="DATA_ANNOTATION_INVALID",
                    details={"annotation_kind": annotation_kind},
                )
            if _COLUMN_ID_RE.fullmatch(selector):
                matches = [row for row in columns if row.get("column_id") == selector]
            else:
                matches = [row for row in columns if row.get("name") == selector]
            if len(matches) != 1:
                raise Refusal(
                    "A user-confirmed annotation column is missing or ambiguous.",
                    code="DATA_ANNOTATION_COLUMN_INVALID",
                    details={"selector": selector, "match_count": len(matches)},
                    repairs=[
                        "Use one exact unique source column name.",
                        "For duplicate headers, use the exact stable `col-...` identifier from an unannotated inspection.",
                        "Do not guess units or semantic types; only record a value the user has confirmed.",
                    ],
                )
            annotations.append(
                {
                    "column_id": str(matches[0]["column_id"]),
                    "annotation_kind": annotation_kind,
                    "value": value,
                    "confirmation": "USER_CONFIRMED",
                }
            )
    return sorted(
        {canonical_json(row): row for row in annotations}.values(),
        key=lambda row: (row["column_id"], row["annotation_kind"], row["value"]),
    )


def _generation_id(
    *,
    parent_generation_ids: Sequence[str],
    operation_binding_sha256: Optional[str],
    format_name: str,
    decisions: Mapping[str, Any],
    raw_artifact_sha256s: Sequence[str],
    records_sha256: str,
    order_sha256: str,
    record_count: int,
    user_confirmed_annotations: Sequence[Mapping[str, str]],
) -> str:
    return sha256_text(
        canonical_json(
            {
                "schema": "uriel.data_generation_identity.v2",
                "parser_version": DATA_PARSER_VERSION,
                "parent_generation_ids": list(parent_generation_ids),
                "operation_binding_sha256": operation_binding_sha256,
                "format": format_name,
                "parser_decisions": decisions,
                "raw_artifact_sha256s": sorted(set(raw_artifact_sha256s)),
                "records_sha256": records_sha256,
                "order_sha256": order_sha256,
                "record_count": record_count,
                "user_confirmed_annotations": [dict(row) for row in user_confirmed_annotations],
            }
        )
    )


def _reconciliation_operation_binding(
    left_generation_id: str,
    right_generation_id: str,
    left_records_sha256: str,
    right_records_sha256: str,
    key_columns: Sequence[str],
    delta_sha256: str,
) -> str:
    return sha256_text(
        canonical_json(
            {
                "schema": "uriel.data_reconciliation_identity.v1",
                "left_generation_id": left_generation_id,
                "right_generation_id": right_generation_id,
                "left_records_sha256": left_records_sha256,
                "right_records_sha256": right_records_sha256,
                "key_columns": list(key_columns),
                "delta_sha256": delta_sha256,
            }
        )
    )


def _generation_paths(root: Path, generation_id: str) -> Tuple[Path, Path, Path]:
    base = root / DATA_ROOT_RELATIVE / "generations" / generation_id
    return base / "manifest.json", base / "records.jsonl", base / "profile.json"


def _generation_index_path(root: Path, generation_id: str) -> Path:
    return root / DATA_ROOT_RELATIVE / "indexes" / (generation_id + ".sqlite")


def _verify_generation_index(
    root: Path,
    generation_id: str,
    records: Sequence[Mapping[str, Any]],
    records_sha256: str,
    order_sha256: str,
    records_file_sha256: str,
    records_file_size_bytes: int,
) -> Dict[str, Any]:
    try:
        target = guard_path(root, _generation_index_path(root, generation_id), must_exist=True)
        if not target.is_file():
            raise OSError("not a regular file")
        if target.stat().st_size > _MAX_SQLITE_INDEX_BYTES:
            raise OSError("index exceeds hard byte budget")
    except (OSError, Refusal) as exc:
        raise Refusal(
            "The derived generation index is missing or not a confined regular file.",
            code="DATA_INDEX_INVALID",
        ) from exc
    connection: Optional[sqlite3.Connection] = None
    rows_match = True
    observed_rows = 0
    try:
        connection = sqlite3.connect(target.as_uri() + "?mode=ro&immutable=1", uri=True)
        connection.execute("PRAGMA query_only=ON")
        try:
            connection.execute("PRAGMA trusted_schema=OFF")
        except sqlite3.DatabaseError:
            pass
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        objects = connection.execute(
            "SELECT type, name, tbl_name FROM sqlite_master "
            "WHERE name NOT LIKE 'sqlite_autoindex%' ORDER BY type, name"
        ).fetchall()
        metadata_count = connection.execute("SELECT COUNT(*) FROM metadata").fetchone()
        if metadata_count is None or metadata_count[0] > 16:
            raise sqlite3.DatabaseError("metadata row budget exceeded")
        metadata = dict(connection.execute("SELECT key, value FROM metadata ORDER BY key").fetchall())
        row_count = connection.execute("SELECT COUNT(*) FROM records").fetchone()
        if row_count is None or row_count[0] > _MAX_GENERATION_RECORDS:
            raise sqlite3.DatabaseError("index row budget exceeded")
        row_stream = connection.execute(
            "SELECT ordinal, record_sha256, canonical_json FROM records ORDER BY ordinal"
        )
        while True:
            batch = row_stream.fetchmany(1024)
            if not batch:
                break
            for row in batch:
                ordinal = observed_rows
                if ordinal >= len(records):
                    rows_match = False
                else:
                    rendered = canonical_json(dict(records[ordinal]))
                    expected = (ordinal, sha256_text(rendered), rendered)
                    if row != expected:
                        rows_match = False
                observed_rows += 1
    except sqlite3.DatabaseError as exc:
        raise Refusal(
            "The derived generation index failed read-only integrity verification.",
            code="DATA_INDEX_INVALID",
            details={"error_type": type(exc).__name__},
        ) from exc
    finally:
        if connection is not None:
            connection.close()

    expected_metadata = {
        "generation_id": generation_id,
        "index_role": "DERIVED_NONAUTHORITATIVE",
        "index_schema": "uriel.data_index.v1",
        "order_sha256": order_sha256,
        "record_count": str(len(records)),
        "records_sha256": records_sha256,
        "records_file_sha256": records_file_sha256,
        "records_file_size_bytes": str(records_file_size_bytes),
    }
    expected_objects = [
        ("index", "idx_records_sha256", "records"),
        ("table", "metadata", "metadata"),
        ("table", "records", "records"),
    ]
    checks = {
        "integrity": integrity == ("ok",),
        "schema_objects": objects == expected_objects,
        "metadata": metadata == expected_metadata,
        "records": rows_match and observed_rows == len(records),
    }
    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise Refusal(
            "The derived generation index does not match its generation.",
            code="DATA_INDEX_INVALID",
            details={"failed_checks": failed},
        )
    return {
        "verified": True,
        "role": "DERIVED_NONAUTHORITATIVE",
        "relative_path": target.relative_to(root).as_posix(),
        "record_count": len(records),
    }


def _ensure_generation_index(
    root: Path,
    generation_id: str,
    records: Sequence[Mapping[str, Any]],
    records_sha256: str,
    order_sha256: str,
    records_file_sha256: str,
    records_file_size_bytes: int,
) -> Dict[str, Any]:
    target = guard_path(root, _generation_index_path(root, generation_id))
    if target.exists():
        return _verify_generation_index(
            root,
            generation_id,
            records,
            records_sha256,
            order_sha256,
            records_file_sha256,
            records_file_size_bytes,
        )
    parent = _ensure_directory(root, target.parent)
    temporary = guard_path(root, parent / ("." + target.name + ".tmp." + uuid.uuid4().hex))
    connection: Optional[sqlite3.Connection] = None
    try:
        connection = sqlite3.connect(str(temporary))
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA temp_store=MEMORY")
        connection.execute("PRAGMA page_size=4096")
        connection.execute("CREATE TABLE metadata (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        connection.execute(
            "CREATE TABLE records ("
            "ordinal INTEGER PRIMARY KEY, record_sha256 TEXT NOT NULL, canonical_json TEXT NOT NULL)"
        )
        metadata = {
            "generation_id": generation_id,
            "index_role": "DERIVED_NONAUTHORITATIVE",
            "index_schema": "uriel.data_index.v1",
            "order_sha256": order_sha256,
            "record_count": str(len(records)),
            "records_sha256": records_sha256,
            "records_file_sha256": records_file_sha256,
            "records_file_size_bytes": str(records_file_size_bytes),
        }
        connection.executemany(
            "INSERT INTO metadata (key, value) VALUES (?, ?)",
            sorted(metadata.items()),
        )
        connection.executemany(
            "INSERT INTO records (ordinal, record_sha256, canonical_json) VALUES (?, ?, ?)",
            (
                (ordinal, sha256_text(canonical_json(dict(record))), canonical_json(dict(record)))
                for ordinal, record in enumerate(records)
            ),
        )
        connection.execute("CREATE INDEX idx_records_sha256 ON records (record_sha256)")
        connection.commit()
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if integrity != ("ok",):
            raise Refusal("The derived generation index failed its build integrity check.", code="DATA_INDEX_INVALID")
        connection.close()
        connection = None
        if temporary.stat().st_size > _MAX_SQLITE_INDEX_BYTES:
            raise Refusal(
                "The derived generation index exceeds the hard byte budget.",
                code="DATA_INDEX_BUDGET",
                details={"max_bytes": _MAX_SQLITE_INDEX_BYTES},
            )
        with temporary.open("rb+") as handle:
            os.fsync(handle.fileno())
        try:
            os.link(str(temporary), str(target))
        except FileExistsError:
            pass
        except OSError as exc:
            raise Refusal(
                "Uriel could not atomically publish the derived generation index.",
                code="DATA_INDEX_WRITE_FAILED",
                details={"error_type": type(exc).__name__},
            ) from exc
    except Refusal:
        raise
    except (OSError, sqlite3.DatabaseError) as exc:
        raise Refusal(
            "Uriel could not build the derived generation index.",
            code="DATA_INDEX_WRITE_FAILED",
            details={"error_type": type(exc).__name__},
        ) from exc
    finally:
        if connection is not None:
            connection.close()
        for suffix in ("", "-journal", "-wal", "-shm"):
            try:
                Path(str(temporary) + suffix).unlink()
            except FileNotFoundError:
                pass
    return _verify_generation_index(
        root,
        generation_id,
        records,
        records_sha256,
        order_sha256,
        records_file_sha256,
        records_file_size_bytes,
    )


def _write_generation(
    root: Path,
    *,
    format_name: str,
    records: Sequence[Mapping[str, Any]],
    columns: Sequence[Mapping[str, Any]],
    header_decision: str,
    raw_artifact_sha256s: Sequence[str],
    parent_generation_ids: Sequence[str],
    operation_binding_sha256: Optional[str],
    reconciliation_sha256: Optional[str],
    created_at_utc: str,
    user_confirmed_annotations: Sequence[Mapping[str, str]],
    pre_manifest_records: Sequence[Tuple[Path, Mapping[str, Any]]] = (),
    pre_manifest_payloads: Sequence[Tuple[Path, bytes]] = (),
    expected_generation_id: Optional[str] = None,
) -> Dict[str, Any]:
    records_bytes, records_sha256, order_sha256, _ = _record_metrics(records)
    records_file_sha256 = sha256_bytes(records_bytes)
    records_file_size_bytes = len(records_bytes)
    if len(records) > _MAX_GENERATION_RECORDS or records_file_size_bytes > _MAX_GENERATION_FILE_BYTES:
        raise Refusal(
            "The derived generation exceeds the hard publication budget.",
            code="DATA_GENERATION_BUDGET",
            details={
                "record_count": len(records),
                "max_records": _MAX_GENERATION_RECORDS,
                "records_file_size_bytes": records_file_size_bytes,
                "max_file_bytes": _MAX_GENERATION_FILE_BYTES,
            },
        )
    normalized_parents = list(parent_generation_ids)
    if len(normalized_parents) != len(set(normalized_parents)) or len(normalized_parents) > 2:
        raise Refusal("Generation parents are invalid or duplicated.", code="DATA_GENERATION_LINEAGE_INVALID")
    normalized_raw_sha256s = sorted(set(raw_artifact_sha256s))
    if not normalized_raw_sha256s or len(normalized_raw_sha256s) > _MAX_RAW_ARTIFACTS_PER_GENERATION:
        raise Refusal(
            "Generation raw-artifact lineage exceeds the hard binding budget.",
            code="DATA_GENERATION_RAW_BINDING_INVALID",
            details={"max_raw_artifacts": _MAX_RAW_ARTIFACTS_PER_GENERATION},
        )
    decisions = _parser_decisions(format_name, columns, header_decision)
    generation_id = _generation_id(
        parent_generation_ids=normalized_parents,
        operation_binding_sha256=operation_binding_sha256,
        format_name=format_name,
        decisions=decisions,
        raw_artifact_sha256s=normalized_raw_sha256s,
        records_sha256=records_sha256,
        order_sha256=order_sha256,
        record_count=len(records),
        user_confirmed_annotations=user_confirmed_annotations,
    )
    if expected_generation_id is not None and generation_id != expected_generation_id:
        raise Refusal("Generation identity changed during reconciliation.", code="DATA_GENERATION_IDENTITY_DRIFT")
    manifest_path, records_path, profile_path = _generation_paths(root, generation_id)
    index_path = _generation_index_path(root, generation_id)
    if manifest_path.exists():
        _, existing_manifest = _load_json_record(root, manifest_path.relative_to(root).as_posix())
        validate_data_record(existing_manifest)
        requested_bindings = {
            "generation_id": generation_id,
            "parent_generation_ids": normalized_parents,
            "operation_binding_sha256": operation_binding_sha256,
            "format": format_name,
            "parser_decisions": decisions,
            "user_confirmed_annotations": [dict(row) for row in user_confirmed_annotations],
            "raw_artifact_sha256s": normalized_raw_sha256s,
            "reconciliation_sha256": reconciliation_sha256,
            "record_count": len(records),
            "column_count": len(columns),
            "records_sha256": records_sha256,
            "order_sha256": order_sha256,
            "records_file_sha256": records_file_sha256,
            "records_file_size_bytes": records_file_size_bytes,
        }
        mismatches = sorted(
            key for key, requested in requested_bindings.items()
            if existing_manifest.get(key) != requested
        )
        if mismatches:
            raise Refusal(
                "An existing generation ID carries different lineage or artifact bindings.",
                code="DATA_GENERATION_IDENTITY_COLLISION",
                details={"generation_id": generation_id, "mismatched_fields": mismatches},
            )
        _ensure_generation_index(
            root,
            generation_id,
            records,
            records_sha256,
            order_sha256,
            records_file_sha256,
            records_file_size_bytes,
        )
        existing = verify_data_generation(root, generation_id)
        existing["status"] = "EXISTING_GENERATION"
        return existing

    profile = _build_profile(
        generation_id,
        created_at_utc,
        format_name,
        records,
        columns,
        header_decision,
        records_sha256,
        order_sha256,
        user_confirmed_annotations,
    )
    manifest_relative = manifest_path.relative_to(root).as_posix()
    records_relative = records_path.relative_to(root).as_posix()
    profile_relative = profile_path.relative_to(root).as_posix()
    manifest = bind_data_record(
        {
            "schema": DATA_GENERATION_SCHEMA,
            "schema_version": 2,
            "created_at_utc": created_at_utc,
            "generation_id": generation_id,
            "parent_generation_ids": normalized_parents,
            "operation_binding_sha256": operation_binding_sha256,
            "format": format_name,
            "parser_version": DATA_PARSER_VERSION,
            "parser_decisions": decisions,
            "user_confirmed_annotations": [dict(row) for row in user_confirmed_annotations],
            "raw_artifact_sha256s": normalized_raw_sha256s,
            "transform_receipt_sha256s": [],
            "reconciliation_sha256": reconciliation_sha256,
            "record_count": len(records),
            "column_count": len(columns),
            "records_sha256": records_sha256,
            "order_sha256": order_sha256,
            "records_file_sha256": records_file_sha256,
            "records_file_size_bytes": records_file_size_bytes,
            "records_relative_path": records_relative,
            "profile_relative_path": profile_relative,
            "profile_sha256": profile["record_sha256"],
            "derived_index_kind": "SQLITE_DERIVED_NONAUTHORITATIVE",
            "derived_index_relative_path": index_path.relative_to(root).as_posix(),
        }
    )
    validate_data_record(manifest)
    record_payloads = [
        (target, canonical_json(record).encode("utf-8"))
        for target, record in pre_manifest_records
    ]
    pending_bytes = sum(
        len(payload)
        for target, payload in (
            (records_path, records_bytes),
            (profile_path, canonical_json(profile).encode("utf-8")),
            *pre_manifest_payloads,
            *record_payloads,
            (manifest_path, canonical_json(manifest).encode("utf-8")),
        )
        if not target.exists()
    )
    if not index_path.exists():
        pending_bytes += max(64 * 1024, len(records_bytes) * 2 + len(records) * 128 + 8192)
    required_bytes = pending_bytes + _DISK_RESERVE_BYTES
    available_bytes = shutil.disk_usage(str(root)).free
    if available_bytes < required_bytes:
        raise Refusal(
            "The project volume does not have enough free space for an atomic Data Desk generation.",
            code="DATA_DISK_SPACE",
            details={"required_bytes": required_bytes, "available_bytes": available_bytes},
            repairs=[
                "Free enough project-volume space for the generation plus Uriel's one-megabyte safety reserve.",
                "Retry the same verified import or parent generations; immutable partial payloads can be reused safely.",
                "Do not redirect only `.uriel/data` to a different volume.",
            ],
        )
    _write_immutable_bytes(root, records_path, records_bytes)
    _write_immutable_record(root, profile_path, profile)
    _ensure_generation_index(
        root,
        generation_id,
        records,
        records_sha256,
        order_sha256,
        records_file_sha256,
        records_file_size_bytes,
    )
    for target, payload in pre_manifest_payloads:
        _write_immutable_bytes(root, target, payload)
    for target, record in pre_manifest_records:
        _write_immutable_record(root, target, record)
    _write_immutable_record(root, manifest_path, manifest)
    result = verify_data_generation(root, generation_id)
    result.update(
        {
            "status": "GENERATED",
            "manifest_relative_path": manifest_relative,
            "profile": profile,
        }
    )
    return result


def inspect_data_artifact(
    root: Union[str, Path],
    receipt_path: str,
    *,
    units: Sequence[str] = (),
    semantic_types: Sequence[str] = (),
) -> Dict[str, Any]:
    """Parse one independently verified managed artifact into a generation."""

    paths = paths_for(root)
    verified = verify_data_import(paths.root, receipt_path)
    receipt = verified["receipt"]
    _, plan = _load_json_record(paths.root, verified["plan_relative_path"])
    _, raw_record = _load_json_record(paths.root, verified["raw_record_relative_path"])
    managed = guard_path(paths.root, paths.root / verified["managed_relative_path"], must_exist=True)
    table = _parse_managed(managed, str(raw_record["format"]), plan["resource_budget"])
    annotations = _resolve_user_annotations(table.columns, units, semantic_types)
    result = _write_generation(
        paths.root,
        format_name=table.format,
        records=table.records,
        columns=table.columns,
        header_decision=table.header_decision,
        raw_artifact_sha256s=[str(receipt["raw_artifact_sha256"])],
        parent_generation_ids=[],
        operation_binding_sha256=None,
        reconciliation_sha256=None,
        created_at_utc=str(receipt["created_at_utc"]),
        user_confirmed_annotations=annotations,
    )
    result["gate_0_authority_granted"] = False
    result["scientific_findings_created"] = False
    result["annotations_are_user_confirmed_only"] = True
    return result


def _load_generation_records(
    root: Path,
    generation_id: str,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], Dict[str, Any]]:
    if not re.fullmatch(r"[0-9a-f]{64}", generation_id):
        raise Refusal("A 64-character generation ID is required.", code="DATA_GENERATION_ID_INVALID")
    manifest_path, records_path, profile_path = _generation_paths(root, generation_id)
    _, manifest = _load_json_record(root, manifest_path.relative_to(root).as_posix())
    validate_data_record(manifest)
    if manifest.get("schema") != DATA_GENERATION_SCHEMA:
        raise Refusal(
            "This Data Desk runtime requires a v2 generation manifest; the legacy contract remains verifiable only as a record.",
            code="DATA_GENERATION_SCHEMA_UNSUPPORTED",
        )
    if manifest.get("generation_id") != generation_id:
        raise Refusal("Generation manifest path and identity disagree.", code="DATA_GENERATION_BINDING_INVALID")
    records_target = guard_path(root, records_path, must_exist=True)
    try:
        records_file_size_bytes = records_target.stat().st_size
    except OSError as exc:
        raise Refusal("Generation records are unreadable.", code="DATA_GENERATION_RECORDS_INVALID") from exc
    if records_file_size_bytes > _MAX_GENERATION_FILE_BYTES:
        raise Refusal(
            "Generation records exceed the hard verifier byte budget.",
            code="DATA_GENERATION_BUDGET",
            details={"max_file_bytes": _MAX_GENERATION_FILE_BYTES},
        )
    declared_count = manifest.get("record_count")
    if not isinstance(declared_count, int) or isinstance(declared_count, bool) or declared_count > _MAX_GENERATION_RECORDS:
        raise Refusal(
            "Generation records exceed the hard verifier record budget.",
            code="DATA_GENERATION_BUDGET",
            details={"max_records": _MAX_GENERATION_RECORDS},
        )
    records: List[Dict[str, Any]] = []
    digest = hashlib.sha256()
    try:
        with records_target.open("rb") as handle:
            for line_number, raw_line in enumerate(handle, start=1):
                digest.update(raw_line)
                if len(raw_line) > _MAX_GENERATION_RECORD_LINE_BYTES:
                    raise Refusal(
                        "A generation record exceeds the hard per-record byte budget.",
                        code="DATA_GENERATION_BUDGET",
                        details={"line_number": line_number, "max_line_bytes": _MAX_GENERATION_RECORD_LINE_BYTES},
                    )
                if not raw_line or not raw_line.endswith(b"\n") or raw_line in {b"\n", b"\r\n"} or raw_line.endswith(b"\r\n"):
                    raise Refusal(
                        "Generation records contain a blank or noncanonical physical line.",
                        code="DATA_GENERATION_RECORDS_INVALID",
                        details={"line_number": line_number},
                    )
                try:
                    line = raw_line[:-1].decode("utf-8", errors="strict")
                except UnicodeDecodeError as exc:
                    raise Refusal(
                        "Generation records are not valid UTF-8.",
                        code="DATA_GENERATION_RECORDS_INVALID",
                        details={"line_number": line_number},
                    ) from exc
                value = _strict_json_loads(line, _MAX_PARSER_FIELD_BYTES)
                if not isinstance(value, dict) or canonical_json(value).encode("utf-8") != raw_line:
                    raise Refusal(
                        "Generation records are not canonical JSON objects.",
                        code="DATA_GENERATION_RECORDS_INVALID",
                        details={"line_number": line_number},
                    )
                records.append(value)
                _check_record_limit(len(records), _MAX_GENERATION_RECORDS)
    except OSError as exc:
        raise Refusal("Generation records are unreadable.", code="DATA_GENERATION_RECORDS_INVALID") from exc
    _, profile = _load_json_record(root, profile_path.relative_to(root).as_posix())
    validate_data_record(profile)
    if profile.get("schema") != DATA_PROFILE_SCHEMA:
        raise Refusal("The generation profile schema is not supported by this runtime.", code="DATA_PROFILE_SCHEMA_UNSUPPORTED")
    return manifest, records, profile, {
        "sha256": digest.hexdigest(),
        "size_bytes": records_file_size_bytes,
    }


def _resolve_key_columns(profile: Mapping[str, Any], requested: Sequence[str]) -> List[str]:
    columns = profile.get("columns", [])
    resolved: List[str] = []
    for item in requested:
        if _COLUMN_ID_RE.fullmatch(item):
            matches = [row for row in columns if row.get("column_id") == item]
        else:
            matches = [row for row in columns if row.get("name") == item]
        if len(matches) != 1:
            raise Refusal(
                "A reconciliation key is missing or ambiguous in the generation profile.",
                code="DATA_RECONCILIATION_KEY_INVALID",
                details={"key": item, "match_count": len(matches)},
                repairs=[
                    "Use one exact unique column name from both generation profiles.",
                    "For duplicate headers, use the exact `col-...` identifier shown in the profile.",
                    "Do not guess record identity; inspect and confirm the intended keys first.",
                ],
            )
        resolved.append(str(matches[0]["column_id"]))
    if not resolved or len(resolved) != len(set(resolved)):
        raise Refusal("At least one unique reconciliation key is required.", code="DATA_RECONCILIATION_KEY_INVALID")
    return resolved


def _compatible_keys(left_profile: Mapping[str, Any], right_profile: Mapping[str, Any], requested: Sequence[str]) -> List[str]:
    left = _resolve_key_columns(left_profile, requested)
    right = _resolve_key_columns(right_profile, requested)
    if left != right:
        raise Refusal(
            "The requested key columns do not resolve to the same stable identities in both generations.",
            code="DATA_RECONCILIATION_KEY_INVALID",
        )
    return left


def _key_of(record: Mapping[str, Any], keys: Sequence[str]) -> Optional[Tuple[str, ...]]:
    values: List[str] = []
    for key in keys:
        value = record.get(key, _MISSING)
        if value is _MISSING or value in (None, ""):
            return None
        values.append(canonical_json(value))
    return tuple(values)


def _delta_analysis(
    left_records: Sequence[Mapping[str, Any]],
    right_records: Sequence[Mapping[str, Any]],
    keys: Sequence[str],
) -> Dict[str, Any]:
    delta_entry_count = len(left_records) + len(right_records)
    if delta_entry_count > _MAX_DELTA_ENTRIES:
        raise Refusal(
            "Reconciliation exceeds the hard per-record delta budget.",
            code="DATA_RECONCILIATION_BUDGET",
            details={"entry_count": delta_entry_count, "max_entries": _MAX_DELTA_ENTRIES},
        )
    left_rendered = [canonical_json(dict(row)) for row in left_records]
    right_rendered = [canonical_json(dict(row)) for row in right_records]
    exact_duplicate_count = sum((Counter(left_rendered) & Counter(right_rendered)).values())
    left_keys = [_key_of(record, keys) for record in left_records]
    right_keys = [_key_of(record, keys) for record in right_records]
    left_index: Dict[Tuple[str, ...], List[int]] = {}
    right_index: Dict[Tuple[str, ...], List[int]] = {}
    left_classes = ["UNKNOWN"] * len(left_records)
    right_classes = ["UNKNOWN"] * len(right_records)
    left_conflicts = [False] * len(left_records)
    right_conflicts = [False] * len(right_records)
    unknown = 0
    for ordinal, key in enumerate(left_keys):
        if key is None:
            unknown += 1
        else:
            left_index.setdefault(key, []).append(ordinal)
    for ordinal, key in enumerate(right_keys):
        if key is None:
            unknown += 1
        else:
            right_index.setdefault(key, []).append(ordinal)

    added = absent = modified = unchanged = candidate = conflict = 0
    for key in sorted(set(left_index) | set(right_index)):
        left_ordinals = left_index.get(key, [])
        right_ordinals = right_index.get(key, [])
        if len(left_ordinals) > 1 or len(right_ordinals) > 1:
            candidate += 1
            unknown += 1
            left_group = [left_rendered[ordinal] for ordinal in left_ordinals]
            right_group = [right_rendered[ordinal] for ordinal in right_ordinals]
            group_conflict = bool(left_ordinals and right_ordinals) and Counter(left_group) != Counter(right_group)
            if group_conflict:
                conflict += 1
            for ordinal in left_ordinals:
                left_classes[ordinal] = "CANDIDATE_DUPLICATE"
                left_conflicts[ordinal] = group_conflict
            for ordinal in right_ordinals:
                right_classes[ordinal] = "CANDIDATE_DUPLICATE"
                right_conflicts[ordinal] = group_conflict
            continue
        if not left_ordinals:
            added += 1
            for ordinal in right_ordinals:
                right_classes[ordinal] = "ADDED"
            continue
        if not right_ordinals:
            absent += 1
            for ordinal in left_ordinals:
                left_classes[ordinal] = "ABSENT"
            continue
        left_group = [left_rendered[ordinal] for ordinal in left_ordinals]
        right_group = [right_rendered[ordinal] for ordinal in right_ordinals]
        left_ordinal = left_ordinals[0]
        right_ordinal = right_ordinals[0]
        if left_group[0] == right_group[0]:
            unchanged += 1
            left_classes[left_ordinal] = "UNCHANGED"
            right_classes[right_ordinal] = "UNCHANGED"
        else:
            modified += 1
            conflict += 1
            left_classes[left_ordinal] = "MODIFIED"
            right_classes[right_ordinal] = "MODIFIED"
            left_conflicts[left_ordinal] = True
            right_conflicts[right_ordinal] = True
    summary = {
        "exact_duplicate_count": exact_duplicate_count,
        "candidate_duplicate_count": candidate,
        "conflict_count": conflict,
        "preserved_conflict_count": conflict,
        "added_count": added,
        "absent_count": absent,
        "modified_count": modified,
        "unchanged_count": unchanged,
        "unknown_count": unknown,
    }
    entries: List[Dict[str, Any]] = []
    for side, rendered_rows, row_keys, classes, conflicts, opposite_rendered, opposite_index in (
        ("LEFT", left_rendered, left_keys, left_classes, left_conflicts, right_rendered, right_index),
        ("RIGHT", right_rendered, right_keys, right_classes, right_conflicts, left_rendered, left_index),
    ):
        for ordinal, (rendered, key, classification, row_conflict) in enumerate(
            zip(rendered_rows, row_keys, classes, conflicts)
        ):
            counterpart_ordinals = opposite_index.get(key, []) if key is not None else []
            exact_counterparts = sum(
                1 for counterpart_ordinal in counterpart_ordinals
                if opposite_rendered[counterpart_ordinal] == rendered
            )
            entry = bind_data_record(
                {
                    "schema": DATA_DELTA_ENTRY_SCHEMA,
                    "schema_version": 1,
                    "side": side,
                    "ordinal": ordinal,
                    "source_record_sha256": sha256_text(rendered),
                    "key_sha256": sha256_text(canonical_json(list(key))) if key is not None else None,
                    "classification": classification,
                    "counterpart_count": len(counterpart_ordinals),
                    "exact_counterpart_count": exact_counterparts,
                    "conflict": row_conflict,
                    "preserved": True,
                }
            )
            validate_data_record(entry)
            entries.append(entry)
    ledger_bytes = "".join(canonical_json(entry) for entry in entries).encode("utf-8")
    if len(ledger_bytes) > _MAX_DELTA_LEDGER_BYTES:
        raise Refusal(
            "Reconciliation delta bytes exceed the hard ledger budget.",
            code="DATA_RECONCILIATION_BUDGET",
            details={"ledger_bytes": len(ledger_bytes), "max_ledger_bytes": _MAX_DELTA_LEDGER_BYTES},
        )
    return {
        "summary": summary,
        "entries": entries,
        "ledger_bytes": ledger_bytes,
        "delta_sha256": sha256_bytes(ledger_bytes),
    }


def _reconciliation_record(
    *,
    left_manifest: Mapping[str, Any],
    right_manifest: Mapping[str, Any],
    keys: Sequence[str],
    summary: Mapping[str, int],
    delta_sha256: str,
    delta_entry_count: int,
    delta_ledger_relative_path: Optional[str],
    result_generation_id: Optional[str],
    result_record_count: int,
    result_records_sha256: Optional[str],
    created_at_utc: str,
) -> Dict[str, Any]:
    record = bind_data_record(
        {
            "schema": DATA_RECONCILIATION_SCHEMA,
            "schema_version": 2,
            "created_at_utc": created_at_utc,
            "left_generation_id": left_manifest["generation_id"],
            "right_generation_id": right_manifest["generation_id"],
            "left_records_sha256": left_manifest["records_sha256"],
            "right_records_sha256": right_manifest["records_sha256"],
            "key_columns": list(keys),
            **dict(summary),
            "contradiction_policy": "PRESERVE_ALL",
            "result_generation_id": result_generation_id,
            "result_record_count": result_record_count,
            "result_records_sha256": result_records_sha256,
            "delta_sha256": delta_sha256,
            "delta_entry_count": delta_entry_count,
            "delta_ledger_relative_path": delta_ledger_relative_path,
        }
    )
    validate_data_record(record)
    return record


def diff_data_generations(
    root: Union[str, Path],
    left_generation_id: str,
    right_generation_id: str,
    keys: Sequence[str],
) -> Dict[str, Any]:
    paths = paths_for(root)
    verify_data_generation(paths.root, left_generation_id)
    verify_data_generation(paths.root, right_generation_id)
    left_manifest, left_records, left_profile, _ = _load_generation_records(paths.root, left_generation_id)
    right_manifest, right_records, right_profile, _ = _load_generation_records(paths.root, right_generation_id)
    key_columns = _compatible_keys(left_profile, right_profile, keys)
    analysis = _delta_analysis(left_records, right_records, key_columns)
    summary = analysis["summary"]
    record = _reconciliation_record(
        left_manifest=left_manifest,
        right_manifest=right_manifest,
        keys=key_columns,
        summary=summary,
        delta_sha256=analysis["delta_sha256"],
        delta_entry_count=len(analysis["entries"]),
        delta_ledger_relative_path=None,
        result_generation_id=None,
        result_record_count=0,
        result_records_sha256=None,
        created_at_utc=max(str(left_manifest["created_at_utc"]), str(right_manifest["created_at_utc"])),
    )
    return {
        "writes_performed": False,
        "reconciliation": record,
        "summary": summary,
        "delta_ledger": analysis["entries"],
        "delta_sha256": analysis["delta_sha256"],
        "delta_entry_count": len(analysis["entries"]),
        "scientific_findings_created": False,
        "gate_0_authority_granted": False,
    }


def reconcile_data_generations(
    root: Union[str, Path],
    left_generation_id: str,
    right_generation_id: str,
    keys: Sequence[str],
) -> Dict[str, Any]:
    paths = paths_for(root)
    verify_data_generation(paths.root, left_generation_id)
    verify_data_generation(paths.root, right_generation_id)
    left_manifest, left_records, left_profile, _ = _load_generation_records(paths.root, left_generation_id)
    right_manifest, right_records, right_profile, _ = _load_generation_records(paths.root, right_generation_id)
    key_columns = _compatible_keys(left_profile, right_profile, keys)
    analysis = _delta_analysis(left_records, right_records, key_columns)
    summary = analysis["summary"]
    columns: List[Dict[str, Any]] = []
    seen = set()
    for profile in (left_profile, right_profile):
        for row in profile["columns"]:
            column_id = str(row["column_id"])
            if column_id not in seen:
                seen.add(column_id)
                columns.append(
                    {
                        "column_id": column_id,
                        "name": row["name"],
                        "position": len(columns),
                        "duplicate_name": bool(row["duplicate_name"]),
                    }
                )
    result_records = [dict(row) for row in left_records] + [dict(row) for row in right_records]
    _, result_records_sha256, result_order_sha256, _ = _record_metrics(result_records)
    raw_sha256s = sorted(set(left_manifest["raw_artifact_sha256s"] + right_manifest["raw_artifact_sha256s"]))
    annotations = sorted(
        {
            canonical_json(dict(row)): dict(row)
            for profile in (left_profile, right_profile)
            for row in profile["user_confirmed_annotations"]
        }.values(),
        key=lambda row: (row["column_id"], row["annotation_kind"], row["value"]),
    )
    decisions = _parser_decisions("RECONCILED", columns, "RECONCILED_UNION")
    operation_binding_sha256 = _reconciliation_operation_binding(
        left_generation_id,
        right_generation_id,
        str(left_manifest["records_sha256"]),
        str(right_manifest["records_sha256"]),
        key_columns,
        str(analysis["delta_sha256"]),
    )
    result_generation_id = _generation_id(
        parent_generation_ids=[left_generation_id, right_generation_id],
        operation_binding_sha256=operation_binding_sha256,
        format_name="RECONCILED",
        decisions=decisions,
        raw_artifact_sha256s=raw_sha256s,
        records_sha256=result_records_sha256,
        order_sha256=result_order_sha256,
        record_count=len(result_records),
        user_confirmed_annotations=annotations,
    )
    created_at = max(str(left_manifest["created_at_utc"]), str(right_manifest["created_at_utc"]))
    delta_ledger_relative = (
        Path(DATA_ROOT_RELATIVE) / "deltas" / (str(analysis["delta_sha256"]) + ".jsonl")
    ).as_posix()
    reconciliation = _reconciliation_record(
        left_manifest=left_manifest,
        right_manifest=right_manifest,
        keys=key_columns,
        summary=summary,
        delta_sha256=analysis["delta_sha256"],
        delta_entry_count=len(analysis["entries"]),
        delta_ledger_relative_path=delta_ledger_relative,
        result_generation_id=result_generation_id,
        result_record_count=len(result_records),
        result_records_sha256=result_records_sha256,
        created_at_utc=created_at,
    )
    reconciliation_path = paths.root / DATA_ROOT_RELATIVE / "reconciliations" / (reconciliation["record_sha256"] + ".json")
    delta_ledger_path = paths.root / delta_ledger_relative
    generation = _write_generation(
        paths.root,
        format_name="RECONCILED",
        records=result_records,
        columns=columns,
        header_decision="RECONCILED_UNION",
        raw_artifact_sha256s=raw_sha256s,
        parent_generation_ids=[left_generation_id, right_generation_id],
        operation_binding_sha256=operation_binding_sha256,
        reconciliation_sha256=str(reconciliation["record_sha256"]),
        created_at_utc=created_at,
        user_confirmed_annotations=annotations,
        pre_manifest_records=[(reconciliation_path, reconciliation)],
        pre_manifest_payloads=[(delta_ledger_path, analysis["ledger_bytes"])],
        expected_generation_id=result_generation_id,
    )
    generation.update(
        {
            "status": "RECONCILED",
            "reconciliation": reconciliation,
            "reconciliation_relative_path": reconciliation_path.relative_to(paths.root).as_posix(),
            "delta_ledger_relative_path": delta_ledger_relative,
            "delta_entry_count": len(analysis["entries"]),
            "summary": summary,
            "all_input_records_preserved": generation["record_count"] == len(left_records) + len(right_records),
            "gate_0_authority_granted": False,
            "scientific_findings_created": False,
        }
    )
    return generation


def _build_receipt_index(root: Path) -> Dict[str, str]:
    receipt_dir = guard_path(root, root / DATA_ROOT_RELATIVE / "receipts" / "import", must_exist=True)
    if not receipt_dir.is_dir():
        raise Refusal("Generation has no import-receipt store.", code="DATA_GENERATION_RAW_BINDING_INVALID")
    candidates: List[Path] = []
    try:
        with os.scandir(str(receipt_dir)) as entries:
            for entry in entries:
                if not entry.name.endswith(".json"):
                    continue
                if len(candidates) >= _MAX_IMPORT_RECEIPTS:
                    raise Refusal(
                        "The import-receipt store exceeds the verifier lookup budget.",
                        code="DATA_GENERATION_RECEIPT_BUDGET",
                        details={"max_receipts": _MAX_IMPORT_RECEIPTS},
                    )
                candidates.append(guard_path(root, Path(entry.path), must_exist=True))
    except OSError as exc:
        raise Refusal("The import-receipt store is unreadable.", code="DATA_GENERATION_RAW_BINDING_INVALID") from exc
    index: Dict[str, str] = {}
    cumulative_bytes = 0
    for candidate in sorted(candidates, key=lambda item: item.name):
        try:
            cumulative_bytes += candidate.stat().st_size
        except OSError as exc:
            raise Refusal("An import receipt is unreadable.", code="DATA_GENERATION_RAW_BINDING_INVALID") from exc
        if cumulative_bytes > _MAX_IMPORT_RECEIPT_INDEX_BYTES:
            raise Refusal(
                "The import-receipt store exceeds the verifier byte budget.",
                code="DATA_GENERATION_RECEIPT_BUDGET",
                details={"max_bytes": _MAX_IMPORT_RECEIPT_INDEX_BYTES},
            )
        relative = candidate.relative_to(root).as_posix()
        _, receipt = _load_json_record(root, relative)
        raw_sha256 = receipt.get("raw_artifact_sha256")
        if isinstance(raw_sha256, str) and re.fullmatch(r"[0-9a-f]{64}", raw_sha256):
            index.setdefault(raw_sha256, relative)
    return index


def _verify_raw_artifact_receipt(
    root: Path,
    raw_artifact_sha256: str,
    context: _VerificationContext,
) -> Dict[str, Any]:
    if context.receipt_index is None:
        context.receipt_index = _build_receipt_index(root)
    candidate = context.receipt_index.get(raw_artifact_sha256)
    if candidate is not None:
        return verify_data_import(root, candidate)
    raise Refusal(
        "A generation raw-artifact binding has no independently verifiable import receipt.",
        code="DATA_GENERATION_RAW_BINDING_INVALID",
    )


def _load_delta_ledger_bytes(root: Path, relative_path: str) -> bytes:
    try:
        target = guard_path(root, root / relative_path, must_exist=True)
        if not target.is_file():
            raise OSError("not a regular file")
        if target.stat().st_size > _MAX_DELTA_LEDGER_BYTES:
            raise OSError("ledger exceeds hard byte budget")
        return target.read_bytes()
    except (OSError, Refusal) as exc:
        raise Refusal(
            "The reconciliation delta ledger is missing or unreadable.",
            code="DATA_RECONCILIATION_LEDGER_INVALID",
        ) from exc


def verify_data_generation(
    root: Union[str, Path],
    generation_id: str,
    *,
    _context: Optional[_VerificationContext] = None,
) -> Dict[str, Any]:
    paths = paths_for(root)
    context = _context or _VerificationContext()
    if generation_id in context.active_generation_ids:
        raise Refusal(
            "Data generation lineage contains a cycle.",
            code="DATA_GENERATION_LINEAGE_CYCLE",
            details={"generation_id": generation_id},
        )
    cached = context.completed.get(generation_id)
    if cached is not None:
        return cached
    if context.generation_count >= _MAX_LINEAGE_GENERATIONS:
        raise Refusal(
            "Data generation lineage exceeds the verifier node budget.",
            code="DATA_GENERATION_LINEAGE_BUDGET",
            details={"max_generations": _MAX_LINEAGE_GENERATIONS},
        )
    context.generation_count += 1
    context.active_generation_ids.append(generation_id)
    try:
        result = _verify_data_generation_once(paths.root, generation_id, context)
    finally:
        context.active_generation_ids.pop()
    context.completed[generation_id] = result
    return result


def _verify_data_generation_once(
    root: Path,
    generation_id: str,
    context: _VerificationContext,
) -> Dict[str, Any]:
    """Recompute one generation under a shared bounded lineage context."""

    paths = paths_for(root)
    manifest, records, profile, records_file = _load_generation_records(paths.root, generation_id)
    context.record_work += len(records)
    context.byte_work += int(records_file["size_bytes"])
    if context.record_work > _MAX_LINEAGE_RECORD_WORK or context.byte_work > _MAX_LINEAGE_BYTE_WORK:
        raise Refusal(
            "Data generation lineage exceeds the verifier's cumulative work budget.",
            code="DATA_GENERATION_LINEAGE_BUDGET",
            details={
                "max_record_work": _MAX_LINEAGE_RECORD_WORK,
                "max_byte_work": _MAX_LINEAGE_BYTE_WORK,
            },
        )
    records_bytes, records_sha256, order_sha256, _ = _record_metrics(records)
    decisions = manifest["parser_decisions"]
    expected_id = _generation_id(
        parent_generation_ids=manifest["parent_generation_ids"],
        operation_binding_sha256=manifest["operation_binding_sha256"],
        format_name=manifest["format"],
        decisions=decisions,
        raw_artifact_sha256s=manifest["raw_artifact_sha256s"],
        records_sha256=records_sha256,
        order_sha256=order_sha256,
        record_count=len(records),
        user_confirmed_annotations=manifest["user_confirmed_annotations"],
    )
    checks = {
        "generation_id": expected_id == generation_id,
        "record_count": manifest["record_count"] == len(records),
        "column_count": manifest["column_count"] == len(decisions["columns"]),
        "records_sha256": manifest["records_sha256"] == records_sha256,
        "order_sha256": manifest["order_sha256"] == order_sha256,
        "records_file_sha256": (
            manifest["records_file_sha256"] == records_file["sha256"] == sha256_bytes(records_bytes)
        ),
        "records_file_size": (
            manifest["records_file_size_bytes"] == records_file["size_bytes"] == len(records_bytes)
        ),
        "profile_binding": manifest["profile_sha256"] == profile["record_sha256"],
        "profile_generation": profile["generation_id"] == generation_id,
        "records_path": manifest["records_relative_path"] == _generation_paths(paths.root, generation_id)[1].relative_to(paths.root).as_posix(),
        "profile_path": manifest["profile_relative_path"] == _generation_paths(paths.root, generation_id)[2].relative_to(paths.root).as_posix(),
        "index_path": manifest["derived_index_relative_path"] == _generation_index_path(
            paths.root, generation_id
        ).relative_to(paths.root).as_posix(),
        "index_role": manifest["derived_index_kind"] == "SQLITE_DERIVED_NONAUTHORITATIVE",
    }
    expected_profile = _build_profile(
        generation_id,
        manifest["created_at_utc"],
        manifest["format"],
        records,
        decisions["columns"],
        decisions["header_decision"],
        records_sha256,
        order_sha256,
        manifest["user_confirmed_annotations"],
    )
    checks["profile_recompute"] = expected_profile["record_sha256"] == profile["record_sha256"]
    checks["annotation_binding"] = (
        manifest["user_confirmed_annotations"] == profile["user_confirmed_annotations"]
    )
    derived_index = _verify_generation_index(
        paths.root,
        generation_id,
        records,
        records_sha256,
        order_sha256,
        str(records_file["sha256"]),
        int(records_file["size_bytes"]),
    )
    if len(manifest["raw_artifact_sha256s"]) > _MAX_RAW_ARTIFACTS_PER_GENERATION:
        raise Refusal(
            "Generation raw-artifact lineage exceeds the verifier budget.",
            code="DATA_GENERATION_RAW_BINDING_INVALID",
            details={"max_raw_artifacts": _MAX_RAW_ARTIFACTS_PER_GENERATION},
        )
    raw_verifications = [
        _verify_raw_artifact_receipt(paths.root, str(raw_sha256), context)
        for raw_sha256 in manifest["raw_artifact_sha256s"]
    ]

    if manifest["format"] != "RECONCILED":
        checks["root_parent_lineage"] = manifest["parent_generation_ids"] == []
        checks["root_operation_binding"] = manifest["operation_binding_sha256"] is None
        checks["root_reconciliation_binding"] = manifest["reconciliation_sha256"] is None
        checks["single_raw_artifact"] = len(raw_verifications) == 1
        if len(raw_verifications) == 1:
            raw_verification = raw_verifications[0]
            _, plan = _load_json_record(paths.root, raw_verification["plan_relative_path"])
            _, raw_record = _load_json_record(paths.root, raw_verification["raw_record_relative_path"])
            managed = guard_path(
                paths.root,
                paths.root / raw_verification["managed_relative_path"],
                must_exist=True,
            )
            reparsed = _parse_managed(managed, str(raw_record["format"]), plan["resource_budget"])
            checks["raw_format"] = manifest["format"] == reparsed.format
            checks["raw_parser_decisions"] = decisions == _parser_decisions(
                reparsed.format, reparsed.columns, reparsed.header_decision
            )
            checks["raw_records_reparsed"] = records == reparsed.records

    reconciliation_sha256 = manifest.get("reconciliation_sha256")
    if reconciliation_sha256:
        reconciliation_path = paths.root / DATA_ROOT_RELATIVE / "reconciliations" / (str(reconciliation_sha256) + ".json")
        _, reconciliation = _load_json_record(paths.root, reconciliation_path.relative_to(paths.root).as_posix())
        validate_data_record(reconciliation)
        checks["reconciliation_schema"] = reconciliation.get("schema") == DATA_RECONCILIATION_SCHEMA
        checks["reconciliation_hash"] = reconciliation["record_sha256"] == reconciliation_sha256
        checks["reconciliation_result"] = reconciliation["result_generation_id"] == generation_id
        verify_data_generation(
            paths.root,
            reconciliation["left_generation_id"],
            _context=context,
        )
        verify_data_generation(
            paths.root,
            reconciliation["right_generation_id"],
            _context=context,
        )
        left_manifest, left_records, left_profile, left_file = _load_generation_records(
            paths.root, reconciliation["left_generation_id"]
        )
        right_manifest, right_records, right_profile, right_file = _load_generation_records(
            paths.root, reconciliation["right_generation_id"]
        )
        context.record_work += len(left_records) + len(right_records)
        context.byte_work += int(left_file["size_bytes"]) + int(right_file["size_bytes"])
        if context.record_work > _MAX_LINEAGE_RECORD_WORK or context.byte_work > _MAX_LINEAGE_BYTE_WORK:
            raise Refusal(
                "Data generation lineage exceeds the verifier's cumulative work budget.",
                code="DATA_GENERATION_LINEAGE_BUDGET",
            )
        compatible_key_columns = _compatible_keys(
            left_profile,
            right_profile,
            reconciliation["key_columns"],
        )
        checks["reconciliation_key_columns"] = compatible_key_columns == reconciliation["key_columns"]
        analysis = _delta_analysis(left_records, right_records, compatible_key_columns)
        summary = analysis["summary"]
        checks["reconciliation_summary"] = all(reconciliation[key] == value for key, value in summary.items())
        checks["reconciliation_sources"] = (
            reconciliation["left_records_sha256"] == left_manifest["records_sha256"]
            and reconciliation["right_records_sha256"] == right_manifest["records_sha256"]
        )
        expected_parents = [
            reconciliation["left_generation_id"],
            reconciliation["right_generation_id"],
        ]
        expected_raw_union = sorted(
            set(left_manifest["raw_artifact_sha256s"] + right_manifest["raw_artifact_sha256s"])
        )
        expected_operation_binding = _reconciliation_operation_binding(
            str(reconciliation["left_generation_id"]),
            str(reconciliation["right_generation_id"]),
            str(left_manifest["records_sha256"]),
            str(right_manifest["records_sha256"]),
            compatible_key_columns,
            str(analysis["delta_sha256"]),
        )
        checks["reconciliation_parent_lineage"] = manifest["parent_generation_ids"] == expected_parents
        checks["reconciliation_raw_union"] = manifest["raw_artifact_sha256s"] == expected_raw_union
        checks["reconciliation_operation_binding"] = (
            manifest["operation_binding_sha256"] == expected_operation_binding
        )
        checks["conflicts_preserved"] = reconciliation["preserved_conflict_count"] == reconciliation["conflict_count"]
        checks["all_records_preserved"] = records == left_records + right_records
        checks["reconciliation_result_count"] = reconciliation["result_record_count"] == len(records)
        checks["reconciliation_result_hash"] = reconciliation["result_records_sha256"] == records_sha256
        expected_delta_path = (
            Path(DATA_ROOT_RELATIVE) / "deltas" / (str(analysis["delta_sha256"]) + ".jsonl")
        ).as_posix()
        persisted_delta = _load_delta_ledger_bytes(
            paths.root,
            str(reconciliation["delta_ledger_relative_path"]),
        )
        context.byte_work += len(persisted_delta)
        if context.byte_work > _MAX_LINEAGE_BYTE_WORK:
            raise Refusal(
                "Data generation lineage exceeds the verifier's cumulative byte budget.",
                code="DATA_GENERATION_LINEAGE_BUDGET",
            )
        checks["reconciliation_delta"] = reconciliation["delta_sha256"] == analysis["delta_sha256"]
        checks["delta_ledger_path"] = reconciliation["delta_ledger_relative_path"] == expected_delta_path
        checks["delta_ledger_hash"] = sha256_bytes(persisted_delta) == reconciliation["delta_sha256"]
        checks["delta_ledger_recompute"] = persisted_delta == analysis["ledger_bytes"]
        checks["delta_entry_count"] = reconciliation["delta_entry_count"] == len(analysis["entries"])
    elif manifest["format"] == "RECONCILED":
        checks["reconciliation_required"] = False

    failed = sorted(name for name, passed in checks.items() if not passed)
    if failed:
        raise Refusal(
            "Data generation verification failed.",
            code="DATA_GENERATION_VERIFICATION_FAILED",
            details={"failed_checks": failed},
            repairs=[
                "Preserve the generation and inspect the failed binding checks.",
                "Restore exact managed records from a verified project backup if they changed.",
                "Reinspect or reconcile from independently verified parent artifacts; never edit a generation in place.",
            ],
        )
    return {
        "verified": True,
        "decision": "PASS",
        "generation_id": generation_id,
        "record_count": len(records),
        "column_count": len(decisions["columns"]),
        "records_sha256": records_sha256,
        "order_sha256": order_sha256,
        "manifest": manifest,
        "profile": profile,
        "derived_index": derived_index,
        "gate_0_authority_granted": False,
        "scientific_findings_created": False,
    }


def project_verified_data_generation(
    root: Union[str, Path],
    generation_id: str,
    *,
    columns: Sequence[str],
    row_indices: Sequence[int],
    row_limit: int,
    byte_limit: int,
    redact: bool = False,
) -> Dict[str, Any]:
    """Build one explicit, bounded, read-only projection of verified records.

    This helper grants no readiness or publication authority.  Callers that
    expose records to an AI or analysis path must separately require an exact
    PASS Data Readiness receipt before calling it.
    """

    paths = paths_for(root)
    if not isinstance(row_limit, int) or isinstance(row_limit, bool) or not 1 <= row_limit <= MAX_AI_SURFACE_ROWS:
        raise Refusal(
            "The AI surface row limit is outside the hard safety budget.",
            code="DATA_SURFACE_ROW_BUDGET",
            details={"minimum": 1, "maximum": MAX_AI_SURFACE_ROWS},
        )
    if not isinstance(byte_limit, int) or isinstance(byte_limit, bool) or not 1 <= byte_limit <= MAX_AI_SURFACE_BYTES:
        raise Refusal(
            "The AI surface byte limit is outside the hard safety budget.",
            code="DATA_SURFACE_BYTE_BUDGET",
            details={"minimum": 1, "maximum": MAX_AI_SURFACE_BYTES},
        )
    requested_rows = list(row_indices)
    if not requested_rows:
        raise Refusal(
            "Generation surfaces require explicit zero-based row indices.",
            code="DATA_SURFACE_ROWS_REQUIRED",
            repairs=["Select only the exact rows required for the declared task."],
        )
    if len(requested_rows) > row_limit or len(requested_rows) != len(set(requested_rows)):
        raise Refusal(
            "The explicit row selection is duplicated or exceeds its declared limit.",
            code="DATA_SURFACE_ROW_BUDGET",
        )
    if any(not isinstance(index, int) or isinstance(index, bool) or index < 0 for index in requested_rows):
        raise Refusal("Row indices must be unique nonnegative integers.", code="DATA_SURFACE_ROW_INVALID")

    if not re.fullmatch(r"[0-9a-f]{64}", generation_id):
        raise Refusal("A 64-character generation ID is required.", code="DATA_GENERATION_ID_INVALID")
    manifest_path, records_path, _profile_path = _generation_paths(paths.root, generation_id)
    _, preflight_manifest = _load_json_record(
        paths.root, manifest_path.relative_to(paths.root).as_posix()
    )
    validate_data_record(preflight_manifest)
    records_target = guard_path(paths.root, records_path, must_exist=True)
    records_size = records_target.stat().st_size
    record_count = preflight_manifest.get("record_count")
    if records_size > MAX_AI_SURFACE_SOURCE_BYTES or (
        not isinstance(record_count, int)
        or isinstance(record_count, bool)
        or record_count > MAX_AI_SURFACE_SOURCE_RECORDS
    ):
        raise Refusal(
            "The generation exceeds the bounded work ceiling for an AI surface.",
            code="DATA_SURFACE_SOURCE_BUDGET",
            details={
                "records_file_bytes": records_size,
                "max_source_bytes": MAX_AI_SURFACE_SOURCE_BYTES,
                "record_count": record_count,
                "max_source_records": MAX_AI_SURFACE_SOURCE_RECORDS,
            },
            repairs=[
                "Create a smaller, independently sealed generation for the task.",
                "Use a separately reviewed streaming projection adapter.",
                "Do not raise the ceiling without installed adversity and memory tests.",
            ],
        )

    verify_data_generation(paths.root, generation_id)
    manifest, records, profile, _records_file = _load_generation_records(paths.root, generation_id)
    if any(index >= len(records) for index in requested_rows):
        raise Refusal(
            "A selected row index is outside the verified generation.",
            code="DATA_SURFACE_ROW_INVALID",
            details={"record_count": len(records)},
        )
    column_ids = _resolve_key_columns(profile, columns)
    by_id = {
        str(row["column_id"]): row
        for row in profile["columns"]
        if isinstance(row, Mapping)
    }
    selected_columns = [
        {
            "column_id": column_id,
            "name": by_id[column_id]["name"],
            "position": by_id[column_id]["position"],
            "duplicate_name": by_id[column_id]["duplicate_name"],
        }
        for column_id in column_ids
    ]
    projected: List[Dict[str, Any]] = []
    used = 0
    for index in requested_rows:
        source_record = records[index]
        row: Dict[str, Any] = {
            "source_row_index": index,
            "record_sha256": sha256_text(canonical_json(source_record)),
            "selected_column_ids": column_ids,
        }
        if redact:
            row["values_redacted"] = True
        else:
            row["values"] = {
                column_id: source_record.get(column_id)
                for column_id in column_ids
            }
            row["values_redacted"] = False
        rendered = canonical_json(row).encode("utf-8")
        if used + len(rendered) > byte_limit:
            raise Refusal(
                "The exact requested projection does not fit its declared byte limit.",
                code="DATA_SURFACE_BYTE_BUDGET",
                details={
                    "byte_limit": byte_limit,
                    "bytes_before_row": used,
                    "rejected_row_index": index,
                    "rejected_row_bytes": len(rendered),
                },
                repairs=[
                    "Select fewer rows or columns.",
                    "Use redaction when values are not required for the task.",
                    "Raise the byte limit only within Uriel's one-megabyte hard ceiling.",
                ],
            )
        projected.append(row)
        used += len(rendered)
    return {
        "schema": "uriel.data_projection.v1",
        "generation_id": generation_id,
        "generation_manifest_sha256": manifest["record_sha256"],
        "source_records_sha256": manifest["records_sha256"],
        "source_order_sha256": manifest["order_sha256"],
        "selected_columns": selected_columns,
        "selected_row_indices": requested_rows,
        "row_limit": row_limit,
        "byte_limit": byte_limit,
        "row_count": len(projected),
        "byte_count": used,
        "redacted": bool(redact),
        "records": projected,
        "records_sha256": sha256_text(canonical_json(projected)),
        "no_authority": True,
        "gate_0_authority_granted": False,
        "scientific_findings_created": False,
    }
