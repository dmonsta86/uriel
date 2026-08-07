#!/usr/bin/env python3
"""Fail-closed validation for Uriel public maintenance surfaces."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

REQUIRED = [
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/audit_false_positive.yml",
    ".github/ISSUE_TEMPLATE/audit_false_negative.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/ISSUE_TEMPLATE/documentation.yml",
    ".github/ISSUE_TEMPLATE/translation_correction.yml",
    ".github/ISSUE_TEMPLATE/forge_trial.yml",
    ".github/pull_request_template.md",
    "SECURITY.md",
    "SUPPORT.md",
    "docs/COMMUNITY.md",
]

PRIVATE_PATTERNS = [
    re.compile(r"[A-Za-z]:\\Users\\", re.IGNORECASE),
    re.compile(r"file:///+[A-Za-z]:/", re.IGNORECASE),
    re.compile(r"(?:api[_-]?key|token|secret|password)\s*[:=]\s*\S+", re.IGNORECASE),
]

def main() -> int:
    errors: list[str] = []
    for rel in REQUIRED:
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"missing community-health file: {rel}")
            continue
        text = path.read_text(encoding="utf-8")
        for pattern in PRIVATE_PATTERNS:
            if pattern.search(text):
                errors.append(f"private/sensitive pattern in {rel}")

    security = ROOT / "SECURITY.md"
    if security.is_file() and "Do not open a public issue" not in security.read_text(encoding="utf-8"):
        errors.append("SECURITY.md does not clearly forbid public vulnerability disclosure")

    if errors:
        print("COMMUNITY HEALTH CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("COMMUNITY HEALTH CHECK: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
