# ADR 0010: Deterministic Data Desk generations and reconciliation

Status: Accepted
Date: 2026-08-08

## Context

ADR 0009 froze the local Evidence Ingress/Data Desk contracts, and R1.2 added
receipt-last immutable intake. The next runtime boundary must turn sealed text
and tabular artifacts into inspectable derived state without silently deciding
scientific validity, record identity, units, or the meaning of a field.

A generation verifier that checks derived files and raw bytes independently is
insufficient: it could miss a mismatch between them. Reconciliation that picks
one side of a conflict would also destroy evidence. Retry identity must remain
stable when publication stops after payload files but before the authority
manifest.

## Decision

Uriel implements a standard-library-only `data_desk` module with this local
flow:

```text
verified import receipt
→ bounded truthful-format parse
→ structural profile and canonical records
→ manifest-last immutable generation
→ no-write diff or preserve-all reconciliation
→ independent raw reparse and recursive verification
```

CSV and TSV are consumed row by row with an explicit UTF-8 delimiter, quoting,
strictness, and first-row-header decision. JSON and JSONL refuse duplicate
object keys, non-standard constants, unsafe numeric tokens, excess nesting,
oversized fields, and non-object tabular shapes. Text and Markdown are treated
as inert physical lines; Markdown is not rendered and formula-like strings are
never executed.

Columns receive stable IDs from exact name plus occurrence, so duplicate
headers remain distinct. Profiles report bounded structural and lexical
observations: row/column counts, missingness, exact duplicates, candidate keys,
lexical type candidates, case collisions, and formula-like text. Queue entries
are `LEAD` or `CANDIDATE`, never findings. Units and semantic types default to
empty and enter identity only through an explicit `USER_CONFIRMED` annotation.

Generation identity binds parser version and explicit format decisions, stable
columns, the complete ordered parent set, a reconciliation-operation binding,
raw-artifact records, record multiset hash, source-order hash, record count,
and user annotations. The operation binding covers both parent IDs, both input
record hashes, confirmed key columns, and the delta hash, so different parent
lineages cannot collide merely because their output rows happen to match.
Immutable records and profile are payloads; `manifest.json` is the authority
marker and is published last. Its timestamp comes from immutable parent
receipts, making interrupted retry byte-for-byte deterministic.

`data diff` is a no-write preview. `data reconcile` emits left records followed
by right records and records exact overlap, candidate duplicate keys,
modified/added/absent/unchanged/unknown groups, and conflicts. It never
imputes, coerces, sorts, deletes, or chooses a winning record. Verification
reparses sealed leaf bytes under the archived resource budget, recomputes the
profile and identities, recursively verifies both reconciliation parents, and
recomputes every delta and preserve-all binding. A content-addressed canonical
JSONL delta ledger provides one hash-bound entry for every input record,
including side, ordinal, record/key hashes, classification, counterpart counts,
conflict state, and preservation state.

Each generation also receives a standard-library SQLite index containing only
canonical derived records and generation-binding metadata. The index is opened
read-only during verification, must pass `integrity_check`, and must reproduce
the exact ordinal/hash/record sequence. The manifest and index both bind the
SHA-256 and byte length of the canonical records file; blank or otherwise
noncanonical physical lines are refused. Its manifest role is explicitly
`SQLITE_DERIVED_NONAUTHORITATIVE`; SQLite never replaces canonical JSONL or
becomes a gate-authority source.

The stronger generation, profile, reconciliation, import-plan, and resource
budget contracts use explicit `v2` schema IDs. Published `v1` schemas remain
packaged byte-for-byte and old v1 import plans remain importable; they are not
silently reinterpreted as v2 records. Parser and verifier work has hard file,
row, field, ledger, receipt-store, SQLite, lineage-node, and cumulative-work
ceilings in addition to each plan's lower declared limits.

## Consequences and limits

- A structurally verified generation still has no Gate 0 or scientific
  authority. Gate 0 integration is a separate fail-closed change.
- Data Desk is intentionally not a statistics package, unit inference engine,
  scientific validator, spreadsheet renderer, or automatic normalizer.
- Reconciliation key selection is an explicit user decision. Ambiguous or
  missing keys fail closed.
- Current profiling retains bounded parsed records in memory after streaming
  delimited input. No scale claim is made until measured benchmark receipts
  exist.
- The SQLite index is disposable and generation-bound. A missing index may be
  rebuilt by repeating the same creating operation, but a verifier never
  silently repairs it and a corrupt index fails closed.
