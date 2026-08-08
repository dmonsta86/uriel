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

## Next product lane: local data integrity

The next major capability is a local-only Evidence Ingress and Data Desk. It
will begin with explicitly selected user-owned files and will provide:

```text
plan → immutable raw artifact → deterministic profile
→ generation/reconciliation → independent verify → Gate 0
```

It will preserve source bytes, versions, conflicts, missingness, and
limitations. It will not silently mutate data, infer scientific authority,
execute active content, or require a cloud service.

## Following lanes

1. Safe scholarly acquisition through explicit, disabled-by-default source
   adapters with resource, provenance, license, prompt-injection, and SSRF
   controls.
2. An operational Forge closure layer for bounded milestones, blockers,
   evidence, independent verification, and resumable next moves.
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
