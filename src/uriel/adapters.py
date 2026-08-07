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


def run_external_agent(
    root: Union[str, Path],
    *,
    task: str,
    agent_executable: str = "agent",
    model: str = "generic/model",
    timeout: int = 900,
    acknowledge_external: bool = False,
) -> Dict[str, Any]:
    """Run a generated review prompt through a generic external agent, then import its JSON.

    External agents are optional and untrusted. Uriel uses ``shell=False`` and imports
    only a hash-bound JSON contract.
    """
    executable = shutil.which(agent_executable)
    if not executable:
        raise Refusal(
            "External agent executable '{0}' was not found on PATH.".format(agent_executable),
            code="EXTERNAL_AGENT_NOT_FOUND",
            repairs=[
                "Install the agent executable and verify it is accessible on PATH.",
                "Run `uriel prompt {0} --provider generic` and paste the prompt into any web model.".format(task),
                "Use the deterministic offline audit without an external AI review.",
            ],
        )
    if timeout < 30 or timeout > 7200:
        raise Refusal("Timeout must be between 30 and 7200 seconds.", code="INVALID_TIMEOUT")

    paths = paths_for(root)
    prompt_result = build_prompt(
        paths.root,
        task=task,
        provider="generic",
        acknowledge_external=acknowledge_external,
    )
    inbox = paths.state / "review-inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    raw_path = inbox / "agent-{0}-{1}.txt".format(task, prompt_result["prompt_sha256"][:12])
    prompt_path = paths.root / str(prompt_result["prompt_path"])
    command = [
        executable,
        "run",
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
            "External agent did not finish within the configured timeout.",
            code="EXTERNAL_AGENT_TIMEOUT",
            details={"timeout": timeout},
            repairs=[
                "Retry one smaller claim or evidence source at a time.",
                "Use the saved prompt manually in a web model instead.",
            ],
        ) from exc

    raw = completed.stdout or ""
    if completed.stderr:
        raw += "\n\n[stderr]\n" + completed.stderr
    atomic_write(raw_path, raw)

    if completed.returncode != 0:
        raise Refusal(
            "External agent returned a non-zero status; its output was preserved for inspection.",
            code="EXTERNAL_AGENT_FAILED",
            details={"return_code": completed.returncode, "output": raw_path.relative_to(paths.root).as_posix()},
            repairs=["Inspect the preserved output and correct agent configuration."],
        )

    text = completed.stdout.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1])
        if text.lstrip().startswith("json\n"):
            text = text.lstrip()[5:]

    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise Refusal(
            "External agent did not return the required JSON object; raw output was preserved.",
            code="EXTERNAL_AGENT_INVALID_JSON",
            details={"output": raw_path.relative_to(paths.root).as_posix(), "error": str(exc)},
            repairs=["Ask the model to return only the contract JSON with no prose or fences."],
        ) from exc

    json_path = inbox / "agent-{0}-{1}.json".format(task, prompt_result["prompt_sha256"][:12])
    atomic_write(json_path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    imported = import_review(paths.root, json_path)
    return {
        "model": model,
        "task": task,
        "prompt_path": prompt_result["prompt_path"],
        "raw_output_path": raw_path.relative_to(paths.root).as_posix(),
        "review_json_path": json_path.relative_to(paths.root).as_posix(),
        "findings_count": imported["findings_count"],
    }


def run_opencode(root: Union[str, Path], *, task: str, model: str, timeout: int = 900, acknowledge_external: bool = False) -> Dict[str, Any]:
    """Deprecated alias for historical compatibility; delegates to run_external_agent."""
    return run_external_agent(root, task=task, agent_executable="agent", model=model, timeout=timeout, acknowledge_external=acknowledge_external)
