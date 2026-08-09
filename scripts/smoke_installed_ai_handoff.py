#!/usr/bin/env python3
"""Exercise prompt/review safety through a freshly installed Uriel command."""
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
                completed.returncode, completed.stdout, completed.stderr
            )
        )
    return completed


def _refusal(
    executable: Path,
    arguments: List[str],
    expected_code: str,
) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        [str(executable), *arguments],
        text=True,
        capture_output=True,
        check=False,
        timeout=120,
    )
    try:
        envelope = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError("installed refusal did not return JSON") from exc
    if (
        completed.returncode != 2
        or envelope.get("status") != "REFUSED"
        or envelope.get("error", {}).get("code") != expected_code
    ):
        raise RuntimeError(
            "installed command did not refuse with {0}: {1}".format(
                expected_code, completed.stdout
            )
        )
    return completed


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--executable", required=True)
    args = parser.parse_args()
    executable = Path(args.executable).resolve(strict=True)

    with tempfile.TemporaryDirectory(prefix="uriel-installed-ai-handoff-") as temporary:
        base = Path(temporary)
        private_root = base / "private-project"
        marker = "PRIVATE-INSTALLED-MARKER"
        _run(
            executable,
            [
                "init",
                str(private_root),
                "--title",
                marker,
                "--question",
                marker,
                "--privacy",
                "confidential",
            ],
        )
        prompt_run = _run(
            executable,
            ["--json", "prompt", "clarity", "--root", str(private_root), "--provider", "local"],
        )
        prompt_result = json.loads(prompt_run.stdout).get("result", {})
        if prompt_result.get("redacted") is not True:
            raise RuntimeError("installed nonpublic local prompt was not redacted by default")
        if prompt_result.get("prompt_bytes", 0) > prompt_result.get("maximum_prompt_bytes", -1):
            raise RuntimeError("installed prompt exceeded its declared hard budget")
        prompt_path = private_root / str(prompt_result["prompt_path"])
        prompt_text = prompt_path.read_text(encoding="utf-8")
        if marker in prompt_text or "redacted_project_projection" not in prompt_text:
            raise RuntimeError("installed nonpublic prompt projection disclosed private text")

        _refusal(
            executable,
            [
                "--json",
                "prompt",
                "clarity",
                "--root",
                str(private_root),
                "--provider",
                "generic-web",
            ],
            "EXTERNAL_AI_PRIVACY_ACK_REQUIRED",
        )
        _refusal(
            executable,
            [
                "--json",
                "assist",
                "clarity",
                "--root",
                str(private_root),
                "--model",
                "generic/test",
            ],
            "EXTERNAL_AGENT_ACK_REQUIRED",
        )

        public_root = base / "public-project"
        _run(
            executable,
            ["init", str(public_root), "--question", "Does the prompt fail before excessive usage?"],
        )
        project_path = public_root / "uriel.project.json"
        project = json.loads(project_path.read_text(encoding="utf-8"))
        project["claims"][0]["statement"] = "x" * (128 * 1024)
        project_path.write_text(
            json.dumps(project, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
            encoding="utf-8",
        )
        _refusal(
            executable,
            ["--json", "prompt", "clarity", "--root", str(public_root)],
            "PROMPT_BUDGET_EXCEEDED",
        )

        review_path = public_root / ".uriel" / "review-inbox" / "oversized.json"
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_bytes(b"{" + b" " * (128 * 1024) + b"}")
        _refusal(
            executable,
            [
                "--json",
                "review-import",
                "--root",
                str(public_root),
                ".uriel/review-inbox/oversized.json",
            ],
            "EXTERNAL_REVIEW_TOO_LARGE",
        )

    print("installed AI handoff safety smoke: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
