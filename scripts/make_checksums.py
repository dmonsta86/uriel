#!/usr/bin/env python3
"""Write deterministic SHA-256 lines for release artifacts."""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


def digest(path: Path) -> str:
    value = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            value.update(block)
    return value.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", default="dist")
    parser.add_argument("--output", default="SHA256SUMS.txt")
    args = parser.parse_args()
    directory = Path(args.directory).resolve()
    output = directory / args.output
    files = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.name != output.name
        and path.suffix in {".whl", ".gz", ".pyz", ".zip", ".bundle"}
    ]
    lines = [f"{digest(path)}  {path.name}" for path in sorted(files, key=lambda item: item.name.casefold())]
    output.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    print("checksums:", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
