# Known limitations and honest claim ceiling

Uriel can make a research record harder to overstate and easier to verify. It cannot mechanize scientific truth.

## What a pass means

A Gate pass means the declared project state satisfied the implemented policy checks for that profile and policy version. A Blessing means a fresh submission-profile audit passed and the packaged bytes verify against the recorded digests.

## What a pass does not mean

- the hypothesis is true;
- the work is globally novel;
- the literature search is complete;
- the statistical model is appropriate for every context;
- the underlying instrument or dataset is unbiased;
- no relevant data was withheld outside the project;
- a quotation or interpretation is correct unless a reviewer checks it;
- research ethics, law, privacy, or licensing requirements are satisfied;
- the work survived independent peer review;
- a journal or conference should accept it;
- an author or reviewer identity was cryptographically verified.

## Detector limitations

The fallacy/framing detector uses conservative text patterns plus declared structure. It can miss sophisticated defects and can flag innocent wording. Findings therefore explain the triggering text and offer repair paths rather than asserting bad faith.

The novelty gate verifies that a search record exists and is bounded; it cannot prove universal absence of prior work. A domain expert and current primary-source search remain necessary.

The evidence gate can verify bytes and mappings, but cannot know whether an undeclared artifact exists. Mandatory attestations create accountability; they do not create omniscience.

## Evidence Ingress and Data Desk limitations

Data Desk accepts only one explicitly selected UTF-8 CSV, TSV, JSON, JSONL,
text, or Markdown file per import. It does not recurse through directories,
extract archives, render Markdown, execute spreadsheet formulas, infer an
encoding, or fetch network content. Parsed records are retained in memory for
profiling after delimited rows are consumed incrementally. The tracked
`synthetic-tabular-10000-v1` receipt records one local 10,000-row, four-column
observation bound to the measured implementation. It is not a throughput,
maximum-capacity, latency-SLA, hardware-equivalence, or real-dataset claim.

Current hard Data Desk parser ceilings are 512 MiB per managed source, 256 MiB
for one in-memory JSON document, 2,000,000 parsed records, 100,000 columns,
256 nesting levels, and 16 MiB per field. Generation verification additionally
caps canonical record files, delta ledgers, SQLite indexes, receipt-store
enumeration, lineage nodes, and cumulative record/byte work. A plan may declare
lower limits. Hitting a ceiling is a refusal, not partial output; these ceilings
are safety boundaries rather than performance claims.

Profiles contain structural and lexical observations, not statistics or
scientific findings. Candidate keys are not decisions about identity. Units and
semantic types remain empty unless a user explicitly confirms them. Missing,
mixed, formula-like, duplicate, added, absent, modified, and conflicting states
are review leads; they do not prove corruption or scientific importance.

Reconciliation requires explicit keys and preserves every input record. Its
per-record delta ledger and SQLite index are derived aids bound to canonical
JSONL generations, including the exact records-file hash and byte length. The
index is nonauthoritative and disposable. None of plan,
import, inspect, diff, reconcile, or generation verification grants Gate 0.

Generation-bound Gate 0 additionally requires one explicit v2 SortSpec and an
active, independently recomputed v2 readiness receipt. Record identity is never
guessed. The v2 readiness lane performs identity-only normalization, refuses
silent exclusions and `keep_first`, preserves duplicates, and uses an explicit
record-hash tie-break. Changing a raw artifact, generation lineage, parser,
policy, normalizer, SortSpec, or bound analysis plan invalidates the active
receipt. Historical receipts remain preserved but cannot become authority
without being selected by a fresh readiness check.

## Scholarly acquisition firewall limitations

`uriel data acquire-mock` is an experimental local policy exercise, not live
scholarly acquisition. It is disabled until the operator supplies
`--acknowledge-local-mock`, reads one regular-file fixture beneath the same
project's `sources/` directory,
and ships no DNS, socket, HTTP, browser, proxy, authentication, cookie,
JavaScript, decompression, subprocess, or background-network implementation.
The fixed `mock.invalid` registry has test-only provenance and makes no claim
about external terms, licenses, availability, or completeness.

The mock validates deterministic policy decisions for simulated host/address
pinning, redirects, headers, media type, content length/encoding, byte and time
ceilings, retries, concurrency, and storage. Those tests do not establish
socket isolation, TLS correctness, DNS security, provider fairness, or safety
of a future live adapter. Raw response bytes are quarantined without parsing,
decoding, rendering, or following embedded instructions. A PASS_LOCAL_MOCK
receipt means only that the local fixture passed this bounded policy and
offline integrity verification. It cannot satisfy Data Readiness, any Gate,
publication authority, a Blessing, or Earned Wings.

AI-facing generation bursts are local packet builders, not inference clients.
They require task-specific rows and columns, cap selection at 1,000 rows and
1 MiB, and can redact values to metadata and hashes. Those ceilings limit
exposure; they are not a promise that a maximum-size packet is affordable,
useful, private under a provider's terms, or appropriate for sensitive data.
Burst task text is additionally capped at 16 KiB, legacy selection at 100
explicit files, and the complete serialized packet at 1 MiB plus 128 KiB.
Legacy source work is refused above 16 MiB per file or 64 MiB total. A chain is
limited to 100 packets; each child binds the SHA-256 identity of its verified
parent. Packet capabilities deny network, shell, packet writes, and project
writes, and request at most 128 KiB of output or 15 minutes of wall time. These
last two limits are instructions that the consuming model host must enforce.
Uriel verifies required membership, checksums, path-safe member names, declared
budgets, no-authority fields, and parent continuity before carrying burst
state forward. It does not upload a packet or call a model.
No AI output can mark readiness, pass a gate, change publication authority, or
issue a Blessing.

Prompt export first refuses a project manifest above 1 MiB. General review
prompts and imported external-review JSON are each limited to 128 KiB. A
nonpublic prompt is metadata-only unless sensitive inclusion is
explicit; the result may be too sparse for useful semantic review, which is the
intended safe failure. `uriel assist` requires explicit external acknowledgement
and stops at 15 minutes or 128 KiB of combined output. It uses no shell, an
isolated temporary working directory, and a minimized environment, but it is
not a sandbox: the selected executable retains the user's OS permissions and
may use network transport. Instruction-level denials of browsing, project
writes, and model tools must not be described as technical enforcement.

Strict source-binding verification refuses more than 10,000 source files,
512 MiB total, or 256 MiB for one file. AI projections additionally refuse a
source generation above 250,000 records or 128 MiB because the current verified
projection implementation reparses the complete sealed generation.

## Certificate design

Version 1 uses SHA-256 content addressing, not public-key author signatures. The standalone verifier checks internal package integrity. Live verification additionally checks the local source state and ledger. Public trust should combine Uriel with signed Git tags/releases and an independent archive.

## Maturity

This is a release candidate with a bounded passing fixture and cross-platform CI configuration. It needs public false-positive/false-negative datasets, discipline-specific validation, usability studies, and independent security review before anyone should mandate it for publication.
