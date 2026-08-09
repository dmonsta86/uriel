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
    errors: list[str] = []
    try:
        locale_map = load_strict(MAP)
        source_registry = load_strict(VISUAL_SOURCES)
    except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
        print(f"LOCALIZATION INTEGRITY: FAIL\n- control file error: {exc}")
        return 1

    validate_public_json("locale map", locale_map, errors)
    validate_public_json("visual source registry", source_registry, errors)
    if locale_map.get("schema") != "uriel.locale_map.v2":
        errors.append("locale map has an unsupported schema")
    if source_registry.get("schema") != "uriel.visual_source_registry.v1":
        errors.append("visual source registry has an unsupported schema")

    locales = locale_map.get("locales")
    if not isinstance(locales, list):
        errors.append("locale map locales must be an array")
        locales = []
    locale_ids = [item.get("locale") for item in locales if isinstance(item, dict)]
    if tuple(locale_ids) != CORE_LOCALES:
        errors.append(f"locale map must contain ordered Core-8 locales {list(CORE_LOCALES)}")
    if locale_map.get("canonical_locale") != "en":
        errors.append("canonical locale must be en")

    archive = source_registry.get("source_archive", {})
    if archive.get("sha256") != EXPECTED_ARCHIVE_SHA256:
        errors.append("visual source archive hash differs from the reviewed package")
    if archive.get("manifest_verification") != "PASS":
        errors.append("visual source archive manifest is not recorded as passing")
    if archive.get("declared_payloads") != 72 or archive.get("undeclared_payloads") != 0:
        errors.append("visual source archive payload counts differ from the verified package")
    if not SHA256_RE.fullmatch(str(archive.get("package_manifest_sha256", ""))):
        errors.append("visual source package-manifest hash is invalid")

    review = source_registry.get("review", {})
    if review.get("method") != "INDEPENDENT_AI_VISUAL_REVIEW":
        errors.append("visual review method is missing or unsupported")
    if review.get("language_review_boundary") != "AI_ASSISTED_REQUIRES_NATIVE_REVIEW":
        errors.append("native-language review boundary is missing")
    if review.get("authority") != "NONE":
        errors.append("visual review must grant no authority")
    reference_score = review.get("reference_score")
    if not isinstance(reference_score, int):
        errors.append("English reference score is invalid")
        reference_score = -1

    reference = source_registry.get("english_reference", {})
    if reference.get("sha256") != EXPECTED_GOLD_SHA256:
        errors.append("English gold reference hash differs from the locked image")
    if not package_member_safe(reference.get("member")):
        errors.append("English gold source member path is unsafe")
    validate_score("English reference", reference.get("score"), reference_score, errors, hard_minima=False)
    if reference.get("score", {}).get("overall") != reference_score:
        errors.append("English reference score does not match the review record")

    source_rows = source_registry.get("locales")
    if not isinstance(source_rows, list):
        errors.append("visual source locales must be an array")
        source_rows = []
    source_by_locale = {}
    source_hashes = set()
    source_members = set()
    for row in source_rows:
        if not isinstance(row, dict):
            errors.append("visual source locale row is not an object")
            continue
        locale = row.get("locale")
        if locale in source_by_locale or locale not in CORE_LOCALES:
            errors.append(f"visual source has duplicate or unknown locale {locale!r}")
            continue
        source_by_locale[locale] = row
        member = row.get("member")
        source_hash = row.get("sha256")
        if not package_member_safe(member) or member in source_members:
            errors.append(f"{locale}: unsafe or duplicate source member")
        source_members.add(member)
        if not SHA256_RE.fullmatch(str(source_hash or "")) or source_hash in source_hashes:
            errors.append(f"{locale}: invalid or duplicate source hash")
        source_hashes.add(source_hash)
        dimensions = row.get("dimensions")
        if not (
            isinstance(dimensions, list)
            and len(dimensions) == 2
            and all(isinstance(value, int) and value > 0 for value in dimensions)
        ):
            errors.append(f"{locale}: invalid source dimensions")
        if not isinstance(row.get("alt_text"), str) or not row["alt_text"].strip():
            errors.append(f"{locale}: missing localized alt text")
        validate_score(str(locale), row.get("score"), reference_score, errors, hard_minima=True)
    if set(source_by_locale) != set(CORE_LOCALES):
        errors.append("visual source registry does not cover exactly Core-8")

    english_path = ROOT / "README.md"
    english_text = english_path.read_text(encoding="utf-8")
    english_hash = sha256(english_path)
    english_blocks = code_blocks(english_text)
    english_lines = set(non_code_lines(english_text))
    source_registry_hash = sha256(VISUAL_SOURCES)
    renderer_path = ROOT / "scripts" / "render_localized_heroes.py"
    renderer_hash = sha256(renderer_path)
    final_hashes = {}

    for item in locales:
        if not isinstance(item, dict) or item.get("locale") not in CORE_LOCALES:
            continue
        locale = item["locale"]
        try:
            readme_path = repo_file(item.get("readme"))
            image_path = repo_file(item.get("image_path"))
            manifest_path = MANIFESTS / f"{locale}.json"
            visual_manifest_path = VISUAL_MANIFESTS / f"{locale}.json"
            manifest = load_strict(manifest_path)
            visual = load_strict(visual_manifest_path)
        except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"{locale}: failed to load bound files: {exc}")
            continue

        validate_public_json(f"{locale} translation manifest", manifest, errors)
        validate_public_json(f"{locale} visual manifest", visual, errors)
        expected_status = "GOLD_REFERENCE" if locale == "en" else "LOCALIZED_AI_REVIEWED"
        expected_manifest = {
            "schema": "uriel.translation_manifest.v2",
            "locale": locale,
            "readme_path": item["readme"],
            "image_status": expected_status,
            "image_path": item["image_path"],
            "visual_manifest_path": f"docs/i18n/visual_manifests/{locale}.json",
            "visual_source_registry_path": "globalization/visual_sources.json",
        }
        for field, expected in expected_manifest.items():
            if manifest.get(field) != expected:
                errors.append(f"{locale}: translation manifest {field} differs from {expected!r}")
        if item.get("image_status") != expected_status:
            errors.append(f"{locale}: locale-map image status differs from {expected_status}")
        if not COMMIT_RE.fullmatch(str(manifest.get("source_commit", ""))):
            errors.append(f"{locale}: source_commit is not a full Git object ID")
        if manifest.get("source_readme_sha256") != english_hash:
            errors.append(f"{locale}: stale English README source hash")
        if manifest.get("readme_sha256") != sha256(readme_path):
            errors.append(f"{locale}: README hash mismatch")
        if manifest.get("image_sha256") != sha256(image_path):
            errors.append(f"{locale}: image hash mismatch")
        if manifest.get("visual_manifest_sha256") != sha256(visual_manifest_path):
            errors.append(f"{locale}: visual-manifest hash mismatch")
        if manifest.get("visual_source_registry_sha256") != source_registry_hash:
            errors.append(f"{locale}: visual-source registry hash mismatch")

        text = readme_path.read_text(encoding="utf-8")
        if unicodedata.normalize("NFC", text) != text:
            errors.append(f"{locale}: README is not NFC normalized")
        if any(ch in text for ch in FORBIDDEN_BIDI):
            errors.append(f"{locale}: hidden bidi controls present")
        missing_sections = REQUIRED_SECTIONS - section_ids(text)
        if missing_sections:
            errors.append(f"{locale}: missing sections {sorted(missing_sections)}")
        if code_blocks(text) != english_blocks:
            errors.append(f"{locale}: code blocks differ from English")
        hero_source, hero_alt = hero_attributes(text)
        if hero_source != item["image_path"]:
            errors.append(f"{locale}: README hero path differs from the locale map")

        source = reference if locale == "en" else source_by_locale.get(locale, {})
        if hero_alt != source.get("alt_text"):
            errors.append(f"{locale}: README hero alt text differs from the reviewed source record")

        image_hash = sha256(image_path)
        duplicate = final_hashes.get(image_hash)
        if duplicate:
            errors.append(f"{locale}: final hero duplicates {duplicate}")
        final_hashes[image_hash] = locale
        try:
            width, height, _chunks = png_info(image_path)
        except (OSError, ValueError) as exc:
            errors.append(f"{locale}: invalid publication PNG: {exc}")
            continue

        visual_expected = {
            "schema": "uriel.localized_asset.v2",
            "locale": locale,
            "image_status": expected_status,
            "image_path": item["image_path"],
            "image_sha256": image_hash,
            "image_dimensions": [width, height],
            "alt_text": source.get("alt_text"),
            "source_archive_name": archive.get("name"),
            "source_archive_sha256": EXPECTED_ARCHIVE_SHA256,
            "source_package_manifest_sha256": archive.get("package_manifest_sha256"),
            "source_member": source.get("member"),
            "source_sha256": source.get("sha256"),
            "source_dimensions": source.get("dimensions"),
            "visual_review_method": "INDEPENDENT_AI_VISUAL_REVIEW",
            "reference_score": reference_score,
            "score": source.get("score"),
            "visual_gate": "PASS",
            "authority": "NONE",
        }
        for field, expected in visual_expected.items():
            if visual.get(field) != expected:
                errors.append(f"{locale}: visual manifest {field} differs from the reviewed record")
        validate_score(locale, visual.get("score"), reference_score, errors, hard_minima=locale != "en")
        if visual.get("native_language_reviewers") != []:
            errors.append(f"{locale}: native reviewers are claimed without the current review boundary")

        if locale == "en":
            if image_hash != EXPECTED_GOLD_SHA256 or [width, height] != reference.get("dimensions"):
                errors.append("en: published gold reference bytes or dimensions changed")
            if visual.get("role") != "GOLD_REFERENCE":
                errors.append("en: visual role is not GOLD_REFERENCE")
            if visual.get("source_kind") != "LOCKED_ENGLISH_REFERENCE":
                errors.append("en: visual source kind is not locked reference")
            if visual.get("publication_mode") != "LOCKED_REFERENCE_BYTES":
                errors.append("en: publication mode changed")
            if visual.get("visible_text_status") != "REFERENCE_COPY":
                errors.append("en: visible-text status changed")
        else:
            if (width, height) != (3840, 2160):
                errors.append(f"{locale}: publication image is not exactly 3840x2160")
            if expected_status not in text or "AI_ASSISTED_REQUIRES_NATIVE_REVIEW" not in text:
                errors.append(f"{locale}: README omits the honest visual review boundary")
            if visual.get("role") != "LOCALIZED_EXPLAINER_POSTER":
                errors.append(f"{locale}: visual role is not localized explainer")
            if visual.get("source_kind") != "GENERATED_FULL_POSTER":
                errors.append(f"{locale}: visual source kind is not generated full poster")
            if visual.get("publication_mode") != "DETERMINISTIC_3840X2160_NORMALIZATION":
                errors.append(f"{locale}: publication mode changed")
            if visual.get("deterministic_typography") is not False:
                errors.append(f"{locale}: generated poster must not claim deterministic typography")
            if visual.get("visible_text_status") != "AI_ASSISTED_REQUIRES_NATIVE_REVIEW":
                errors.append(f"{locale}: generated text review boundary changed")

            expected_paths = {
                "image_prompt_path": f"globalization/image_prompts/{locale}.md",
                "image_copy_path": f"globalization/image_copy/{locale}.json",
                "image_renderer_path": "scripts/render_localized_heroes.py",
            }
            for field, expected in expected_paths.items():
                if visual.get(field) != expected:
                    errors.append(f"{locale}: visual manifest {field} differs from {expected}")
            try:
                prompt_path = repo_file(expected_paths["image_prompt_path"])
                copy_path = repo_file(expected_paths["image_copy_path"])
                image_copy = load_strict(copy_path)
            except (OSError, UnicodeError, ValueError, json.JSONDecodeError) as exc:
                errors.append(f"{locale}: prompt or copy failed validation: {exc}")
                continue
            if visual.get("image_prompt_sha256") != sha256(prompt_path):
                errors.append(f"{locale}: image-prompt hash mismatch")
            if visual.get("image_copy_sha256") != sha256(copy_path):
                errors.append(f"{locale}: image-copy hash mismatch")
            if visual.get("image_renderer_sha256") != renderer_hash:
                errors.append(f"{locale}: image-renderer hash mismatch")
            if visual.get("image_prompt_role") != "ART_ONLY_REGENERATION_INPUT_NOT_EXACT_SOURCE_PROMPT":
                errors.append(f"{locale}: image-prompt provenance role changed")

            prompt = prompt_path.read_text(encoding="utf-8")
            prompt_lower = prompt.lower()
            if not 2000 <= len(prompt.encode("utf-8")) <= 16 * 1024:
                errors.append(f"{locale}: art-only prompt has an unexpected size")
            if (
                "do not render:" not in prompt_lower
                or "- words;" not in prompt_lower
                or "no wings" not in prompt_lower
                or "3840" not in prompt
            ):
                errors.append(f"{locale}: art-only prompt lost core production constraints")
            validate_public_json(f"{locale} image copy", image_copy, errors)
            if set(image_copy) != COPY_FIELDS:
                errors.append(f"{locale}: image-copy fields differ from visual_copy.v2")
            if image_copy.get("schema") != "forge_of_uriel.visual_copy.v2":
                errors.append(f"{locale}: image-copy schema changed")
            if image_copy.get("locale") != locale or image_copy.get("direction") != item.get("direction"):
                errors.append(f"{locale}: image-copy locale or direction mismatch")
            if image_copy.get("translation_status") != "AI_ASSISTED_REQUIRES_NATIVE_REVIEW":
                errors.append(f"{locale}: image-copy native-review boundary changed")
            for field, count in (("left_rail", 4), ("right_rail", 5), ("footer", 4)):
                values = image_copy.get(field)
                if not isinstance(values, list) or len(values) != count or not all(
                    isinstance(value, str) and value.strip() for value in values
                ):
                    errors.append(f"{locale}: image-copy {field} must contain {count} non-empty strings")

        if locale != "en":
            localized_lines = non_code_lines(text)
            identical = sum(line in english_lines for line in localized_lines)
            if localized_lines and identical / len(localized_lines) > 0.35:
                errors.append(
                    f"{locale}: too much narrative remains byte-identical to English "
                    f"({identical}/{len(localized_lines)})"
                )
        status = manifest.get("translation_status")
        reviewers = manifest.get("reviewers") or []
        if status in {"NATIVE_REVIEWED", "VERIFIED"} and not reviewers:
            errors.append(f"{locale}: claims {status} without reviewer evidence")

    asset_root = ROOT / "docs" / "assets" / "i18n"
    stale = [
        path.relative_to(ROOT).as_posix()
        for path in asset_root.rglob("*")
        if path.is_file() and ("candidate" in path.name.lower() or path.name == "uriel-forge-hero-art.png")
    ]
    staging = [
        path.relative_to(ROOT).as_posix()
        for path in asset_root.rglob("*")
        if path.is_dir() and "staging" in path.name.lower()
    ]
    if stale or staging:
        errors.append(f"stale localized visual artifacts remain: {sorted(stale + staging)}")

    if len(final_hashes) != len(CORE_LOCALES):
        errors.append("not every Core-8 publication image reached the distinct-hash ledger")

    if errors:
        print("LOCALIZATION INTEGRITY: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print(
        "LOCALIZATION INTEGRITY: PASS "
        f"({len(CORE_LOCALES)} READMEs, {len(final_hashes)} distinct heroes, "
        "7 localized posters at 3840x2160)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
