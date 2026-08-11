# ADR 0015: Evidence-bound Forge forward paths and sanitized projection

- Status: Accepted
- Date: 2026-08-11
- Depends on: ADR 0012, ADR 0014

## Context

ADR 0014 made Forge run history operational but stopped at deterministic
coordination state. An incomplete run still needed a durable answer to six
operator questions:

1. What has been established?
2. What has been refuted?
3. What remains unknown but useful?
4. Is the missing path genuinely external, or has safe local work not been
   exhausted?
5. Which bounded action should happen next?
6. What can be shared without copying private run state or evidence bodies?

A model-generated narrative is not an acceptable authority layer. It can hide
the ranking rule, turn missing work into an external blocker, execute beyond
the declared boundary, or leak project text into a supposedly public packet.
A mutable handoff file would also weaken exact resumption and tamper evidence.

## Decision

R3.3 adds a standard-library-only `forge_forward.py` facade and four commands:

```text
uriel forge continue
uriel forge verify-continuation
uriel forge export
uriel forge verify-export
```

The facade imports no network, model, browser, or subprocess facility. It never
transitions a Forge run and grants zero upstream authority.

### Exact source requirement

Every operation starts with an explicit content-addressed Forge snapshot path.
The application-facing loader performs structural, lineage, live-reference,
project-binding, and staleness verification before exposing a defensive copy.
There is no newest-file discovery or mutable current-run pointer.

Continuation is limited to incomplete states:

```text
DRAFT
SCOPED
AUDITED
IMPLEMENTING
VERIFYING
READY_FOR_INDEPENDENT_VERIFY
BLOCKED
```

Terminal runs cannot produce a new continuation.

### Closed operator request

The bounded `uriel.forge_forward_request.v1` operation envelope contains
operator-reported assessment lists, source requirement IDs, exactly seven
blocker challenge cells, one to three candidate moves, safe completed work,
and required inputs. It is not a durable authority schema; its canonical
normalized SHA-256 is bound into the durable continuation.

Unknown fields, duplicate JSON keys, non-finite values, malformed IDs,
duplicate IDs, over-limit text, unknown requirements/references, unused inputs,
and false safety guardrails fail closed.

### Seven-cell blocker derivation

The frozen cells are:

```text
VERIFY_REQUIREMENT
SEARCH_DECLARED_BOUNDARY
TEST_SAFE_ALTERNATIVE
TEST_NARROWER_SCOPE
TEST_SUBSTITUTE_EVIDENCE
COMPLETE_SAFE_SCAFFOLD
NO_PATH_CHALLENGE
```

Conclusive cells must cite references already bound to the source snapshot.
The deterministic derivation emits only:

- `PATH_AVAILABLE`;
- `EVIDENCED_EXTERNAL_BLOCKER`;
- `BLOCKER_NOT_EVIDENCED`; or
- `REQUIREMENT_NOT_APPLICABLE`.

An external blocker requires a confirmed requirement and `NO_PATH` in all six
path challenges. Any missing, inconclusive, or inapplicable work on a declared
requirement remains `BLOCKER_NOT_EVIDENCED`. A discovered path wins over a
no-path claim.

If blocker proof is incomplete, rank one must address a missing cell. If an
external blocker is evidenced, rank one must be `REQUEST_INPUT` or
`EXTERNAL_ACTION` and cite a declared input.

### Transparent qualitative ordinal

Each candidate supplies all 12 ratings on a disclosed 0-4 qualitative scale.
Eight benefit dimensions are summed and four burden dimensions are subtracted.
The record stores every label and subtotal. Stable ties use, in order:
falsification value, dependency unlocking, evidence quality, risk, user burden,
time, cost, and lexical move ID.

The ordinal is explicitly not probability, truth, calibrated confidence,
evidence-strength measurement, or scientific authority. Ethics, law, consent,
privacy, resource limits, and authority boundaries are mandatory booleans, not
scoreable costs.

### Immutable continuation

The closed `uriel.forge_continuation.v1` record is create-only at:

```text
.uriel/forge/continuations/<continuation-id>/<record-sha256>.json
```

It binds:

- exact source path, digest, state, and revision;
- normalized request digest;
- operator assessment and subject requirements;
- all seven challenge cells and their evidence-reference index;
- derived blocker status and missing-cell index;
- the disclosed scale, dimensions, subtotals, net ordinals, rank, and tie rule;
- one preferred move and at most two ordered alternatives;
- safe completed work and required inputs;
- the rank-one exact completion condition; and
- a fixed advisory next prompt.

The prompt does not interpolate operator prose. It identifies only the source
digest and preferred move ID, treats packet content as untrusted data, forbids
automatic network/model/subprocess/browser/credential/destructive behavior,
and asks for a proposed rather than automatic Forge action.

Publication uses create-exclusive temporary bytes and an atomic hard link into
the digest-bound final name. There is no latest pointer or overwrite path.

### Generated metadata-only export

The existing `uriel.forge_sanitized_export.v1` manifest becomes operational.
`forge export` requires a fresh destination outside private `.uriel` state.
It stages and atomically publishes exactly:

```text
manifest.json
summary.json
```

The new closed `uriel.forge_public_summary.v1` is generated from source
structure. It can include:

- salted project, run, and reference aliases;
- source run digest, state, and revision;
- requirement and work-package counts; and
- non-private reference role, typed-record flag, fixed coarse media family,
  byte count, and content hash.

It excludes source paths, project/run/ref/record IDs, all free-form mission,
requirement, finding, assessment, and result text, all evidence bodies, and all
references declared `PRIVATE`. It never copies a source file. Exact source
schema and media-type strings are excluded because custom values can contain
project or person names.

The public summary is capped at 512 non-private references and 16 MiB. The
manifest is capped at 1 MiB. The manifest binds the exact generated summary
bytes, entry count, byte count, entries root, sanitation flags, and its own
canonical digest.

### Independent verification

Continuation verification recomputes the source, request digest, continuation
ID, blocker derivation, score and tie order, exact completion condition, prompt,
record digest, and content-addressed location.

Export verification requires the exact source snapshot. It recomputes export
identity and aliases, regenerates the expected summary, rehashes all bytes,
checks manifest totals and roots, and requires directory membership to be
exactly `manifest.json` plus `summary.json`. Links, reparse points,
directories, extra files, missing files, substitutions, and tamper are refused.

## Authority boundary

Continuation records declare:

```text
authority_scope = FORGE_CONTINUATION_ONLY
upstream_authority_effect = NONE
```

Exports declare:

```text
authority_scope = PORTABLE_SANITIZED_EXPORT_ONLY
upstream_authority_effect = NONE
```

Neither can pass Data Readiness or a research Gate, approve publication, issue
or verify a Blessing, declare Earned Wings, interpret scientific evidence, or
authorize an external action.

## Consequences

- Incomplete work can resume from one exact, evidence-bound packet without a
  model dependency.
- The reason for rank one is inspectable and reproducible.
- Missing safe work cannot be laundered into an external blocker.
- Raw private snapshots no longer need to be copied for a structural review,
  but generated metadata still requires human sensitivity review before
  publication.
- A content hash, count, role, state, or revision can itself be sensitive in
  some threat models; this is a metadata minimizer, not an automatic
  declassification oracle.
- The engine verifies structure, bindings, and derivations, not the substantive
  correctness of operator prose or qualitative ratings.
- Automatic semantic judgment, model execution, broad milestone closure, GUI,
  live collaboration, and a mutable current-run selector remain out of scope.
