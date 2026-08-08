#!/usr/bin/env python3
"""Recompute the synthetic trial's clean descriptive summary."""

from __future__ import annotations

import json
import sys
from pathlib import Path

CASE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(REPOSITORY / "src"))

from uriel.forge_trials import recompute_clean_summary  # noqa: E402


if __name__ == "__main__":
    print(json.dumps(recompute_clean_summary(CASE_ROOT), indent=2, sort_keys=True))
