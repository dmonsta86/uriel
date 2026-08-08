#!/usr/bin/env python3
"""Validate separate, complete, honestly imaged Core-8 READMEs."""

from __future__ import annotations

import hashlib
import json
import re
import struct
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAP = ROOT / "docs" / "i18n" / "locale_map.json"
MANIFESTS = ROOT / "docs" / "i18n" / "manifests"

REQUIRED_SECTIONS = {
    "mission", "status", "difference", "intellectual-honesty", "quick-start",
    "data-readiness", "gates", "blessing", "ai", "privacy", "trials",
    "community", "limitations",
}

FORBIDDEN_BIDI = {
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2066", "\u2067", "\u2068", "\u2069",
}

COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("not a PNG")
    return struct.unpack(">II", header[16:24])

def hero_source(text: str) -> str | None:
    match = re.search(r'<img\s+[^>]*src="([^"]+)"', text, re.IGNORECASE)
    return match.group(1) if match else None

def load_strict(path: Path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key {key!r} in {path}")
            result[key] = value
        return result
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)

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
        s = raw_line.strip()
        if not s or s.startswith("<!--") or s == "---" or s.startswith("<p") or s.startswith("</p") or s.startswith("<img") or s.startswith("<a") or s.startswith("</a") or s.startswith("<div") or s.startswith("</div>"):
            continue
        lines.append(s)
    return lines

