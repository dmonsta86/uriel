"""Standalone packet model with immutable generations.

Implements the ``uriel.packet_manifest.v1`` contract: a packet is a numbered
directory of files plus ``MANIFEST.json`` and ``SHA256SUMS.txt``. Packet IDs
are content-derived from the sorted file list, so identical replay is
idempotent, a colliding generation is refused, and an earlier packet is never
silently overwritten.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from .checkpoints import GenerationRefusal
from .core import (
    Refusal,
    atomic_write_text,
    canonical_json,
    guard_path,
    read_json,
    sha256_bytes,
    sha256_file,
    utc_now,
)

PACKET_SCHEMA = "uriel.packet_manifest.v1"

PACKET_TYPES = (
    "lens_review",
    "research_plan",
    "paper_submission",
    "revision_response",
    "conditional_acceptance",
    "production",
    "resubmission",
    "archive",
)

PACKET_STATUSES = (
    "ready",
    "ready_with_disclosed_limitations",
    "revision_required",
    "blocked",
)

BLOCKING_PLACEHOLDERS = (
    "UNKNOWN_REQUIRED",
    "CHARACTER_LIMIT_EXCEEDED",
    "MISSING_ATTACHMENT",
    "UNVERIFIED_REQUIREMENT",
)

REVISION_PLACEHOLDERS = (
    "TODO",
    "TBD",
    "PLACEHOLDER",
    "UNCITED_CLAIM",
)

_MANIFEST_RELATIVE = frozenset({"MANIFEST.json", "SHA256SUMS.txt"})


def validate_packet_manifest(record: Mapping[str, Any]) -> List[str]:
    """Return human-readable violations of the packet manifest v1 contract."""
    errors: List[str] = []
    if record.get("schema") != PACKET_SCHEMA:
        errors.append("schema must be uriel.packet_manifest.v1")
    for field in ("packet_id", "project_generation"):
        if not isinstance(record.get(field), str) or not record.get(field):
            errors.append(f"{field} must be non-empty text")
    if record.get("packet_type") not in PACKET_TYPES:
        errors.append("packet_type must be a known packet type")
    if record.get("status") not in PACKET_STATUSES:
        errors.append("status must be a known packet status")
    parent = record.get("parent_packet_id")
    if parent is not None and not (isinstance(parent, str) and parent):
        errors.append("parent_packet_id must be non-empty text or null")
    files = record.get("files")
    if not isinstance(files, list):
        errors.append("files must be an array")
        return errors
    for index, entry in enumerate(files):
        if not isinstance(entry, Mapping):
            errors.append(f"files[{index}] must be an object")
            continue
        for field in ("path", "sha256", "size"):
            if field not in entry:
                errors.append(f"files[{index}].{field} is required")
        path_value = entry.get("path")
        if not (isinstance(path_value, str) and path_value):
            errors.append(f"files[{index}].path must be non-empty text")
        digest = entry.get("sha256")
        if not (isinstance(digest, str) and re.fullmatch(r"^[0-9a-f]{64}$", digest)):
            errors.append(f"files[{index}].sha256 must be a SHA-256 hex digest")
        if not isinstance(entry.get("size"), int) or entry.get("size", -1) < 0:
            errors.append(f"files[{index}].size must be a non-negative integer")
    return errors


def packet_id_for(packet_type: str, files: Sequence[Tuple[str, str]]) -> str:
    """Content-derived packet ID from the sorted (path, sha256) file list."""
    identity = canonical_json({"packet_type": packet_type, "files": sorted(files)})
    return f"{packet_type}-" + sha256_bytes(identity.encode("utf-8"))[:16]


def write_packet_generation(
    store_dir: Path,
    *,
    packet_type: str,
    project_generation: str,
    files: Mapping[str, bytes],
    parent_packet_id: Optional[str] = None,
    warnings: Sequence[str] = (),
    created_at_utc: Optional[str] = None,
) -> Tuple[Path, Dict[str, Any]]:
    """Write one immutable packet generation and return (path, manifest).

    ``files`` maps relative packet filenames to their bytes. The packet ID is
    derived from the sorted file list, so rebuilding the same content is
    idempotent and different content is a new generation that never
    overwrites the old one.
    """
    if packet_type not in PACKET_TYPES:
        raise GenerationRefusal(f"unknown packet type: {packet_type}")
    file_rows: List[Dict[str, Any]] = []
    for relative, content in sorted(files.items()):
        relative_path = Path(relative)
        if (
            not relative
            or relative.startswith(("/", "\\"))
            or os.path.isabs(relative)
            or relative_path.is_absolute()
            or ".." in relative_path.parts
        ):
            raise GenerationRefusal(f"unsafe packet filename: {relative}")
        file_rows.append(
            {
                "path": relative_path.as_posix(),
                "sha256": sha256_bytes(content),
                "size": len(content),
            }
        )
    packet_id = packet_id_for(packet_type, [(row["path"], row["sha256"]) for row in file_rows])
    target_dir = store_dir / packet_type / packet_id
    if target_dir.exists():
        existing = read_json(target_dir / "MANIFEST.json")
        if existing.get("files") == file_rows and existing.get("packet_id") == packet_id:
            return target_dir, existing
        raise GenerationRefusal(
            f"packet {packet_id} already exists with different content"
        )
    manifest: Dict[str, Any] = {
        "schema": PACKET_SCHEMA,
        "packet_id": packet_id,
        "packet_type": packet_type,
        "project_generation": project_generation,
        "parent_packet_id": parent_packet_id,
        "files": file_rows,
        "status": "ready",
        "warnings": list(warnings),
        "created_at_utc": created_at_utc or utc_now(),
    }
    violations = validate_packet_manifest(manifest)
    if violations:
        raise GenerationRefusal("invalid packet manifest: " + "; ".join(violations))
    target_dir.mkdir(parents=True, exist_ok=True)
    for relative, content in sorted(files.items()):
        target = target_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(target, content.decode("utf-8"))
    atomic_write_text(target_dir / "MANIFEST.json", canonical_json(manifest))
    checksum_lines = "".join(
        f"{row['sha256']}  {row['path']}\n" for row in sorted(file_rows, key=lambda r: r["path"])
    )
    atomic_write_text(target_dir / "SHA256SUMS.txt", checksum_lines)
    return target_dir, manifest


def packet_placeholders(packet_dir: Path) -> List[str]:
    """Return blocking/revision placeholder tokens found in packet text files."""
    found: List[str] = []
    for path in sorted(packet_dir.rglob("*")):
        if not path.is_file() or path.name in _MANIFEST_RELATIVE:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for token in BLOCKING_PLACEHOLDERS + REVISION_PLACEHOLDERS:
            if token in text and token not in found:
                found.append(token)
    return found


def preflight_packet(packet_dir: Path) -> str:
    """Classify a packet as ready, revision_required, or blocked."""
    manifest_path = packet_dir / "MANIFEST.json"
    if not manifest_path.is_file():
        return "blocked"
    manifest = read_json(manifest_path)
    violations = validate_packet_manifest(manifest)
    if violations:
        return "blocked"
    missing = [
        entry["path"]
        for entry in manifest["files"]
        if not (packet_dir / entry["path"]).is_file()
    ]
    if missing:
        return "blocked"
    placeholders = packet_placeholders(packet_dir)
    if any(token in BLOCKING_PLACEHOLDERS for token in placeholders):
        return "blocked"
    if placeholders:
        return "revision_required"
    if manifest["status"] == "blocked":
        return "blocked"
    if manifest["warnings"] or manifest["status"] == "ready_with_disclosed_limitations":
        return "ready_with_disclosed_limitations"
    return "ready"


def verify_packet(packet_dir: Path) -> Dict[str, Any]:
    """Recompute hashes and sizes for every manifest entry."""
    manifest_path = packet_dir / "MANIFEST.json"
    if not manifest_path.is_file():
        return {"status": "fail", "mismatches": ["MANIFEST.json missing"]}
    manifest = read_json(manifest_path)
    violations = validate_packet_manifest(manifest)
    mismatches: List[str] = []
    if violations:
        return {"status": "fail", "mismatches": violations}
    for entry in manifest["files"]:
        target = packet_dir / entry["path"]
        if not target.is_file():
            mismatches.append(f"{entry['path']}: missing")
            continue
        if sha256_file(target) != entry["sha256"]:
            mismatches.append(f"{entry['path']}: sha256 mismatch")
        if target.stat().st_size != entry["size"]:
            mismatches.append(f"{entry['path']}: size mismatch")
    checksums_path = packet_dir / "SHA256SUMS.txt"
    if checksums_path.is_file():
        checksums = checksums_path.read_text(encoding="utf-8")
        for row in manifest["files"]:
            expected = f"{row['sha256']}  {row['path']}\n"
            if expected not in checksums:
                mismatches.append(f"SHA256SUMS.txt: missing {row['path']}")
    else:
        mismatches.append("SHA256SUMS.txt: missing")
    return {"status": "pass" if not mismatches else "fail", "mismatches": mismatches}
