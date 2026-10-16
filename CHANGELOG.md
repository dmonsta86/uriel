# Changelog

All notable changes to Uriel are documented here.

## Unreleased

### Added

- `uriel next`: a read-only research protocol driver that evaluates the Three
  Gates, the plan lock, the manuscript check, the recorded audit, and the build,
  sorts open items into seven ordered stages (frame, prior work, design and lock,
  evidence, challenge, manuscript, submission), and names exactly one next action
  with its reason, command, completion condition, and human/agent owner.
  `--prompt` writes a create-only, self-contained instruction for the next
  assistant session with twelve non-negotiable rules.
- `uriel plan lock` / `plan status`: content-addressed, ledger-ordered locks of
  the hypothesis and analysis plan; plan drift, reasoned re-locks, post-results
  revisions, and unsupported preregistration wording are reported.
- The experimental Paper Builder (`uriel paper init|check|build|verify-build|lint`):
  a canonical Markdown manuscript directory with section checklists pre-filled
  from the project record; `{{dp:ID}}` datapoints re-extracted from hashed CSV,
  JSON, or text artifacts with kind bounds, GRIM, cross-datapoint relations, run
  provenance, and confirmation-gated refresh (`dp-add`, `dp-refresh`); citation
  resolution against a verification-status reference registry; verbatim quote
  checks against held sources; claim anchors tied to the project record; a
  per-section number policy; recomputation of reported t/F/chi-square/r/z
  p-values, intervals, and percentages; and a deterministic lint for assistant
  residue, placeholders, stock filler, unsourced attribution, hype, proof
  language, and causal wording without identification. Builds refuse on
  blockers and write a number-trace supplement and digest-bound receipt.
- Framing checks: every major claim needs a recorded rival explanation with a
  discriminating observation; `ruled_out` requires linked evidence or a passed
  adversarial test; manuscripts must address each rival (`[alt:ID]`) and may
  not dismiss an open one, state a claim as settled while a rival is open,
  interpret data with no recorded rival reading, or generalize beyond the
  claim's scope. `paper lint` also flags single-explanation wording,
  unsupported dismissals, and texts that never consider another explanation.
- Model checks: an optional `models` record (additive to `uriel.project.v1`)
  with exact dimensional analysis of each equation (units with SI prefixes and
  custom `[dimensions]`), required symbol meanings and units, a declared role
  (`descriptive_fit`, `predictive`, `mechanistic`), domain, assumptions,
  source, and verification; validation and a rival comparison for predictive
  or mechanistic models; tested implementations; and manuscript checks against
  calling a descriptive fit a mechanism, stating an underdetermined model as
  settled, or using undeclared equations (`[model:ID]`).
- Statistical recomputation reads text extracted from published PDFs: it
  repairs control bytes, lost chi and minus signs, split decimals, and
  publisher font substitutions for `=`, `<`, and `>`, and it accepts "ns",
  inequality-reported statistics, intervening MSE terms, thousands separators,
  and Q/G² tests. Measured locally against the statcheck project's
  hand-extracted material (227 results from 8 published papers), extraction
  coverage rose from 46 to 218 of 225 supported results. All 216 recomputed
  p-values matched an independent SciPy computation, and all 24 hand-labelled
  results agreed with their error and decision-error labels. This was a one-off
  local measurement, not a tracked benchmark.
- Fewer false positives on non-statistical text: "p = 3.14" (pi) and similar
  values are checked only in a visibly statistical context, and "proved to be"
  is no longer read as proof language.
- Seven mirrored schemas (`uriel.paper.v1`, `uriel.datapoints.v1`,
  `uriel.references.v1`, `uriel.paper_check.v1`, `uriel.paper_build.v1`,
  `uriel.plan_lock.v1`, `uriel.next_step.v1`) and the
  [research protocol](docs/RESEARCH_PROTOCOL.md) and
  [Paper Builder](docs/PAPER_BUILDER.md) guides.
- A read-only `uriel paper review` surface that automatically compares an
  explicit candidate against all selected-scope verbatim baselines, reports
  claim/evidence currency and declared closest-prior-work coverage, binds an
  exact baseline/candidate review token, and requires explicit user intent for
  material changes without rewriting or granting scientific authority.
- An opt-in, default-off Research Verbatim Ledger with manual, individually
  confirmed assisted, and explicit per-project modes; per-user/per-project
  isolation; exact-text, record, consent, and ledger hashes; advisory drift
  review; review/search/export/disable/removal controls; public CLI and Python
  routes; mirrored schemas; and focused negative tests for silent capture,
  scope leakage, substitution, tamper, revoked consent, repeated offers, and
  disabled-state compatibility.
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
- Experimental `uriel forge continue` and `verify-continuation` commands with
  exact incomplete-source binding, seven-cell blocker proof, one preferred
  Next Move plus at most two alternatives, a disclosed 12-dimension
  qualitative ordinal and stable tie rule, mandatory guardrails, immutable
  content-addressed packets, and a fixed non-executing next prompt.
- Operational `uriel forge export` and `verify-export` commands that build a
  fresh two-file metadata-only projection, replace source identities with
  salted aliases, omit private references and every evidence body/path/free
  text field, reject links or extra members, and regenerate all bytes against
  the exact source under 512-reference and 16-MiB ceilings.
- Closed mirrored `uriel.forge_continuation.v1` and
  `uriel.forge_public_summary.v1` contracts, focused adversity tests, CLI
  integration, and fresh-wheel smoke coverage for the complete R3.3 path.
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
