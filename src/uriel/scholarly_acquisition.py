"""Disabled-by-default scholarly acquisition firewall with local mocks only.

R2.1 deliberately ships no DNS, socket, HTTP, browser, subprocess, proxy, or
credential path.  The exact in-memory/local-fixture transport below exists to
exercise the frozen policy boundary.  Raw response bytes remain opaque until
they have been quarantined and independently rehashed.
"""
from __future__ import annotations

import ipaddress
import json
import os
import re
import shutil
import stat
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple, Union

from .core import (
    Refusal,
    canonical_json,
    canonical_json_bytes,
    guard_path,
    paths_for,
    safe_relative_path,
    sha256_bytes,
    sha256_file,
    sha256_text,
    utc_now,
)
from .data_contracts import (
    MAX_RECORD_FILE_BYTES,
    SCHOLARLY_ADAPTER_SCHEMA,
    SCHOLARLY_BUDGET_SCHEMA,
    SCHOLARLY_PLAN_SCHEMA,
    SCHOLARLY_QUERY_SCHEMA,
    SCHOLARLY_QUARANTINE_SCHEMA,
    SCHOLARLY_RECEIPT_SCHEMA,
    SCHOLARLY_REGISTRY_SCHEMA,
    SCHOLARLY_SOURCE_SCHEMA,
    bind_data_record,
    validate_data_record,
)


SCHOLARLY_POLICY_VERSION = "uriel.scholarly_acquisition_policy.v1"
ACQUISITION_ROOT_RELATIVE = Path(".uriel/acquisition")
MOCK_SOURCE_ID = "mock.scholarly-metadata.v1"
DEFAULT_MAX_REQUEST_BYTES = 8192
DEFAULT_MAX_HEADER_BYTES = 16384
DEFAULT_MAX_RESPONSE_BYTES = 1024 * 1024
DEFAULT_TOTAL_TIMEOUT_MS = 10000
DEFAULT_MIN_FREE_DISK_BYTES = 1024 * 1024
MAX_RECORD_NESTING_DEPTH = 64
_REPARSE_POINT = 0x400
_HEADER_NAME = re.compile(r"^[a-z0-9!#$%&'*+.^_`|~-]+$")
_SCENARIO_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_ARCHIVE_SUFFIXES = frozenset({".7z", ".bz2", ".gz", ".rar", ".tar", ".tgz", ".xz", ".zip"})
_BUNDLE_KEYS = frozenset({"registry", "source", "query", "budget", "adapter", "plan"})


@dataclass(frozen=True)
class LocalMockExchange:
    """One injected response transcript; it cannot perform transport itself."""

    scenario_id: str
    simulated_dns_answers: Tuple[str, ...]
    connected_address: str
    peer_hostname: str
    response_status: int
    headers: Tuple[Tuple[str, str], ...]
    body_chunks: Tuple[bytes, ...]
    elapsed_ms: int
    attempt_count: int
    proxy_used: bool
    credentials_used: bool
    background_threads_started: int
    network_calls: int
    resolver_calls: int
    redirect_count: int


class LocalMockTransport:
    """Exact, injected local-fixture transport used only for policy exercises."""

    __slots__ = (
        "_root",
        "_fixture_relative",
        "_expected_request_sha256",
        "_scenario_id",
        "_simulated_dns_answers",
        "_connected_address",
        "_peer_hostname",
        "_response_status",
        "_headers",
        "_elapsed_ms",
        "_attempt_count",
        "_proxy_used",
        "_credentials_used",
        "_background_threads_started",
        "_network_calls",
        "_resolver_calls",
        "_redirect_count",
    )

    def __init__(
        self,
        root: Union[str, Path],
        fixture_relative: str,
        *,
        expected_request_sha256: str,
        scenario_id: str = "local-fixture-v1",
        simulated_dns_answers: Sequence[str] = ("8.8.8.8",),
        connected_address: str = "8.8.8.8",
        peer_hostname: str = "mock.invalid",
        response_status: int = 200,
        headers: Optional[Sequence[Tuple[str, str]]] = None,
        elapsed_ms: int = 1,
        attempt_count: int = 1,
        proxy_used: bool = False,
        credentials_used: bool = False,
        background_threads_started: int = 0,
        network_calls: int = 0,
        resolver_calls: int = 0,
        redirect_count: int = 0,
    ) -> None:
        self._root = os.fspath(root)
        relative = safe_relative_path(fixture_relative)
        if len(relative.parts) < 2 or relative.parts[0].casefold() != "sources":
            raise Refusal(
                "The local mock fixture must be an explicit file beneath the project sources directory.",
                code="SCHOLARLY_FIXTURE_SCOPE_REFUSED",
            )
        self._fixture_relative = relative.as_posix()
        self._expected_request_sha256 = expected_request_sha256
        self._scenario_id = scenario_id
        self._simulated_dns_answers = tuple(simulated_dns_answers)
        self._connected_address = connected_address
        self._peer_hostname = peer_hostname
        self._response_status = response_status
        self._headers = None if headers is None else tuple((str(k), str(v)) for k, v in headers)
        self._elapsed_ms = elapsed_ms
        self._attempt_count = attempt_count
        self._proxy_used = proxy_used
        self._credentials_used = credentials_used
        self._background_threads_started = background_threads_started
        self._network_calls = network_calls
        self._resolver_calls = resolver_calls
        self._redirect_count = redirect_count

    def exchange(self, request_descriptor_sha256: str, budget: Mapping[str, Any]) -> LocalMockExchange:
        if request_descriptor_sha256 != self._expected_request_sha256:
            raise Refusal(
                "The injected local mock is bound to a different request descriptor.",
                code="SCHOLARLY_MOCK_REQUEST_MISMATCH",
            )
        body_chunks = _read_confined_fixture(self._root, self._fixture_relative, budget)
        body_size = sum(len(chunk) for chunk in body_chunks)
        headers = self._headers
        if headers is None:
            headers = (
                ("content-type", "application/json"),
                ("content-length", str(body_size)),
            )
        return LocalMockExchange(
            scenario_id=self._scenario_id,
            simulated_dns_answers=self._simulated_dns_answers,
            connected_address=self._connected_address,
            peer_hostname=self._peer_hostname,
            response_status=self._response_status,
            headers=headers,
            body_chunks=body_chunks,
            elapsed_ms=self._elapsed_ms,
            attempt_count=self._attempt_count,
            proxy_used=self._proxy_used,
            credentials_used=self._credentials_used,
            background_threads_started=self._background_threads_started,
            network_calls=self._network_calls,
            resolver_calls=self._resolver_calls,
            redirect_count=self._redirect_count,
        )


