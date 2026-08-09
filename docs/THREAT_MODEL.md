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

The QR payload is an identifier for verification, not a secret or digital signature. For public non-repudiation, publish the Blessing digest in an independently controlled signed release, archival repository, transparency log, or institutional record.

## Race caveat

A source file can theoretically change between metadata inspection and hashing. Uriel detects many resulting inconsistencies but does not claim atomic filesystem snapshots across platforms. High-stakes workflows should run on a quiescent copy, immutable dataset, versioned object store, or filesystem snapshot.

## Reporting security issues

Follow [SECURITY.md](../SECURITY.md). Do not include confidential research data, provider credentials, or exploit details in a public issue.
