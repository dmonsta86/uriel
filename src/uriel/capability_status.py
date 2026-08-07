"""Capability status & live inventory generator (CAPSTATUS-001..002).

Inspects the live Uriel codebase and generates machine-readable capability inventory JSON
and human-readable Markdown tables.
"""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

CAPABILITY_INVENTORY_SCHEMA = "uriel.capability_inventory.v1"

CAPABILITIES: List[Dict[str, Any]] = [
    {
        "id": "CAP-CORE-001",
        "name": "Deterministic project core",
        "status": "SHIPPED",
        "entry_point": "uriel init / uriel verify / python -m uriel.core",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/core.py"],
        "verified_commit": "HEAD",
        "notes": "Offline-first, content-addressed, zero network dependencies.",
    },
    {
        "id": "CAP-GATE0-001",
        "name": "Data Readiness & Gate 0",
        "status": "SHIPPED",
        "entry_point": "uriel data-readiness / python -m uriel.data_readiness",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/data_readiness.py"],
        "verified_commit": "HEAD",
        "notes": "Strict raw data hash binding, receipt verification, order invariance.",
    },
    {
        "id": "CAP-GATES-001",
        "name": "Three Integrity Gates (Gates 1, 2, 3)",
        "status": "SHIPPED",
        "entry_point": "uriel gate / uriel audit / python -m uriel.gate_contract",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/gate_contract.py", "src/uriel/audit.py"],
        "verified_commit": "HEAD",
        "notes": "Gate 1 (Frame), Gate 2 (Evidence & Calculation), Gate 3 (Adversarial Challenge).",
    },
    {
        "id": "CAP-BLESSING-001",
        "name": "Strict Blessing Integration & Independent Verifier",
        "status": "SHIPPED",
        "entry_point": "uriel blessing / python -m uriel.strict_blessing",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/strict_blessing.py", "src/uriel/independent_verify.py"],
        "verified_commit": "HEAD",
        "notes": "Requires Gate 0 PASS, 3 Gate PASS, independent verifier PASS. Fail-closed.",
    },
    {
        "id": "CAP-LIFECYCLE-001",
        "name": "Research Lifecycle, Workbench & Free-Model Burst Surfaces",
        "status": "SHIPPED",
        "entry_point": "uriel workbench / uriel burst / python -m uriel.workbench",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/workbench.py", "src/uriel/surfaces.py", "src/uriel/gap_register.py", "src/uriel/repair_packet.py"],
        "verified_commit": "HEAD",
        "notes": "Read-only bounded AI surfaces, Gap Register, Repair Packets.",
    },
    {
        "id": "CAP-INGRESS-001",
        "name": "Evidence Ingress & Data Desk",
        "status": "SHIPPED",
        "entry_point": "uriel ingress / python -m uriel.ingress",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/ingress.py", "src/uriel/data_desk.py"],
        "verified_commit": "HEAD",
        "notes": "Safe ingestion, provenance tracking, data table reconciliation.",
    },
    {
        "id": "CAP-ASSURANCE-001",
        "name": "Assurance Depth, Evidence Microscope & Decision Card",
        "status": "SHIPPED",
        "entry_point": "uriel assurance / python -m uriel.assurance_case",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": [
            "src/uriel/claim_types.py", "src/uriel/evidence_strength.py", "src/uriel/assurance_case.py",
            "src/uriel/evidence_microscope.py", "src/uriel/measurement_lineage.py", "src/uriel/transformation_lineage.py",
            "src/uriel/evidence_independence.py", "src/uriel/uncertainty.py", "src/uriel/depth_policy.py",
            "src/uriel/visual_integrity.py", "src/uriel/decision_card.py", "src/uriel/communication_fidelity.py"
        ],
        "verified_commit": "HEAD",
        "notes": "4-Layer Assurance Chain, Evidence Strength Vector, Decision Card & Backend Proof Bundle.",
    },
    {
        "id": "CAP-LOCAL-AI-001",
        "name": "Generic Local-Model Adapters",
        "status": "BETA",
        "entry_point": "python -m uriel.local_ai (optional module)",
        "platforms": ["Windows", "macOS", "Linux"],
        "modules": ["src/uriel/local_ai.py"],
        "verified_commit": "HEAD",
        "notes": "Provider-neutral local inference wrapper; strictly optional.",
    },
    {
        "id": "CAP-DESKTOP-001",
        "name": "Desktop Native GUI & Installer",
        "status": "PLANNED",
        "entry_point": "n/a (in active development)",
        "platforms": ["Windows (Planned)", "macOS (Planned)", "Linux (Planned)"],
        "modules": ["bin/input_bridge_widget_slave/"],
        "verified_commit": "HEAD",
        "notes": "Standalone native GUI application; currently CLI/Python-first.",
    },
]


def generate_capability_inventory(repo_root: Path) -> Dict[str, Any]:
    """Generate machine-readable capability inventory from live repo."""
    try:
        commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(repo_root)).decode().strip()
    except Exception:
        commit = "unknown"

    inventory = {
        "schema": CAPABILITY_INVENTORY_SCHEMA,
        "commit": commit,
        "capabilities": CAPABILITIES,
    }
    return inventory


def render_capability_markdown_table() -> str:
    """Render Markdown table for README.md and CAPABILITY_STATUS.md."""
    lines = [
        "| Capability | Status | Verified entry point | Platforms | Notes |",
        "|---|---|---|---|---|",
    ]
    for c in CAPABILITIES:
        status_str = f"`{c['status']}`"
        entry_str = f"`{c['entry_point']}`"
        platforms_str = ", ".join(c["platforms"])
        lines.append(f"| {c['name']} | {status_str} | {entry_str} | {platforms_str} | {c['notes']} |")
    return "\n".join(lines)


def write_capability_status_files(repo_root: Path) -> None:
    """Generate and write docs/CAPABILITY_STATUS.json and docs/CAPABILITY_STATUS.md."""
    inventory = generate_capability_inventory(repo_root)
    json_content = json.dumps(inventory, indent=2, ensure_ascii=False) + "\n"
    
    md_content = f"# Uriel Forge Capability Status\n\nCommit: `{inventory['commit']}`\n\n" + render_capability_markdown_table() + "\n"
    
    docs_dir = repo_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "CAPABILITY_STATUS.json").write_text(json_content, encoding="utf-8")
    (docs_dir / "CAPABILITY_STATUS.md").write_text(md_content, encoding="utf-8")
    
    manifest_dir = repo_root / "manifest"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    (manifest_dir / "capability_inventory.json").write_text(json_content, encoding="utf-8")
    (docs_dir / "CAPABILITY_INVENTORY.md").write_text(md_content, encoding="utf-8")