def make_scholarly_budget(
    *,
    max_request_bytes: int = DEFAULT_MAX_REQUEST_BYTES,
    max_header_bytes: int = DEFAULT_MAX_HEADER_BYTES,
    max_response_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    max_quarantine_bytes: int = DEFAULT_MAX_RESPONSE_BYTES,
    total_timeout_ms: int = DEFAULT_TOTAL_TIMEOUT_MS,
    connect_timeout_ms: int = 3000,
    read_timeout_ms: int = 7000,
    max_dns_answers: int = 8,
    min_free_disk_bytes: int = DEFAULT_MIN_FREE_DISK_BYTES,
) -> Dict[str, Any]:
    """Create a bounded budget. Retry, concurrency, and decompression stay fixed."""

    budget = bind_data_record(
        {
            "schema": SCHOLARLY_BUDGET_SCHEMA,
            "schema_version": 1,
            "policy_version": SCHOLARLY_POLICY_VERSION,
            "max_request_bytes": max_request_bytes,
            "max_header_bytes": max_header_bytes,
            "max_response_bytes": max_response_bytes,
            "max_quarantine_bytes": max_quarantine_bytes,
            "total_timeout_ms": total_timeout_ms,
            "connect_timeout_ms": connect_timeout_ms,
            "read_timeout_ms": read_timeout_ms,
            "max_retries": 0,
            "max_dns_answers": max_dns_answers,
            "per_source_concurrency": 1,
            "global_concurrency": 1,
            "min_free_disk_bytes": min_free_disk_bytes,
            "max_decompressed_bytes": 0,
        }
    )
    validate_data_record(budget)
    if max_quarantine_bytes > max_response_bytes:
        raise Refusal(
            "The quarantine ceiling cannot exceed the response ceiling.",
            code="SCHOLARLY_BUDGET_INVALID",
        )
    if connect_timeout_ms > total_timeout_ms or read_timeout_ms > total_timeout_ms:
        raise Refusal(
            "Connect and read ceilings must each fit inside the total ceiling.",
            code="SCHOLARLY_BUDGET_INVALID",
        )
    return budget


def _make_source() -> Dict[str, Any]:
    source = bind_data_record(
        {
            "schema": SCHOLARLY_SOURCE_SCHEMA,
            "schema_version": 1,
            "policy_version": SCHOLARLY_POLICY_VERSION,
            "source_id": MOCK_SOURCE_ID,
            "mode": "TEST_ONLY_LOCAL_MOCK",
            "scheme": "https",
            "hostname": "mock.invalid",
            "port": 443,
            "method": "GET",
            "path": "/v1/works",
            "query_parameter_names": ["max_results", "terms", "year_from", "year_to"],
            "allowed_statuses": [200],
            "allowed_media_types": ["application/json"],
            "license_status": "TEST_FIXTURE_NO_EXTERNAL_RIGHTS_CLAIM",
            "retention_policy": "PROJECT_LOCAL_OPERATOR_CONTROLLED",
            "terms_review_status": "NOT_APPLICABLE_LOCAL_MOCK",
            "live_enabled": False,
            "redirects_enabled": False,
            "authentication_enabled": False,
            "cookies_enabled": False,
            "response_parsing_enabled": False,
        }
    )
    validate_data_record(source)
    return source


def _make_registry(source: Mapping[str, Any]) -> Dict[str, Any]:
    registry = bind_data_record(
        {
            "schema": SCHOLARLY_REGISTRY_SCHEMA,
            "schema_version": 1,
            "policy_version": SCHOLARLY_POLICY_VERSION,
            "registry_id": "uriel-local-mock-registry-v1",
            "status": "TEST_ONLY",
            "live_network_enabled": False,
            "generic_browsing_enabled": False,
            "entries": [
                {
                    "source_id": source["source_id"],
                    "source_record_sha256": source["record_sha256"],
                }
            ],
        }
    )
    validate_data_record(registry)
    return registry


def _make_query(
    terms: Sequence[str],
    year_from: Optional[int],
    year_to: Optional[int],
    max_results: int,
) -> Dict[str, Any]:
    cleaned: List[str] = []
    for term in terms:
        if not isinstance(term, str) or not term or term != term.strip():
            raise Refusal(
                "Each scholarly query term must be a nonblank, already-trimmed string.",
                code="SCHOLARLY_QUERY_INVALID",
            )
        if len(term) > 128 or any(ord(character) < 32 or ord(character) == 127 for character in term):
            raise Refusal(
                "A scholarly query term contains a control character or exceeds 128 characters.",
                code="SCHOLARLY_QUERY_INVALID",
            )
        cleaned.append(term)
    if len(cleaned) != len(set(cleaned)):
        raise Refusal("Duplicate scholarly query terms are refused.", code="SCHOLARLY_QUERY_INVALID")
    query = bind_data_record(
        {
            "schema": SCHOLARLY_QUERY_SCHEMA,
            "schema_version": 1,
            "policy_version": SCHOLARLY_POLICY_VERSION,
            "source_id": MOCK_SOURCE_ID,
            "terms": cleaned,
            "year_from": year_from,
            "year_to": year_to,
            "max_results": max_results,
            "free_form_url_supplied": False,
            "ai_role": "STRUCTURED_FIELDS_ONLY",
            "authority": "NONE",
        }
    )
    validate_data_record(query)
    return query


def _make_adapter() -> Dict[str, Any]:
    adapter = bind_data_record(
        {
            "schema": SCHOLARLY_ADAPTER_SCHEMA,
            "schema_version": 1,
            "policy_version": SCHOLARLY_POLICY_VERSION,
            "adapter_id": "local-mock-in-memory-v1",
            "transport_kind": "LOCAL_MOCK_IN_MEMORY",
            "injected_transport_required": True,
            "default_transport_available": False,
            "network_calls_permitted": 0,
            "resolver_calls_permitted": 0,
            "proxy_use_permitted": False,
            "subprocess_permitted": False,
            "background_threads_permitted": False,
            "credentials_permitted": False,
            "cookies_permitted": False,
            "javascript_permitted": False,
            "decompression_permitted": False,
            "response_parsing_permitted": False,
            "authority": "NONE",
        }
    )
    validate_data_record(adapter)
    return adapter


