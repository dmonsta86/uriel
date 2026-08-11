# ADR 0014: Deterministic local Forge engine and verifier

Status: Accepted
Date: 2026-08-10

Follow-up: [ADR 0015](0015-forge-forward-path.md) implements the R3.3
continuation, blocker-proof, Next Move, and metadata-only export layer without
changing this run/state contract.

## Context

ADR 0012 froze the private `uriel.forge_run.v1` compatibility contract and its
state map but deliberately shipped no writer. A useful Forge needs one
operational path that can coordinate bounded work without becoming another
research Gate, publication decision, verifier authority, or Blessing system.
It must also remain safe for automation: no implicit newest-file selection,
network or model calls, shell execution, mutable authority pointer, unbounded
JSON, or unconfined reference path.

The public roadmap additionally permits
`COMPLETE_WITH_DEFERRED_SOFT_GATES`. That state is unsafe if any arbitrary file
can be labeled a deferral. A soft-gate deferral must identify its owner, reason,
impact, safe fallback, next task, and exact completion condition, while a hard
research gate remains non-deferrable.

## Decision

R3.2 implements a standard-library-only `forge_engine.py` and these CLI paths:

```text
uriel forge init --root PROJECT --request INIT.json
uriel forge transition --root PROJECT --snapshot EXACT.json \
  --to-state STATE --rationale TEXT [--request UPDATE.json]
uriel forge verify --root PROJECT --snapshot EXACT.json
```

The request envelopes are deliberately small internal operation contracts:
`uriel.forge_init_request.v1` supplies mission, non-goals, requirements,
project-relative reference descriptors, and work packages;
`uriel.forge_transition_request.v1` may append references, replace the complete
work-package projection under transition rules, identify closure references,
and add a result summary. They are bounded strict JSON inputs, not persistent
authority records.

### Immutable private storage

Every revision is written beneath:

```text
.uriel/forge/runs/<run-id>/<revision>-<record-sha256>.json
```

The directory is ignored by Git. A fully written temporary file is atomically
linked into its final create-only name; an existing different body is refused.
The run directory's regular-directory identity is rechecked after temporary
creation, immediately before publication, and after publication.
There is no mutable `CURRENT`, `latest`, or modification-time selector. The CLI
returns the exact next snapshot path. A per-parent operating-system file lock
prevents concurrent forks, is released automatically when a process exits or
crashes, and lets a retry return the already sealed semantic child. Its
persistent one-byte file is coordination state, not authority.

Run IDs are deterministic over the bound project and normalized baseline.
Revision zero is `DRAFT`; each child binds its parent record digest, one event,
and exact changed-reference/work-package IDs. Mission, non-goals,
requirements, project identity, and binding remain immutable within a lineage.
References are append-only. Scoped work-package definitions are immutable;
their statuses and acceptance-reference sets evolve through a separate frozen
transition map.

### Validation and independent verification

Readers enforce the 4 MiB pre-parse snapshot ceiling, strict UTF-8 JSON,
duplicate-key and non-finite-number refusal, a 64-level nesting ceiling,
type-strict schema constants, closed objects, canonical record and component
digests, content-addressed filenames, and a maximum 4,096-record lineage walk.
They recompute:

- exact project identity and project-manifest bytes;
- every parent link, event kind, state transition, and BLOCKED resume stage;
- requirement, reference, work-package, event, and record digests;
- ID uniqueness, append-only relations, work-package status movement,
  dependency membership, and dependency acyclicity;
- reference indexes, closure membership, requirement coverage, and state/result
  consistency;
- project-relative path safety, regular-file identity, size, SHA-256, typed JSON
  schema identity, and live staleness; and
- referenced strict gate decisions when present. A referenced non-PASS hard
  gate prevents either completion state.

References are streamed and cumulative hashing is capped at 1 GiB during both
creation and verification. Typed JSON is capped at 16 MiB. Verification opens stable regular
file descriptors and refuses links, junctions, reparse points, aliases,
identity changes, missing bytes, and hash substitution. A changed live binding
invalidates an active or complete snapshot. `STALE` is accepted only after the
verifier observes that mismatch. `SUPERSEDED` is the separate administrative
replacement state and may preserve still-current bindings. Both preserve and
verify the historical lineage.

### Soft-gate deferrals

R3.2 adds the additive closed `uriel.forge_deferral.v1` record. It is limited to
64 KiB and binds one work-package ID, `gate_kind = SOFT`, owner, reason, impact,
safe fallback, next task, completion condition, timestamp, zero upstream
authority, and its canonical digest. A deferred work package must accept a
typed, hash-bound deferral for its exact ID. A
`COMPLETE_WITH_DEFERRED_SOFT_GATES` result must include every such deferral in
its closure references. A plain text file, mislabeled schema, wrong package ID,
missing field, changed byte, or hard gate cannot satisfy this rule.

### Authority and execution boundary

Forge output always declares:

```text
authority_scope = FORGE_WORKFLOW_ONLY
upstream_authority_effect = NONE
```

The engine imports no network, HTTP, browser, model, or subprocess facility and
does not mutate source artifacts, project manifests, Data Desk state, Gate
decisions, publication records, verifier receipts, Blessings, or Earned Wings.
Existing records are only typed, byte-hashed references. Forge completion means
the declared operational bundle closed under this workflow; it is not a claim
that the research is true, publishable, independently peer reviewed, or
Blessing-eligible.

## Consequences and limits

- The operational run/state/verifier slice is `EXPERIMENTAL` and exercised
  through source tests and a fresh-wheel CLI smoke.
- At the R3.2 boundary recorded here, sanitized export remained contract-only
  and raw Forge snapshots could not be copied as public exports. ADR 0015 now
  provides a generated metadata-only projector; the raw-snapshot prohibition
  remains.
- ADR 0015 now owns blocker proof, Next Move scoring, durable continuation
  packets, and next prompts. R3.4 still owns the restrained Earned Wings
  presentation layer.
- The engine detects byte and relation inconsistencies; it cannot determine
  whether a requirement, owner, rationale, evidence interpretation, or closure
  judgment is substantively correct.
- Content addressing and local lineage are tamper-evident, not a signature,
  trusted timestamp, operating-system sandbox, append-only filesystem, or
  defense against an administrator who rewrites every copy.
