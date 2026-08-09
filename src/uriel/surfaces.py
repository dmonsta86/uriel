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

from .core import Refusal, atomic_write, canonical_json, canonical_root, guard_path, is_reparse_or_link, paths_for, sha256_file, sha256_text, utc_now
from .data_desk import MAX_AI_SURFACE_BYTES, project_verified_data_generation
from .generation_readiness import require_generation_readiness

BURST_SCHEMA = "uriel.burst.v1"
AI_SURFACE_SCHEMA = "uriel.ai_surface.v1"
DEFAULT_BUDGET_BYTES = 32_000
MAX_BURST_RECORD_FILES = 100
MAX_BURST_PACKETS = 100
MAX_BURST_TASK_BYTES = 16 * 1024
MAX_BURST_PACKET_BYTES = MAX_AI_SURFACE_BYTES + 128 * 1024
MAX_BURST_SOURCE_FILE_BYTES = 16 * 1024 * 1024
MAX_BURST_SOURCE_TOTAL_BYTES = 64 * 1024 * 1024
MAX_BURST_OUTPUT_BYTES = 128 * 1024
MAX_BURST_WALL_TIME_SECONDS = 15 * 60
REQUIRED_BURST_FILES = frozenset(
    {
        "00_INSTRUCTION.md",
        "STATE.json",
        "SOURCE_MANIFEST.json",
        "SELECTED_RECORDS.jsonl",
        "OUTPUT_REQUIREMENTS.md",
        "NEXT_PROMPT.txt",
    }
)
OPTIONAL_BURST_FILES = frozenset({"AI_SURFACE.json"})
_CHECKSUM_LINE = re.compile(r"^([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._-]{0,127})$")

PRIVACY_NOTICE = (
    "This packet may contain unpublished or sensitive work. Review the provider's "
    "retention, training, and privacy terms. Use a local model or a provider you "
    "trust for sensitive projects. Uriel cannot guarantee a third party's handling "
    "of uploaded data."
)

