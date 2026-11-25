#!/usr/bin/env python3
"""Validate complete, distinct, provenance-bound Core-8 READMEs and visuals."""

from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import struct
import sys
import unicodedata
import zlib
from pathlib import Path, PurePosixPath
from typing import Iterable, Mapping


ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "docs" / "i18n" / "locale_map.json"
MANIFESTS = ROOT / "docs" / "i18n" / "manifests"
VISUAL_MANIFESTS = ROOT / "docs" / "i18n" / "visual_manifests"
VISUAL_SOURCES = ROOT / "globalization" / "visual_sources.json"

CORE_LOCALES = ("en", "es", "fr", "pt-BR", "zh-Hans", "ar", "hi", "ja")
EXPECTED_ARCHIVE_SHA256 = "bf9985e5c96cafdcfef9aa1249fe838a4aceca076fb7a1f4e479301bb460f357"
EXPECTED_GOLD_SHA256 = "0012a2e35149cb6efcfb6e1f503c8cd750d03af27eae417e2fa849bb64ad038e"
MAX_JSON_BYTES = 1024 * 1024
MAX_PNG_BYTES = 32 * 1024 * 1024
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
PRIVATE_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/](?:Users|Documents)[\\/]|[\\/]Users[\\/])", re.I)

REQUIRED_SECTIONS = {
    "mission", "status", "difference", "intellectual-honesty", "quick-start",
    "data-readiness", "gates", "blessing", "ai", "privacy", "trials",
    "community", "limitations",
}

FORBIDDEN_BIDI = {
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2066", "\u2067", "\u2068", "\u2069",
}

COPY_FIELDS = {
    "schema", "locale", "language", "direction", "official_brand",
    "localized_title", "subtitle", "challenge", "supporting_line",
    "left_rail", "right_rail", "center_microline", "footer",
    "translation_status",
}

SCORE_LIMITS = {
    "composition_parity": (13, 15),
    "character_expression": (14, 15),
    "research_story": (18, 20),
    "detail_density": (9, 10),
    "lighting_materials": (8, 10),
    "cultural_subtlety": (9, 10),
    "text_safe_composition": (4, 5),
    "accessibility_contrast": (4, 5),
    "brand_continuity": (5, 5),
    "negative_constraints": (5, 5),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def is_reparse_or_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        info = path.stat()
    except FileNotFoundError:
        return False
    reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(getattr(info, "st_file_attributes", 0) & reparse_flag)


def repo_file(value: object, *, must_exist: bool = True) -> Path:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or "//" in value
        or value.endswith("/")
        or ":" in value
    ):
        raise ValueError(f"invalid repository-relative path: {value!r}")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"unsafe repository-relative path: {value!r}")
    candidate = ROOT.joinpath(*pure.parts)
    root_resolved = ROOT.resolve(strict=True)
    current = ROOT
    for part in pure.parts:
        current = current / part
        if current.exists() and is_reparse_or_link(current):
            raise ValueError(f"repository path traverses a link or reparse point: {value}")
    resolved = candidate.resolve(strict=must_exist)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"repository path escaped the project: {value!r}") from exc
    if must_exist and not resolved.is_file():
        raise ValueError(f"repository path is not a file: {value!r}")
    return resolved


def load_strict(path: Path):
    raw = path.read_bytes()
    if len(raw) > MAX_JSON_BYTES:
        raise ValueError(f"JSON exceeds {MAX_JSON_BYTES} bytes: {path}")

    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key {key!r} in {path}")
            result[key] = value
        return result

    def reject_constant(value: str):
        raise ValueError(f"non-finite JSON constant {value!r} in {path}")

    return json.loads(
        raw.decode("utf-8"),
        object_pairs_hook=pairs,
        parse_constant=reject_constant,
    )


def walk_strings(value) -> Iterable[str]:
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield str(key)
            yield from walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)


def validate_public_json(label: str, value, errors: list[str]) -> None:
    for text in walk_strings(value):
        if unicodedata.normalize("NFC", text) != text:
            errors.append(f"{label}: JSON string is not NFC normalized")
            break
        if any(ch in text for ch in FORBIDDEN_BIDI):
            errors.append(f"{label}: hidden bidi control present in JSON")
            break
        if PRIVATE_PATH_RE.search(text):
            errors.append(f"{label}: private absolute path leaked into public JSON")
            break


def package_member_safe(value: object) -> bool:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or "//" in value
        or value.endswith("/")
        or ":" in value
    ):
        return False
    pure = PurePosixPath(value)
    return not pure.is_absolute() and all(part not in {"", ".", ".."} for part in pure.parts)


