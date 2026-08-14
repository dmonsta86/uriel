"""Opt-in, project-confined Research Verbatim Ledger.

This module preserves explicitly selected user wording. It grants no
scientific authority and contains no provider, network, telemetry,
account-global, or background-capture path.
"""
from __future__ import annotations

import datetime as _dt
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set, Tuple, Union

from .core import (
    Refusal,
    atomic_write_json,
    canonical_json,
    guard_path,
    is_reparse_or_link,
    load_project,
    paths_for,
    read_json,
    safe_relative_path,
    sha256_file,
    sha256_text,
    utc_now,
)


CONSENT_SCHEMA = "uriel.research_verbatim_consent.v1"
ENTRY_SCHEMA = "uriel.research_verbatim_entry.v1"
LEDGER_SCHEMA = "uriel.research_verbatim_ledger.v1"
EXPORT_SCHEMA = "uriel.research_verbatim_export.v1"
SCHEMA_VERSION = 1

MODES = ("OFF", "MANUAL", "ASSISTED", "PROJECT")
ACTIVE_MODES = ("MANUAL", "ASSISTED", "PROJECT")
OFFER_STATES = ("UNSEEN", "OFFERED", "DECLINED", "ACCEPTED", "DISABLED")
CAPTURE_MODES = ("MANUAL", "ASSISTED", "PROJECT")
OFFER_SIGNALS = (
    "HIGH_DETAIL",
    "ACCURACY_SENSITIVE",
    "NOVEL",
    "LONG_LIVED",
    "PROJECT_BASELINE",
    "FORMAL_PREDICTION",
    "CONSEQUENTIAL_REFINEMENT",
)
LINK_RELATIONS = ("REFINES", "CORRECTS", "SUPERSEDES")
DRIFT_CATEGORIES = (
    "PRESERVED_MEANING",
    "OMISSION",
    "CONTRADICTION",
    "OVERSTATEMENT",
    "UNRESOLVED_AMBIGUITY",
)
OFFER_TEXT = (
    "This sounds like an original project baseline where your exact wording "
    "may matter later. Keep this statement verbatim for this project? "
    "Nothing is saved unless you opt in."
)
NORMALIZATION_RULES: Dict[str, str] = {
    "rule_id": "EXACT_UTF8_V1",
    "encoding": "UTF-8",
    "unicode_normalization": "NONE",
    "whitespace_normalization": "NONE",
    "line_ending_normalization": "NONE",
}

MAX_USER_REFERENCE_BYTES = 1024
MAX_SOURCE_REFERENCE_BYTES = 1024
MAX_EXACT_TEXT_BYTES = 128 * 1024
MAX_SUMMARY_BYTES = 16 * 1024
MAX_LABEL_BYTES = 1024
MAX_STATE_BYTES = 2 * 1024 * 1024
MAX_LEDGER_BYTES = 64 * 1024 * 1024
MAX_ENTRIES = 10_000
MAX_TRANSITIONS = 10_000

_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ENTRY_ID = re.compile(r"^rvl-[0-9a-f]{24}$")
_WORD = re.compile(r"[\w'-]+", re.UNICODE)
_NEGATION_WORDS = {"no", "not", "never", "none", "cannot", "without", "neither"}
_OVERSTATEMENT_WORDS = {
    "always", "certain", "certainly", "conclusive", "definitive",
    "definitively", "guarantee", "guaranteed", "proves", "proven",
    "universal", "universally",
}
_STOP_WORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for", "from",
    "has", "have", "in", "is", "it", "of", "on", "or", "that", "the", "this",
    "to", "was", "were", "will", "with",
}
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----"),
    re.compile(
        r"(?i)\b(?:api[_ -]?key|password|passwd|secret|access[_ -]?token)"
        r"\s*[:=]\s*\S{4,}"
    ),
    re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"),
)


@dataclass(frozen=True)
class VerbatimScope:
    root: Path
    user_isolation_key: str
    project_isolation_key: str
    store_root: Path
    user_directory: Path
    scope_directory: Path
    consent_path: Path
    ledger_path: Path


def _refusal(
    message: str,
    code: str,
    *,
    details: Optional[Mapping[str, Any]] = None,
    repairs: Optional[Sequence[str]] = None,
) -> Refusal:
    options = list(
        repairs
        or (
            "Inspect the selected user and project scope, then retry the exact action.",
            "Review the Research Verbatim Ledger help and current consent state.",
            "Cancel this action and leave the isolated ledger unchanged.",
        )
    )
    return Refusal(message, code=code, details=details, repairs=options)


def _bounded_text(
    value: Any,
    *,
    name: str,
    maximum: int,
    allow_empty: bool = False,
) -> str:
    if not isinstance(value, str):
        raise _refusal(name + " must be text.", "VERBATIM_TEXT_REQUIRED")
    if not value and not allow_empty:
        raise _refusal(name + " must not be empty.", "VERBATIM_TEXT_EMPTY")
    if "\x00" in value:
        raise _refusal(name + " contains a NUL character.", "VERBATIM_TEXT_NUL")
    size = len(value.encode("utf-8"))
    if size > maximum:
        raise _refusal(
            name + " exceeds the bounded UTF-8 size.",
            "VERBATIM_TEXT_TOO_LARGE",
            details={"bytes": size, "maximum_bytes": maximum},
            repairs=(
                "Select one smaller project-defining statement.",
                "Split distinct statements into separately confirmed entries.",
                "Keep the larger document in normal evidence storage.",
            ),
        )
    return value


def _digest_record(value: Mapping[str, Any], field: str) -> str:
    body = dict(value)
    body.pop(field, None)
    return sha256_text(canonical_json(body))