HANDOFF_PHRASE = (
    "Read 00_INSTRUCTION.md and complete every non-blocked task in advisory "
    "read-only mode. Do not ask whether to continue. Ask all unavoidable "
    "questions in one numbered batch, return an updated action plan and exact "
    "next prompt as labeled output, and stop only when complete or genuinely blocked."
)

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
TASK_CAPABILITIES = {
    "mode": "ADVISORY_READ_ONLY",
    "network": "DENIED",
    "shell": "DENIED",
    "project_writes": "DENIED",
    "packet_writes": "DENIED",
    "max_output_bytes": MAX_BURST_OUTPUT_BYTES,
    "max_wall_time_seconds": MAX_BURST_WALL_TIME_SECONDS,
}


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _selected_records_jsonl(selected: Sequence[Mapping[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
        for row in selected
    )


def _selected_from_projection(
    generation_id: str,
    projection: Mapping[str, Any],
    *,
    redact: bool,
) -> List[Dict[str, Any]]:
    selected: List[Dict[str, Any]] = []
    for projected in projection["records"]:
        row_index = int(projected["source_row_index"])
        selected.append(
            {
                "id": "row-{0}-{1}".format(row_index, projected["record_sha256"][:12]),
                "name": "data-generation:{0}:row:{1}".format(generation_id, row_index),
                "sha256": projected["record_sha256"],
                "content_sha256": sha256_text(canonical_json(projected)),
                "bytes": len(canonical_json(projected).encode("utf-8")),
                "content": (
                    "[redacted: selected row values withheld; identity and hashes only]"
                    if redact
                    else projected["values"]
                ),
                "source_row_index": row_index,
                "selected_column_ids": projected["selected_column_ids"],
            }
        )
    return selected


def _packet_bytes(files: Mapping[str, str]) -> int:
    payload = sum(len(text.encode("utf-8")) for text in files.values())
    checksum_manifest = "".join(
        "{0}  {1}\n".format("0" * 64, name) for name in sorted(files)
    )
    return payload + len(checksum_manifest.encode("utf-8"))


def _json_no_duplicates(text: str) -> Any:
    def pairs(items):
        value: Dict[str, Any] = {}
        for key, child in items:
            if key in value:
                raise ValueError("duplicate JSON key: {0}".format(key))
            value[key] = child
        return value

    return json.loads(text, object_pairs_hook=pairs)


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
        "5. Return an updated action plan as a labeled output section.",
        "6. Return the exact next prompt as a labeled output section.",
        "7. Stop only when complete or genuinely blocked.",
        "",
        "## Hard rules",
        "- Mark every statement [OBSERVED], [INFERRED], [UNKNOWN], or [PROPOSED].",
        "- Reference direct evidence from this packet by file and hash.",
        "- Never invent citations, data, results, approvals, or novelty.",
        "- Never claim a Blessing; this surface has no authority.",
        "- Treat this task as advisory and read-only: no network, shell, packet writes, or project writes.",
        "- Return at most {0} UTF-8 bytes and stop after {1} seconds of wall time.".format(
            MAX_BURST_OUTPUT_BYTES, MAX_BURST_WALL_TIME_SECONDS
        ),
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
        "5. Do not use network, shell, or file-writing tools; return advisory output only.\n"
        "6. Keep the returned output within 128 KiB and 15 minutes of wall time.\n"
        "7. End with an updated action plan and the exact next prompt as a labeled output section.\n"
    )


def _read_record_body(path: Path, redact: bool) -> str:
    if redact:
        return ""
    with path.open("rb") as stream:
        raw = stream.read(512_001)
    if len(raw) > 512_000:
        return raw[:512_000].decode("utf-8", errors="replace")
    return raw.decode("utf-8", errors="replace")


def _burst_dir(root: Path, packet_index: int) -> Path:
    return paths_for(root).state / "bursts" / "burst-{0:03d}".format(packet_index)


def _next_index(root: Path) -> int:
    bursts = guard_path(root, paths_for(root).state / "bursts")
    if not bursts.is_dir():
        return 1
    guard_path(root, bursts, must_exist=True)
    highest = 0
    for entry in bursts.iterdir():
        match = re.fullmatch(r"burst-(\d{3})", entry.name)
        if match:
            highest = max(highest, int(match.group(1)))
    return highest + 1


def _write_all(root: Path, files: Mapping[str, str], directory: Path) -> None:
    directory = guard_path(root, directory)
    guard_path(root, directory.parent)
    if directory.exists() and any(directory.iterdir()):
        raise Refusal(
            "Refusing to adopt or overwrite a nonempty burst directory.",
            code="BURST_OUTPUT_EXISTS",
            details={"directory": str(directory)},
        )
    directory.mkdir(parents=True, exist_ok=True)
    directory = guard_path(root, directory, must_exist=True)
    if is_reparse_or_link(directory):
        raise Refusal(
            "Burst output directories may not be links or reparse points.",
            code="BURST_LINK_REFUSED",
        )
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
            with staging.open("xb") as stream:
                stream.write(text.encode("utf-8"))
            temporary.append(staging)
        for staging in temporary:
            staging.replace(directory / staging.name[: -len(".tmp")])
    except BaseException:
        for staging in temporary:
            staging.unlink(missing_ok=True)
        raise


def _write_checksums(root: Path, directory: Path) -> str:
    directory = guard_path(root, directory, must_exist=True)
    lines: List[str] = []
    for path in sorted(directory.iterdir()):
        if path.name == "SHA256SUMS.txt":
            continue
        guard_path(root, path, must_exist=True)
        if is_reparse_or_link(path) or not path.is_file():
            raise Refusal("Burst members must be regular project-local files.", code="BURST_LINK_REFUSED")
        lines.append("{0}  {1}".format(sha256_file(path), path.name))
    manifest = "\n".join(lines) + "\n"
    atomic_write(directory / "SHA256SUMS.txt", manifest)
    return manifest


def verify_burst(packet_dir: Union[str, Path]) -> Dict[str, Any]:
    """Verify exact membership, chained hashes, bounded work, and semantics."""
    return _verify_burst(Path(packet_dir).expanduser().absolute(), verify_live_generation=True)


def _verify_burst(directory: Path, *, verify_live_generation: bool) -> Dict[str, Any]:
    if not directory.is_dir():
        raise Refusal("No burst packet at {0}.".format(directory), code="BURST_MISSING")
    if is_reparse_or_link(directory):
        raise Refusal("Burst packet directories may not be links or reparse points.", code="BURST_LINK_REFUSED")
    sums_path = directory / "SHA256SUMS.txt"
    if not sums_path.is_file():
        raise Refusal("Burst packet has no SHA256SUMS.txt.", code="BURST_MISSING_SUMS")
    if is_reparse_or_link(sums_path):
        raise Refusal("The burst checksum manifest may not be a link.", code="BURST_LINK_REFUSED")
    if sums_path.stat().st_size > 64 * 1024:
        raise Refusal("The burst checksum manifest exceeds its hard size ceiling.", code="BURST_SUMS_INVALID")
    packet_sha256 = sha256_file(sums_path)

    expected: Dict[str, str] = {}
    manifest_errors: List[str] = []
    try:
        checksum_lines = sums_path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise Refusal("The burst checksum manifest is unreadable.", code="BURST_SUMS_INVALID") from exc
    for line_number, line in enumerate(checksum_lines, start=1):
        if not line.strip():
            continue
        match = _CHECKSUM_LINE.fullmatch(line)
        if match is None:
            manifest_errors.append("invalid checksum line {0}".format(line_number))
            continue
        digest, name = match.groups()
        if name == "SHA256SUMS.txt":
            manifest_errors.append("checksum manifest must not list itself")
        elif name in expected:
            manifest_errors.append("duplicate checksum member: {0}".format(name))
        else:
            expected[name] = digest

    entries: List[Path] = []
    directory_entry_overflow = False
    for index, entry in enumerate(directory.iterdir()):
        if index >= 32:
            directory_entry_overflow = True
            break
        entries.append(entry)
    semantic_errors: List[str] = []
    if directory_entry_overflow:
        semantic_errors.append("burst directory exceeds the 32-entry inspection ceiling")
    packet_bytes = sum(
        path.stat().st_size
        for path in entries
        if path.is_file() and not is_reparse_or_link(path)
    )
    if packet_bytes > MAX_BURST_PACKET_BYTES:
        semantic_errors.append(
            "packet bytes {0} exceed {1}".format(packet_bytes, MAX_BURST_PACKET_BYTES)
        )

    declared = set(expected)
    missing_members = sorted(REQUIRED_BURST_FILES - declared)
    unexpected_manifest_files = sorted(declared - REQUIRED_BURST_FILES - OPTIONAL_BURST_FILES)
    mismatches: List[str] = []
    missing: List[str] = []
    link_files: List[str] = []
    for name, digest in expected.items():
        target = directory / name
        if not target.is_file():
            missing.append(name)
        elif is_reparse_or_link(target):
            link_files.append(name)
        elif target.stat().st_size > MAX_BURST_PACKET_BYTES:
            mismatches.append(name)
            semantic_errors.append("{0} exceeds the per-member byte ceiling".format(name))
        elif sha256_file(target) != digest:
            mismatches.append(name)
    unknown_files = [
        path.name
        for path in entries
        if path.name != "SHA256SUMS.txt" and path.name not in expected
    ]

    def load_member_json(name: str) -> Optional[Mapping[str, Any]]:
        if name in missing or name in mismatches or name in link_files:
            return None
        try:
            value = _json_no_duplicates((directory / name).read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError):
            semantic_errors.append("{0} is unreadable JSON".format(name))
            return None
        if not isinstance(value, Mapping):
            semantic_errors.append("{0} must contain one JSON object".format(name))
            return None
        return value

    state = load_member_json("STATE.json")
    source_manifest = load_member_json("SOURCE_MANIFEST.json")
    if source_manifest is not None and (
        source_manifest.get("schema") != "uriel.burst_source_manifest.v1"
        or not isinstance(source_manifest.get("sources"), list)
    ):
        semantic_errors.append("SOURCE_MANIFEST.json has an invalid structure")

    selected_rows: List[Mapping[str, Any]] = []
    selected_path = directory / "SELECTED_RECORDS.jsonl"
    if "SELECTED_RECORDS.jsonl" not in missing and "SELECTED_RECORDS.jsonl" not in mismatches and "SELECTED_RECORDS.jsonl" not in link_files:
        try:
            selected_lines = [line for line in selected_path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, UnicodeDecodeError):
            selected_lines = []
            semantic_errors.append("SELECTED_RECORDS.jsonl is unreadable")
        for line_number, line in enumerate(selected_lines, start=1):
            try:
                row = _json_no_duplicates(line)
            except (json.JSONDecodeError, ValueError):
                semantic_errors.append("selected record line {0} is invalid JSON".format(line_number))
                continue
            if not isinstance(row, Mapping):
                semantic_errors.append("selected record line {0} is not an object".format(line_number))
                continue
            selected_rows.append(row)

    generation_mode = bool(state and state.get("data_generation_id"))
    if generation_mode and "AI_SURFACE.json" not in declared:
        missing_members.append("AI_SURFACE.json")
    if not generation_mode and "AI_SURFACE.json" in declared:
        unexpected_manifest_files.append("AI_SURFACE.json")

    packet_index: Optional[int] = None
    if state is not None:
        if state.get("schema") != BURST_SCHEMA:
            semantic_errors.append("STATE.json has the wrong schema")
        if state.get("no_authority") is not True:
            semantic_errors.append("STATE.json must declare no_authority=true")
        if state.get("task_capabilities") != TASK_CAPABILITIES:
            semantic_errors.append("STATE.json does not carry the exact read-only task capabilities")
        packet_index_value = state.get("packet_index")
        if (
            not isinstance(packet_index_value, int)
            or isinstance(packet_index_value, bool)
            or not 1 <= packet_index_value <= MAX_BURST_PACKETS
        ):
            semantic_errors.append("STATE.json has an invalid packet index")
        else:
            packet_index = packet_index_value
            if directory.name != "burst-{0:03d}".format(packet_index):
                semantic_errors.append("burst directory name and STATE.json index disagree")
        task = state.get("next_task")
        if not isinstance(task, str) or not task.strip():
            semantic_errors.append("STATE.json requires one bounded next_task")
        elif len(task.encode("utf-8")) > MAX_BURST_TASK_BYTES:
            semantic_errors.append("STATE.json next_task exceeds the task budget")
        budget = state.get("budget_bytes")
        if not isinstance(budget, int) or isinstance(budget, bool) or not 1024 <= budget <= MAX_AI_SURFACE_BYTES:
            semantic_errors.append("STATE.json has an invalid byte budget")
        else:
            if selected_path.is_file() and selected_path.stat().st_size > budget:
                semantic_errors.append("SELECTED_RECORDS.jsonl exceeds the declared byte budget")
            if selected_path.is_file():
                selected_size = selected_path.stat().st_size
                if state.get("selected_records_bytes") != selected_size:
                    semantic_errors.append("selected-record byte count does not match STATE.json")
                if state.get("packet_generation") != sha256_file(selected_path):
                    semantic_errors.append("selected-record hash does not match STATE.json")
        if isinstance(task, str) and state.get("task_bytes") != len(task.encode("utf-8")):
            semantic_errors.append("task byte count does not match STATE.json")
        if state.get("packet_byte_limit") != MAX_BURST_PACKET_BYTES:
            semantic_errors.append("STATE.json has the wrong packet byte ceiling")

        if packet_index == 1:
            if state.get("parent_packet") is not None or state.get("parent_packet_sha256") is not None:
                semantic_errors.append("the first burst packet must have no parent")
        elif packet_index is not None:
            parent_digest = state.get("parent_packet_sha256")
            if state.get("parent_packet") != packet_index - 1 or not isinstance(parent_digest, str) or _HEX64.fullmatch(parent_digest) is None:
                semantic_errors.append("STATE.json has an invalid parent packet binding")
            else:
                previous = directory.parent / "burst-{0:03d}".format(packet_index - 1)
                try:
                    parent_check = _verify_burst(previous, verify_live_generation=False)
                except Refusal as exc:
                    semantic_errors.append("parent burst verification refused: {0}".format(exc.code))
                else:
                    if not parent_check.get("verified"):
                        semantic_errors.append("parent burst packet does not verify")
                    if parent_check.get("packet_sha256") != parent_digest:
                        semantic_errors.append("parent burst packet hash does not match STATE.json")

        if isinstance(task, str) and packet_index is not None:
            instruction_path = directory / "00_INSTRUCTION.md"
            try:
                if instruction_path.read_text(encoding="utf-8") != _instruction_md(packet_index, task, bool(state.get("redacted"))):
                    semantic_errors.append("00_INSTRUCTION.md does not match the sealed task contract")
            except (OSError, UnicodeDecodeError):
                semantic_errors.append("instruction file is unreadable")

        if generation_mode:
            generation_id = str(state.get("data_generation_id"))
            row_limit = state.get("row_limit")
            row_indices = state.get("selected_row_indices")
            selected_columns = state.get("selected_columns")
            if not isinstance(row_limit, int) or isinstance(row_limit, bool) or not 1 <= row_limit <= 1000:
                semantic_errors.append("STATE.json has an invalid generation row limit")
            if not isinstance(row_indices, list) or any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in row_indices):
                semantic_errors.append("STATE.json has invalid selected row indices")
                row_indices = []
            if not isinstance(selected_columns, list) or any(not isinstance(value, Mapping) for value in selected_columns):
                semantic_errors.append("STATE.json has invalid selected columns")
                selected_columns = []
            column_ids = [str(value.get("column_id", "")) for value in selected_columns]
            if len(selected_rows) > (row_limit if isinstance(row_limit, int) else 0):
                semantic_errors.append("selected record count exceeds the generation row limit")
            if [row.get("source_row_index") for row in selected_rows] != row_indices:
                semantic_errors.append("selected record order does not match STATE.json")

            projected_rows: List[Dict[str, Any]] = []
            for position, row in enumerate(selected_rows):
                row_index = row.get("source_row_index")
                row_columns = row.get("selected_column_ids")
                record_sha = row.get("sha256")
                if (
                    not isinstance(row_index, int)
                    or isinstance(row_index, bool)
                    or row_columns != column_ids
                    or not isinstance(record_sha, str)
                    or _HEX64.fullmatch(record_sha) is None
                ):
                    semantic_errors.append("selected record {0} has an invalid generation binding".format(position))
                    continue
                projected: Dict[str, Any] = {
                    "source_row_index": row_index,
                    "record_sha256": record_sha,
                    "selected_column_ids": column_ids,
                    "values_redacted": bool(state.get("redacted")),
                }
                if state.get("redacted"):
                    if row.get("content") != "[redacted: selected row values withheld; identity and hashes only]":
                        semantic_errors.append("a redacted selected record exposes unexpected content")
                elif not isinstance(row.get("content"), Mapping):
                    semantic_errors.append("an unredacted selected record has invalid values")
                    continue
                else:
                    projected["values"] = row.get("content")
                projected_digest = sha256_text(canonical_json(projected))
                if row.get("content_sha256") != projected_digest:
                    semantic_errors.append("a selected record projection hash is invalid")
                if row.get("bytes") != len(canonical_json(projected).encode("utf-8")):
                    semantic_errors.append("a selected record projection byte count is invalid")
                projected_rows.append(projected)
            projected_digest = sha256_text(canonical_json(projected_rows))

            ai_surface = load_member_json("AI_SURFACE.json")
            if ai_surface is not None:
                surface_core = {
                    "project_generation": generation_id,
                    "allowed_task": state.get("next_task"),
                    "row_limit": row_limit,
                    "byte_limit": state.get("budget_bytes"),
                    "redaction_policy": (
                        "VALUES_REDACTED_METADATA_AND_HASHES_ONLY"
                        if state.get("redacted")
                        else "EXPLICIT_ROWS_AND_COLUMNS_ONLY"
                    ),
                    "records_sha256": projected_digest,
                    "source_manifest_sha256": ai_surface.get("source_manifest_sha256"),
                    "acceptance_receipt": state.get("data_readiness_receipt_sha256"),
                    "no_authority": True,
                }
                if ai_surface.get("schema") != AI_SURFACE_SCHEMA:
                    semantic_errors.append("AI_SURFACE.json has the wrong schema")
                for key, value in surface_core.items():
                    if ai_surface.get(key) != value:
                        semantic_errors.append("AI surface {0} does not match the sealed projection".format(key))
                if ai_surface.get("surface_id") != "surface-" + sha256_text(canonical_json(surface_core))[:24]:
                    semantic_errors.append("AI surface identity is invalid")
                receipt_sha = ai_surface.get("acceptance_receipt")
                if not isinstance(receipt_sha, str) or _HEX64.fullmatch(receipt_sha) is None:
                    semantic_errors.append("AI surface receipt is not a SHA-256 identity")

            sources = source_manifest.get("sources") if source_manifest is not None else None
            if not isinstance(sources, list) or len(sources) != 1 or not isinstance(sources[0], Mapping):
                semantic_errors.append("generation burst source manifest must contain exactly one source")
            else:
                source = sources[0]
                if source.get("name") != "data-generation:{0}".format(generation_id):
                    semantic_errors.append("generation source name is invalid")
                if source.get("selected_row_indices") != row_indices or source.get("selected_columns") != selected_columns:
                    semantic_errors.append("generation source selection does not match STATE.json")
                if ai_surface is not None and source.get("generation_manifest_sha256") != ai_surface.get("source_manifest_sha256"):
                    semantic_errors.append("AI surface and source manifest bind different generations")

            if verify_live_generation and isinstance(row_limit, int) and row_indices and column_ids:
                if directory.parent.name != "bursts" or directory.parent.parent.name != ".uriel":
                    semantic_errors.append("generation burst is detached from its canonical project")
                else:
                    project_root = directory.parent.parent.parent
                    try:
                        canonical = canonical_root(project_root)
                        if _burst_dir(canonical, packet_index or 0) != directory:
                            raise Refusal("Burst path is not canonical.", code="BURST_PATH_INVALID")
                        live_status = require_generation_readiness(canonical, generation_id)
                        live_projection = project_verified_data_generation(
                            canonical,
                            generation_id,
                            columns=column_ids,
                            row_indices=row_indices,
                            row_limit=row_limit,
                            byte_limit=int(state.get("budget_bytes")),
                            redact=bool(state.get("redacted")),
                        )
                    except (Refusal, OSError, ValueError) as exc:
                        semantic_errors.append("live generation verification failed closed: {0}".format(exc))
                    else:
                        if live_status.get("receipt_sha256") != state.get("data_readiness_receipt_sha256"):
                            semantic_errors.append("live readiness receipt differs from STATE.json")
                        live_receipt = live_status.get("receipt")
                        if not isinstance(live_receipt, Mapping) or live_receipt.get("binding_digest") != state.get("data_readiness_binding_digest"):
                            semantic_errors.append("live readiness binding differs from STATE.json")
                        if _selected_from_projection(generation_id, live_projection, redact=bool(state.get("redacted"))) != selected_rows:
                            semantic_errors.append("selected records differ from the live verified generation")
                        if ai_surface is not None and (
                            live_projection.get("records_sha256") != ai_surface.get("records_sha256")
                            or live_projection.get("generation_manifest_sha256") != ai_surface.get("source_manifest_sha256")
                        ):
                            semantic_errors.append("AI surface differs from the live verified generation")

    output_path = directory / "OUTPUT_REQUIREMENTS.md"
    next_prompt_path = directory / "NEXT_PROMPT.txt"
    try:
        if output_path.read_text(encoding="utf-8") != _output_requirements_md():
            semantic_errors.append("OUTPUT_REQUIREMENTS.md does not match the read-only task contract")
    except (OSError, UnicodeDecodeError):
        semantic_errors.append("OUTPUT_REQUIREMENTS.md is unreadable")
    try:
        if next_prompt_path.read_text(encoding="utf-8") != HANDOFF_PHRASE + "\n":
            semantic_errors.append("NEXT_PROMPT.txt does not contain the exact handoff phrase")
    except (OSError, UnicodeDecodeError):
        semantic_errors.append("NEXT_PROMPT.txt is unreadable")

    missing = sorted(set(missing + missing_members))
    mismatches = sorted(set(mismatches))
    unknown_files = sorted(set(unknown_files))
    link_files = sorted(set(link_files))
    unexpected_manifest_files = sorted(set(unexpected_manifest_files))
    verified = not any((manifest_errors, missing, mismatches, unknown_files, link_files, unexpected_manifest_files, semantic_errors))
    return {
        "schema": "uriel.burst_verify.v1",
        "packet": str(directory),
        "packet_sha256": packet_sha256,
        "checked": len(expected),
        "missing": missing,
        "mismatched": mismatches,
        "unknown_files": unknown_files,
        "link_files": link_files,
        "unexpected_manifest_files": unexpected_manifest_files,
        "manifest_errors": manifest_errors,
        "semantic_errors": semantic_errors,
        "packet_bytes": packet_bytes,
        "packet_byte_limit": MAX_BURST_PACKET_BYTES,
        "verified": verified,
    }


