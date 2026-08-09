"""Single-source capability catalog and deterministic public inventory.

Tracked capability files bind to a stable catalog fingerprint rather than a
Git commit that would change when those same tracked files are regenerated.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict, List, Mapping


CAPABILITY_INVENTORY_SCHEMA = "uriel.capability_inventory.v1"
CAPABILITY_STATUSES = ("SHIPPED", "BETA", "EXPERIMENTAL", "PLANNED", "DEFERRED")

CAPABILITIES: List[Dict[str, Any]] = [
    {
        "id": "CAP-CORE-001",
        "name": "Deterministic project core and packaging",
        "status": "SHIPPED",
        "entry_point": "uriel start / uriel verify / uriel doctor",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/core.py", "src/uriel/cli.py"],
        "verification": ["tests/test_core.py", "tests/test_packaging.py"],
        "notes": "Offline-first project confinement, content-addressed records, receipts, and zero runtime dependencies.",
    },
    {
        "id": "CAP-READINESS-001",
        "name": "Data Readiness and Gate 0",
        "status": "BETA",
        "entry_point": "uriel readiness",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/data_readiness.py"],
        "verification": ["tests/test_data_readiness.py"],
        "notes": "Dataset identity, sorting, normalization, reconciliation, staleness, and order-invariance checks.",
    },
    {
        "id": "CAP-GATES-001",
        "name": "Three Integrity Gates",
        "status": "BETA",
        "entry_point": "uriel audit",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/gate_contract.py", "src/uriel/audit.py"],
        "verification": ["tests/test_gate_contract.py", "tests/test_audit.py"],
        "notes": "Scope and claim language, direct evidence, and adversarial robustness with fail-closed repair guidance.",
    },
    {
        "id": "CAP-BLESSING-001",
        "name": "Strict Blessing and independent verifier",
        "status": "EXPERIMENTAL",
        "entry_point": "uriel blessing / uriel verify-blessing",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/strict_blessing.py", "src/uriel/independent_verify.py"],
        "verification": ["tests/test_strict_blessing.py", "tests/test_blessing.py"],
        "notes": "Content-addressed attestation of recorded gate decisions and exact bound artifacts; not independent scientific validation.",
    },
    {
        "id": "CAP-LIFECYCLE-001",
        "name": "Research lifecycle, workbench, repair, and submission",
        "status": "BETA",
        "entry_point": "uriel intake / uriel workbench / uriel burst / uriel submit",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": [
            "src/uriel/workbench.py",
            "src/uriel/surfaces.py",
            "src/uriel/gap_register.py",
            "src/uriel/repair_packet.py",
        ],
        "verification": [
            "tests/test_workbench.py",
            "tests/test_lifecycle_packet.py",
            "tests/test_lifecycle_submission.py",
        ],
        "notes": "Question intake, bounded review packets, gap records, repair packets, decisions, and submission support.",
    },
    {
        "id": "CAP-ASSURANCE-001",
        "name": "Assurance depth, evidence microscope, and decision card",
        "status": "EXPERIMENTAL",
        "entry_point": "Python API (uriel.assurance_case, uriel.decision_card)",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/assurance_case.py", "src/uriel/decision_card.py"],
        "verification": ["tests/test_assurance_depth.py"],
        "notes": "Exploratory assurance chains, evidence-strength records, and decision artifacts; no dedicated CLI contract yet.",
    },
    {
        "id": "CAP-TRIALS-001",
        "name": "Synthetic Forge Trial fixture and adjudicated scorer",
        "status": "BETA",
        "entry_point": "python scripts/check_forge_trial.py",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/forge_trials.py"],
        "verification": ["tests/test_forge_trials.py"],
        "notes": "Validates the sealed synthetic fixture and scores supplied adjudicated findings; it does not claim a detector was run.",
    },
    {
        "id": "CAP-INGRESS-001",
        "name": "Evidence ingress and Data Desk",
        "status": "EXPERIMENTAL",
        "entry_point": "uriel data plan / import / inspect / diff / reconcile / verify-generation",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": [
            "src/uriel/data_contracts.py",
            "src/uriel/data_ingress.py",
            "src/uriel/data_desk.py",
        ],
        "verification": [
            "tests/test_data_contracts.py",
            "tests/test_data_ingress.py",
            "tests/test_data_desk.py",
            "tests/test_cli.py",
        ],
        "notes": "Bounded local immutable intake, structural generations, per-record delta ledgers, derived indexes, preserve-all reconciliation, and deep verification; no scientific finding or Gate 0 authority.",
    },
    {
        "id": "CAP-FORGE-001",
        "name": "Operational Forge Method closure engine",
        "status": "PLANNED",
        "entry_point": "n/a (planned capability)",
        "platforms": ["Windows (planned)", "macOS (planned)", "Linux (planned)"],
        "modules": [],
        "verification": [],
        "notes": "The Forge of Uriel is the public identity; a general automatic milestone-closure engine is not implemented.",
    },
    {
        "id": "CAP-LOCAL-AI-001",
        "name": "Built-in local-model adapter",
        "status": "PLANNED",
        "entry_point": "n/a (planned capability)",
        "platforms": ["Windows (planned)", "macOS (planned)", "Linux (planned)"],
        "modules": [],
        "verification": [],
        "notes": "External and local models can consume bounded prompts today; Uriel does not ship an inference provider.",
    },
    {
        "id": "CAP-DESKTOP-001",
        "name": "Desktop GUI and native installer",
        "status": "PLANNED",
        "entry_point": "n/a (planned capability)",
        "platforms": ["Windows (planned)", "macOS (planned)", "Linux (planned)"],
        "modules": [],
        "verification": [],
        "notes": "The supported product is currently CLI/Python-first.",
    },
]


def _catalog_bytes() -> bytes:
    return json.dumps(
        CAPABILITIES,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def capability_source_fingerprint() -> str:
    """Return the stable SHA-256 binding for the canonical capability catalog."""

    return hashlib.sha256(_catalog_bytes()).hexdigest()


def validate_capability_catalog(repo_root: Path) -> List[str]:
    """Return catalog defects without changing repository state."""

    errors: List[str] = []
    identifiers: set[str] = set()
    for capability in CAPABILITIES:
        identifier = str(capability.get("id", ""))
        if not identifier or identifier in identifiers:
            errors.append(f"duplicate or empty capability id: {identifier!r}")
        identifiers.add(identifier)
        status = capability.get("status")
        if status not in CAPABILITY_STATUSES:
            errors.append(f"{identifier}: unknown status {status!r}")
        modules = capability.get("modules")
        verification = capability.get("verification")
        if not isinstance(modules, list) or not isinstance(verification, list):
            errors.append(f"{identifier}: modules and verification must be lists")
            continue
        if status in {"PLANNED", "DEFERRED"}:
            if modules or verification:
                errors.append(f"{identifier}: planned/deferred capability claims implementation evidence")
        else:
            if not modules or not verification:
                errors.append(f"{identifier}: implemented capability lacks modules or verification")
            for relative in [*modules, *verification]:
                if not (repo_root / relative).is_file():
                    errors.append(f"{identifier}: missing evidence file {relative}")
    return errors


def generate_capability_inventory(repo_root: Path) -> Dict[str, Any]:
    """Generate the machine-readable inventory from the canonical catalog."""

    errors = validate_capability_catalog(repo_root)
    if errors:
        raise ValueError("invalid capability catalog: " + "; ".join(errors))
    return {
        "schema": CAPABILITY_INVENTORY_SCHEMA,
        "source": "src/uriel/capability_status.py",
        "source_fingerprint": capability_source_fingerprint(),
        "capabilities": deepcopy(CAPABILITIES),
    }


def render_capability_markdown(inventory: Mapping[str, Any]) -> str:
    """Render the human-readable capability boundary."""

    lines = [
        "# The Forge of Uriel Capability Status",
        "",
        f"Catalog fingerprint: `{inventory['source_fingerprint']}`",
        "",
        "Status meanings:",
        "",
        "- `SHIPPED`: supported core behavior with a public CLI contract.",
        "- `BETA`: usable and tested, with interfaces or policy still allowed to evolve.",
        "- `EXPERIMENTAL`: available for careful evaluation; not a claim of scientific authority.",
        "- `PLANNED`: named boundary only; no implementation is claimed.",
        "",
        "| Capability | Status | Verified entry point | Platforms | Evidence | Notes |",
        "|---|---|---|---|---|---|",
    ]
    for capability in inventory["capabilities"]:
        evidence = ", ".join(
            f"`{path}`" for path in [*capability["modules"], *capability["verification"]]
        ) or "—"
        lines.append(
            "| {name} | `{status}` | `{entry}` | {platforms} | {evidence} | {notes} |".format(
                name=capability["name"],
                status=capability["status"],
                entry=capability["entry_point"],
                platforms=", ".join(capability["platforms"]),
                evidence=evidence,
                notes=capability["notes"],
            )
        )
    return "\n".join(lines) + "\n"


def capability_artifacts(repo_root: Path) -> Dict[str, str]:
    """Return every tracked capability artifact and its exact expected text."""

    inventory = generate_capability_inventory(repo_root)
    json_text = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    markdown = render_capability_markdown(inventory)
    return {
        "docs/CAPABILITY_STATUS.json": json_text,
        "manifest/capability_inventory.json": json_text,
        "docs/CAPABILITY_STATUS.md": markdown,
        "docs/CAPABILITY_INVENTORY.md": markdown,
    }


def write_capability_status_files(repo_root: Path) -> None:
    """Regenerate all public capability artifacts from one catalog."""

    for relative, content in capability_artifacts(repo_root).items():
        target = repo_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
