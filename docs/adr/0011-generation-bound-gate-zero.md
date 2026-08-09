# ADR 0011: Generation-bound Gate 0 and bounded AI surfaces

Status: Accepted
Date: 2026-08-08

## Context

ADR 0010 made Data Desk generations independently verifiable but deliberately
gave them no Gate 0 authority. A safe authority bridge must identify one exact
generation and one explicit record identity, preserve duplicate and
contradictory records, invalidate stale inputs, and prevent an AI-facing export
from becoming a second authority path.

Selecting the newest file by modification time is not sufficient. More than
one valid SortSpec or readiness receipt may exist for the same generation, and
historical receipts must remain preserved after a different receipt becomes
active. The strict verifier and Blessing issuer must bind the same selection
that Gate 0 evaluated.

## Decision

Uriel adds a generation-bound v2 readiness lane with this required sequence:

```text
source consent and intake policy PASS
→ raw artifact sealed
→ parser safety PASS
→ extraction and normalization receipt PASS
→ record identity and SortSpec PASS
→ reconciliation and order invariance PASS
→ independent generation verification PASS
→ Gate 0 Data Readiness evaluation
```

`uriel.sort_spec.v2` binds the exact Data Desk generation manifest, parser and
policy versions, raw and parent lineage, stable column IDs, explicit primary
and tie-break keys, null order, duplicate policy, analysis-plan hash, and an
implicit record-hash final tie-break. The only normalization rule is identity
without coercion. The v2 lane never silently excludes records and never offers
the legacy `keep_first` duplicate policy.

`uriel.data_readiness.v2` is deterministic and content-addressed. It records
all 22 mandatory checks, exact normalized-generation identity, row
reconciliation, order-invariance recomputation, and independent generation
verification. A changed raw artifact, generation, parser, policy, normalizer,
SortSpec, parent, or analysis plan makes the receipt fail live recomputation.

After every readiness check, Uriel atomically writes a hash-bound
`uriel.data_readiness_selection.v1` record to `.uriel/readiness/CURRENT.json`.
This replaceable selector names one immutable generation, SortSpec, readiness
receipt, and readiness binding. Gate 0, strict-gate evaluation, the independent
project verifier, and Blessing issuance all recompute that exact selection.
The selector's own content hash participates in the full project binding, so
switching between two existing receipts changes the binding. Missing, damaged,
or mismatched selection state fails closed. Historical receipts remain
content-validated and bound as evidence but cannot regain authority; callers
may inspect one directly with the independent receipt verifier.

Read-only status calls never create readiness state and no v2 authority path
uses filesystem modification time. Published v1 SortSpec and readiness
contracts remain unchanged and available through the legacy dataset lane.

Generation-backed AI burst packets require an active PASS receipt, an allowed
task, explicit unique zero-based row indices, and explicit stable columns.
They enforce a hard maximum of 1,000 selected rows and 1 MiB of exposed record
JSON, support metadata/hash-only redaction, bind generation and readiness
hashes, and declare that they grant no Gate 0, gate, publication, finding, or
Blessing authority. AI output has no write path to immutable generations,
readiness receipts, gate decisions, or publication state.

## Consequences and limits

- A verified Data Desk generation is still not ready until an explicit v2
  SortSpec is evaluated and becomes the active independently verified receipt.
- Uriel does not infer record identity, scientific meaning, statistics,
  exclusions, transformations, or publication fitness.
- Re-running an existing SortSpec deterministically restores the same active
  selection and full binding; selecting another existing receipt changes the
  binding without deleting history.
- The row and byte ceilings are exposure controls, not context-window or model
  quality claims. Users should select less than the maximum whenever possible.
- AI packets are advisory inputs. Only deterministic local code can write gate
  authority, and every substantive strict gate fails when Gate 0 is not PASS.