def main() -> int:
    errors: list[str] = []
    locale_map = load_strict(MAP)
    english_path = ROOT / "README.md"
    english_text = english_path.read_text(encoding="utf-8")
    english_hash = sha256(english_path)
    english_blocks = code_blocks(english_text)
    english_lines = set(non_code_lines(english_text))
    english_image = ROOT / "docs/assets/the-forge-of-uriel/hero.png"
    english_image_hash = sha256(english_image)
    localized_hashes: dict[str, str] = {}

    locales = locale_map.get("locales", [])
    locale_ids = [item.get("locale") for item in locales]
    if len(locale_ids) != len(set(locale_ids)):
        errors.append("locale map contains duplicate locale identifiers")

    for item in locales:
        locale = item["locale"]
        readme_path = ROOT / item["readme"]
        manifest_path = MANIFESTS / f"{locale}.json"

        if not readme_path.is_file():
            errors.append(f"{locale}: missing {item['readme']}")
            continue
        if not manifest_path.is_file():
            errors.append(f"{locale}: missing manifest")
            continue

        text = readme_path.read_text(encoding="utf-8")
        manifest = load_strict(manifest_path)

        expected_manifest_fields = {
            "schema": "uriel.translation_manifest.v1",
            "locale": locale,
            "readme_path": item["readme"],
            "image_status": item["image_status"],
            "image_path": item["image_path"],
        }
        for field, expected in expected_manifest_fields.items():
            if manifest.get(field) != expected:
                errors.append(
                    f"{locale}: manifest {field}={manifest.get(field)!r}, expected {expected!r}"
                )
        if not COMMIT_RE.fullmatch(str(manifest.get("source_commit", ""))):
            errors.append(f"{locale}: manifest source_commit is not a full Git object ID")

        if unicodedata.normalize("NFC", text) != text:
            errors.append(f"{locale}: README is not NFC normalized")
        if any(ch in text for ch in FORBIDDEN_BIDI):
            errors.append(f"{locale}: hidden bidi controls present")
        missing_sections = REQUIRED_SECTIONS - section_ids(text)
        if missing_sections:
            errors.append(f"{locale}: missing sections {sorted(missing_sections)}")
        if code_blocks(text) != english_blocks:
            errors.append(f"{locale}: code blocks differ from English")
        if manifest.get("source_readme_sha256") != english_hash:
            errors.append(f"{locale}: stale English source hash")
        if manifest.get("readme_sha256") != sha256(readme_path):
            errors.append(f"{locale}: README hash mismatch")
        bound_hero = hero_source(text)
        if bound_hero != item["image_path"]:
            errors.append(
                f"{locale}: README hero source {bound_hero!r} does not match locale map "
                f"{item['image_path']!r}"
            )

        image_path = ROOT / item["image_path"]
        if not image_path.is_file():
            errors.append(f"{locale}: missing image {item['image_path']}")
            continue
        image_hash = sha256(image_path)
        if manifest.get("image_sha256") != image_hash:
            errors.append(f"{locale}: image hash mismatch")
        try:
            width, height = png_dimensions(image_path)
            if abs((width / height) - (16 / 9)) > 0.01:
                errors.append(f"{locale}: hero is not 16:9 ({width}x{height})")
        except (OSError, ValueError) as exc:
            errors.append(f"{locale}: invalid PNG hero: {exc}")

        if item["image_status"] == "ENGLISH_FALLBACK":
            if item["image_path"] != "docs/assets/the-forge-of-uriel/hero.png":
                errors.append(f"{locale}: fallback must use the English path directly")
            if image_hash != english_image_hash:
                errors.append(f"{locale}: fallback hash differs from English unexpectedly")
            if "ENGLISH_FALLBACK" not in text:
                errors.append(f"{locale}: README does not disclose English visual fallback")
        elif item["image_status"] == "LOCALIZED" and locale != "en":
            if image_hash == english_image_hash:
                errors.append(f"{locale}: localized asset is only a copied English image")
            if f"docs/assets/i18n/{locale}/" not in item["image_path"]:
                errors.append(f"{locale}: localized image path is not locale-specific")
            if "LOCALIZED" not in text:
                errors.append(f"{locale}: README does not disclose localized artwork")
            if "ENGLISH_FALLBACK" in text:
                errors.append(f"{locale}: README still claims an English visual fallback")
            duplicate = localized_hashes.get(image_hash)
            if duplicate:
                errors.append(f"{locale}: localized hero duplicates {duplicate}")
            localized_hashes[image_hash] = locale

            provenance = {
                "image_art_path": f"docs/assets/i18n/{locale}/uriel-forge-hero-art.png",
                "image_copy_path": f"globalization/image_copy/{locale}.json",
                "image_renderer_path": "scripts/render_localized_heroes.py",
            }
            for field, expected in provenance.items():
                if manifest.get(field) != expected:
                    errors.append(
                        f"{locale}: manifest {field}={manifest.get(field)!r}, expected {expected!r}"
                    )

            art_path = ROOT / provenance["image_art_path"]
            copy_path = ROOT / provenance["image_copy_path"]
            renderer_path = ROOT / provenance["image_renderer_path"]
            if not art_path.is_file():
                errors.append(f"{locale}: missing approved art layer")
            else:
                art_hash = sha256(art_path)
                if manifest.get("image_art_sha256") != art_hash:
                    errors.append(f"{locale}: art-layer hash mismatch")
                if art_hash == image_hash:
                    errors.append(f"{locale}: final hero has no deterministic text overlay")
                try:
                    if png_dimensions(art_path) != png_dimensions(image_path):
                        errors.append(f"{locale}: art and final hero dimensions differ")
                except (OSError, ValueError) as exc:
                    errors.append(f"{locale}: invalid art-layer PNG: {exc}")
            if not copy_path.is_file():
                errors.append(f"{locale}: missing deterministic image copy")
            else:
                copy_hash = sha256(copy_path)
                if manifest.get("image_copy_sha256") != copy_hash:
                    errors.append(f"{locale}: image-copy hash mismatch")
                image_copy = load_strict(copy_path)
                if image_copy.get("locale") != locale:
                    errors.append(f"{locale}: image copy declares the wrong locale")
                if image_copy.get("translation_status") != manifest.get("translation_status"):
                    errors.append(f"{locale}: README and image-copy review statuses differ")
            if not renderer_path.is_file():
                errors.append(f"{locale}: missing deterministic image renderer")
            elif manifest.get("image_renderer_sha256") != sha256(renderer_path):
                errors.append(f"{locale}: image-renderer hash mismatch")
        elif item["image_status"] not in {"ENGLISH_FALLBACK", "LOCALIZED"}:
            errors.append(f"{locale}: unknown image status {item['image_status']!r}")

        if locale != "en":
            localized_lines = non_code_lines(text)
            identical = sum(line in english_lines for line in localized_lines)
            if localized_lines and identical / len(localized_lines) > 0.35:
                errors.append(
                    f"{locale}: too much narrative text remains byte-identical to English "
                    f"({identical}/{len(localized_lines)})"
                )

        status = manifest.get("translation_status")
        reviewers = manifest.get("reviewers") or []
        if status in {"NATIVE_REVIEWED", "VERIFIED"} and not reviewers:
            errors.append(f"{locale}: claims {status} without reviewer evidence")

    if errors:
        print("LOCALIZATION INTEGRITY: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1

    print("LOCALIZATION INTEGRITY: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
