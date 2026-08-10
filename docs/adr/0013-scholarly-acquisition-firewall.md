# ADR 0013: Scholarly acquisition firewall and local-mock quarantine

Status: Accepted for R2.1 local mocks; live transport remains unapproved
Date: 2026-08-10

## Context

Uriel is useful without network acquisition, but researchers eventually need a
disciplined path from structured scholarly discovery into local evidence
handling. Network acquisition is a separate trust boundary: hosts, DNS
answers, redirects, proxies, credentials, response headers, compressed bodies,
parsers, and embedded instructions can all expand authority or consume
unbounded resources.

Adding a convenient HTTP client first would make the security policy depend on
library defaults and ambient machine state. It would also blur Uriel's
offline-first product promise. R2.1 therefore needs to freeze and exercise the
contract before any real source adapter, resolver, socket, TLS, or HTTP worker
exists.

## Decision

R2.1 ships a disabled-by-default scholarly-acquisition firewall foundation and
one exact local-mock execution path. It ships no live network implementation.

The public CLI surface is:

```text
uriel data acquire-mock
uriel data verify-acquisition
```

`acquire-mock` requires an explicit `--acknowledge-local-mock`, bounded
structured terms, and one regular-file fixture beneath the same project's
`sources/` directory. The fixture
is treated as opaque response bytes. Omitting the acknowledgement refuses
before acquisition state is created.

### Closed record set

Eight additive Draft 2020-12 schemas define the boundary:

1. `uriel.scholarly_source_registry.v1`: a test-only registry with live
   networking and generic browsing disabled.
2. `uriel.scholarly_source.v1`: the one fixed mock source, exact HTTPS
   components, response policy, test-only rights status, and retention policy.
3. `uriel.scholarly_query.v1`: bounded terms, years, and result count with no
   free-form URL.
4. `uriel.scholarly_budget.v1`: request, header, response, quarantine, time,
   DNS-answer, concurrency, disk-reserve, retry, and decompression ceilings.
5. `uriel.scholarly_adapter.v1`: the exact local-mock interface and its zero
   network, resolver, proxy, process, credential, cookie, parser, and authority
   permissions.
6. `uriel.scholarly_plan.v1`: exact project, registry, source, query, budget,
   adapter, and component request bindings.
7. `uriel.scholarly_quarantine.v1`: raw-byte identity, canonical response
   headers, completeness, path, and explicit untrusted/unparsed state.
8. `uriel.scholarly_receipt.v1`: every parent binding, policy transcript,
   quarantine identity, local-mock decision, and explicit no-authority fields.

Every record is closed to undeclared fields and binds canonical JSON with
`record_sha256`. Editor-facing and packaged schema copies must remain byte
identical. The records use no absolute path, credential, cookie, free-form URL,
or mutable "latest" pointer.

### Request construction

The source record fixes method, scheme, lowercase hostname, port, path,
accepted status, and media type. The query supplies only structured values.
Uriel constructs a component request descriptor and hashes canonical JSON over
that descriptor. No URL parser, URL join, redirect target, host suffix match,
or caller-supplied request target participates in R2.1.

An AI may propose the same structured term/year/count fields, but those fields
cannot change the source, host, budget, transport, project writes, credentials,
or authority. The plan explicitly records `authority = NONE`.

### Exact injected transport

The only accepted runtime type is the exact `LocalMockTransport`; subclasses
and missing/default transports are refused. The transport reads one confined
project-relative regular file only when execution reaches the mock exchange.
It imports or invokes no DNS, socket, HTTP, browser, subprocess, proxy,
credential helper, cookie store, JavaScript engine, decompressor, or
background-network facility.

Proxy and credential environment variables are irrelevant because the module
never reads them and has no network client to configure. This is a strong
module boundary, not an operating-system sandbox: unrelated code or processes
retain the user's normal machine authority.

### Policy simulation

The local transcript carries simulated resolver answers, connected address,
peer hostname, response status, headers, timing, attempts, redirects, and
authority counters. Uriel deterministically refuses:

- empty, duplicate, excessive, invalid, scoped, or non-global simulated
  addresses;
- a connected address outside the pinned simulated answer set;
- a changed hostname, redirect, unexpected status, retry, timeout, proxy,
  credential, background-thread, network-call, or resolver-call claim;
- malformed, mixed-case, duplicate, control-containing, undeclared,
  authentication, cookie, or redirect headers;
- a media type other than exact `application/json`;
- missing, malformed, or inconsistent `Content-Length`;
- any content encoding other than absent or `identity`;
- a response or quarantine body above the cumulative plan ceiling; and
- insufficient project-volume space for the maximum quarantine plus reserve.

