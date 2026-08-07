#!/usr/bin/env python3
"""Fail-closed public identity and provider-neutrality checker for Uriel."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PUBLIC_PREFIXES = (
    "README.md",
    "pyproject.toml",
    "CITATION.cff",
    "docs/",
    "examples/",
    "installer/",
    "templates/",
    "src/uriel/templates/",
)

TEXT_SUFFIXES = {
    ".md", ".txt", ".rst", ".toml", ".yaml", ".yml", ".json",
    ".py", ".ps1", ".sh", ".cmd", ".bat"
}

DISALLOWED_PATTERNS = {
    "opencode": re.compile(r"\bopencode\b", re.IGNORECASE),
    "deepseek": re.compile(r"\bdeepseek\b", re.IGNORECASE),
    "gemini": re.compile(r"\bgemini\b", re.IGNORECASE),
    "claude": re.compile(r"\bclaude\b", re.IGNORECASE),
    "cursor": re.compile(r"\bcursor(?:\.com)?\b", re.IGNORECASE),
    "aider": re.compile(r"\baider\b", re.IGNORECASE),
    "cline": re.compile(r"\bcline\b", re.IGNORECASE),
}

ALLOWED_NAMED_RECOMMENDATION = "GPT-5.6 Sol with ultra mode"
ALLOWED_RECOMMENDATION_FILES = {
    "README.md",
    "docs/AI_USAGE_AND_PRIVACY.md",
}

REQUIRED_README_PHRASES = (
    "The Forge of Uriel",
    "Every idea deserves its strongest fair hearing",
    "Every claim must survive its strongest fair challenge",
    "The Forge Method",
    "The Blessing of Uriel",
    "Data before conclusions",
)

FORBIDDEN_PLACEHOLDERS = (
    "GENERATE_FROM_LIVE_REPO",
    "<GENERATE",
    "TODO_PUBLIC",
    "TBD_PUBLIC",
)


def tracked_files() -> list[Path]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "-z"],
            cwd=ROOT,
        )
        names = [item for item in output.decode("utf-8").split("\0") if item]
        return [ROOT / name for name in names]
    except (FileNotFoundError, subprocess.CalledProcessError, UnicodeDecodeError):
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]


def is_public(path: Path) -> bool:
    rel = path.relative_to(ROOT).as_posix()
    return any(rel == prefix or rel.startswith(prefix) for prefix in PUBLIC_PREFIXES)


def main() -> int:
    errors: list[str] = []
    recommendation_occurrences: list[str] = []

    for path in tracked_files():
        if not is_public(path) or path.suffix.lower() not in TEXT_SUFFIXES:
            continue

        rel = path.relative_to(ROOT).as_posix()
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for label, pattern in DISALLOWED_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{rel}: disallowed public provider/tool name: {label}")

        if ALLOWED_NAMED_RECOMMENDATION in text:
            recommendation_occurrences.append(rel)
            if rel not in ALLOWED_RECOMMENDATION_FILES:
                errors.append(
                    f"{rel}: named recommendation is outside the explicit allowlist"
                )

        for marker in FORBIDDEN_PLACEHOLDERS:
            if marker in text:
                errors.append(f"{rel}: unresolved public placeholder: {marker}")

    readme = ROOT / "README.md"
    if not readme.is_file():
        errors.append("README.md is missing")
    else:
        readme_text = readme.read_text(encoding="utf-8")
        for phrase in REQUIRED_README_PHRASES:
            if phrase not in readme_text:
                errors.append(f"README.md: required public phrase missing: {phrase}")

    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == ".opencode" or rel.startswith(".opencode/"):
            errors.append(f"{rel}: provider-specific project configuration is tracked")

    if len(recommendation_occurrences) > 2:
        errors.append(
            "named recommendation appears in too many public files: "
            + ", ".join(sorted(recommendation_occurrences))
        )

    if errors:
        print("PUBLIC IDENTITY CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("PUBLIC IDENTITY CHECK: PASS")
    print(
        "Allowed named recommendation files: "
        + ", ".join(sorted(recommendation_occurrences or ["none"]))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
