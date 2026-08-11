#!/usr/bin/env python3
"""Exercise the local Forge engine through one freshly installed Uriel CLI."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import List


def _run(executable: Path, arguments: List[str], *, expected: int = 0) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(executable), *arguments],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != expected:
        raise RuntimeError(
            "installed Forge command returned {0}, expected {1}:\n{2}\n{3}".format(
                completed.returncode,
                expected,
                completed.stdout,
                completed.stderr,
            )
        )
    return completed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True)
    args = parser.parse_args()
    executable = Path(args.executable).resolve(strict=True)

    with tempfile.TemporaryDirectory(prefix="uriel-installed-forge-") as temporary:
        root = Path(temporary) / "project"
        _run(executable, ["init", str(root), "--question", "Can installed Forge preserve exact lineage?"])
        request_path = root / "artifacts" / "forge-init.json"
        request_path.parent.mkdir(parents=True, exist_ok=True)
        request_path.write_text(
            json.dumps(
                {
                    "schema": "uriel.forge_init_request.v1",
                    "mission": "Exercise the installed deterministic Forge facade.",
                    "non_goals": ["Do not grant Gate, publication, Blessing, or Earned Wings authority."],
                    "requirements": [
                        {
                            "requirement_id": "req-installed",
                            "statement": "The installed CLI writes immutable local snapshots.",
                            "acceptance_condition": "The exact child and parent independently verify.",
                            "source_kind": "OPERATOR",
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        initialized = _run(
            executable,
            [
                "--json",
                "forge",
                "init",
                "--root",
                str(root),
                "--request",
                "artifacts/forge-init.json",
            ],
        )
        baseline = json.loads(initialized.stdout).get("result", {})
        if (
            baseline.get("state") != "DRAFT"
            or baseline.get("verified") is not True
            or baseline.get("authority_granted") is not False
            or (baseline.get("network_calls"), baseline.get("ai_calls"), baseline.get("subprocess_calls")) != (0, 0, 0)
        ):
            raise RuntimeError("installed Forge baseline crossed its deterministic authority boundary")

        moved = _run(
            executable,
            [
                "--json",
                "forge",
                "transition",
                "--root",
                str(root),
                "--snapshot",
                str(baseline["snapshot_relative_path"]),
                "--to-state",
                "SCOPED",
                "--rationale",
                "The installed smoke mission and boundary were reviewed.",
            ],
        )
        child = json.loads(moved.stdout).get("result", {})
        if child.get("state") != "SCOPED" or child.get("lineage_records") != 2:
            raise RuntimeError("installed Forge transition did not create one verified child")

        checked = _run(
            executable,
            [
                "--json",
                "forge",
                "verify",
                "--root",
                str(root),
                "--snapshot",
                str(child["snapshot_relative_path"]),
            ],
        )
        verification = json.loads(checked.stdout).get("result", {})
        if verification.get("verified") is not True or verification.get("bindings_current") is not True:
            raise RuntimeError("installed Forge independent verification did not pass")

        snapshot = root / str(child["snapshot_relative_path"])
        forged = json.loads(snapshot.read_text(encoding="utf-8"))
        forged["mission"] = "tampered"
        snapshot.write_text(json.dumps(forged), encoding="utf-8")
        refused = _run(
            executable,
            [
                "--json",
                "forge",
                "verify",
                "--root",
                str(root),
                "--snapshot",
                str(child["snapshot_relative_path"]),
            ],
            expected=2,
        )
        error = json.loads(refused.stdout).get("error", {})
        if error.get("code") != "FORGE_RECORD_DIGEST_MISMATCH" or str(root) in refused.stdout:
            raise RuntimeError("installed Forge tamper refusal was unstable or disclosed the project path")

    print("installed Forge engine: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
