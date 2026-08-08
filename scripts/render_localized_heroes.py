#!/usr/bin/env python3
"""Render deterministic localized text over approved art-only Uriel heroes.

The art layer may be generated, but every rendered character comes from the
reviewable JSON files in ``globalization/image_copy``.  A local Chromium-family
browser performs the rasterization, so this script adds no Python dependency.
"""

from __future__ import annotations

import argparse
import base64
import html
import json
import shutil
import struct
import subprocess
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
LOCALE_MAP = ROOT / "docs" / "i18n" / "locale_map.json"
COPY_ROOT = ROOT / "globalization" / "image_copy"
ASSET_ROOT = ROOT / "docs" / "assets" / "i18n"
ART_NAME = "uriel-forge-hero-art.png"
OUTPUT_NAME = "uriel-forge-hero.png"

REQUIRED_COPY = {
    "locale",
    "subtitle",
    "challenge",
    "supporting",
    "question_intake",
    "read_only",
    "data_readiness",
    "sorting",
    "evidence",
    "gates",
    "repair",
    "submission",
    "provenance",
}

FONT_STACKS = {
    "ar": '"Nirmala UI", "Segoe UI", Arial, sans-serif',
    "hi": '"Nirmala UI", "Segoe UI", Arial, sans-serif',
    "ja": '"Yu Gothic", Meiryo, "Segoe UI", sans-serif',
    "zh-Hans": '"Microsoft YaHei", "Segoe UI", sans-serif',
}


def load_json(path: Path) -> dict:
    def reject_duplicates(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key {key!r} in {path}")
            result[key] = value
        return result

    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=reject_duplicates)


