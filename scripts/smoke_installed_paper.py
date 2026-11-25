#!/usr/bin/env python3
"""Exercise the research protocol, plan lock, and Paper Builder through an installed wheel."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Dict, List


def _invoke(executable: Path, arguments: List[str], *, expected_code: int = 0) -> Dict[str, Any]:
    completed = subprocess.run(
        [str(executable), "--json", *arguments],
        text=True,
        capture_output=True,
        check=False,
        timeout=180,
    )
    if completed.returncode != expected_code:
        raise RuntimeError(
            "installed command {0} returned {1}, expected {2}: {3}\n{4}".format(
                arguments[:2], completed.returncode, expected_code, completed.stdout, completed.stderr
            )
        )
    try:
        return json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("installed paper command did not return JSON") from exc


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True)
    args = parser.parse_args()
    executable = Path(args.executable).resolve(strict=True)

    with tempfile.TemporaryDirectory(prefix="uriel-installed-paper-") as temporary:
        project = Path(temporary) / "project"
        _invoke(executable, [
            "init", str(project), "--title", "Installed paper smoke",
            "--question", "Does the installed manuscript route bind every reported number?",
        ])
        root = ["--root", str(project)]

        first = _invoke(executable, ["next", *root])["result"]
        if first.get("schema") != "uriel.next_step.v1" or (first.get("stage") or {}).get("id") != "frame":
            raise RuntimeError("installed next did not start at the framing stage")
        if first.get("boundaries", {}).get("writes") != 0:
            raise RuntimeError("installed next reported writes")

        record_path = project / "uriel.project.json"
        record = json.loads(record_path.read_text(encoding="utf-8"))
        record["hypothesis"]["statement"] = "The installed route renders reported numbers only from bound artifacts."
        record["hypothesis"]["falsifier"] = "A typed number in a bound section passes the submission check."
        record["methods"]["analysis_plan"] = "Register each value with dp-add, then check and build the manuscript."
        record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        locked = _invoke(executable, ["plan", "lock", *root])["result"]
        if locked.get("status") != "LOCKED":
            raise RuntimeError("installed plan lock did not lock")
        if _invoke(executable, ["plan", "status", *root])["result"].get("state") != "CURRENT":
            raise RuntimeError("installed plan status was not CURRENT")

        (project / "make_summary.py").write_text(
            "open('artifacts/summary.csv', 'w', encoding='utf-8').write('metric,value\\nn_total,40\\nmean_rt,312.5\\n')\n",
            encoding="utf-8",
        )
        run = _invoke(executable, ["run", *root, "--", sys.executable, "make_summary.py"])["result"]
        if run.get("status") != "PASS":
            raise RuntimeError("installed workload did not pass")

        _invoke(executable, ["paper", "init", *root])
        for key, kind, fmt in (("n_total", "count", "d"), ("mean_rt", "mean", ".1f")):
            added = _invoke(executable, [
                "paper", "dp-add", *root, "--id", key, "--artifact", "artifacts/summary.csv",
                "--csv-column", "value", "--csv-row", "metric=" + key, "--kind", kind, "--format", fmt,
                "--description", "Installed smoke value " + key,
            ])["result"]["datapoint"]
            if added.get("source_token") is None or len(str(added.get("sha256", ""))) != 64:
                raise RuntimeError("installed dp-add did not bind the extracted token")

        results = project / "paper" / "sections" / "03_results.md"
        results.write_text(
            results.read_text(encoding="utf-8")
            + "We analysed {{dp:n_total}} trials with a mean reaction time of {{dp:mean_rt}} ms.\n",
            encoding="utf-8",
        )
        check = _invoke(executable, ["paper", "check", *root, "--profile", "draft"])["result"]
        if check.get("status") != "PASS" or check.get("datapoints", {}).get("verified") != 2:
            raise RuntimeError("installed draft check did not pass with two verified datapoints")
        built = _invoke(executable, ["paper", "build", *root, "--profile", "draft"])["result"]
        manuscript = (project / built["manuscript"]).read_text(encoding="utf-8")
        if "We analysed 40 trials with a mean reaction time of 312.5 ms." not in manuscript or "{{" in manuscript:
            raise RuntimeError("installed build did not render bound values")
        if not _invoke(executable, ["paper", "verify-build", *root])["result"].get("current"):
            raise RuntimeError("installed build was not current immediately after building")

        summary = project / "artifacts" / "summary.csv"
        summary.write_text(summary.read_text(encoding="utf-8").replace("40", "41"), encoding="utf-8")
        stale = _invoke(executable, ["paper", "check", *root, "--profile", "draft"], expected_code=2)["result"]
        if "DATAPOINT_ARTIFACT_STALE" not in {row["code"] for row in stale.get("findings", [])}:
            raise RuntimeError("installed check did not detect a changed artifact")
        _invoke(executable, ["paper", "verify-build", *root], expected_code=2)
        _invoke(executable, ["paper", "dp-refresh", *root, "--id", "n_total"], expected_code=2)
        _invoke(executable, ["paper", "dp-refresh", *root, "--id", "n_total", "--confirm-change"])

        draft = project / "draft.md"
        draft.write_text("Certainly! Studies have shown t(28) = 2.20, p = .36.\n", encoding="utf-8")
        lint = _invoke(executable, ["paper", "lint", *root, "--file", "draft.md"], expected_code=2)["result"]
        found = {row["code"] for row in lint.get("findings", [])}
        if not {"ASSISTANT_RESIDUE", "STAT_DECISION_INCONSISTENT"} <= found:
            raise RuntimeError("installed lint missed assistant residue or a decision inconsistency")

        prompt = _invoke(executable, ["next", *root, "--prompt", "NEXT_STEP.md"])["result"]
        if not (project / "NEXT_STEP.md").is_file() or not prompt.get("prompt_sha256"):
            raise RuntimeError("installed next did not write the prompt file")
        _invoke(executable, ["next", *root, "--prompt", "NEXT_STEP.md"], expected_code=2)

    print("installed paper smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
