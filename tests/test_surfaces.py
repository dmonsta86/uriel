"""Tests for bounded free-model burst packets (``uriel burst``)."""
from __future__ import annotations

import json
import hashlib
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, canonical_json, initialize_project
from uriel.data_contracts import plan_data_import
from uriel.data_desk import inspect_data_artifact
from uriel.data_ingress import import_data_artifact
from uriel.data_readiness import make_generation_sort_spec, readiness_check, readiness_status
from uriel.surfaces import (
    HANDOFF_PHRASE,
    MAX_BURST_PACKET_BYTES,
    MAX_BURST_SOURCE_FILE_BYTES,
    MAX_BURST_TASK_BYTES,
    PRIVACY_NOTICE,
    TASK_CAPABILITIES,
    burst_init,
    verify_burst,
)


def _record(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


def _reseal_packet(packet: Path) -> None:
    lines = []
    for path in sorted(packet.iterdir()):
        if path.name == "SHA256SUMS.txt":
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        lines.append("{0}  {1}".format(digest, path.name))
    (packet / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


class BurstTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        initialize_project(self.root, title="t", question="q", privacy="public")
        self.record = _record(self.root / "artifacts" / "observations.jsonl", "a\nb\nc\n")

    def _generation(self) -> dict:
        source = Path(self.tmp.name) / "selected.csv"
        source.write_text("id,value,private\na,1,secret-a\nb,2,secret-b\n", encoding="utf-8")
        plan = plan_data_import(self.root, source, label="selected")["plan"]
        plan_path = self.root / "artifacts" / "data-plan.json"
        plan_path.write_text(canonical_json(plan), encoding="utf-8")
        imported = import_data_artifact(
            self.root, source, plan_path.relative_to(self.root).as_posix()
        )
        return inspect_data_artifact(self.root, imported["receipt_relative_path"])

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_init_creates_seven_files_and_verifies(self):
        result = burst_init(self.root, [self.record], next_task="Label the observations.")
        self.assertEqual(len(result["files"]), 7)
        packet = Path(result["packet"])
        self.assertEqual(sorted(path.name for path in packet.iterdir()), sorted(result["files"]))
        self.assertTrue(result["verify"]["verified"])
        self.assertLessEqual(result["packet_bytes"], MAX_BURST_PACKET_BYTES)
        self.assertEqual(result["packet_bytes"], result["verify"]["packet_bytes"])
        for name in (
            "00_INSTRUCTION.md",
            "STATE.json",
            "SOURCE_MANIFEST.json",
            "SELECTED_RECORDS.jsonl",
            "OUTPUT_REQUIREMENTS.md",
            "NEXT_PROMPT.txt",
            "SHA256SUMS.txt",
        ):
            self.assertTrue((packet / name).is_file())

    def test_instruction_contains_privacy_notice_and_numbered_tasks(self):
        result = burst_init(self.root, [self.record], next_task="Draft a hypothesis.")
        packet = Path(result["packet"])
        text = (packet / "00_INSTRUCTION.md").read_text(encoding="utf-8")
        self.assertIn(PRIVACY_NOTICE, text)
        self.assertIn("1. Read STATE.json, SOURCE_MANIFEST.json", text)
        self.assertIn("4. Ask all unavoidable questions in ONE numbered batch", text)
        self.assertIn("6. Return the exact next prompt as a labeled output section", text)
        self.assertIn("no authority", text.lower())

    def test_next_prompt_contains_handoff_phrase(self):
        result = burst_init(self.root, [self.record], next_task="Draft a hypothesis.")
        packet = Path(result["packet"])
        text = (packet / "NEXT_PROMPT.txt").read_text(encoding="utf-8")
        self.assertIn(HANDOFF_PHRASE, text)
        self.assertIn("00_INSTRUCTION.md", text)
        self.assertNotIn("00_READ_ME_FIRST.md", text)

    def test_state_carries_task_and_no_authority(self):
        result = burst_init(self.root, [self.record], next_task="Draft a hypothesis.")
        state = result["state"]
        self.assertEqual(state["next_task"], "Draft a hypothesis.")
        self.assertEqual(state["unresolved_tasks"], ["Draft a hypothesis."])
        self.assertTrue(state["no_authority"])
        self.assertEqual(TASK_CAPABILITIES, state["task_capabilities"])
        self.assertEqual("DENIED", state["task_capabilities"]["network"])
        self.assertEqual("DENIED", state["task_capabilities"]["shell"])
        self.assertEqual("DENIED", state["task_capabilities"]["project_writes"])

    def test_selected_records_are_hashed_and_bounded(self):
        result = burst_init(self.root, [self.record], next_task="t")
        packet = Path(result["packet"])
        lines = (packet / "SELECTED_RECORDS.jsonl").read_text(encoding="utf-8").splitlines()
        row = json.loads(lines[0])
        self.assertEqual(row["name"], "artifacts/observations.jsonl")
        self.assertRegex(row["sha256"], r"^[0-9a-f]{64}$")
        self.assertEqual(row["content"], "a\nb\nc\n")

    def test_redact_removes_bodies_keeps_hashes(self):
        result = burst_init(self.root, [self.record], next_task="t", redact=True)
        packet = Path(result["packet"])
        lines = (packet / "SELECTED_RECORDS.jsonl").read_text(encoding="utf-8").splitlines()
        row = json.loads(lines[0])
        self.assertIn("redacted", row["content"])
        self.assertRegex(row["content_sha256"], r"^[0-9a-f]{64}$")
        self.assertTrue(result["redacted"])

    def test_budget_truncates_oversized_bodies(self):
        big = _record(self.root / "artifacts" / "big.txt", "x" * 5000)
        result = burst_init(self.root, [big], next_task="t", budget_bytes=1024)
        packet = Path(result["packet"])
        lines = (packet / "SELECTED_RECORDS.jsonl").read_text(encoding="utf-8").splitlines()
        row = json.loads(lines[0])
        self.assertIn("exceeds packet budget", row["content"])

    def test_continue_creates_next_packet_with_parent_state(self):
        first = burst_init(self.root, [self.record], next_task="Step one")
        second = burst_init(self.root, [self.record], next_task="Step two")
        self.assertEqual(second["packet_index"], first["packet_index"] + 1)
        state = second["state"]
        self.assertEqual(state["parent_packet"], first["packet_index"])
        self.assertIn("Step one", state["completed_tasks"])
        self.assertEqual(state["next_task"], "Step two")

    def test_verify_detects_tamper(self):
        result = burst_init(self.root, [self.record], next_task="t")
        packet = Path(result["packet"])
        (packet / "NEXT_PROMPT.txt").write_text("tampered", encoding="utf-8")
        check = verify_burst(packet)
        self.assertFalse(check["verified"])
        self.assertIn("NEXT_PROMPT.txt", check["mismatched"])

    def test_tampered_parent_cannot_be_carried_into_a_new_packet(self):
        first = burst_init(self.root, [self.record], next_task="Step one")
        packet = Path(first["packet"])
        (packet / "STATE.json").write_text("{}\n", encoding="utf-8")
        with self.assertRaises(Refusal) as caught:
            burst_init(self.root, [self.record], next_task="Step two")
        self.assertEqual("BURST_PARENT_INVALID", caught.exception.code)

    def test_resealed_parent_rewrite_breaks_child_hash_chain(self):
        first = burst_init(self.root, [self.record], next_task="Step one")
        second = burst_init(self.root, [self.record], next_task="Step two")
        first_packet = Path(first["packet"])
        state_path = first_packet / "STATE.json"
        state = json.loads(state_path.read_text(encoding="utf-8"))
        state["questions_asked"] = ["rewritten history"]
        state_path.write_text(json.dumps(state, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        _reseal_packet(first_packet)
        self.assertTrue(verify_burst(first_packet)["verified"])
        checked = verify_burst(Path(second["packet"]))
        self.assertFalse(checked["verified"])
        self.assertTrue(any("parent burst packet hash" in row for row in checked["semantic_errors"]))

    def test_empty_link_output_path_cannot_escape_project(self):
        outside = Path(self.tmp.name) / "outside-burst-target"
        outside.mkdir()
        bursts = self.root / ".uriel" / "bursts"
        bursts.mkdir(parents=True)
        link = bursts / "burst-001"
        try:
            link.symlink_to(outside, target_is_directory=True)
        except OSError as exc:
            self.skipTest("directory symlinks are unavailable: {0}".format(exc))
        with self.assertRaises(Refusal) as caught:
            burst_init(self.root, [self.record], next_task="t", packet_index=1)
        self.assertIn(caught.exception.code, {"LINK_TRAVERSAL_REFUSAL", "BURST_LINK_REFUSED"})
        self.assertEqual([], list(outside.iterdir()))

    def test_checksum_manifest_cannot_traverse_outside_packet(self):
        result = burst_init(self.root, [self.record], next_task="t")
        packet = Path(result["packet"])
        sums = packet / "SHA256SUMS.txt"
        sums.write_text(
            sums.read_text(encoding="utf-8") + ("0" * 64) + "  ../outside.txt\n",
            encoding="utf-8",
        )
        checked = verify_burst(packet)
        self.assertFalse(checked["verified"])
        self.assertTrue(any("checksum line" in row for row in checked["manifest_errors"]))

    def test_nonempty_output_directory_and_oversized_task_are_refused(self):
        occupied = self.root / ".uriel" / "bursts" / "burst-001"
        occupied.mkdir(parents=True)
        (occupied / "unrelated.txt").write_text("do not adopt", encoding="utf-8")
        with self.assertRaises(Refusal) as output:
            burst_init(self.root, [self.record], next_task="t", packet_index=1)
        self.assertEqual("BURST_OUTPUT_EXISTS", output.exception.code)
        self.assertEqual("do not adopt", (occupied / "unrelated.txt").read_text(encoding="utf-8"))

        with self.assertRaises(Refusal) as task:
            burst_init(
                self.root,
                [self.record],
                next_task="x" * (MAX_BURST_TASK_BYTES + 1),
                packet_index=2,
            )
        self.assertEqual("BURST_TASK_BUDGET", task.exception.code)

    def test_verify_refuses_missing_packet(self):
        with self.assertRaises(Refusal):
            verify_burst(Path(self.tmp.name) / "nope")

    def test_out_of_root_record_refused(self):
        outside = _record(Path(self.tmp.name) / "outside.txt", "x")
        with self.assertRaises(Refusal):
            burst_init(self.root, [outside], next_task="t")

    def test_oversized_legacy_source_is_refused_before_read_or_hash(self):
        oversized = self.root / "artifacts" / "oversized.bin"
        with oversized.open("wb") as stream:
            stream.truncate(MAX_BURST_SOURCE_FILE_BYTES + 1)
        with self.assertRaises(Refusal) as caught:
            burst_init(self.root, [oversized], next_task="t")
        self.assertEqual("BURST_SOURCE_BUDGET", caught.exception.code)


    def test_missing_task_refused(self):
        with self.assertRaises(Refusal):
            burst_init(self.root, [self.record], next_task="   ")

    def test_generation_burst_requires_readiness_and_exposes_only_explicit_projection(self):
        generation = self._generation()
        with self.assertRaises(Refusal) as unready:
            burst_init(
                self.root,
                [],
                next_task="Review row b.",
                generation_id=generation["generation_id"],
                generation_columns=["id", "value"],
                row_indices=[1],
                row_limit=1,
                budget_bytes=4096,
            )
        self.assertEqual("READINESS_GENERATION_NOT_READY", unready.exception.code)

        spec = make_generation_sort_spec(
            self.root, generation["generation_id"], keys=["id"]
        )
        receipt = readiness_check(
            self.root, spec["path"], generation=generation["generation_id"]
        )
        result = burst_init(
            self.root,
            [],
            next_task="Review row b.",
            generation_id=generation["generation_id"],
            generation_columns=["id", "value"],
            row_indices=[1],
            row_limit=1,
            budget_bytes=4096,
            readiness_sort_spec=spec["path"],
            readiness_receipt=receipt["path"],
        )
        packet = Path(result["packet"])
        self.assertEqual(8, len(result["files"]))
        surface = json.loads((packet / "AI_SURFACE.json").read_text(encoding="utf-8"))
        self.assertEqual("uriel.ai_surface.v1", surface["schema"])
        self.assertEqual("Review row b.", surface["allowed_task"])
        self.assertEqual(1, surface["row_limit"])
        self.assertEqual(receipt["receipt_sha256"], surface["acceptance_receipt"])
        self.assertTrue(surface["no_authority"])
        selected_text = (packet / "SELECTED_RECORDS.jsonl").read_text(encoding="utf-8")
        self.assertIn('"source_row_index": 1', selected_text)
        self.assertNotIn("secret-a", selected_text)
        self.assertNotIn("secret-b", selected_text)
        self.assertEqual(
            "PASS",
            readiness_status(
                self.root,
                generation=generation["generation_id"],
                receipt_path=receipt["path"],
            )["decision"],
        )

    def test_generation_burst_redaction_and_global_usage_ceiling(self):
        generation = self._generation()
        spec = make_generation_sort_spec(self.root, generation["generation_id"], keys=["id"])
        receipt = readiness_check(self.root, spec["path"], generation=generation["generation_id"])
        result = burst_init(
            self.root,
            [],
            next_task="Check metadata only.",
            generation_id=generation["generation_id"],
            generation_columns=["private"],
            row_indices=[0],
            row_limit=1,
            budget_bytes=4096,
            readiness_receipt=receipt["path"],
            redact=True,
        )
        selected = (Path(result["packet"]) / "SELECTED_RECORDS.jsonl").read_text(encoding="utf-8")
        self.assertIn("values withheld", selected)
        self.assertNotIn("secret-a", selected)
        with self.assertRaises(Refusal) as excessive:
            burst_init(
                self.root,
                [self.record],
                next_task="t",
                budget_bytes=1024 * 1024 + 1,
            )
        self.assertEqual("BURST_BUDGET_INVALID", excessive.exception.code)

    def test_resealed_detached_ai_surface_is_rejected(self):
        generation = self._generation()
        spec = make_generation_sort_spec(self.root, generation["generation_id"], keys=["id"])
        receipt = readiness_check(self.root, spec["path"], generation=generation["generation_id"])
        result = burst_init(
            self.root,
            [],
            next_task="Review one value.",
            generation_id=generation["generation_id"],
            generation_columns=["value"],
            row_indices=[0],
            row_limit=1,
            budget_bytes=4096,
            readiness_receipt=receipt["path"],
        )
        packet = Path(result["packet"])
        surface_path = packet / "AI_SURFACE.json"
        surface = json.loads(surface_path.read_text(encoding="utf-8"))
        surface["records_sha256"] = "0" * 64
        surface_path.write_text(json.dumps(surface, sort_keys=True, indent=2) + "\n", encoding="utf-8")
        _reseal_packet(packet)
        checked = verify_burst(packet)
        self.assertFalse(checked["verified"])
        self.assertTrue(any("AI surface records_sha256" in row for row in checked["semantic_errors"]))


if __name__ == "__main__":
    unittest.main()
