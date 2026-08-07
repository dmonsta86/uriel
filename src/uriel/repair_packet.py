"""Immutable constructive failure packet (STRICT_BLESSING_CONTRACT.md section 11).

A gate failure never ends with a bare refusal.  Each failure produces a
standalone packet with the exact 14 files, a MANIFEST, and SHA256SUMS.
Placeholder packets can never be marked ready.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import Refusal, atomic_write, atomic_write_json, canonical_json, canonical_root, paths_for, sha256_file, sha256_text, utc_now
from .gate_failures import constructive_response

REPAIR_PACKET_SCHEMA = "uriel.repair_packet.v1"

PACKET_FILES = (
    "00_READ_ME_FIRST.md",
    "01_FAILURE_SUMMARY.md",
    "02_GATE_RESULTS.json",
    "03_BLOCKERS.csv",
    "04_GAP_REGISTER.csv",
    "05_DATA_SORTING_OR_COLLECTION_PLAN.md",
    "06_REPAIR_PLAN.md",
    "07_PIVOT_OPTIONS.md",
    "08_EVIDENCE_REQUESTS.md",
    "09_UPDATED_PROJECT_SPEC.md",
    "10_COMPLETION_CHECKLIST.md",
    "11_RECHECK_INSTRUCTIONS.md",
    "12_NEXT_PROMPT.txt",
    "MANIFEST.json",
    "SHA256SUMS.txt",
)

PLACEHOLDER_MARKERS = ("TODO", "TBD", "FIXME", "[placeholder]", "[TODO]")


def _has_placeholder(text: str) -> bool:
    upper = text.upper()
    return any(marker in upper for marker in ("TODO", "TBD", "FIXME"))


def build_repair_packet(
    root: Union[str, Path],
    *,
    gate: int,
    gate_name: str,
    decision: str,
    failure_summary: str,
    gates_results: Mapping[str, Any],
    blockers: Sequence[Mapping[str, Any]],
    gaps: Sequence[Mapping[str, Any]],
    sorting_plan: str,
    repair_plan: str,
    pivot_options: Sequence[str],
    evidence_requests: Sequence[str],
    updated_project_spec: str,
    completion_checklist: Sequence[str],
    recheck_instructions: str,
    next_prompt: str,
    what_was_inspected: str = "",
    what_remains_valid: str = "",
    what_uriel_filled: str = "",
    what_cannot_be_filled: str = "",
    prefer_repair: str = "",
    alternatives: Sequence[str] = (),
    rerun_gates: Sequence[int] = (),
    new_generation_required: bool = False,
) -> Dict[str, Any]:
    """Generate a standalone immutable failure packet under .uriel/repair-packets/."""
    from .gap_register import render_gap_register_csv

    gate_results_json = json.dumps(gates_results, indent=2, sort_keys=True)
    if _has_placeholder(gate_results_json):
        raise Refusal("The gate results contain placeholder markers.", code="PACKET_PLACEHOLDER")
    blockers_csv = _render_blockers_csv(blockers)
    gaps_csv = render_gap_register_csv(gaps)
    pivot_text = "\n".join("- " + str(item) for item in pivot_options) or "- No pivot proposed yet."
    evidence_text = "\n".join("- " + str(item) for item in evidence_requests) or "- No evidence requests yet."
    checklist_text = "\n".join("- [ ] " + str(item) for item in completion_checklist) or "- [ ] Define the exact completion conditions."
    alt_text = "\n".join("- " + str(item) for item in alternatives) or "- No alternatives proposed yet."
    rerun_text = ", ".join("Gate {0}".format(item) for item in sorted(set(rerun_gates))) or "Gate {0}".format(gate)

    read_me = """# Failure packet - Gate {gate} ({gate_name})

Decision: {decision}

What happened: {summary}

## Rules for reading this packet

1. The failure is a project state, not a judgment of the person.
2. Every file in this packet is byte-addressed in SHA256SUMS.txt.
3. Nothing here invents evidence. Items Uriel cannot fill are listed in
   08_EVIDENCE_REQUESTS.md with an action label.
4. Do not edit packet files. Produce a new generation and a new packet instead.
5. Recheck with the exact commands in 11_RECHECK_INSTRUCTIONS.md.
""".format(
        gate=gate, gate_name=gate_name, decision=decision, summary=failure_summary,
    )

    failure_summary_md = """# Failure summary

