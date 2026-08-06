#!/usr/bin/env python3
"""Create and audit the same bounded passing fixture used by the test suite."""
from __future__ import annotations

import argparse
from pathlib import Path

from uriel.demo import make_passing_project
from uriel.audit import audit_project
from uriel.blessing import issue_blessing


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("path", nargs="?", default="./uriel-passing-example")
    args = parser.parse_args()
    root = Path(args.path).resolve()
    make_passing_project(root)
    report = audit_project(root, profile="submission")
    print("audit:", report.status, report.audit_id)
    if report.status != "PASS":
        return 2
    result = issue_blessing(root)
    print("blessing:", result["blessing_id"])
    print("package:", result["package"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
