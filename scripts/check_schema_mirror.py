#!/usr/bin/env python3
"""Require editor-facing schemas to exactly mirror packaged runtime schemas."""
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PACKAGED = ROOT / "src" / "uriel" / "schemas"
EDITOR = ROOT / "schemas"


def main() -> int:
    packaged = {path.name: path for path in PACKAGED.glob("*.json")}
    editor = {path.name: path for path in EDITOR.glob("*.json")}
    errors = []
    for name in sorted(set(packaged) - set(editor)):
        errors.append("missing editor mirror: " + name)
    for name in sorted(set(editor) - set(packaged)):
        errors.append("editor-only schema: " + name)
    for name in sorted(set(packaged) & set(editor)):
        if packaged[name].read_bytes() != editor[name].read_bytes():
            errors.append("byte mismatch: " + name)
    if errors:
        print("SCHEMA MIRROR: FAIL")
        for error in errors:
            print("- " + error)
        return 1
    print("SCHEMA MIRROR: PASS ({0} schemas)".format(len(packaged)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
