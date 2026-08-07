"""Pure-standard-library localization helper for human-facing Uriel messages.

Machine contracts, JSON keys, status enums, hashes, schemas, commands, and
scientific authority remain locale-independent.
"""
from __future__ import annotations

import json
import locale as _locale
import os
import unicodedata
from importlib import resources
from string import Formatter
from typing import Any, Mapping

DEFAULT_LOCALE = "en"
SUPPORTED_LOCALES = (
    "en", "es", "fr", "pt-BR", "zh-Hans", "ar", "hi", "ja",
)


def normalize_locale(value: str | None) -> str:
    if not value:
        return DEFAULT_LOCALE
    value = value.strip().replace("_", "-")
    lower = value.casefold()
    aliases = {
        "en-us": "en", "en-gb": "en",
        "es-es": "es", "es-mx": "es", "es-419": "es",
        "fr-fr": "fr", "fr-ca": "fr",
        "pt": "pt-BR", "pt-br": "pt-BR",
        "zh": "zh-Hans", "zh-cn": "zh-Hans", "zh-sg": "zh-Hans",
        "ar-sa": "ar", "ar-eg": "ar",
        "hi-in": "hi",
        "ja-jp": "ja",
    }
    if lower in aliases:
        return aliases[lower]
    for supported in SUPPORTED_LOCALES:
        if lower == supported.casefold():
            return supported
    base = lower.split("-", 1)[0]
    for supported in SUPPORTED_LOCALES:
        if base == supported.casefold().split("-", 1)[0]:
            return supported
    return DEFAULT_LOCALE


def resolve_locale(explicit: str | None = None) -> str:
    if explicit:
        return normalize_locale(explicit)
    env = os.environ.get("URIEL_LANG")
    if env:
        return normalize_locale(env)
    try:
        system_locale = _locale.getlocale()[0]
    except Exception:
        system_locale = None
    return normalize_locale(system_locale)


def _load(locale_name: str) -> Mapping[str, str]:
    try:
        package = resources.files("uriel.locales")
        path = package.joinpath(f"{locale_name}.json")
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        # Fallback to loading from disk if uninstalled
        disk_path = (
            resources.files("uriel").parent / "locales" / f"{locale_name}.json"
        )
        data = json.loads(disk_path.read_text(encoding="utf-8"))

    messages = data.get("messages")
    if not isinstance(messages, dict):
        raise RuntimeError(f"invalid locale catalog: {locale_name}")
    return {str(k): unicodedata.normalize("NFC", str(v)) for k, v in messages.items()}


def placeholder_names(template: str) -> set[str]:
    return {
        field_name
        for _, field_name, _, _ in Formatter().parse(template)
        if field_name
    }


class Translator:
    def __init__(self, locale_name: str | None = None) -> None:
        self.locale = resolve_locale(locale_name)
        self._english = _load(DEFAULT_LOCALE)
        self._messages = self._english if self.locale == DEFAULT_LOCALE else _load(self.locale)

    def text(self, message_id: str, **values: Any) -> str:
        if message_id not in self._english:
            raise KeyError(f"unknown English message ID: {message_id}")
        source = self._english[message_id]
        translated = self._messages.get(message_id, source)
        if placeholder_names(source) != placeholder_names(translated):
            raise RuntimeError(f"placeholder mismatch: {message_id}/{self.locale}")
        return translated.format(**values)
