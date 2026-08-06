"""Optional adapters that call external tools without entering Uriel's trust core."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, Optional, Union

from .core import Refusal, atomic_write, paths_for
from .prompts import build_prompt
from .reviews import import_review

_MODEL_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._:/-]+$")


def run_opencode(
    root: Union[str, Path],
    *,
    task: str,
    model: str,
    timeout: int = 900,
    acknowledge_external: bool = False,
) -> Dict[str, Any]:
    """Run a generated review prompt through OpenCode, then import its JSON.

    OpenCode and the selected provider are optional and untrusted.  Uriel uses
    ``shell=False`` and imports only a hash-bound JSON contract.
    """

    executable = shutil.which("opencode")
    if not executable:
        raise Refusal(
            "OpenCode was not found on PATH.",
            code="OPENCODE_NOT_FOUND",
            repairs=[
                "Install OpenCode using its current official instructions, then reopen the terminal.",
                "Run `uriel prompt {0} --provider opencode` and paste the saved prompt into any free web model.".format(task),
                "Use the deterministic offline audit without an AI review.",
            ],
        )
    if not _MODEL_RE.fullmatch(model):
        raise Refusal(
            "OpenCode model names must use provider/model format.",
            code="INVALID_OPENCODE_MODEL",
            repairs=[
                "Run `opencode models` and copy an exact provider/model identifier.",
                "Select one of OpenCode's currently listed free models if available.",
                "Omit the adapter and use the generated prompt manually.",
            ],
        )
    if timeout < 30 or timeout > 7200:
        raise Refusal("OpenCode timeout must be between 30 and 7200 seconds.", code="INVALID_TIMEOUT")
    paths = paths_for(root)
    prompt_result = build_prompt(
        paths.root,
        task=task,
        provider="opencode",
        acknowledge_external=acknowledge_external,
    )
    inbox = paths.state / "review-inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    raw_path = inbox / "opencode-{0}-{1}.txt".format(task, prompt_result["prompt_sha256"][:12])
    prompt_path = paths.root / str(prompt_result["prompt_path"])
    command = [
        executable,
        "run",
        "--model",
        model,
        "--agent",
        "uriel-reviewer",
        "--file",
        str(prompt_path),
        "Follow the attached Uriel review contract. Return only the required JSON object, with no Markdown fences or extra prose.",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=str(paths.root),
            shell=False,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise Refusal(
            "OpenCode did not finish within the configured timeout.",
            code="OPENCODE_TIMEOUT",
            details={"timeout": timeout},
            repairs=[
                "Retry one smaller claim or evidence source at a time.",
                "Choose a faster model or increase the timeout within the allowed bound.",
                "Use the saved prompt manually and import the JSON later.",
            ],
        ) from exc
    raw = completed.stdout or ""
    if completed.stderr:
        raw += "\n\n[stderr]\n" + completed.stderr
    atomic_write(raw_path, raw)
    if completed.returncode != 0:
        raise Refusal(
            "OpenCode returned a non-zero status; its output was preserved for inspection.",
            code="OPENCODE_FAILED",
            details={"return_code": completed.returncode, "output": raw_path.relative_to(paths.root).as_posix()},
            repairs=[
                "Inspect the preserved output and correct provider authentication or model selection.",
                "Run `opencode models` and retry with an available model.",
                "Use the saved prompt in a web interface instead of the adapter.",
            ],
        )
    text = completed.stdout.strip()
    # Accept plain JSON or extract exactly one fenced JSON block for resilience.
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])
        if text.lstrip().startswith("json\n"):
            text = text.lstrip()[5:]
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Refusal(
            "OpenCode did not return the required JSON object; raw output was preserved.",
            code="OPENCODE_INVALID_JSON",
            details={"output": raw_path.relative_to(paths.root).as_posix(), "error": str(exc)},
            repairs=[
                "Ask the model to return only the contract JSON with no prose or fences.",
                "Copy the useful findings into a fresh `uriel review-template` file and validate it.",
                "Use a stronger model for contract-following while keeping the same bounded task.",
            ],
        ) from exc
    json_path = inbox / "opencode-{0}-{1}.json".format(task, prompt_result["prompt_sha256"][:12])
    atomic_write(json_path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    imported = import_review(paths.root, json_path)
    return {
        "model": model,
        "task": task,
        "prompt_path": prompt_result["prompt_path"],
        "raw_output_path": raw_path.relative_to(paths.root).as_posix(),
        "review": imported,
    }