def png_info(path: Path) -> tuple[int, int, tuple[str, ...]]:
    raw = path.read_bytes()
    if len(raw) > MAX_PNG_BYTES:
        raise ValueError(f"PNG exceeds {MAX_PNG_BYTES} bytes")
    if raw[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    position = 8
    chunks = []
    dimensions = None
    seen_iend = False
    while position < len(raw):
        if position + 12 > len(raw):
            raise ValueError("truncated PNG chunk header")
        length = struct.unpack(">I", raw[position:position + 4])[0]
        chunk_type = raw[position + 4:position + 8]
        end = position + 12 + length
        if end > len(raw):
            raise ValueError("truncated PNG chunk payload")
        payload = raw[position + 8:position + 8 + length]
        expected_crc = struct.unpack(">I", raw[position + 8 + length:end])[0]
        actual_crc = zlib.crc32(chunk_type + payload) & 0xFFFFFFFF
        if actual_crc != expected_crc:
            raise ValueError("PNG chunk CRC mismatch")
        try:
            name = chunk_type.decode("ascii")
        except UnicodeDecodeError as exc:
            raise ValueError("non-ASCII PNG chunk type") from exc
        chunks.append(name)
        if name == "IHDR":
            if dimensions is not None or length != 13:
                raise ValueError("invalid or duplicate IHDR")
            dimensions = struct.unpack(">II", payload[:8])
        if name == "IEND":
            if length != 0:
                raise ValueError("invalid IEND")
            seen_iend = True
            position = end
            break
        position = end
    if not seen_iend or position != len(raw) or dimensions is None:
        raise ValueError("missing IEND, trailing bytes, or missing IHDR")
    if any(name in {"tEXt", "zTXt", "iTXt", "eXIf"} for name in chunks):
        raise ValueError("publication PNG contains text or EXIF metadata")
    return dimensions[0], dimensions[1], tuple(chunks)


def hero_attributes(text: str) -> tuple[str | None, str | None]:
    match = re.search(r"<img\b(?P<attrs>[^>]*)>", text, re.IGNORECASE | re.DOTALL)
    if not match:
        return None, None
    attrs = match.group("attrs")
    source = re.search(r'\bsrc="([^"]+)"', attrs, re.IGNORECASE)
    alt = re.search(r'\balt="([^"]*)"', attrs, re.IGNORECASE)
    return (source.group(1) if source else None, alt.group(1) if alt else None)


def code_blocks(text: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r"```(?:[^\n]*)\n(.*?)```", text, re.DOTALL)
    ]


def section_ids(text: str) -> set[str]:
    return set(re.findall(r"<!--\s*URIEL:SECTION:([a-z0-9-]+):START\s*-->", text))


def non_code_lines(text: str) -> list[str]:
    text = re.sub(r"```(?:[^\n]*)\n.*?```", "", text, flags=re.DOTALL)
    lines = []
    for raw_line in text.splitlines():
        value = raw_line.strip()
        if (
            not value
            or value.startswith("<!--")
            or value == "---"
            or value.startswith(("<p", "</p", "<img", "<a", "</a", "<div", "</div>"))
        ):
            continue
        lines.append(value)
    return lines


def validate_score(
    locale: str,
    score: object,
    reference_score: int,
    errors: list[str],
    *,
    hard_minima: bool,
) -> None:
    if not isinstance(score, dict) or set(score) != set(SCORE_LIMITS) | {"overall"}:
        errors.append(f"{locale}: visual score fields differ from the locked rubric")
        return
    subtotal = 0
    for field, (minimum, maximum) in SCORE_LIMITS.items():
        value = score.get(field)
        floor = minimum if hard_minima else 0
        if not isinstance(value, int) or isinstance(value, bool) or not floor <= value <= maximum:
            errors.append(f"{locale}: visual score {field} is outside {floor}..{maximum}")
            return
        subtotal += value
    if score.get("overall") != subtotal:
        errors.append(f"{locale}: visual overall score does not equal the rubric subtotal")
    if hard_minima and subtotal < 90:
        errors.append(f"{locale}: visual overall score is below 90")
    if hard_minima and abs(subtotal - reference_score) > 3:
        errors.append(f"{locale}: visual score is more than three points from English")


def main() -> int:
    errors = []
    try:
        locale_map = load_strict(MAP)
        english = ROOT / "README.md"
        if tuple(item["locale"] for item in locale_map["locales"]) != CORE_LOCALES:
            errors.append("Core locale list changed")
        for item in locale_map["locales"]:
            locale = item["locale"]
            readme = repo_file(item["readme"])
            manifest = load_strict(MANIFESTS / (locale + ".json"))
            expected = {"schema": "uriel.readme_pointer.v1", "locale": locale,
                        "readme_path": item["readme"], "readme_sha256": sha256(readme),
                        "canonical_sha256": sha256(english),
                        "status": "canonical" if locale == "en" else "pointer"}
            if manifest != expected:
                errors.append(locale + ": README pointer manifest drift")
            content = readme.read_text(encoding="utf-8")
            if locale != "en" and ("(README.md)" not in content or "```" in content or "![" in content):
                errors.append(locale + ": stale translated instructions or image")
        if any((ROOT / "docs" / "assets").rglob("*.png")):
            errors.append("Retired hero artwork remains")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(str(exc))
    if errors:
        print("LOCALIZATION INTEGRITY: FAIL")
        for error in errors:
            print("- " + error)
        return 1
    print("LOCALIZATION INTEGRITY: PASS (canonical English and 7 hash-bound pointers)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
