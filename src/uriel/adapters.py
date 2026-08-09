"""Optional, explicitly authorized adapters outside Uriel's trust core."""
from __future__ import annotations

import json
import os
import re
import shutil
import signal
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Sequence, Union

from .core import Refusal, atomic_write, paths_for, sha256_text
from .prompts import MAX_REVIEW_OUTPUT_BYTES, build_prompt
from .reviews import import_review


MIN_AGENT_TIMEOUT_SECONDS = 30
MAX_AGENT_TIMEOUT_SECONDS = 900
MAX_AGENT_OUTPUT_BYTES = MAX_REVIEW_OUTPUT_BYTES
_CAPTURE_PAYLOAD_BYTES = MAX_AGENT_OUTPUT_BYTES - 64
_MODEL_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}/[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$"
)
_SAFE_ENVIRONMENT_KEYS = (
    "PATH",
    "SystemRoot",
    "WINDIR",
    "COMSPEC",
    "PATHEXT",
    "TEMP",
    "TMP",
    "TMPDIR",
    "LANG",
    "LC_ALL",
)


@dataclass(frozen=True)
class _ProcessCapture:
    returncode: int
    stdout: str
    stderr: str


def _sanitized_environment() -> Dict[str, str]:
    """Forward only process basics, never ambient credential-like variables."""

    environment = {
        key: os.environ[key]
        for key in _SAFE_ENVIRONMENT_KEYS
        if key in os.environ and "\x00" not in os.environ[key]
    }
    environment.update(
        {
            "PYTHONIOENCODING": "utf-8",
            "URIEL_EXTERNAL_AGENT": "1",
            "URIEL_AGENT_AUTHORITY": "ADVISORY_READ_ONLY",
            "URIEL_AGENT_NETWORK_TOOLS": "DENIED_BY_INSTRUCTION",
            "URIEL_AGENT_PROJECT_WRITES": "DENIED_BY_INSTRUCTION",
        }
    )
    return environment


def _stop_process(process: subprocess.Popen[bytes]) -> None:
    """Best-effort termination of the external agent and its descendants."""

    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            completed = subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
                timeout=10,
            )
            if completed.returncode and process.poll() is None:
                process.terminate()
        else:
            os.killpg(process.pid, signal.SIGTERM)
        process.wait(timeout=5)
    except (OSError, subprocess.SubprocessError):
        try:
            if os.name == "nt":
                process.kill()
            else:
                os.killpg(process.pid, signal.SIGKILL)
        except OSError:
            pass
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass


def _run_bounded_process(
    command: Sequence[str],
    *,
    cwd: Path,
    timeout: float,
    max_output_bytes: int,
    environment: Mapping[str, str],
) -> _ProcessCapture:
    """Run without a shell while bounding time and combined captured bytes."""

    if max_output_bytes < 1 or max_output_bytes > MAX_AGENT_OUTPUT_BYTES:
        raise Refusal("Invalid external-agent output budget.", code="INVALID_AGENT_OUTPUT_BUDGET")
    popen_kwargs: Dict[str, Any] = {
        "cwd": str(cwd),
        "shell": False,
        "stdin": subprocess.DEVNULL,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.PIPE,
        "env": dict(environment),
    }
    if os.name == "nt":
        popen_kwargs["creationflags"] = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    else:
        popen_kwargs["start_new_session"] = True
    process: subprocess.Popen[bytes] = subprocess.Popen(list(command), **popen_kwargs)
    assert process.stdout is not None and process.stderr is not None

    buffers = {"stdout": bytearray(), "stderr": bytearray()}
    captured_total = [0]
    output_exceeded = threading.Event()
    reader_failed = threading.Event()
    lock = threading.Lock()

    def consume(name: str, stream: Any) -> None:
        try:
            while True:
                block = stream.read(16 * 1024)
                if not block:
                    break
                with lock:
                    remaining = max_output_bytes - captured_total[0]
                    if remaining > 0:
                        accepted = block[:remaining]
                        buffers[name].extend(accepted)
                        captured_total[0] += len(accepted)
                    if len(block) > max(remaining, 0):
                        output_exceeded.set()
        except OSError:
            reader_failed.set()

    readers = [
        threading.Thread(target=consume, args=("stdout", process.stdout), daemon=True),
        threading.Thread(target=consume, args=("stderr", process.stderr), daemon=True),
    ]
    for reader in readers:
        reader.start()

    deadline = time.monotonic() + timeout
    timed_out = False
    try:
        while process.poll() is None:
            if output_exceeded.is_set():
                _stop_process(process)
                break
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                _stop_process(process)
                break
            try:
                process.wait(timeout=min(0.025, remaining))
            except subprocess.TimeoutExpired:
                pass
    except BaseException:
        _stop_process(process)
        raise
    finally:
        if process.poll() is None:
            _stop_process(process)
        for reader in readers:
            reader.join(timeout=5)
        for stream in (process.stdout, process.stderr):
            try:
                stream.close()
            except OSError:
                reader_failed.set()

    if timed_out:
        raise Refusal(
            "External agent did not finish within the configured timeout.",
            code="EXTERNAL_AGENT_TIMEOUT",
            details={"timeout": timeout},
            repairs=[
                "Retry one smaller claim or evidence source at a time.",
                "Use the saved bounded prompt manually in an authorized model session.",
                "Complete the review with Uriel's deterministic audit and a human reviewer.",
            ],
        )
    if output_exceeded.is_set():
        raise Refusal(
            "External agent exceeded Uriel's hard captured-output budget and was stopped.",
            code="EXTERNAL_AGENT_OUTPUT_LIMIT",
            details={"maximum_bytes": max_output_bytes},
            repairs=[
                "Retry with one narrower claim and request compact JSON.",
                "Use a bounded burst whose output request is smaller than the hard ceiling.",
                "Inspect the task manually without importing the oversized response.",
            ],
        )
    if reader_failed.is_set():
        raise Refusal("External agent output could not be read safely.", code="EXTERNAL_AGENT_CAPTURE_FAILED")
    return _ProcessCapture(
        returncode=int(process.returncode or 0),
        stdout=bytes(buffers["stdout"]).decode("utf-8", errors="replace"),
        stderr=bytes(buffers["stderr"]).decode("utf-8", errors="replace"),
    )


