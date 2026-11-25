#!/usr/bin/env python3
"""Bind the canonical README and localized pointers to their current bytes."""
import hashlib
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    data = json.loads((ROOT / "docs/i18n/locale_map.json").read_text(encoding="utf-8"))
    canonical = digest(ROOT / "README.md")
    for row in data["locales"]:
        locale = row["locale"]
        path = ROOT / row["readme"]
        value = {"schema": "uriel.readme_pointer.v1", "locale": locale,
                 "readme_path": row["readme"], "readme_sha256": digest(path),
                 "canonical_sha256": canonical, "status": "canonical" if locale == "en" else "pointer"}
        (ROOT / "docs/i18n/manifests" / (locale + ".json")).write_text(json.dumps(value, indent=2)+"\n", encoding="utf-8")
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
