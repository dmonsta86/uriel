# Maintainer handoff and durable continuation point

Checked locally on **2026-08-06**.

This file is the shortest authoritative continuation point for a human or coding agent. The larger design rationale lives in `README.md`, `docs/ARCHITECTURE.md`, `docs/THREAT_MODEL.md`, `docs/LIMITATIONS.md`, and `AGENTS.md`.

## Current implementation state

Uriel 1.0.0 is an initial release candidate with:

- a Python 3.9+ standard-library-only runtime;
- root confinement and link/reparse traversal refusal;
- atomic state writes, SHA-256 source manifests, SQLite indexing, and a hash-chained ledger;
- shell-free workload receipts;
- rough-question intake that preserves the original wording;
- deterministic Novelty & Clarity, Evidence & Citation, and Adversarial Integrity gates;
- persistent repair reminders with exactly three options for blockers;
- hash-bound optional review imports and privacy-aware prompt export;
- content-addressed Blessing packages, printable SVG/text certificates, QR payloads, and a standalone verifier;
- PowerShell and POSIX launchers, OpenCode integration, CI, release, issue, security, and contribution assets.

## Latest verified local checks

The current checkout has passed:

```text
Python compilation: PASS
Unit tests: 27/27 PASS
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

Local checks do not establish the public multi-platform support matrix. GitHub CI must establish the advertised Python 3.9-3.12 matrix on Linux, Windows, and macOS.

## Exact next actions

1. Confirm every GitHub Actions job is green on Linux, Windows, and macOS for each advertised Python version.
2. Run the privacy sweep and full release check against the exact public `main` tree.
3. Enable private vulnerability reporting in the repository security settings.
4. Create `v1.0.0-rc1`; the tag workflow should attach the wheel, source distribution, portable archive, checksums, and release-check transcript.
5. Open public issues for an independent threat-model review, a research-domain pilot, and false-positive/false-negative fixtures.
6. Keep grant, funding, and account-specific application drafts outside the public repository; publish only accurate acknowledgments or disclosures after an award.

## Rules a continuation agent must not violate

- Do not weaken a Gate or issue a fake Blessing to make a demo pass.
- Do not treat model output as evidence, novelty proof, or authority.
- Do not introduce mandatory cloud calls, telemetry, API keys, provider SDKs, or paid services.
- Do not dismiss rough wording as a bad idea; clarify it while preserving the original question.
- Do not rely on another paper's conclusion when the underlying primary datum can be cited and inspected.
- Do not hide missingness, exclusions, negative results, control mismatches, contradiction, uncertainty, or limitations.
- Do not add private paths, credentials, unpublished research content, identities, or adoption claims.
- Preserve Python 3.9 compatibility and zero runtime dependencies unless a documented major-version decision changes that boundary.

## Copy-paste continuation prompt for Gemini, DeepSeek, or another coding agent

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
- Python 3.9+ and zero runtime dependencies.
- Offline deterministic core; optional AI remains outside the trust boundary.
- No telemetry, silent network access, auto-sharing, or mandatory account.
- Never weaken root confinement, source membership, hash binding, audit Gate order, or Blessing prerequisites.
- Every blocker must remain friendly, specific, non-condescending, and offer exactly three repair paths.
- Preserve unresolved findings as durable reminders.
- Prefer exact primary artifacts and direct datapoints over inherited conclusions.
- Never invent users, stars, downloads, benchmarks, citations, grants, field validation, or venue acceptance.
- Add a regression test for every behavior change.

Before editing, run:
python scripts/release_check.py --full

After editing, run:
python scripts/release_check.py --full

If a terminal or agent is interrupted after the wheel and source archive were rebuilt, resume without discarding that work; Uriel verifies that the source fingerprint is unchanged:
python scripts/release_check.py --full --reuse-artifacts

Report changed files, exact tests run, failures, unresolved risks, and the current Git status. Do not claim Windows/macOS or Python 3.9–3.12 success unless public CI proves it.
```

## Recovery artifacts

Keep an extracted source folder, a source ZIP, and a Git bundle until the GitHub repository and release are visible. These are independent recovery paths; a failed login, push, CI job, or model session cannot erase all three.

## Interruption safety

When Uriel receives SIGINT, SIGTERM, SIGHUP, or Windows SIGBREAK while an external check is active, it stops that child process tree and leaves `STATUS: INTERRUPTED` in `release-check.txt`. An abrupt power loss or forced OS kill cannot run cleanup code, but the last atomic checkpoint remains and the operating system releases the lock; inspect the report, then rerun the same command.
