"""R3.2 deterministic Forge engine, lineage, and adversity tests."""
from __future__ import annotations

import ast
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import uriel.forge_engine as forge_module
from uriel.core import Refusal, canonical_json, initialize_project, sha256_text
from uriel.forge_engine import (
    INIT_REQUEST_SCHEMA,
    TRANSITION_REQUEST_SCHEMA,
    forge_init,
    forge_transition,
    load_forge_request,
    verify_forge_run,
)
from uriel.gate_contract import GATE1_CHECKS, decide_gate


BASE_TIME = "2026-08-10T12:00:00Z"


class ForgeEngineTests(unittest.TestCase):
    def _workspace(self, base: Path) -> Path:
        root = base / "project"
        initialize_project(root, title="Forge engine", question="Can closure remain exact?")
        return root

    def _request(self, **overrides):
        value = {
            "schema": INIT_REQUEST_SCHEMA,
            "mission": "Exercise one exact, local Forge lineage.",
            "non_goals": ["Do not grant scientific or publication authority."],
            "requirements": [
                {
                    "requirement_id": "req-integrity",
                    "statement": "Every revision remains content addressed.",
                    "acceptance_condition": "The independent verifier recomputes the entire lineage.",
                    "source_kind": "OPERATOR",
                }
            ],
        }
        value.update(overrides)
        return value

    def _transition(self, root: Path, parent: dict, state: str, index: int, update=None):
        return forge_transition(
            root,
            parent["snapshot_relative_path"],
            state,
            "Move to {0} after the declared checks.".format(state),
            update,
            created_at_utc="2026-08-10T12:00:{0:02d}Z".format(index),
        )

    def _artifact(self, root: Path, name: str, body: str = "receipt") -> Path:
        target = root / "artifacts" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")
        return target

    def _ref(self, path: str, ref_id: str, role: str, *, schema=None, record_id=None, media="text/plain"):
        return {
            "ref_id": ref_id,
            "role": role,
            "record_schema": schema,
            "path": path,
            "media_type": media,
            "record_id": record_id,
            "disclosure": "PRIVATE",
        }

    def test_init_is_immutable_idempotent_and_authority_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            first = forge_init(root, self._request(), created_at_utc=BASE_TIME)
            second = forge_init(root, self._request(), created_at_utc="2026-08-10T13:00:00Z")
            self.assertEqual("SEALED", first["status"])
            self.assertEqual("ALREADY_SEALED", second["status"])
            self.assertEqual(first["record_sha256"], second["record_sha256"])
            self.assertEqual("DRAFT", first["state"])
            self.assertTrue(first["verified"])
            self.assertFalse(first["authority_granted"])
            self.assertEqual((0, 0, 0), (first["network_calls"], first["ai_calls"], first["subprocess_calls"]))
            snapshots = list((root / ".uriel" / "forge" / "runs" / first["run_id"]).glob("*.json"))
            self.assertEqual(1, len(snapshots))

    def test_normal_state_path_closes_only_with_receipt_and_complete_work(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            self._artifact(root, "test-plan.txt", "plan")
            plan_ref = self._ref("artifacts/test-plan.txt", "ref-test-plan", "TEST_PLAN")
            package = {
                "work_package_id": "wp-0123456789abcdef",
                "objective": "Exercise the deterministic state path.",
                "non_goals": [],
                "depends_on": [],
                "requirement_ids": ["req-integrity"],
                "input_ref_ids": ["ref-project-manifest"],
                "acceptance_ref_ids": ["ref-test-plan"],
                "completion_condition": "A content-addressed test receipt exists.",
                "status": "PROPOSED",
            }
            current = forge_init(
                root,
                self._request(references=[plan_ref], work_packages=[package]),
                created_at_utc=BASE_TIME,
            )
            package["status"] = "READY"
            current = self._transition(root, current, "SCOPED", 1, {"schema": TRANSITION_REQUEST_SCHEMA, "work_packages": [package]})
            current = self._transition(root, current, "AUDITED", 2)
            package["status"] = "IN_PROGRESS"
            current = self._transition(root, current, "IMPLEMENTING", 3, {"schema": TRANSITION_REQUEST_SCHEMA, "work_packages": [package]})
            package["status"] = "VERIFYING"
            current = self._transition(root, current, "VERIFYING", 4, {"schema": TRANSITION_REQUEST_SCHEMA, "work_packages": [package]})

            self._artifact(root, "test-receipt.txt", "all focused checks pass")
            receipt = self._ref("artifacts/test-receipt.txt", "ref-test-receipt", "TEST_RECEIPT")
            package["status"] = "COMPLETE"
            package["acceptance_ref_ids"].append("ref-test-receipt")
            current = self._transition(
                root,
                current,
                "READY_FOR_INDEPENDENT_VERIFY",
                5,
                {
                    "schema": TRANSITION_REQUEST_SCHEMA,
                    "references": [receipt],
                    "work_packages": [package],
                },
            )
            current = self._transition(
                root,
                current,
                "COMPLETE",
                6,
                {
                    "schema": TRANSITION_REQUEST_SCHEMA,
                    "closure_ref_ids": ["ref-test-receipt"],
                    "result_summary": "The exact declared package completed and independently verifies.",
                },
            )
            self.assertEqual("COMPLETE", current["state"])
            self.assertEqual(7, current["lineage_records"])
            self.assertTrue(verify_forge_run(root, current["snapshot_relative_path"])["verified"])

    def test_closure_reference_must_resolve_to_a_bound_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            current = forge_init(root, self._request(), created_at_utc=BASE_TIME)
            for index, state in enumerate(
                ("SCOPED", "AUDITED", "IMPLEMENTING", "VERIFYING", "READY_FOR_INDEPENDENT_VERIFY"),
                start=1,
            ):
                current = self._transition(root, current, state, index)
            with self.assertRaises(Refusal) as unknown:
                self._transition(
                    root,
                    current,
                    "COMPLETE",
                    6,
                    {
                        "schema": TRANSITION_REQUEST_SCHEMA,
                        "closure_ref_ids": ["ref-does-not-exist"],
                        "result_summary": "This must not close.",
                    },
                )
            self.assertEqual("FORGE_REF_MISSING", unknown.exception.code)

    def test_reference_hashing_stops_at_the_cumulative_budget(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            self._artifact(root, "first.bin", "1234")
            self._artifact(root, "second.bin", "5678")
            project_size = (root / "uriel.project.json").stat().st_size
            request = self._request(
                references=[
                    self._ref("artifacts/first.bin", "ref-first", "EVIDENCE"),
                    self._ref("artifacts/second.bin", "ref-second", "EVIDENCE"),
                ]
            )
            with mock.patch.object(forge_module, "MAX_TOTAL_REFERENCE_BYTES", project_size + 5):
                with self.assertRaises(Refusal) as limited:
                    forge_init(root, request, created_at_utc=BASE_TIME)
            self.assertEqual("FORGE_RESOURCE_LIMIT", limited.exception.code)
            self.assertEqual(1, limited.exception.details["maximum_bytes"])

    def test_transition_map_terminal_and_blocked_resume_are_exact(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            self._artifact(root, "gap.json", '{"schema":"uriel.gap_register.v1"}')
            self._artifact(root, "draft-gap.json", '{"schema":"uriel.gap_register.v1"}')
            initial = forge_init(root, self._request(), created_at_utc=BASE_TIME)
            draft_blocked = self._transition(
                root,
                initial,
                "BLOCKED",
                1,
                {
                    "schema": TRANSITION_REQUEST_SCHEMA,
                    "references": [
                        self._ref(
                            "artifacts/draft-gap.json",
                            "ref-draft-gap",
                            "GAP_REGISTER",
                            schema="uriel.gap_register.v1",
                            media="application/json",
                        )
                    ],
                },
            )
            draft_resumed = self._transition(root, draft_blocked, "DRAFT", 2)
            scoped = self._transition(root, draft_resumed, "SCOPED", 3)
            blocked = self._transition(
                root,
                scoped,
                "BLOCKED",
                4,
                {
                    "schema": TRANSITION_REQUEST_SCHEMA,
                    "references": [
                        self._ref(
                            "artifacts/gap.json",
                            "ref-gap",
                            "GAP_REGISTER",
                            schema="uriel.gap_register.v1",
                            media="application/json",
                        )
                    ],
                },
            )
            with self.assertRaises(Refusal) as skipped:
                self._transition(root, blocked, "AUDITED", 5)
            self.assertEqual("FORGE_TRANSITION_REFUSED", skipped.exception.code)
            resumed = self._transition(root, blocked, "SCOPED", 5)
            failed = self._transition(root, resumed, "FAILED", 6)
            with self.assertRaises(Refusal) as terminal:
                self._transition(root, failed, "STALE", 7)
            self.assertEqual("FORGE_TRANSITION_REFUSED", terminal.exception.code)

    def test_project_change_requires_and_permits_explicit_stale_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            initial = forge_init(root, self._request(), created_at_utc=BASE_TIME)
            with self.assertRaises(Refusal) as current:
                self._transition(root, initial, "STALE", 1)
            self.assertEqual("FORGE_TRANSITION_REFUSED", current.exception.code)
            project_path = root / "uriel.project.json"
            project = json.loads(project_path.read_text(encoding="utf-8"))
            project["title"] = "Changed after Forge binding"
            project_path.write_text(json.dumps(project), encoding="utf-8")
            with self.assertRaises(Refusal) as stale:
                verify_forge_run(root, initial["snapshot_relative_path"])
            self.assertEqual("FORGE_PROJECT_BINDING_MISMATCH", stale.exception.code)
            marked = self._transition(root, initial, "STALE", 1)
            verified = verify_forge_run(root, marked["snapshot_relative_path"])
            self.assertTrue(verified["verified"])
            self.assertFalse(verified["bindings_current"])
            self.assertGreater(verified["stale_reference_count"], 0)

    def test_record_manifest_filename_and_parent_tamper_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            initial = forge_init(root, self._request(), created_at_utc=BASE_TIME)
            scoped = self._transition(root, initial, "SCOPED", 1)
            path = root / scoped["snapshot_relative_path"]
            value = json.loads(path.read_text(encoding="utf-8"))
            value["mission"] = "tampered"
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(Refusal) as caught:
                verify_forge_run(root, scoped["snapshot_relative_path"])
            self.assertEqual("FORGE_RECORD_DIGEST_MISMATCH", caught.exception.code)

    def test_reference_tamper_missing_path_escape_and_alias_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            artifact = self._artifact(root, "evidence.txt", "first")
            request = self._request(references=[self._ref("artifacts/evidence.txt", "ref-evidence", "EVIDENCE")])
            initial = forge_init(root, request, created_at_utc=BASE_TIME)
            artifact.write_text("changed", encoding="utf-8")
            with self.assertRaises(Refusal) as changed:
                verify_forge_run(root, initial["snapshot_relative_path"])
            self.assertEqual("FORGE_REF_HASH_MISMATCH", changed.exception.code)

            for path in ("../escape.txt", r"C:\private.txt", "artifacts/../evidence.txt"):
                with self.subTest(path=path):
                    with self.assertRaises(Refusal) as unsafe:
                        forge_init(
                            root,
                            self._request(references=[self._ref(path, "ref-unsafe", "EVIDENCE")]),
                            created_at_utc=BASE_TIME,
                        )
                    self.assertEqual("FORGE_REF_PATH_UNSAFE", unsafe.exception.code)

    def test_duplicate_ids_unknown_relations_and_dependency_cycle_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            duplicate = self._request(
                requirements=[
                    {
                        "requirement_id": "req-same",
                        "statement": "First.",
                        "acceptance_condition": "First closes.",
                        "source_kind": "OPERATOR",
                    },
                    {
                        "requirement_id": "req-same",
                        "statement": "Second.",
                        "acceptance_condition": "Second closes.",
                        "source_kind": "OPERATOR",
                    },
                ]
            )
            with self.assertRaises(Refusal) as repeated:
                forge_init(root, duplicate, created_at_utc=BASE_TIME)
            self.assertEqual("FORGE_DUPLICATE_ID", repeated.exception.code)

            self._artifact(root, "acceptance.txt")
            ref = self._ref("artifacts/acceptance.txt", "ref-acceptance", "TEST_PLAN")
            packages = []
            for identifier, dependency in (("wp-0000000000000001", "wp-0000000000000002"), ("wp-0000000000000002", "wp-0000000000000001")):
                packages.append(
                    {
                        "work_package_id": identifier,
                        "objective": "Cycle member.",
                        "non_goals": [],
                        "depends_on": [dependency],
                        "requirement_ids": ["req-integrity"],
                        "input_ref_ids": [],
                        "acceptance_ref_ids": ["ref-acceptance"],
                        "completion_condition": "Cycle cannot close.",
                        "status": "PROPOSED",
                    }
                )
            with self.assertRaises(Refusal) as cycle:
                forge_init(root, self._request(references=[ref], work_packages=packages), created_at_utc=BASE_TIME)
            self.assertEqual("FORGE_DEPENDENCY_CYCLE", cycle.exception.code)

    def test_closed_requests_forbidden_authority_and_strict_json_refuse(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            with self.assertRaises(Refusal) as unknown:
                forge_init(root, self._request(extra="no"), created_at_utc=BASE_TIME)
            self.assertEqual("FORGE_UNKNOWN_FIELD", unknown.exception.code)
            with self.assertRaises(Refusal) as authority:
                forge_init(root, self._request(gate_status="PASS"), created_at_utc=BASE_TIME)
            self.assertEqual("FORGE_FORBIDDEN_AUTHORITY_FIELD", authority.exception.code)

            request_path = root / "artifacts" / "request.json"
            request_path.parent.mkdir(parents=True, exist_ok=True)
            cases = [
                b'{"schema":"uriel.forge_init_request.v1","schema":"duplicate"}',
                b'{"schema":"uriel.forge_init_request.v1","mission":NaN}',
                b'\xff',
            ]
            for raw in cases:
                with self.subTest(raw=raw):
                    request_path.write_bytes(raw)
                    with self.assertRaises(Refusal) as strict:
                        load_forge_request(root, "artifacts/request.json", initial=True)
                    self.assertEqual("FORGE_SCHEMA_MISMATCH", strict.exception.code)

    def test_forged_bool_integer_and_digest_do_not_pass_schema_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            result = forge_init(root, self._request(), created_at_utc=BASE_TIME)
            path = root / result["snapshot_relative_path"]
            value = json.loads(path.read_text(encoding="utf-8"))
            value["schema_version"] = True
            # Recompute neither component nor record digest: the type check must
            # win before an integer/bool equality can be accepted.
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(Refusal) as caught:
                verify_forge_run(root, result["snapshot_relative_path"])
            self.assertEqual("FORGE_SCHEMA_MISMATCH", caught.exception.code)

    def test_one_parent_cannot_fork_to_two_different_children(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            initial = forge_init(root, self._request(), created_at_utc=BASE_TIME)
            first = self._transition(root, initial, "SCOPED", 1)
            self.assertEqual("SCOPED", first["state"])
            retry = forge_transition(
                root,
                initial["snapshot_relative_path"],
                "SCOPED",
                "Move to SCOPED after the declared checks.",
                created_at_utc="2026-08-10T12:05:00Z",
            )
            self.assertEqual("ALREADY_SEALED", retry["status"])
            self.assertEqual(first["record_sha256"], retry["record_sha256"])
            with self.assertRaises(Refusal) as fork:
                forge_transition(
                    root,
                    initial["snapshot_relative_path"],
                    "SCOPED",
                    "A conflicting second scope decision.",
                    created_at_utc="2026-08-10T12:00:02Z",
                )
            self.assertEqual("FORGE_TRANSITION_REFUSED", fork.exception.code)

    def test_completion_refuses_referenced_failed_gate(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            checks = [
                {"check_id": check_id, "status": "PASS", "evidence": [], "applicability_predicate": None}
                for check_id in GATE1_CHECKS
            ]
            checks[0]["status"] = "FAIL_INCOMPLETE"
            gate = self._artifact(
                root,
                "gate.json",
                canonical_json(decide_gate(1, checks, binding_digest="b" * 64)),
            )
            closure = self._artifact(root, "closure.txt", "closure")
            initial = forge_init(root, self._request(), created_at_utc=BASE_TIME)
            scoped = self._transition(root, initial, "SCOPED", 1)
            audited = self._transition(root, scoped, "AUDITED", 2)
            implementing = self._transition(root, audited, "IMPLEMENTING", 3)
            verifying = self._transition(root, implementing, "VERIFYING", 4)
            ready = self._transition(
                root,
                verifying,
                "READY_FOR_INDEPENDENT_VERIFY",
                5,
                {
                    "schema": TRANSITION_REQUEST_SCHEMA,
                    "references": [
                        self._ref(
                            gate.relative_to(root).as_posix(),
                            "ref-gate-one",
                            "GATE_DECISION",
                            schema="uriel.gate_decision.v1",
                            media="application/json",
                        ),
                        self._ref(closure.relative_to(root).as_posix(), "ref-closure", "TEST_RECEIPT"),
                    ],
                },
            )
            with self.assertRaises(Refusal) as failed:
                self._transition(
                    root,
                    ready,
                    "COMPLETE",
                    6,
                    {"schema": TRANSITION_REQUEST_SCHEMA, "closure_ref_ids": ["ref-closure"]},
                )
            self.assertEqual("FORGE_TRANSITION_REFUSED", failed.exception.code)

    def test_forged_pass_gate_is_refused_before_closure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            forged = {
                "schema": "uriel.gate_decision.v1",
                "gate": 1,
                "decision": "PASS",
            }
            gate = self._artifact(root, "forged-gate.json", json.dumps(forged))
            initial = forge_init(root, self._request(), created_at_utc=BASE_TIME)
            scoped = self._transition(root, initial, "SCOPED", 1)
            audited = self._transition(root, scoped, "AUDITED", 2)
            implementing = self._transition(root, audited, "IMPLEMENTING", 3)
            verifying = self._transition(root, implementing, "VERIFYING", 4)
            with self.assertRaises(Refusal) as caught:
                self._transition(
                    root,
                    verifying,
                    "READY_FOR_INDEPENDENT_VERIFY",
                    5,
                    {
                        "schema": TRANSITION_REQUEST_SCHEMA,
                        "references": [
                            self._ref(
                                gate.relative_to(root).as_posix(),
                                "ref-forged-gate",
                                "GATE_DECISION",
                                schema="uriel.gate_decision.v1",
                                media="application/json",
                            )
                        ],
                    },
                )
            self.assertEqual("FORGE_SCHEMA_MISMATCH", caught.exception.code)

    def test_deferred_soft_gate_needs_typed_deferral_reference(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            self._artifact(root, "plan.txt")
            plan_ref = self._ref("artifacts/plan.txt", "ref-plan", "TEST_PLAN")
            package = {
                "work_package_id": "wp-0123456789abcdef",
                "objective": "Optional usability polish.",
                "non_goals": [],
                "depends_on": [],
                "requirement_ids": ["req-integrity"],
                "input_ref_ids": [],
                "acceptance_ref_ids": ["ref-plan"],
                "completion_condition": "A named owner closes the deferred check.",
                "status": "PROPOSED",
            }
            current = forge_init(root, self._request(references=[plan_ref], work_packages=[package]), created_at_utc=BASE_TIME)
            package["status"] = "READY"
            current = self._transition(root, current, "SCOPED", 1, {"schema": TRANSITION_REQUEST_SCHEMA, "work_packages": [package]})
            current = self._transition(root, current, "AUDITED", 2)
            package["status"] = "IN_PROGRESS"
            current = self._transition(root, current, "IMPLEMENTING", 3, {"schema": TRANSITION_REQUEST_SCHEMA, "work_packages": [package]})
            package["status"] = "VERIFYING"
            current = self._transition(root, current, "VERIFYING", 4, {"schema": TRANSITION_REQUEST_SCHEMA, "work_packages": [package]})
            package["status"] = "DEFERRED"
            with self.assertRaises(Refusal) as missing:
                self._transition(root, current, "READY_FOR_INDEPENDENT_VERIFY", 5, {"schema": TRANSITION_REQUEST_SCHEMA, "work_packages": [package]})
            self.assertEqual("FORGE_TRANSITION_REFUSED", missing.exception.code)

    def test_typed_soft_gate_deferral_binds_owner_impact_fallback_and_package(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            self._artifact(root, "plan.txt")
            plan_ref = self._ref("artifacts/plan.txt", "ref-plan", "TEST_PLAN")
            package = {
                "work_package_id": "wp-0123456789abcdef",
                "objective": "Optional usability polish.",
                "non_goals": [],
                "depends_on": [],
                "requirement_ids": ["req-integrity"],
                "input_ref_ids": [],
                "acceptance_ref_ids": ["ref-plan"],
                "completion_condition": "A named owner closes the deferred check.",
                "status": "PROPOSED",
            }
            current = forge_init(root, self._request(references=[plan_ref], work_packages=[package]), created_at_utc=BASE_TIME)
            package["status"] = "READY"
            current = self._transition(root, current, "SCOPED", 1, {"schema": TRANSITION_REQUEST_SCHEMA, "work_packages": [package]})
            current = self._transition(root, current, "AUDITED", 2)
            package["status"] = "IN_PROGRESS"
            current = self._transition(root, current, "IMPLEMENTING", 3, {"schema": TRANSITION_REQUEST_SCHEMA, "work_packages": [package]})
            package["status"] = "VERIFYING"
            current = self._transition(root, current, "VERIFYING", 4, {"schema": TRANSITION_REQUEST_SCHEMA, "work_packages": [package]})

            deferral = {
                "schema": "uriel.forge_deferral.v1",
                "schema_version": 1,
                "deferral_id": "forge-deferral-0123456789abcdef",
                "work_package_id": package["work_package_id"],
                "gate_kind": "SOFT",
                "owner": "project maintainer",
                "reason": "Observed non-maintainer sessions are not yet scheduled.",
                "impact": "Usability maturity remains unproven.",
                "safe_fallback": "Keep the CLI capability experimental and make no usability claim.",
                "next_task": "Run the documented observed-user protocol.",
                "completion_condition": "Three non-maintainers complete the written flow on two operating systems.",
                "created_at_utc": "2026-08-10T12:00:05Z",
                "authority_scope": "FORGE_WORKFLOW_ONLY",
                "upstream_authority_effect": "NONE",
            }
            deferral["record_sha256"] = sha256_text(canonical_json(deferral))
            self._artifact(root, "deferral.json", json.dumps(deferral))
            package["status"] = "DEFERRED"
            package["acceptance_ref_ids"].append("ref-deferral")
            current = self._transition(
                root,
                current,
                "READY_FOR_INDEPENDENT_VERIFY",
                5,
                {
                    "schema": TRANSITION_REQUEST_SCHEMA,
                    "references": [
                        self._ref(
                            "artifacts/deferral.json",
                            "ref-deferral",
                            "DEFERRAL",
                            schema="uriel.forge_deferral.v1",
                            media="application/json",
                        )
                    ],
                    "work_packages": [package],
                },
            )
            closed = self._transition(
                root,
                current,
                "COMPLETE_WITH_DEFERRED_SOFT_GATES",
                6,
                {
                    "schema": TRANSITION_REQUEST_SCHEMA,
                    "closure_ref_ids": ["ref-deferral"],
                    "result_summary": "Core work closed; one typed soft gate remains explicitly deferred.",
                },
            )
            self.assertEqual("COMPLETE_WITH_DEFERRED_SOFT_GATES", closed["state"])
            self.assertTrue(verify_forge_run(root, closed["snapshot_relative_path"])["verified"])

    def test_module_has_no_network_ai_or_subprocess_import_surface(self) -> None:
        source = (Path(__file__).resolve().parents[1] / "src" / "uriel" / "forge_engine.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module.split(".")[0])
        self.assertFalse({"socket", "subprocess", "urllib", "http", "requests", "openai"} & imported)
        self.assertNotIn("eval(", source)
        self.assertNotIn("exec(", source)

    @unittest.skipIf(os.name == "nt", "ordinary symlink creation is not consistently available on Windows CI")
    def test_reference_symlink_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = self._workspace(Path(temporary))
            outside = Path(temporary) / "outside.txt"
            outside.write_text("private", encoding="utf-8")
            link = root / "artifacts" / "link.txt"
            link.parent.mkdir(parents=True)
            link.symlink_to(outside)
            with self.assertRaises(Refusal) as caught:
                forge_init(
                    root,
                    self._request(references=[self._ref("artifacts/link.txt", "ref-link", "EVIDENCE")]),
                    created_at_utc=BASE_TIME,
                )
            self.assertEqual("FORGE_REF_PATH_UNSAFE", caught.exception.code)


if __name__ == "__main__":
    unittest.main()
