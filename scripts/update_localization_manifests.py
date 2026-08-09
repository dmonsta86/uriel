#!/usr/bin/env python3
"""Refresh Core-8 translation and visual-provenance manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Mapping


ROOT = Path(__file__).resolve().parents[1]
LOCALE_MAP = ROOT / "docs" / "i18n" / "locale_map.json"
MANIFEST_ROOT = ROOT / "docs" / "i18n" / "manifests"
VISUAL_MANIFEST_ROOT = ROOT / "docs" / "i18n" / "visual_manifests"
VISUAL_SOURCES = ROOT / "globalization" / "visual_sources.json"
ENGLISH_README = ROOT / "README.md"
RENDERER = ROOT / "scripts" / "render_localized_heroes.py"
PROMPT_ROOT = ROOT / "globalization" / "image_prompts"
COPY_ROOT = ROOT / "globalization" / "image_copy"
COMMIT_RE = re.compile(r"^[0-9a-f]{40}$")

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


def png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG: {path}")
    return struct.unpack(">II", header[16:24])


def load_json(path: Path) -> dict:
    def reject_duplicates(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key {key!r} in {path}")
            result[key] = value
        return result

    def reject_constant(value: str):
        raise ValueError(f"non-finite JSON constant {value!r} in {path}")

    return json.loads(
        path.read_text(encoding="utf-8"),
        object_pairs_hook=reject_duplicates,
        parse_constant=reject_constant,
    )


def write_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def git_head() -> str:
    return subprocess.check_output(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        text=True,
        encoding="utf-8",
    ).strip()


def validate_score(locale: str, score: Mapping[str, object], reference: int) -> None:
    expected = set(SCORE_LIMITS) | {"overall"}
    if set(score) != expected:
        raise ValueError(f"{locale}: score fields differ from the locked rubric")
    subtotal = 0
    for field, (minimum, maximum) in SCORE_LIMITS.items():
        value = score[field]
        if not isinstance(value, int) or isinstance(value, bool):
            raise ValueError(f"{locale}: {field} must be an integer")
        if not minimum <= value <= maximum:
            raise ValueError(f"{locale}: {field}={value} is outside {minimum}..{maximum}")
        subtotal += value
    if score["overall"] != subtotal or subtotal < 90:
        raise ValueError(f"{locale}: overall visual score is inconsistent or below 90")
    if abs(subtotal - reference) > 3:
        raise ValueError(f"{locale}: visual score is more than three points from English")


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
    if locale_map.get("schema") != "uriel.locale_map.v2":
        raise ValueError("unsupported locale-map schema")
    source_registry = load_json(VISUAL_SOURCES)
    if source_registry.get("schema") != "uriel.visual_source_registry.v1":
        raise ValueError("unsupported visual-source registry schema")

    source_rows = source_registry.get("locales")
    if not isinstance(source_rows, list):
        raise ValueError("visual-source registry locales must be an array")
    source_by_locale = {}
    for row in source_rows:
        locale = row.get("locale") if isinstance(row, dict) else None
        if not isinstance(locale, str) or locale in source_by_locale:
            raise ValueError("visual-source registry has an invalid or duplicate locale")
        source_by_locale[locale] = row

    configured = {item["locale"] for item in locale_map["locales"]}
    if configured != set(source_by_locale):
        raise ValueError("locale map and visual-source registry locale sets differ")

    reference = source_registry["english_reference"]
    reference_score = source_registry["review"]["reference_score"]
    if reference["score"]["overall"] != reference_score:
        raise ValueError("English visual-reference score is inconsistent")

    source_hash = sha256(ENGLISH_README)
    renderer_rel = RENDERER.relative_to(ROOT).as_posix()
    renderer_hash = sha256(RENDERER)
    source_registry_rel = VISUAL_SOURCES.relative_to(ROOT).as_posix()
    source_registry_hash = sha256(VISUAL_SOURCES)
    archive = source_registry["source_archive"]
    canonical_locale = locale_map["canonical_locale"]

    for item in locale_map["locales"]:
        locale = item["locale"]
        manifest_path = MANIFEST_ROOT / f"{locale}.json"
        previous = load_json(manifest_path)
        translation_status = previous["translation_status"]
        reviewers = previous.get("reviewers", [])
        if translation_status in {"NATIVE_REVIEWED", "VERIFIED"} and not reviewers:
            raise ValueError(f"{locale}: {translation_status} requires at least one named reviewer")

        readme = ROOT / item["readme"]
        image = ROOT / item["image_path"]
        image_dimensions = png_dimensions(image)
        source = reference if locale == canonical_locale else source_by_locale[locale]
        score = source["score"]

        visual_manifest = {
            "locale": locale,
            "role": "GOLD_REFERENCE" if locale == canonical_locale else "LOCALIZED_EXPLAINER_POSTER",
            "image_status": item["image_status"],
            "image_path": item["image_path"],
            "image_sha256": sha256(image),
            "image_dimensions": list(image_dimensions),
            "alt_text": source["alt_text"],
            "source_archive_name": archive["name"],
            "source_archive_sha256": archive["sha256"],
            "source_package_manifest_sha256": archive["package_manifest_sha256"],
            "source_member": source["member"],
            "source_sha256": source["sha256"],
            "source_dimensions": source["dimensions"],
            "source_kind": "LOCKED_ENGLISH_REFERENCE" if locale == canonical_locale else "GENERATED_FULL_POSTER",
            "visual_review_method": source_registry["review"]["method"],
            "visual_reviewed_at_utc": source_registry["review"]["reviewed_at_utc"],
            "reference_score": reference_score,
            "score": score,
            "visual_gate": "PASS",
            "visible_text_status": (
                "REFERENCE_COPY"
                if locale == canonical_locale
                else source_registry["review"]["language_review_boundary"]
            ),
            "native_language_reviewers": [],
            "authority": source_registry["review"]["authority"],
        }

        if locale == canonical_locale:
            visual_manifest.update(
                {
                    "publication_mode": "LOCKED_REFERENCE_BYTES",
                    "deterministic_typography": False,
                }
            )
        else:
            validate_score(locale, score, reference_score)
            if image_dimensions != (3840, 2160):
                raise ValueError(f"{locale}: publication image must be exactly 3840x2160")
            prompt = PROMPT_ROOT / f"{locale}.md"
            copy = COPY_ROOT / f"{locale}.json"
            visual_manifest.update(
                {
                    "publication_mode": "DETERMINISTIC_3840X2160_NORMALIZATION",
                    "deterministic_typography": False,
                    "image_prompt_path": prompt.relative_to(ROOT).as_posix(),
                    "image_prompt_sha256": sha256(prompt),
                    "image_prompt_role": "ART_ONLY_REGENERATION_INPUT_NOT_EXACT_SOURCE_PROMPT",
                    "image_copy_path": copy.relative_to(ROOT).as_posix(),
                    "image_copy_sha256": sha256(copy),
                    "image_renderer_path": renderer_rel,
                    "image_renderer_sha256": renderer_hash,
                }
            )

        visual_manifest["schema"] = "uriel.localized_asset.v2"
        visual_manifest_path = VISUAL_MANIFEST_ROOT / f"{locale}.json"
        write_json(visual_manifest_path, visual_manifest)

        manifest = {
            "source_commit": args.source_commit,
            "source_readme_sha256": source_hash,
            "locale": locale,
            "translation_status": translation_status,
            "reviewers": reviewers,
            "readme_path": item["readme"],
            "readme_sha256": sha256(readme),
            "image_status": item["image_status"],
            "image_path": item["image_path"],
            "image_sha256": sha256(image),
            "visual_manifest_path": visual_manifest_path.relative_to(ROOT).as_posix(),
            "visual_manifest_sha256": sha256(visual_manifest_path),
            "visual_source_registry_path": source_registry_rel,
            "visual_source_registry_sha256": source_registry_hash,
            "verified_at_utc": args.verified_at,
            "schema": "uriel.translation_manifest.v2",
        }
        write_json(manifest_path, manifest)
        print(f"Updated {visual_manifest_path.relative_to(ROOT)}")
        print(f"Updated {manifest_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