def burst_init(
    root: Union[str, Path],
    record_paths: Sequence[Union[str, Path]],
    *,
    next_task: str = "",
    budget_bytes: int = DEFAULT_BUDGET_BYTES,
    redact: bool = False,
    packet_index: Optional[int] = None,
    generation_id: Optional[str] = None,
    generation_columns: Sequence[str] = (),
    row_indices: Sequence[int] = (),
    row_limit: int = 100,
    readiness_sort_spec: Optional[str] = None,
    readiness_receipt: Optional[str] = None,
) -> Dict[str, Any]:
    """Create the next bounded burst packet from project record files."""
    if not next_task.strip():
        raise Refusal("A next_task is required.", code="BURST_TASK_REQUIRED")
    task_bytes = len(next_task.encode("utf-8"))
    if task_bytes > MAX_BURST_TASK_BYTES:
        raise Refusal(
            "The burst task exceeds the hard instruction-size limit.",
            code="BURST_TASK_BUDGET",
            details={"task_bytes": task_bytes, "maximum": MAX_BURST_TASK_BYTES},
            repairs=["State one bounded next task and move supporting detail into explicitly selected records."],
        )
    if len(record_paths) > MAX_BURST_RECORD_FILES:
        raise Refusal(
            "The burst selects too many project files.",
            code="BURST_RECORD_BUDGET",
            details={"selected": len(record_paths), "maximum": MAX_BURST_RECORD_FILES},
        )
    root_path = canonical_root(root)
    paths = paths_for(root_path)
    if packet_index is None:
        packet_index = _next_index(root_path)
    if (
        not isinstance(packet_index, int)
        or isinstance(packet_index, bool)
        or not 1 <= packet_index <= MAX_BURST_PACKETS
    ):
        raise Refusal(
            "Burst packet index must be an integer from 1 through {0}.".format(MAX_BURST_PACKETS),
            code="BURST_INDEX_INVALID",
        )
    directory = _burst_dir(root_path, packet_index)

    parent_packet_sha256: Optional[str] = None
    if packet_index > 1:
        previous = _burst_dir(root_path, packet_index - 1)
        if not previous.is_dir():
            raise Refusal(
                "The preceding burst packet is missing; the continuity chain cannot advance.",
                code="BURST_PARENT_MISSING",
                details={"expected_parent": str(previous)},
            )
        try:
            parent_verification = verify_burst(previous)
        except Refusal as exc:
            raise Refusal(
                "The preceding burst packet cannot be verified.",
                code="BURST_PARENT_INVALID",
                details={"parent": str(previous), "reason": exc.code},
            ) from exc
        if not parent_verification.get("verified"):
            raise Refusal(
                "The preceding burst packet failed integrity or semantic verification.",
                code="BURST_PARENT_INVALID",
                details={
                    "parent": str(previous),
                    "missing": parent_verification.get("missing", []),
                    "mismatched": parent_verification.get("mismatched", []),
                    "semantic_errors": parent_verification.get("semantic_errors", []),
                },
            )
        parent_packet_sha256 = str(parent_verification.get("packet_sha256", ""))
        if _HEX64.fullmatch(parent_packet_sha256) is None:
            raise Refusal(
                "The preceding burst packet has no valid content identity.",
                code="BURST_PARENT_INVALID",
            )
        parent_state = previous / "STATE.json"
    else:
        parent_state = None

    resolved: List[Path] = []
    total_source_bytes = 0
    for item in record_paths:
        target = guard_path(root_path, item, must_exist=True)
        if not target.is_file():
            raise Refusal("Not a file: {0}".format(target), code="BURST_BAD_RECORD")
        size = target.stat().st_size
        if size > MAX_BURST_SOURCE_FILE_BYTES:
            raise Refusal(
                "A selected burst source exceeds the bounded per-file work ceiling.",
                code="BURST_SOURCE_BUDGET",
                details={
                    "path": target.relative_to(root_path).as_posix(),
                    "size_bytes": size,
                    "max_file_bytes": MAX_BURST_SOURCE_FILE_BYTES,
                },
            )
        total_source_bytes += size
        if total_source_bytes > MAX_BURST_SOURCE_TOTAL_BYTES:
            raise Refusal(
                "The selected burst sources exceed the bounded total work ceiling.",
                code="BURST_SOURCE_BUDGET",
                details={
                    "selected_bytes": total_source_bytes,
                    "max_total_bytes": MAX_BURST_SOURCE_TOTAL_BYTES,
                },
            )
        resolved.append(target)

    budget = int(budget_bytes)
    if not 1024 <= budget <= MAX_AI_SURFACE_BYTES:
        raise Refusal(
            "Burst byte budget is outside the hard AI-surface safety range.",
            code="BURST_BUDGET_INVALID",
            details={"minimum": 1024, "maximum": MAX_AI_SURFACE_BYTES},
        )
    selected: List[Dict[str, Any]] = []
    source_rows: List[Dict[str, Any]] = []
    used = 0
    generation_status: Optional[Dict[str, Any]] = None
    projection: Optional[Dict[str, Any]] = None
    if generation_id is not None:
        if resolved:
            raise Refusal(
                "A burst may contain either explicit project files or one generation projection, not both.",
                code="BURST_INPUT_AMBIGUOUS",
            )
        if not generation_columns:
            raise Refusal(
                "Generation bursts require explicit task-needed columns.",
                code="BURST_COLUMNS_REQUIRED",
            )
        generation_status = require_generation_readiness(
            root_path,
            generation_id,
            sort_spec_path=readiness_sort_spec,
            receipt_path=readiness_receipt,
        )
        projection = project_verified_data_generation(
            root_path,
            generation_id,
            columns=generation_columns,
            row_indices=row_indices,
            row_limit=row_limit,
            byte_limit=budget,
            redact=redact,
        )
        source_rows.append(
            {
                "name": "data-generation:{0}".format(generation_id),
                "bytes": projection["byte_count"],
                "sha256": projection["source_records_sha256"],
                "generation_manifest_sha256": projection["generation_manifest_sha256"],
                "selected_row_indices": projection["selected_row_indices"],
                "selected_columns": projection["selected_columns"],
            }
        )
        selected.extend(_selected_from_projection(generation_id, projection, redact=redact))
        exposed_bytes = len(_selected_records_jsonl(selected).encode("utf-8"))
        if exposed_bytes > budget:
            raise Refusal(
                "The complete generation packet rows exceed the declared AI byte limit.",
                code="BURST_BUDGET_INVALID",
                details={"byte_limit": budget, "selected_records_bytes": exposed_bytes},
                repairs=["Select fewer rows or columns, redact values, or raise the bounded byte limit."],
            )
        used = exposed_bytes
    else:
        for target in resolved:
            size = target.stat().st_size
            source_rows.append(
                {"name": target.relative_to(root_path).as_posix(), "bytes": size, "sha256": sha256_file(target)}
            )
            row = {
                "id": "rec-{0}".format(sha256_text(target.relative_to(root_path).as_posix()))[:12],
                "name": target.relative_to(root_path).as_posix(),
                "sha256": sha256_file(target),
            }
            if redact:
                row["bytes"] = 0
                row["content"] = "[redacted: metadata only]"
                row["content_sha256"] = sha256_file(target)
            else:
                body = _read_record_body(target, False)
                encoded = body.encode("utf-8")
                row["bytes"] = len(encoded)
                row["content_sha256"] = _digest(body)
                candidate = {**row, "content": body}
                candidate_rows = [*selected, candidate]
                if len(_selected_records_jsonl(candidate_rows).encode("utf-8")) <= budget:
                    row = candidate
                else:
                    row["content"] = "[omitted: exceeds packet budget; see source file]"
            selected.append(row)
            used = len(_selected_records_jsonl(selected).encode("utf-8"))
            if used > budget:
                raise Refusal(
                    "Burst record metadata exceeds the declared AI byte limit.",
                    code="BURST_BUDGET_INVALID",
                    details={"byte_limit": budget, "selected_records_bytes": used},
                    repairs=["Select fewer files or raise the bounded byte limit."],
                )

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

    selected_records_text = _selected_records_jsonl(selected)
    state: Dict[str, Any] = {
        "schema": BURST_SCHEMA,
        "packet_index": packet_index,
        "created_at_utc": utc_now(),
        "parent_packet": packet_index - 1 if packet_index > 1 else None,
        "parent_packet_sha256": parent_packet_sha256,
        "project_generation": generation_id or (sha256_file(paths.project) if paths.project.is_file() else None),
        "packet_generation": sha256_text(selected_records_text),
        "completed_tasks": completed_tasks,
        "unresolved_tasks": [next_task],
        "evidence_reviewed": [row["name"] for row in source_rows],
        "claims_reviewed": [],
        "questions_asked": questions_asked,
        "next_task": next_task,
        "redacted": bool(redact),
        "budget_bytes": budget,
        "selected_records_bytes": used,
        "task_bytes": task_bytes,
        "packet_byte_limit": MAX_BURST_PACKET_BYTES,
        "task_capabilities": dict(TASK_CAPABILITIES),
        "no_authority": True,
    }
    if generation_id is not None and generation_status is not None and projection is not None:
        state.update(
            {
                "data_generation_id": generation_id,
                "data_readiness_receipt_sha256": generation_status["receipt_sha256"],
                "data_readiness_binding_digest": generation_status["receipt"]["binding_digest"],
                "selected_row_indices": projection["selected_row_indices"],
                "selected_columns": projection["selected_columns"],
                "row_limit": row_limit,
                "allowed_task": next_task,
            }
        )

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
        "SELECTED_RECORDS.jsonl": selected_records_text,
        "OUTPUT_REQUIREMENTS.md": _output_requirements_md(),
        "NEXT_PROMPT.txt": HANDOFF_PHRASE + "\n",
    }
    if generation_id is not None and generation_status is not None and projection is not None:
        surface_core = {
            "project_generation": generation_id,
            "allowed_task": next_task,
            "row_limit": row_limit,
            "byte_limit": budget,
            "redaction_policy": (
                "VALUES_REDACTED_METADATA_AND_HASHES_ONLY"
                if redact
                else "EXPLICIT_ROWS_AND_COLUMNS_ONLY"
            ),
            "records_sha256": projection["records_sha256"],
            "source_manifest_sha256": projection["generation_manifest_sha256"],
            "acceptance_receipt": generation_status["receipt_sha256"],
            "no_authority": True,
        }
        surface = {
            "schema": AI_SURFACE_SCHEMA,
            "surface_id": "surface-" + sha256_text(canonical_json(surface_core))[:24],
            "created_at_utc": utc_now(),
            **surface_core,
        }
        files["AI_SURFACE.json"] = json.dumps(
            surface, ensure_ascii=False, sort_keys=True, indent=2
        ) + "\n"
    packet_bytes = _packet_bytes(files)
    if packet_bytes > MAX_BURST_PACKET_BYTES:
        raise Refusal(
            "The complete burst packet exceeds the hard context-safety ceiling.",
            code="BURST_PACKET_BUDGET",
            details={"packet_bytes": packet_bytes, "maximum": MAX_BURST_PACKET_BYTES},
            repairs=["Select fewer records, shorten the task, or use redaction."],
        )
    _write_all(root_path, files, directory)
    _write_checksums(root_path, directory)
    verification = verify_burst(directory)
    return {
        "schema": "uriel.burst_result.v1",
        "packet": str(directory),
        "packet_index": packet_index,
        "files": sorted(files) + ["SHA256SUMS.txt"],
        "selected_records": len(selected),
        "bytes": used,
        "packet_bytes": packet_bytes,
        "packet_byte_limit": MAX_BURST_PACKET_BYTES,
        "redacted": bool(redact),
        "state": state,
        "verify": verification,
        "note": "This packet is advisory and carries no authority; it cannot issue a Blessing.",
    }
