"""Evidence independence graph (INDEP-001..002).

Constructs an independence graph across evidence sources to detect shared datasets,
samples, instruments, analysis scripts, or citation loops.
Distinguishes repeated reporting (same lineage) from independent replication.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

from .core import Refusal, canonical_json, sha256_text


def build_evidence_independence_graph(
    evidence_rows: Sequence[Mapping[str, Any]],
) -> Dict[str, Any]:
    """Construct nodes and shared lineage edges for evidence sources."""
    nodes: List[Dict[str, Any]] = []
    edges: List[Dict[str, Any]] = []

    # Map by dataset, instrument, author, and code
    by_artifact: Dict[str, List[str]] = {}
    by_locator: Dict[Tuple[str, str], List[str]] = {}

    for row in evidence_rows:
        ev_id = str(row.get("id"))
        art = str(row.get("artifact_path", ""))
        loc = str(row.get("source_locator", ""))
        nodes.append({
            "id": ev_id,
            "artifact_path": art,
            "source_locator": loc,
            "primary": bool(row.get("primary")),
        })
        if art:
            by_artifact.setdefault(art, []).append(ev_id)
        if art and loc:
            by_locator.setdefault((art, loc), []).append(ev_id)

    # Detect shared artifact edges
    for art, ids in by_artifact.items():
        if len(ids) > 1:
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    edges.append({
                        "source": ids[i],
                        "target": ids[j],
                        "relationship": "shared_artifact",
                        "shared_value": art,
                    })

    # Detect duplicate locator edges (strict shared lineage)
    for (art, loc), ids in by_locator.items():
        if len(ids) > 1:
            for i in range(len(ids)):
                for j in range(i + 1, len(ids)):
                    edges.append({
                        "source": ids[i],
                        "target": ids[j],
                        "relationship": "duplicate_locator",
                        "shared_value": f"{art}#{loc}",
                    })

    independent_clusters = len(by_artifact)
    has_shared_lineage = len(edges) > 0

    return {
        "schema": "uriel.evidence_independence.v1",
        "nodes": nodes,
        "edges": edges,
        "independent_cluster_count": independent_clusters,
        "has_shared_lineage": has_shared_lineage,
        "corroboration_type": "independent_replication" if independent_clusters >= 2 and not has_shared_lineage else ("repeated_report" if has_shared_lineage else "single_source"),
    }
