# Threat model

## Assets

- integrity of project-local artifacts;
- binding between claims, evidence, execution, and audit results;
- confidentiality decisions at the optional-AI boundary;
- credibility of a `URIEL-BLESSING-v1` package;
- the author’s ability to revisit and repair refused work.

## Adversaries and failure modes

1. **Accidental drift:** a source or result changes after a test.
2. **Path escape:** `..`, absolute paths, links, junctions, or another volume expose or overwrite unrelated data.
3. **Selective evidence:** positive artifacts are declared while null, negative, excluded, or contradictory material is omitted.
4. **Citation laundering:** a chain repeats another paper’s conclusion without reaching primary data or methods.
5. **Model authority injection:** an AI output is treated as proof because it sounds confident.
6. **Stale review:** an old model/human review is attached to changed project bytes.
7. **Certificate tampering:** a package file is edited after issuance.
8. **Overclaiming:** a certificate is presented as truth, peer review, universal novelty, or venue acceptance.
9. **Local compromise:** an attacker can rewrite both project files and the local ledger.
10. **Concurrent mutation:** files change during inventory or workload execution.
11. **Parser confusion or exhaustion:** spoofed extensions, malformed rows,
    duplicate JSON keys, deep nesting, huge fields, or numeric tokens consume
    resources or produce a lossy interpretation.
12. **Derived-state substitution:** generation records, profiles, delta ledgers,
    or SQLite indexes no longer correspond to the sealed raw bytes.
13. **Conflict erasure:** reconciliation silently chooses one contradictory
    record or hides duplicate identity.
14. **Formula activation:** inert source text is executed after spreadsheet
    export or another downstream handoff.
15. **Readiness selector confusion:** a stale or merely newest receipt is used
    instead of the exact generation and SortSpec approved for Gate 0.
16. **AI overexposure or authority injection:** an advisory model receives
    unnecessary records, consumes an unbounded context, or writes output that
    is mistaken for generation, gate, publication, or Blessing authority.
17. **Acquisition boundary confusion:** a hostile host, address, redirect,
    header, compressed body, oversized response, prompt-like payload, or stale
    record is treated as trusted evidence or is allowed to expand authority.
18. **Forge closure forgery:** a caller skips lifecycle stages, forks one
    parent, rewrites a snapshot, cycles dependencies, aliases a reference,
    labels a hard gate as deferred, or treats workflow completion as research
    authority.

## Implemented controls

- exact-root confinement and link/reparse refusal;
- atomic replace for structured state;
- exact source membership and per-file digests;
- pre/post workload manifests and stream hashes;
- hash-chained ledger and immutable content-addressed records;
- mandatory evidence digest and exact locator fields;
- directness/primary-source checks and separation of extraction from interpretation;
- omission, counterevidence, negative-result, and limitation checks;
- hash-bound external review contracts;
- package membership and standalone verification;
- explicit non-claims on the certificate and submission material.
- plan-bound byte/record/column/depth/field/time budgets and truthful-format
  parser refusals;
- stable duplicate-column identities, inert formula-like text, and lead/candidate
  labels rather than scientific findings;
- manifest-last generations with independent sealed-byte reparsing, recursive
  parent verification, ordered two-parent operation identity, complete raw
  lineage, exact records-file bytes, and separate content/order hashes;
- one hash-bound delta entry per input record, explicit one-sided duplicate
  evidence, and preserve-all reconciliation;
- read-only SQLite `integrity_check`, exact generation/file metadata, and a
  bounded canonical record-sequence comparison for the explicitly
  nonauthoritative derived index;
- hard parser, records-file, ledger, index, receipt, lineage-node, and
  cumulative-work budgets, with repeated parent verification cached per run.
- deterministic v2 SortSpecs and readiness receipts plus one hash-bound active
  selector; missing, stale, damaged, or mismatched selection state fails closed
  and no v2 authority decision uses modification time;
- generation AI surfaces require an active PASS receipt, an allowed task,
  explicit rows and columns, a maximum of 1,000 rows and 1 MiB, hashes, a
  redaction policy, and an explicit no-authority declaration.
- burst packets cap task, file, selected-record, and complete serialized sizes;
  checksum member names cannot traverse, required members are enforced, and a
  parent packet must pass integrity and semantic verification before its state
  is carried forward; child packets bind the parent's checksum-manifest hash;
