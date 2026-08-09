"""Content-addressed Uriel Blessing package and printable certificate.

A Blessing is a SHA-256-bound attestation that the declared source state passed
Uriel's submission profile.  It is deliberately *not* an identity signature,
peer review, ethical approval, or a claim of universal truth.
"""
from __future__ import annotations

import json
import os
import re
import shutil
import textwrap
import uuid
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, Set, Tuple, Union

from .audit import POLICY_VERSION, audit_project
from .core import (
    IntegrityError,
    Refusal,
    append_ledger,
    atomic_write,
    atomic_write_json,
    build_manifest,
    canonical_json,
    guard_path,
    latest_receipts,
    load_project,
    paths_for,
    read_json,
    safe_relative_path,
    sha256_file,
    sha256_text,
    verify_ledger,
    verify_receipt,
    verify_source_manifest,
)
from .qr import qr_matrix, qr_svg
from .reviews import list_reviews

BLESSING_SCHEMA = "URIEL-BLESSING-v1"

_CORE_KEYS = (
    "schema",
    "schema_version",
    "proof_type",
    "project_id",
    "project_title",
    "project_kind",
    "issued_at_utc",
    "policy_version",
    "audit_id",
    "audit_sha256",
    "source_manifest_sha256",
    "source_records_sha256",
    "project_manifest_sha256",
    "receipt_sha256s",
    "review_sha256s",
    "audit_ledger_event_sha256",
    "verification_payload",
    "scope",
    "non_claims",
)


def _core_payload(value: Mapping[str, Any]) -> Dict[str, Any]:
    return {key: value.get(key) for key in _CORE_KEYS}


def _blessing_id(value: Mapping[str, Any]) -> str:
    return sha256_text(canonical_json(_core_payload(value)))


def _find_audit_event(root: Path, audit_id: str) -> str:
    paths = paths_for(root)
    if not paths.ledger.exists():
        return "0" * 64
    for line in paths.ledger.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        event = json.loads(line)
        if (
            isinstance(event, dict)
            and event.get("event_type") == "audit.completed"
            and isinstance(event.get("payload"), dict)
            and event["payload"].get("audit_id") == audit_id
        ):
            return str(event.get("event_sha256", ""))
    return "0" * 64


def _certificate_text(blessing: Mapping[str, Any]) -> str:
    border = "+" + "-" * 76 + "+"
    rows = [
        border,
        "|" + " THE BLESSING OF URIEL ".center(76) + "|",
        "|" + " Earned deterministic research-integrity audit ".center(76) + "|",
        border,
        "Project: {0}".format(blessing.get("project_title", "Untitled")),
        "Issued:  {0}".format(blessing.get("issued_at_utc", "")),
        "Audit:   {0}".format(blessing.get("audit_id", "")),
        "Blessing SHA-256:",
        "  {0}".format(blessing.get("blessing_id", "")),
        "QR payload:",
        "  {0}".format(blessing.get("verification_payload", "")),
        "",
        "PASSED: Gate 1 Novelty & Clarity",
        "PASSED: Gate 2 Evidence & Citation",
        "PASSED: Gate 3 Adversarial Integrity",
        "",
        "Scope: {0}".format(blessing.get("scope", "")),
        "",
        "This certificate binds declared local artifacts and audit outputs. It does",
        "not certify universal truth, global novelty, peer review, authorship identity,",
        "ethical approval, legal compliance, or the absence of undisclosed material.",
        border,
    ]
    return "\n".join(rows) + "\n"


