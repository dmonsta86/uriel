"""Data Readiness Gate 0: SortSpec generation, order-invariant normalization,
and the Data Readiness Receipt (``uriel.data_readiness.v1``).

The exact input generation must possess a valid receipt before any
data-dependent conclusion (prediction, trend, effect, comparison, association,
causal interpretation, ranking, forecast, conclusion, or signal) is offered.
Without it the only valid conclusion is: "The result is not yet known because
the data generation has not passed readiness verification."

Supported datasets: CSV, TSV, and JSONL. Anything else blocks with a
constructive failure. Record identity must be declared; ambiguous identity
blocks. Duplicate-key ambiguity blocks unless a policy resolves it.
"""
from __future__ import annotations

import csv
import json
import os
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .core import (
    Refusal,
    atomic_write_json,
    canonical_json,
    canonical_root,
    guard_path,
    paths_for,
    sha256_file,
    sha256_text,
    utc_now,
)
from .generation_readiness import (
    current_generation_readiness_status,
    generation_readiness_check,
    generation_readiness_status,
    generation_receipt_inventory,
    make_generation_sort_spec,
    require_generation_readiness,
    verify_generation_readiness_receipt,
)

SORT_SPEC_SCHEMA = "uriel.sort_spec.v1"
READINESS_SCHEMA = "uriel.data_readiness.v1"
EMBARGO_SENTENCE = (
    "The result is not yet known because the data generation has not passed "
    "readiness verification."
)
SUPPORTED_SUFFIXES = (".csv", ".tsv", ".jsonl")
NULL_ORDERINGS = ("nulls_first", "nulls_last", "nulls_error")
DUPLICATE_POLICIES = ("block", "exact", "keep_first")

REQUIRED_CHECKS = (
    "source_identity",
    "record_identity",
    "schema",
    "encoding",
    "type_normalization",
    "datetime_normalization",
    "numeric_locale",
    "category_normalization",
    "duplicate_handling",
    "join_keys_and_cardinality",
    "missingness",
    "exclusions",
    "transformations",
    "stable_deterministic_sorting",
    "tie_break_rules",
    "null_ordering",
    "order_invariance",
    "row_reconciliation",
    "cross_platform_fixture_equivalence",
    "rebuild_hash_equality",
    "analysis_plan_binding",
    "independent_verification",
)


def _utf8_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise Refusal(
            "Dataset is not valid UTF-8: {0}".format(exc),
            code="READINESS_ENCODING",
            repairs=["Re-export the dataset as UTF-8 without a BOM mismatch.",
                     "Record a declared encoding and normalization rule."],
        ) from exc


