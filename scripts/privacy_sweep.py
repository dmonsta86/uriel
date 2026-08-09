#!/usr/bin/env python3
"""Fail when likely secrets, private workspace residue, or generated state enters a release."""
from __future__ import annotations

import argparse
import re
import subprocess
from pathlib import Path
from typing import Iterable, List, Tuple

TEXT_SUFFIXES = {
    ".py", ".ps1", ".psm1", ".md", ".txt", ".json", ".jsonl", ".toml", ".yml", ".yaml",
    ".cff", ".ini", ".cfg", ".sh", ".bat", ".svg", ".xml",
}
SKIP_PARTS = {".git", ".venv", "venv", "dist", "build", "__pycache__", ".pytest_cache", ".uriel"}
SCANNER_EXEMPTIONS = {"scripts/privacy_sweep.py", "scripts/check_public_identity.py"}
PATTERNS = (
    ("PRIVATE_KEY", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("AWS_KEY", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("GITHUB_TOKEN", re.compile(r"\bgh[opusr]_[A-Za-z0-9_]{20,}\b")),
    ("GENERIC_SECRET", re.compile(r"(?i)\b(?:api[_-]?key|client[_-]?secret|access[_-]?token)\s*[:=]\s*['\"][^'\"]{12,}['\"]")),
    ("SOURCE_WORKSPACE", re.compile(r"(?i)(?:[A-Z]:\\root\\UPJ|\.unlockpro-research|tallermax|m600\.local|Scientific-Institutions|_SORT_CONTROL|URIEL_LUNA_ROADMAP)")),
    ("WINDOWS_USER_PROFILE", re.compile(r"(?i)[A-Z]:\\Users\\(?!Example\\)[^\\\s`]+")),
    ("INTERNAL_RESEARCH_ID", re.compile(r"(?i)\b(?:canonical|project)\s+215\b")),
)


def candidates(root: Path) -> Iterable[Path]:
    try:
        output = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=root,
        )
        paths = [root / name for name in output.decode("utf-8").split("\0") if name]
    except (FileNotFoundError, subprocess.CalledProcessError, UnicodeDecodeError):
        paths = list(root.rglob("*"))
    for path in sorted(paths, key=lambda item: item.as_posix().casefold()):
        if any(part in SKIP_PARTS for part in path.relative_to(root).parts):
            continue
        if path.is_file() and (path.suffix.casefold() in TEXT_SUFFIXES or path.name in {"LICENSE", "MANIFEST.in", "AGENTS.md"}):
            yield path


def sweep(root: Path) -> List[Tuple[str, str, int]]:
    findings: List[Tuple[str, str, int]] = []
    for path in candidates(root):
        if path.relative_to(root).as_posix() in SCANNER_EXEMPTIONS:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            for code, pattern in PATTERNS:
                if pattern.search(line):
                    findings.append((code, path.relative_to(root).as_posix(), number))
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()
    root = Path(args.root).resolve()
    findings = sweep(root)
    if findings:
        for code, path, line in findings:
            print(f"{code}: {path}:{line}")
        return 2
    print("privacy sweep: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
