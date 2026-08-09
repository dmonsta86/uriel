# ADR 0012: Minimal Forge run and sanitized-export contracts

Status: Accepted
Date: 2026-08-08

## Context

The Forge of Uriel needs an operational closure layer, but Uriel already has
authoritative project manifests, source manifests, Data Desk generations,
readiness selections, audits, gate decisions, gap registers, lifecycle
decisions, publication records, packets, verifier receipts, and strict
Blessings. Re-copying those records into a Forge-specific gate, evidence, or
certificate system would create conflicting authority and stale closure
claims.

The public roadmap also names a Forge state sequence and requires private run
state to remain ignored by Git. Any portable run export must omit local paths,
identities, credentials, private URLs, restricted evidence bodies, and
unrelated project names. Those compatibility and disclosure boundaries need
to be frozen before a writer or state-transition engine exists.

## Decision

R3.1 adds two additive, closed JSON contracts and no runtime engine:

1. `uriel.forge_run.v1` is one immutable, content-addressed private
   coordination snapshot. Mission, requirements, one lineage event, work
   packages, indexes, and an integrity manifest are nested in that snapshot.
   Existing Uriel records appear only as typed, hashed references.
2. `uriel.forge_sanitized_export.v1` is a portable manifest for a future
   deterministic projection. It contains aliases, bounded exported-file
   metadata, hashes, link information, and mandatory sanitization receipts. It
   cannot contain the source project ID, source run ID, local source paths,
   human identities, credentials, private URLs, or evidence bodies.

This is deliberately smaller than independent run, task, event, register, and
checksum databases. Snapshot lineage provides the event history; the nested
manifest binds the snapshot components; references preserve existing
authority. Future application code may materialize private run directories,
but those files cannot become a second gate or Blessing system.

### Private run identity and integrity

Each run snapshot has a stable `run_id`, monotonically increasing `revision`,
nullable parent-record digest, one event, exact project binding, bounded
collections, and `record_sha256`. The record digest is SHA-256 over Uriel
canonical JSON after removing only the top-level `record_sha256` field.
Component digests use canonical JSON over the exact corresponding array or
object. An update creates a new snapshot; it never rewrites an earlier
snapshot.

Reference paths use portable project-relative forward-slash spelling. They
cannot be absolute, contain a drive prefix, backslash, colon, control
character, `.` segment, or `..` segment. A future verifier must additionally
resolve each path through `canonical_root()` and `guard_path()` and reject
links, junctions, reparse points, missing files, and hash mismatches.

Requirement IDs, reference IDs, work-package IDs, and dependency edges are
locally scoped to one run. Future runtime validation must reject duplicates,
unknown references, self-dependencies, and cycles. The JSON Schema bounds the
shape and collection sizes; the engine remains responsible for relational and
filesystem checks.

A future reader must enforce the schema's pre-parse ceilings: 4 MiB for one
private run snapshot and 1 MiB for one sanitized-export manifest. Exported
payload files are separately limited to 512 files and 16 MiB total. Reference
sizes are metadata bindings, not permission to load a referenced artifact into
memory, a prompt, or an AI context; verification must stream or inspect within
the existing operation budget.

### State compatibility

The compatible state vocabulary is:

```text
DRAFT
SCOPED
AUDITED
IMPLEMENTING
VERIFYING
READY_FOR_INDEPENDENT_VERIFY
COMPLETE
COMPLETE_WITH_DEFERRED_SOFT_GATES
BLOCKED
FAILED
STALE
SUPERSEDED
ABORTED
```

The normal path is:

```text
DRAFT -> SCOPED -> AUDITED -> IMPLEMENTING -> VERIFYING
-> READY_FOR_INDEPENDENT_VERIFY
-> COMPLETE | COMPLETE_WITH_DEFERRED_SOFT_GATES
```

Any nonterminal working state may become `BLOCKED`, `FAILED`, `STALE`,
`SUPERSEDED`, or `ABORTED`. A resolved `BLOCKED` run may resume at the exact
stage recorded by its lineage event. A completed run may only become `STALE`
or `SUPERSEDED`; a changed binding cannot silently remain complete.
`FAILED`, `STALE`, `SUPERSEDED`, and `ABORTED` are terminal for that lineage.
The machine-readable transition map in the schema is a compatibility
annotation. R3.2 must enforce it; R3.1 does not write transitions.

Forge outcomes are prefixed (`FORGE_COMPLETE`, `FORGE_BLOCKED`, and so on) so
they cannot be mistaken for a scientific gate result. The snapshot explicitly
declares `authority_scope = FORGE_WORKFLOW_ONLY` and
`upstream_authority_effect = NONE`.

### Existing authority remains upstream

Forge owns mission wording, requirement baselines, work-package descriptions,
dependency ordering, operational lineage, and references. It does not own or
infer:

- project or generation identity;
- Data Readiness or Gate 0;
- Gates 1-3 or audit findings;
- blocker truth outside referenced gap records;
- publication authority;
- packet contents;
- independent-verifier results; or
- Blessing issuance or Earned Wings eligibility.

Gate 0 comes from the generation-readiness and gate-decision path, while the
audit record covers Gates 1-3. A Forge snapshot must reference the applicable
records and cannot infer one from the other. No Forge field named `blessed`,
`gate_pass`, `publication_ready`, `verified`, or equivalent is permitted.

### Sanitized export

Raw Forge snapshots are private and are never exported directly. A future
projector must create a new `uriel.forge_sanitized_export.v1` manifest and
fresh exported files. The manifest requires all of these receipts to be true:

- source identities were replaced with non-identifying aliases;
- absolute and private source paths were removed;
- credentials and secret-like values were removed;
- private URLs were removed;
- restricted evidence bodies were removed;
- unrelated project names were removed;
- exported links and hashes were independently rechecked.

Export entries contain metadata and hashes only. An export manifest grants no
gate, publication, verifier, or Blessing authority. The contract limits one
export to 512 files and 16 MiB; R3.2 may choose smaller operational limits.

### Reserved deterministic failures

The R3.2 validator should return stable codes including
`FORGE_SCHEMA_MISMATCH`, `FORGE_UNKNOWN_FIELD`, `FORGE_DUPLICATE_ID`,
`FORGE_RECORD_DIGEST_MISMATCH`, `FORGE_PROJECT_BINDING_MISMATCH`,
`FORGE_REF_PATH_UNSAFE`, `FORGE_REF_MISSING`, `FORGE_REF_HASH_MISMATCH`,
`FORGE_DEPENDENCY_UNKNOWN`, `FORGE_DEPENDENCY_CYCLE`,
`FORGE_TRANSITION_REFUSED`, `FORGE_FORBIDDEN_AUTHORITY_FIELD`, and
`FORGE_EXPORT_SANITIZATION_INCOMPLETE`.

## Consequences and limits

- The schemas can be packaged, reviewed, and compatibility-tested before any
  mutating code exists.
- The operational Forge capability remains `PLANNED`; there is no Forge CLI,
  persistence engine, transition writer, verifier, exporter, or AI authority.
- The contracts add no network operation, subprocess path, or runtime
  dependency.
- `.uriel/forge/` remains local ignored state. A future exporter must use a
  deliberate destination and fail closed before publishing anything.
- Cross-record uniqueness, graph acyclicity, canonical digest recomputation,
  path confinement, transition enforcement, and sanitization scans are
  implementation obligations for R3.2, not claims made by schema presence.