- writes refuse project-local links and reparse points before creating packet
  files; gate and verifier stores rehash filenames, sealed content, checks, and
  exact bindings before any PASS can be consumed;
- source-binding and legacy burst inputs have file-count, per-file, total-byte,
  packet-count, output, and wall-time ceilings; AI task capabilities explicitly
  deny network, shell, packet writes, and project writes.
- the release gate validates an implementation-bound synthetic Data Desk
  measurement and runs the generation/readiness/burst/Gate 0 chain through a
  fresh wheel; it enforces evidence presence and integrity, not a speed target.
- nonpublic review prompts use an allowlisted metadata projection, prompt and
  imported-review bytes are capped, and external-agent invocation requires
  explicit acknowledgement plus project policy, an isolated working directory,
  a minimized environment, no shell, exact model identity, and bounded capture.
- scholarly acquisition is disabled by default and R2.1 ships only a fixed
  local-mock registry and exact injected transport. Structured fields build a
  component request with no free-form URL; simulated host/address pinning,
  response status, headers, content length/type/encoding, timeout, retry,
  concurrency, disk, and cumulative-byte checks fail closed. Raw bytes remain
  opaque in content-addressed quarantine, receipt publication is last, and a
  separate offline verifier rehashes all records and bytes.
- Forge snapshots are private, create-only, and content addressed, with no
  mutable latest selector. One deterministic facade enforces the frozen state
  map, exact BLOCKED resume, terminal states, crash-released per-parent
  operating-system file locking,
  append-only references, scoped work-package immutability, status movement,
  dependency acyclicity, canonical component/record hashes, and full parent
  lineage. Bounded stable-descriptor reads reject duplicate/deep/non-finite
  JSON, unsafe paths, links/reparse points, file aliases, stale bytes, and
  project substitution. Referenced hard gates must remain PASS for closure;
  soft deferral requires a closed hash-bound owner/reason/impact/fallback
  record for the exact work package. Forge always grants zero upstream
  authority and imports no network, model, or subprocess facility.

## Explicit non-controls

Uriel 1.0 does not provide a hardware root of trust, trusted timestamp authority, public transparency log, author identity signature, sandbox, antivirus scanner, secure enclave, remote backup, or protection against an administrator who can rewrite the entire project and every copy of its history.

Data Desk does not sanitize a value for every possible downstream application.
It flags formula-like text and never executes it, but an exporter or user can
still create a dangerous spreadsheet later. It also does not establish that a
declared key, unit, semantic type, measurement, or source method is true.

The AI-surface limits reduce accidental exposure and runaway context, but they
do not determine whether selected values are legally or ethically shareable.
The operator remains responsible for consent, provider retention terms, and
choosing redaction before any packet leaves the local machine. Uriel does not
send a generation packet to a provider by itself.

The scholarly local mock is not an operating-system network firewall and does
not prove a future live fetcher safe. It performs no real DNS or connection,
does not review provider terms or licenses, does not parse metadata, and cannot
protect against an unrelated process launched outside this module. No live
source adapter is shipped.

Forge content addressing is tamper evidence, not a signature, trusted
timestamp, filesystem snapshot, mandatory OS write protection, or defense
against an administrator who rewrites every project file and every history
copy. Its 1 GiB reference-verification budget limits one operation but can
still be expensive on slow storage. Forge checks declared structure and bytes;
it cannot establish that a mission, requirement, owner, deferral rationale,
evidence interpretation, or completion judgment is substantively correct.
The sanitized exporter, blocker-proof/Next-Move path, and continuation packets
remain unimplemented.

The optional `uriel assist` command does start an operator-selected external
process and may therefore cause provider transport. Its temporary working
directory, minimized environment, instructions, timeout, and output cap are not
an operating-system sandbox, credential firewall, or technical network denial.
Do not use it when the executable itself is not trusted and authorized.

The QR payload is an identifier for verification, not a secret or digital signature. For public non-repudiation, publish the Blessing digest in an independently controlled signed release, archival repository, transparency log, or institutional record.

## Race caveat

A source file can theoretically change between metadata inspection and hashing. Uriel detects many resulting inconsistencies but does not claim atomic filesystem snapshots across platforms. High-stakes workflows should run on a quiescent copy, immutable dataset, versioned object store, or filesystem snapshot.

## Reporting security issues

Follow [SECURITY.md](../SECURITY.md). Do not include confidential research data, provider credentials, or exploit details in a public issue.
