# Changelog

All notable changes to Uriel are documented here.

## Unreleased

### Added

- Eight closed, content-addressed R2.1 scholarly-acquisition contracts covering
  fixed source registry, source policy, structured query, cumulative budget,
  adapter boundary, plan, raw-byte quarantine, and receipt.
- `uriel data acquire-mock` and `verify-acquisition` as an explicitly
  acknowledged local-only firewall exercise with no live networking, no
  free-form URL, receipt-last immutable storage, and separate offline
  verification.
- Adversity coverage for simulated SSRF/rebinding, redirects, authentication
  and cookies, malformed or duplicate headers, content type/length/encoding,
  cumulative response size, timeout, retries, concurrency, low disk,
  indirection, interruption, binary/prompt-injection bytes, strict JSON, and
  record/quarantine tampering.
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
- Deterministic Data Desk inspection for bounded UTF-8 CSV, TSV, JSON, JSONL,
  text, and Markdown, with explicit format/header decisions, stable duplicate
  column identities, missingness, lexical candidates, duplicate ledgers, and
  user-confirmed-only unit/semantic annotations.
- Immutable manifest-last data generations with separate record-multiset and
  source-order hashes, raw-byte reparsing, recursive lineage verification,
  no-write generation diffs, per-record canonical delta ledgers, derived
  generation-bound SQLite indexes, and reconciliation that preserves every
  input record and contradiction.
- Explicit v2 Data Desk contracts with published v1 schemas preserved intact;
  old v1 import plans remain accepted rather than silently reinterpreted.
- Ordered two-parent reconciliation identity, complete parent/raw/key/delta
  verification, exact canonical records-file bindings, one-sided duplicate
  evidence, and hard parser/verifier work ceilings.
- Generation-bound v2 SortSpecs, deterministic 22-check readiness receipts,
  and a hash-bound active selector shared by Gate 0, strict gates, independent
  verification, and Blessing issuance, with stale/tamper fail-closed behavior.
- Explicit generation AI projections and burst packets with required rows,
  columns, allowed task, redaction policy, hashes, no-authority declarations,
  and hard 1,000-row/1-MiB exposure ceilings.
- Cryptographically chained burst history, reparse-point-safe packet writes,
  independently rehashed gate/verifier receipts, and explicit read-only AI,
  input-work, output-size, and wall-time ceilings.
- Fresh-wheel exercise of the exact Data Desk generation, readiness, bounded
  redacted burst, independent packet verification, and strict Gate 0 chain,
  including deterministic retry, stale-plan refusal, and path non-disclosure.
- An implementation-bound 10,000-row synthetic Data Desk measurement receipt
  and release checker with an explicit no-throughput/no-capacity claim boundary.
- Allowlist-based nonpublic prompt projection, 128-KiB prompt/review ceilings,
  exact external-review membership checks, and no implicit sensitive export for
  a merely labeled local model.
- Explicitly acknowledged external-agent execution with project-policy checks,
  validated/passed model identity, isolated temporary working directory,
  minimized environment, no shell, bounded capture, and process-tree timeout.
- Additive, closed v1 contracts for immutable private Forge run snapshots and
  bounded sanitized-export manifests, with frozen lifecycle compatibility,
  authority-neutral references, path/privacy exclusions, and contract tests.
- Experimental `uriel forge init`, `transition`, and `verify` commands with
  immutable content-addressed private revisions, exact transition and BLOCKED
  resume rules, per-parent fork prevention, complete lineage/component digest
  checks, confined streamed references, dependency and closure validation,
  explicit staleness, stable refusals, and no network/model/subprocess or
  upstream authority path.
- A closed, 64-KiB `uriel.forge_deferral.v1` contract requiring the owner,
  reason, impact, safe fallback, next task, and completion condition for one
  exact deferred soft-gate work package; referenced hard gates remain
  non-deferrable.
- Distinct Core-8 README visuals with the English gold reference preserved and
  seven localized explainer posters published at 3840 × 2160 after independent
  100-point visual review. Generated visible text remains explicitly
  `AI_ASSISTED_REQUIRES_NATIVE_REVIEW`; no native approval is implied.
- Hash-bound visual-source and localized-asset v2 manifests covering source
  archive/member hashes, dimensions, exact alt text, review scores, prompt/copy
  provenance, renderer identity, publication hashes, and zero authority.
- A confined, offline, no-implicit-bulk visual renderer with required source
  SHA-256 pins, atomic final publication, strict JSON, PNG/path/resource gates,
  and focused mutation tests for localization integrity.

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
- Provider-neutral prompt export, hash-bound review import, default-deny capability requests, and optional external-agent adapter.
- Portable zipapp build and multi-platform CI.
- Browser-authenticated GitHub publishing helpers and a no-terminal GitHub Desktop path.
- Tag-triggered GitHub release automation for wheel, source distribution, portable archive, and checksums.
- Full offline release check with fresh-wheel installation and packaged-schema verification.
- Interruption-safe release orchestration that stops active child process groups, checkpoints `INTERRUPTED`, and resumes only from hash-matched artifacts.
- Durable maintainer handoff and continuation prompt for low-cost or free coding agents.
- Idempotent GitHub metadata binding and an all-in-one Windows prerequisite/publishing launcher.
