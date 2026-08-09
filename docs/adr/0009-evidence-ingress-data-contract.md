# ADR 0009: Evidence Ingress and Data Desk contract boundary

- **Status**: Accepted
- **Date**: 2026-08-08
- **Scope**: R1.1 contract freeze with the bounded R1.2 managed-intake implementation

## Context

Uriel already has project confinement, canonical JSON, content hashes,
immutable checkpoints, Data Readiness, receipts, and independent verification.
The missing local-data layer must reuse those invariants without silently
editing a user's source, leaking local paths, or turning broad document parsing
and network acquisition into core claims.

The CLI already has a `uriel data` group for advisory SortSpec proposals.
Replacing that group would break a current command, while adding a second data
namespace would split one lifecycle across two surfaces.

## Decision

The public subsystem names are **Evidence Ingress** for explicit source
selection and immutable managed copying, and **Data Desk** for inspection,
generation, diff, and reconciliation.

R1.1 established two contract commands; R1.2 adds managed intake and its
read-only verifier to the same group:

```text
uriel data plan --root PROJECT --source FILE
uriel data import --root PROJECT --source FILE --plan PROJECT_RELATIVE_JSON
uriel data verify-import --root PROJECT --receipt PROJECT_RELATIVE_JSON
uriel data verify-record --root PROJECT --record PROJECT_RELATIVE_JSON
```

`data plan` inspects exactly one explicitly selected regular file, enforces a
declared resource budget, verifies UTF-8, hashes the bytes, and emits a
path-free dry-run plan. It writes nothing and permits no network access.
`data import` requires the exact saved plan and selected source, streams the
source once, atomically publishes content-addressed bytes, preserves logical
label relations, and writes its import receipt last. `data verify-import`
recomputes the plan, raw-record, receipt, and managed-byte bindings.
`data verify-record` validates an exact schema/version, rejects unknown fields,
recomputes the record hash, and refuses project-path escape.

The future command shape remains:

```text
plan -> import -> inspect -> diff -> reconcile -> verify
```

`plan`, `import`, import verification, and contract-record verification are
exposed now. `inspect`, `diff`, `reconcile`, and generation verification remain
unavailable until their own bounded packages land.

## Frozen record set

| Record | Schema ID | Binding purpose |
|---|---|---|
| Data import plan | `uriel.data_import_plan.v1` | consent, selected-byte identity, format, budget, and no-write policy |
| Data import receipt | `uriel.data_import_receipt.v1` | exact plan-to-copy byte equality |
| Raw artifact record | `uriel.raw_artifact.v1` | immutable managed bytes and logical label |
| Data generation manifest | `uriel.data_generation_manifest.v1` | parent-aware raw/transform/reconciliation lineage |
| Table/column profile | `uriel.data_profile.v1` | structural counts, observed types, and limitations |
| Transform receipt | `uriel.data_transform_receipt.v1` | input/output generation, rules, row reconciliation, and source invariance |
| Reconciliation result | `uriel.data_reconciliation.v1` | exact/candidate duplicates and preserved conflicts |
| Quarantine/refusal record | `uriel.data_refusal.v1` | constructive failure with a `NO_WRITE` safe state |
| Resource budget | `uriel.resource_budget.v1` | byte, record, column, nesting, and time ceilings |
| Verification receipt | `uriel.data_verification_receipt.v1` | independent target-hash recomputation and decision |

Every record uses `schema`, `schema_version`, canonical serialization, and a
`record_sha256` over canonical JSON with `record_sha256` omitted. Existing
SortSpec, source-manifest, checkpoint, AI-surface, Data Readiness, and verifier
records are referenced rather than cloned.

## Source and privacy boundary

- Initial formats are CSV, TSV, JSON, JSONL, UTF-8 text, and Markdown.
- Directory recursion, archives, links/reparse points, devices, sockets, and
  named pipes fail closed.
- SQLite, XLSX, statistical packages, images, PDF/DOCX extraction, and archives
  require optional adapters and separate evidence.
- A plan contains a logical label, content hash, byte size, detected media,
  access condition, and `PRIVATE_EPHEMERAL` location policy. It never serializes
  the local absolute source path.
- Normalized views will be new generations. Raw source bytes remain immutable.
- Exact duplicates and duplicate candidates may be reported; contradictions
  remain preserved and cannot be erased by reconciliation.

## Consequences

This establishes an executable, packaged contract plus bounded immutable local
intake. It does **not** establish Data Desk profiling, generations,
reconciliation, Gate 0 integration, broad-format support, or scientific
authority. The overall Evidence Ingress and Data Desk lifecycle therefore
remains `PLANNED` until later packages close the complete managed-data path.
