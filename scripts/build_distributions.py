#!/usr/bin/env python3
"""Build wheel and sdist using the declared setuptools backend.

This helper avoids changing the working tree by building from a temporary copy.
It requires the build-system tools declared in pyproject.toml, but Uriel itself
still has zero runtime dependencies.
"""
from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable


IGNORED_NAMES = {
    ".git",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    ".release-venv",
    "venv",
    "build",
    "dist",
    "__pycache__",
    ".coverage",
    "htmlcov",
    ".env",
    ".uriel",
    "release-check.txt",
    ".uriel-release-check.lock",
}


def ignore(directory: str, names: Iterable[str]) -> set[str]:
    ignored: set[str] = set()
    for name in names:
        if name in IGNORED_NAMES or name.endswith(".egg-info") or name.endswith((".pyc", ".pyo")):
            ignored.add(name)
    return ignored


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output", default="dist")
    parser.add_argument("--clean", action="store_true")
    parser.add_argument("--timeout", type=int, default=600, help="maximum build seconds (default: 600)")
    args = parser.parse_args()
    if args.timeout < 10:
        parser.error("--timeout must be at least 10 seconds")

    root = Path(args.repository).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = root / output
    if args.clean and output.exists():
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)

    try:
        import setuptools  # noqa: F401
        import wheel  # noqa: F401
    except ImportError as exc:
        raise SystemExit(
            "Build tools are missing. Install them with: python -m pip install --upgrade setuptools wheel"
        ) from exc

    with tempfile.TemporaryDirectory(prefix="uriel-build-") as temporary:
        checkout = Path(temporary) / "uriel"
        shutil.copytree(root, checkout, ignore=ignore)
        build_output = Path(temporary) / "dist"
        build_output.mkdir()
        code = (
            "from setuptools import build_meta; "
            "print(build_meta.build_sdist(r'" + str(build_output).replace("'", "\\'") + "')); "
            "print(build_meta.build_wheel(r'" + str(build_output).replace("'", "\\'") + "'))"
        )
        print("building source distribution and wheel...", flush=True)
        try:
            completed = subprocess.run(
                [sys.executable, "-c", code],
                cwd=str(checkout),
                check=False,
                text=True,
                capture_output=True,
                timeout=args.timeout,
            )
        except subprocess.TimeoutExpired as exc:
            if exc.stdout:
                print(exc.stdout, end="", file=sys.stderr)
            if exc.stderr:
                print(exc.stderr, end="", file=sys.stderr)
            raise SystemExit(f"distribution build exceeded {args.timeout} seconds") from exc
        if completed.returncode:
            if completed.stdout:
                print(completed.stdout, end="", file=sys.stderr)
            if completed.stderr:
                print(completed.stderr, end="", file=sys.stderr)
            return completed.returncode
        artifacts = sorted(build_output.iterdir(), key=lambda item: item.name.casefold())
        if not artifacts:
            raise SystemExit("No distribution artifacts were produced.")
        for artifact in artifacts:
            destination = output / artifact.name
            shutil.copy2(artifact, destination)
            print("built:", destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
