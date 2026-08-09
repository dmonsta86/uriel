# Changelog

All notable changes to Uriel are documented here.

## Unreleased

### Added

- Versioned R1.1 Evidence Ingress/Data Desk contracts for import planning,
  immutable raw artifacts, generations, profiles, transformations,
  reconciliation, refusals, resource budgets, and independent verification.
- `uriel data plan` as a path-private, budgeted, no-write local-file dry run,
  plus `uriel data verify-record` for exact schema/version/hash verification.
- Immutable, content-addressed local intake through `uriel data import`, with
  receipt-last authority, exact-byte deduplication, path redaction, deterministic
  retry, disk/resource checks, and no implied Gate 0 authority.
- `uriel data verify-import` for independent recomputation of archived plan,
  raw-artifact, import-receipt, and managed-byte bindings.

## 1.0.0-rc2 — 2026-08-06

This release-candidate line contains the current offline-first research
assurance, lifecycle, submission, verification, localization, and packaging
baseline. Future release assets must bind to the exact reviewed commit; the
existing `v1.0.0-rc2` tag is not moved.

### Added

- Standard-library-only, root-confined project runtime.
- Deterministic source manifests and local SQLite index.
- Shell-free workload execution with hash-bound receipts.
- Hash-chained provenance ledger.
- Plain-language idea intake that preserves the original question.
- Three audit profiles plus a mandatory submission profile.
- Checks for clarity, framing, evidence provenance, directness, contradictions, assumptions, controls, omissions, uncertainty, ethics, reproducibility, and common fallacy patterns.
- Constructive blocker records with exactly three repair paths and durable reminders.
- Content-addressed Blessing packages with SVG/text certificate, QR payload, submission drafts, and standalone verifier.
- Provider-neutral prompt export, hash-bound review import, default-deny capability requests, and optional compatible external agent adapter.
- Portable zipapp build and multi-platform CI.
- Browser-authenticated GitHub publishing helpers and a no-terminal GitHub Desktop path.
- Tag-triggered GitHub release automation for wheel, source distribution, portable archive, and checksums.
- Full offline release check with fresh-wheel installation and packaged-schema verification.
- Interruption-safe release orchestration that stops active child process groups, checkpoints `INTERRUPTED`, and resumes only from hash-matched artifacts.
- Durable maintainer handoff and continuation prompt for low-cost or free coding agents.
- Idempotent GitHub metadata binding and an all-in-one Windows prerequisite/publishing launcher.