def _certificate_svg(blessing: Mapping[str, Any]) -> str:
    matrix = qr_matrix(str(blessing["verification_payload"]))
    module = 5
    border = 4
    qr_size = (len(matrix) + border * 2) * module
    qr_x = 720 - qr_size - 32
    qr_y = 100
    commands: List[str] = []
    for y, row in enumerate(matrix):
        for x, dark in enumerate(row):
            if dark:
                commands.append(
                    "M{0},{1}h{2}v{2}h-{2}z".format(
                        qr_x + (x + border) * module,
                        qr_y + (y + border) * module,
                        module,
                    )
                )

    def esc(value: Any) -> str:
        import html

        return html.escape(str(value))

    digest = str(blessing.get("blessing_id", ""))
    return """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 720 1000" width="720" height="1000" role="img" aria-label="Uriel Blessing certificate">
<rect width="720" height="1000" fill="white"/>
<rect x="24" y="24" width="672" height="952" rx="14" fill="none" stroke="black" stroke-width="3"/>
<text x="48" y="92" font-family="serif" font-size="38" font-weight="700">THE BLESSING OF URIEL</text>
<text x="48" y="128" font-family="sans-serif" font-size="16">Earned deterministic research-integrity audit</text>
<rect x="{qx}" y="{qy}" width="{qs}" height="{qs}" fill="white"/>
<path fill="black" d="{path}"/>
<text x="48" y="210" font-family="sans-serif" font-size="20" font-weight="700">{title}</text>
<text x="48" y="244" font-family="monospace" font-size="12">Issued {issued}</text>
<text x="48" y="276" font-family="monospace" font-size="12">Audit {audit}</text>
<text x="48" y="350" font-family="sans-serif" font-size="18">✓ Gate 1 — Novelty &amp; Clarity</text>
<text x="48" y="390" font-family="sans-serif" font-size="18">✓ Gate 2 — Evidence &amp; Citation</text>
<text x="48" y="430" font-family="sans-serif" font-size="18">✓ Gate 3 — Adversarial Integrity</text>
<text x="48" y="500" font-family="sans-serif" font-size="14" font-weight="700">Blessing SHA-256</text>
<text x="48" y="528" font-family="monospace" font-size="11">{d1}</text>
<text x="48" y="548" font-family="monospace" font-size="11">{d2}</text>
<line x1="48" y1="590" x2="672" y2="590" stroke="black"/>
<text x="48" y="628" font-family="sans-serif" font-size="13">This certificate binds the declared local source manifest, audit,</text>
<text x="48" y="650" font-family="sans-serif" font-size="13">execution receipts, and optional review hashes under Uriel policy v1.</text>
<text x="48" y="690" font-family="sans-serif" font-size="13">It is not peer review, proof of universal truth or global novelty, an</text>
<text x="48" y="712" font-family="sans-serif" font-size="13">authorship identity signature, ethical approval, or proof that no data</text>
<text x="48" y="734" font-family="sans-serif" font-size="13">was omitted. Verify the package and live project state before relying on it.</text>
<text x="48" y="900" font-family="serif" font-size="18" font-style="italic">Truth is earned by inspectable evidence, not declared by authority.</text>
</svg>
""".format(
        qx=qr_x,
        qy=qr_y,
        qs=qr_size,
        path="".join(commands),
        title=esc(blessing.get("project_title", "Untitled")),
        issued=esc(blessing.get("issued_at_utc", "")),
        audit=esc(blessing.get("audit_id", "")),
        d1=esc(digest[:32]),
        d2=esc(digest[32:]),
    )


