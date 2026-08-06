"""Stable utility imports used by integrations and tests."""
from __future__ import annotations

from .core import (
    IntegrityError,
    Refusal,
    atomic_write_bytes,
    atomic_write_json,
    atomic_write_text,
    canonical_json,
    guard_path,
    is_reparse_or_link,
    read_json,
    safe_relative,
    sha256_bytes,
    sha256_file,
    sha256_text,
    utc_now,
)

__all__ = [
    "IntegrityError",
    "Refusal",
    "atomic_write_bytes",
    "atomic_write_json",
    "atomic_write_text",
    "canonical_json",
    "guard_path",
    "is_reparse_or_link",
    "read_json",
    "safe_relative",
    "sha256_bytes",
    "sha256_file",
    "sha256_text",
    "utc_now",
]
