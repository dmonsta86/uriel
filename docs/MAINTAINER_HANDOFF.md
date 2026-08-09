# Maintainer handoff and durable continuation point

This document is versioned with the repository. Treat the commit containing
this file—not a self-referential hash in prose—as its exact baseline, and
verify local `HEAD` against the intended remote before publishing.

This file is the shortest authoritative continuation point for a human or coding agent. The larger design rationale lives in `README.md`, `docs/ARCHITECTURE.md`, `docs/THREAT_MODEL.md`, `docs/LIMITATIONS.md`, and `AGENTS.md`.

## Current implementation state

Uriel `1.0.0rc2` is the current release-candidate code line with:

- a Python 3.9+ standard-library-only runtime;
- root confinement and link/reparse traversal refusal;
- atomic state writes, SHA-256 source manifests, SQLite indexing, and a hash-chained ledger;
- shell-free workload receipts;
- rough-question intake that preserves the original wording;
- deterministic Novelty & Clarity, Evidence & Citation, and Adversarial Integrity gates;
- persistent repair reminders with exactly three options for blockers;
- hash-bound optional review imports and privacy-aware prompt export;
- content-addressed Blessing packages, printable SVG/text certificates, QR payloads, and a standalone verifier;
- beta research lifecycle, workbench, repair, checkpoint, decision, and submission surfaces;
- experimental assurance-depth APIs and a sealed synthetic Forge Trial validator/scorer;
- PowerShell and POSIX launchers, bounded external-agent integration, CI, release, issue, security, and contribution assets.

The current `main` commit is a post-tag maintenance revision. The existing
`v1.0.0-rc2` tag remains immutable; no release claim should combine its assets
with later `main` changes until a new exact candidate is reviewed and tagged.

## Cross-project field lesson

An operator-authorized research run outside this repository exposed several
domain-neutral practices that Uriel should absorb into future Forge Method and
trial work. This is a methodological steer, not evidence that Uriel currently
implements or validates the practices, and it imports no other project's
identity, subject matter, sources, conclusions, private artifacts, or value
premises.

The highest-value practices are:

- **typed claim separation:** keep observations, derived inferences,
  assumptions, authority rules, boundary claims, and conclusions distinct;
- **missing-numerator discipline:** record an unavailable target quantity as
  unknown with a reason instead of silently replacing it with zero, a broad
  proxy, or an unjustified extrapolation;
- **denominator, clock, and applicability binding:** keep numerator,
  denominator, unit, eligible population, timing convention, place, period,
  coverage, and uncertainty attached to each quantitative claim;
- **category isolation:** a rationale established for an exceptional subset
  cannot justify the remainder without a separate premise;
- **boundary stress testing:** test cases immediately before and after a
  proposed threshold, and distinguish an administratively clear line from an
  intrinsic change in the thing being studied;
- **counterfactual discipline:** do not convert an administrative reason code,
  stated intention, or observed association into an outcome actually caused or
  prevented;
- **competing-premise bundles:** construct the strongest serious argument paths
  and expose the first empirical, normative, or authority premise where they
  diverge;
- **Dialectical Reset:** strip loaded framing, independently reconstruct the
  strongest serious case for each rival position from first principles as if
  each advocate were genuinely convinced, and only then compare objections,
  hidden premises, and discriminating evidence; and
- **cross-artifact reconciliation:** require the narrative, claim records,
  source ledger, quantitative snapshot, decision record, and tests to agree.

The proposed Dialectical Reset protocol is stricter than recording one generic
alternative explanation:

1. Produce a neutral, provenance-bound restatement without deleting material
   context, definitions, or uncertainty.
2. Build position A's strongest evidence/premise graph, value and authority
   bridges, falsifiers, and weakest link before exposing it to position B.
3. Build position B independently under the same evidence and burden rules;
   neither side inherits the other's framing or gets to answer a caricature.
4. Locate the first empirical, logical, definitional, boundary, normative, or
   authority premise where the graphs diverge.
5. Reconstruct both positions after their strongest mutual objections and name
   the evidence or test most likely to discriminate between them.
6. Do not manufacture parity. Fabricated evidence, category errors,
   unfalsifiable escape clauses, and undeclared value or authority premises
   remain visible as failures rather than receiving false balance.

Suggested Uriel mapping:

1. **Gate 1** should expose claim type, category scope, threshold meaning, and
   any conclusion that crosses from observation into value or authority
   without an explicit bridge.
2. **Gate 2** should test denominator and timing compatibility, preserve true
   missingness, distinguish direct measurements from proxies or modeled
   estimates, and require derived arithmetic to expose its inputs.
3. **Gate 3** should test exception-to-general-rule spillover, competing
   premise bundles, Dialectical Reset reconstruction, near-boundary
   counterexamples, counterfactual overreach, and less-harmful mechanisms that
   could satisfy the same function.

