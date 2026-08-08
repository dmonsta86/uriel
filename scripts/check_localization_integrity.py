#!/usr/bin/env python3
"""Validate separate, complete, honestly imaged Core-8 READMEs."""

from __future__ import annotations

import hashlib
import json
import re
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

def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

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

    for item in locale_map["locales"]:
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

        image_path = ROOT / item["image_path"]
        if not image_path.is_file():
            errors.append(f"{locale}: missing image {item['image_path']}")
            continue
        image_hash = sha256(image_path)

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