def png_dimensions(path: Path) -> tuple[int, int]:
    header = path.read_bytes()[:24]
    if len(header) != 24 or header[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError(f"not a PNG file: {path}")
    return struct.unpack(">II", header[16:24])


def find_browser(explicit: str | None) -> Path:
    candidates: list[Path] = []
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


def build_html(locale: str, direction: str, copy: dict, art: Path, width: int, height: int) -> str:
    missing = REQUIRED_COPY - set(copy)
    if missing:
        raise ValueError(f"{locale}: missing image-copy fields: {sorted(missing)}")
    if copy["locale"] != locale:
        raise ValueError(f"{locale}: copy file declares locale {copy['locale']!r}")

    encoded_art = base64.b64encode(art.read_bytes()).decode("ascii")
    feature_keys = (
        "question_intake",
        "read_only",
        "data_readiness",
        "sorting",
        "evidence",
        "gates",
        "repair",
        "submission",
        "provenance",
    )
    features = "\n".join(
        f'<div class="feature">{html.escape(str(copy[key]))}</div>'
        for key in feature_keys
    )
    font_stack = FONT_STACKS.get(locale, '"Segoe UI", Arial, sans-serif')
    text_align = "right" if direction == "rtl" else "left"
    edge_rule = "border-right" if direction == "rtl" else "border-left"

    return f"""<!doctype html>
<html lang="{html.escape(locale)}" dir="{html.escape(direction)}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width={width}, initial-scale=1">
<style>
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0;
    width: {width}px;
    height: {height}px;
    overflow: hidden;
    background: #05080b;
  }}
  .canvas {{ position: relative; width: 100%; height: 100%; overflow: hidden; }}
  .art {{ position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; }}
  .panel {{
    position: absolute;
    left: 3.45%;
    top: 5.4%;
    width: 42.5%;
    height: 55.5%;
    color: #f5f1e8;
    font-family: {font_stack};
    text-align: {text_align};
    text-shadow: 0 2px 8px rgba(0, 0, 0, .92);
  }}
  .brand {{
    direction: ltr;
    unicode-bidi: isolate;
    font-family: Georgia, "Times New Roman", serif;
    font-size: 53px;
    font-weight: 800;
    line-height: .91;
    letter-spacing: 1.5px;
    color: #f5e5c1;
  }}
  .brand span {{ color: #e7b45b; }}
  .subtitle {{
    margin-top: 12px;
    max-width: 96%;
    font-size: 21px;
    font-weight: 650;
    line-height: 1.25;
    color: #e8bd6c;
  }}
  .challenge {{
    margin-top: 25px;
    max-width: 97%;
    font-size: 32px;
    font-weight: 760;
    line-height: 1.12;
    color: #fff8e9;
  }}
  .supporting {{
    margin-top: 10px;
    max-width: 96%;
    font-size: 18px;
    font-weight: 520;
    line-height: 1.3;
    color: #efcc86;
  }}
  .features {{
    margin-top: 24px;
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 7px 12px;
    width: 100%;
  }}
  .feature {{
    min-height: 27px;
    padding: 5px 9px;
    {edge_rule}: 2px solid rgba(231, 180, 91, .78);
    background: rgba(5, 8, 11, .52);
    font-size: 15px;
    font-weight: 670;
    line-height: 1.18;
    color: #f5e5c1;
  }}
</style>
</head>
<body>
<main class="canvas" aria-label="The Forge of Uriel — {html.escape(str(copy['subtitle']))}">
  <img class="art" src="data:image/png;base64,{encoded_art}" alt="">
  <section class="panel">
    <div class="brand">THE FORGE<br><span>OF URIEL</span></div>
    <div class="subtitle">{html.escape(str(copy['subtitle']))}</div>
    <div class="challenge">{html.escape(str(copy['challenge']))}</div>
    <div class="supporting">{html.escape(str(copy['supporting']))}</div>
    <div class="features">{features}</div>
  </section>
</main>
</body>
</html>
"""


def render(browser: Path, locale: str, html_text: str, output: Path, width: int, height: int) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"uriel-{locale}-hero-") as temp_name:
        temp = Path(temp_name)
        page = temp / "hero.html"
        screenshot = temp / "hero.png"
        profile = temp / "browser-profile"
        page.write_text(html_text, encoding="utf-8")
        command = [
            str(browser),
            "--headless=new",
            "--disable-background-networking",
            "--disable-extensions",
            "--disable-gpu",
            "--disable-sync",
            "--hide-scrollbars",
            "--metrics-recording-only",
            "--no-first-run",
            "--run-all-compositor-stages-before-draw",
            "--force-device-scale-factor=1",
            "--virtual-time-budget=1200",
            f"--user-data-dir={profile}",
            f"--window-size={width},{height}",
            f"--screenshot={screenshot}",
            page.resolve().as_uri(),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0 or not screenshot.is_file():
            detail = (completed.stderr or completed.stdout).strip()
            raise RuntimeError(f"{locale}: browser rendering failed: {detail}")
        if png_dimensions(screenshot) != (width, height):
            raise RuntimeError(
                f"{locale}: rendered dimensions {png_dimensions(screenshot)} do not match "
                f"source dimensions {(width, height)}"
            )
        shutil.copyfile(screenshot, output)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--locale",
        action="append",
        dest="locales",
        help="Locale to render; repeat for multiple locales (default: every non-English locale).",
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
    locales = args.locales or list(configured)
    unknown = [locale for locale in locales if locale not in configured]
    if unknown:
        raise ValueError(f"unknown or canonical locale(s): {unknown}")

    browser = find_browser(args.browser)
    print(f"Renderer: {browser}")
    for locale in locales:
        item = configured[locale]
        art = ASSET_ROOT / locale / ART_NAME
        output = ASSET_ROOT / locale / OUTPUT_NAME
        if not art.is_file():
            raise FileNotFoundError(f"{locale}: missing approved art layer: {art}")
        width, height = png_dimensions(art)
        copy = load_json(COPY_ROOT / f"{locale}.json")
        page = build_html(locale, item["direction"], copy, art, width, height)
        render(browser, locale, page, output, width, height)
        print(f"Rendered {locale}: {output.relative_to(ROOT)} ({width}x{height})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