def _submission_documents(
    project: Mapping[str, Any],
    audit: Mapping[str, Any],
    blessing_id: str,
) -> Dict[str, str]:
    submission = project.get("submission") if isinstance(project.get("submission"), Mapping) else {}
    venues = [str(item) for item in submission.get("target_venues", []) if isinstance(item, str) and item.strip()]
    authors = [str(item) for item in submission.get("author_names", []) if isinstance(item, str) and item.strip()]
    limitations = [
        str(row.get("statement"))
        for row in project.get("limitations", [])
        if isinstance(row, Mapping) and str(row.get("statement", "")).strip()
    ]
    audit_limits = [str(item) for item in audit.get("limitations", []) if isinstance(item, str)]
    title = str(project.get("title", "Untitled work"))
    corresponding = str(submission.get("corresponding_author", "[corresponding author]"))
    field = str(submission.get("field", "the relevant field"))
    article_type = str(submission.get("article_type", "research article"))
    venue_text = ", ".join(venues) if venues else "[select a venue after checking current scope, policies, fees, and format]"
    author_text = ", ".join(authors) if authors else "[authors]"

    cover = """# Draft cover letter

Dear Editor,

Please consider **{title}** as a {article_type} for {venue_text}.

The work addresses the following bounded question: {question}

Its claimed contribution is limited to the scope and evidence declared in the accompanying manuscript and Uriel audit package. The project passed Uriel's three deterministic Gates for the exact source manifest recorded in Blessing `{blessing_id}`. This statement is offered as a provenance and completeness aid, not as a substitute for editorial or peer review.

Known limitations, counterevidence, data availability, code availability, funding, and conflicts are disclosed in the submission materials. We ask reviewers to evaluate the underlying artifacts and reasoning directly.

Sincerely,
{author_text}
Corresponding author: {corresponding}
""".format(
        title=title,
        article_type=article_type,
        venue_text=venue_text,
        question=project.get("question", ""),
        blessing_id=blessing_id,
        author_text=author_text,
        corresponding=corresponding,
    )

    limitation_lines = ["# Draft limitations section", ""]
    if limitations:
        limitation_lines.extend("- " + item for item in limitations)
    else:
        limitation_lines.append("- No project-specific limitation text was available. Add it before submission; a venue should not receive this placeholder.")
    limitation_lines.extend(["", "## Limits of the Uriel audit", ""])
    limitation_lines.extend("- " + item for item in audit_limits)
    limitation_lines.append("")

    availability = """# Data and code availability statement

**Data:** {data}

**Code:** {code}

The Uriel package records SHA-256 digests for the exact local artifacts used by the audit. Hashes establish byte identity; they do not grant access rights or replace repository preservation. Remove private paths and confirm consent, licensing, embargoes, and repository retention before publication.
""".format(
        data=submission.get("data_availability") or "[state where the data can be accessed, under what conditions, or why access is restricted]",
        code=submission.get("code_availability") or "[state where code and environment instructions can be accessed]",
    )

    venue = """# Venue targeting notes

Declared field: **{field}**

Declared candidate venues:
{venues}

Uriel does not assert that these venues are current, suitable, reputable, affordable, or accepting submissions. Before submission, verify directly on each venue's official site:

- current aims and scope;
- article type and word/data limits;
- required reporting guideline and checklist;
- data, code, preregistration, ethics, and conflict policies;
- fees, waivers, preprint rules, license, and archival policy;
- current submission portal and deadlines;
- indexing and publisher identity to avoid a similarly named predatory venue.

For optional help, run `uriel prompt submission-review --provider generic-web --acknowledge-external` and independently verify every current venue fact it returns.
""".format(
        field=field,
        venues="\n".join("- " + item for item in venues) if venues else "- No venue declared yet.",
    )

    checklist = """# Submission formatting and integrity checklist

- [ ] Title, abstract, claims, tables, and conclusion use the same bounded scope.
- [ ] Every major claim resolves to an exact evidence record and source location.
- [ ] Primary data or original output replaces conclusion-only citation chains where obtainable.
- [ ] Null, negative, failed, excluded, and contradictory results are disclosed.
- [ ] Sample counts, exclusions, missingness, controls, effect sizes, and uncertainty agree across text and tables.
- [ ] Figures and tables can be regenerated from the declared command or have a reasoned non-code verification route.
- [ ] Ethics status, consent, privacy, licensing, funding, and conflicts are accurate.
- [ ] Data and code links are durable and permissions were checked.
- [ ] The chosen venue's current official author instructions were checked on the submission date.
- [ ] The Uriel certificate is described as a provenance audit, not peer review or proof of truth.
"""

    readme = """# Uriel Blessing package

This directory is content-addressed by Blessing `{blessing_id}`.

Run:

```console
python verify.py .
```

The standalone verifier checks package membership and SHA-256 hashes without installing Uriel. Live project verification is stronger because it also checks the current source manifest and local provenance ledger:

```console
uriel verify-blessing PATH_TO_THIS_DIRECTORY --root PATH_TO_PROJECT
```

A verified package proves only that these packaged bytes are internally consistent with the recorded audit payload. Read `blessing.json`, `audit.json`, and the certificate disclaimer before relying on it.
""".format(blessing_id=blessing_id)

    return {
        "submission/cover-letter.md": cover,
        "submission/limitations.md": "\n".join(limitation_lines),
        "submission/data-availability.md": availability,
        "submission/venue-notes.md": venue,
        "submission/formatting-checklist.md": checklist,
        "README.md": readme,
    }


