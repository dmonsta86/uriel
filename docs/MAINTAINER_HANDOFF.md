# Maintainer handoff and durable continuation point

Checked locally on **2026-08-08** at canonical `main` HEAD
`14ba9606e8989a710356132fa0366c4a16bfa962`.

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
- PowerShell and POSIX launchers, compatible external agent integration, CI, release, issue, security, and contribution assets.

The current `main` commit is a post-tag maintenance revision. The existing
`v1.0.0-rc2` tag remains immutable; no release claim should combine its assets
with later `main` changes until a new exact candidate is reviewed and tagged.

## Latest verified local checks

The current checkout has passed:

```text
Python compilation: PASS
Unit tests: 263/263 PASS
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
6. Implement the local Evidence Ingress/Data Desk lane while preserving the planned capability label until executable evidence closes it.
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

## Copy-paste continuation prompt for compatible AI, web AI session, or another coding agent

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
- The canonical product line is project 215 in the `Scientific-Institutions` repository on `main`; do not create a second canonical copy.
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
