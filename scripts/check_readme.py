#!/usr/bin/env python3
"""Fail-closed checks for Uriel's public README and onboarding contract."""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def local_target(value: str) -> Path | None:
    if value.startswith(("http://", "https://", "mailto:", "#", "data:")):
        return None
    clean = unquote(value.split("#", 1)[0].strip())
    if not clean:
        return None
    return (ROOT / clean).resolve()


def main() -> int:
    errors: list[str] = []
    text = README.read_text(encoding="utf-8")

    if len(re.findall(r"^\s*```", text, re.MULTILINE)) % 2:
        errors.append("README.md has an unbalanced fenced code block")

    for value in re.findall(r"\]\(([^)]+)\)", text):
        target = local_target(value)
        if target is None:
            continue
        try:
            target.relative_to(ROOT)
        except ValueError:
            errors.append(f"README link escapes repository: {value}")
            continue
        if not target.exists():
            errors.append(f"README has a missing local link: {value}")

    for value in re.findall(r'(?:src|href)="([^"]+)"', text):
        target = local_target(value)
        if target is None:
            continue
        try:
            target.relative_to(ROOT)
        except ValueError:
            errors.append(f"README HTML reference escapes repository: {value}")
            continue
        if not target.exists():
            errors.append(f"README has a missing local HTML reference: {value}")

    cli_text = (ROOT / "src" / "uriel" / "cli.py").read_text(encoding="utf-8")
    cli_commands = set(re.findall(r'commands\.add_parser\("([a-z0-9-]+)"', cli_text))
    for command in re.findall(r"^\s*uriel\s+([^\s#]+)", text, re.MULTILINE):
        if command.startswith("-"):
            continue
        if command not in cli_commands:
            errors.append(f"README advertises an unknown CLI command: uriel {command}")

    required = (
        "Distribution package: `uriel-research`",
        "Python import and CLI command: `uriel`",
        "python -m pip install --no-deps --no-build-isolation .",
        "uriel start --root",
        "uriel status --root",
        "uriel verify --root",
        "content-addressed attestation",
        "not independent scientific validation",
    )
    for phrase in required:
        if phrase not in text:
            errors.append(f"README is missing required truth/onboarding copy: {phrase}")
    if not re.search(r"does not claim\s+that Uriel detected", text):
        errors.append("README does not state the Forge Trial detector truth boundary")

    forbidden = (
        "signed, content-addressed audit certificate",
        "A Blessing certifies that evidence was verified",
        "Forge Method milestone closure",
        "```text\nrefuted\nimpossible\n```",
    )
    for phrase in forbidden:
        if phrase in text:
            errors.append(f"README contains an obsolete or overbroad claim: {phrase}")

    markdown_files = [README, *sorted((ROOT / "docs").glob("*.md"))]
    for path in markdown_files:
        body = path.read_text(encoding="utf-8")
        if len(re.findall(r"^\s*```", body, re.MULTILINE)) % 2:
            errors.append(
                f"{path.relative_to(ROOT).as_posix()} has an unbalanced fenced code block"
            )

    if errors:
        print("README CONTRACT CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("README CONTRACT CHECK: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
