#!/usr/bin/env python3
"""Install reviewed Core-8 visual sources at a deterministic publication size.

The art-only path renders exact v2 typography from ``globalization/image_copy``.
The full-poster path preserves supplied typography and therefore requires a
separate language-review boundary in the asset manifest.  Both paths confine
and stability-check the selected source, normalize it to 3840x2160 with a local
Chromium-family browser, and publish the final image last.  The script performs
no network access and adds no Python dependency.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import os
import shutil
import stat
import struct
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, Mapping, Tuple


ROOT = Path(__file__).resolve().parents[1]
LOCALE_MAP = ROOT / "docs" / "i18n" / "locale_map.json"
COPY_ROOT = ROOT / "globalization" / "image_copy"
ASSET_ROOT = ROOT / "docs" / "assets" / "i18n"
ART_NAME = "uriel-forge-hero-art.png"
OUTPUT_NAME = "uriel-forge-hero.png"
TARGET_WIDTH = 3840
TARGET_HEIGHT = 2160
MAX_JSON_BYTES = 64 * 1024
MAX_ART_BYTES = 32 * 1024 * 1024
MIN_SOURCE_WIDTH = 1536
MIN_SOURCE_HEIGHT = 864

REQUIRED_COPY = {
    "schema",
    "locale",
    "language",
    "direction",
    "official_brand",
    "localized_title",
    "subtitle",
    "challenge",
    "supporting_line",
    "left_rail",
    "right_rail",
    "center_microline",
    "footer",
    "translation_status",
}

FONT_STACKS = {
    "ar": '"Nirmala UI", "Segoe UI", Arial, sans-serif',
    "hi": '"Nirmala UI", "Segoe UI", Arial, sans-serif',
    "ja": '"Yu Gothic", Meiryo, "Segoe UI", sans-serif',
    "zh-Hans": '"Microsoft YaHei", "Segoe UI", sans-serif',
}


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_bounded_stable(path: Path, maximum: int) -> bytes:
    before = path.stat()
    if before.st_size > maximum:
        raise ValueError(f"input exceeds {maximum} bytes: {path}")
    value = path.read_bytes()
    after = path.stat()
    identity_before = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns)
    identity_after = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
    if identity_before != identity_after or len(value) != after.st_size:
        raise RuntimeError(f"input changed while it was being read: {path}")
    return value


def load_json(path: Path) -> dict:
    raw = read_bounded_stable(path, MAX_JSON_BYTES)

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
        raw.decode("utf-8"),
        object_pairs_hook=reject_duplicates,
        parse_constant=reject_constant,
    )


def png_dimensions_bytes(value: bytes) -> Tuple[int, int]:
    header = value[:24]
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("input is not a PNG")
    return struct.unpack(">II", header[16:24])


def png_dimensions(path: Path) -> Tuple[int, int]:
    return png_dimensions_bytes(read_bounded_stable(path, MAX_ART_BYTES))


def is_reparse_or_link(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        info = path.stat()
        reparse_flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        return bool(getattr(info, "st_file_attributes", 0) & reparse_flag)
    except FileNotFoundError:
        return False


def confined_candidate(raw_name: str) -> Path:
    raw = Path(raw_name)
    if not raw.is_absolute():
        raw = ROOT / raw
    lexical = Path(os.path.abspath(str(raw)))
    if not lexical.is_file():
        raise FileNotFoundError(f"candidate is missing or not a file: {lexical}")

    root_resolved = ROOT.resolve(strict=True)
    try:
        common = os.path.commonpath([str(ROOT), str(lexical)])
    except ValueError as exc:
        raise ValueError("candidate is outside the repository") from exc
    if os.path.normcase(common) != os.path.normcase(str(ROOT)):
        raise ValueError("candidate is outside the repository")

    resolved = lexical.resolve(strict=True)
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError("candidate is outside the repository") from exc

    current = lexical
    while True:
        if is_reparse_or_link(current):
            raise ValueError(f"candidate path contains a link or reparse point: {current}")
        if os.path.normcase(str(current)) == os.path.normcase(str(ROOT)):
            break
        if current.parent == current:
            raise ValueError("candidate is outside the repository")
        current = current.parent

    return resolved


def find_browser(explicit: str | None) -> Path:
    candidates = []
    if explicit:
        candidates.append(Path(explicit))
    for command in (
        "msedge",
        "microsoft-edge",
        "google-chrome",
        "chrome",
        "chromium",
        "chromium-browser",
    ):
        resolved = shutil.which(command)
        if resolved:
            candidates.append(Path(resolved))
    candidates.extend(
        Path(path)
        for path in (
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        )
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise FileNotFoundError(
        "No Chromium-family browser found. Pass --browser with an Edge, Chrome, "
        "or Chromium executable."
    )


def image_data_url(value: bytes) -> str:
    return "data:image/png;base64," + base64.b64encode(value).decode("ascii")


def build_art_html(art_bytes: bytes) -> str:
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><style>
html,body{{margin:0;width:{TARGET_WIDTH}px;height:{TARGET_HEIGHT}px;overflow:hidden;background:#05080b}}
img{{display:block;width:100%;height:100%;object-fit:cover}}
</style></head><body><img src="{image_data_url(art_bytes)}" alt=""></body></html>
"""


