#!/usr/bin/env python3
"""Exercise the Research Verbatim Ledger through a fresh installed wheel."""
from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Dict, List


def _invoke(
    executable: Path,
    arguments: List[str],
    *,
    expected_code: int = 0,
) -> Dict[str, Any]:
    completed = subprocess.run(
        [str(executable), "--json", *arguments],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    if completed.returncode != expected_code:
        raise RuntimeError(
            "installed command returned {0}, expected {1}: {2}\n{3}".format(
                completed.returncode,
                expected_code,
                completed.stdout,
                completed.stderr,
            )
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("installed verbatim command did not return JSON") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True)
    args = parser.parse_args()
    executable = Path(args.executable).resolve(strict=True)

    with tempfile.TemporaryDirectory(
        prefix="uriel-installed-verbatim-"
    ) as temporary:
        project = Path(temporary) / "project"
        initialized = _invoke(
            executable,
            [
                "init",
                str(project),
                "--title",
                "Installed verbatim smoke",
                "--question",
                "Does exact wording survive the installed route?",
                "--privacy",
                "confidential",
            ],
        )
        if not initialized.get("result", {}).get("project_id"):
            raise RuntimeError("installed project initialization lacked identity")

        default = _invoke(
            executable,
            [
                "verbatim",
                "status",
                "--root",
                str(project),
                "--user",
                "installed-user",
            ],
        )["result"]
        if (
            default.get("mode") != "OFF"
            or default.get("entry_count") != 0
            or default.get("consent_store_exists")
            or default.get("ledger_store_exists")
        ):
            raise RuntimeError("installed verbatim default was not lazy OFF")

        offered = _invoke(
            executable,
            [
                "verbatim",
                "offer",
                "--root",
                str(project),
                "--user",
                "installed-user",
                "--signal",
                "project-baseline",
            ],
        )["result"]
        if (
            offered.get("decision") != "OFFER"
            or offered.get("verbatim_entry_created") is not False
            or offered.get("message_content_recorded") is not False
        ):
            raise RuntimeError("installed offer created or implied content capture")

        selected = _invoke(
            executable,
            [
                "verbatim",
                "consent",
                "--root",
                str(project),
                "--user",
                "installed-user",
                "--mode",
                "manual",
                "--confirm",
            ],
        )["result"]
        if selected.get("mode") != "MANUAL":
            raise RuntimeError("installed explicit mode selection failed")

        exact = "Prediction:\n  the effect remains at or below five percent."
        captured = _invoke(
            executable,
            [
                "verbatim",
                "capture",
                "--root",
                str(project),
                "--user",
                "installed-user",
                "--text",
                exact,
                "--source-ref",
                "installed-message-1",
                "--mode",
                "manual",
                "--confirm-entry",
                "--project-research",
                "--summary",
                "A bounded prediction.",
            ],
        )["result"]
        entry = captured.get("entry", {})
        entry_id = str(entry.get("entry_id", ""))
        if entry.get("exact_text") != exact or not entry_id.startswith("rvl-"):
            raise RuntimeError("installed exact capture did not round-trip")

        reviewed = _invoke(
            executable,
            [
                "verbatim",
                "review",
                "--root",
                str(project),
                "--user",
                "installed-user",
            ],
        )["result"]
        if reviewed.get("entry_count") != 1:
            raise RuntimeError("installed review did not return the isolated entry")

        drift = _invoke(
            executable,
            [
                "verbatim",
                "drift",
                "--root",
                str(project),
                "--user",
                "installed-user",
                "--entry",
                entry_id,
                "--later-text",
                "The effect is definitively above five percent.",
            ],
        )["result"]
        if (
            drift.get("scientific_proof") is not False
            or drift.get("source_text_modified") is not False
            or drift.get("persisted") is not False
        ):
            raise RuntimeError("installed drift crossed its advisory boundary")

        exported = _invoke(
            executable,
            [
                "verbatim",
                "export",
                "--root",
                str(project),
                "--user",
                "installed-user",
                "--destination",
                "exports/verbatim.json",
            ],
        )["result"]
        if exported.get("entry_count") != 1:
            raise RuntimeError("installed export lacked the selected scope")

        _invoke(
            executable,
            [
                "verbatim",
                "disable",
                "--root",
                str(project),
                "--user",
                "installed-user",
            ],
        )
        refusal = _invoke(
            executable,
            [
                "verbatim",
                "capture",
                "--root",
                str(project),
                "--user",
                "installed-user",
                "--text",
                "This must not be captured.",
                "--source-ref",
                "installed-message-2",
                "--mode",
                "manual",
                "--confirm-entry",
                "--project-research",
            ],
            expected_code=2,
        )
        if refusal.get("error", {}).get("code") != "VERBATIM_CONSENT_REQUIRED":
            raise RuntimeError("installed revoked consent did not fail closed")

        _invoke(
            executable,
            [
                "verbatim",
                "remove-entry",
                "--root",
                str(project),
                "--user",
                "installed-user",
                entry_id,
                "--confirm",
            ],
        )
        removed = _invoke(
            executable,
            [
                "verbatim",
                "remove-ledger",
                "--root",
                str(project),
                "--user",
                "installed-user",
                "--confirm",
            ],
        )["result"]
        if removed.get("removed") is not True:
            raise RuntimeError("installed whole-ledger removal did not complete")

    print("installed Research Verbatim Ledger smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