def _request_descriptor(source: Mapping[str, Any], query: Mapping[str, Any]) -> Dict[str, Any]:
    parameters = [
        {"name": "max_results", "value": str(query["max_results"])},
        {"name": "terms", "value": " | ".join(query["terms"])},
    ]
    if query["year_from"] is not None:
        parameters.append({"name": "year_from", "value": str(query["year_from"])})
    if query["year_to"] is not None:
        parameters.append({"name": "year_to", "value": str(query["year_to"])})
    return {
        "method": source["method"],
        "scheme": source["scheme"],
        "hostname": source["hostname"],
        "port": source["port"],
        "path": source["path"],
        "query_parameters": parameters,
    }


def plan_scholarly_mock(
    root: Union[str, Path],
    terms: Sequence[str],
    *,
    year_from: Optional[int] = None,
    year_to: Optional[int] = None,
    max_results: int = 25,
    acknowledge_local_mock: bool = False,
    budget: Optional[Mapping[str, Any]] = None,
    created_at_utc: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a no-write, no-network plan bound to the fixed local mock source."""

    if not acknowledge_local_mock:
        raise Refusal(
            "Scholarly acquisition is disabled by default; acknowledge the local-mock-only boundary.",
            code="SCHOLARLY_ACQUISITION_DISABLED",
            repairs=[
                "Use the local mock only after reviewing that it reads one confined project fixture.",
                "Do not treat the mock as a live scholarly source or network firewall.",
                "Keep real acquisition outside Uriel until a separately reviewed adapter ships.",
            ],
        )
    paths = paths_for(root)
    source = _make_source()
    registry = _make_registry(source)
    query = _make_query(terms, year_from, year_to, max_results)
    selected_budget = dict(budget) if budget is not None else make_scholarly_budget()
    validate_data_record(selected_budget)
    if selected_budget.get("schema") != SCHOLARLY_BUDGET_SCHEMA:
        raise Refusal("A scholarly v1 resource budget is required.", code="SCHOLARLY_BUDGET_INVALID")
    adapter = _make_adapter()
    request = _request_descriptor(source, query)
    if len(canonical_json_bytes(request)) > int(selected_budget["max_request_bytes"]):
        raise Refusal("The canonical request exceeds its bound.", code="SCHOLARLY_REQUEST_BUDGET")
    plan = bind_data_record(
        {
            "schema": SCHOLARLY_PLAN_SCHEMA,
            "schema_version": 1,
            "created_at_utc": created_at_utc or utc_now(),
            "policy_version": SCHOLARLY_POLICY_VERSION,
            "project_binding_sha256": sha256_file(paths.project),
            "registry_record_sha256": registry["record_sha256"],
            "source_record_sha256": source["record_sha256"],
            "query_record_sha256": query["record_sha256"],
            "budget_record_sha256": selected_budget["record_sha256"],
            "adapter_record_sha256": adapter["record_sha256"],
            "source_id": source["source_id"],
            "request_descriptor": request,
            "request_descriptor_sha256": sha256_text(canonical_json(request)),
            "consent": "EXPLICIT_LOCAL_MOCK_ONLY",
            "mode": "DRY_RUN_LOCAL_MOCK",
            "network_permitted": False,
            "writes_performed": False,
            "planned_quarantine_schema": SCHOLARLY_QUARANTINE_SCHEMA,
            "planned_receipt_schema": SCHOLARLY_RECEIPT_SCHEMA,
            "authority": "NONE",
        }
    )
    validate_data_record(plan)
    return {
        "registry": registry,
        "source": source,
        "query": query,
        "budget": selected_budget,
        "adapter": adapter,
        "plan": plan,
    }


def _strict_pairs(pairs: Sequence[Tuple[str, Any]]) -> Dict[str, Any]:
    value: Dict[str, Any] = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key: {0}".format(key))
        value[key] = item
    return value


def _reject_json_constant(value: str) -> None:
    raise ValueError("non-finite JSON number: {0}".format(value))


def _assert_json_depth(value: Any, maximum: int = MAX_RECORD_NESTING_DEPTH) -> None:
    stack: List[Tuple[Any, int]] = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        if depth > maximum:
            raise Refusal(
                "A scholarly acquisition record exceeds the JSON nesting ceiling.",
                code="SCHOLARLY_RECORD_UNREADABLE",
            )
        if isinstance(current, Mapping):
            stack.extend((child, depth + 1) for child in current.values())
        elif isinstance(current, list):
            stack.extend((child, depth + 1) for child in current)


def _strict_json_loads(raw: bytes) -> Dict[str, Any]:
    try:
        text = raw.decode("utf-8")
        value = json.loads(
            text,
            object_pairs_hook=_strict_pairs,
            parse_constant=_reject_json_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise Refusal(
            "A scholarly acquisition record is not strict UTF-8 JSON.",
            code="SCHOLARLY_RECORD_UNREADABLE",
            details={"error_type": type(exc).__name__},
        ) from exc
    if not isinstance(value, dict):
        raise Refusal(
            "A scholarly acquisition record must contain one JSON object.",
            code="SCHOLARLY_RECORD_OBJECT_REQUIRED",
        )
    _assert_json_depth(value)
    return value


def _regular_file(path: Path) -> bool:
    try:
        observed = os.lstat(str(path))
    except OSError:
        return False
    return bool(
        stat.S_ISREG(observed.st_mode)
        and not stat.S_ISLNK(observed.st_mode)
        and not (getattr(observed, "st_file_attributes", 0) & _REPARSE_POINT)
    )


def _ensure_directory(root: Path, directory: Path) -> Path:
    target = guard_path(root, directory)
    if _path_contains_indirection(root, target):
        raise Refusal(
            "The scholarly acquisition store crosses filesystem indirection.",
            code="SCHOLARLY_STORAGE_PATH_REFUSED",
        )
    target.mkdir(parents=True, exist_ok=True)
    target = guard_path(root, target, must_exist=True)
    if _path_contains_indirection(root, target) or not target.is_dir():
        raise Refusal(
            "The scholarly acquisition store is not a normal directory.",
            code="SCHOLARLY_STORAGE_PATH_REFUSED",
        )
    return target


def _write_immutable_bytes(root: Path, target: Path, data: bytes) -> bool:
    parent = _ensure_directory(root, target.parent)
    target = guard_path(root, target)
    temporary = guard_path(root, parent / ("." + target.name + ".tmp." + uuid.uuid4().hex))
    descriptor = None
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0)
        descriptor = os.open(str(temporary), flags, 0o600)
        with os.fdopen(descriptor, "wb", closefd=True) as handle:
            descriptor = None
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(str(temporary), str(target))
            return True
        except FileExistsError:
            existing = guard_path(root, target, must_exist=True)
            existing_bytes = _read_regular_bounded(
                root,
                existing,
                len(data),
                failure_code="SCHOLARLY_IMMUTABLE_COLLISION",
                limit_code="SCHOLARLY_IMMUTABLE_COLLISION",
                message="An immutable scholarly acquisition path contains different bytes.",
            )
            if existing_bytes != data:
                raise Refusal(
                    "An immutable scholarly acquisition path contains different bytes.",
                    code="SCHOLARLY_IMMUTABLE_COLLISION",
                )
            return False
        except OSError as exc:
            raise Refusal(
                "Uriel could not atomically publish an immutable scholarly record.",
                code="SCHOLARLY_STORAGE_WRITE_FAILED",
                details={"error_type": type(exc).__name__},
            ) from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


def _write_record(root: Path, relative: Path, record: Mapping[str, Any]) -> bool:
    validate_data_record(record)
    return _write_immutable_bytes(root, root / relative, canonical_json_bytes(record))


def _read_record(root: Path, relative: Path, expected_schema: str) -> Dict[str, Any]:
    try:
        target = guard_path(root, root / relative, must_exist=True)
    except Refusal as exc:
        raise Refusal(
            "The selected scholarly acquisition record is not a regular file.",
            code="SCHOLARLY_RECORD_FILE_REFUSED",
        ) from exc
    raw = _read_regular_bounded(
        root,
        target,
        MAX_RECORD_FILE_BYTES,
        failure_code="SCHOLARLY_RECORD_UNREADABLE",
        limit_code="SCHOLARLY_RECORD_FILE_REFUSED",
        message="The selected scholarly record could not be read safely.",
    )
    value = _strict_json_loads(raw)
    if value.get("schema") != expected_schema:
        raise Refusal(
            "The selected scholarly record has the wrong schema.",
            code="SCHOLARLY_RECORD_SCHEMA_MISMATCH",
        )
    validate_data_record(value)
    return value


def _record_relative(kind: str, digest: str) -> Path:
    if kind == "plan":
        return ACQUISITION_ROOT_RELATIVE / "plans" / (digest + ".json")
    if kind == "quarantine":
        return ACQUISITION_ROOT_RELATIVE / "records" / "quarantine" / (digest + ".json")
    return ACQUISITION_ROOT_RELATIVE / "records" / kind / (digest + ".json")


def _quarantine_relative(content_sha256: str) -> Path:
    return (
        ACQUISITION_ROOT_RELATIVE
        / "quarantine"
        / "sha256"
        / content_sha256[:2]
        / content_sha256
    )


def _receipt_relative(receipt_sha256: str) -> Path:
    return ACQUISITION_ROOT_RELATIVE / "receipts" / (receipt_sha256 + ".json")


def _same_identity(first: os.stat_result, second: os.stat_result) -> bool:
    first_id = (getattr(first, "st_dev", 0), getattr(first, "st_ino", 0))
    second_id = (getattr(second, "st_dev", 0), getattr(second, "st_ino", 0))
    identity_matches = first_id != (0, 0) and second_id != (0, 0) and first_id == second_id
    return bool(
        identity_matches
        and first.st_size == second.st_size
        and getattr(first, "st_mtime_ns", 0) == getattr(second, "st_mtime_ns", 0)
    )


def _path_contains_indirection(root: Path, target: Path) -> bool:
    try:
        relative = target.relative_to(root)
    except ValueError:
        return True
    current = root
    for part in relative.parts:
        current = current / part
        try:
            observed = os.lstat(str(current))
        except FileNotFoundError:
            continue
        except OSError:
            return True
        if stat.S_ISLNK(observed.st_mode) or bool(
            getattr(observed, "st_file_attributes", 0) & _REPARSE_POINT
        ):
            return True
    return False


def _read_regular_bounded(
    root: Path,
    target: Path,
    maximum_bytes: int,
    *,
    failure_code: str,
    limit_code: str,
    message: str,
) -> bytes:
    if _path_contains_indirection(root, target):
        raise Refusal(message, code=failure_code)
    try:
        before = os.lstat(str(target))
    except OSError as exc:
        raise Refusal(message, code=failure_code, details={"error_type": type(exc).__name__}) from exc
    if not _regular_file(target):
        raise Refusal(message, code=failure_code)
    if before.st_size > maximum_bytes:
        raise Refusal(
            "The selected scholarly file exceeds its byte ceiling.",
            code=limit_code,
            details={"size_bytes": before.st_size, "max_bytes": maximum_bytes},
        )
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NOFOLLOW", 0)
    try:
        descriptor = os.open(str(target), flags)
    except OSError as exc:
        raise Refusal(message, code=failure_code, details={"error_type": type(exc).__name__}) from exc
    chunks: List[bytes] = []
    total = 0
    try:
        with os.fdopen(descriptor, "rb", closefd=True) as handle:
            opened = os.fstat(handle.fileno())
            if (
                not stat.S_ISREG(opened.st_mode)
                or bool(getattr(opened, "st_file_attributes", 0) & _REPARSE_POINT)
                or not _same_identity(before, opened)
            ):
                raise Refusal(message, code=failure_code)
            while True:
                block = handle.read(min(64 * 1024, maximum_bytes - total + 1))
                if not block:
                    break
                total += len(block)
                if total > maximum_bytes:
                    raise Refusal(
                        "The selected scholarly file exceeded its byte ceiling while being read.",
                        code=limit_code,
                    )
                chunks.append(block)
    except Refusal:
        raise
    except OSError as exc:
        raise Refusal(message, code=failure_code, details={"error_type": type(exc).__name__}) from exc
    try:
        after = os.lstat(str(target))
    except OSError as exc:
        raise Refusal(message, code=failure_code, details={"error_type": type(exc).__name__}) from exc
    if (
        _path_contains_indirection(root, target)
        or not _same_identity(before, after)
        or total != before.st_size
    ):
        raise Refusal(message, code=failure_code)
    return b"".join(chunks)


def _read_confined_fixture(
    root: Union[str, Path],
    fixture_relative: str,
    budget: Mapping[str, Any],
) -> Tuple[bytes, ...]:
    paths = paths_for(root)
    relative = safe_relative_path(fixture_relative)
    if len(relative.parts) < 2 or relative.parts[0].casefold() != "sources":
        raise Refusal(
            "The local mock fixture must remain beneath the project sources directory.",
            code="SCHOLARLY_FIXTURE_SCOPE_REFUSED",
        )
    if relative.suffix.lower() in _ARCHIVE_SUFFIXES:
        raise Refusal(
            "Archive fixtures are refused; the local mock never decompresses content.",
            code="SCHOLARLY_FIXTURE_ARCHIVE_REFUSED",
        )
    try:
        target = guard_path(paths.root, paths.root / relative, must_exist=True)
    except Refusal as exc:
        refusal_code = (
            "SCHOLARLY_FIXTURE_TYPE_REFUSED"
            if exc.code == "LINK_TRAVERSAL_REFUSAL"
            else "SCHOLARLY_FIXTURE_UNREADABLE"
        )
        raise Refusal(
            "The local mock fixture is missing, outside its scope, or crosses filesystem indirection.",
            code=refusal_code,
            details={"cause_code": exc.code},
        ) from exc
    ceiling = min(int(budget["max_response_bytes"]), int(budget["max_quarantine_bytes"]))
    body = _read_regular_bounded(
        paths.root,
        target,
        ceiling,
        failure_code="SCHOLARLY_FIXTURE_TYPE_REFUSED",
        limit_code="SCHOLARLY_RESPONSE_BUDGET",
        message="The local mock fixture could not be read as one stable, confined regular file.",
    )
    return (body,)


def _validate_bundle(
    root: Union[str, Path],
    bundle: Mapping[str, Any],
    *,
    require_current_project: bool,
) -> Tuple[Dict[str, Dict[str, Any]], bool]:
    if not isinstance(bundle, Mapping) or set(bundle) != set(_BUNDLE_KEYS):
        raise Refusal(
            "The scholarly mock bundle must contain exactly six bound records.",
            code="SCHOLARLY_BUNDLE_INVALID",
        )
    expected = {
        "registry": SCHOLARLY_REGISTRY_SCHEMA,
        "source": SCHOLARLY_SOURCE_SCHEMA,
        "query": SCHOLARLY_QUERY_SCHEMA,
        "budget": SCHOLARLY_BUDGET_SCHEMA,
        "adapter": SCHOLARLY_ADAPTER_SCHEMA,
        "plan": SCHOLARLY_PLAN_SCHEMA,
    }
    records: Dict[str, Dict[str, Any]] = {}
    for key in sorted(expected):
        candidate = bundle[key]
        if not isinstance(candidate, Mapping):
            raise Refusal("A scholarly bundle member is not an object.", code="SCHOLARLY_BUNDLE_INVALID")
        record = dict(candidate)
        if record.get("schema") != expected[key]:
            raise Refusal("A scholarly bundle member has the wrong schema.", code="SCHOLARLY_BUNDLE_INVALID")
        validate_data_record(record)
        records[key] = record
    source = records["source"]
    registry = records["registry"]
    query = records["query"]
    budget = records["budget"]
    adapter = records["adapter"]
    plan = records["plan"]
    expected_entry = {
        "source_id": source["source_id"],
        "source_record_sha256": source["record_sha256"],
    }
    if registry["entries"] != [expected_entry]:
        raise Refusal("The registry does not bind the exact mock source.", code="SCHOLARLY_REGISTRY_BINDING_INVALID")
    if query["source_id"] != source["source_id"] or plan["source_id"] != source["source_id"]:
        raise Refusal("The source ID binding is inconsistent.", code="SCHOLARLY_PLAN_BINDING_INVALID")
    bindings = {
        "registry_record_sha256": registry["record_sha256"],
        "source_record_sha256": source["record_sha256"],
        "query_record_sha256": query["record_sha256"],
        "budget_record_sha256": budget["record_sha256"],
        "adapter_record_sha256": adapter["record_sha256"],
    }
    if any(plan.get(key) != digest for key, digest in bindings.items()):
        raise Refusal("The acquisition plan has a stale component binding.", code="SCHOLARLY_PLAN_BINDING_INVALID")
    request = _request_descriptor(source, query)
    request_sha256 = sha256_text(canonical_json(request))
    if plan["request_descriptor"] != request or plan["request_descriptor_sha256"] != request_sha256:
        raise Refusal("The acquisition request descriptor does not recompute.", code="SCHOLARLY_REQUEST_BINDING_INVALID")
    if len(canonical_json_bytes(request)) > int(budget["max_request_bytes"]):
        raise Refusal("The canonical request exceeds the bound plan.", code="SCHOLARLY_REQUEST_BUDGET")
    if int(budget["max_quarantine_bytes"]) > int(budget["max_response_bytes"]):
        raise Refusal("The quarantine budget exceeds the response budget.", code="SCHOLARLY_BUDGET_INVALID")
    paths = paths_for(root)
    project_current = sha256_file(paths.project) == plan["project_binding_sha256"]
    if require_current_project and not project_current:
        raise Refusal(
            "The project record changed after the scholarly mock plan was created.",
            code="SCHOLARLY_PLAN_PROJECT_STALE",
        )
    return records, project_current


def _validate_addresses(exchange: LocalMockExchange, budget: Mapping[str, Any]) -> None:
    answers = exchange.simulated_dns_answers
    if not answers or len(answers) > int(budget["max_dns_answers"]) or len(answers) != len(set(answers)):
        raise Refusal("The simulated resolver answer set is invalid.", code="SCHOLARLY_DNS_POLICY")
    normalized: List[str] = []
    for text in answers:
        if "%" in text:
            raise Refusal("Scoped addresses are refused.", code="SCHOLARLY_SSRF_REFUSED")
        try:
            address = ipaddress.ip_address(text)
        except ValueError as exc:
            raise Refusal("A simulated resolver answer is invalid.", code="SCHOLARLY_DNS_POLICY") from exc
        if not address.is_global:
            raise Refusal(
                "A simulated resolver answer is not globally routable.",
                code="SCHOLARLY_SSRF_REFUSED",
                details={"address": text},
            )
        normalized.append(str(address))
    try:
        connected = str(ipaddress.ip_address(exchange.connected_address))
    except ValueError as exc:
        raise Refusal("The simulated peer address is invalid.", code="SCHOLARLY_DNS_POLICY") from exc
    if connected not in normalized:
        raise Refusal(
            "The simulated connected peer is outside the pinned answer set.",
            code="SCHOLARLY_DNS_REBINDING_REFUSED",
        )


def _validate_headers(
    headers: Sequence[Tuple[str, str]],
    budget: Mapping[str, Any],
    body_size: int,
) -> Tuple[List[Dict[str, str]], str]:
    values: Dict[str, str] = {}
    total = 0
    for name, value in headers:
        if name != name.lower() or _HEADER_NAME.fullmatch(name) is None:
            raise Refusal("A response header name is malformed or ambiguous.", code="SCHOLARLY_HEADER_REFUSED")
        if name in values:
            raise Refusal("Duplicate response headers are refused.", code="SCHOLARLY_HEADER_REFUSED")
        if value != value.strip() or any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise Refusal("A response header value is malformed.", code="SCHOLARLY_HEADER_REFUSED")
        total += len(name.encode("ascii")) + len(value.encode("utf-8")) + 4
        if total > int(budget["max_header_bytes"]):
            raise Refusal("Response headers exceed their byte ceiling.", code="SCHOLARLY_HEADER_BUDGET")
        values[name] = value
    if set(values) - {"content-type", "content-length", "content-encoding"}:
        raise Refusal("An undeclared response header is refused.", code="SCHOLARLY_HEADER_REFUSED")
    if values.get("content-type") != "application/json":
        raise Refusal("The response media type is outside the source policy.", code="SCHOLARLY_CONTENT_TYPE_REFUSED")
    length = values.get("content-length", "")
    if re.fullmatch(r"[0-9]+", length) is None or int(length) != body_size:
        raise Refusal("Content-Length is missing, malformed, or inconsistent.", code="SCHOLARLY_CONTENT_LENGTH_REFUSED")
    if values.get("content-encoding", "identity") != "identity":
        raise Refusal("Compressed responses are refused.", code="SCHOLARLY_CONTENT_ENCODING_REFUSED")
    canonical_headers = [{"name": name, "value": values[name]} for name in sorted(values)]
    return canonical_headers, sha256_text(canonical_json(canonical_headers))


def _validate_exchange(
    exchange: LocalMockExchange,
    source: Mapping[str, Any],
    budget: Mapping[str, Any],
) -> Tuple[bytes, str, Dict[str, Any]]:
    if type(exchange) is not LocalMockExchange:
        raise Refusal("The local mock returned an unknown exchange type.", code="SCHOLARLY_TRANSPORT_REFUSED")
    if _SCENARIO_ID.fullmatch(exchange.scenario_id) is None:
        raise Refusal("The local mock scenario ID is invalid.", code="SCHOLARLY_TRANSPORT_REFUSED")
    if exchange.peer_hostname != source["hostname"]:
        raise Refusal("The simulated peer hostname changed.", code="SCHOLARLY_HOST_REFUSED")
    _validate_addresses(exchange, budget)
    if exchange.response_status not in source["allowed_statuses"]:
        code = "SCHOLARLY_REDIRECT_REFUSED" if 300 <= exchange.response_status < 400 else "SCHOLARLY_STATUS_REFUSED"
        raise Refusal("The response status is outside the source policy.", code=code)
    if exchange.attempt_count != 1:
        raise Refusal("Retries are disabled for the local mock.", code="SCHOLARLY_RETRY_REFUSED")
    if (
        not isinstance(exchange.elapsed_ms, int)
        or isinstance(exchange.elapsed_ms, bool)
        or exchange.elapsed_ms < 0
        or exchange.elapsed_ms > int(budget["total_timeout_ms"])
    ):
        raise Refusal("The local mock exceeded its total time ceiling.", code="SCHOLARLY_TIMEOUT")
    if exchange.redirect_count != 0:
        raise Refusal("Redirects are disabled.", code="SCHOLARLY_REDIRECT_REFUSED")
    if (
        exchange.proxy_used
        or exchange.credentials_used
        or exchange.background_threads_started != 0
        or exchange.network_calls != 0
        or exchange.resolver_calls != 0
    ):
        raise Refusal(
            "The local mock transcript claims forbidden ambient authority.",
            code="SCHOLARLY_TRANSPORT_AUTHORITY_REFUSED",
        )
    body_parts: List[bytes] = []
    body_size = 0
    ceiling = min(int(budget["max_response_bytes"]), int(budget["max_quarantine_bytes"]))
    for chunk in exchange.body_chunks:
        if type(chunk) is not bytes:
            raise Refusal("The local mock emitted a non-byte body chunk.", code="SCHOLARLY_BODY_REFUSED")
        body_size += len(chunk)
        if body_size > ceiling:
            raise Refusal("The response exceeded its cumulative byte ceiling.", code="SCHOLARLY_RESPONSE_BUDGET")
        body_parts.append(chunk)
    canonical_headers, headers_sha256 = _validate_headers(exchange.headers, budget, body_size)
    body = b"".join(body_parts)
    trace = {
        "scenario_id": exchange.scenario_id,
        "simulated_dns_answers": list(exchange.simulated_dns_answers),
        "connected_address": exchange.connected_address,
        "peer_hostname": exchange.peer_hostname,
        "attempt_count": exchange.attempt_count,
        "elapsed_ms": exchange.elapsed_ms,
        "response_status": exchange.response_status,
        "response_headers": canonical_headers,
        "headers_sha256": headers_sha256,
        "body_content_sha256": sha256_bytes(body),
        "body_size_bytes": body_size,
        "proxy_used": exchange.proxy_used,
        "credentials_used": exchange.credentials_used,
        "background_threads_started": exchange.background_threads_started,
        "network_calls": exchange.network_calls,
        "resolver_calls": exchange.resolver_calls,
        "redirect_count": exchange.redirect_count,
    }
    return body, headers_sha256, trace


def _verified_quarantine_bytes(
    root: Path,
    relative: Path,
    expected_sha256: str,
    expected_size: int,
) -> bytes:
    try:
        target = guard_path(root, root / relative, must_exist=True)
    except Refusal as exc:
        raise Refusal(
            "The quarantined scholarly body is missing or outside the project.",
            code="SCHOLARLY_QUARANTINE_TAMPERED",
        ) from exc
    body = _read_regular_bounded(
        root,
        target,
        expected_size,
        failure_code="SCHOLARLY_QUARANTINE_TAMPERED",
        limit_code="SCHOLARLY_QUARANTINE_TAMPERED",
        message="The quarantined scholarly body could not be verified safely.",
    )
    if sha256_bytes(body) != expected_sha256 or len(body) != expected_size:
        raise Refusal(
            "The quarantined scholarly body no longer matches its content address.",
            code="SCHOLARLY_QUARANTINE_TAMPERED",
        )
    return body


def execute_scholarly_mock(
    root: Union[str, Path],
    bundle: Mapping[str, Any],
    transport: LocalMockTransport,
) -> Dict[str, Any]:
    """Execute one exact local mock, quarantine bytes, and publish receipt last."""

    if type(transport) is not LocalMockTransport:
        raise Refusal(
            "R2.1 accepts only the exact injected LocalMockTransport type.",
            code="SCHOLARLY_TRANSPORT_REFUSED",
        )
    records, _ = _validate_bundle(root, bundle, require_current_project=True)
    paths = paths_for(root)
    try:
        transport_root = paths_for(transport._root).root
    except Refusal as exc:
        raise Refusal(
            "The injected local mock is not bound to the execution project.",
            code="SCHOLARLY_TRANSPORT_ROOT_MISMATCH",
        ) from exc
    if transport_root != paths.root:
        raise Refusal(
            "The injected local mock is bound to a different project root.",
            code="SCHOLARLY_TRANSPORT_ROOT_MISMATCH",
        )
    budget = records["budget"]
    required_free = (
        int(budget["max_quarantine_bytes"])
        + int(budget["min_free_disk_bytes"])
        + 256 * 1024
    )
    available_free = shutil.disk_usage(str(paths.root)).free
    if available_free < required_free:
        raise Refusal(
            "The project volume lacks space for quarantine plus its safety reserve.",
            code="SCHOLARLY_DISK_SPACE",
            details={"required_bytes": required_free, "available_bytes": available_free},
        )

    plan = records["plan"]
    exchange = transport.exchange(plan["request_descriptor_sha256"], budget)
    body, headers_sha256, trace = _validate_exchange(exchange, records["source"], budget)
    content_sha256 = sha256_bytes(body)
    quarantine_relative = _quarantine_relative(content_sha256)
    quarantine = bind_data_record(
        {
            "schema": SCHOLARLY_QUARANTINE_SCHEMA,
            "schema_version": 1,
            "created_at_utc": plan["created_at_utc"],
            "policy_version": SCHOLARLY_POLICY_VERSION,
            "plan_record_sha256": plan["record_sha256"],
            "request_descriptor_sha256": plan["request_descriptor_sha256"],
            "source_id": plan["source_id"],
            "mock_scenario_id": trace["scenario_id"],
            "response_status": trace["response_status"],
            "media_type": "application/json",
            "response_headers": trace["response_headers"],
            "headers_sha256": headers_sha256,
            "body_content_sha256": content_sha256,
            "body_size_bytes": len(body),
            "managed_relative_path": quarantine_relative.as_posix(),
            "complete": True,
            "raw_untrusted": True,
            "parsed": False,
            "decoded": False,
            "instructions_followed": False,
            "immutable": True,
        }
    )
    validate_data_record(quarantine)

    for kind in ("source", "registry", "query", "budget", "adapter", "plan"):
        record = records[kind]
        _write_record(
            paths.root,
            _record_relative(kind, str(record["record_sha256"])),
            record,
        )
    _write_immutable_bytes(paths.root, paths.root / quarantine_relative, body)
    quarantine_record_relative = _record_relative(
        "quarantine", str(quarantine["record_sha256"])
    )
    _write_record(paths.root, quarantine_record_relative, quarantine)
    _verified_quarantine_bytes(paths.root, quarantine_relative, content_sha256, len(body))

    receipt = bind_data_record(
        {
            "schema": SCHOLARLY_RECEIPT_SCHEMA,
            "schema_version": 1,
            "created_at_utc": plan["created_at_utc"],
            "policy_version": SCHOLARLY_POLICY_VERSION,
            "plan_record_sha256": plan["record_sha256"],
            "registry_record_sha256": records["registry"]["record_sha256"],
            "source_record_sha256": records["source"]["record_sha256"],
            "query_record_sha256": records["query"]["record_sha256"],
            "budget_record_sha256": records["budget"]["record_sha256"],
            "adapter_record_sha256": records["adapter"]["record_sha256"],
            "request_descriptor_sha256": plan["request_descriptor_sha256"],
            "quarantine_record_sha256": quarantine["record_sha256"],
            "body_content_sha256": content_sha256,
            "body_size_bytes": len(body),
            "managed_relative_path": quarantine_relative.as_posix(),
            "mock_trace": trace,
            "decision": "PASS_LOCAL_MOCK",
            "independent_quarantine_verification": "PASS",
            "quarantine_complete": True,
            "network_permitted": False,
            "live_adapter_enabled": False,
            "parsed": False,
            "readiness_authority_granted": False,
            "gate_authority_granted": False,
            "publication_authority_granted": False,
            "blessing_authority_granted": False,
        }
    )
    validate_data_record(receipt)
    receipt_relative = _receipt_relative(str(receipt["record_sha256"]))
    verification = _verify_scholarly_receipt(paths.root, receipt_relative, receipt)
    receipt_created = _write_record(paths.root, receipt_relative, receipt)
    return {
        "status": "SEALED" if receipt_created else "ALREADY_SEALED",
        "decision": receipt["decision"],
        "receipt_relative_path": receipt_relative.as_posix(),
        "receipt_record_sha256": receipt["record_sha256"],
        "quarantine_record_relative_path": quarantine_record_relative.as_posix(),
        "managed_relative_path": quarantine_relative.as_posix(),
        "body_content_sha256": content_sha256,
        "body_size_bytes": len(body),
        "network_calls": 0,
        "resolver_calls": 0,
        "parsed": False,
        "source_path_disclosed": False,
        "authority_granted": False,
        "verification": {
            "verified": verification["verified"],
            "decision": verification["decision"],
        },
    }


def _verify_scholarly_receipt(
    root: Union[str, Path],
    receipt_relative: Path,
    receipt_value: Mapping[str, Any],
) -> Dict[str, Any]:
    """Verify an in-memory receipt against independently re-read sealed state."""

    paths = paths_for(root)
    receipt = dict(receipt_value)
    validate_data_record(receipt)
    expected_receipt_relative = _receipt_relative(str(receipt["record_sha256"]))
    if receipt_relative != expected_receipt_relative:
        raise Refusal(
            "The scholarly receipt is not stored at its content-addressed path.",
            code="SCHOLARLY_RECEIPT_PATH_INVALID",
        )

    component_specs = {
        "registry": ("registry", SCHOLARLY_REGISTRY_SCHEMA, "registry_record_sha256"),
        "source": ("source", SCHOLARLY_SOURCE_SCHEMA, "source_record_sha256"),
        "query": ("query", SCHOLARLY_QUERY_SCHEMA, "query_record_sha256"),
        "budget": ("budget", SCHOLARLY_BUDGET_SCHEMA, "budget_record_sha256"),
        "adapter": ("adapter", SCHOLARLY_ADAPTER_SCHEMA, "adapter_record_sha256"),
        "plan": ("plan", SCHOLARLY_PLAN_SCHEMA, "plan_record_sha256"),
    }
    bundle: Dict[str, Dict[str, Any]] = {}
    for key, (kind, schema_id, receipt_field) in component_specs.items():
        digest = str(receipt[receipt_field])
        record = _read_record(paths.root, _record_relative(kind, digest), schema_id)
        if record.get("record_sha256") != digest:
            raise Refusal(
                "A scholarly receipt component no longer matches its binding.",
                code="SCHOLARLY_RECEIPT_BINDING_INVALID",
            )
        bundle[key] = record
    records, project_binding_current = _validate_bundle(
        paths.root,
        bundle,
        require_current_project=False,
    )
    plan = records["plan"]
    quarantine_digest = str(receipt["quarantine_record_sha256"])
    quarantine = _read_record(
        paths.root,
        _record_relative("quarantine", quarantine_digest),
        SCHOLARLY_QUARANTINE_SCHEMA,
    )
    if quarantine["record_sha256"] != quarantine_digest:
        raise Refusal(
            "The quarantine record does not match the receipt.",
            code="SCHOLARLY_RECEIPT_BINDING_INVALID",
        )
    expected_quarantine_relative = _quarantine_relative(str(receipt["body_content_sha256"]))
    binding_checks = {
        "plan": quarantine["plan_record_sha256"] == plan["record_sha256"],
        "request": quarantine["request_descriptor_sha256"] == plan["request_descriptor_sha256"]
        and receipt["request_descriptor_sha256"] == plan["request_descriptor_sha256"],
        "body_hash": quarantine["body_content_sha256"] == receipt["body_content_sha256"],
        "body_size": quarantine["body_size_bytes"] == receipt["body_size_bytes"],
        "path": quarantine["managed_relative_path"] == expected_quarantine_relative.as_posix()
        and receipt["managed_relative_path"] == expected_quarantine_relative.as_posix(),
        "headers": quarantine["headers_sha256"] == receipt["mock_trace"]["headers_sha256"]
        and quarantine["response_headers"] == receipt["mock_trace"]["response_headers"],
        "scenario": quarantine["mock_scenario_id"] == receipt["mock_trace"]["scenario_id"],
        "status": quarantine["response_status"] == receipt["mock_trace"]["response_status"],
    }
    failed = sorted(name for name, passed in binding_checks.items() if not passed)
    if failed:
        raise Refusal(
            "The scholarly receipt and quarantine bindings are inconsistent.",
            code="SCHOLARLY_RECEIPT_BINDING_INVALID",
            details={"failed_checks": failed},
        )

    body = _verified_quarantine_bytes(
        paths.root,
        expected_quarantine_relative,
        str(receipt["body_content_sha256"]),
        int(receipt["body_size_bytes"]),
    )
    trace = receipt["mock_trace"]
    header_pairs = tuple(
        (str(row["name"]), str(row["value"])) for row in trace["response_headers"]
    )
    reconstructed = LocalMockExchange(
        scenario_id=str(trace["scenario_id"]),
        simulated_dns_answers=tuple(str(item) for item in trace["simulated_dns_answers"]),
        connected_address=str(trace["connected_address"]),
        peer_hostname=str(trace["peer_hostname"]),
        response_status=int(trace["response_status"]),
        headers=header_pairs,
        body_chunks=(body,),
        elapsed_ms=int(trace["elapsed_ms"]),
        attempt_count=int(trace["attempt_count"]),
        proxy_used=bool(trace["proxy_used"]),
        credentials_used=bool(trace["credentials_used"]),
        background_threads_started=int(trace["background_threads_started"]),
        network_calls=int(trace["network_calls"]),
        resolver_calls=int(trace["resolver_calls"]),
        redirect_count=int(trace["redirect_count"]),
    )
    recomputed_body, recomputed_headers_sha256, recomputed_trace = _validate_exchange(
        reconstructed,
        records["source"],
        records["budget"],
    )
    if (
        recomputed_body != body
        or recomputed_headers_sha256 != quarantine["headers_sha256"]
        or recomputed_trace != trace
    ):
        raise Refusal(
            "The local mock policy transcript does not recompute.",
            code="SCHOLARLY_TRACE_INVALID",
        )
    return {
        "verified": True,
        "decision": "PASS_LOCAL_MOCK",
        "receipt": receipt,
        "receipt_relative_path": receipt_relative.as_posix(),
        "managed_relative_path": expected_quarantine_relative.as_posix(),
        "body_content_sha256": receipt["body_content_sha256"],
        "body_size_bytes": receipt["body_size_bytes"],
        "project_binding_current": project_binding_current,
        "network_calls": 0,
        "resolver_calls": 0,
        "transport_invoked": False,
        "parsed": False,
        "authority_granted": False,
    }


def verify_scholarly_mock(
    root: Union[str, Path],
    receipt_path: str,
) -> Dict[str, Any]:
    """Offline verifier for records, policy transcript, and quarantined bytes."""

    paths = paths_for(root)
    receipt_relative = safe_relative_path(receipt_path)
    receipt = _read_record(paths.root, receipt_relative, SCHOLARLY_RECEIPT_SCHEMA)
    return _verify_scholarly_receipt(paths.root, receipt_relative, receipt)
