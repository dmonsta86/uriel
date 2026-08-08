#!/usr/bin/env python3
"""Refresh Core-8 localization manifests from the tracked files they bind."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCALE_MAP = ROOT / "docs" / "i18n" / "locale_map.json"
MANIFEST_ROOT = ROOT / "docs" / "i18n" / "manifests"
ENGLISH_README = ROOT / "README.md"
RENDERER = ROOT / "scripts" / "render_localized_heroes.py"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_json(path: Path) -> dict:
    def reject_duplicates(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key {key!r} in {path}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--source-commit",
        default=git_head(),
        help="Committed source baseline (default: current HEAD). File hashes remain authoritative.",
    )
    parser.add_argument(
        "--verified-at",
        default=datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        help="UTC verification timestamp.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not COMMIT_RE.fullmatch(args.source_commit):
        raise ValueError("--source-commit must be a 40-character lowercase Git object ID")

    locale_map = load_json(LOCALE_MAP)
    source_hash = sha256(ENGLISH_README)
    renderer_rel = RENDERER.relative_to(ROOT).as_posix()
    renderer_hash = sha256(RENDERER)

    for item in locale_map["locales"]:
        locale = item["locale"]
        manifest_path = MANIFEST_ROOT / f"{locale}.json"
        previous = load_json(manifest_path)
        status = previous["translation_status"]
        reviewers = previous.get("reviewers", [])
        if status in {"NATIVE_REVIEWED", "VERIFIED"} and not reviewers:
            raise ValueError(f"{locale}: {status} requires at least one named reviewer")

        readme = ROOT / item["readme"]
        image = ROOT / item["image_path"]
        manifest = {
            "source_commit": args.source_commit,
            "source_readme_sha256": source_hash,
            "locale": locale,
            "translation_status": status,
            "reviewers": reviewers,
            "readme_path": item["readme"],
            "readme_sha256": sha256(readme),
            "image_status": item["image_status"],
            "image_path": item["image_path"],
            "image_sha256": sha256(image),
        }

        if locale != locale_map["canonical_locale"] and item["image_status"] == "LOCALIZED":
            art_rel = f"docs/assets/i18n/{locale}/uriel-forge-hero-art.png"
            copy_rel = f"globalization/image_copy/{locale}.json"
            art = ROOT / art_rel
            copy = ROOT / copy_rel
            manifest.update(
                {
                    "image_art_path": art_rel,
                    "image_art_sha256": sha256(art),
                    "image_copy_path": copy_rel,
                    "image_copy_sha256": sha256(copy),
                    "image_renderer_path": renderer_rel,
                    "image_renderer_sha256": renderer_hash,
                }
            )

        manifest["verified_at_utc"] = args.verified_at
        manifest["schema"] = "uriel.translation_manifest.v1"
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
            newline="\n",
        )
        print(f"Updated {manifest_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