def _standalone_verifier() -> str:
    return r'''#!/usr/bin/env python3
"""Standalone verifier for a Uriel Blessing package (standard library only)."""
import hashlib
import json
import pathlib
import sys


def canonical(value):
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha(path):
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def main():
    root = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    value = json.loads((root / "blessing.json").read_text(encoding="utf-8"))
    core_keys = (
        "schema", "schema_version", "proof_type", "project_id", "project_title",
        "project_kind", "issued_at_utc", "policy_version", "audit_id", "audit_sha256",
        "source_manifest_sha256", "source_records_sha256", "project_manifest_sha256",
        "receipt_sha256s", "review_sha256s", "audit_ledger_event_sha256",
        "verification_payload", "scope", "non_claims",
    )
    core = {key: value.get(key) for key in core_keys}
    blessing_id = hashlib.sha256(canonical(core)).hexdigest()
    errors = []
    if blessing_id != value.get("blessing_id"):
        errors.append("Blessing id mismatch")
    files = value.get("files", {})
    actual_names = sorted(
        path.relative_to(root).as_posix() for path in root.rglob("*")
        if path.is_file() and path.name != "blessing.json"
    )
    expected_names = sorted(files)
    if actual_names != expected_names:
        errors.append("Package membership mismatch")
    for name, expected in files.items():
        path = root / pathlib.PurePosixPath(name)
        if not path.is_file() or sha(path) != expected:
            errors.append("File hash mismatch: " + name)
    package_payload = {"blessing_id": blessing_id, "files": files}
    package_sha = hashlib.sha256(canonical(package_payload)).hexdigest()
    if package_sha != value.get("package_sha256"):
        errors.append("Package digest mismatch")
    print(json.dumps({"verified": not errors, "blessing_id": blessing_id, "errors": errors}, indent=2))
    return 0 if not errors else 2


if __name__ == "__main__":
    raise SystemExit(main())
'''


