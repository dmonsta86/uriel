#!/usr/bin/env python3
"""Exercise Evidence Ingress through an installed Uriel console command."""
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

    print("installed Evidence Ingress smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
