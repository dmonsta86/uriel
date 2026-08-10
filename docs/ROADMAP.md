# The Forge of Uriel — public roadmap

This is the public product roadmap. It describes direction and current
boundaries; it does not turn planned work into a feature claim.

## Current release boundary

The current public release line is `1.0.0-rc2`, an offline-first,
standard-library-only Python research-assurance toolkit. The canonical `main`
line may contain post-tag maintenance before a future release tag is created.
Release assets and compatibility claims always bind to the exact commit and
tag being published.

Available now includes:

- confined project initialization, manifests, receipts, ledgers, verification,
  and portable packaging;
- Data Readiness (Gate 0) and three sequential integrity gates;
- constructive findings with durable repair paths;
- lifecycle/workbench, bounded AI surfaces, submission and revision records;
- experimental content-addressed Blessing packages and independent
  verification;
- assurance-depth APIs, Core-8 localization, and a synthetic Forge Trial
  validator/scorer.
- an experimental local Evidence Ingress/Data Desk candidate on canonical
  `main`, with immutable raw intake, structural generations, conflict-preserving
  reconciliation, and independent deep verification. It is not part of the
  historical `v1.0.0-rc2` tag.
- additive v1 compatibility contracts for a future private Forge run and
  sanitized portable export. These schemas do not implement the planned Forge
  engine, CLI, state transitions, exporter, or verifier.
- an experimental, disabled-by-default scholarly-acquisition firewall exercised
  only with one confined local fixture. It provides fixed registry/query/budget
  contracts, raw-byte quarantine, receipt-last storage, and offline
  verification, but no live network adapter.

## Active product lane: local data integrity

The local-only Evidence Ingress and Data Desk now provide the first executable
part of this chain for explicitly selected user-owned files:

```text
plan → immutable raw artifact → deterministic profile
→ generation/reconciliation → independent verify → Gate 0
```

The lane preserves source bytes, versions, conflicts, missingness, and
limitations. It does not silently mutate data, infer scientific authority,
execute active content, or require a cloud service.

The generation-to-Gate-0 bridge is implemented with an explicit v2 SortSpec,
deterministic readiness receipt, and one hash-bound active selection. Current
closure work exercises that chain through a clean installed wheel and tracks
one implementation-bound 10,000-row synthetic measurement. Data Desk remains
`EXPERIMENTAL`; broader platform, domain, usability, and adversarial evidence
must accumulate before any maturity promotion.

## Active product lane: scholarly firewall foundation

R2.1 now implements and adversity-tests the no-network foundation:

```text
fixed test registry -> structured query -> bound budget and request
-> exact local mock -> raw-byte quarantine -> offline verify
```

This lane is `EXPERIMENTAL`. It is useful for hardening the contract and
consumer path before network code exists. Simulated SSRF, redirect, header,
size, timeout, retry, disk, prompt-injection, and tamper checks are not a claim
that real DNS/TLS/HTTP transport has shipped or been secured.

## Following lanes

1. One official structured-metadata adapter, only after source terms, rate and
   fairness policy, contact identity, license, retention, versioning, bulk
   alternative, socket isolation, and independent threat review are explicit.
   Live canaries must remain opt-in and tiny; CI stays local.
2. An operational Forge closure layer for bounded milestones, blockers,
   evidence, independent verification, and resumable next moves. Its additive
   run/export contracts are frozen; runtime behavior remains planned.
3. A restrained optional presentation detail: when Gate 0 and all three gates
   are current green and the exact Blessing verifies, the record may display
   “Blessing issued — this idea has earned its wings.” This is not a fifth gate,
   truth claim, peer review, or publication approval.
4. Optional local-model and desktop surfaces only after the CLI workflow proves
   useful in real trials. The deterministic core remains authoritative.

## Evidence-led progress

Each promoted capability must work through its real consumer path and pass
difference, integration, and adversity checks. Release maturity is based on
measured behavior, adversarial fixtures, clean installation, platform evidence,
and user/domain validation—not roadmap size, model agreement, stars, or social
attention.

Uriel remains complementary infrastructure. It is not a truth oracle, peer
reviewer, statistics package, citation manager, ethics approval system,
publication guarantee, autonomous crawler, or AI provider.
