#!/usr/bin/env python3
"""Build a deterministic, standard-library-only Uriel zipapp."""
from __future__ import annotations

import argparse
import hashlib
import os
import stat
import zipfile
from pathlib import Path
from typing import Iterable, Tuple

EPOCH = (1980, 1, 1, 0, 0, 0)


def files(source: Path) -> Iterable[Tuple[str, bytes]]:
    main = b"from uriel.cli import main\nraise SystemExit(main())\n"
    yield "__main__.py", main
    package = source / "uriel"
    for path in sorted(package.rglob("*"), key=lambda item: item.as_posix().casefold()):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix in {".pyc", ".pyo"}:
            continue
        yield path.relative_to(source).as_posix(), path.read_bytes()


def build(repository: Path, output: Path) -> str:
    source = repository / "src"
    if not (source / "uriel" / "cli.py").is_file():
        raise SystemExit("Run this script from the Uriel repository or pass --repository.")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name("." + output.name + ".tmp")
    if temporary.exists():
        temporary.unlink()
    with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for name, content in files(source):
            info = zipfile.ZipInfo(name, date_time=EPOCH)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            archive.writestr(info, content)
    os.replace(str(temporary), str(output))
    try:
        output.chmod(output.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    except OSError:
        pass
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    return digest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--output", default="dist/uriel.pyz")
    args = parser.parse_args()
    repository = Path(args.repository).resolve()
    output = Path(args.output)
    if not output.is_absolute():
        output = repository / output
    digest = build(repository, output)
    print("built:", output)
    print("sha256:", digest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
