#!/usr/bin/env python3
"""Measure one bounded synthetic Data Desk path without making scale claims."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import sys
import tempfile
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Tuple

from uriel import __version__
from uriel.core import canonical_json, initialize_project, sha256_file
from uriel.data_contracts import plan_data_import
from uriel.data_desk import inspect_data_artifact, verify_data_generation
from uriel.data_ingress import import_data_artifact


BENCHMARK_ID = "synthetic-tabular-10000-v1"
ROW_COUNT = 10_000
COLUMN_COUNT = 4
IMPLEMENTATION_FILES = (
    "scripts/benchmark_data_desk.py",
    "src/uriel/data_contracts.py",
    "src/uriel/data_ingress.py",
    "src/uriel/data_desk.py",
)
CLAIM_BOUNDARY = (
    "One synthetic local observation; not a throughput, capacity, latency-SLA, "
    "hardware-equivalence, or real-dataset claim."
)


def fixture_bytes() -> bytes:
    lines = ["id,group,value,note\n"]
    lines.extend(
        "r{0:05d},g{1},{2},text-{3}\n".format(index, index % 10, index % 997, index % 17)
        for index in range(ROW_COUNT)
    )
    return "".join(lines).encode("utf-8")


def implementation_binding(repository: Path) -> Dict[str, Any]:
    files = {
        relative: sha256_file(repository / relative)
        for relative in IMPLEMENTATION_FILES
    }
    return {
        "files": files,
        "binding_sha256": hashlib.sha256(canonical_json(files).encode("utf-8")).hexdigest(),
    }


def _measure(operation: Callable[[], Any]) -> Tuple[Any, float]:
    started = time.perf_counter_ns()
    result = operation()
    elapsed_ms = (time.perf_counter_ns() - started) / 1_000_000
    return result, round(elapsed_ms, 3)


def run_benchmark(repository: Path) -> Dict[str, Any]:
    payload = fixture_bytes()
    timings: Dict[str, float] = {}
    tracemalloc.start()
    try:
        with tempfile.TemporaryDirectory(prefix="uriel-data-benchmark-") as temporary:
            base = Path(temporary)
            root = base / "project"
            source = base / "source" / "synthetic.csv"
            source.parent.mkdir()
            source.write_bytes(payload)
            initialize_project(
                root,
                title="Synthetic Data Desk benchmark",
                question="Can one bounded synthetic table be sealed and reproduced?",
                privacy="public",
            )

            planned, timings["plan_ms"] = _measure(
                lambda: plan_data_import(root, source, label="synthetic-10000")
            )
            plan_path = root / "artifacts" / "benchmark-plan.json"
            plan_path.write_text(canonical_json(planned["plan"]), encoding="utf-8")
            imported, timings["import_ms"] = _measure(
                lambda: import_data_artifact(
                    root, source, plan_path.relative_to(root).as_posix()
                )
            )
            inspected, timings["inspect_ms"] = _measure(
                lambda: inspect_data_artifact(root, imported["receipt_relative_path"])
            )
            verified, timings["verify_ms"] = _measure(
                lambda: verify_data_generation(root, inspected["generation_id"])
            )
            repeated, timings["repeat_inspect_ms"] = _measure(
                lambda: inspect_data_artifact(root, imported["receipt_relative_path"])
            )
            _current, peak_bytes = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()

    if inspected.get("record_count") != ROW_COUNT:
        raise RuntimeError("benchmark inspection returned the wrong record count")
    if verified.get("verified") is not True or verified.get("decision") != "PASS":
        raise RuntimeError("benchmark generation did not independently verify")
    if repeated.get("generation_id") != inspected.get("generation_id"):
        raise RuntimeError("benchmark repeat changed generation identity")

    return {
        "schema": "uriel.data_desk_benchmark_receipt.v1",
        "schema_version": 1,
        "benchmark_id": BENCHMARK_ID,
        "measured_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "uriel_version": __version__,
        "runtime": {
            "python": "{0}.{1}.{2}".format(*sys.version_info[:3]),
            "platform": platform.system() or "unknown",
            "architecture": platform.machine() or "unknown",
        },
        "fixture": {
            "kind": "deterministic synthetic CSV",
            "rows": ROW_COUNT,
            "columns": COLUMN_COUNT,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        "implementation": implementation_binding(repository),
        "operations_ms": timings,
        "peak_traced_python_bytes": peak_bytes,
        "result": {
            "generation_id": inspected["generation_id"],
            "record_count": inspected["record_count"],
            "verification_decision": verified["decision"],
            "deterministic_repeat": True,
        },
        "claim_boundary": CLAIM_BOUNDARY,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repository",
        default=str(Path(__file__).resolve().parents[1]),
        help="Uriel source repository whose implementation is being measured",
    )
    parser.add_argument("--report", default="", help="optional JSON receipt path")
    parser.add_argument("--replace", action="store_true", help="replace an existing report atomically")
    args = parser.parse_args()
    repository = Path(args.repository).resolve(strict=True)
    receipt = run_benchmark(repository)
    rendered = json.dumps(receipt, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    if args.report:
        report = Path(args.report)
        if not report.is_absolute():
            report = repository / report
        if report.exists() and not args.replace:
            raise SystemExit("refusing to overwrite existing benchmark receipt; pass --replace explicitly")
        report.parent.mkdir(parents=True, exist_ok=True)
        temporary = report.with_name("." + report.name + ".tmp")
        if temporary.exists():
            raise SystemExit("refusing to overwrite a pre-existing benchmark temporary file")
        temporary.write_text(rendered, encoding="utf-8")
        os.replace(str(temporary), str(report))
    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