These checks prove policy logic against deterministic inputs. They do not prove
DNS pinning, socket peer inspection, TLS, proxy isolation, timeout
interruptibility, streaming behavior, or retry fairness for code that does not
yet exist.

### Quarantine ordering and storage

The successful sequence is:

```text
validate exact bundle
-> recompute request and project bindings
-> disk preflight
-> invoke exact local mock
-> validate complete transcript and cumulative raw bytes
-> write immutable component records
-> write content-addressed raw quarantine bytes
-> write quarantine record
-> independently rehash quarantine
-> construct the success receipt in memory
-> run the offline verifier against independently reopened sealed state
-> write the verified success receipt last
```

State is stored below `.uriel/acquisition/`, which remains project-local and
ignored by Git. Immutable publication uses a fully flushed temporary file and
hard-link no-overwrite commit. A collision with different bytes refuses.
Interrupted work can leave unreferenced content-addressed records or raw bytes,
but cannot leave an authoritative success receipt because the receipt is the
last publication.

The fixture's absolute path and filename are not written into the plan,
quarantine record, receipt, or CLI result. The fixture is checked as a regular
non-link file beneath the execution project's `sources/` directory; a
transport bound to another project root is refused. Each project-local path
component is checked for links or reparse points before and after one bounded
descriptor read; platforms that cannot establish a stable file identity fail
closed. Record and quarantine reads use the same bounded pattern.
Archive suffixes are refused and no decompression occurs.

### Raw bytes remain untrusted

The local fixture may contain binary data, invalid UTF-8, NUL bytes, HTML,
script text, or prompt-injection language. R2.1 preserves those bytes exactly
without decoding, parsing, rendering, executing, or following instructions.
The declared `application/json` response policy is transport metadata; it is
not a claim that an extractor has validated the body.

A future deterministic extractor is a separate package and must consume only
a complete independently verified quarantine. It cannot construct another
request from response content.

### Independent verification

`verify-acquisition` is a separate offline path. It uses no transport and:

- strictly and boundedly parses UTF-8 JSON while rejecting duplicate keys,
  non-finite numbers, excessive nesting, and JSON type confusion;
- validates and rehashes receipt, plan, registry, source, query, budget,
  adapter, and quarantine records;
- recomputes the request descriptor from source plus query;
- reopens and rehashes exact quarantine bytes;
- reconstructs and revalidates the complete mock policy transcript; and
- reports whether the historical plan still matches the current project record
  without invalidating an otherwise intact historical receipt.

The verifier cannot set Data Readiness, Gate, publication, Blessing, or Earned
Wings state.

## Authority and integration boundary

`PASS_LOCAL_MOCK` means only that one local fixture passed the R2.1 policy and
integrity contract. It is not evidence that:

- a real scholarly service was contacted;
- metadata is valid, complete, current, licensed, or scientifically relevant;
- DNS, TLS, HTTP, proxy, timeout, or retry handling is secure;
- embedded content is safe to parse;
- a claim is supported; or
- any Uriel Gate should pass.

Quarantined bytes do not enter Data Desk automatically. An operator must make
a separate explicit Evidence Ingress decision. Data Readiness and Gate 0 then
remain responsible for the exact selected generation. Gates 1-3, publication
authority, the independent project verifier, and strict Blessing remain
unchanged.

## Entry gate for any live adapter

No live adapter becomes available, `BETA`, or default-enabled until a separate
ADR and independent threat review close all of these:

- official source identity, current terms, rate/fairness policy, contact
  identity, license, retention, versioning, and bulk alternative;
- isolated no-AI worker boundaries and explicit credential non-use;
- exact resolver, all-answer validation, IP-class refusal, peer pinning, and
  rebinding behavior;
- HTTPS/TLS, proxy denial, redirect denial, header parsing, streaming ceilings,
  deadline enforcement, retries, concurrency, low disk, and crash recovery;
- raw-byte quarantine before parser access;
- cross-platform Python 3.9+ and clean-wheel tests;
- deterministic local mock CI plus tiny opt-in live canaries; and
- proof that no acquisition result can alter existing authority paths.

Generic crawling, browser automation, arbitrary URLs, recursive discovery,
authentication, JavaScript, forms, cookies, and general static-site scraping
remain outside the core.

## Consequences

- Uriel gains a real consumer path for hardening acquisition contracts without
  weakening its offline-first baseline.
- The additional schemas and tests increase maintenance surface, but they make
  future network proposals reviewable against stable bindings and explicit
  non-goals.
- Users can exercise quarantine and verification locally, but should not expect
  useful live literature retrieval from R2.1.
- A future adapter can reuse the record and receipt boundary, but cannot claim
  safety merely by implementing the same interface.
