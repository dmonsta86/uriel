"""Bounded free-model AI surfaces (burst packets).

Generates small, resumable context packets for free or rate-limited models per
the free-AI workflow: one numbered instruction file, a state record, a source
manifest, bounded selected records, output requirements, an exact next prompt,
and a checksum manifest.  A burst is a read-only bounded surface: it carries
no tool authority and can never issue a Blessing.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Union

from .core import Refusal, canonical_root, guard_path, paths_for, sha256_file, sha256_text, utc_now

BURST_SCHEMA = "uriel.burst.v1"
DEFAULT_BUDGET_BYTES = 32_000

PRIVACY_NOTICE = (
    "This packet may contain unpublished or sensitive work. Review the provider's "
    "retention, training, and privacy terms. Use a local model or a provider you "
    "trust for sensitive projects. Uriel cannot guarantee a third party's handling "
    "of uploaded data."
)

HANDOFF_PHRASE = (
    "Read 00_READ_ME_FIRST.md and complete every non-blocked task. Do not ask "
    "whether to continue. Ask all unavoidable questions in one numbered batch, "
    "update the packet, write NEXT_PROMPT.txt, and stop only when complete or "
    "genuinely blocked."
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _instruction_md(packet_index: int, next_task: str, redacted: bool) -> str:
    lines = [
        "# Burst packet {0} — instructions".format(packet_index),
        "",
        "## Privacy notice",
        PRIVACY_NOTICE,
        "",
        "## What this packet contains",
        "Burst {0} is a bounded, resumable context packet for this task.".format(packet_index),
        "It contains only the records selected for this task, plus hashes and state.",
        "The AI performing this task has NO tool authority from this packet.",
        "",
        "## Task",
        next_task,
        "",
        "## Instructions (numbered)",
        "1. Read STATE.json, SOURCE_MANIFEST.json, and SELECTED_RECORDS.jsonl first.",
        "2. Report your access limits (context window, rate limits, available tools) before working.",
        "3. Perform all non-blocked work from the supplied material.",
        "4. Ask all unavoidable questions in ONE numbered batch; otherwise proceed.",
        "5. Write an updated action plan into the packet's next generation.",
        "6. Write the exact next prompt to NEXT_PROMPT.txt.",
        "7. Stop only when complete or genuinely blocked.",
        "",
        "## Hard rules",
        "- Mark every statement [OBSERVED], [INFERRED], [UNKNOWN], or [PROPOSED].",
        "- Reference direct evidence from this packet by file and hash.",
        "- Never invent citations, data, results, approvals, or novelty.",
        "- Never claim a Blessing; this surface has no authority.",
    ]
    if redacted:
        lines.append("- Record bodies were redacted: only metadata and hashes are exposed.")
    return "\n".join(lines) + "\n"


def _output_requirements_md() -> str:
    return (
        "# Output requirements\n\n"
        "1. Use the labels [OBSERVED], [INFERRED], [UNKNOWN], [PROPOSED].\n"
        "2. Cite evidence by packet file and SHA-256 hash only.\n"
        "3. Do not invent citations, quotes, data, test results, or consensus.\n"
        "4. Do not claim a Blessing or any authority over the project.\n"
        "5. End with an updated action plan and the exact next prompt in NEXT_PROMPT.txt.\n"
    )


def _read_record_body(path: Path, redact: bool) -> str:
    if redact:
        return ""
    raw = path.read_bytes()
    if len(raw) > 512_000:
        return raw[:512_000].decode("utf-8", errors="replace")
    return raw.decode("utf-8", errors="replace")


def _burst_dir(root: Path, packet_index: int) -> Path:
    return paths_for(root).state / "bursts" / "burst-{0:03d}".format(packet_index)


def _next_index(root: Path) -> int:
    bursts = paths_for(root).state / "bursts"
    if not bursts.is_dir():
        return 1
    highest = 0
    for entry in bursts.iterdir():
        match = re.fullmatch(r"burst-(\d{3})", entry.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _write_all(files: Mapping[str, str], directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    temporary: List[Path] = []
    try:
        for name, text in files.items():
            target = directory / name
            if target.exists():
                raise Refusal(
                    "Refusing to overwrite existing burst file {0}.".format(target),
                    code="BURST_OUTPUT_EXISTS",
                )
            staging = directory / (name + ".tmp")
            staging.write_bytes(text.encode("utf-8"))
            temporary.append(staging)
        for staging in temporary:
            staging.replace(directory / staging.name[: -len(".tmp")])
    except BaseException:
        for staging in temporary:
            staging.unlink(missing_ok=True)
        raise


def _write_checksums(directory: Path) -> str:
    lines: List[str] = []
    for path in sorted(directory.iterdir()):
        if path.name == "SHA256SUMS.txt":
            continue
        lines.append("{0}  {1}".format(sha256_file(path), path.name))
    manifest = "\n".join(lines) + "\n"
    (directory / "SHA256SUMS.txt").write_bytes(manifest.encode("utf-8"))
    return manifest


def verify_burst(packet_dir: Union[str, Path]) -> Dict[str, Any]:
    """Re-hash every file in a burst packet against its checksum manifest."""
    directory = Path(packet_dir).expanduser()
    if not directory.is_dir():
        raise Refusal("No burst packet at {0}.".format(directory), code="BURST_MISSING")
    sums_path = directory / "SHA256SUMS.txt"
    if not sums_path.is_file():
        raise Refusal("Burst packet has no SHA256SUMS.txt.", code="BURST_MISSING_SUMS")
    expected: Dict[str, str] = {}
    for line in sums_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            digest, _, name = line.partition("  ")
            expected[name] = digest
    mismatches: List[str] = []
    missing: List[str] = []
    for name, digest in expected.items():
        target = directory / name
        if not target.is_file():
            missing.append(name)
            continue
        if sha256_file(target) != digest:
            mismatches.append(name)
    unknown_files = [
        path.name
        for path in directory.iterdir()
        if path.name != "SHA256SUMS.txt" and path.name not in expected
    ]
    return {
        "schema": "uriel.burst_verify.v1",
        "packet": str(directory),
        "checked": len(expected),
        "missing": missing,
        "mismatched": mismatches,
        "unknown_files": unknown_files,
        "verified": not missing and not mismatches and not unknown_files,
    }


def burst_init(
    root: Union[str, Path],
    record_paths: Sequence[Union[str, Path]],
    *,
    next_task: str = "",
    budget_bytes: int = DEFAULT_BUDGET_BYTES,
    redact: bool = False,
    packet_index: Optional[int] = None,
) -> Dict[str, Any]:
    """Create the next bounded burst packet from project record files."""
    if not next_task.strip():
        raise Refusal("A next_task is required.", code="BURST_TASK_REQUIRED")
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    if packet_index is None:
        packet_index = _next_index(root_path)
    directory = _burst_dir(root_path, packet_index)

    if packet_index > 1:
        previous = _burst_dir(root_path, packet_index - 1)
        parent_state = previous / "STATE.json" if previous.is_dir() else None
    else:
        parent_state = None

    resolved: List[Path] = []
    for item in record_paths:
        target = guard_path(root_path, item, must_exist=True)
        if not target.is_file():
            raise Refusal("Not a file: {0}".format(target), code="BURST_BAD_RECORD")
        resolved.append(target)

    budget = max(1024, int(budget_bytes))
    selected: List[Dict[str, Any]] = []
    source_rows: List[Dict[str, Any]] = []
    used = 0
    for target in resolved:
        size = target.stat().st_size
        source_rows.append(
            {"name": target.relative_to(root_path).as_posix(), "bytes": size, "sha256": sha256_file(target)}
        )
        body = _read_record_body(target, redact)
        encoded = body.encode("utf-8")
        row: Dict[str, Any] = {
            "id": "rec-{0}".format(sha256_text(target.relative_to(root_path).as_posix()))[:12],
            "name": target.relative_to(root_path).as_posix(),
            "sha256": sha256_file(target),
            "bytes": len(encoded),
        }
        if redact:
            row["content"] = "[redacted: metadata only]"
            row["content_sha256"] = sha256_file(target)
        else:
            row["content_sha256"] = _digest(body)
            if used + len(encoded) <= budget:
                row["content"] = body
                used += len(encoded)
            else:
                row["content"] = "[omitted: exceeds packet budget; see source file]"
        selected.append(row)

    completed_tasks: List[str] = []
    questions_asked: List[str] = []
    if parent_state is not None and parent_state.is_file():
        prior = json.loads(parent_state.read_text(encoding="utf-8"))
        prior_tasks = prior.get("completed_tasks", [])
        if isinstance(prior_tasks, list):
            completed_tasks = [str(task) for task in prior_tasks]
        if prior.get("next_task"):
            completed_tasks.append(str(prior["next_task"]))
        prior_questions = prior.get("questions_asked", [])
        if isinstance(prior_questions, list):
            questions_asked = [str(question) for question in prior_questions]

    state: Dict[str, Any] = {
        "schema": BURST_SCHEMA,
        "packet_index": packet_index,
        "created_at_utc": utc_now(),
        "parent_packet": packet_index - 1 if packet_index > 1 else None,
        "project_generation": sha256_file(paths.project) if paths.project.is_file() else None,
        "packet_generation": _digest(json.dumps(selected, sort_keys=True)),
        "completed_tasks": completed_tasks,
        "unresolved_tasks": [next_task],
        "evidence_reviewed": [row["name"] for row in source_rows],
        "claims_reviewed": [],
        "questions_asked": questions_asked,
        "next_task": next_task,
        "redacted": bool(redact),
        "budget_bytes": budget,
        "no_authority": True,
    }

    files: Dict[str, str] = {
        "00_INSTRUCTION.md": _instruction_md(packet_index, next_task, bool(redact)),
        "STATE.json": json.dumps(state, ensure_ascii=False, sort_keys=True, indent=2) + "\n",
        "SOURCE_MANIFEST.json": json.dumps(
            {"schema": "uriel.burst_source_manifest.v1", "sources": source_rows},
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        )
        + "\n",
        "SELECTED_RECORDS.jsonl": "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in selected
        ),
        "OUTPUT_REQUIREMENTS.md": _output_requirements_md(),
        "NEXT_PROMPT.txt": HANDOFF_PHRASE + "\n",
    }
    _write_all(files, directory)
    _write_checksums(directory)
    verification = verify_burst(directory)
    return {
        "schema": "uriel.burst_result.v1",
        "packet": str(directory),
        "packet_index": packet_index,
        "files": sorted(files) + ["SHA256SUMS.txt"],
        "selected_records": len(selected),
        "bytes": used,
        "redacted": bool(redact),
        "state": state,
        "verify": verification,
        "note": "This packet is advisory and carries no authority; it cannot issue a Blessing.",
    }
