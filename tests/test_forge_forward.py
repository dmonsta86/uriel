"""R3.3 Forge continuation, Next Move, and sanitized export adversity tests."""
from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, initialize_project
from uriel.forge_engine import INIT_REQUEST_SCHEMA, forge_init, forge_transition
from uriel.forge_forward import (
    BENEFIT_DIMENSIONS,
    BURDEN_DIMENSIONS,
    CHECK_IDS,
    FORWARD_REQUEST_SCHEMA,
    forge_continue,
    forge_export,
    load_forward_request,
    verify_forge_continuation,
    verify_forge_export,
)


BASE_TIME = "2026-08-11T12:00:00Z"


class ForgeForwardTests(unittest.TestCase):
    @staticmethod
    def _run_cli(*args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        source = str(Path(__file__).resolve().parents[1] / "src")
        env["PYTHONPATH"] = source + os.pathsep + env.get("PYTHONPATH", "")
        return subprocess.run(
            [sys.executable, "-m", "uriel", *args],
            text=True,
            capture_output=True,
            env=env,
            check=False,
        )

    def _workspace(self, base: Path) -> tuple[Path, dict]:
        root = base / "project"
        initialize_project(
            root,
            title="Private Person Research Lab",
            question="Can an incomplete exact run preserve a safe forward path?",
        )
        artifacts = root / "artifacts"
        artifacts.mkdir(parents=True, exist_ok=True)
        (artifacts / "public-evidence.txt").write_text(
            "PUBLIC-CONTENT-MUST-NOT-BE-COPIED",
            encoding="utf-8",
        )
        (artifacts / "sanitizable-evidence.txt").write_text(
            "SANITIZABLE-BODY-MUST-NOT-BE-COPIED",
            encoding="utf-8",
        )
        (artifacts / "private-person-name.txt").write_text(
            "PERSONAL-SECRET-CONTENT",
            encoding="utf-8",
        )
        (artifacts / "private-schema-record.json").write_text(
            json.dumps(
                {
                    "schema": "uriel.private_person.v1",
                    "evidence_body": "CUSTOM-SCHEMA-BODY-MUST-NOT-BE-COPIED",
                }
            ),
            encoding="utf-8",
        )
        references = [
            self._ref("ref-public", "artifacts/public-evidence.txt", "PUBLIC"),
            self._ref("ref-sanitizable", "artifacts/sanitizable-evidence.txt", "SANITIZABLE_METADATA"),
            self._ref("ref-private", "artifacts/private-person-name.txt", "PRIVATE"),
            {
                "ref_id": "ref-private-schema",
                "role": "EVIDENCE",
                "record_schema": "uriel.private_person.v1",
                "path": "artifacts/private-schema-record.json",
                "media_type": "application/vnd.private-person+json",
                "record_id": None,
                "disclosure": "SANITIZABLE_METADATA",
            },
        ]
        source = forge_init(
            root,
            {
                "schema": INIT_REQUEST_SCHEMA,
                "mission": "Exercise a bounded incomplete Forge run.",
                "non_goals": ["Do not grant upstream authority."],
                "requirements": [
                    {
                        "requirement_id": "req-forward",
                        "statement": "Preserve one evidence-bound next move.",
                        "acceptance_condition": "The continuation independently recomputes.",
                        "source_kind": "OPERATOR",
                    }
                ],
                "references": references,
            },
            created_at_utc="2026-08-11T11:00:00Z",
        )
        return root, source

    @staticmethod
    def _ref(ref_id: str, path: str, disclosure: str) -> dict:
        return {
            "ref_id": ref_id,
            "role": "EVIDENCE",
            "record_schema": None,
            "path": path,
            "media_type": "text/plain",
            "record_id": None,
            "disclosure": disclosure,
        }

    @staticmethod
    def _ratings(benefit: str = "HIGH", burden: str = "LOW") -> dict:
        return {
            **{name: benefit for name in BENEFIT_DIMENSIONS},
            **{name: burden for name in BURDEN_DIMENSIONS},
        }

    @staticmethod
    def _guardrails() -> dict:
        return {
            "ethics_respected": True,
            "law_respected": True,
            "consent_respected": True,
            "privacy_respected": True,
            "resource_limits_respected": True,
            "authority_not_bypassed": True,
        }

    def _move(
        self,
        move_id: str,
        *,
        kind: str = "LOCAL_CHECK",
        addresses: list[str] | None = None,
        inputs: list[str] | None = None,
        benefit: str = "HIGH",
        burden: str = "LOW",
    ) -> dict:
        return {
            "move_id": move_id,
            "kind": kind,
            "action": "Perform the bounded action for " + move_id + ".",
            "completion_condition": "A bound receipt exists for " + move_id + ".",
            "required_input_ids": inputs or [],
            "addresses_check_ids": addresses or [],
            "ratings": self._ratings(benefit, burden),
            "guardrails": self._guardrails(),
        }

    @staticmethod
    def _checks(*, path_found: bool = True, missing: str | None = None) -> list[dict]:
        rows = []
        for identifier in CHECK_IDS:
            if identifier == "VERIFY_REQUIREMENT":
                outcome = "REQUIREMENT_CONFIRMED"
            elif identifier == missing:
                outcome = "NOT_RUN"
            elif identifier == "SEARCH_DECLARED_BOUNDARY" and path_found:
                outcome = "PATH_FOUND"
            else:
                outcome = "NO_PATH"
            rows.append(
                {
                    "check_id": identifier,
                    "outcome": outcome,
                    "evidence_ref_ids": [] if outcome == "NOT_RUN" else ["ref-public"],
                    "finding": "Bounded operator finding for " + identifier + ".",
                }
            )
        return rows

    def _request(
        self,
        *,
        checks: list[dict] | None = None,
        moves: list[dict] | None = None,
        required_inputs: list[dict] | None = None,
    ) -> dict:
        return {
            "schema": FORWARD_REQUEST_SCHEMA,
            "operator_assessment": {
                "established": ["One exact source snapshot independently verifies."],
                "refuted": ["An unbound mutable latest pointer is not required."],
                "unknown": ["The scientific outcome remains unknown."],
                "remains_useful": ["The bounded workflow and evidence map remain useful."],
            },
            "subject_requirement_ids": ["req-forward"],
            "blocker_checks": checks or self._checks(),
            "candidate_moves": moves
            or [
                self._move("move-preferred", addresses=["SEARCH_DECLARED_BOUNDARY"]),
                self._move(
                    "move-alternative",
                    addresses=["TEST_SAFE_ALTERNATIVE"],
                    benefit="MODERATE",
                    burden="MODERATE",
                ),
            ],
            "safe_work_completed": ["Verified the exact source lineage and live references."],
            "required_inputs": required_inputs or [],
        }

    def test_continuation_is_immutable_recomputable_and_authority_neutral(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._workspace(Path(temporary))
            result = forge_continue(
                root,
                source["snapshot_relative_path"],
                self._request(),
                created_at_utc=BASE_TIME,
            )
            self.assertEqual("SEALED", result["status"])
            self.assertEqual("PATH_AVAILABLE", result["blocker_status"])
            self.assertEqual("move-preferred", result["preferred_move_id"])
            self.assertTrue(result["verified"])
            self.assertFalse(result["authority_granted"])
            self.assertEqual((0, 0, 0), (result["network_calls"], result["ai_calls"], result["subprocess_calls"]))

            checked = verify_forge_continuation(root, result["continuation_relative_path"])
            self.assertEqual(result["record_sha256"], checked["record_sha256"])
            packet_path = root / result["continuation_relative_path"]
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            self.assertEqual(7, len(packet["blocker_proof"]["checks"]))
            self.assertEqual(12, len(packet["next_moves"]["ranked"][0]["ratings"]))
            self.assertEqual(
                "ORDINAL_PRIORITY_ONLY_NOT_PROBABILITY_OR_TRUTH",
                packet["next_moves"]["score_interpretation"],
            )
            self.assertIn("untrusted research data", packet["next_prompt"]["text"])
            self.assertFalse(packet["next_prompt"]["automatic_execution"])

            second = forge_continue(
                root,
                source["snapshot_relative_path"],
                self._request(),
                created_at_utc=BASE_TIME,
            )
            self.assertEqual("ALREADY_SEALED", second["status"])
            self.assertEqual(result["record_sha256"], second["record_sha256"])

    def test_external_blocker_requires_external_input_as_rank_one(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._workspace(Path(temporary))
            required = [
                {
                    "input_id": "input-external",
                    "kind": "EXTERNAL",
                    "description": "A third-party archive receipt.",
                    "acceptance_condition": "Its exact digest and disclosure terms are recorded.",
                }
            ]
            bad = self._request(
                checks=self._checks(path_found=False),
                moves=[self._move("move-local", addresses=["NO_PATH_CHALLENGE"])],
                required_inputs=required,
            )
            with self.assertRaises(Refusal) as refused:
                forge_continue(root, source["snapshot_relative_path"], bad, created_at_utc=BASE_TIME)
            self.assertEqual("FORGE_FORWARD_SCHEMA_MISMATCH", refused.exception.code)

            good = self._request(
                checks=self._checks(path_found=False),
                moves=[
                    self._move(
                        "move-request",
                        kind="REQUEST_INPUT",
                        addresses=["NO_PATH_CHALLENGE"],
                        inputs=["input-external"],
                    )
                ],
                required_inputs=required,
            )
            result = forge_continue(root, source["snapshot_relative_path"], good, created_at_utc=BASE_TIME)
            self.assertEqual("EVIDENCED_EXTERNAL_BLOCKER", result["blocker_status"])
            self.assertEqual("move-request", result["preferred_move_id"])

    def test_missing_blocker_work_cannot_be_promoted_to_external_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._workspace(Path(temporary))
            missing = "TEST_SUBSTITUTE_EVIDENCE"
            bad = self._request(
                checks=self._checks(path_found=False, missing=missing),
                moves=[self._move("move-wrong", addresses=["NO_PATH_CHALLENGE"])],
            )
            with self.assertRaises(Refusal) as refused:
                forge_continue(root, source["snapshot_relative_path"], bad, created_at_utc=BASE_TIME)
            self.assertEqual("FORGE_FORWARD_BLOCKER_PROOF_INCOMPLETE", refused.exception.code)

            good = copy.deepcopy(bad)
            good["candidate_moves"][0]["addresses_check_ids"] = [missing]
            result = forge_continue(root, source["snapshot_relative_path"], good, created_at_utc=BASE_TIME)
            self.assertEqual("BLOCKER_NOT_EVIDENCED", result["blocker_status"])

    def test_tie_break_is_stable_and_guardrails_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._workspace(Path(temporary))
            request = self._request(
                moves=[
                    self._move("move-z", addresses=["SEARCH_DECLARED_BOUNDARY"]),
                    self._move("move-a", addresses=["SEARCH_DECLARED_BOUNDARY"]),
                ]
            )
            result = forge_continue(root, source["snapshot_relative_path"], request, created_at_utc=BASE_TIME)
            self.assertEqual("move-a", result["preferred_move_id"])

            unsafe = copy.deepcopy(request)
            unsafe["candidate_moves"][0]["guardrails"]["privacy_respected"] = False
            with self.assertRaises(Refusal) as refused:
                forge_continue(root, source["snapshot_relative_path"], unsafe, created_at_utc="2026-08-11T12:00:01Z")
            self.assertEqual("FORGE_FORWARD_GUARDRAIL_REFUSAL", refused.exception.code)

    def test_continuation_refuses_unknown_refs_terminal_sources_and_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._workspace(Path(temporary))
            unknown = self._request()
            unknown["blocker_checks"][0]["evidence_ref_ids"] = ["ref-unknown"]
            with self.assertRaises(Refusal) as refused:
                forge_continue(root, source["snapshot_relative_path"], unknown, created_at_utc=BASE_TIME)
            self.assertEqual("FORGE_FORWARD_SOURCE_MISMATCH", refused.exception.code)

            result = forge_continue(root, source["snapshot_relative_path"], self._request(), created_at_utc=BASE_TIME)
            packet_path = root / result["continuation_relative_path"]
            packet = json.loads(packet_path.read_text(encoding="utf-8"))
            packet["operator_assessment"]["unknown"] = ["tampered"]
            packet_path.write_text(json.dumps(packet), encoding="utf-8")
            with self.assertRaises(Refusal) as tampered:
                verify_forge_continuation(root, result["continuation_relative_path"])
            self.assertEqual("FORGE_FORWARD_DIGEST_MISMATCH", tampered.exception.code)

        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._workspace(Path(temporary))
            terminal = forge_transition(
                root,
                source["snapshot_relative_path"],
                "ABORTED",
                "The operator ended this bounded trial.",
                created_at_utc=BASE_TIME,
            )
            with self.assertRaises(Refusal) as refused:
                forge_continue(root, terminal["snapshot_relative_path"], self._request(), created_at_utc=BASE_TIME)
            self.assertEqual("FORGE_FORWARD_SOURCE_TERMINAL", refused.exception.code)

    def test_metadata_only_export_excludes_paths_bodies_and_private_identity(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._workspace(Path(temporary))
            result = forge_export(
                root,
                source["snapshot_relative_path"],
                "portable-export",
                created_at_utc=BASE_TIME,
            )
            self.assertEqual("EXPORTED", result["status"])
            self.assertTrue(result["verified"])
            self.assertEqual(3, result["exported_reference_count"])
            self.assertFalse(result["body_exported"])
            self.assertEqual((0, 0, 0), (result["network_calls"], result["ai_calls"], result["subprocess_calls"]))

            manifest_path = root / result["manifest_relative_path"]
            summary_path = manifest_path.parent / "summary.json"
            combined = manifest_path.read_text(encoding="utf-8") + summary_path.read_text(encoding="utf-8")
            for forbidden in (
                "Private Person Research Lab",
                "private-person-name.txt",
                "PERSONAL-SECRET-CONTENT",
                "PUBLIC-CONTENT-MUST-NOT-BE-COPIED",
                "SANITIZABLE-BODY-MUST-NOT-BE-COPIED",
                "CUSTOM-SCHEMA-BODY-MUST-NOT-BE-COPIED",
                "uriel.private_person.v1",
                "vnd.private-person",
                "artifacts/",
            ):
                self.assertNotIn(forbidden, combined)
            self.assertIn("METADATA_ONLY", combined)
            self.assertIn('"media_family": "JSON"', combined)
            self.assertIn('"typed_record": true', combined)
            self.assertNotIn(source["run_id"], combined)

            checked = verify_forge_export(
                root,
                result["manifest_relative_path"],
                source["snapshot_relative_path"],
            )
            self.assertEqual(result["export_id"], checked["export_id"])
            with self.assertRaises(Refusal) as exists:
                forge_export(
                    root,
                    source["snapshot_relative_path"],
                    "portable-export",
                    created_at_utc="2026-08-11T12:00:01Z",
                )
            self.assertEqual("FORGE_EXPORT_DESTINATION_EXISTS", exists.exception.code)

            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            summary["requirement_count"] += 1
            summary_path.write_text(json.dumps(summary), encoding="utf-8")
            with self.assertRaises(Refusal) as tampered:
                verify_forge_export(
                    root,
                    result["manifest_relative_path"],
                    source["snapshot_relative_path"],
                )
            self.assertEqual("FORGE_EXPORT_DIGEST_MISMATCH", tampered.exception.code)

    def test_request_loader_rejects_duplicate_keys_and_unknown_fields(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, _ = self._workspace(Path(temporary))
            request_path = root / "artifacts" / "forward.json"
            request_path.write_text(
                '{"schema":"uriel.forge_forward_request.v1","schema":"duplicate"}',
                encoding="utf-8",
            )
            with self.assertRaises(Refusal) as duplicate:
                load_forward_request(root, "artifacts/forward.json")
            self.assertEqual("FORGE_FORWARD_SCHEMA_MISMATCH", duplicate.exception.code)

            value = self._request()
            value["unexpected"] = True
            request_path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaises(Refusal) as unknown:
                load_forward_request(root, "artifacts/forward.json")
            self.assertEqual("FORGE_FORWARD_UNKNOWN_FIELD", unknown.exception.code)

    def test_cli_continue_verify_export_and_verify_export(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root, source = self._workspace(Path(temporary))
            request_path = root / "artifacts" / "forward.json"
            request_path.write_text(json.dumps(self._request()), encoding="utf-8")
            continued = self._run_cli(
                "--json",
                "forge",
                "continue",
                "--root",
                str(root),
                "--snapshot",
                source["snapshot_relative_path"],
                "--request",
                "artifacts/forward.json",
            )
            self.assertEqual(0, continued.returncode, continued.stderr)
            continuation = json.loads(continued.stdout)["result"]
            self.assertEqual("PATH_AVAILABLE", continuation["blocker_status"])
            self.assertNotIn(str(root), continued.stdout)

            checked = self._run_cli(
                "--json",
                "forge",
                "verify-continuation",
                "--root",
                str(root),
                "--packet",
                continuation["continuation_relative_path"],
            )
            self.assertEqual(0, checked.returncode, checked.stderr)
            self.assertTrue(json.loads(checked.stdout)["result"]["verified"])

            exported = self._run_cli(
                "--json",
                "forge",
                "export",
                "--root",
                str(root),
                "--snapshot",
                source["snapshot_relative_path"],
                "--destination",
                "cli-export",
            )
            self.assertEqual(0, exported.returncode, exported.stderr)
            export = json.loads(exported.stdout)["result"]
            self.assertFalse(export["body_exported"])
            verified = self._run_cli(
                "--json",
                "forge",
                "verify-export",
                "--root",
                str(root),
                "--manifest",
                export["manifest_relative_path"],
                "--snapshot",
                source["snapshot_relative_path"],
            )
            self.assertEqual(0, verified.returncode, verified.stderr)
            self.assertTrue(json.loads(verified.stdout)["result"]["verified"])


if __name__ == "__main__":
    unittest.main()
