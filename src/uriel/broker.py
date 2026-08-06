"""Default-deny capability broker for optional external assistance.

No network client is implemented in Uriel Core.  A request is a local,
hash-addressed record that explains what an external capability would need and
what may be disclosed.  Users can fulfill it with an offline model, a web chat,
OpenCode, or manual research without changing the deterministic audit engine.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, Mapping, Optional, Union

from .core import append_ledger, atomic_write_json, load_project, paths_for, sha256_text, canonical_json, utc_now

REQUEST_SCHEMA = "uriel.capability_request.v1"


def create_request(
    root: Union[Path, str],
    capability: str,
    purpose: str,
    *,
    exposure: str = "redacted_metadata",
) -> Dict[str, Any]:
    paths = paths_for(root)
    project = load_project(paths.root)
    body: Dict[str, Any] = {
        "schema": REQUEST_SCHEMA,
        "created_at_utc": utc_now(),
        "project_id": project.get("project_id"),
        "capability": capability,
        "purpose": purpose,
        "exposure": exposure,
        "status": "pending-default-deny",
        "network_invoked": False,
        "provider": None,
        "provider_endorsement": False,
        "authority_write": False,
        "instructions": (
            "Fulfill locally where possible. If an external provider is considered, review privacy, retention, training, jurisdiction, cost, "
            "and authorization first; export only the minimum necessary content."
        ),
    }
    request_id = sha256_text(canonical_json(body))[:24]
    body["request_id"] = request_id
    directory = paths.state / "capability-requests"
    directory.mkdir(parents=True, exist_ok=True)
    destination = directory / f"{request_id}.json"
    atomic_write_json(destination, body)
    append_ledger(paths.root, "capability.requested", {"request_id": request_id, "capability": capability, "exposure": exposure})
    body["request_relpath"] = destination.relative_to(paths.root).as_posix()
    return body
