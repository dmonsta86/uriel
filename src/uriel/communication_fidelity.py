"""Communication fidelity, voice, tone, and posture checks (TONE-001..003).

Enforces that Uriel output is calm, precise, patient, plainspoken, constructive,
and firm about evidence. Avoids jargon walls, praise padding, condescension, repeated
dramatic warnings, and performative certainty.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .core import Refusal, canonical_json, sha256_text

FORBIDDEN_TONE_PATTERNS = [
    (r"\b(great job|excellent work|amazing effort|brilliant thought)\b", "praise_padding"),
    (r"\b(obviously|clearly you don't|foolish|obviously wrong)\b", "condescension"),
    (r"\b(100% certain|guaranteed true|flawless|infallible)\b", "performative_certainty"),
]


def check_communication_fidelity(text: str) -> Dict[str, Any]:
    """Validate text output against Uriel's tone and posture contract."""
    clean = str(text)
    violations = []
    for pattern, kind in FORBIDDEN_TONE_PATTERNS:
        match = re.search(pattern, clean, re.IGNORECASE)
        if match:
            violations.append({"kind": kind, "matched_text": match.group(0)})

    word_count = len(clean.split())
    is_jargon_wall = word_count > 300 and clean.count(";") > 10

    valid = len(violations) == 0 and not is_jargon_wall
    return {
        "valid": valid,
        "violations": violations,
        "is_jargon_wall": is_jargon_wall,
        "word_count": word_count,
        "status": "PASS" if valid else "FAIL_TONE_VIOLATION",
    }


def format_constructive_failure(
    failure_code: str,
    what_remains_valid: str,
    preferred_repair: str,
    alternative_repairs: Sequence[str] = (),
) -> Dict[str, Any]:
    """Format failure response with plainspoken tone and exact next move."""
    alternatives = list(alternative_repairs)[:2]  # At most 2 alternatives per TONE-003
    return {
        "failure_code": failure_code,
        "what_remains_valid": what_remains_valid or "All unaffected claims and prior evidence remain valid.",
        "preferred_repair": preferred_repair,
        "alternative_repairs": alternatives,
        "tone": "constructive_and_plainspoken",
    }