The best next implementation proof is a small domain-neutral Forge Trial
extension containing seeded cases for: `null` treated as zero; a broad proxy
substituted for a narrow endpoint; incompatible denominators compared; an
exception used as blanket justification; an administrative code described as
a prevented outcome; a conclusion that changes when its hidden premise is made
explicit; asymmetric burdens of proof; loaded rival framing; and manufactured
false equivalence. Detection behavior, reconstruction fidelity, premise
divergence, and framing symmetry must be measured before any corresponding
capability is promoted. Until then, retain this as a candidate method and do
not describe it as shipped automation.

## Latest verified local checks

The current checkout has passed:

```text
Python compilation: PASS
Full unit-test suite: PASS (exact count recorded in release-check.txt)
Privacy sweep: PASS
Portable zipapp: PASS
Wheel build: PASS
Source distribution build: PASS
Fresh virtual-environment wheel install: PASS
Installed `python -m uriel --version`: PASS
Installed `uriel --version`: PASS
Packaged schema inventory: PASS
Passing fixture submission audit: PASS
Blessing issue and standalone/live verification: PASS
Tampered Blessing refusal: PASS
Rough-question reminder persistence: PASS
`pip check`: PASS
```

Local checks do not establish the public multi-platform support matrix. The
workflow is configured for Python 3.9–3.14 on Linux, Windows, and macOS
(including an Apple Silicon smoke job); public CI must establish which exact
jobs passed for the candidate commit.

## Exact next actions

1. Run the privacy sweep and full release check against the exact candidate `main` commit.
2. Observe public CI for that exact commit across the configured matrix; do not infer it from workflow YAML.
3. Enable private vulnerability reporting in repository settings if the operator chooses to do so.
4. Create a new exact release-candidate tag only after review; never move the existing `v1.0.0-rc2` tag.
5. Open public issues for an independent threat-model review, a research-domain pilot, and false-positive/false-negative fixtures after operator approval.
6. Exercise the experimental Evidence Ingress/Data Desk lane with real domain fixtures and preserve its honest capability label until broader evidence supports promotion.
7. Keep grant, funding, and account-specific application drafts outside the public repository; publish only accurate acknowledgments or disclosures after an award.

## Rules a continuation agent must not violate

- Do not weaken a Gate or issue a fake Blessing to make a demo pass.
- Do not treat model output as evidence, novelty proof, or authority.
- Do not introduce mandatory cloud calls, telemetry, API keys, provider SDKs, or paid services.
- Do not dismiss rough wording as a bad idea; clarify it while preserving the original question.
- Do not rely on another paper's conclusion when the underlying primary datum can be cited and inspected.
- Do not hide missingness, exclusions, negative results, control mismatches, contradiction, uncertainty, or limitations.
- Do not add private paths, credentials, unpublished research content, identities, or adoption claims.
- Preserve Python 3.9 compatibility and zero runtime dependencies unless a documented major-version decision changes that boundary.

## Copy-paste continuation prompt for a compatible AI, web model session, or coding agent

```text
You are maintaining the Uriel open-source repository. Work directly in the extracted repository and do not redesign it from scratch.

Read, in order:
1. docs/MAINTAINER_HANDOFF.md
2. AGENTS.md
3. README.md
4. docs/ARCHITECTURE.md
5. docs/THREAT_MODEL.md
6. docs/LIMITATIONS.md
7. docs/RELEASE_CHECKLIST.md

Non-negotiable constraints:
- Treat the current repository's `main` worktree as canonical; do not create a second canonical copy.
- Python 3.9+ and zero runtime dependencies.
- Offline deterministic core; optional AI remains outside the trust boundary.
- No telemetry, silent network access, auto-sharing, or mandatory account.
- Never weaken root confinement, source membership, hash binding, audit Gate order, or Blessing prerequisites.
- Every blocker must remain friendly, specific, non-condescending, and offer exactly three repair paths.
- Preserve unresolved findings as durable reminders.
- Prefer exact primary artifacts and direct datapoints over inherited conclusions.
- Never invent users, stars, downloads, benchmarks, citations, grants, field validation, or venue acceptance.
- Add a regression test for every behavior change.

Before editing, verify the repository identity and run:
git status --short --branch
python scripts/release_check.py --full

After editing, run:
python scripts/release_check.py --full

If a terminal or agent is interrupted after the wheel and source archive were rebuilt, resume without discarding that work; Uriel verifies that the source fingerprint is unchanged:
python scripts/release_check.py --full --reuse-artifacts

Report changed files, exact tests run, failures, unresolved risks, and the current Git status. Do not claim Windows/macOS or Python 3.9–3.14 success unless public CI proves it. Do not push, tag, release, or delete/rewrite Git history without operator approval.
```

## Recovery artifacts

Keep an extracted source folder, a source ZIP, and a Git bundle until the GitHub repository and release are visible. These are independent recovery paths; a failed login, push, CI job, or model session cannot erase all three.

## Interruption safety

When Uriel receives SIGINT, SIGTERM, SIGHUP, or Windows SIGBREAK while an external check is active, it stops that child process tree and leaves `STATUS: INTERRUPTED` in `release-check.txt`. An abrupt power loss or forced OS kill cannot run cleanup code, but the last atomic checkpoint remains and the operating system releases the lock; inspect the report, then rerun the same command.