def _validate_model(model: str) -> None:
    if (
        not isinstance(model, str)
        or _MODEL_RE.fullmatch(model) is None
        or ".." in model
        or "//" in model
        or model.endswith("/")
    ):
        raise Refusal(
            "Model must be one bounded provider/model identifier.",
            code="INVALID_AGENT_MODEL",
            details={"maximum_characters": 193},
        )


def run_external_agent(
    root: Union[str, Path],
    *,
    task: str,
    agent_executable: str = "agent",
    model: str = "generic/model",
    timeout: int = 900,
    acknowledge_external: bool = False,
) -> Dict[str, Any]:
    """Run one bounded prompt through an explicitly authorized external process.

    This reduces accidental exposure with an isolated working directory,
    minimized environment, no shell, hard time/output ceilings, and exact
    review binding. It is not an operating-system sandbox and does not prevent
    provider transport performed by the selected executable.
    """

    if not acknowledge_external:
        raise Refusal(
            "Running an external agent requires explicit acknowledgement of process, provider, privacy, and cost risk.",
            code="EXTERNAL_AGENT_ACK_REQUIRED",
            repairs=[
                "Generate a redacted prompt only and inspect it before any manual upload.",
                "Use Uriel's deterministic offline audit without an AI process.",
                "Rerun with `--acknowledge-external` only after authorizing the executable, model, material, and provider terms.",
            ],
        )
    _validate_model(model)
    if timeout < MIN_AGENT_TIMEOUT_SECONDS or timeout > MAX_AGENT_TIMEOUT_SECONDS:
        raise Refusal(
            "Timeout must be between 30 and 900 seconds.",
            code="INVALID_TIMEOUT",
            details={"minimum_seconds": MIN_AGENT_TIMEOUT_SECONDS, "maximum_seconds": MAX_AGENT_TIMEOUT_SECONDS},
        )
    executable = shutil.which(agent_executable)
    if not executable:
        raise Refusal(
            "External agent executable '{0}' was not found on PATH.".format(agent_executable),
            code="EXTERNAL_AGENT_NOT_FOUND",
            repairs=[
                "Install the explicitly chosen agent executable and verify it is accessible on PATH.",
                "Generate a bounded prompt and use it manually in an authorized model session.",
                "Use the deterministic offline audit without an external AI review.",
            ],
        )

    paths = paths_for(root)
    prompt_result = build_prompt(
        paths.root,
        task=task,
        provider="generic-web",
        model=model,
        acknowledge_external=True,
    )
    prompt_path = paths.root / str(prompt_result["prompt_path"])
    instruction = (
        "Use only the attached Uriel prompt. Do not browse, run shell commands, access unrelated files, or write project files. "
        "Provider transport needed to invoke the selected model is operator-authorized but no additional model tools are authorized. "
        "Return only the required JSON object and stay below {0} UTF-8 bytes."
    ).format(MAX_AGENT_OUTPUT_BYTES)
    with tempfile.TemporaryDirectory(prefix="uriel-external-agent-") as temporary:
        isolated_root = Path(temporary)
        isolated_prompt = isolated_root / "URIEL_REVIEW_PROMPT.md"
        isolated_prompt.write_bytes(prompt_path.read_bytes())
        command = [
            executable,
            "run",
            "--model",
            model,
            "--file",
            str(isolated_prompt),
            instruction,
        ]
        completed = _run_bounded_process(
            command,
            cwd=isolated_root,
            timeout=float(timeout),
            max_output_bytes=_CAPTURE_PAYLOAD_BYTES,
            environment=_sanitized_environment(),
        )

    inbox = paths.state / "review-inbox"
    inbox.mkdir(parents=True, exist_ok=True)
    raw = completed.stdout or ""
    if completed.stderr:
        raw += "\n\n[stderr]\n" + completed.stderr
    raw_encoded = raw.encode("utf-8")
    raw_truncated = len(raw_encoded) > MAX_AGENT_OUTPUT_BYTES
    if raw_truncated:
        raw = raw_encoded[:MAX_AGENT_OUTPUT_BYTES].decode("utf-8", errors="ignore")
    raw_digest = sha256_text(raw)
    raw_path = inbox / "agent-{0}-{1}-{2}.txt".format(
        task, prompt_result["prompt_sha256"][:12], raw_digest[:12]
    )
    atomic_write(raw_path, raw)

    if completed.returncode != 0:
        raise Refusal(
            "External agent returned a non-zero status; its bounded output was preserved for inspection.",
            code="EXTERNAL_AGENT_FAILED",
            details={
                "return_code": completed.returncode,
                "output": raw_path.relative_to(paths.root).as_posix(),
                "raw_output_truncated": raw_truncated,
            },
            repairs=[
                "Inspect the preserved bounded output and correct the explicit agent configuration.",
                "Retry with one smaller task after confirming the selected model identifier.",
                "Use the saved prompt manually or complete the review without an external agent.",
            ],
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
            "External agent did not return the required JSON object; bounded raw output was preserved.",
            code="EXTERNAL_AGENT_INVALID_JSON",
            details={"output": raw_path.relative_to(paths.root).as_posix(), "error": str(exc)},
            repairs=[
                "Ask the model to return only the contract JSON with no prose or fences.",
                "Retry one smaller review task with the same bound prompt.",
                "Correct the JSON manually without inventing or deleting findings, then import it separately.",
            ],
        ) from exc
    if not isinstance(value, Mapping):
        raise Refusal("External agent output must be one JSON object.", code="EXTERNAL_AGENT_INVALID_JSON")
    if (
        value.get("reviewer_type") != "ai"
        or value.get("provider") != "generic-web"
        or value.get("model") != model
    ):
        raise Refusal(
            "External review identity does not match the invoked provider/model binding.",
            code="EXTERNAL_AGENT_IDENTITY_MISMATCH",
            details={"expected_provider": "generic-web", "expected_model": model},
        )

    canonical = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n"
    canonical_bytes = len(canonical.encode("utf-8"))
    if canonical_bytes > MAX_AGENT_OUTPUT_BYTES:
        raise Refusal(
            "Normalized external review exceeds Uriel's hard import budget.",
            code="EXTERNAL_AGENT_NORMALIZED_OUTPUT_LIMIT",
            details={"review_bytes": canonical_bytes, "maximum_bytes": MAX_AGENT_OUTPUT_BYTES},
        )
    json_digest = sha256_text(canonical)
    json_path = inbox / "agent-{0}-{1}-{2}.json".format(
        task, prompt_result["prompt_sha256"][:12], json_digest[:12]
    )
    atomic_write(json_path, canonical)
    imported = import_review(paths.root, json_path)
    return {
        "model": model,
        "provider": "generic-web",
        "task": task,
        "prompt_path": prompt_result["prompt_path"],
        "prompt_bytes": prompt_result["prompt_bytes"],
        "raw_output_path": raw_path.relative_to(paths.root).as_posix(),
        "raw_output_truncated": raw_truncated,
        "review_json_path": json_path.relative_to(paths.root).as_posix(),
        "finding_count": imported["finding_count"],
        "authority": "ADVISORY_ONLY",
        "controls": {
            "shell": "DENIED",
            "working_directory": "ISOLATED_TEMPORARY",
            "ambient_credentials": "NOT_FORWARDED",
            "model_tool_network": "DENIED_BY_INSTRUCTION",
            "project_writes": "DENIED_BY_INSTRUCTION",
            "os_sandbox": False,
            "maximum_output_bytes": MAX_AGENT_OUTPUT_BYTES,
            "timeout_seconds": timeout,
        },
    }


def run_opencode(
    root: Union[str, Path],
    *,
    task: str,
    model: str,
    timeout: int = 900,
    acknowledge_external: bool = False,
) -> Dict[str, Any]:
    """Deprecated compatibility alias; delegates to the bounded adapter."""

    return run_external_agent(
        root,
        task=task,
        agent_executable="agent",
        model=model,
        timeout=timeout,
        acknowledge_external=acknowledge_external,
    )