def _rail(items, class_name: str) -> str:
    return "\n".join(
        f'<div class="rail-item {class_name}">{html.escape(str(item))}</div>'
        for item in items
    )


def validate_copy(locale: str, direction: str, copy: Mapping[str, object]) -> None:
    missing = REQUIRED_COPY - set(copy)
    unknown = set(copy) - REQUIRED_COPY
    if missing or unknown:
        raise ValueError(
            f"{locale}: image-copy fields differ; missing={sorted(missing)}, "
            f"unknown={sorted(unknown)}"
        )
    if copy["schema"] != "forge_of_uriel.visual_copy.v2":
        raise ValueError(f"{locale}: unsupported image-copy schema")
    if copy["locale"] != locale or copy["direction"] != direction:
        raise ValueError(f"{locale}: locale or direction mismatch in image copy")
    if copy["translation_status"] != "AI_ASSISTED_REQUIRES_NATIVE_REVIEW":
        raise ValueError(f"{locale}: image-copy review boundary is missing")
    for key, expected in (("left_rail", 4), ("right_rail", 5), ("footer", 4)):
        value = copy[key]
        if not isinstance(value, list) or len(value) != expected:
            raise ValueError(f"{locale}: {key} must contain exactly {expected} items")
        if any(not isinstance(item, str) or not item.strip() for item in value):
            raise ValueError(f"{locale}: {key} contains an empty or non-text item")
    for key in REQUIRED_COPY - {"left_rail", "right_rail", "footer"}:
        if not isinstance(copy[key], str) or not str(copy[key]).strip():
            raise ValueError(f"{locale}: {key} must be non-empty text")


