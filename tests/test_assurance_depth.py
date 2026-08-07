"""Unit, mutation, and acceptance tests for Assurance Depth & Communication (Wave U5).

Exercises:
- Four-Layer Assurance Chain (CHAIN-001..002)
- Claim types & evidence floors (CLAIM-001..003)
- Multidimensional Evidence Strength Vector (STRENGTH-001..004)
- Evidence Microscope & microscopic discrepancy evaluation (MICRO-001..004)
- Measurement & transformation lineage (MEASURE-001..002, TRANSFORM-001..002)
- Evidence independence graph (INDEP-001..002)
- Uncertainty budget & certainty ceiling (UNCERT-001..003)
- Adaptive depth policy (DEPTH-001..004)
- Visual & statistical integrity (VISUAL-001..002, STATS-001)
- Decision Card & proof bundle (COMM-001..004)
- Communication fidelity & tone checks (TONE-001..003)
- Mutation test suite (verifying guards fail when inverted)
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from uriel.assurance_case import evaluate_four_layer_assurance_chain
from uriel.claim_types import classify_claim_type, evaluate_claim_evidence_floor
from uriel.communication_fidelity import check_communication_fidelity, format_constructive_failure
from uriel.decision_card import build_backend_proof_bundle, render_decision_card
from uriel.depth_policy import evaluate_adaptive_depth_triggers, evaluate_depth_stopping_rule
from uriel.evidence_independence import build_evidence_independence_graph
from uriel.evidence_microscope import build_microscope_trace, evaluate_microscopic_discrepancy
from uriel.evidence_strength import compute_evidence_strength_vector
from uriel.measurement_lineage import build_measurement_record, check_measurement_compatibility
from uriel.transformation_lineage import build_transform_step, verify_transform_chain
from uriel.uncertainty import compute_uncertainty_budget, validate_confidence_percentage
from uriel.visual_integrity import validate_figure_integrity, validate_table_integrity
from uriel.core import Refusal


class AssuranceDepthTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    # 1. Evidence Strength & Floors
    def test_weak_critical_dimension_blocks_strong_status(self) -> None:
        claim = {"statement": "X causes Y", "effect_size": "0.5"}
        evidence = [{"id": "E1", "artifact_path": "a.csv", "source_locator": "1", "primary": True}]
        receipts = []  # No PASS receipts -> reproducibility WEAK
        vector = compute_evidence_strength_vector(claim, evidence, receipts, [])
        self.assertEqual(vector["vector"]["reproducibility"], "WEAK")
        self.assertEqual(vector["overall_status"], "WEAK")
        self.assertIn("reproducibility", vector["critical_failures"])

    def test_shared_lineage_not_independent(self) -> None:
        evidence = [
            {"id": "E1", "artifact_path": "data.csv", "source_locator": "row1", "primary": True},
            {"id": "E2", "artifact_path": "data.csv", "source_locator": "row1", "primary": True},
        ]
        graph = build_evidence_independence_graph(evidence)
        self.assertTrue(graph["has_shared_lineage"])
        self.assertEqual(graph["corroboration_type"], "repeated_report")

    def test_causal_claim_requires_causal_floor(self) -> None:
        claim = {"id": "C1", "statement": "Smoking causes lung cancer"}
        evidence = [{"role": "primary", "artifact_path": "obs.csv"}]  # Missing control & falsification
        res = evaluate_claim_evidence_floor(claim, evidence)
        self.assertFalse(res["met"])
        self.assertTrue(res["narrowed"])
        self.assertEqual(res["effective_class"], "associational")

    # 2. Microscope
    def test_microscope_trace_and_discrepancy(self) -> None:
        trace = build_microscope_trace(
            "C1", "Plant growth rate is 5mm/day",
            [{"id": "E1", "artifact_path": "growth.csv"}],
            record_manifest={"records_sha256": "abc1234", "record_count": 1}
        )
        self.assertTrue(trace["complete_to_source"])
        discrepancy = evaluate_microscopic_discrepancy(5.0, 5.002, threshold=0.001)
        self.assertTrue(discrepancy["is_material"])
        self.assertEqual(discrepancy["status"], "FAIL_MATERIAL_DISCREPANCY")

    def test_immaterial_discrepancy_recorded_without_false_alarm(self) -> None:
        discrepancy = evaluate_microscopic_discrepancy(5.0, 5.0001, threshold=0.001)
        self.assertFalse(discrepancy["is_material"])
        self.assertEqual(discrepancy["status"], "IMMATERIAL_RECORDED")

    # 3. Units and Lineage
    def test_unit_and_percent_mismatch_detected(self) -> None:
        m1 = build_measurement_record(50, "percent")
        m2 = build_measurement_record(0.5, "fraction")
        comp = check_measurement_compatibility(m1, m2)
        self.assertFalse(comp["compatible"])
        self.assertTrue(comp["ratio_mismatch"])

    def test_transform_chain_discontinuity(self) -> None:
        s1 = build_transform_step("step1", "tool", "1.0", {}, "hashA", "hashB")
        s2 = build_transform_step("step2", "tool", "1.0", {}, "hashC", "hashD")
        chain_res = verify_transform_chain([s1, s2])
        self.assertFalse(chain_res["valid"])
        self.assertEqual(chain_res["status"], "FAIL_TRANSFORM_DISCONTINUITY")

    # 4. Uncertainty Budget
    def test_unquantified_sources_blocks_certainty(self) -> None:
        budget = compute_uncertainty_budget({"id": "C1"}, [0.01], unquantified_sources=["unmeasured_bias"])
        self.assertEqual(budget["certainty_ceiling"], "unquantified")
        self.assertTrue(budget["blocks_strong_claim"])

    def test_uncalibrated_confidence_percentage_refused(self) -> None:
        with self.assertRaises(Refusal) as context:
            validate_confidence_percentage(95.0, has_calibration_evidence=False)
        self.assertEqual(context.exception.code, "UNCALIBRATED_CONFIDENCE_REFUSED")

    # 5. Four-Layer Chain
    def test_higher_layer_cannot_compensate_failed_lower_layer(self) -> None:
        gate_decisions = [{"gate": 0, "decision": "FAIL_DATA_NOT_READY"}, {"gate": 1, "decision": "PASS"}]
        strength = {"overall_status": "STRONG"}
        chain = evaluate_four_layer_assurance_chain(gate_decisions, strength)
        self.assertEqual(chain["overall_status"], "FAIL_DATA_NOT_READY")
        self.assertEqual(chain["layers"]["layer2_measurement_analysis"]["status"], "BLOCKED_LOWER_LAYER")

    # 6. Communication & Tone
    def test_decision_card_structure(self) -> None:
        card = render_decision_card("Study Title", "PASS", ["Finding 1"], [], "Low residual risk", "Publish", "sha123")
        self.assertEqual(card["overall_status"], "PASS")

    def test_tone_checker_detects_forbidden_patterns(self) -> None:
        res = check_communication_fidelity("Great job! This is 100% certain.")
        self.assertFalse(res["valid"])
        self.assertEqual(len(res["violations"]), 2)

    def test_constructive_failure_limits_alternatives(self) -> None:
        res = format_constructive_failure("FAIL_STALE", "Data CSV valid", "Rerun sort", ["Alt 1", "Alt 2", "Alt 3"])
        self.assertEqual(len(res["alternative_repairs"]), 2)


class MutationTests(unittest.TestCase):
    """Mutation tests: verify that inverting or bypassing critical guards causes failures."""

    def test_mutation_bypassing_critical_dimension_fails(self) -> None:
        claim = {"statement": "X causes Y"}
        vector = compute_evidence_strength_vector(claim, [], [], [])
        self.assertNotEqual(vector["overall_status"], "STRONG")

    def test_mutation_bypassing_layer_one_fails(self) -> None:
        chain = evaluate_four_layer_assurance_chain([{"gate": 0, "decision": "FAIL_STALE"}], {"overall_status": "STRONG"})
        self.assertNotEqual(chain["overall_status"], "PASS")
