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

        checks = []
        for check_id in (
            "VERIFY_REQUIREMENT",
            "SEARCH_DECLARED_BOUNDARY",
            "TEST_SAFE_ALTERNATIVE",
            "TEST_NARROWER_SCOPE",
            "TEST_SUBSTITUTE_EVIDENCE",
            "COMPLETE_SAFE_SCAFFOLD",
            "NO_PATH_CHALLENGE",
        ):
            outcome = (
                "REQUIREMENT_CONFIRMED"
                if check_id == "VERIFY_REQUIREMENT"
                else "PATH_FOUND"
                if check_id == "SEARCH_DECLARED_BOUNDARY"
                else "NO_PATH"
            )
            checks.append(
                {
                    "check_id": check_id,
                    "outcome": outcome,
                    "evidence_ref_ids": ["ref-project-manifest"],
                    "finding": "Installed smoke finding for " + check_id + ".",
                }
            )
        dimensions = (
            "information_gain",
            "rival_discrimination",
            "falsification_value",
            "evidence_quality",
            "dependency_unlocking",
            "risk",
            "cost",
            "time",
            "user_burden",
            "reversibility",
            "reproducibility",
            "honest_outcome_potential",
        )
        forward_path = root / "artifacts" / "forge-forward.json"
        forward_path.write_text(
            json.dumps(
                {
                    "schema": "uriel.forge_forward_request.v1",
                    "operator_assessment": {
                        "established": ["The installed exact source verifies."],
                        "refuted": ["A mutable latest pointer is unnecessary."],
                        "unknown": ["The research outcome remains unknown."],
                        "remains_useful": ["The evidence-bound next move remains useful."],
                    },
                    "subject_requirement_ids": ["req-installed"],
                    "blocker_checks": checks,
                    "candidate_moves": [
                        {
                            "move_id": "move-installed",
                            "kind": "LOCAL_CHECK",
                            "action": "Exercise the installed continuation facade.",
                            "completion_condition": "The exact continuation independently verifies.",
                            "required_input_ids": [],
                            "addresses_check_ids": ["SEARCH_DECLARED_BOUNDARY"],
                            "ratings": {
                                name: "LOW" if name in {"risk", "cost", "time", "user_burden"} else "HIGH"
                                for name in dimensions
                            },
                            "guardrails": {
                                "ethics_respected": True,
                                "law_respected": True,
                                "consent_respected": True,
                                "privacy_respected": True,
                                "resource_limits_respected": True,
                                "authority_not_bypassed": True,
                            },
                        }
                    ],
                    "safe_work_completed": ["Verified the installed source lineage."],
                    "required_inputs": [],
                }
            ),
            encoding="utf-8",
        )
        continued = _run(
            executable,
            [
                "--json",
                "forge",
                "continue",
                "--root",
                str(root),
                "--snapshot",
                str(child["snapshot_relative_path"]),
                "--request",
                "artifacts/forge-forward.json",
            ],
        )
        continuation = json.loads(continued.stdout).get("result", {})
        if continuation.get("blocker_status") != "PATH_AVAILABLE" or continuation.get("verified") is not True:
            raise RuntimeError("installed Forge continuation did not derive and verify")
        _run(
            executable,
            [
                "--json",
                "forge",
                "verify-continuation",
                "--root",
                str(root),
                "--packet",
                str(continuation["continuation_relative_path"]),
            ],
        )
        exported = _run(
            executable,
            [
                "--json",
                "forge",
                "export",
                "--root",
                str(root),
                "--snapshot",
                str(child["snapshot_relative_path"]),
                "--destination",
                "artifacts/forge-export",
            ],
        )
        export = json.loads(exported.stdout).get("result", {})
        if export.get("verified") is not True or export.get("body_exported") is not False:
            raise RuntimeError("installed Forge sanitized export crossed its body boundary")
        _run(
            executable,
            [
                "--json",
                "forge",
                "verify-export",
                "--root",
                str(root),
                "--manifest",
                str(export["manifest_relative_path"]),
                "--snapshot",
                str(child["snapshot_relative_path"]),
            ],
        )

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
