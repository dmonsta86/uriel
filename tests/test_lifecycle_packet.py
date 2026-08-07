from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from uriel.checkpoints import GenerationRefusal
from uriel.packet import (
    packet_id_for,
    packet_placeholders,
    preflight_packet,
    validate_packet_manifest,
    verify_packet,
    write_packet_generation,
)


class PacketTests(unittest.TestCase):
    def _packet(self, store: Path, content: dict, **kwargs) -> tuple:
        return write_packet_generation(
            store,
            packet_type=kwargs.pop("packet_type", "revision_response"),
            project_generation="gen-abc",
            files=content,
            **kwargs,
        )

    def test_packet_generation_writes_files_manifest_and_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            path, manifest = self._packet(
                store, {"00_READ_ME_FIRST.md": b"# Read this first\n", "02_REQUIRED_ACTIONS.csv": b"a,b\n"}
            )
            self.assertTrue(path.is_dir())
            self.assertTrue((path / "MANIFEST.json").is_file())
            self.assertTrue((path / "SHA256SUMS.txt").is_file())
            self.assertEqual([], validate_packet_manifest(manifest))
            self.assertEqual(2, len(manifest["files"]))
            self.assertEqual("revision_response", manifest["packet_type"])
            self.assertIsNone(manifest["parent_packet_id"])
            self.assertEqual("pass", verify_packet(path)["status"])

    def test_packet_id_is_content_addressed(self) -> None:
        from uriel.core import sha256_text

        digest = sha256_text("same\n")
        entry = ("00_READ_ME_FIRST.md", digest)
        self.assertEqual(packet_id_for("archive", [entry]), packet_id_for("archive", [entry]))
        self.assertNotEqual(packet_id_for("archive", [entry]), packet_id_for("archive", [("00_READ_ME_FIRST.md", "2" * 64)]))

    def test_identical_rebuild_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            first_path, first_manifest = self._packet(store, {"00_READ_ME_FIRST.md": b"x\n"})
            second_path, second_manifest = self._packet(store, {"00_READ_ME_FIRST.md": b"x\n"})
            self.assertEqual(first_path, second_path)
            self.assertEqual(first_manifest["packet_id"], second_manifest["packet_id"])

    def test_changed_content_is_new_generation_and_never_overwrites(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            first_path, first_manifest = self._packet(store, {"00_READ_ME_FIRST.md": b"v1\n"})
            second_path, second_manifest = self._packet(
                store, {"00_READ_ME_FIRST.md": b"v2\n"}, parent_packet_id=first_manifest["packet_id"]
            )
            self.assertNotEqual(first_path, second_path)
            self.assertNotEqual(first_manifest["packet_id"], second_manifest["packet_id"])
            self.assertEqual(first_manifest["packet_id"], second_manifest["parent_packet_id"])
            self.assertEqual(b"v1\n", (first_path / "00_READ_ME_FIRST.md").read_bytes())

    def test_unsafe_filenames_are_refused(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            for name in ("../escape.txt", "/absolute.txt"):
                with self.assertRaises(GenerationRefusal):
                    self._packet(store, {name: b"x"})

    def test_placeholder_preflight_statuses(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            clean, _ = self._packet(store, {"00_READ_ME_FIRST.md": b"clean\n"}, packet_type="archive")
            self.assertEqual("ready", preflight_packet(clean))
            todo, _ = self._packet(store, {"00_READ_ME_FIRST.md": b"fill TODO here\n"}, packet_type="archive")
            self.assertEqual("revision_required", preflight_packet(todo))
            blocked, _ = self._packet(
                store, {"00_READ_ME_FIRST.md": b"UNKNOWN_REQUIRED\n"}, packet_type="archive"
            )
            self.assertEqual("blocked", preflight_packet(blocked))

    def test_missing_file_and_warnings_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            path, manifest = self._packet(
                store, {"00_READ_ME_FIRST.md": b"clean\n", "01_SUMMARY.md": b"ok\n"},
                warnings=["one disclosed limitation"],
            )
            self.assertEqual("ready_with_disclosed_limitations", preflight_packet(path))
            (path / "01_SUMMARY.md").unlink()
            self.assertEqual("blocked", preflight_packet(path))
            self.assertEqual(["01_SUMMARY.md: missing"], verify_packet(path)["mismatches"])

    def test_verify_detects_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            path, _ = self._packet(store, {"00_READ_ME_FIRST.md": b"original\n"})
            target = path / "00_READ_ME_FIRST.md"
            target.write_text("tampered\n", encoding="utf-8")
            result = verify_packet(path)
            self.assertEqual("fail", result["status"])
            self.assertTrue(any("sha256 mismatch" in m for m in result["mismatches"]))

    def test_placeholders_ignores_manifest_and_checksums(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            store = Path(temporary)
            path, _ = self._packet(store, {"00_READ_ME_FIRST.md": b"TBD\n"}, packet_type="production")
            self.assertEqual(["TBD"], packet_placeholders(path))


if __name__ == "__main__":
    unittest.main()
