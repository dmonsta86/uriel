#!/usr/bin/env python3
"""Validate the synthetic Forge Trial without fabricating detector metrics."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from uriel.forge_trials import run_forge_trials  # noqa: E402


def main() -> int:
    result = run_forge_trials(ROOT)
    fixture = result["fixture_validation"]
    evaluation = result["detector_evaluation"]
    if fixture["status"] != "PASS":
        print("FORGE TRIAL FIXTURE CHECK: FAIL")
        for error in fixture["errors"]:
            print(f"- {error}")
        return 1
    if evaluation["status"] != "NOT_RUN":
        print("FORGE TRIAL FIXTURE CHECK: FAIL")
        print("- release check must not substitute seeded defects for observed findings")
        return 1
    if any(evaluation[field] is not None for field in ("precision", "recall", "f1")):
        print("FORGE TRIAL FIXTURE CHECK: FAIL")
        print("- detector metrics exist even though no detector result was supplied")
        return 1

    print("FORGE TRIAL FIXTURE CHECK: PASS")
    print("seeded_issue_count:", fixture["seeded_issue_count"])
    print("scorecard_total_points:", fixture["scorecard_total_points"])
    print("detector_status: NOT_RUN (no precision/recall claim)")
    print("fixture_digest:", fixture["fixture_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