def build_overlay_html(
    locale: str,
    direction: str,
    copy: Mapping[str, object],
    art_bytes: bytes,
) -> str:
    validate_copy(locale, direction, copy)
    font_stack = FONT_STACKS.get(locale, '"Segoe UI", Arial, sans-serif')
    text_align = "right" if direction == "rtl" else "left"
    edge = "border-right" if direction == "rtl" else "border-left"
    localized_title = html.escape(str(copy["localized_title"]))
    return f"""<!doctype html>
<html lang="{html.escape(locale)}" dir="{html.escape(direction)}">
<head><meta charset="utf-8"><style>
*{{box-sizing:border-box}}
html,body{{margin:0;width:{TARGET_WIDTH}px;height:{TARGET_HEIGHT}px;overflow:hidden;background:#05080b}}
.canvas{{position:relative;width:100%;height:100%;overflow:hidden}}
.art{{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}}
.panel{{position:absolute;left:3.5%;top:4.2%;width:39.5%;max-height:65%;padding:26px 34px 22px;
color:#f8f0df;font-family:{font_stack};text-align:{text_align};
background:linear-gradient(120deg,rgba(4,7,9,.93),rgba(4,7,9,.72));
border:2px solid rgba(221,164,70,.48);box-shadow:0 18px 55px rgba(0,0,0,.42);
text-shadow:0 3px 12px rgba(0,0,0,.95)}}
.official{{direction:ltr;unicode-bidi:isolate;font-family:Georgia,"Times New Roman",serif;
font-size:28px;font-weight:760;letter-spacing:5px;color:#d7aa5d}}
.title{{margin-top:12px;font-family:{font_stack};font-size:78px;font-weight:850;line-height:1.02;
color:#f5dfb0;letter-spacing:.3px}}
.language{{display:inline-block;margin-top:12px;padding:7px 15px;border:1px solid rgba(230,180,91,.65);
font-size:22px;font-weight:700;color:#e8bd6c;background:rgba(8,11,13,.72)}}
.subtitle{{margin-top:18px;font-size:27px;font-weight:720;line-height:1.25;color:#e9bd6c}}
.challenge{{margin-top:28px;font-size:47px;font-weight:850;line-height:1.12;color:#fff8e9}}
.support{{margin-top:13px;font-size:25px;font-weight:560;line-height:1.3;color:#f0d297}}
.rails{{margin-top:27px;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:9px 16px}}
.rail-item{{min-height:45px;padding:10px 13px;{edge}:4px solid rgba(231,180,91,.82);
background:rgba(8,11,13,.76);font-size:22px;font-weight:740;line-height:1.15;color:#f5e5c1}}
.right-rail{{color:#f3ce86}}
.micro{{position:absolute;left:5%;right:5%;top:69.5%;padding:9px 24px;
font-family:{font_stack};font-size:22px;font-weight:760;letter-spacing:1.1px;text-align:center;
color:#f1cf8f;background:rgba(4,7,9,.72);border-top:1px solid rgba(231,180,91,.5);
border-bottom:1px solid rgba(231,180,91,.5);text-shadow:0 2px 8px #000}}
.footer{{position:absolute;left:9%;right:9%;top:73.2%;display:grid;grid-template-columns:repeat(4,1fr);
gap:10px;font-family:{font_stack};font-size:19px;font-weight:780;text-align:center;color:#e9c477;
text-shadow:0 2px 8px #000}}
.footer span{{padding:6px 10px;background:rgba(4,7,9,.78);border:1px solid rgba(231,180,91,.36)}}
</style></head>
<body><main class="canvas" aria-label="{localized_title}">
<img class="art" src="{image_data_url(art_bytes)}" alt="">
<section class="panel">
  <div class="official">{html.escape(str(copy['official_brand']))}</div>
  <div class="title">{localized_title}</div>
  <div class="language">{html.escape(str(copy['language']))}</div>
  <div class="subtitle">{html.escape(str(copy['subtitle']))}</div>
  <div class="challenge">{html.escape(str(copy['challenge']))}</div>
  <div class="support">{html.escape(str(copy['supporting_line']))}</div>
  <div class="rails">{_rail(copy['left_rail'], 'left-rail')}{_rail(copy['right_rail'], 'right-rail')}</div>
</section>
<div class="micro">{html.escape(str(copy['center_microline']))}</div>
<div class="footer">{''.join(f'<span>{html.escape(str(item))}</span>' for item in copy['footer'])}</div>
</main></body></html>
"""


def atomic_copy(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    handle, temporary_name = tempfile.mkstemp(prefix=f".{output.name}.", suffix=".tmp", dir=output.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(handle, "wb") as stream:
            with source.open("rb") as incoming:
                shutil.copyfileobj(incoming, stream, length=1024 * 1024)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, output)
    finally:
        if temporary.exists():
            temporary.unlink()


def render(browser: Path, locale: str, html_text: str, output: Path) -> None:
    with tempfile.TemporaryDirectory(prefix=f"uriel-{locale}-hero-") as temp_name:
        temp = Path(temp_name)
        page = temp / "hero.html"
        screenshot = temp / "hero.png"
        profile = temp / "browser-profile"
        page.write_text(html_text, encoding="utf-8", newline="\n")
        command = [
            str(browser),
            "--headless=new",
            "--disable-background-networking",
            "--disable-component-update",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-features=OptimizationHints,MediaRouter",
            "--disable-gpu",
            "--disable-sync",
            "--hide-scrollbars",
            "--metrics-recording-only",
            "--no-first-run",
            "--no-pings",
            "--run-all-compositor-stages-before-draw",
            "--force-device-scale-factor=1",
            "--virtual-time-budget=1500",
            f"--user-data-dir={profile}",
            f"--window-size={TARGET_WIDTH},{TARGET_HEIGHT}",
            f"--screenshot={screenshot}",
            page.resolve().as_uri(),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=60)
        if completed.returncode != 0 or not screenshot.is_file():
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"{locale}: browser rendering failed: {detail}")
        if png_dimensions(screenshot) != (TARGET_WIDTH, TARGET_HEIGHT):
            raise RuntimeError(
                f"{locale}: rendered dimensions {png_dimensions(screenshot)} do not match "
                f"{(TARGET_WIDTH, TARGET_HEIGHT)}"
            )
        atomic_copy(screenshot, output)


