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
    "prompts/",
    "src/uriel/",
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
    "unsupported-chatgpt-web-provider": re.compile(r"\bchatgpt-web\b", re.IGNORECASE),
    "corrupted-web-provider": re.compile(r"\bweb\s+AI\s+session-web\b", re.IGNORECASE),
}

NAMED_RECOMMENDATION_PATTERN = re.compile(
    r"\b(?:GPT-5\.6\s+Sol|Sol\s+(?:Pro|Medium|High|Extra\s+High)|Sol\s+5\.6)\b",
    re.IGNORECASE,
)
PRIVATE_PUBLIC_PATTERNS = {
    "internal research id": re.compile(r"\b(?:canonical|project)\s+215\b", re.IGNORECASE),
    "private repository folder": re.compile(r"\bScientific-Institutions\b", re.IGNORECASE),
    "private control packet": re.compile(r"\b(?:_SORT_CONTROL|URIEL_LUNA_ROADMAP)\b", re.IGNORECASE),
    "local user profile": re.compile(r"[A-Za-z]:\\Users\\(?!Example\\)[^\\\s`]+", re.IGNORECASE),
}
OBSOLETE_ASSETS = (
    "docs/assets/uriel-banner.png",
    "docs/assets/uriel-forge-banner.png",
)
FORBIDDEN_TRACKED_NAMES = {".DS_Store", "Thumbs.db", "desktop.ini"}
FORBIDDEN_TRACKED_SUFFIXES = {".bak", ".bundle", ".log", ".orig", ".pyc", ".pyo", ".rej", ".swp", ".tmp"}

REQUIRED_README_PHRASES = (
    "The Forge of Uriel",
    "Forge Method",
    "The Blessing of Uriel",
    "The Three Gates",
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
    return bool(re.fullmatch(r"README(?:\.[A-Za-z0-9-]+)?\.md", rel)) or any(
        rel == prefix or rel.startswith(prefix) for prefix in PUBLIC_PREFIXES
    )


def recommendation_allowed(relative: str) -> bool:
    return relative == "docs/AI_USAGE_AND_PRIVACY.md" or bool(
        re.fullmatch(r"README(?:\.[A-Za-z0-9-]+)?\.md", relative)
    )


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

        if NAMED_RECOMMENDATION_PATTERN.search(text):
            recommendation_occurrences.append(rel)
            if not recommendation_allowed(rel):
                errors.append(
                    f"{rel}: named recommendation is outside the explicit allowlist"
                )

        for label, pattern in PRIVATE_PUBLIC_PATTERNS.items():
            if pattern.search(text):
                errors.append(f"{rel}: public file contains {label}")

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

        # Fail-closed regression check against active URIEL FORGE title branding or obsolete hero references
        if re.search(r"^#+\s*Uriel Forge\b", readme_text, re.MULTILINE):
            errors.append("README.md: active heading still uses 'Uriel Forge' instead of 'The Forge of Uriel'")
        if "uriel-forge-banner.png" in readme_text or "01_uriel_forge" in readme_text:
            errors.append("README.md: active hero image reference points to obsolete 'uriel-forge-banner.png'")

    for path in tracked_files():
        rel = path.relative_to(ROOT).as_posix()
        if rel == ".opencode" or rel.startswith(".opencode/"):
            errors.append(f"{rel}: provider-specific project configuration is tracked")
        if path.name in FORBIDDEN_TRACKED_NAMES or path.suffix.casefold() in FORBIDDEN_TRACKED_SUFFIXES:
            errors.append(f"{rel}: backup/cache/log residue must not be tracked")

    for relative in OBSOLETE_ASSETS:
        if (ROOT / relative).exists():
            errors.append(f"{relative}: obsolete duplicate public asset is still present")

    asset_manifest = ROOT / "docs" / "design" / "ASSET_MANIFEST.md"
    if not asset_manifest.is_file():
        errors.append("docs/design/ASSET_MANIFEST.md: missing")
    else:
        asset_text = asset_manifest.read_text(encoding="utf-8")
        declared = re.findall(r"`((?:docs/assets|docs/design/visual-prompts)/[^`]+)`", asset_text)
        if not declared:
            errors.append("docs/design/ASSET_MANIFEST.md: no repository-relative assets declared")
        for relative in declared:
            if not (ROOT / relative).is_file():
                errors.append(f"docs/design/ASSET_MANIFEST.md: missing declared path {relative}")
        actual = {
            path.relative_to(ROOT).as_posix()
            for directory in (ROOT / "docs" / "assets", ROOT / "docs" / "design" / "visual-prompts")
            for path in directory.rglob("*")
            if path.is_file()
        }
        declared_set = set(declared)
        for relative in sorted(actual - declared_set):
            errors.append(f"docs/design/ASSET_MANIFEST.md: tracked public asset is undeclared: {relative}")
        for relative in sorted(declared_set - actual):
            errors.append(f"docs/design/ASSET_MANIFEST.md: declared public asset is not in the asset surface: {relative}")

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