def issue_blessing(root: Union[str, Path]) -> Dict[str, Any]:
    paths = paths_for(root)
    report = audit_project(paths.root, profile="submission")
    if not report.blessable:
        blockers = [
            finding.as_dict()
            for gate in report.gates
            for finding in gate.findings
            if finding.severity == "blocker" and finding.status == "FAIL"
        ]
        raise Refusal(
            "Uriel cannot issue a Blessing because the submission profile has unresolved mandatory findings.",
            code="BLESSING_NOT_EARNED",
            details={"audit_id": report.audit_id, "blockers": blockers[:20]},
            repairs=[
                "Open `.uriel/REMINDERS.md`, repair the first active Gate, and rerun `uriel audit --profile submission`.",
                "Narrow unsupported claims rather than weakening the evidence requirement.",
                "Submit without a Uriel Blessing and disclose unresolved limitations if they cannot be repaired honestly.",
            ],
        )
    source = build_manifest(paths.root, persist=True)
    source_check = verify_source_manifest(paths.root, source)
    if not source_check.get("verified"):
        raise IntegrityError("The source changed before Blessing issuance.", code="BLESSING_SOURCE_CHANGED")
    if source.get("manifest_sha256") != report.source_manifest_sha256:
        raise IntegrityError("The audit is stale relative to the current source manifest.", code="BLESSING_STALE_AUDIT")
    project = load_project(paths.root)
    project_hash = sha256_file(paths.project)
    if project_hash != report.project_manifest_sha256:
        raise IntegrityError("The project manifest changed after the audit.", code="BLESSING_PROJECT_CHANGED")
    audit_path = guard_path(paths.root, paths.root / safe_relative_path(report.audit_path), must_exist=True)
    audit_hash = sha256_file(audit_path)

    receipt_hashes: List[str] = []
    for receipt in latest_receipts(paths.root):
        verification = verify_receipt(paths.root, receipt)
        if (
            verification.get("verified")
            and receipt.get("status") == "PASS"
            and receipt.get("post_records_sha256") == source.get("records_sha256")
        ):
            receipt_hashes.append(str(receipt.get("receipt_sha256")))
    review_hashes = sorted(
        str(row.get("review_sha256"))
        for row in list_reviews(paths.root)
        if row.get("source_manifest_sha256") == source.get("manifest_sha256")
        and row.get("project_manifest_sha256") == project_hash
    )
    verification_payload = "URIEL-BLESSING-v1:{0}:{1}".format(
        report.audit_id, str(source.get("records_sha256", ""))[:16]
    )
    core: Dict[str, Any] = {
        "schema": BLESSING_SCHEMA,
        "schema_version": 1,
        "proof_type": "sha256-content-addressed-attestation",
        "project_id": project.get("project_id"),
        "project_title": project.get("title"),
        "project_kind": project.get("kind"),
        "issued_at_utc": report.created_at_utc,
        "policy_version": POLICY_VERSION,
        "audit_id": report.audit_id,
        "audit_sha256": audit_hash,
        "source_manifest_sha256": source.get("manifest_sha256"),
        "source_records_sha256": source.get("records_sha256"),
        "project_manifest_sha256": project_hash,
        "receipt_sha256s": sorted(set(receipt_hashes)),
        "review_sha256s": sorted(set(review_hashes)),
        "audit_ledger_event_sha256": _find_audit_event(paths.root, report.audit_id),
        "verification_payload": verification_payload,
        "scope": "The exact declared local project state and Uriel policy version recorded by this payload.",
        "non_claims": [
            "not proof of universal truth or global novelty",
            "not peer review, editorial acceptance, authorship identity, ethical approval, or legal compliance",
            "not proof that undisclosed or inaccessible data does not exist",
        ],
    }
    blessing_id = _blessing_id(core)

    package_dir = paths.blessings / blessing_id
    if package_dir.exists():
        result = verify_blessing(package_dir, project_root=paths.root)
        if result.get("verified"):
            return result
        raise IntegrityError(
            "An existing content-addressed Blessing package is damaged; Uriel will not silently repair it.",
            code="BLESSING_PACKAGE_DAMAGED",
            details={"package": str(package_dir), "errors": result.get("errors")},
        )

    temporary = paths.blessings / ".candidate-{0}".format(uuid.uuid4().hex)
    temporary.mkdir(parents=True, exist_ok=False)
    try:
        atomic_write_json(temporary / "audit.json", report.as_dict())
        atomic_write_json(temporary / "source-manifest.json", source)
        atomic_write(temporary / "verification-qr.svg", qr_svg(str(core["verification_payload"])))
        documents = _submission_documents(project, report.as_dict(), blessing_id)
        provisional = {**core, "blessing_id": blessing_id}
        atomic_write(temporary / "certificate.txt", _certificate_text(provisional))
        atomic_write(temporary / "certificate.svg", _certificate_svg(provisional))
        atomic_write(temporary / "verify.py", _standalone_verifier())
        try:
            os.chmod(temporary / "verify.py", 0o755)
        except OSError:
            pass
        for name, text in documents.items():
            destination = temporary / safe_relative_path(name)
            atomic_write(destination, text if text.endswith("\n") else text + "\n")
        file_hashes: Dict[str, str] = {}
        for path in sorted(temporary.rglob("*"), key=lambda item: item.as_posix()):
            if path.is_file():
                file_hashes[path.relative_to(temporary).as_posix()] = sha256_file(path)
        package_sha = sha256_text(canonical_json({"blessing_id": blessing_id, "files": file_hashes}))
        blessing = {
            **core,
            "blessing_id": blessing_id,
            "files": file_hashes,
            "package_sha256": package_sha,
        }
        atomic_write_json(temporary / "blessing.json", blessing)
        os.replace(str(temporary), str(package_dir))
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)

    event = append_ledger(
        paths.root,
        "blessing.issued",
        {
            "blessing_id": blessing_id,
            "package_sha256": read_json(package_dir / "blessing.json").get("package_sha256"),
            "audit_id": report.audit_id,
            "source_manifest_sha256": source.get("manifest_sha256"),
        },
    )
    result = verify_blessing(package_dir, project_root=paths.root)
    result["ledger_event_sha256"] = event.get("event_sha256")
    return result