def parse_source_args(values, option: str) -> Dict[str, str]:
    result = {}
    for value in values or []:
        if "=" not in value:
            raise ValueError(f"{option} must use LOCALE=PROJECT_RELATIVE_PATH")
        locale, path = value.split("=", 1)
        if not locale or not path or locale in result:
            raise ValueError(f"invalid or duplicate {option} declaration: {value!r}")
        result[locale] = path
    return result


def parse_digest_args(values) -> Dict[str, str]:
    result = parse_source_args(values, "--source-sha256")
    for locale, digest in result.items():
        if len(digest) != 64 or any(character not in "0123456789abcdef" for character in digest):
            raise ValueError(f"{locale}: --source-sha256 must be a lowercase SHA-256 digest")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--locale",
        action="append",
        dest="locales",
        help=(
            "Locale to render; repeat for multiple locales. If omitted, locales are "
            "derived from explicitly supplied sources; there is no implicit bulk run."
        ),
    )
    parser.add_argument(
        "--candidate",
        action="append",
        default=[],
        metavar="LOCALE=PATH",
        help="Install one reviewed, repository-confined art candidate before rendering.",
    )
    parser.add_argument(
        "--poster",
        action="append",
        default=[],
        metavar="LOCALE=PATH",
        help=(
            "Install one reviewed, repository-confined full poster without adding an "
            "overlay. Generated poster text still requires an explicit review record."
        ),
    )
    parser.add_argument(
        "--source-sha256",
        action="append",
        default=[],
        metavar="LOCALE=SHA256",
        help="Required expected digest for every --candidate or --poster source.",
    )
    parser.add_argument("--browser", help="Path to an Edge, Chrome, or Chromium executable.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    locale_map = load_json(LOCALE_MAP)
    configured = {
        item["locale"]: item
        for item in locale_map["locales"]
        if item["locale"] != locale_map["canonical_locale"]
    }
    candidates = parse_source_args(args.candidate, "--candidate")
    posters = parse_source_args(args.poster, "--poster")
    expected_hashes = parse_digest_args(args.source_sha256)
    overlap = sorted(set(candidates) & set(posters))
    if overlap:
        raise ValueError(f"locale cannot use both --candidate and --poster: {overlap}")
    source_locales = set(candidates) | set(posters)
    if set(expected_hashes) != source_locales:
        raise ValueError("--source-sha256 locales must exactly match all supplied source locales")
    locales = args.locales or list(candidates) + list(posters)
    if not locales:
        raise ValueError("select at least one locale or provide an explicit source")
    if len(locales) != len(set(locales)):
        raise ValueError("locale selections must be unique")
    unknown = sorted((set(locales) | source_locales) - set(configured))
    if unknown:
        raise ValueError(f"unknown or canonical locale(s): {unknown}")
    if (set(candidates) | set(posters)) - set(locales):
        raise ValueError("every source locale must also be selected with --locale")

    browser = find_browser(args.browser)
    print(f"Renderer: {browser}")
    for locale in locales:
        item = configured[locale]
        art_path = ASSET_ROOT / locale / ART_NAME
        final_path = ASSET_ROOT / locale / OUTPUT_NAME
        copy = load_json(COPY_ROOT / f"{locale}.json")
        validate_copy(locale, item["direction"], copy)

        poster_name = posters.get(locale)
        candidate_name = candidates.get(locale)
        if poster_name:
            poster = confined_candidate(poster_name)
            poster_bytes = read_bounded_stable(poster, MAX_ART_BYTES)
            poster_hash = sha256_bytes(poster_bytes)
            if poster_hash != expected_hashes[locale]:
                raise ValueError(f"{locale}: poster SHA-256 differs from --source-sha256")
            source_width, source_height = png_dimensions_bytes(poster_bytes)
            if source_width < MIN_SOURCE_WIDTH or source_height < MIN_SOURCE_HEIGHT:
                raise ValueError(
                    f"{locale}: poster is below {MIN_SOURCE_WIDTH}x{MIN_SOURCE_HEIGHT}: "
                    f"{source_width}x{source_height}"
                )
            if abs((source_width / source_height) - (16 / 9)) > 0.01:
                raise ValueError(f"{locale}: poster is not 16:9")
            with tempfile.TemporaryDirectory(prefix=f"uriel-{locale}-poster-") as install_name:
                normalized_poster = Path(install_name) / OUTPUT_NAME
                render(
                    browser,
                    locale + "-poster",
                    build_art_html(poster_bytes),
                    normalized_poster,
                )
                atomic_copy(normalized_poster, final_path)
            final_hash = sha256_bytes(read_bounded_stable(final_path, MAX_ART_BYTES))
            print(
                f"Installed full poster {locale}: source={source_width}x{source_height} "
                f"source_sha256={poster_hash} final_sha256={final_hash}"
            )
            continue

        if candidate_name:
            candidate = confined_candidate(candidate_name)
            candidate_bytes = read_bounded_stable(candidate, MAX_ART_BYTES)
            candidate_hash = sha256_bytes(candidate_bytes)
            if candidate_hash != expected_hashes[locale]:
                raise ValueError(f"{locale}: candidate SHA-256 differs from --source-sha256")
            source_width, source_height = png_dimensions_bytes(candidate_bytes)
            if source_width < MIN_SOURCE_WIDTH or source_height < MIN_SOURCE_HEIGHT:
                raise ValueError(
                    f"{locale}: candidate is below {MIN_SOURCE_WIDTH}x{MIN_SOURCE_HEIGHT}: "
                    f"{source_width}x{source_height}"
                )
            if abs((source_width / source_height) - (16 / 9)) > 0.01:
                raise ValueError(f"{locale}: candidate is not 16:9")
            with tempfile.TemporaryDirectory(prefix=f"uriel-{locale}-install-") as install_name:
                install_root = Path(install_name)
                normalized_art = install_root / ART_NAME
                rendered_final = install_root / OUTPUT_NAME
                render(browser, locale + "-art", build_art_html(candidate_bytes), normalized_art)
                normalized_bytes = read_bounded_stable(normalized_art, MAX_ART_BYTES)
                render(
                    browser,
                    locale,
                    build_overlay_html(locale, item["direction"], copy, normalized_bytes),
                    rendered_final,
                )
                atomic_copy(normalized_art, art_path)
                atomic_copy(rendered_final, final_path)
            print(
                f"Installed {locale}: source={source_width}x{source_height} "
                f"source_sha256={candidate_hash}"
            )
        else:
            if not art_path.is_file():
                raise FileNotFoundError(f"{locale}: missing approved art layer: {art_path}")
            art_bytes = read_bounded_stable(art_path, MAX_ART_BYTES)
            if png_dimensions_bytes(art_bytes) != (TARGET_WIDTH, TARGET_HEIGHT):
                raise ValueError(
                    f"{locale}: installed art must be {TARGET_WIDTH}x{TARGET_HEIGHT}; "
                    "install a reviewed candidate to normalize it"
                )
            render(
                browser,
                locale,
                build_overlay_html(locale, item["direction"], copy, art_bytes),
                final_path,
            )

        art_hash = sha256_bytes(read_bounded_stable(art_path, MAX_ART_BYTES))
        final_hash = sha256_bytes(read_bounded_stable(final_path, MAX_ART_BYTES))
        print(
            f"Rendered {locale}: {final_path.relative_to(ROOT)} "
            f"({TARGET_WIDTH}x{TARGET_HEIGHT}) art_sha256={art_hash} final_sha256={final_hash}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
