"""Dependency-free structural validation for ``uriel.project.json``.

The package also ships JSON Schema documents for editors.  Runtime validation
uses the standard library so Uriel remains useful on an offline machine with a
stock Python installation.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple

from .core import PROJECT_SCHEMA, load_project, safe_relative_path

_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_REQUIRED_TOP = (
    "schema",
    "schema_version",
    "project_id",
    "title",
    "kind",
    "question",
    "hypothesis",
    "framing_review",
    "novelty_review",
    "claims",
    "evidence",
    "methods",
    "assumptions",
    "alternative_explanations",
    "contradictions",
    "adversarial_tests",
    "reviewer_objections",
    "limitations",
    "ethics",
    "disclosures",
    "submission",
    "privacy",
    "workloads",
    "external_reviews",
    "waivers",
)


def _add(errors: List[Dict[str, str]], path: str, message: str) -> None:
    errors.append({"path": path, "message": message})


def _mapping(errors: List[Dict[str, str]], value: Any, path: str) -> Optional[Mapping[str, Any]]:
    if not isinstance(value, Mapping):
        _add(errors, path, "must be a JSON object")
        return None
    return value


def _array(errors: List[Dict[str, str]], value: Any, path: str) -> Optional[Sequence[Any]]:
    if not isinstance(value, list):
        _add(errors, path, "must be a JSON array")
        return None
    return value


def _text(errors: List[Dict[str, str]], value: Any, path: str, minimum: int = 0) -> None:
    if not isinstance(value, str):
        _add(errors, path, "must be text")
    elif len(value.strip()) < minimum:
        _add(errors, path, "must contain at least {0} non-space characters".format(minimum))


def _identifier(errors: List[Dict[str, str]], value: Any, path: str) -> Optional[str]:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        _add(errors, path, "must be a portable identifier: letters, numbers, dot, underscore, or hyphen")
        return None
    return value


def _id_objects(
    errors: List[Dict[str, str]], value: Any, path: str
) -> Tuple[Sequence[Any], Set[str]]:
    rows = _array(errors, value, path)
    if rows is None:
        return [], set()
    identifiers: Set[str] = set()
    for index, row in enumerate(rows):
        row_path = "{0}/{1}".format(path, index)
        obj = _mapping(errors, row, row_path)
        if obj is None:
            continue
        identifier = _identifier(errors, obj.get("id"), row_path + "/id")
        if identifier is not None:
            if identifier in identifiers:
                _add(errors, row_path + "/id", "duplicates an earlier identifier")
            identifiers.add(identifier)
    return rows, identifiers


def _string_list(errors: List[Dict[str, str]], value: Any, path: str) -> None:
    rows = _array(errors, value, path)
    if rows is None:
        return
    for index, item in enumerate(rows):
        if not isinstance(item, str):
            _add(errors, "{0}/{1}".format(path, index), "must be text")


def validate_manifest(manifest: Mapping[str, Any]) -> List[Dict[str, str]]:
    errors: List[Dict[str, str]] = []
    if manifest.get("schema") != PROJECT_SCHEMA:
        _add(errors, "/schema", "must equal {0}".format(PROJECT_SCHEMA))
    if manifest.get("schema_version") != 1:
        _add(errors, "/schema_version", "must equal 1")
    for key in _REQUIRED_TOP:
        if key not in manifest:
            _add(errors, "/" + key, "required field is missing")

    _text(errors, manifest.get("project_id"), "/project_id", 8)
    _text(errors, manifest.get("title"), "/title", 2)
    _text(errors, manifest.get("question"), "/question", 1)
    if manifest.get("kind") not in {"research", "software", "hybrid"}:
        _add(errors, "/kind", "must be research, software, or hybrid")

    hypothesis = _mapping(errors, manifest.get("hypothesis"), "/hypothesis")
    if hypothesis is not None:
        for key in ("statement", "falsifier"):
            _text(errors, hypothesis.get(key), "/hypothesis/" + key)
        definitions = _mapping(errors, hypothesis.get("operational_definitions"), "/hypothesis/operational_definitions")
        if definitions is not None:
            for key, value in definitions.items():
                _text(errors, key, "/hypothesis/operational_definitions/<key>", 1)
                _text(errors, value, "/hypothesis/operational_definitions/" + str(key))
        _string_list(errors, hypothesis.get("success_criteria"), "/hypothesis/success_criteria")

    framing = _mapping(errors, manifest.get("framing_review"), "/framing_review")
    if framing is not None:
        _text(errors, framing.get("neutral_restatement"), "/framing_review/neutral_restatement")
        for key in ("competing_frames", "loaded_terms_reviewed", "scope_boundaries"):
            _string_list(errors, framing.get(key), "/framing_review/" + key)

    novelty = _mapping(errors, manifest.get("novelty_review"), "/novelty_review")
    if novelty is not None:
        _text(errors, novelty.get("status"), "/novelty_review/status")
        _text(errors, novelty.get("search_date"), "/novelty_review/search_date")
        for key in (
            "databases",
            "queries",
            "nearest_prior_work",
            "differentiators",
            "negative_searches",
            "scope_limitations",
        ):
            _string_list(errors, novelty.get(key), "/novelty_review/" + key)

    claim_rows, claim_ids = _id_objects(errors, manifest.get("claims"), "/claims")
    evidence_rows, evidence_ids = _id_objects(errors, manifest.get("evidence"), "/evidence")
    assumption_rows, assumption_ids = _id_objects(errors, manifest.get("assumptions"), "/assumptions")
    adversarial_rows, adversarial_ids = _id_objects(errors, manifest.get("adversarial_tests"), "/adversarial_tests")
    _id_objects(errors, manifest.get("alternative_explanations"), "/alternative_explanations")
    _id_objects(errors, manifest.get("contradictions"), "/contradictions")
    _id_objects(errors, manifest.get("reviewer_objections"), "/reviewer_objections")
    _id_objects(errors, manifest.get("limitations"), "/limitations")
    _id_objects(errors, manifest.get("external_reviews"), "/external_reviews")
    _id_objects(errors, manifest.get("waivers"), "/waivers")

    for index, row in enumerate(claim_rows):
        if not isinstance(row, Mapping):
            continue
        base = "/claims/{0}".format(index)
        for key in ("statement", "type", "importance", "falsifier", "reasoning", "reconciliation"):
            _text(errors, row.get(key), base + "/" + key)
        scope = _mapping(errors, row.get("scope"), base + "/scope")
        if scope is not None:
            for key in ("population", "setting", "timeframe"):
                _text(errors, scope.get(key), base + "/scope/" + key)
        for field, valid in (
            ("evidence_ids", evidence_ids),
            ("counterevidence_ids", evidence_ids),
            ("assumption_ids", assumption_ids),
            ("adversarial_test_ids", adversarial_ids),
        ):
            values = _array(errors, row.get(field), base + "/" + field)
            if values is not None:
                for pos, item in enumerate(values):
                    if not isinstance(item, str):
                        _add(errors, "{0}/{1}/{2}".format(base, field, pos), "must be an identifier")
                    elif item not in valid:
                        _add(errors, "{0}/{1}/{2}".format(base, field, pos), "references an unknown identifier")

    for index, row in enumerate(evidence_rows):
        if not isinstance(row, Mapping):
            continue
        base = "/evidence/{0}".format(index)
        for key in (
            "kind",
            "description",
            "artifact_path",
            "sha256",
            "source_locator",
            "source_type",
            "directness",
            "extraction",
            "data_location",
            "interpretation",
            "limitations",
        ):
            _text(errors, row.get(key), base + "/" + key)
        declared_sha256 = row.get("sha256")
        if isinstance(declared_sha256, str) and declared_sha256 and not re.fullmatch(r"[0-9a-fA-F]{64}", declared_sha256):
            _add(errors, base + "/sha256", "must be a 64-character SHA-256 digest")
        artifact_path = row.get("artifact_path")
        if isinstance(artifact_path, str) and artifact_path:
            try:
                safe_relative_path(artifact_path)
            except Exception:
                _add(errors, base + "/artifact_path", "must be a safe project-relative path")
        if not isinstance(row.get("primary"), bool):
            _add(errors, base + "/primary", "must be true or false")
        for field in ("supports_claims", "counterevidence_for_claims"):
            values = _array(errors, row.get(field), base + "/" + field)
            if values is not None:
                for pos, item in enumerate(values):
                    if not isinstance(item, str) or item not in claim_ids:
                        _add(errors, "{0}/{1}/{2}".format(base, field, pos), "references an unknown claim")

    for index, row in enumerate(assumption_rows):
        if isinstance(row, Mapping):
            base = "/assumptions/{0}".format(index)
            for key in ("statement", "risk", "test"):
                _text(errors, row.get(key), base + "/" + key)

    for index, row in enumerate(adversarial_rows):
        if isinstance(row, Mapping):
            base = "/adversarial_tests/{0}".format(index)
            for key in ("target", "procedure", "failure_condition", "result", "status"):
                _text(errors, row.get(key), base + "/" + key)

    methods = _mapping(errors, manifest.get("methods"), "/methods")
    if methods is not None:
        for key in (
            "design",
            "population",
            "sampling",
            "analysis_plan",
            "effect_size_metric",
            "uncertainty_method",
            "causal_identification",
            "missing_data_plan",
            "preregistration",
            "reproducibility_command",
        ):
            _text(errors, methods.get(key), "/methods/" + key)
        for key in ("controls", "exclusions"):
            _string_list(errors, methods.get(key), "/methods/" + key)
        size = methods.get("sample_size")
        if size is not None and (not isinstance(size, int) or isinstance(size, bool) or size < 0):
            _add(errors, "/methods/sample_size", "must be null or a non-negative integer")

    ethics = _mapping(errors, manifest.get("ethics"), "/ethics")
    if ethics is not None:
        _text(errors, ethics.get("review_status"), "/ethics/review_status")
        _string_list(errors, ethics.get("risks"), "/ethics/risks")
        _string_list(errors, ethics.get("mitigations"), "/ethics/mitigations")

    disclosures = _mapping(errors, manifest.get("disclosures"), "/disclosures")
    if disclosures is not None:
        for key in ("funding", "conflicts", "known_counterevidence", "omitted_data", "negative_results"):
            _string_list(errors, disclosures.get(key), "/disclosures/" + key)
        attestations = _mapping(errors, disclosures.get("attestations"), "/disclosures/attestations")
        if attestations is not None:
            for key in (
                "all_known_material_data_declared",
                "null_and_negative_results_declared",
                "citations_checked_against_sources",
                "no_claim_relies_only_on_another_authors_conclusion",
            ):
                if not isinstance(attestations.get(key), bool):
                    _add(errors, "/disclosures/attestations/" + key, "must be true or false")

    submission = _mapping(errors, manifest.get("submission"), "/submission")
    if submission is not None:
        for key in (
            "field",
            "article_type",
            "corresponding_author",
            "data_availability",
            "code_availability",
        ):
            _text(errors, submission.get(key), "/submission/" + key)
        for key in ("target_venues", "author_names"):
            _string_list(errors, submission.get(key), "/submission/" + key)

    privacy = _mapping(errors, manifest.get("privacy"), "/privacy")
    if privacy is not None:
        if privacy.get("classification") not in {"public", "internal", "confidential", "restricted"}:
            _add(errors, "/privacy/classification", "has an unknown classification")
        if privacy.get("external_ai") not in {"allow", "ask", "deny"}:
            _add(errors, "/privacy/external_ai", "must be allow, ask, or deny")
        _string_list(errors, privacy.get("redaction_notes"), "/privacy/redaction_notes")

    workloads = _array(errors, manifest.get("workloads"), "/workloads")
    if workloads is not None:
        workload_ids: Set[str] = set()
        for index, row in enumerate(workloads):
            base = "/workloads/{0}".format(index)
            obj = _mapping(errors, row, base)
            if obj is None:
                continue
            identifier = _identifier(errors, obj.get("id"), base + "/id")
            if identifier in workload_ids:
                _add(errors, base + "/id", "duplicates an earlier workload")
            if identifier:
                workload_ids.add(identifier)
            command = _array(errors, obj.get("command"), base + "/command")
            if command is not None:
                for pos, part in enumerate(command):
                    if not isinstance(part, str) or not part:
                        _add(errors, "{0}/command/{1}".format(base, pos), "must be non-empty text")

    return errors


def validate_project(root: str) -> Dict[str, Any]:
    manifest = load_project(root)
    errors = validate_manifest(manifest)
    return {
        "schema": manifest.get("schema"),
        "valid": not errors,
        "error_count": len(errors),
        "errors": errors,
    }
