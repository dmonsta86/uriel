#!/usr/bin/env python3
"""Fail when Uriel's tracked capability claims drift from live evidence."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from uriel.capability_status import (  # noqa: E402
    CAPABILITIES,
    capability_artifacts,
    capability_source_fingerprint,
    validate_capability_catalog,
)


def main() -> int:
    errors = validate_capability_catalog(ROOT)
    cli_text = (ROOT / "src" / "uriel" / "cli.py").read_text(encoding="utf-8")
    cli_commands = set(re.findall(r'commands\.add_parser\("([a-z0-9-]+)"', cli_text))

    for capability in CAPABILITIES:
        identifier = capability["id"]
        status = capability["status"]
        entry = capability["entry_point"]
        advertised_commands = re.findall(r"\buriel\s+([a-z0-9-]+)", entry)
        for command in advertised_commands:
            if command not in cli_commands:
                errors.append(f"{identifier}: advertised CLI command does not exist: uriel {command}")
        script_entries = re.findall(r"python\s+(scripts/[A-Za-z0-9_.\-/]+)", entry)
        for relative in script_entries:
            if not (ROOT / relative).is_file():
                errors.append(f"{identifier}: advertised script does not exist: {relative}")
        if status in {"PLANNED", "DEFERRED"} and not entry.startswith("n/a"):
            errors.append(f"{identifier}: planned/deferred entry point is not explicitly unavailable")
        if status not in {"PLANNED", "DEFERRED"} and entry.startswith("n/a"):
            errors.append(f"{identifier}: implemented capability has no usable entry point")

    for relative, expected in capability_artifacts(ROOT).items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing generated capability artifact: {relative}")
            continue
        actual = path.read_text(encoding="utf-8")
        if actual != expected:
            errors.append(
                f"stale capability artifact: {relative}; run "
                "`python -c \"from pathlib import Path; "
                "from uriel.capability_status import write_capability_status_files; "
                "write_capability_status_files(Path('.'))\"` with PYTHONPATH=src"
            )

    if errors:
        print("CAPABILITY STATUS CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("CAPABILITY STATUS CHECK: PASS")
    print("catalog_fingerprint:", capability_source_fingerprint())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
