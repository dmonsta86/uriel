#!/usr/bin/env python3
"""Regenerate every tracked capability artifact from the canonical catalog."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from uriel.capability_status import capability_source_fingerprint, write_capability_status_files  # noqa: E402


def main() -> int:
    write_capability_status_files(ROOT)
    print("Updated capability artifacts.")
    print("catalog_fingerprint:", capability_source_fingerprint())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
