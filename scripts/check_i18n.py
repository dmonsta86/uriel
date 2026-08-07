#!/usr/bin/env python3
"""Validate Uriel's Core-8 documentation and locale catalogs."""

from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path
from string import Formatter
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "globalization" / "locale_registry.json"
SOURCE_CATALOG = ROOT / "globalization" / "catalog_source.en.json"

FORBIDDEN_BIDI = {
    "\u202a", "\u202b", "\u202c", "\u202d", "\u202e",
    "\u2066", "\u2067", "\u2068", "\u2069",
}

def load_json_strict(path: Path) -> Any:
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError(f"duplicate JSON key {key!r}: {path}")
            out[key] = value
        return out
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=pairs)

def placeholders(text: str) -> set[str]:
    return {
        name
        for _, name, _, _ in Formatter().parse(text)
        if name
    }

def fenced_blocks(text: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(r"```(?:[^\n]*)\n(.*?)```", text, re.DOTALL)
    ]

def main() -> int:
    errors: list[str] = []
    registry = load_json_strict(REGISTRY)
    source = load_json_strict(SOURCE_CATALOG)["messages"]
    english_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    english_blocks = fenced_blocks(english_readme)

    for item in registry["core_locales"]:
        locale = item["locale"]
        readme = ROOT / item["readme"]
        if not readme.is_file():
            errors.append(f"{locale}: missing README {item['readme']}")
            continue
        text = readme.read_text(encoding="utf-8")
        if unicodedata.normalize("NFC", text) != text:
            errors.append(f"{locale}: README is not NFC-normalized")
        if any(char in text for char in FORBIDDEN_BIDI):
            errors.append(f"{locale}: hidden bidi controls present")
        if locale != "en" and fenced_blocks(text) != english_blocks:
            errors.append(f"{locale}: code blocks differ from English")
        for link in re.findall(r"\]\((?!https?://|mailto:|#)([^)]+)\)", text):
            target = (ROOT / link.split("#", 1)[0]).resolve()
            try:
                target.relative_to(ROOT.resolve())
            except ValueError:
                errors.append(f"{locale}: link escapes repository: {link}")
                continue
            if link.split("#", 1)[0] and not target.exists():
                errors.append(f"{locale}: missing relative link: {link}")

        catalog = ROOT / "src" / "uriel" / "locales" / f"{locale}.json"
        if not catalog.is_file():
            errors.append(f"{locale}: missing installed locale catalog")
            continue
        loaded = load_json_strict(catalog)
        messages = loaded.get("messages", {})
        if set(messages) != set(source):
            missing = sorted(set(source) - set(messages))
            extra = sorted(set(messages) - set(source))
            errors.append(f"{locale}: key mismatch missing={missing} extra={extra}")
        for key, english in source.items():
            translated = messages.get(key)
            if translated is None:
                continue
            if placeholders(english) != placeholders(str(translated)):
                errors.append(f"{locale}:{key}: placeholder mismatch")
            if unicodedata.normalize("NFC", str(translated)) != str(translated):
                errors.append(f"{locale}:{key}: message is not NFC-normalized")

    if errors:
        print("I18N CHECK: FAIL")
        for error in errors:
            print(f"- {error}")
        return 1
    print("I18N CHECK: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
