"""Mandatory regression and adversarial tests (STRICT_BLESSING_CONTRACT.md section 17).

Each test maps to a numbered section-17 requirement.  Items already proven by
the pre-existing suites are cross-referenced in the docstring rather than
duplicated: test_gate_contract.py covers 5 (missing check ID), 6 (skipped
check), 7 (exception), 9 (NOT_APPLICABLE without predicate), 10 (user
override), 12 (manual decision editing); test_data_readiness.py covers 13
(stale receipt), 24 (ambiguous identity), 26 (order-invariance);
test_gap_register.py covers 27 (packet per class), 28 (completion criteria),
29 (placeholder); tests/test_strict_blessing.py covers 25 (join-by-row),
30 (no Blessing with blockers), 31 (verifier recomputation).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from uriel.audit import audit_project
from uriel.core import (
    Refusal,
    append_ledger,
    initialize_project,
    load_project,
    run_workload,
    save_project,
)
from uriel.data_readiness import make_sort_spec, readiness_check
from uriel.demo import make_passing_project
from uriel.gap_register import build_gap
from uriel.gate_contract import GATE_SPECS, decide_gate, load_gate_decisions
from uriel.gate_failures import AUDIT_TO_FAILURE, FAILURE_TAXONOMY, classify_failure
from uriel.independent_verify import compute_binding_digest, independent_verify, latest_verifier
from uriel.repair_packet import build_repair_packet, verify_repair_packet
from uriel.strict_blessing import (
    blessing_eligibility,
    issue_strict_blessing,
    run_strict_gates,
    strict_gates_from_audit,
    verify_strict_blessing,
)
from tests.test_strict_blessing import _refresh_fixture_receipt

LOW_CONTEXT_DOC = Path(__file__).resolve().parents[1] / "docs" / "low-context-implementation" / "STRICT_BLESSING_LOW_CONTEXT.md"


def _csv(target: Path, header: str, *rows: str) -> None:
    target.write_text("\n".join([header, *rows]) + "\n", encoding="utf-8")


class MandatoryRegressionTests(unittest.TestCase):
    def _rough(self, root: Path) -> None:
        initialize_project(root, title="A rough thought", question="Could plants remember weather?")

    def _ready(self, root: Path) -> None:
        make_passing_project(root)
        _csv(root / "artifacts" / "data.csv", "id,group,value", "a,g1,10", "b,g1,20", "c,g2,30")
        make_sort_spec(root, "artifacts/data.csv", keys=["id"])
        receipt = readiness_check(root)
        self.assertEqual(receipt["receipt"]["decision"], "PASS", receipt["receipt"])
        _refresh_fixture_receipt(root)

    def _eligible(self, root: Path) -> None:
        self._ready(root)
        run_strict_gates(root, persist=True)
        verifier = independent_verify(root)
        self.assertEqual(verifier["decision"], "PASS", verifier["errors"])

    def _claim_project(self, root: Path) -> dict:
        project = load_project(root)
        claim = project["claims"][0]
        return project, claim

    def _add_evidence(self, root: Path, evidence: dict, claim_id: str) -> None:
        project = load_project(root)
        project["evidence"] = [row for row in project.get("evidence", []) if row.get("id") != evidence["id"]]
        project["evidence"].append(evidence)
        for claim in project["claims"]:
            if claim["id"] == claim_id:
                ids = list(claim.get("evidence_ids", []))
                if evidence["id"] not in ids:
                    ids.append(evidence["id"])
                claim["evidence_ids"] = ids
        save_project(root, project, event="test.evidence_mutated", details={"evidence": evidence["id"]})

    def _decisions(self, root: Path) -> dict:
        return {int(row["gate"]): row["decision"] for row in load_gate_decisions(root)}

    def _full_checks(self, gate: int, failing_check: str, status: str) -> list:
        checks = []
        for check_id in GATE_SPECS[gate][1]:
            checks.append({
                "check_id": check_id,
                "status": status if check_id == failing_check else "PASS",
                "evidence": ["Deterministic fixture."],
                "applicability_predicate": None,
            })
        return checks

    # 17.1 Directly refuted central data fails Gate 2 with FAIL_REFUTED.
    def test_17_01_refuted_central_data_fails_gate_two(self) -> None:
        decision = decide_gate(2, self._full_checks(2, "claim_map_complete", "FAIL_REFUTED"),
                               binding_digest="0" * 64)
        self.assertEqual(decision["decision"], "FAIL_REFUTED")

    # 17.2 Incomplete required data fails with FAIL_INCOMPLETE.
    def test_17_02_incomplete_fails_gate_two(self) -> None:
        decision = decide_gate(2, self._full_checks(2, "claim_map_complete", "FAIL_INCOMPLETE"),
                               binding_digest="0" * 64)
        self.assertEqual(decision["decision"], "FAIL_INCOMPLETE")
        self.assertEqual(classify_failure("CLAIM_INCOMPLETE")["status"], "FAIL_INCOMPLETE")

    # 17.3 Contradictory evidence fails with FAIL_CONTRADICTORY.
    def test_17_03_contradictory_fails(self) -> None:
        self.assertEqual(classify_failure("CONTRADICTION_UNRESOLVED")["status"], "FAIL_CONTRADICTORY")
        decision = decide_gate(3, self._full_checks(3, "contradictory_observations", "FAIL_CONTRADICTORY"),
                               binding_digest="0" * 64)
        self.assertEqual(decision["decision"], "FAIL_CONTRADICTORY")

    # 17.4 Data not ready blocks all substantive gates and Blessing.
    def test_17_04_data_not_ready_blocks_all_gates_and_blessing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._rough(root)
            decisions = strict_gates_from_audit(root)
            self.assertEqual(next(d for d in decisions if d["gate"] == 0)["decision"], "FAIL_DATA_NOT_READY")
            for number in (1, 2, 3):
                self.assertEqual(next(d for d in decisions if d["gate"] == number)["decision"],
                                 "FAIL_DATA_NOT_READY", number)
            run_strict_gates(root, persist=True)
            with self.assertRaises(Refusal) as context:
                issue_strict_blessing(root)
            self.assertEqual(context.exception.code, "STRICT_BLESSING_NOT_EARNED")

    # 17.8 A timeout prevents PASS.
    def test_17_08_timeout_prevents_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._eligible(root)
            timed = run_workload(
                root, [__import__("sys").executable, "-c", "import time; time.sleep(60)"],
                timeout=2, workload_id="timeout-probe")
            self.assertEqual(timed["status"], "TIMEOUT")
            decisions = strict_gates_from_audit(root)
            self.assertEqual(next(d for d in decisions if d["gate"] == 2)["decision"], "FAIL_STALE")
            verifier = independent_verify(root)
            self.assertEqual(verifier["decision"], "FAIL")

    # 17.10 A user override cannot change failure to pass.
    def test_17_10_user_override_cannot_flip_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._rough(root)
            project = load_project(root)
            project["waivers"] = [{"claim_id": "*", "gate": 2, "granted": True,
                                   "reason": "Operator override.", "granted_by": "operator"}]
            save_project(root, project, event="test.waiver_override", details={})
            eligibility = blessing_eligibility(root)
            self.assertFalse(eligibility["eligible"])
            with self.assertRaises(Refusal) as context:
                issue_strict_blessing(root)
            self.assertEqual(context.exception.code, "STRICT_BLESSING_NOT_EARNED")

    # 17.11 AI-generated approval cannot change failure to pass.
    def test_17_11_ai_approval_cannot_flip_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._rough(root)
            append_ledger(root, "ai.approval", {"approved": True, "model": "any", "scope": "all gates"})
            self.assertFalse(blessing_eligibility(root)["eligible"])
            with self.assertRaises(Refusal) as context:
                issue_strict_blessing(root)
            self.assertEqual(context.exception.code, "STRICT_BLESSING_NOT_EARNED")
            blessings = root / ".uriel" / "blessings"
            certificates = list(blessings.rglob("certificate.txt")) if blessings.exists() else []
            self.assertEqual(certificates, [])

    # 17.14 Changed data invalidates Gate 2 and Blessing.
    def test_17_14_changed_data_invalidates_gate_two_and_blessing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._eligible(root)
            (root / "artifacts" / "data.csv").write_bytes(
                b"id,group,value\na,g1,10\nb,g1,20\nc,g2,30\nd,g2,40\n")
            run_strict_gates(root, persist=True)
            decisions = self._decisions(root)
            self.assertEqual(decisions[0], "FAIL_STALE")
            self.assertNotEqual(decisions[2], "PASS")
            with self.assertRaises(Refusal) as context:
                issue_strict_blessing(root)
            self.assertEqual(context.exception.code, "STRICT_BLESSING_NOT_EARNED")

    # 17.15 Changed claim language invalidates Gate 1.
    def test_17_15_changed_claim_language_invalidates_gate_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._eligible(root)
            project = load_project(root)
            project["claims"][0]["statement"] = project["claims"][0]["statement"] + " under narrow laboratory conditions."
            save_project(root, project, event="test.claim_language", details={})
            verifier = independent_verify(root)
            self.assertEqual(verifier["decision"], "FAIL")
            self.assertTrue(any("Gate 1" in error for error in verifier["errors"]), verifier["errors"])

    # 17.16 Changed analysis plan invalidates relevant decisions.
    def test_17_16_changed_analysis_plan_invalidates_decisions(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._eligible(root)
            project = load_project(root)
            project["methods"]["analysis_plan"] = project["methods"]["analysis_plan"] + " Re-verify with a larger fixture."
            save_project(root, project, event="test.analysis_plan", details={})
            verifier = independent_verify(root)
            self.assertEqual(verifier["decision"], "FAIL")
            self.assertTrue(any("different binding" in error for error in verifier["errors"]), verifier["errors"])
            self.assertFalse(blessing_eligibility(root)["eligible"])

    # 17.17 Unresolved alternative explanation fails Gate 3.
    def test_17_17_unresolved_alternative_explanation_fails_gate_three(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._eligible(root)
            project = load_project(root)
            project["alternative_explanations"] = []
            save_project(root, project, event="test.alternatives_removed", details={})
            decisions = strict_gates_from_audit(root)
            self.assertEqual(next(d for d in decisions if d["gate"] == 3)["decision"], "FAIL_ADVERSARIAL")
            self.assertFalse(blessing_eligibility(root)["eligible"])

    # 17.18 An omitted material limitation fails Gate 3.
    def test_17_18_omitted_material_limitation_fails_gate_three(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._eligible(root)
            project = load_project(root)
            project["limitations"] = []
            save_project(root, project, event="test.limitations_removed", details={})
            report = audit_project(root, profile="submission")
            codes = {finding.code for gate in report.gates for finding in gate.findings}
            self.assertIn("LIMITATIONS_MISSING", codes)
            decisions = strict_gates_from_audit(root)
            self.assertEqual(next(d for d in decisions if d["gate"] == 3)["decision"], "FAIL_INCOMPLETE")

    # 17.19 A scope-limiting finding fails the unmodified artifact.
    def test_17_19_scope_limiting_finding_fails(self) -> None:
        meta = classify_failure("CLAIM_SCOPE_INCOMPLETE")
        self.assertEqual(meta["status"], "FAIL_SCOPE_MISMATCH")
        self.assertEqual(meta["severity"], "SCOPE_LIMITING")
        check = {"check_id": "claim_map_complete", "status": "FAIL_SCOPE_MISMATCH",
                 "evidence": ["Generalized beyond the observed population."], "applicability_predicate": None}
        decision = decide_gate(2, [check], binding_digest="0" * 64)
        self.assertNotEqual(decision["decision"], "PASS")

    # 17.20 A new narrowed generation can be re-audited.
    def test_17_20_narrowed_generation_can_be_rea_audited(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            rough = Path(temporary) / "rough"
            narrowed = Path(temporary) / "narrowed"
            self._rough(rough)
            decisions = strict_gates_from_audit(rough)
            self.assertTrue(all(d["decision"] != "PASS" for d in decisions))
            self._eligible(narrowed)
            self.assertEqual(blessing_eligibility(narrowed)["eligible"], True)

    # 17.21 Duplicate citations are not counted as independent evidence.
    def test_17_21_duplicate_citations_not_independent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._eligible(root)
            project, claim = self._claim_project(root)
            original = next(row for row in project["evidence"] if row["id"] == claim["evidence_ids"][0])
            duplicate = {key: value for key, value in original.items()}
            duplicate["id"] = "E1-REPEAT"
            duplicate["description"] = "The same page of the same artifact restated."
            duplicate["primary"] = True
            self._add_evidence(root, duplicate, claim["id"])
            report = audit_project(root, profile="submission")
            codes = {finding.code for gate in report.gates for finding in gate.findings}
            self.assertIn("DUPLICATE_CITATION_SOURCE", codes)
            gate2 = next(d for d in strict_gates_from_audit(root) if d["gate"] == 2)
            primary = next(check for check in gate2["checks"] if check["check_id"] == "primary_sources_used")
            self.assertEqual(primary["status"], "FAIL_CONTRADICTORY")
            self.assertNotEqual(gate2["decision"], "PASS")
            verifier = independent_verify(root)
            self.assertEqual(verifier["decision"], "FAIL")

    # 17.22 A paper conclusion without underlying evidence does not satisfy Gate 2.
    def test_17_22_conclusion_without_evidence_fails_gate_two(self) -> None:
        self.assertEqual(
            classify_failure("ATTESTATION_NO_CLAIM_RELIES_ONLY_ON_ANOTHER_AUTHORS_CONCLUSION")["status"],
            "FAIL_UNSUPPORTED")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._eligible(root)
            project = load_project(root)
            project["disclosures"]["attestations"]["no_claim_relies_only_on_another_authors_conclusion"] = False
            save_project(root, project, event="test.attestation_revoked", details={})
            decisions = strict_gates_from_audit(root)
            gate2 = next(d for d in decisions if d["gate"] == 2)
            primary = next(check for check in gate2["checks"] if check["check_id"] == "primary_sources_used")
            self.assertEqual(primary["status"], "FAIL_UNSUPPORTED")

    # 17.23 Unread files are listed and block dependent claims.
    def test_17_23_unread_files_listed_and_block(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._eligible(root)
            hidden = root / ".uriel" / "unread_evidence.txt"
            hidden.write_text("not part of any source snapshot\n", encoding="utf-8")
            project, claim = self._claim_project(root)
            original = next(row for row in project["evidence"] if row["id"] == claim["evidence_ids"][0])
            row = {key: value for key, value in original.items()}
            row["id"] = "E-UNREAD"
            row["artifact_path"] = ".uriel/unread_evidence.txt"
            row["source_locator"] = "exact row: file-level claim without snapshot"
            row["primary"] = True
            self._add_evidence(root, row, claim["id"])
            report = audit_project(root, profile="submission")
            codes = {finding.code for gate in report.gates for finding in gate.findings}
            self.assertIn("EVIDENCE_NOT_MANIFESTED", codes)
            decisions = strict_gates_from_audit(root)
            self.assertNotEqual(next(d for d in decisions if d["gate"] == 2)["decision"], "PASS")

    # 17.27 A failure packet is produced for every failure class.
    def test_17_27_packet_for_every_failure_class(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._rough(root)
            for status in sorted(FAILURE_TAXONOMY):
                if status in {"NEEDS_CLARIFICATION", "NOT_APPLICABLE"}:
                    continue
                gap = build_gap(gate=2, failure_code=status, severity=FAILURE_TAXONOMY[status]["severity"],
                                observed_fact="Observed in the deterministic audit output.",
                                why_it_matters="It blocks the dependent claim.")
                result = build_repair_packet(
                    root, gate=2, gate_name="Evidence & Citation", decision=status,
                    failure_summary="Failure class {0} produced a repair packet.".format(status),
                    gates_results={"status": status, "counts": {"failed": 1}},
                    blockers=[{"failure_code": status, "severity": "BLOCKING",
                               "observed_fact": "Observed.", "why_it_matters": "Blocks the claim."}],
                    gaps=[gap], sorting_plan="SortSpec with primary key id.",
                    repair_plan="Provide the missing exact artifact and rerun.",
                    pivot_options=["Narrow the claim"],
                    evidence_requests=["Primary source artifact"],
                    updated_project_spec="Exact version clarified.",
                    completion_checklist=["Claim maps to an exact artifact with matching hash"],
                    recheck_instructions="Run `uriel audit --profile submission`.",
                    next_prompt="Continue from the completion checklist.",
                )
                verification = verify_repair_packet(result["path"])
                self.assertTrue(verification["verified"], (status, verification["errors"]))
                self.assertFalse(verification.get("placeholder"))

    # 17.28 Every packet contains exact completion criteria and next instructions.
    def test_17_28_packet_has_exact_completion_criteria(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._rough(root)
            gap = build_gap(gate=3, failure_code="FAIL_ADVERSARIAL", severity="BLOCKING",
                            observed_fact="No adversarial test was declared.",
                            why_it_matters="Alternative explanations remain unresolved.",
                            completion_condition="At least one adversarial test resolves every alternative.",
                            verification_command="uriel audit --profile submission")
            result = build_repair_packet(
                root, gate=3, gate_name="Adversarial Integrity", decision="FAIL_ADVERSARIAL",
                failure_summary="Alternative explanations are unresolved.",
                gates_results={"status": "FAIL_ADVERSARIAL", "counts": {"failed": 1}},
                blockers=[{"failure_code": "FAIL_ADVERSARIAL", "severity": "BLOCKING",
                           "observed_fact": "No adversarial test.", "why_it_matters": "Unresolved alternatives."}],
                gaps=[gap], sorting_plan="SortSpec with primary key id.",
                repair_plan="Declare and run one adversarial test.",
                pivot_options=["Narrow the claim"],
                evidence_requests=["Adversarial test protocol"],
                updated_project_spec="Adversarial test declared.",
                completion_checklist=["Alternative explanation resolved by the test"],
                recheck_instructions="Run `uriel audit --profile submission`.",
                next_prompt="Continue from the completion checklist.",
            )
            directory = Path(result["path"])
            rendered = " ".join(path.read_text(encoding="utf-8") for path in directory.rglob("*.md"))
            self.assertIn("completion", rendered.lower())
            self.assertIn("recheck", rendered.lower())

    # 17.32 Cross-platform fixtures produce equivalent authoritative results.
    def test_17_32_cross_platform_fixture_equivalence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._ready(root)
            check = next(c for c in readiness_check(root)["checks"]
                         if c["check"] == "cross_platform_fixture_equivalence")
            self.assertEqual(check["status"], "PASS")

    # 17.33 A low-context task cannot mark itself complete without the exact acceptance test.
    def test_17_33_low_context_requires_exact_acceptance_test(self) -> None:
        self.assertTrue(LOW_CONTEXT_DOC.is_file(), LOW_CONTEXT_DOC)
        text = LOW_CONTEXT_DOC.read_text(encoding="utf-8")
        self.assertIn("python -m unittest", text)
        self.assertIn("tests.test_strict_contract_mandatory", text)

    # 17.34 No production CLI flag bypasses the contract.
    def test_17_34_no_cli_flag_bypasses_contract(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._rough(root)
            for args in (
                ("audit", "--root", root, "--force"),
                ("blessing", "issue", "--root", root, "--skip-gates"),
                ("data", "propose-sort", "--root", root, "--dataset", "artifacts/data.csv", "--confirm"),
            ):
                import os
                import subprocess
                import sys
                env = os.environ.copy()
                env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1] / "src")
                result = subprocess.run(
                    [sys.executable, "-m", "uriel", *[str(item) for item in args]],
                    text=True, capture_output=True, env=env, check=False)
                self.assertNotEqual(result.returncode, 0, args)

    # 17.35 Certificate verification fails after any bound artifact changes.
    def test_17_35_certificate_fails_after_bound_artifact_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._eligible(root)
            issued = issue_strict_blessing(root)
            self.assertTrue(issued["verified"], issued["errors"])
            (root / "analysis.py").write_text("tampered\n", encoding="utf-8")
            checked = verify_strict_blessing(Path(issued["package"]), project_root=root)
            self.assertFalse(checked["verified"])
            self.assertTrue(any("binding" in error.lower() for error in checked["errors"]), checked["errors"])

    # Mutation spot check: inverting a guard changes the gate decision.
    def test_mutation_inverting_classification_changes_decision(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self._eligible(root)
            project = load_project(root)
            project["methods"]["reproducibility_command"] = ""
            save_project(root, project, event="test.reproducibility_removed", details={})
            real = next(d for d in strict_gates_from_audit(root) if d["gate"] == 2)["decision"]
            self.assertEqual(real, "FAIL_REPRODUCIBILITY")
            original = __import__("uriel.strict_blessing", fromlist=["classify_failure"]).classify_failure

            def inverted(code):
                meta = original(code)
                if code == "REPRODUCIBILITY_COMMAND_MISSING":
                    return {**meta, "status": "PASS"}
                return meta

            with mock.patch("uriel.strict_blessing.classify_failure", side_effect=inverted):
                mutated = next(d for d in strict_gates_from_audit(root) if d["gate"] == 2)["decision"]
            self.assertNotEqual(mutated, real)

    # Mutation spot check: every AUDIT_TO_FAILURE code is exercised by a decision path.
    def test_mutation_all_failure_codes_produce_statuses(self) -> None:
        for code, status in AUDIT_TO_FAILURE.items():
            meta = classify_failure(code)
            self.assertEqual(meta["status"], status, code)
            self.assertIn(meta["group"], FAILURE_TAXONOMY[status]["group"] if status in FAILURE_TAXONOMY else "unsupported")
            self.assertTrue(meta["severity"])


if __name__ == "__main__":
    unittest.main()