def verify_blessing(
    package: Union[str, Path],
    *,
    project_root: Optional[Union[str, Path]] = None,
) -> Dict[str, Any]:
    candidate = Path(package).expanduser()
    if candidate.is_file():
        package_dir = candidate.parent
        blessing_path = candidate
    else:
        package_dir = candidate
        blessing_path = package_dir / "blessing.json"
    errors: List[str] = []
    try:
        value = read_json(blessing_path)
    except Refusal as exc:
        return {"verified": False, "errors": [str(exc)], "package": str(package_dir)}
    if value.get("schema") != BLESSING_SCHEMA:
        errors.append("Blessing schema mismatch")
    calculated_id = _blessing_id(value)
    if calculated_id != value.get("blessing_id"):
        errors.append("Blessing id mismatch")
    files = value.get("files")
    if not isinstance(files, Mapping):
        files = {}
        errors.append("Blessing file manifest is missing")
    expected_names = sorted(str(name) for name in files)
    actual_names = sorted(
        path.relative_to(package_dir).as_posix()
        for path in package_dir.rglob("*")
        if path.is_file() and path.name != "blessing.json"
    )
    if actual_names != expected_names:
        errors.append("Package membership mismatch")
    for name, expected in files.items():
        try:
            rel = safe_relative_path(str(name))
            path = package_dir / rel
            if not path.is_file() or sha256_file(path) != expected:
                errors.append("File hash mismatch: {0}".format(name))
        except Refusal:
            errors.append("Unsafe package path: {0}".format(name))
    package_sha = sha256_text(canonical_json({"blessing_id": value.get("blessing_id"), "files": dict(files)}))
    if package_sha != value.get("package_sha256"):
        errors.append("Package digest mismatch")
    audit_copy = package_dir / "audit.json"
    source_copy = package_dir / "source-manifest.json"
    if audit_copy.is_file() and sha256_file(audit_copy) != value.get("audit_sha256"):
        # The package audit is canonical pretty JSON, while the original audit
        # hash refers to the original file. They should be identical because both
        # use Uriel's pretty JSON writer.
        errors.append("Packaged audit does not match the recorded audit hash")
    if source_copy.is_file():
        source = read_json(source_copy)
        if source.get("manifest_sha256") != value.get("source_manifest_sha256"):
            errors.append("Packaged source manifest identity mismatch")
        if source.get("records_sha256") != value.get("source_records_sha256"):
            errors.append("Packaged source record digest mismatch")

    live_verified: Optional[bool] = None
    if project_root is not None:
        try:
            paths = paths_for(project_root)
            source = build_manifest(paths.root, persist=True)
            source_check = verify_source_manifest(paths.root, source)
            ledger = verify_ledger(paths.root)
            live_errors = []
            if not source_check.get("verified"):
                live_errors.append("Live source manifest does not verify")
            if source.get("manifest_sha256") != value.get("source_manifest_sha256"):
                live_errors.append("Live source manifest differs from the blessed source")
            if source.get("records_sha256") != value.get("source_records_sha256"):
                live_errors.append("Live source record set differs from the blessed source")
            if sha256_file(paths.project) != value.get("project_manifest_sha256"):
                live_errors.append("Live project manifest differs from the blessed project")
            if not ledger.get("verified"):
                live_errors.append("Live provenance ledger does not verify")
            blessing_events = []
            for line in paths.ledger.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("event_type") == "blessing.issued" and event.get("payload", {}).get("blessing_id") == value.get("blessing_id"):
                    blessing_events.append(event)
            if not blessing_events:
                live_errors.append("The live ledger has no issuance event for this Blessing")
            errors.extend(live_errors)
            live_verified = not live_errors
        except (Refusal, IntegrityError, OSError, json.JSONDecodeError) as exc:
            errors.append("Live project verification failed: {0}".format(exc))
            live_verified = False
    return {
        "verified": not errors,
        "package_verified": not [error for error in errors if not error.startswith("Live ") and "live" not in error.casefold()],
        "live_project_verified": live_verified,
        "blessing_id": value.get("blessing_id"),
        "package_sha256": value.get("package_sha256"),
        "verification_payload": value.get("verification_payload"),
        "package": str(package_dir.resolve()),
        "certificate_svg": str((package_dir / "certificate.svg").resolve()),
        "certificate_text": str((package_dir / "certificate.txt").resolve()),
        "errors": errors,
    }
