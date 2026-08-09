#!/usr/bin/env python3
"""Exercise Evidence Ingress and Data Desk through an installed Uriel command."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import List


def _run(executable: Path, arguments: List[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(executable), *arguments],
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode:
        raise RuntimeError(
            "installed command failed ({0}): {1}\n{2}".format(
                completed.returncode,
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

    with tempfile.TemporaryDirectory(prefix="uriel-installed-ingress-") as temporary:
        base = Path(temporary)
        root = base / "project"
        source = base / "private-source-name" / "records.csv"
        source.parent.mkdir()
        source.write_text("id,value\na,1\nb,2\n", encoding="utf-8")

        _run(executable, ["init", str(root), "--question", "Can installed Uriel seal exact bytes?"])
        planned = _run(
            executable,
            ["--json", "data", "plan", "--root", str(root), "--source", str(source), "--label", "smoke-records"],
        )
        if str(source) in planned.stdout or "private-source-name" in planned.stdout:
            raise RuntimeError("data plan disclosed the private source path")
        plan_value = json.loads(planned.stdout)
        if plan_value.get("status") != "OK":
            raise RuntimeError("data plan did not return an OK CLI envelope")
        plan_path = root / "artifacts" / "installed-import-plan.json"
        plan_path.write_text(planned.stdout, encoding="utf-8")

        imported = _run(
            executable,
            [
                "--json",
                "data",
                "import",
                "--root",
                str(root),
                "--source",
                str(source),
                "--plan",
                "artifacts/installed-import-plan.json",
            ],
        )
        if str(source) in imported.stdout or "private-source-name" in imported.stdout:
            raise RuntimeError("data import disclosed the private source path")
        result = json.loads(imported.stdout).get("result", {})
        if result.get("status") != "SEALED" or result.get("outcome") != "COPIED":
            raise RuntimeError("installed data import did not seal a copied artifact")
        if result.get("gate_0_authority_granted") is not False:
            raise RuntimeError("managed intake incorrectly granted Gate 0 authority")

        verified = _run(
            executable,
            [
                "--json",
                "data",
                "verify-import",
                "--root",
                str(root),
                "--receipt",
                str(result["receipt_relative_path"]),
            ],
        )
        verification = json.loads(verified.stdout).get("result", {})
        if verification.get("verified") is not True or verification.get("decision") != "PASS":
            raise RuntimeError("installed data import verification did not pass")

        retry = _run(
            executable,
            [
                "--json",
                "data",
                "import",
                "--root",
                str(root),
                "--source",
                str(source),
                "--plan",
                "artifacts/installed-import-plan.json",
            ],
        )
        retry_result = json.loads(retry.stdout).get("result", {})
        if retry_result.get("status") != "ALREADY_IMPORTED" or retry_result.get("copy_performed") is not False:
            raise RuntimeError("installed data import retry was not deterministic and copy-free")

        inspected = _run(
            executable,
            [
                "--json",
                "data",
                "inspect",
                "--root",
                str(root),
                "--receipt",
                str(result["receipt_relative_path"]),
                "--semantic-type",
                "id=record identifier",
            ],
        )
        first_generation = json.loads(inspected.stdout).get("result", {})
        if first_generation.get("record_count") != 2 or first_generation.get("gate_0_authority_granted") is not False:
            raise RuntimeError("installed Data Desk inspection did not create a bounded two-record generation")

        second_source = base / "another-private-source-name" / "records.csv"
        second_source.parent.mkdir()
        second_source.write_text("id,value\na,1\nb,changed\nc,3\n", encoding="utf-8")
        second_plan = _run(
            executable,
            ["--json", "data", "plan", "--root", str(root), "--source", str(second_source), "--label", "smoke-records-2"],
        )
        second_plan_path = root / "artifacts" / "installed-import-plan-2.json"
        second_plan_path.write_text(second_plan.stdout, encoding="utf-8")
        second_import = _run(
            executable,
            [
                "--json", "data", "import", "--root", str(root), "--source", str(second_source),
                "--plan", "artifacts/installed-import-plan-2.json",
            ],
        )
        second_receipt = json.loads(second_import.stdout).get("result", {}).get("receipt_relative_path")
        second_inspection = _run(
            executable,
            [
                "--json", "data", "inspect", "--root", str(root), "--receipt", str(second_receipt),
                "--semantic-type", "id=record identifier",
            ],
        )
        second_generation = json.loads(second_inspection.stdout).get("result", {})

        preview = _run(
            executable,
            [
                "--json", "data", "diff", "--root", str(root),
                "--left-generation", str(first_generation["generation_id"]),
                "--right-generation", str(second_generation["generation_id"]),
                "--keys", "id",
            ],
        )
        preview_result = json.loads(preview.stdout).get("result", {})
        if preview_result.get("writes_performed") is not False or preview_result.get("summary", {}).get("modified_count") != 1:
            raise RuntimeError("installed Data Desk diff did not produce the expected no-write delta")

        reconciled = _run(
            executable,
            [
                "--json", "data", "reconcile", "--root", str(root),
                "--left-generation", str(first_generation["generation_id"]),
                "--right-generation", str(second_generation["generation_id"]),
                "--keys", "id",
            ],
        )
        reconciled_result = json.loads(reconciled.stdout).get("result", {})
        if reconciled_result.get("record_count") != 5 or reconciled_result.get("all_input_records_preserved") is not True:
            raise RuntimeError("installed Data Desk reconciliation did not preserve all five input records")
        generation_id = str(reconciled_result["generation_id"])

        generation_verified = _run(
            executable,
            ["--json", "data", "verify-generation", "--root", str(root), "--generation", generation_id],
        )
        generation_verification = json.loads(generation_verified.stdout).get("result", {})
        if generation_verification.get("verified") is not True or generation_verification.get("decision") != "PASS":
            raise RuntimeError("installed Data Desk deep generation verification did not pass")

        repeated_reconciliation = _run(
            executable,
            [
                "--json", "data", "reconcile", "--root", str(root),
                "--left-generation", str(first_generation["generation_id"]),
                "--right-generation", str(second_generation["generation_id"]),
                "--keys", "id",
            ],
        )
        repeated_id = json.loads(repeated_reconciliation.stdout).get("result", {}).get("generation_id")
        if repeated_id != generation_id:
            raise RuntimeError("installed Data Desk reconciliation retry changed generation identity")

        combined_output = "".join(
            completed.stdout
            for completed in (
                inspected, second_plan, second_import, second_inspection, preview,
                reconciled, generation_verified, repeated_reconciliation,
            )
        )
        if str(source) in combined_output or str(second_source) in combined_output or "another-private-source-name" in combined_output:
            raise RuntimeError("installed Data Desk output disclosed a private source path")

    print("installed Evidence Ingress and Data Desk smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
