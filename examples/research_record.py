"""Synthetic example: freeze, test, audit, conclude, and find a duplicate."""
from __future__ import annotations
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from uriel.record_store import Folder, digest, parse_structured
from uriel import research_record as rr


def run(root):
    store = Folder(root)
    rr.initialize(store, "synthetic-linear", "Does the simulated line have a five-unit offset?", "evidence-neutral")
    control = "Synthetic control: y = 2*x with intercept zero."
    rr.add_record(store, "linear-control", {"kind": "source", "provenance": "synthetic known control",
                  "original_text": control, "sha256": digest(control)})
    rr.add_record(store, "offset", {"kind": "lead", "idea": "five-unit offset", "aliases": ["intercept shift"],
                  "owner": "unassigned", "status": "queued"})
    rr.freeze(store, "prediction", {"lead": "offset", "hypothesis": "y = 2*x + 5",
              "control_source": "linear-control", "control_result": "intercept = 0",
              "effect_size": 5, "effect_derivation": "(2*x+5)-(2*x)=5",
              "unit": "units", "acceptance_criteria": "reproduce zero control; observed offset within 1 unit of zero"})
    # Only now construct the synthetic test observations.
    values = [(x, 2*x) for x in range(5)]
    intercept = sum(y-2*x for x, y in values)/len(values)
    data = json.dumps(values)
    rr.add_record(store, "observations", {"kind": "source", "provenance": "synthetic exact test pairs",
                  "original_text": data, "sha256": digest(data)})
    audit = {
        "statistic_response": "y-2*x changes by 5 under the alternative.",
        "right_observable": "The residual directly measures intercept.",
        "resolution_smoothing": "No smoothing; synthetic precision of 1 unit.",
        "selection_dust_calibration": "All five generated pairs retained; no selection or instrument.",
        "shared_calibration": "Slope 2 was fixed before generation.",
        "equations_units_signs": "Residual r=y-2*x; r positive for upward offset; all quantities in units.",
        "covariance": "Deterministic synthetic pairs; no statistical inference from independent samples.",
    }
    result = {"lead": "offset", "prediction": "prediction", "source": "observations", "result": "zero residual",
              "unit": "units", "mode": "evidence-neutral", "observed_at": datetime.now(timezone.utc).isoformat(),
              "null": True, "effect_estimate": intercept, "sensitivity": 1, "sensitivity_basis": "declared synthetic precision",
              "control_reproduced": True, "control_evidence": "linear-control",
              "acceptance_met": abs(intercept) <= 1, "acceptance_evidence": "observations",
              "audit": {key: {"pass": True, "reason": value} for key, value in audit.items()}}
    recorded = rr.add_result(store, "result", result)
    classification = parse_structured(recorded["content"])["negative_audit"]["classification"]
    rr.conclude(store, "conclusion", {"lead": "offset", "result": "result", "classification": classification,
                "mode": "evidence-neutral", "coincidence": False, "multi_factor": False, "logical_steps": ["freeze alternative", "calculate residual"],
                "alternatives": ["zero intercept"], "workarounds": ["none"], "would_change": "a different synthetic dataset",
                "thoroughness": "one deterministic fixture, not empirical validation", "reviewer": "example"})
    print(json.dumps(rr.check_before_push(store, "intercept shift"), indent=2))


if __name__ == "__main__":
    run(Path(sys.argv[1]))
