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
        timeout=120,
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


def _run_refusal(executable: Path, arguments: List[str]) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(executable), *arguments],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if completed.returncode == 0:
        raise RuntimeError(
            "installed command unexpectedly succeeded: {0}\n{1}".format(
                " ".join(arguments), completed.stdout
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

        sort_spec_run = _run(
            executable,
            [
                "--json", "readiness", "init-sort-spec", "--root", str(root),
                "--generation", str(first_generation["generation_id"]), "--keys", "id",
            ],
        )
        sort_spec = json.loads(sort_spec_run.stdout).get("result", {})
        readiness_run = _run(
            executable,
            [
                "--json", "readiness", "check", "--root", str(root),
                "--generation", str(first_generation["generation_id"]),
                "--sort-spec", str(sort_spec["path"]),
            ],
        )
        readiness = json.loads(readiness_run.stdout).get("result", {})
        if readiness.get("receipt", {}).get("decision") != "PASS":
            raise RuntimeError("installed generation readiness did not pass")
        repeated_readiness_run = _run(
            executable,
            [
                "--json", "readiness", "check", "--root", str(root),
                "--generation", str(first_generation["generation_id"]),
                "--sort-spec", str(sort_spec["path"]),
            ],
        )
        repeated_readiness = json.loads(repeated_readiness_run.stdout).get("result", {})
        if repeated_readiness.get("receipt_sha256") != readiness.get("receipt_sha256"):
            raise RuntimeError("installed readiness repeat changed receipt identity")
        readiness_status_run = _run(
            executable,
            [
                "--json", "readiness", "status", "--root", str(root),
                "--generation", str(first_generation["generation_id"]),
            ],
        )
        readiness_state = json.loads(readiness_status_run.stdout).get("result", {})
        if readiness_state.get("decision") != "PASS" or readiness_state.get("receipt_sha256") != readiness.get("receipt_sha256"):
            raise RuntimeError("installed active readiness selection did not bind the PASS receipt")

        burst_run = _run(
            executable,
            [
                "--json", "burst", "init", "--root", str(root),
                "--generation", str(first_generation["generation_id"]),
                "--columns", "id", "value", "--row-index", "0", "--row-index", "1",
                "--row-limit", "2", "--readiness-sort-spec", str(sort_spec["path"]),
                "--readiness-receipt", str(readiness["path"]),
                "--next-task", "Check only the selected rows for transcription consistency.",
                "--budget-bytes", "4096", "--redact",
            ],
        )
        burst = json.loads(burst_run.stdout).get("result", {})
        if burst.get("verify", {}).get("verified") is not True or burst.get("selected_records") != 2:
            raise RuntimeError("installed bounded generation burst did not verify")
        capabilities = burst.get("state", {}).get("task_capabilities", {})
        if any(capabilities.get(name) != "DENIED" for name in ("network", "shell", "project_writes", "packet_writes")):
            raise RuntimeError("installed generation burst did not deny external tool authority")
        burst_verify_run = _run(
            executable,
            ["--json", "burst", "verify", "--packet", str(burst["packet"])],
        )
        if json.loads(burst_verify_run.stdout).get("result", {}).get("verified") is not True:
            raise RuntimeError("installed independent burst verification did not pass")

        audit_recheck = _run(
            executable,
            [
                "--json", "audit", "recheck", "--root", str(root),
                "--profile", "submission", "--generation", str(first_generation["generation_id"]),
                "--sort-spec", str(sort_spec["path"]),
                "--readiness-receipt", str(readiness["path"]),
            ],
        )
        gate_zero = json.loads(audit_recheck.stdout).get("result", {}).get("gates", {}).get("gates", [{}])[0]
        if gate_zero.get("gate") != 0 or gate_zero.get("decision") != "PASS":
            raise RuntimeError("installed strict audit did not consume exact generation readiness")

        stale_source = base / "stale-private-source-name" / "records.csv"
        stale_source.parent.mkdir()
        stale_source.write_text("id,value\nx,1\n", encoding="utf-8")
        stale_plan_run = _run(
            executable,
            [
                "--json", "data", "plan", "--root", str(root),
                "--source", str(stale_source), "--label", "stale-smoke",
            ],
        )
        stale_plan_path = root / "artifacts" / "installed-stale-plan.json"
        stale_plan_path.write_text(stale_plan_run.stdout, encoding="utf-8")
        stale_source.write_text("id,value\nx,changed\n", encoding="utf-8")
        stale_refusal = _run_refusal(
            executable,
            [
                "--json", "data", "import", "--root", str(root),
                "--source", str(stale_source), "--plan", "artifacts/installed-stale-plan.json",
            ],
        )
        stale_envelope = json.loads(stale_refusal.stdout)
        if (
            stale_refusal.returncode != 2
            or stale_envelope.get("status") != "REFUSED"
            or stale_envelope.get("error", {}).get("code") != "DATA_PLAN_STALE"
        ):
            raise RuntimeError("installed stale-plan path did not fail with DATA_PLAN_STALE")
        if "stale-private-source-name" in stale_refusal.stdout + stale_refusal.stderr:
            raise RuntimeError("installed stale-plan refusal disclosed the private source path")

        combined_output = "".join(
            completed.stdout
            for completed in (
                inspected, second_plan, second_import, second_inspection, preview,
                reconciled, generation_verified, repeated_reconciliation,
                sort_spec_run, readiness_run, repeated_readiness_run,
                readiness_status_run, burst_run, burst_verify_run, audit_recheck,
            )
        )
        if str(source) in combined_output or str(second_source) in combined_output or "another-private-source-name" in combined_output:
            raise RuntimeError("installed Data Desk output disclosed a private source path")

    print("installed Evidence Ingress and Data Desk smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
