"""Tests for bounded free-model burst packets (``uriel burst``)."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from uriel.core import Refusal, initialize_project
from uriel.surfaces import (
    HANDOFF_PHRASE,
    PRIVACY_NOTICE,
    burst_init,
    verify_burst,
)


def _record(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(text.encode("utf-8"))
    return path


class BurstTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name) / "project"
        initialize_project(self.root, title="t", question="q", privacy="public")
        self.record = _record(self.root / "artifacts" / "observations.jsonl", "a\nb\nc\n")

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_init_creates_seven_files_and_verifies(self):
        result = burst_init(self.root, [self.record], next_task="Label the observations.")
        self.assertEqual(len(result["files"]), 7)
        packet = Path(result["packet"])
        self.assertEqual(sorted(path.name for path in packet.iterdir()), sorted(result["files"]))
        self.assertTrue(result["verify"]["verified"])
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
        self.assertIn("6. Write the exact next prompt to NEXT_PROMPT.txt", text)
        self.assertIn("no authority", text.lower())

    def test_next_prompt_contains_handoff_phrase(self):
        result = burst_init(self.root, [self.record], next_task="Draft a hypothesis.")
        packet = Path(result["packet"])
        text = (packet / "NEXT_PROMPT.txt").read_text(encoding="utf-8")
        self.assertIn(HANDOFF_PHRASE, text)

    def test_state_carries_task_and_no_authority(self):
        result = burst_init(self.root, [self.record], next_task="Draft a hypothesis.")
        state = result["state"]
        self.assertEqual(state["next_task"], "Draft a hypothesis.")
        self.assertEqual(state["unresolved_tasks"], ["Draft a hypothesis."])
        self.assertTrue(state["no_authority"])

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

    def test_verify_refuses_missing_packet(self):
        with self.assertRaises(Refusal):
            verify_burst(Path(self.tmp.name) / "nope")

    def test_out_of_root_record_refused(self):
        outside = _record(Path(self.tmp.name) / "outside.txt", "x")
        with self.assertRaises(Refusal):
            burst_init(self.root, [outside], next_task="t")


    def test_missing_task_refused(self):
        with self.assertRaises(Refusal):
            burst_init(self.root, [self.record], next_task="   ")


if __name__ == "__main__":
    unittest.main()
