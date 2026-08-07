"""Four-Layer Assurance Chain (CHAIN-001..002).

Binds every material conclusion across four explicit structural layers:
Layer 1: Data & Acquisition (Data Readiness Gate 0, SortSpec, raw data integrity)
Layer 2: Measurement & Analysis (Gate 1 & Gate 2, transformation lineage, precision)
Layer 3: Inference & Adversarial Testing (Gate 3, alternative explanations, sensitivity)
Layer 4: Communication & Presentation (Decision Card, proof bundle, voice/tone)

A higher layer cannot compensate for a failed lower layer. If Layer 1 fails (e.g. data
not ready or stale), the entire assurance case evaluates to FAIL_DATA_NOT_READY.
"""
from __future__ import annotations

from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import Refusal, canonical_json, canonical_root, sha256_text

ASSURANCE_LAYERS = (
    "layer1_data_acquisition",
    "layer2_measurement_analysis",
    "layer3_inference_adversarial",
    "layer4_communication_presentation",
)


def evaluate_four_layer_assurance_chain(
    gate_decisions: Sequence[Mapping[str, Any]],
    evidence_strength: Mapping[str, Any],
    verifier_receipt: Optional[Mapping[str, Any]] = None,
    decision_card: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    """Evaluate the Four-Layer Assurance Chain in strict hierarchical order."""
    decisions_by_gate = {int(d.get("gate", 0)): str(d.get("decision", "not_run")) for d in gate_decisions}

    # Layer 1: Data & Acquisition
    l1_pass = decisions_by_gate.get(0) == "PASS"
    l1_status = "PASS" if l1_pass else (decisions_by_gate.get(0, "FAIL_DATA_NOT_READY"))

    # Layer 2: Measurement & Analysis
    l2_pass = l1_pass and decisions_by_gate.get(1) == "PASS" and decisions_by_gate.get(2) == "PASS"
    l2_status = "PASS" if l2_pass else ("BLOCKED_LOWER_LAYER" if not l1_pass else "FAIL")

    # Layer 3: Inference & Adversarial
    l3_pass = l2_pass and decisions_by_gate.get(3) == "PASS" and (verifier_receipt or {}).get("decision") == "PASS"
    l3_status = "PASS" if l3_pass else ("BLOCKED_LOWER_LAYER" if not l2_pass else "FAIL")

    # Layer 4: Communication & Presentation
    l4_pass = l3_pass and (decision_card is not None and bool(decision_card.get("valid", True)))
    l4_status = "PASS" if l4_pass else ("BLOCKED_LOWER_LAYER" if not l3_pass else "FAIL")

    chain_status = "PASS" if l4_pass else (l1_status if not l1_pass else (l2_status if not l2_pass else (l3_status if not l3_pass else l4_status)))

    return {
        "schema": "uriel.assurance_case.v1",
        "overall_status": chain_status,
        "layers": {
            "layer1_data_acquisition": {"status": l1_status, "gate": 0},
            "layer2_measurement_analysis": {"status": l2_status, "gates": [1, 2]},
            "layer3_inference_adversarial": {"status": l3_status, "gate": 3, "verifier": bool(verifier_receipt)},
            "layer4_communication_presentation": {"status": l4_status, "decision_card": bool(decision_card)},
        },
        "hierarchical_integrity_maintained": True if (l1_pass or l2_status != "PASS") else False,
    }