## What failed
{summary}

## What evidence was inspected
{inspected}

## What is directly refuted
Directly refuted findings are listed in 03_BLOCKERS.csv and 02_GATE_RESULTS.json.

## What is merely incomplete
Incomplete findings are listed in 04_GAP_REGISTER.csv.

## What remains useful
{valid}

## What Uriel has already filled
{filled}

## What cannot be filled without evidence
{cannot_fill}

## Preferred repair path
{prefer}

## At least two honest alternatives where available
{alt}

## Best sorting/normalization/collection method
{sorting}

## Exact completion conditions
See 10_COMPLETION_CHECKLIST.md.

## Exact commands or next prompt
See 11_RECHECK_INSTRUCTIONS.md and 12_NEXT_PROMPT.txt.

## Which gates must be rerun
{rerun}

## Whether a new project generation is required
{newgen}
""".format(
        summary=failure_summary,
        inspected=what_was_inspected or "See 02_GATE_RESULTS.json.",
        valid=what_remains_valid or "The unaffected claims and artifacts remain valid.",
        filled=what_uriel_filled or "Uriel filled this packet and the sorting/repair plans.",
        cannot_fill=what_cannot_be_filled or "See 08_EVIDENCE_REQUESTS.md.",
        prefer=prefer_repair or repair_plan,
        alt=alt_text,
        sorting=sorting_plan or "See 05_DATA_SORTING_OR_COLLECTION_PLAN.md.",
        rerun=rerun_text,
        newgen="YES - a new generation is required" if new_generation_required else "No - the same generation can be re-audited after repair.",
    )

    sorting_md = "# Data sorting / collection plan\n\n{0}\n".format(sorting_plan or "SortSpec is generated with `uriel readiness init-sort-spec`; see the data readiness documentation.")
    repair_md = "# Repair plan\n\n{0}\n".format(repair_plan or "See the gap register and evidence requests; each gap names its preferred repair.")
    spec_md = "# Updated project specification\n\n{0}\n".format(updated_project_spec or "No spec change proposed; the exact version being audited contains the clarified language.")
    recheck_md = "# Recheck instructions\n\n{0}\n".format(recheck_instructions or "Run `uriel audit --profile submission` and `uriel blessing eligibility` after each repair.")
    next_prompt_txt = next_prompt + ("\n" if not next_prompt.endswith("\n") else "")

    manifest = {
        "schema": REPAIR_PACKET_SCHEMA,
        "schema_version": 1,
        "created_at_utc": utc_now(),
        "gate": gate,
        "gate_name": gate_name,
        "decision": decision,
        "packet_files": list(PACKET_FILES),
        "new_generation_required": new_generation_required,
        "rerun_gates": sorted(set(rerun_gates)) or [gate],
    }

    files: Dict[str, str] = {
        "00_READ_ME_FIRST.md": read_me,
        "01_FAILURE_SUMMARY.md": failure_summary_md,
        "02_GATE_RESULTS.json": gate_results_json + "\n",
        "03_BLOCKERS.csv": blockers_csv,
        "04_GAP_REGISTER.csv": gaps_csv,
        "05_DATA_SORTING_OR_COLLECTION_PLAN.md": sorting_md,
        "06_REPAIR_PLAN.md": repair_md,
        "07_PIVOT_OPTIONS.md": "# Pivot options\n\n{0}\n".format(pivot_text),
        "08_EVIDENCE_REQUESTS.md": "# Evidence requests\n\n{0}\n".format(evidence_text),
        "09_UPDATED_PROJECT_SPEC.md": spec_md,
        "10_COMPLETION_CHECKLIST.md": "# Completion checklist\n\n{0}\n".format(checklist_text),
        "11_RECHECK_INSTRUCTIONS.md": recheck_md,
        "12_NEXT_PROMPT.txt": next_prompt_txt,
    }

    for name, text in files.items():
        if _has_placeholder(text):
            raise Refusal(
                "The packet file {0} still contains placeholder markers; a placeholder "
                "packet cannot be marked ready.".format(name),
                code="PACKET_PLACEHOLDER",
            )

    root_path = canonical_root(root)
    paths = paths_for(root_path)
    store = paths.state / "repair-packets"
    packet_digest = sha256_text(canonical_json({
        "gate": gate, "decision": decision, "files": {k: sha256_text(v) for k, v in files.items()},
    }))
    destination = store / "packet-{0}".format(packet_digest)
    if destination.exists():
        return {"packet_id": packet_digest, "path": str(destination),
                "packet_sha256": _read_packet_sha(destination)}
    destination.mkdir(parents=True, exist_ok=False)
    hashes: Dict[str, str] = {}
    for name, text in files.items():
        path = destination / name
        atomic_write(path, text)
        hashes[name] = sha256_file(path)
    manifest_bytes = canonical_json(manifest)
    atomic_write_json(destination / "MANIFEST.json", manifest)
    hashes["MANIFEST.json"] = sha256_file(destination / "MANIFEST.json")
    sums_lines = []
    for name in sorted(hashes):
        sums_lines.append("{0}  {1}".format(hashes[name], name))
    atomic_write(destination / "SHA256SUMS.txt", "\n".join(sums_lines) + "\n")
    hashes["SHA256SUMS.txt"] = sha256_file(destination / "SHA256SUMS.txt")
    return {"packet_id": packet_digest, "path": str(destination),
            "packet_sha256": sha256_text(canonical_json({"packet_id": packet_digest, "files": hashes}))}


def _render_blockers_csv(blockers: Sequence[Mapping[str, Any]]) -> str:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["failure_code", "severity", "subject", "message", "evidence"])
    for blocker in blockers:
        writer.writerow([
            blocker.get("failure_code", blocker.get("code", "")),
            blocker.get("severity", ""),
            blocker.get("subject", blocker.get("check_id", "")),
            blocker.get("message", ""),
            "; ".join(blocker.get("evidence", [])),
        ])
    return buffer.getvalue()


def _read_packet_sha(destination: Path) -> str:
    sums = (destination / "SHA256SUMS.txt").read_text(encoding="utf-8")
    from collections import OrderedDict

    hashes: "OrderedDict[str, str]" = OrderedDict()
    for line in sums.splitlines():
        parts = line.split("  ", 1)
        if len(parts) == 2:
            hashes[parts[1]] = parts[0]
    return sha256_text(canonical_json({"packet_id": destination.name[7:], "files": dict(hashes)}))


def verify_repair_packet(packet_dir: Union[str, Path]) -> Dict[str, Any]:
    """Verify packet membership, hashes, and completeness."""
    directory = Path(packet_dir)
    errors: List[str] = []
    missing = [name for name in PACKET_FILES if not (directory / name).is_file()]
    if missing:
        errors.append("Missing packet files: {0}".format(", ".join(missing)))
    sums_path = directory / "SHA256SUMS.txt"
    if sums_path.is_file():
        declared: Dict[str, str] = {}
        for line in sums_path.read_text(encoding="utf-8").splitlines():
            parts = line.split("  ", 1)
            if len(parts) == 2:
                declared[parts[1]] = parts[0]
        for name, expected in declared.items():
            path = directory / name
            if not path.is_file() or sha256_file(path) != expected:
                errors.append("Hash mismatch: {0}".format(name))
    else:
        errors.append("SHA256SUMS.txt is missing")
    manifest_path = directory / "MANIFEST.json"
    if manifest_path.is_file():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            for name in manifest.get("packet_files", []):
                if not (directory / name).is_file():
                    errors.append("Manifest-declared file missing: {0}".format(name))
        except (OSError, json.JSONDecodeError) as exc:
            errors.append("MANIFEST.json is unreadable: {0}".format(exc))
    else:
        errors.append("MANIFEST.json is missing")
    for name in ("00_READ_ME_FIRST.md", "01_FAILURE_SUMMARY.md", "06_REPAIR_PLAN.md", "10_COMPLETION_CHECKLIST.md"):
        path = directory / name
        if path.is_file():
            try:
                if _has_placeholder(path.read_text(encoding="utf-8")):
                    errors.append("Placeholder markers remain in {0}".format(name))
            except OSError:
                errors.append("Unreadable packet file: {0}".format(name))
    return {"verified": not errors, "errors": errors, "packet_id": directory.name[7:]}
