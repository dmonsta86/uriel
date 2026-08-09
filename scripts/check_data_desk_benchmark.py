#!/usr/bin/env python3
"""Validate the tracked Data Desk measurement without inventing performance."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Mapping

from benchmark_data_desk import (
    BENCHMARK_ID,
    CLAIM_BOUNDARY,
    COLUMN_COUNT,
    ROW_COUNT,
    fixture_bytes,
    implementation_binding,
)


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "benchmarks" / "data_desk" / "synthetic-tabular-10000-v1.json"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TIMING_KEYS = {"plan_ms", "import_ms", "inspect_ms", "verify_ms", "repeat_inspect_ms"}
_TOP_LEVEL_KEYS = {
    "schema",
    "schema_version",
    "benchmark_id",
    "measured_at_utc",
    "uriel_version",
    "runtime",
    "fixture",
    "implementation",
    "operations_ms",
    "peak_traced_python_bytes",
    "result",
    "claim_boundary",
}


def validate_receipt(repository: Path, value: Mapping[str, Any]) -> Dict[str, Any]:
    errors = []
    if set(value) != _TOP_LEVEL_KEYS:
        errors.append("top-level receipt membership mismatch")
    if value.get("schema") != "uriel.data_desk_benchmark_receipt.v1" or value.get("schema_version") != 1:
        errors.append("schema/version mismatch")
    if value.get("benchmark_id") != BENCHMARK_ID:
        errors.append("benchmark ID mismatch")
    try:
        measured = datetime.fromisoformat(str(value.get("measured_at_utc", "")).replace("Z", "+00:00"))
        if measured.tzinfo is None:
            raise ValueError("timezone missing")
    except ValueError:
        errors.append("measurement timestamp is not timezone-aware ISO-8601")

    payload = fixture_bytes()
    fixture = value.get("fixture")
    expected_fixture = {
        "kind": "deterministic synthetic CSV",
        "rows": ROW_COUNT,
        "columns": COLUMN_COUNT,
        "bytes": len(payload),
        "sha256": hashlib.sha256(payload).hexdigest(),
    }
    if fixture != expected_fixture:
        errors.append("fixture identity mismatch")
    if value.get("implementation") != implementation_binding(repository):
        errors.append("implementation binding mismatch")

    timings = value.get("operations_ms")
    if not isinstance(timings, Mapping) or set(timings) != _TIMING_KEYS:
        errors.append("operation timing membership mismatch")
    elif any(
        not isinstance(timing, (int, float))
        or isinstance(timing, bool)
        or timing <= 0
        or timing > 600_000
        for timing in timings.values()
    ):
        errors.append("operation timing is outside the receipt sanity bounds")
    peak = value.get("peak_traced_python_bytes")
    if not isinstance(peak, int) or isinstance(peak, bool) or peak <= 0:
        errors.append("peak traced Python bytes must be a positive observation")

    result = value.get("result")
    if not isinstance(result, Mapping):
        errors.append("result is not an object")
    elif (
        result.get("record_count") != ROW_COUNT
        or result.get("verification_decision") != "PASS"
        or result.get("deterministic_repeat") is not True
        or not isinstance(result.get("generation_id"), str)
        or _HEX64.fullmatch(str(result.get("generation_id"))) is None
    ):
        errors.append("benchmark result is incomplete or invalid")
    if value.get("claim_boundary") != CLAIM_BOUNDARY:
        errors.append("claim boundary mismatch")
    if not isinstance(value.get("uriel_version"), str) or not value.get("uriel_version", "").strip():
        errors.append("Uriel version must be a nonempty string")

    runtime = value.get("runtime")
    if not isinstance(runtime, Mapping) or set(runtime) != {"python", "platform", "architecture"}:
        errors.append("runtime description mismatch")
    elif any(not isinstance(item, str) or not item.strip() for item in runtime.values()):
        errors.append("runtime fields must be nonempty strings")

    serialized = json.dumps(value, ensure_ascii=False, sort_keys=True)
    if re.search(r"(?i)(?:[a-z]:\\|/home/|/users/|\\users\\)", serialized):
        errors.append("receipt contains a local user path")
    return {
        "verified": not errors,
        "errors": errors,
        "benchmark_id": value.get("benchmark_id"),
        "rows": expected_fixture["rows"],
        "bytes": expected_fixture["bytes"],
        "claim_boundary": CLAIM_BOUNDARY,
    }


def main() -> int:
    try:
        value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print("DATA DESK BENCHMARK: FAIL")
        print(str(exc))
        return 2
    if not isinstance(value, Mapping):
        print("DATA DESK BENCHMARK: FAIL")
        print("receipt must contain one JSON object")
        return 2
    result = validate_receipt(ROOT, value)
    if not result["verified"]:
        print("DATA DESK BENCHMARK: FAIL")
        for error in result["errors"]:
            print("- " + error)
        return 2
    print("DATA DESK BENCHMARK: PASS")
    print("fixture: {0} rows / {1} bytes".format(result["rows"], result["bytes"]))
    print("claim boundary: " + result["claim_boundary"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
