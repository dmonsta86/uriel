#!/usr/bin/env python3
"""Bind release metadata to the maintainer's public GitHub repository.

The operation is deterministic and idempotent. It changes only pyproject.toml
and CITATION.cff, and it never contacts GitHub.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

SLUG = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9._-]{1,100}$")


def write_text_lf(path: Path, value: str) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(value)


def update_pyproject(path: Path, base_url: str) -> bool:
    original = path.read_text(encoding="utf-8")
    block = (
        "[project.urls]\n"
        f'Homepage = "{base_url}"\n'
        f'Repository = "{base_url}"\n'
        f'Issues = "{base_url}/issues"\n'
        f'Documentation = "{base_url}#readme"\n\n'
    )
    pattern = re.compile(r"(?ms)^\[project\.urls\]\n.*?(?=^\[|\Z)")
    if pattern.search(original):
        updated = pattern.sub(block, original, count=1)
    else:
        anchor = "[project.scripts]\n"
        if anchor not in original:
            raise SystemExit("pyproject.toml has no [project.scripts] insertion anchor")
        updated = original.replace(anchor, block + anchor, 1)
    if updated != original:
        write_text_lf(path, updated)
        return True
    return False


def upsert_cff(lines: list[str], key: str, value: str) -> list[str]:
    replacement = f'{key}: "{value}"'
    prefix = key + ":"
    for index, line in enumerate(lines):
        if line.startswith(prefix):
            lines[index] = replacement
            return lines
    insert_after = next((i for i, line in enumerate(lines) if line.startswith("date-released:")), 4)
    lines.insert(insert_after + 1, replacement)
    return lines


def update_citation(path: Path, base_url: str) -> bool:
    original = path.read_text(encoding="utf-8")
    lines = original.splitlines()
    lines = upsert_cff(lines, "repository-code", base_url)
    lines = upsert_cff(lines, "url", base_url)
    updated = "\n".join(lines) + "\n"
    if updated != original:
        write_text_lf(path, updated)
        return True
    return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--slug", required=True, help="GitHub OWNER/REPOSITORY")
    parser.add_argument("--repository", default=str(Path(__file__).resolve().parents[1]))
    args = parser.parse_args()

    if not SLUG.fullmatch(args.slug):
        raise SystemExit("--slug must use the form OWNER/REPOSITORY")
    root = Path(args.repository).resolve()
    pyproject = root / "pyproject.toml"
    citation = root / "CITATION.cff"
    if not pyproject.is_file() or not citation.is_file():
        raise SystemExit("repository must contain pyproject.toml and CITATION.cff")

    base_url = "https://github.com/" + args.slug
    changed = []
    if update_pyproject(pyproject, base_url):
        changed.append("pyproject.toml")
    if update_citation(citation, base_url):
        changed.append("CITATION.cff")
    if changed:
        print("configured repository metadata:", ", ".join(changed))
    else:
        print("repository metadata already configured")
    print("repository:", base_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
