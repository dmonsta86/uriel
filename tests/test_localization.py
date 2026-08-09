from __future__ import annotations

import json
import struct
import tempfile
import unittest
import zlib
from pathlib import Path

from scripts import check_localization_integrity as integrity
from scripts import render_localized_heroes as renderer


ROOT = Path(__file__).resolve().parents[1]


def png_chunk(name: bytes, payload: bytes) -> bytes:
    checksum = zlib.crc32(name + payload) & 0xFFFFFFFF
    return struct.pack(">I", len(payload)) + name + payload + struct.pack(">I", checksum)


def tiny_png(*, text_metadata: bool = False) -> bytes:
    value = b"\x89PNG\r\n\x1a\n"
    value += png_chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
    if text_metadata:
        value += png_chunk(b"tEXt", b"author\x00private")
    value += png_chunk(b"IDAT", zlib.compress(b"\x00\x00\x00\x00"))
    value += png_chunk(b"IEND", b"")
    return value


class LocalizationIntegrityTests(unittest.TestCase):
    def test_current_core8_contract_passes(self) -> None:
        self.assertEqual(integrity.main(), 0)

    def test_strict_json_rejects_duplicates_and_nonfinite_values(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            duplicate = Path(temp_name) / "duplicate.json"
            duplicate.write_text('{"a": 1, "a": 2}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate key"):
                integrity.load_strict(duplicate)

            nonfinite = Path(temp_name) / "nonfinite.json"
            nonfinite.write_text('{"a": NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-finite"):
                integrity.load_strict(nonfinite)

    def test_repository_paths_fail_closed(self) -> None:
        for unsafe in (
            "../README.md",
            "/README.md",
            "docs\\i18n\\locale_map.json",
            "C:/Users/private/file.json",
            "docs//i18n/locale_map.json",
            "docs/i18n/",
        ):
            with self.subTest(path=unsafe):
                with self.assertRaises(ValueError):
                    integrity.repo_file(unsafe, must_exist=False)

    def test_png_parser_rejects_metadata_corruption_and_trailing_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            clean = root / "clean.png"
            clean.write_bytes(tiny_png())
            self.assertEqual(integrity.png_info(clean)[:2], (1, 1))

            metadata = root / "metadata.png"
            metadata.write_bytes(tiny_png(text_metadata=True))
            with self.assertRaisesRegex(ValueError, "metadata"):
                integrity.png_info(metadata)

            corrupt = root / "corrupt.png"
            corrupt_bytes = bytearray(tiny_png())
            corrupt_bytes[-5] ^= 0x01
            corrupt.write_bytes(corrupt_bytes)
            with self.assertRaisesRegex(ValueError, "CRC"):
                integrity.png_info(corrupt)

            trailing = root / "trailing.png"
            trailing.write_bytes(tiny_png() + b"private-tail")
            with self.assertRaisesRegex(ValueError, "trailing"):
                integrity.png_info(trailing)

    def test_visual_score_mutations_fail_the_locked_gate(self) -> None:
        source = json.loads((ROOT / "globalization" / "visual_sources.json").read_text(encoding="utf-8"))
        reference = source["review"]["reference_score"]
        passing = source["locales"][1]["score"]
        errors: list[str] = []
        integrity.validate_score("es", passing, reference, errors, hard_minima=True)
        self.assertEqual(errors, [])

        mutated = dict(passing)
        mutated["research_story"] = 17
        mutated["overall"] -= 2
        integrity.validate_score("es", mutated, reference, errors, hard_minima=True)
        self.assertTrue(any("research_story" in error for error in errors))

    def test_every_localized_manifest_preserves_review_boundary(self) -> None:
        for locale in integrity.CORE_LOCALES[1:]:
            with self.subTest(locale=locale):
                visual = integrity.load_strict(
                    ROOT / "docs" / "i18n" / "visual_manifests" / f"{locale}.json"
                )
                self.assertEqual(visual["image_status"], "LOCALIZED_AI_REVIEWED")
                self.assertEqual(
                    visual["visible_text_status"],
                    "AI_ASSISTED_REQUIRES_NATIVE_REVIEW",
                )
                self.assertEqual(visual["native_language_reviewers"], [])
                self.assertFalse(visual["deterministic_typography"])


class LocalizedRendererTests(unittest.TestCase):
    def test_source_assignment_parser_rejects_ambiguous_inputs(self) -> None:
        self.assertEqual(
            renderer.parse_source_args(["es=docs/source.png"], "--poster"),
            {"es": "docs/source.png"},
        )
        for values in (["missing-separator"], ["=empty.png"], ["es="], ["es=a", "es=b"]):
            with self.subTest(values=values):
                with self.assertRaises(ValueError):
                    renderer.parse_source_args(values, "--poster")

    def test_source_digests_are_lowercase_sha256(self) -> None:
        digest = "a" * 64
        self.assertEqual(renderer.parse_digest_args([f"es={digest}"]), {"es": digest})
        for value in ("f" * 63, "F" * 64, "z" * 64):
            with self.subTest(value=value):
                with self.assertRaisesRegex(ValueError, "lowercase SHA-256"):
                    renderer.parse_digest_args([f"es={value}"])

    def test_candidate_outside_repository_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temp_name:
            outside = Path(temp_name) / "candidate.png"
            outside.write_bytes(tiny_png())
            with self.assertRaisesRegex(ValueError, "outside the repository"):
                renderer.confined_candidate(str(outside))

    def test_copy_contract_and_generated_html_are_offline(self) -> None:
        locale_map = integrity.load_strict(ROOT / "docs" / "i18n" / "locale_map.json")
        directions = {row["locale"]: row["direction"] for row in locale_map["locales"]}
        for locale in integrity.CORE_LOCALES[1:]:
            with self.subTest(locale=locale):
                copy = integrity.load_strict(ROOT / "globalization" / "image_copy" / f"{locale}.json")
                renderer.validate_copy(locale, directions[locale], copy)
                page = renderer.build_overlay_html(locale, directions[locale], copy, tiny_png())
                self.assertNotIn("http://", page)
                self.assertNotIn("https://", page)
                self.assertIn("data:image/png;base64,", page)


if __name__ == "__main__":
    unittest.main()
