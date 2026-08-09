# Architecture

## Recommendation: one repository, two distributions

Uriel should not be split into an “offline project” and an “AI project.” That creates policy drift, duplicate bugs, and confusing certificates. The best structure is one repository with one trust core and two distributions:

1. an installable Python package and `uriel` CLI;
2. a portable `uriel.pyz` archive built from the same source and tests.

Optional adapters sit outside the deterministic trust boundary. This gives a poor or offline user the same audit semantics as a well-funded team.

## Why Python

Python 3.9+ is the best fit for this version because its standard library already provides:

- cross-platform filesystem and subprocess APIs;
- SHA-256 and secure random identifiers;
- atomic replace primitives;
- JSON, SQLite, ZIP, argument parsing, and unit testing;
- readable source that researchers can inspect and modify;
- a one-file zipapp distribution.

A Rust rewrite could eventually reduce startup/runtime variability and produce native binaries, but it would raise contribution and build barriers today. A browser/Electron app would increase dependencies and obscure the core. The current engine therefore stays in one language with zero runtime packages.

## Trust boundary

```text
TRUSTED / DETERMINISTIC
  core.py       confinement, hashing, atomic state, ledger, receipts
  data_contracts.py  local Evidence Ingress contracts and no-write planning
  data_ingress.py  immutable managed raw intake and receipt verification
  data_desk.py  bounded parsing, structural profiles, generations, reconciliation
  schema.py     structural and reference validation
  audit.py      declared-policy evaluation
  blessing.py   content-addressed package and verifier
  qr.py         deterministic QR encoding

OPTIONAL / UNTRUSTED INPUT
  prompts.py    bounded export
  adapters.py   compatible external agent process invocation
  reviews.py    contract validation and content binding
  humans        source interpretation, methods, ethics, judgment
  providers     search/model output, never self-authenticating
```

An imported review can add findings or candidate locators. Its existence cannot pass a Gate. It must match the current source and project hashes, and its proposed evidence must still be registered and independently inspected.

## State layout

```text
project/
  uriel.project.json
  sources/
  artifacts/
  .uriel/
    config.json
    ledger.jsonl
    REMINDERS.md
    manifests/
    receipts/
    audits/
    blessings/
    prompts/
    reviews/
    review-inbox/
    capability-requests/
    data/
      plans/<plan-sha256>.json
      raw/sha256/<prefix>/<content-sha256>
      records/raw/<record-sha256>.json
      receipts/import/<plan-sha256>.json
      generations/<generation-id>/
        records.jsonl
        profile.json
        manifest.json
      reconciliations/<record-sha256>.json
      deltas/<delta-sha256>.jsonl
      indexes/<generation-id>.sqlite
    index/files.sqlite
```

The `.uriel/data/` store is created only by an explicit managed import. Raw
bytes are addressed by their SHA-256, and the import receipt is published last
as the authority marker. An interrupted operation may leave verified,
content-addressed recovery bytes, but it cannot leave an authoritative partial
receipt. Managed intake does not grant Data Readiness or Gate 0 authority.

Data Desk generation identity binds the parser version and explicit format
decision, stable column identities, raw-artifact records, record multiset hash,
source-order hash, the complete ordered parent set, a reconciliation-operation
binding, and any explicit user-confirmed unit or semantic annotation. Records
and profiles are written first; the generation manifest is published last. A
verifier recomputes canonical records and exact records-file bytes, reparses
each sealed leaf artifact under its archived budget, verifies parent lineages,
checks the complete raw-artifact union, and recomputes reconciliation deltas.
Reconciliation appends left records followed by right records and never
resolves a contradiction by deleting either side.

`.uriel/` is derived, local state and is ignored by default. Publish selected Blessing packages or audit exports deliberately; do not commit secrets or raw restricted data.

## Determinism and content binding

- Canonical JSON sorts keys and uses stable separators.
- Data contract records bind their body with `record_sha256`; nested resource
  budgets carry their own independently recomputable binding.
- A no-write import plan exposes a logical label, media, size, and content hash
  while keeping the selected absolute source path private and ephemeral.
- Structural generations preserve exact records and source order separately;
  reordering therefore changes `order_sha256` even when the multiset hash is
  unchanged.
- Data Desk v2 manifests bind the exact canonical records-file hash and byte
  length. The derived SQLite metadata repeats that binding and is checked by a
  bounded row stream rather than treated as authority.
- Published Data Desk v1 schemas remain available as their original contracts;
  stronger records use new v2 IDs instead of silently tightening v1.
- Units and semantic types are empty by default and enter a generation only as
  explicit `USER_CONFIRMED` annotations. Lexical candidates never become
  semantic authority.
- Source records are sorted by case-folded project-relative path.
- Every record contains path, SHA-256, size, and media type.
- The source manifest has a digest over all records and a root-binding digest.
- Workload receipts bind command, source-before/source-after, stdout, stderr, status, and platform.
- Ledger events hash the previous event and their canonical body.
- An audit binds source manifest, source record set, project manifest, policy version, profile, and Gate results.
- A Blessing binds the passing submission audit, relevant receipts/reviews, certificate payload, and exact package membership.

## Fail-closed semantics

Expected integrity failures raise `Refusal` with a stable code and exactly three repair options. Unexpected failures return CLI status `3`. Audit blockers return status `2`; a pass returns `0`.

## Extension strategy

Discipline-specific logic should be implemented as:

- additional schema profiles;
- reporting-guideline checklists;
- import/export adapters;
- test fixtures that demonstrate both expected detection and acceptable non-detection.

Extensions must not weaken the base Three Gates or silently convert warnings into passes.