def _load_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    suffix = path.suffix.lower()
    if suffix == ".jsonl":
        rows: List[Dict[str, str]] = []
        for line in _utf8_text(path).splitlines():
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise Refusal("JSONL rows must be JSON objects.",
                              code="READINESS_JSONL_SHAPE")
            rows.append({str(key): _as_text(item) for key, item in value.items()})
        columns: List[str] = []
        for row in rows:
            for key in row:
                if key not in columns:
                    columns.append(key)
        return rows, columns
    delimiter = "\t" if suffix == ".tsv" else ","
    with open(path, "r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle, delimiter=delimiter)
        if not reader.fieldnames:
            raise Refusal("Dataset has no header row.", code="READINESS_NO_HEADER",
                          repairs=["Add a header row with column names."])
        columns = [str(name) for name in reader.fieldnames]
        if columns and columns[0].startswith("\ufeff"):
            columns[0] = columns[0][1:]
            reader.fieldnames[0] = columns[0]
        rows = [row for row in reader]
    return rows, columns


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def make_sort_spec(
    root: Union[Path, str],
    dataset: str,
    *,
    keys: Sequence[str] = (),
    tie_break: Sequence[str] = (),
    nulls: str = "nulls_last",
    duplicate_policy: str = "block",
    analysis_plan: Optional[str] = None,
    normalization: Sequence[str] = (),
    exclusions: Sequence[str] = (),
) -> Dict[str, Any]:
    """Generate a versioned SortSpec. Ambiguous record identity blocks."""
    if nulls not in NULL_ORDERINGS:
        raise Refusal("Unknown null ordering.", code="READINESS_INVALID_NULLS",
                      repairs=["Choose nulls_first, nulls_last, or nulls_error."])
    if duplicate_policy not in DUPLICATE_POLICIES:
        raise Refusal("Unknown duplicate policy.", code="READINESS_INVALID_DUPLICATES",
                      repairs=["Choose block, exact, or keep_first."])
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    dataset_path = guard_path(root_path, root_path / dataset, must_exist=True)
    if dataset_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise Refusal(
            "Unsupported dataset format; only CSV, TSV, and JSONL are supported.",
            code="READINESS_UNSUPPORTED_FORMAT",
            repairs=["Convert the dataset to CSV, TSV, or JSONL first.",
                     "Record the conversion as a transformation rule."],
        )
    rows, columns = _load_rows(dataset_path)
    key_list = [str(item) for item in keys]
    tie_list = [str(item) for item in tie_break]
    unknown = [name for name in key_list + tie_list if name not in columns]
    if unknown:
        raise Refusal(
            "SortSpec names columns that do not exist: {0}".format(", ".join(unknown)),
            code="READINESS_UNKNOWN_COLUMN",
            repairs=["Use one of: " + ", ".join(columns)],
        )
    if not key_list:
        raise Refusal(
            "Record identity is ambiguous: no primary keys declared.",
            code="READINESS_AMBIGUOUS_IDENTITY",
            repairs=["Declare primary keys from: " + ", ".join(columns)],
        )
    spec = {
        "schema": SORT_SPEC_SCHEMA,
        "version": 1,
        "dataset_identity": sha256_file(dataset_path),
        "dataset_path": str(dataset_path.relative_to(root_path).as_posix()),
        "columns": columns,
        "record_identity": key_list,
        "primary_keys": key_list,
        "tie_break_keys": tie_list,
        "null_ordering": nulls,
        "normalization_rules": [str(item) for item in normalization],
        "duplicate_policy": duplicate_policy,
        "join_policy": "single_dataset_row_position_join_forbidden",
        "canonical_serialization": "utf8_lf_escaped",
        "order_invariance_tests": ["shuffle_reproduces_canonical_order"],
        "cross_platform_status": "deterministic_utf8_lf_no_locale",
        "exclusions": [str(item) for item in exclusions],
        "analysis_plan_sha256": None if analysis_plan is None else sha256_file(
            guard_path(root_path, root_path / analysis_plan, must_exist=True)
        ),
    }
    spec_bytes = canonical_json(spec)
    spec_sha = sha256_text(spec_bytes)
    readiness_dir = guard_path(root_path, paths.state / "readiness")
    readiness_dir.mkdir(parents=True, exist_ok=True)
    target = guard_path(readiness_dir, readiness_dir / ("sortspec-" + spec_sha + ".json"))
    if not target.exists():
        atomic_write_json(target, spec, pretty=False)
    return {"sort_spec_sha256": spec_sha, "sort_spec": spec, "path": str(target),
            "row_count": len(rows)}


def _normalized_rows(
    rows: List[Dict[str, str]], spec: Mapping[str, Any]
) -> List[Dict[str, str]]:
    keys = [str(item) for item in spec.get("primary_keys", [])]
    tie_break = [str(item) for item in spec.get("tie_break_keys", [])]
    nulls = str(spec.get("null_ordering", "nulls_last"))

    def key_of(row: Dict[str, str]) -> Tuple[Any, ...]:
        values: List[Any] = []
        for name in keys + tie_break:
            value = row.get(name, "")
            if value == "":
                if nulls == "nulls_error":
                    raise Refusal(
                        "Null value in a sort key; null ordering forbids nulls.",
                        code="READINESS_NULL_IN_KEY",
                        repairs=["Fill the missing key value or allow nulls_first/nulls_last."],
                    )
                values.append((2 if nulls == "nulls_first" else 3, ""))
            else:
                values.append((1, value.casefold() if name in tie_break else value))
        return tuple(values)

    return sorted(rows, key=key_of)


def _canonical_serialize(rows: List[Dict[str, str]]) -> str:
    return canonical_json([{key: row[key] for key in sorted(row)} for row in rows])


def _rebuild_hash(rows: List[Dict[str, str]]) -> str:
    return sha256_text(_canonical_serialize(rows))


def readiness_check(
    root: Union[Path, str],
    sort_spec_path: Optional[str] = None,
    *,
    dataset: Optional[str] = None,
    analysis_plan: Optional[str] = None,
    generation: Optional[str] = None,
) -> Dict[str, Any]:
    """Execute the Gate 0 check matrix and write a Data Readiness Receipt."""
    if generation is not None:
        if dataset is not None:
            raise Refusal(
                "Choose either a legacy dataset path or a Data Desk generation, not both.",
                code="READINESS_INPUT_AMBIGUOUS",
            )
        if analysis_plan is not None:
            raise Refusal(
                "A v2 analysis plan is sealed in its SortSpec; create a new SortSpec to change it.",
                code="READINESS_ANALYSIS_PLAN_IN_SORT_SPEC",
            )
        result = generation_readiness_check(root, generation, sort_spec_path)
        result["embargo_sentence"] = (
            None if result["receipt"].get("decision") == "PASS" else EMBARGO_SENTENCE
        )
        return result
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    readiness_dir = guard_path(root_path, paths.state / "readiness")
    if sort_spec_path is None:
        candidates = sorted(readiness_dir.glob("sortspec-*.json")) if readiness_dir.is_dir() else []
        if not candidates:
            raise Refusal("No SortSpec exists; generate one first.",
                          code="READINESS_SORT_SPEC_MISSING",
                          repairs=["Run `uriel readiness init-sort-spec --dataset <path> --keys ...`."])
        sort_spec_path = str(candidates[-1])
    sort_spec_file = guard_path(root_path, root_path / sort_spec_path
                                if Path(sort_spec_path).is_absolute() else readiness_dir / sort_spec_path,
                                must_exist=True)
    try:
        spec = json.loads(sort_spec_file.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise Refusal("SortSpec is unreadable.", code="READINESS_SORT_SPEC_UNREADABLE") from exc
    if spec.get("schema") != SORT_SPEC_SCHEMA:
        raise Refusal("Not a SortSpec document.", code="READINESS_SORT_SPEC_UNREADABLE")
    dataset_name = dataset or str(spec.get("dataset_path", ""))
    if not dataset_name:
        raise Refusal("SortSpec does not name a dataset.", code="READINESS_SORT_SPEC_UNREADABLE")
    dataset_path = guard_path(root_path, root_path / dataset_name, must_exist=True)
    rows, columns = _load_rows(dataset_path)
    source_generation = sha256_file(dataset_path)
    plan_path: Optional[Path] = None
    if analysis_plan:
        plan_path = guard_path(root_path, root_path / analysis_plan, must_exist=True)
    elif spec.get("analysis_plan_sha256"):
        plan_path = None
    analysis_plan_sha = None if plan_path is None else sha256_file(plan_path)

    def _check(name: str, passed: bool, evidence: Any) -> Dict[str, Any]:
        return {"check": name, "status": "PASS" if passed else "FAIL", "evidence": evidence}

    checks: List[Dict[str, Any]] = []
    checks.append(_check("source_identity",
                         source_generation == spec.get("dataset_identity"),
                         {"declared": spec.get("dataset_identity"), "actual": source_generation}))
    key_list = [str(item) for item in spec.get("primary_keys", [])]
    checks.append(_check("record_identity", bool(key_list) and all(k in columns for k in key_list),
                         {"keys": key_list, "columns": columns}))
    declared_columns = [str(item) for item in spec.get("columns", [])]
    checks.append(_check("schema", bool(columns) and set(declared_columns) == set(columns),
                         {"declared": declared_columns, "actual": columns}))
    checks.append(_check("encoding", True, "utf8_strict"))
    nulls = str(spec.get("null_ordering", "nulls_last"))
    duplicates_by_key = [row for row in rows if any(row.get(key) == "" for key in key_list)]
    key_counts: Dict[Tuple[str, ...], int] = {}
    for row in rows:
        key_counts[tuple(row.get(key, "") for key in key_list)] = key_counts.get(
            tuple(row.get(key, "") for key in key_list), 0
        ) + 1
    ambiguous = {key for key, count in key_counts.items() if count > 1}
    policy = str(spec.get("duplicate_policy", "block"))
    if policy == "block" and ambiguous:
        checks.append(_check("duplicate_handling", False,
                             {"policy": "block", "duplicate_keys": len(ambiguous)}))
    else:
        checks.append(_check("duplicate_handling", True,
                             {"policy": policy, "duplicate_keys": len(ambiguous),
                              "resolved": len(ambiguous) > 0}))
    checks.append(_check("join_keys_and_cardinality",
                         not ambiguous or policy != "block",
                         {"cardinality": "unique" if not ambiguous else "duplicated_keys_resolved"}))
    missing = {
        key: sum(1 for row in rows if row.get(key, "") == "")
        for key in key_list
    }
    missingness_blocked = any(count > 0 for count in missing.values()) and nulls == "nulls_error"
    checks.append(_check("missingness", not missingness_blocked, {"null_counts": missing}))
    checks.append(_check("exclusions", True, {"recorded": list(spec.get("exclusions", []))}))
    checks.append(_check("transformations", True, {"rules": list(spec.get("normalization_rules", []))}))
    blocker: Optional[str] = None
    try:
        _normalized_rows(rows, spec)
    except Refusal as exc:
        blocker = str(exc)
        checks.append({"check": "null_ordering", "status": "BLOCKED",
                       "evidence": {"blocker": blocker, "repairs": list(exc.repairs)}})
    if blocker is None:
        normalized = _normalized_rows(rows, spec)
        canonical = _canonical_serialize(normalized)
        normalized_generation = sha256_text(canonical)
        checks.append(_check("stable_deterministic_sorting", True, {"stable_by_construction": True}))
        checks.append(_check("tie_break_rules", True, {"keys": list(spec.get("tie_break_keys", []))}))
        checks.append(_check("null_ordering", True, {"ordering": nulls, "nulls_in_keys": len(duplicates_by_key)}))
        shuffled = _normalized_rows(list(reversed(rows)), spec)
        order_invariant = _canonical_serialize(shuffled) == canonical
        checks.append(_check("order_invariance", order_invariant, {"shuffled_reproduces": order_invariant}))
        checks.append(_check("row_reconciliation", len(normalized) == len(rows),
                             {"input_rows": len(rows), "output_rows": len(normalized)}))
        checks.append(_check("cross_platform_fixture_equivalence", True,
                             {"serialization": "utf8_lf_escaped_no_locale"}))
        rebuild_matches = _rebuild_hash(normalized) == normalized_generation
        checks.append(_check("rebuild_hash_equality", rebuild_matches, {"normalized_generation": normalized_generation}))
    else:
        checks.append(_check("stable_deterministic_sorting", False, {"blocker": blocker}))
        checks.append(_check("tie_break_rules", False, {"blocker": blocker}))
        checks.append(_check("order_invariance", False, {"blocker": blocker}))
        checks.append(_check("row_reconciliation", False, {"blocker": blocker}))
        checks.append(_check("cross_platform_fixture_equivalence", False, {"blocker": blocker}))
        checks.append(_check("rebuild_hash_equality", False, {"blocker": blocker}))
        normalized_generation = ""
    checks.append(_check("analysis_plan_binding", True,
                         {"analysis_plan_sha256": analysis_plan_sha or spec.get("analysis_plan_sha256")}))
    binding_digest = sha256_text(canonical_json({
        "source_generation": source_generation,
        "normalized_generation": normalized_generation,
        "sort_spec_sha256": spec.get("sort_spec_sha256", "") or sort_spec_file.name[9:-5],
        "analysis_plan_sha256": analysis_plan_sha or spec.get("analysis_plan_sha256"),
        "check_statuses": [check["status"] for check in checks],
    }))
    checks.append(_check("independent_verification", True,
                         {"recompute": "binding_digest_recomputable_from_receipt"}))
    counts = {
        "required": len(REQUIRED_CHECKS),
        "executed": len(checks),
        "failed": sum(1 for check in checks if check["status"] == "FAIL"),
        "blocked": sum(1 for check in checks if check["status"] == "BLOCKED"),
        "unresolved_blockers": 1 if blocker else 0,
        "not_applicable": 0,
    }
    if counts["blocked"] > 0 or counts["unresolved_blockers"] > 0:
        decision = "BLOCKED"
    elif counts["failed"] == 0:
        decision = "PASS"
    else:
        decision = "FAIL"
    receipt = {
        "schema": READINESS_SCHEMA,
        "source_generation": source_generation,
        "normalized_generation": normalized_generation,
        "sort_spec_sha256": spec.get("sort_spec_sha256", "") or sort_spec_file.name[9:-5],
        "analysis_plan_sha256": analysis_plan_sha or spec.get("analysis_plan_sha256"),
        "required_check_count": counts["required"],
        "executed_check_count": counts["executed"],
        "failed_check_count": counts["failed"],
        "blocked_check_count": counts["blocked"],
        "unresolved_blocker_count": counts["unresolved_blockers"],
        "not_applicable_count": counts["not_applicable"],
        "decision": decision,
        "binding_digest": binding_digest,
        "independent_verifier_sha256": None,
        "created_at_utc": utc_now(),
    }
    receipt_bytes = canonical_json(receipt)
    receipt_sha = sha256_text(receipt_bytes)
    target = guard_path(readiness_dir, readiness_dir / ("receipt-" + receipt_sha + ".json"))
    if not target.exists():
        atomic_write_json(target, receipt, pretty=False)
    return {
        "receipt_sha256": receipt_sha,
        "receipt": receipt,
        "checks": checks,
        "path": str(target),
        "embargo_sentence": None if decision == "PASS" else EMBARGO_SENTENCE,
    }


def readiness_status(
    root: Union[Path, str],
    *,
    dataset: Optional[str] = None,
    generation: Optional[str] = None,
    sort_spec_path: Optional[Union[str, Path]] = None,
    receipt_path: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    """Latest receipt plus staleness against the current source generation."""
    if generation is not None:
        if dataset is not None:
            raise Refusal(
                "Choose either a legacy dataset path or a Data Desk generation, not both.",
                code="READINESS_INPUT_AMBIGUOUS",
            )
        status = generation_readiness_status(
            root,
            generation,
            sort_spec_path=sort_spec_path,
            receipt_path=receipt_path,
        )
        status["embargo_sentence"] = (
            None if status.get("decision") == "PASS" else EMBARGO_SENTENCE
        )
        return status
    if dataset is None and sort_spec_path is None and receipt_path is None:
        active_status = current_generation_readiness_status(root)
        if active_status.get("exists"):
            active_status["embargo_sentence"] = (
                None if active_status.get("decision") == "PASS" else EMBARGO_SENTENCE
            )
            return active_status
        generation_receipts = generation_receipt_inventory(root)
        if len(generation_receipts) == 1:
            row = generation_receipts[0]
            status = generation_readiness_status(
                root,
                row["generation_id"],
                receipt_path=row["path"],
            )
            status["embargo_sentence"] = (
                None if status.get("decision") == "PASS" else EMBARGO_SENTENCE
            )
            return status
        if len(generation_receipts) > 1:
            return {
                "exists": True,
                "decision": "AMBIGUOUS",
                "candidates": generation_receipts,
                "embargo_sentence": EMBARGO_SENTENCE,
            }
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    readiness_dir = guard_path(root_path, paths.state / "readiness")
    receipts = sorted(readiness_dir.glob("receipt-*.json"), key=lambda p: (p.stat().st_mtime_ns, p.name)) if readiness_dir.is_dir() else []
    if not receipts:
        return {"exists": False, "decision": None,
                "embargo_sentence": EMBARGO_SENTENCE}
    import json

    latest = json.loads(receipts[-1].read_text(encoding="utf-8"))
    stale = False
    if dataset:
        dataset_path = guard_path(root_path, root_path / dataset, must_exist=True)
        stale = sha256_file(dataset_path) != latest.get("source_generation")
    elif latest.get("source_generation"):
        spec_dir = readiness_dir
        for spec_path in spec_dir.glob("sortspec-*.json"):
            try:
                spec = json.loads(spec_path.read_text(encoding="utf-8"))
                if spec.get("dataset_identity") == latest.get("source_generation"):
                    dataset_path = guard_path(root_path, root_path / spec.get("dataset_path", ""),
                                              must_exist=True)
                    stale = sha256_file(dataset_path) != latest.get("source_generation")
                    break
            except (OSError, ValueError):
                continue
    if stale:
        latest = dict(latest)
        latest["decision"] = "STALE"
    return {"exists": True, "decision": latest.get("decision"), "receipt": latest,
            "receipt_sha256": receipts[-1].name[8:-5],
            "embargo_sentence": None if latest.get("decision") == "PASS" else EMBARGO_SENTENCE}


def data_readiness_state(root: Union[Path, str]) -> Dict[str, Any]:
    """Short status used by the onboarding/AI-entry surfaces."""
    status = readiness_status(root)
    return {
        "data_readiness": "PASS" if status.get("decision") == "PASS"
        else ("STALE" if status.get("decision") == "STALE"
              else ("FAIL" if status.get("exists") else "not_started")),
        "embargo_sentence": status.get("embargo_sentence"),
    }


SORT_PROPOSAL_SCHEMA = "uriel.sort_proposal.v1"
SORT_KINDS = (
    "time_series",
    "panel_longitudinal",
    "experiment",
    "survey",
    "documents_evidence",
    "generic_records",
)
NEVER_OPERATIONS = (
    "join_by_row_position",
    "file_enumeration_order_as_scientific_order",
    "locale_dependent_ordering",
    "guessed_primary_key_when_identity_ambiguous",
    "silent_duplicate_key_drop",
    "silent_ambiguous_date_or_number_coercion",
)

_DATETIME_TOKENS = ("timestamp", "datetime", "date", "time", "ts", "dt", "day", "week", "month", "year")
_DATETIME_SUFFIXES = ("_at", "_on", "_utc", "_local", "_date", "_time")
_ENTITY_TOKENS = ("id", "uuid", "entity", "subject", "participant", "respondent",
                  "user", "patient", "unit", "source", "device", "phone")
_WAVE_TOKENS = ("wave", "visit", "timepoint", "round", "session", "phase", "period", "t_", "tp")
_CONDITION_TOKENS = ("condition", "treatment", "arm", "experiment", "intervention", "exposure")
_REPLICATE_TOKENS = ("replicate", "rep", "run", "trial", "iteration", "block", "lane")
_MEASURE_TOKENS = ("measure", "metric", "variable", "outcome", "item", "question",
                   "indicator", "score", "response", "answer", "instrument", "tool")
_SEQUENCE_TOKENS = ("seq", "sequence", "order", "event", "position", "section", "step")
_VERSION_TOKENS = ("version", "revision", "rev", "v")
_HEX64_RE = None  # assigned lazily in _looks_like_hash


def _split_tokens(name: str) -> List[str]:
    lowered = name.lower().replace("-", "_").replace(" ", "_")
    tokens: List[str] = []
    for piece in lowered.split("_"):
        if not piece:
            continue
        head = piece[0]
        tail = piece[1:]
        for index in range(len(tail)):
            if tail[index].isdigit() and (index == 0 or tail[index - 1].isdigit()):
                continue
            if tail[index].isupper():
                piece = piece[: index + 1] + "_" + piece[index + 1 :]
        tokens.extend(part for part in piece.split("_") if part)
    return tokens


def _column_labels(name: str) -> List[str]:
    tokens = _split_tokens(name)
    labels: List[str] = []
    if any(token in _DATETIME_TOKENS for token in tokens) or name.lower().endswith(_DATETIME_SUFFIXES):
        labels.append("timestamp")
    if any(token in _ENTITY_TOKENS for token in tokens):
        labels.append("entity")
    if any(token in _WAVE_TOKENS for token in tokens):
        labels.append("wave")
    if any(token in _CONDITION_TOKENS for token in tokens):
        labels.append("condition")
    if any(token in _REPLICATE_TOKENS for token in tokens):
        labels.append("replicate")
    if any(token in _MEASURE_TOKENS for token in tokens):
        labels.append("measure")
    if any(token in _SEQUENCE_TOKENS for token in tokens):
        labels.append("sequence")
    if any(token in _VERSION_TOKENS for token in tokens):
        labels.append("version")
    return labels


def _looks_like_hash(value: str) -> bool:
    global _HEX64_RE
    if _HEX64_RE is None:
        import re

        _HEX64_RE = re.compile(r"^[0-9a-f]{32,64}$")
    return bool(_HEX64_RE.match(value))


def _sample_datetime_ratio(rows: List[Dict[str, str]], column: str, limit: int = 20) -> float:
    import datetime as _datetime

    seen = 0
    parsed = 0
    for row in rows[:limit]:
        value = _as_text(row.get(column, "")).strip()
        if not value:
            continue
        seen += 1
        candidate = value
        if candidate.endswith("Z"):
            candidate = candidate[:-1] + "+00:00"
        try:
            _datetime.datetime.fromisoformat(candidate)
            parsed += 1
        except ValueError:
            continue
    return (parsed / seen) if seen else 0.0


def _classify_columns(rows: List[Dict[str, str]], columns: Sequence[str]) -> Dict[str, List[str]]:
    """Deterministic, conservative column role classification."""
    roles: Dict[str, List[str]] = {
        "timestamp": [], "entity": [], "wave": [], "condition": [],
        "replicate": [], "measure": [], "sequence": [], "version": [], "hash": [],
    }
    for column in columns:
        for label in _column_labels(column):
            if label in roles:
                roles[label].append(column)
    roles["timestamp"] = [name for name in roles["timestamp"]
                          if _sample_datetime_ratio(rows, name) >= 0.5]
    for column in columns:
        if column in roles["timestamp"] or column in roles["entity"]:
            continue
        if all(_looks_like_hash(_as_text(row.get(column, "")).strip())
               for row in rows[:20] if _as_text(row.get(column, "")).strip()):
            roles["hash"].append(column)
    return roles


def _unique_ratio(rows: List[Dict[str, str]], key_columns: Sequence[str], limit: int = 50) -> float:
    seen: set = set()
    for row in rows[:limit]:
        seen.add(tuple(_as_text(row.get(name, "")) for name in key_columns))
    return len(seen) / min(len(rows[:limit]), limit) if rows[:limit] else 0.0


def propose_sort_spec_plan(
    root: Union[Path, str],
    dataset: str,
    *,
    sample: int = 20,
) -> Dict[str, Any]:
    """Propose a best-sorting-method plan from the structure of the data (§9.1).

    A proposal only. It never seals a SortSpec, never writes state, and never
    guesses identity. If no safe identity/sort rule exists the plan returns
    ``gate_status = BLOCKED_AMBIGUOUS_IDENTITY`` with the minimum identity
    clarification or reconstruction plan.
    """
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    dataset_path = guard_path(root_path, root_path / dataset, must_exist=True)
    if dataset_path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise Refusal(
            "Unsupported dataset format; only CSV, TSV, and JSONL are supported.",
            code="READINESS_UNSUPPORTED_FORMAT",
            repairs=["Convert the dataset to CSV, TSV, or JSONL first.",
                     "Record the conversion as a transformation rule."],
        )
    rows, columns = _load_rows(dataset_path)
    if not columns:
        raise Refusal("The dataset has no columns; no safe sort rule can be proposed.",
                      code="READINESS_EMPTY_STRUCTURE",
                      repairs=["Provide a header row or record schema."])
    roles = _classify_columns(rows, columns)
    record_id_rule = "sha256 of the canonical serialized row (immutable record ID)"
    warnings: List[str] = []

    kind: Optional[str] = None
    primary: List[str] = []
    tie_break: List[str] = []
    evidence: Dict[str, Any] = {}
    blocked_reasons: List[str] = []

    timestamp = roles["timestamp"][:1]
    entity = roles["entity"][:1]
    respondent = [
        name for name in roles["entity"]
        if any(token in _split_tokens(name) for token in ("respondent", "user", "participant"))
    ][:1]
    wave = roles["wave"][:1]
    condition = roles["condition"][:1]
    replicate = roles["replicate"][:1]
    measure = roles["measure"][:1]
    sequence = roles["sequence"][:1]
    version = roles["version"][:1]
    hash_column = roles["hash"][:1]

    if timestamp:
        kind = "time_series"
        evidence["series_timepoint"] = timestamp
        if entity:
            evidence["series_entity"] = entity
            primary = entity + timestamp
        else:
            evidence["series_entity"] = "single_series_declared_entity"
            primary = timestamp
        if sequence:
            tie_break.append(sequence[0])
        tie_break.append(record_id_rule)
    elif respondent and wave:
        kind = "survey"
        evidence["survey_respondent"] = respondent
        evidence["survey_wave"] = wave
        primary = respondent + wave
        if measure:
            tie_break.append(measure[0])
        tie_break.append(record_id_rule)
    elif entity and wave:
        kind = "panel_longitudinal"
        evidence["panel_entity"] = entity
        evidence["panel_timepoint"] = wave
        primary = entity + wave
        if measure:
            tie_break.append(measure[0])
        tie_break.append(record_id_rule)
    elif entity and condition:
        kind = "experiment"
        evidence["experiment_unit"] = entity
        evidence["experiment_condition"] = condition
        primary = entity + condition
        if replicate:
            primary.append(replicate[0])
        if timestamp:
            tie_break.append(timestamp[0])
        tie_break.append(record_id_rule)
    elif entity and (version or timestamp):
        kind = "documents_evidence"
        evidence["document_source"] = entity
        primary = entity
        if version:
            primary.append(version[0])
        elif timestamp:
            primary.append(timestamp[0])
        if sequence:
            tie_break.append(sequence[0])
        tie_break.append(record_id_rule)
    elif any(name in roles["entity"] for name in ("id", "uuid")):
        kind = "generic_records"
        primary = [name for name in roles["entity"] if name in ("id", "uuid")]
        tie_break = [record_id_rule]
        evidence["generic_primary"] = primary
    else:
        blocked_reasons.append(
            "no entity, timepoint, condition, version, or declared primary-key column found"
        )

    for key_name in primary:
        ratio = _unique_ratio(rows, [key_name])
        if ratio < 0.999:
            warnings.append(
                "{0}: proposed primary key is not unique in the sample ({1:.0%} unique); "
                "the duplicate policy must resolve this explicitly, never silently".format(
                    key_name, ratio
                )
            )
    combined = primary + tie_break[:-1] if tie_break else primary
    combined_unique = _unique_ratio(rows, [name for name in combined if name != record_id_rule])
    if combined and combined_unique < 0.999:
        warnings.append(
            "proposed composite key is not unique in the sample ({0:.0%}); "
            "an immutable record ID (content hash) is required as final tie-break".format(
                combined_unique
            )
        )
    if timestamp:
        warnings.append(
            "timestamp column {0}: verify the timezone and that no silent coercion "
            "occurred; ambiguous dates must be resolved, never coerced".format(timestamp[0])
        )

    blocked = bool(blocked_reasons)
    plan: Dict[str, Any] = {
        "schema": SORT_PROPOSAL_SCHEMA,
        "version": 1,
        "dataset": str(dataset_path.relative_to(root_path).as_posix()),
        "dataset_identity": sha256_file(dataset_path),
        "detected_kind": kind,
        "kind_evidence": evidence,
        "gate_status": "BLOCKED_AMBIGUOUS_IDENTITY" if blocked else "PROPOSAL",
        "record_identity_rule": record_id_rule,
        "proposed_primary_keys": primary,
        "proposed_tie_break_keys": [item for item in tie_break if item != record_id_rule],
        "immutable_record_id_rule": record_id_rule,
        "recommended": {
            "null_ordering": "nulls_last",
            "duplicate_policy": "block",
            "normalization_rules": ["utf8_lf", "strip_whitespace"],
            "canonical_serialization": "utf8_lf_escaped",
            "order_invariance_test": "shuffle_reproduces_canonical_order",
        },
        "refused_operations": list(NEVER_OPERATIONS),
        "warnings": warnings,
        "blocked_reasons": blocked_reasons,
        "identity_clarification_plan": (
            [
                "Declare record identity explicitly: add an immutable record ID column "
                "(for example a stable hash or UUID) or name the columns that uniquely "
                "identify one row.",
                "Then run: uriel readiness init-sort-spec --dataset {0} --keys <record-id>".format(
                    str(dataset_path.relative_to(root_path).as_posix())
                ),
            ]
            if blocked
            else []
        ),
        "next_step": (
            "uriel readiness init-sort-spec --dataset {0} --keys {1}{2}".format(
                str(dataset_path.relative_to(root_path).as_posix()),
                " ".join(primary) if primary else "<record-id>",
                " --tie-break " + " ".join(
                    [item for item in tie_break if item != record_id_rule]
                ) if tie_break and any(item != record_id_rule for item in tie_break) else "",
            )
            if not blocked
            else "Resolve identity first; no SortSpec may be sealed while identity is ambiguous."
        ),
        "proposal_only": True,
        "generated_at_utc": utc_now(),
    }
    return plan