def _validate_utc_timestamp(value: Any, *, name: str) -> str:
    text = _bounded_text(value, name=name, maximum=64)
    if not text.endswith("Z"):
        raise _refusal(
            name + " must be a UTC timestamp ending in Z.",
            "VERBATIM_TIMESTAMP_INVALID",
        )
    try:
        parsed = _dt.datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise _refusal(
            name + " is not a valid ISO 8601 timestamp.",
            "VERBATIM_TIMESTAMP_INVALID",
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != _dt.timedelta(0):
        raise _refusal(
            name + " must identify UTC.",
            "VERBATIM_TIMESTAMP_INVALID",
        )
    return text


def _scope(root: Union[Path, str], user_reference: str) -> VerbatimScope:
    raw_user = _bounded_text(
        user_reference.strip() if isinstance(user_reference, str) else user_reference,
        name="User scope reference",
        maximum=MAX_USER_REFERENCE_BYTES,
    )
    user_value = unicodedata.normalize("NFC", raw_user)
    paths = paths_for(root)
    project = load_project(paths.root)
    project_id = str(project.get("project_id", "")).strip()
    if not project_id:
        raise _refusal(
            "The Uriel project has no stable project identity.",
            "VERBATIM_PROJECT_ID_MISSING",
        )
    user_digest = sha256_text("uriel-rvl-user-v1\n" + user_value)
    project_digest = sha256_text("uriel-rvl-project-v1\n" + project_id)
    store_root = guard_path(paths.root, paths.state / "research-verbatim")
    user_directory = guard_path(paths.root, store_root / ("user-" + user_digest))
    scope_directory = guard_path(
        paths.root, user_directory / ("project-" + project_digest)
    )
    return VerbatimScope(
        root=paths.root,
        user_isolation_key="sha256:" + user_digest,
        project_isolation_key="sha256:" + project_digest,
        store_root=store_root,
        user_directory=user_directory,
        scope_directory=scope_directory,
        consent_path=guard_path(paths.root, scope_directory / "consent.json"),
        ledger_path=guard_path(paths.root, scope_directory / "ledger.json"),
    )


def _default_consent(scope: VerbatimScope) -> Dict[str, Any]:
    value: Dict[str, Any] = {
        "schema": CONSENT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "user_isolation_key": scope.user_isolation_key,
        "project_isolation_key": scope.project_isolation_key,
        "mode": "OFF",
        "offer_state": "UNSEEN",
        "revision": 0,
        "transitions": [],
        "state_sha256": "",
    }
    value["state_sha256"] = _digest_record(value, "state_sha256")
    return value


def _validate_consent(
    scope: VerbatimScope, value: Mapping[str, Any]
) -> Dict[str, Any]:
    state = dict(value)
    if state.get("schema") != CONSENT_SCHEMA or state.get("schema_version") != 1:
        raise _refusal(
            "Research Verbatim Ledger consent schema mismatch.",
            "VERBATIM_CONSENT_SCHEMA_MISMATCH",
        )
    if (
        state.get("user_isolation_key") != scope.user_isolation_key
        or state.get("project_isolation_key") != scope.project_isolation_key
    ):
        raise _refusal(
            "Research Verbatim Ledger consent belongs to another scope.",
            "VERBATIM_SCOPE_MISMATCH",
        )
    if state.get("mode") not in MODES or state.get("offer_state") not in OFFER_STATES:
        raise _refusal(
            "Research Verbatim Ledger consent has an unknown state.",
            "VERBATIM_CONSENT_STATE_INVALID",
        )
    supplied = str(state.get("state_sha256", ""))
    if not _HEX64.fullmatch(supplied) or supplied != _digest_record(
        state, "state_sha256"
    ):
        raise _refusal(
            "Research Verbatim Ledger consent integrity verification failed.",
            "VERBATIM_CONSENT_TAMPERED",
            repairs=(
                "Restore the exact consent bytes from a verified backup.",
                "Inspect the changed state without capturing a new entry.",
                "Remove the isolated ledger and establish fresh explicit consent.",
            ),
        )
    transitions = state.get("transitions")
    revision = state.get("revision")
    if (
        not isinstance(transitions, list)
        or not isinstance(revision, int)
        or revision != len(transitions)
        or len(transitions) > MAX_TRANSITIONS
    ):
        raise _refusal(
            "Research Verbatim Ledger consent history is inconsistent.",
            "VERBATIM_CONSENT_HISTORY_INVALID",
        )
    prior_mode = "OFF"
    prior_offer = "UNSEEN"
    allowed_actions = {
        "OFFER_SHOWN": ("OFF", "OFFERED"),
        "OFFER_DECLINED": ("OFF", "DECLINED"),
        "CAPTURE_DISABLED": ("OFF", "DISABLED"),
    }
    for index, transition in enumerate(transitions, start=1):
        if not isinstance(transition, Mapping):
            raise _refusal(
                "Research Verbatim Ledger consent transition is invalid.",
                "VERBATIM_CONSENT_HISTORY_INVALID",
            )
        if (
            transition.get("revision") != index
            or transition.get("from_mode") != prior_mode
            or transition.get("from_offer_state") != prior_offer
        ):
            raise _refusal(
                "Research Verbatim Ledger consent transition chain is invalid.",
                "VERBATIM_CONSENT_HISTORY_INVALID",
            )
        action = str(transition.get("action", ""))
        to_mode = str(transition.get("to_mode", ""))
        to_offer = str(transition.get("to_offer_state", ""))
        if action == "MODE_SELECTED":
            action_valid = to_mode in ACTIVE_MODES and to_offer == "ACCEPTED"
        else:
            action_valid = allowed_actions.get(action) == (to_mode, to_offer)
        if not action_valid:
            raise _refusal(
                "Research Verbatim Ledger consent transition is not allowed.",
                "VERBATIM_CONSENT_HISTORY_INVALID",
            )
        _validate_utc_timestamp(
            transition.get("created_at_utc"),
            name="Consent transition timestamp",
        )
        prior_mode = to_mode
        prior_offer = to_offer
    if prior_mode != state["mode"] or prior_offer != state["offer_state"]:
        raise _refusal(
            "Research Verbatim Ledger consent head does not match its history.",
            "VERBATIM_CONSENT_HISTORY_INVALID",
        )
    return state


def _load_consent(scope: VerbatimScope) -> Tuple[Dict[str, Any], bool]:
    if not scope.consent_path.exists():
        return _default_consent(scope), False
    target = guard_path(scope.root, scope.consent_path, must_exist=True)
    if target.stat().st_size > MAX_STATE_BYTES:
        raise _refusal(
            "Research Verbatim Ledger consent state exceeds its size ceiling.",
            "VERBATIM_CONSENT_TOO_LARGE",
        )
    return _validate_consent(scope, read_json(target)), True


def _write_consent(
    scope: VerbatimScope, state: Mapping[str, Any]
) -> Dict[str, Any]:
    checked = dict(state)
    checked["state_sha256"] = _digest_record(checked, "state_sha256")
    _validate_consent(scope, checked)
    scope.scope_directory.mkdir(parents=True, exist_ok=True)
    atomic_write_json(scope.consent_path, checked)
    return _validate_consent(scope, read_json(scope.consent_path))


def _transition(
    scope: VerbatimScope,
    state: Mapping[str, Any],
    *,
    action: str,
    mode: str,
    offer_state: str,
) -> Dict[str, Any]:
    current = dict(state)
    transitions = list(current["transitions"])
    if len(transitions) >= MAX_TRANSITIONS:
        raise _refusal(
            "Research Verbatim Ledger consent history is full.",
            "VERBATIM_CONSENT_HISTORY_LIMIT",
        )
    revision = int(current["revision"]) + 1
    transitions.append(
        {
            "revision": revision,
            "action": action,
            "from_mode": current["mode"],
            "to_mode": mode,
            "from_offer_state": current["offer_state"],
            "to_offer_state": offer_state,
            "created_at_utc": utc_now(),
        }
    )
    current.update(
        {
            "mode": mode,
            "offer_state": offer_state,
            "revision": revision,
            "transitions": transitions,
        }
    )
    return _write_consent(scope, current)


def _default_ledger(scope: VerbatimScope) -> Dict[str, Any]:
    value: Dict[str, Any] = {
        "schema": LEDGER_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "user_isolation_key": scope.user_isolation_key,
        "project_isolation_key": scope.project_isolation_key,
        "revision": 0,
        "entries": [],
        "ledger_sha256": "",
    }
    value["ledger_sha256"] = _digest_record(value, "ledger_sha256")
    return value


def _validate_link(value: Any) -> Dict[str, str]:
    if not isinstance(value, Mapping):
        raise _refusal("Entry links must be objects.", "VERBATIM_LINK_INVALID")
    relation = str(value.get("relation", "")).upper()
    entry_id = str(value.get("entry_id", ""))
    if relation not in LINK_RELATIONS or not _ENTRY_ID.fullmatch(entry_id):
        raise _refusal(
            "Entry link relation or target is invalid.",
            "VERBATIM_LINK_INVALID",
            repairs=(
                "Use REFINES, CORRECTS, or SUPERSEDES with an existing entry ID.",
                "Review the isolated ledger and copy the exact target entry ID.",
                "Omit the optional relationship link.",
            ),
        )
    return {"relation": relation, "entry_id": entry_id}


def _validate_entry(scope: VerbatimScope, value: Any) -> Dict[str, Any]:
    if not isinstance(value, Mapping):
        raise _refusal("A verbatim entry must be an object.", "VERBATIM_ENTRY_INVALID")
    entry = dict(value)
    if entry.get("schema") != ENTRY_SCHEMA or entry.get("schema_version") != 1:
        raise _refusal(
            "Research Verbatim Ledger entry schema mismatch.",
            "VERBATIM_ENTRY_SCHEMA_MISMATCH",
        )
    if (
        entry.get("user_isolation_key") != scope.user_isolation_key
        or entry.get("project_isolation_key") != scope.project_isolation_key
    ):
        raise _refusal(
            "A Research Verbatim Ledger entry belongs to another scope.",
            "VERBATIM_SCOPE_MISMATCH",
        )
    if not _ENTRY_ID.fullmatch(str(entry.get("entry_id", ""))):
        raise _refusal(
            "Research Verbatim Ledger entry ID is invalid.",
            "VERBATIM_ENTRY_ID_INVALID",
        )
    _validate_utc_timestamp(
        entry.get("captured_at_utc"),
        name="Entry capture timestamp",
    )
    text = _bounded_text(
        entry.get("exact_text"),
        name="Exact entry text",
        maximum=MAX_EXACT_TEXT_BYTES,
    )
    if entry.get("exact_text_sha256") != sha256_text(text):
        raise _refusal(
            "Exact verbatim text no longer matches its SHA-256.",
            "VERBATIM_TEXT_HASH_MISMATCH",
        )
    if entry.get("normalization") != NORMALIZATION_RULES:
        raise _refusal(
            "Exact verbatim normalization rules changed.",
            "VERBATIM_NORMALIZATION_MISMATCH",
        )
    if entry.get("capture_mode") not in CAPTURE_MODES:
        raise _refusal(
            "Research Verbatim Ledger capture mode is invalid.",
            "VERBATIM_CAPTURE_MODE_INVALID",
        )
    source = entry.get("source")
    if not isinstance(source, Mapping) or source.get("kind") != "USER_MESSAGE":
        raise _refusal(
            "Only an explicitly selected user message can be a verbatim source.",
            "VERBATIM_SOURCE_KIND_FORBIDDEN",
        )
    _bounded_text(
        source.get("message_ref"),
        name="Source message reference",
        maximum=MAX_SOURCE_REFERENCE_BYTES,
    )
    label = entry.get("label")
    if label is not None:
        _bounded_text(
            label, name="Entry label", maximum=MAX_LABEL_BYTES, allow_empty=True
        )
    summary = entry.get("summary")
    if summary is not None:
        if not isinstance(summary, Mapping) or summary.get("role") != "ADVISORY_SUMMARY":
            raise _refusal("Entry summary boundary is invalid.", "VERBATIM_SUMMARY_INVALID")
        summary_text = _bounded_text(
            summary.get("text"),
            name="Advisory summary",
            maximum=MAX_SUMMARY_BYTES,
            allow_empty=True,
        )
        if summary.get("text_sha256") != sha256_text(summary_text):
            raise _refusal("Entry summary hash mismatch.", "VERBATIM_SUMMARY_HASH_MISMATCH")
        if summary_text == text:
            raise _refusal(
                "A summary must remain distinct from exact text.",
                "VERBATIM_SUMMARY_SUBSTITUTION",
            )
    links = entry.get("links")
    if not isinstance(links, list):
        raise _refusal("Entry links must be an array.", "VERBATIM_LINK_INVALID")
    checked_links = [_validate_link(item) for item in links]
    signatures = {(item["relation"], item["entry_id"]) for item in checked_links}
    if len(signatures) != len(checked_links):
        raise _refusal(
            "Duplicate entry links are not allowed.",
            "VERBATIM_LINK_DUPLICATE",
        )
    supplied = str(entry.get("entry_record_sha256", ""))
    if not _HEX64.fullmatch(supplied) or supplied != _digest_record(
        entry, "entry_record_sha256"
    ):
        raise _refusal(
            "Research Verbatim Ledger entry integrity verification failed.",
            "VERBATIM_ENTRY_TAMPERED",
        )
    expected_id = "rvl-" + sha256_text(
        canonical_json(
            {
                "user_isolation_key": entry["user_isolation_key"],
                "project_isolation_key": entry["project_isolation_key"],
                "source_message_ref": source["message_ref"],
                "captured_at_utc": entry["captured_at_utc"],
                "exact_text_sha256": entry["exact_text_sha256"],
                "capture_mode": entry["capture_mode"],
            }
        )
    )[:24]
    if entry["entry_id"] != expected_id:
        raise _refusal(
            "Research Verbatim Ledger stable entry ID does not match its provenance.",
            "VERBATIM_ENTRY_ID_MISMATCH",
        )
    return entry


def _validate_ledger(
    scope: VerbatimScope, value: Mapping[str, Any]
) -> Dict[str, Any]:
    ledger = dict(value)
    if ledger.get("schema") != LEDGER_SCHEMA or ledger.get("schema_version") != 1:
        raise _refusal(
            "Research Verbatim Ledger schema mismatch.",
            "VERBATIM_LEDGER_SCHEMA_MISMATCH",
        )
    if (
        ledger.get("user_isolation_key") != scope.user_isolation_key
        or ledger.get("project_isolation_key") != scope.project_isolation_key
    ):
        raise _refusal(
            "Research Verbatim Ledger belongs to another scope.",
            "VERBATIM_SCOPE_MISMATCH",
        )
    entries = ledger.get("entries")
    if not isinstance(entries, list) or len(entries) > MAX_ENTRIES:
        raise _refusal(
            "Research Verbatim Ledger entry count is invalid.",
            "VERBATIM_ENTRY_COUNT_INVALID",
        )
    checked = [_validate_entry(scope, item) for item in entries]
    identifiers = [str(item["entry_id"]) for item in checked]
    if len(set(identifiers)) != len(identifiers):
        raise _refusal(
            "Research Verbatim Ledger contains duplicate entry IDs.",
            "VERBATIM_ENTRY_ID_DUPLICATE",
        )
    revision = ledger.get("revision")
    if not isinstance(revision, int) or revision < len(entries):
        raise _refusal(
            "Research Verbatim Ledger revision is invalid.",
            "VERBATIM_LEDGER_REVISION_INVALID",
        )
    supplied = str(ledger.get("ledger_sha256", ""))
    if not _HEX64.fullmatch(supplied) or supplied != _digest_record(
        ledger, "ledger_sha256"
    ):
        raise _refusal(
            "Research Verbatim Ledger integrity verification failed.",
            "VERBATIM_LEDGER_TAMPERED",
        )
    return ledger


def _load_ledger(scope: VerbatimScope) -> Tuple[Dict[str, Any], bool]:
    if not scope.ledger_path.exists():
        return _default_ledger(scope), False
    target = guard_path(scope.root, scope.ledger_path, must_exist=True)
    if target.stat().st_size > MAX_LEDGER_BYTES:
        raise _refusal(
            "Research Verbatim Ledger exceeds its bounded size.",
            "VERBATIM_LEDGER_TOO_LARGE",
        )
    return _validate_ledger(scope, read_json(target)), True


def _write_ledger(
    scope: VerbatimScope, value: Mapping[str, Any]
) -> Dict[str, Any]:
    ledger = dict(value)
    ledger["ledger_sha256"] = _digest_record(ledger, "ledger_sha256")
    _validate_ledger(scope, ledger)
    scope.scope_directory.mkdir(parents=True, exist_ok=True)
    atomic_write_json(scope.ledger_path, ledger)
    return _validate_ledger(scope, read_json(scope.ledger_path))


def _looks_like_secret(text: str) -> bool:
    return any(pattern.search(text) is not None for pattern in _SECRET_PATTERNS)


def _require_active(state: Mapping[str, Any]) -> str:
    mode = str(state.get("mode"))
    if mode not in ACTIVE_MODES:
        raise _refusal(
            "Research Verbatim Ledger capture is OFF for this user and project.",
            "VERBATIM_CONSENT_REQUIRED",
            repairs=(
                "Explicitly opt in to manual, assisted, or project mode.",
                "Inspect the unchanged consent state.",
                "Continue normal Uriel work without capturing exact wording.",
            ),
        )
    return mode


def consent_status(
    root: Union[Path, str], user_reference: str
) -> Dict[str, Any]:
    """Inspect consent without creating default state."""

    scope = _scope(root, user_reference)
    state, state_exists = _load_consent(scope)
    ledger, ledger_exists = _load_ledger(scope)
    return {
        "schema": CONSENT_SCHEMA,
        "user_isolation_key": scope.user_isolation_key,
        "project_isolation_key": scope.project_isolation_key,
        "mode": state["mode"],
        "offer_state": state["offer_state"],
        "consent_revision": state["revision"],
        "entry_count": len(ledger["entries"]),
        "consent_store_exists": state_exists,
        "ledger_store_exists": ledger_exists,
        "capture_enabled": state["mode"] in ACTIVE_MODES,
        "offline_only": True,
    }


def consider_offer(
    root: Union[Path, str],
    user_reference: str,
    signals: Iterable[str],
) -> Dict[str, Any]:
    """Return at most one discreet offer and never create an entry."""

    scope = _scope(root, user_reference)
    state, _ = _load_consent(scope)
    supplied = {
        str(signal).strip().upper().replace("-", "_") for signal in signals
    }
    unknown = sorted(supplied - set(OFFER_SIGNALS))
    if unknown:
        raise _refusal(
            "Unknown Research Verbatim Ledger offer signal.",
            "VERBATIM_OFFER_SIGNAL_INVALID",
            details={"unknown": unknown, "allowed": list(OFFER_SIGNALS)},
        )
    common = {
        "verbatim_entry_created": False,
        "message_content_recorded": False,
    }
    if not supplied:
        return dict(common, decision="NO_OFFER", reason="NO_QUALIFYING_SIGNAL")
    if state["mode"] != "OFF":
        return dict(common, decision="SUPPRESSED", reason="ALREADY_ENABLED")
    if state["offer_state"] != "UNSEEN":
        return dict(
            common,
            decision="SUPPRESSED",
            reason="OFFER_ALREADY_RESOLVED",
            offer_state=state["offer_state"],
        )
    updated = _transition(
        scope,
        state,
        action="OFFER_SHOWN",
        mode="OFF",
        offer_state="OFFERED",
    )
    return dict(
        common,
        decision="OFFER",
        offer=OFFER_TEXT,
        offer_state=updated["offer_state"],
        preference_metadata_recorded=True,
    )


def decline_offer(
    root: Union[Path, str], user_reference: str
) -> Dict[str, Any]:
    scope = _scope(root, user_reference)
    state, _ = _load_consent(scope)
    updated = _transition(
        scope,
        state,
        action="OFFER_DECLINED",
        mode="OFF",
        offer_state="DECLINED",
    )
    return {
        "mode": updated["mode"],
        "offer_state": updated["offer_state"],
        "verbatim_entry_created": False,
        "message_content_recorded": False,
    }


def set_consent_mode(
    root: Union[Path, str],
    user_reference: str,
    mode: str,
    *,
    explicit_opt_in: bool,
) -> Dict[str, Any]:
    selected = str(mode).upper()
    if selected not in ACTIVE_MODES:
        raise _refusal(
            "Consent mode must be MANUAL, ASSISTED, or PROJECT.",
            "VERBATIM_MODE_INVALID",
        )
    if not explicit_opt_in:
        raise _refusal(
            "Research Verbatim Ledger mode requires explicit user opt-in.",
            "VERBATIM_EXPLICIT_OPT_IN_REQUIRED",
        )
    scope = _scope(root, user_reference)
    state, _ = _load_consent(scope)
    _load_ledger(scope)
    updated = _transition(
        scope,
        state,
        action="MODE_SELECTED",
        mode=selected,
        offer_state="ACCEPTED",
    )
    return {
        "mode": updated["mode"],
        "offer_state": updated["offer_state"],
        "consent_revision": updated["revision"],
        "user_isolation_key": scope.user_isolation_key,
        "project_isolation_key": scope.project_isolation_key,
    }


def disable_capture(
    root: Union[Path, str], user_reference: str
) -> Dict[str, Any]:
    scope = _scope(root, user_reference)
    state, _ = _load_consent(scope)
    ledger_exists = scope.ledger_path.exists()
    updated = _transition(
        scope,
        state,
        action="CAPTURE_DISABLED",
        mode="OFF",
        offer_state="DISABLED",
    )
    return {
        "mode": updated["mode"],
        "offer_state": updated["offer_state"],
        "entry_count": None,
        "ledger_preserved": ledger_exists,
        "ledger_content_read": False,
        "future_capture_enabled": False,
    }


def propose_entry(
    root: Union[Path, str],
    user_reference: str,
    exact_text: str,
    *,
    source_message_ref: str,
    label: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an in-memory assisted proposal with no content write."""

    scope = _scope(root, user_reference)
    state, _ = _load_consent(scope)
    if state["mode"] != "ASSISTED":
        raise _refusal(
            "Assisted proposals require explicit ASSISTED mode.",
            "VERBATIM_ASSISTED_MODE_REQUIRED",
        )
    text = _bounded_text(
        exact_text, name="Exact entry text", maximum=MAX_EXACT_TEXT_BYTES
    )
    source_ref = _bounded_text(
        source_message_ref,
        name="Source message reference",
        maximum=MAX_SOURCE_REFERENCE_BYTES,
    )
    label_value = (
        None
        if label is None
        else _bounded_text(
            label, name="Entry label", maximum=MAX_LABEL_BYTES, allow_empty=True
        )
    )
    proposal_id = "rvp-" + sha256_text(
        canonical_json(
            {
                "user_isolation_key": scope.user_isolation_key,
                "project_isolation_key": scope.project_isolation_key,
                "source_message_ref": source_ref,
                "exact_text_sha256": sha256_text(text),
                "label": label_value,
            }
        )
    )[:24]
    return {
        "proposal_id": proposal_id,
        "exact_text": text,
        "exact_text_sha256": sha256_text(text),
        "source_message_ref": source_ref,
        "label": label_value,
        "requires_entry_confirmation": True,
        "persisted": False,
    }


def capture_entry(
    root: Union[Path, str],
    user_reference: str,
    exact_text: str,
    *,
    source_message_ref: str,
    capture_mode: str,
    confirmed: bool,
    project_research_statement: bool,
    qualifying_research_statement: bool = False,
    label: Optional[str] = None,
    summary: Optional[str] = None,
    links: Sequence[Mapping[str, str]] = (),
    captured_at_utc: Optional[str] = None,
    source_kind: str = "USER_MESSAGE",
) -> Dict[str, Any]:
    """Persist one exact, explicitly authorized user research statement."""

    scope = _scope(root, user_reference)
    state, _ = _load_consent(scope)
    active_mode = _require_active(state)
    selected_mode = str(capture_mode).upper()
    if selected_mode not in CAPTURE_MODES:
        raise _refusal("Capture mode is invalid.", "VERBATIM_CAPTURE_MODE_INVALID")
    allowed = (
        selected_mode == "MANUAL"
        or (selected_mode == "ASSISTED" and active_mode == "ASSISTED")
        or (selected_mode == "PROJECT" and active_mode == "PROJECT")
    )
    if not allowed:
        raise _refusal(
            "The requested capture route is not authorized by the active mode.",
            "VERBATIM_CAPTURE_MODE_NOT_AUTHORIZED",
            details={"active_mode": active_mode, "capture_mode": selected_mode},
        )
    if selected_mode in {"MANUAL", "ASSISTED"} and not confirmed:
        raise _refusal(
            "Every manual or assisted entry requires explicit confirmation.",
            "VERBATIM_ENTRY_CONFIRMATION_REQUIRED",
        )
    if selected_mode == "PROJECT" and not qualifying_research_statement:
        raise _refusal(
            "Project mode captures only identified qualifying research statements.",
            "VERBATIM_PROJECT_QUALIFICATION_REQUIRED",
        )
    if not project_research_statement:
        raise _refusal(
            "Only project-relevant user research wording may enter this ledger.",
            "VERBATIM_UNRELATED_CONTENT_REFUSED",
        )
    if str(source_kind).upper() != "USER_MESSAGE":
        raise _refusal(
            "Hidden, system, provider, or unrelated content cannot be captured.",
            "VERBATIM_SOURCE_KIND_FORBIDDEN",
        )
    text = _bounded_text(
        exact_text, name="Exact entry text", maximum=MAX_EXACT_TEXT_BYTES
    )
    if _looks_like_secret(text):
        raise _refusal(
            "The selected text resembles a credential or secret.",
            "VERBATIM_CREDENTIAL_CONTENT_REFUSED",
            repairs=(
                "Remove the credential and select only the research statement.",
                "Rotate any exposed credential through its owning service.",
                "Keep authentication material outside Uriel.",
            ),
        )
    source_ref = _bounded_text(
        source_message_ref,
        name="Source message reference",
        maximum=MAX_SOURCE_REFERENCE_BYTES,
    )
    label_value = (
        None
        if label is None
        else _bounded_text(
            label, name="Entry label", maximum=MAX_LABEL_BYTES, allow_empty=True
        )
    )
    summary_value: Optional[Dict[str, str]] = None
    if summary is not None:
        summary_text = _bounded_text(
            summary,
            name="Advisory summary",
            maximum=MAX_SUMMARY_BYTES,
            allow_empty=True,
        )
        if summary_text == text:
            raise _refusal(
                "Exact text cannot be substituted into the summary field.",
                "VERBATIM_SUMMARY_SUBSTITUTION",
            )
        summary_value = {
            "role": "ADVISORY_SUMMARY",
            "text": summary_text,
            "text_sha256": sha256_text(summary_text),
        }
    ledger, _ = _load_ledger(scope)
    if len(ledger["entries"]) >= MAX_ENTRIES:
        raise _refusal(
            "Research Verbatim Ledger reached its entry ceiling.",
            "VERBATIM_ENTRY_LIMIT",
        )
    checked_links = [_validate_link(item) for item in links]
    known_ids = {str(item["entry_id"]) for item in ledger["entries"]}
    missing_links = sorted(
        {item["entry_id"] for item in checked_links} - known_ids
    )
    if missing_links:
        raise _refusal(
            "Entry relationship targets are absent from this isolated ledger.",
            "VERBATIM_LINK_TARGET_MISSING",
            details={"missing_entry_ids": missing_links},
        )
    captured = _validate_utc_timestamp(
        captured_at_utc or utc_now(),
        name="Entry capture timestamp",
    )
    identity = {
        "user_isolation_key": scope.user_isolation_key,
        "project_isolation_key": scope.project_isolation_key,
        "source_message_ref": source_ref,
        "captured_at_utc": captured,
        "exact_text_sha256": sha256_text(text),
        "capture_mode": selected_mode,
    }
    entry_id = "rvl-" + sha256_text(canonical_json(identity))[:24]
    if entry_id in known_ids:
        raise _refusal(
            "This exact capture identity already exists.",
            "VERBATIM_ENTRY_DUPLICATE",
        )
    entry: Dict[str, Any] = {
        "schema": ENTRY_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "entry_id": entry_id,
        "user_isolation_key": scope.user_isolation_key,
        "project_isolation_key": scope.project_isolation_key,
        "source": {"kind": "USER_MESSAGE", "message_ref": source_ref},
        "captured_at_utc": captured,
        "normalization": dict(NORMALIZATION_RULES),
        "exact_text": text,
        "exact_text_sha256": sha256_text(text),
        "capture_mode": selected_mode,
        "label": label_value,
        "summary": summary_value,
        "links": checked_links,
        "entry_record_sha256": "",
    }
    entry["entry_record_sha256"] = _digest_record(entry, "entry_record_sha256")
    _validate_entry(scope, entry)
    updated = dict(ledger)
    updated["revision"] = int(updated["revision"]) + 1
    updated["entries"] = [*list(updated["entries"]), entry]
    written = _write_ledger(scope, updated)
    return {
        "status": "CAPTURED",
        "entry": dict(entry),
        "ledger_revision": written["revision"],
        "entry_count": len(written["entries"]),
    }


def verify_ledger(
    root: Union[Path, str], user_reference: str
) -> Dict[str, Any]:
    scope = _scope(root, user_reference)
    state, state_exists = _load_consent(scope)
    ledger, ledger_exists = _load_ledger(scope)
    return {
        "verified": True,
        "mode": state["mode"],
        "offer_state": state["offer_state"],
        "consent_store_exists": state_exists,
        "ledger_store_exists": ledger_exists,
        "entry_count": len(ledger["entries"]),
        "state_sha256": state["state_sha256"],
        "ledger_sha256": ledger["ledger_sha256"],
        "user_isolation_key": scope.user_isolation_key,
        "project_isolation_key": scope.project_isolation_key,
    }


def review_entries(
    root: Union[Path, str], user_reference: str
) -> Dict[str, Any]:
    scope = _scope(root, user_reference)
    ledger, exists = _load_ledger(scope)
    return {
        "entry_count": len(ledger["entries"]),
        "ledger_store_exists": exists,
        "entries": [dict(item) for item in ledger["entries"]],
        "exact_text_is_distinct_from_summary": True,
    }


def search_entries(
    root: Union[Path, str], user_reference: str, query: str
) -> Dict[str, Any]:
    needle = _bounded_text(
        query, name="Search query", maximum=MAX_EXACT_TEXT_BYTES
    ).casefold()
    rows = review_entries(root, user_reference)["entries"]
    matches = []
    for entry in rows:
        fields = (
            str(entry.get("exact_text", "")),
            str(entry.get("label") or ""),
            str(entry.get("source", {}).get("message_ref", "")),
        )
        if any(needle in value.casefold() for value in fields):
            matches.append(entry)
    return {"query": query, "match_count": len(matches), "entries": matches}


def _comparison_tokens(text: str) -> Tuple[List[str], Set[str]]:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    tokens = [token for token in _WORD.findall(normalized) if token]
    meaningful = {
        token for token in tokens if token not in _STOP_WORDS and len(token) > 1
    }
    return tokens, meaningful


def drift_review(
    root: Union[Path, str],
    user_reference: str,
    later_text: str,
    *,
    entry_ids: Sequence[str],
) -> Dict[str, Any]:
    """Compare conservatively without persisting or editing either text."""

    later = _bounded_text(
        later_text, name="Later review text", maximum=MAX_EXACT_TEXT_BYTES
    )
    if not entry_ids:
        raise _refusal(
            "Drift review requires at least one linked entry.",
            "VERBATIM_DRIFT_ENTRY_REQUIRED",
        )
    scope = _scope(root, user_reference)
    ledger, _ = _load_ledger(scope)
    by_id = {str(item["entry_id"]): item for item in ledger["entries"]}
    missing = sorted(set(entry_ids) - set(by_id))
    if missing:
        raise _refusal(
            "Drift review entry is absent from this isolated ledger.",
            "VERBATIM_DRIFT_ENTRY_MISSING",
            details={"missing_entry_ids": missing},
        )
    later_tokens, later_terms = _comparison_tokens(later)
    later_normalized = unicodedata.normalize("NFKC", later).casefold().strip()
    results = []
    for entry_id in entry_ids:
        entry = by_id[entry_id]
        original = str(entry["exact_text"])
        original_tokens, original_terms = _comparison_tokens(original)
        original_normalized = (
            unicodedata.normalize("NFKC", original).casefold().strip()
        )
        shared = original_terms & later_terms
        coverage = len(shared) / max(1, len(original_terms))
        union = original_terms | later_terms
        overlap = len(shared) / max(1, len(union))
        original_negative = any(
            token in _NEGATION_WORDS or token.endswith("n't")
            for token in original_tokens
        )
        later_negative = any(
            token in _NEGATION_WORDS or token.endswith("n't")
            for token in later_tokens
        )
        new_overstatement = sorted(
            (_OVERSTATEMENT_WORDS & later_terms)
            - (_OVERSTATEMENT_WORDS & original_terms)
        )
        categories: List[str] = []
        if later_normalized == original_normalized:
            categories.append("PRESERVED_MEANING")
        else:
            if coverage < 0.80:
                categories.append("OMISSION")
            if original_negative != later_negative and overlap >= 0.25:
                categories.append("CONTRADICTION")
            if new_overstatement:
                categories.append("OVERSTATEMENT")
            categories.append("UNRESOLVED_AMBIGUITY")
        results.append(
            {
                "entry_id": entry_id,
                "exact_text_sha256": entry["exact_text_sha256"],
                "categories": categories,
                "lexical_evidence": {
                    "original_term_coverage": round(coverage, 6),
                    "set_overlap": round(overlap, 6),
                    "negation_changed": original_negative != later_negative,
                    "new_overstatement_markers": new_overstatement,
                },
            }
        )
    return {
        "schema": "uriel.research_verbatim_drift_review.v1",
        "later_text_sha256": sha256_text(later),
        "entry_results": results,
        "categories": list(DRIFT_CATEGORIES),
        "advisory_only": True,
        "scientific_proof": False,
        "semantic_fidelity_decided": False,
        "source_text_modified": False,
        "later_text_modified": False,
        "persisted": False,
    }


def export_ledger(
    root: Union[Path, str],
    user_reference: str,
    destination: str,
) -> Dict[str, Any]:
    scope = _scope(root, user_reference)
    state, _ = _load_consent(scope)
    ledger, _ = _load_ledger(scope)
    safe = safe_relative_path(destination)
    if safe.parts and safe.parts[0] == ".uriel":
        raise _refusal(
            "A verbatim export must be outside private .uriel state.",
            "VERBATIM_EXPORT_PRIVATE_DESTINATION",
        )
    target = guard_path(scope.root, scope.root / safe)
    if target.exists():
        raise _refusal(
            "Uriel will not overwrite an existing verbatim export.",
            "VERBATIM_EXPORT_EXISTS",
        )
    record: Dict[str, Any] = {
        "schema": EXPORT_SCHEMA,
        "schema_version": SCHEMA_VERSION,
        "created_at_utc": utc_now(),
        "user_isolation_key": scope.user_isolation_key,
        "project_isolation_key": scope.project_isolation_key,
        "consent": {
            "mode": state["mode"],
            "offer_state": state["offer_state"],
            "revision": state["revision"],
            "state_sha256": state["state_sha256"],
        },
        "ledger_sha256": ledger["ledger_sha256"],
        "entry_count": len(ledger["entries"]),
        "entries": list(ledger["entries"]),
        "privacy_notice": (
            "This explicit export contains exact user wording. Review its "
            "classification and destination before sharing."
        ),
        "authority": {
            "advisory_only": True,
            "scientific_proof": False,
            "publication_authority": False,
        },
        "export_record_sha256": "",
    }
    record["export_record_sha256"] = _digest_record(
        record, "export_record_sha256"
    )
    atomic_write_json(target, record)
    readback = read_json(target)
    expected_export_hash = record["export_record_sha256"]
    if (
        not isinstance(readback, Mapping)
        or readback.get("export_record_sha256") != expected_export_hash
        or _digest_record(readback, "export_record_sha256")
        != expected_export_hash
    ):
        raise _refusal(
            "Verbatim export readback mismatch.",
            "VERBATIM_EXPORT_READBACK",
        )
    return {
        "output": safe.as_posix(),
        "bytes": target.stat().st_size,
        "sha256": sha256_file(target),
        "entry_count": record["entry_count"],
        "export_record_sha256": record["export_record_sha256"],
    }


def remove_entry(
    root: Union[Path, str],
    user_reference: str,
    entry_id: str,
    *,
    confirmed: bool,
) -> Dict[str, Any]:
    if not confirmed:
        raise _refusal(
            "Selected-entry removal requires explicit confirmation.",
            "VERBATIM_REMOVAL_CONFIRMATION_REQUIRED",
        )
    scope = _scope(root, user_reference)
    ledger, exists = _load_ledger(scope)
    if not exists:
        raise _refusal(
            "No Research Verbatim Ledger exists in this scope.",
            "VERBATIM_LEDGER_MISSING",
        )
    kept = [item for item in ledger["entries"] if item["entry_id"] != entry_id]
    if len(kept) == len(ledger["entries"]):
        raise _refusal(
            "Selected verbatim entry was not found in this scope.",
            "VERBATIM_ENTRY_NOT_FOUND",
        )
    updated = dict(ledger)
    updated["revision"] = int(updated["revision"]) + 1
    updated["entries"] = kept
    written = _write_ledger(scope, updated)
    return {
        "removed_entry_id": entry_id,
        "entry_count": len(written["entries"]),
        "ledger_revision": written["revision"],
        "other_scopes_changed": False,
    }


def remove_ledger(
    root: Union[Path, str],
    user_reference: str,
    *,
    confirmed: bool,
) -> Dict[str, Any]:
    """Remove exactly one scope using non-recursive, closed membership."""

    if not confirmed:
        raise _refusal(
            "Whole-ledger removal requires explicit confirmation.",
            "VERBATIM_REMOVAL_CONFIRMATION_REQUIRED",
        )
    scope = _scope(root, user_reference)
    if not scope.scope_directory.exists():
        return {
            "removed": False,
            "removed_file_count": 0,
            "other_scopes_changed": False,
        }
    directory = guard_path(scope.root, scope.scope_directory, must_exist=True)
    if is_reparse_or_link(directory):
        raise _refusal(
            "Ledger scope directory is a link or reparse point.",
            "VERBATIM_REMOVE_LINK_REFUSED",
        )
    allowed = {"consent.json", "ledger.json"}
    members = list(directory.iterdir())
    unknown = sorted(item.name for item in members if item.name not in allowed)
    if unknown:
        raise _refusal(
            "Unknown files are present in the isolated ledger directory.",
            "VERBATIM_REMOVE_UNKNOWN_MEMBER",
            details={"unknown_members": unknown},
            repairs=(
                "Inspect and classify the unknown files without deleting them.",
                "Move unrelated files only through an explicit reviewed action.",
                "Use selected-entry removal instead.",
            ),
        )
    verified_members: Dict[str, Path] = {}
    for member in members:
        if is_reparse_or_link(member):
            raise _refusal(
                "Ledger member is a link or reparse point.",
                "VERBATIM_REMOVE_LINK_REFUSED",
            )
        guarded = guard_path(scope.root, member, must_exist=True)
        if not guarded.is_file():
            raise _refusal(
                "Ledger member is not a regular file.",
                "VERBATIM_REMOVE_MEMBER_INVALID",
            )
        verified_members[member.name] = guarded
    removed = 0
    for name in ("ledger.json", "consent.json"):
        target = verified_members.get(name)
        if target is not None:
            target.unlink()
            removed += 1
    directory.rmdir()
    return {
        "removed": True,
        "removed_file_count": removed,
        "other_scopes_changed": False,
        "default_after_removal": "OFF",
    }


class ResearchVerbatimLedger:
    """Programmatic facade bound to one project and one user scope."""

    def __init__(
        self, root: Union[Path, str], user_reference: str
    ) -> None:
        self.root = root
        self.user_reference = user_reference

    def status(self) -> Dict[str, Any]:
        return consent_status(self.root, self.user_reference)

    def consider_offer(self, signals: Iterable[str]) -> Dict[str, Any]:
        return consider_offer(self.root, self.user_reference, signals)

    def decline(self) -> Dict[str, Any]:
        return decline_offer(self.root, self.user_reference)

    def set_mode(
        self, mode: str, *, explicit_opt_in: bool
    ) -> Dict[str, Any]:
        return set_consent_mode(
            self.root,
            self.user_reference,
            mode,
            explicit_opt_in=explicit_opt_in,
        )

    def disable(self) -> Dict[str, Any]:
        return disable_capture(self.root, self.user_reference)

    def propose(
        self,
        exact_text: str,
        *,
        source_message_ref: str,
        label: Optional[str] = None,
    ) -> Dict[str, Any]:
        return propose_entry(
            self.root,
            self.user_reference,
            exact_text,
            source_message_ref=source_message_ref,
            label=label,
        )

    def capture(self, exact_text: str, **kwargs: Any) -> Dict[str, Any]:
        return capture_entry(
            self.root, self.user_reference, exact_text, **kwargs
        )

    def verify(self) -> Dict[str, Any]:
        return verify_ledger(self.root, self.user_reference)

    def review(self) -> Dict[str, Any]:
        return review_entries(self.root, self.user_reference)

    def search(self, query: str) -> Dict[str, Any]:
        return search_entries(self.root, self.user_reference, query)

    def drift(
        self, later_text: str, *, entry_ids: Sequence[str]
    ) -> Dict[str, Any]:
        return drift_review(
            self.root,
            self.user_reference,
            later_text,
            entry_ids=entry_ids,
        )

    def export(self, destination: str) -> Dict[str, Any]:
        return export_ledger(
            self.root, self.user_reference, destination
        )

    def remove_entry(
        self, entry_id: str, *, confirmed: bool
    ) -> Dict[str, Any]:
        return remove_entry(
            self.root,
            self.user_reference,
            entry_id,
            confirmed=confirmed,
        )

    def remove(self, *, confirmed: bool) -> Dict[str, Any]:
        return remove_ledger(
            self.root, self.user_reference, confirmed=confirmed
        )


__all__ = [
    "ACTIVE_MODES",
    "CAPTURE_MODES",
    "CONSENT_SCHEMA",
    "DRIFT_CATEGORIES",
    "ENTRY_SCHEMA",
    "EXPORT_SCHEMA",
    "LEDGER_SCHEMA",
    "LINK_RELATIONS",
    "MODES",
    "NORMALIZATION_RULES",
    "OFFER_SIGNALS",
    "OFFER_TEXT",
    "ResearchVerbatimLedger",
    "capture_entry",
    "consent_status",
    "consider_offer",
    "decline_offer",
    "disable_capture",
    "drift_review",
    "export_ledger",
    "propose_entry",
    "remove_entry",
    "remove_ledger",
    "review_entries",
    "search_entries",
    "set_consent_mode",
    "verify_ledger",
]
