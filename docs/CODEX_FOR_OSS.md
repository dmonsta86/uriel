# Applying to OpenAI Codex for OSS

Last verified: **2026-08-06**.

The current Codex for Open Source program is for maintainers of active public open-source projects. OpenAI says it considers meaningful usage, broad adoption, **or clear importance to the software ecosystem**, together with evidence of active maintenance. Selected maintainers may receive six months of ChatGPT Pro including Codex, API credits, and possible conditional access to Codex Security.

Uriel is new, so the application must be honest about its stage. Do not invent stars, downloads, users, institutions, security incidents, or maintenance activity. A clear ecosystem need can be argued directly, but the repository should first show a real release, tests, issues, documented maintenance, and public work.

## Before applying

1. Publish with `PUBLISH_TO_GITHUB.cmd` or `scripts/publish_github.sh`; the publisher binds `pyproject.toml` and `CITATION.cff` to the authenticated account automatically.
2. Review `LICENSE`, `SECURITY.md`, privacy guidance, and all generated examples for private names, paths, tokens, unpublished data, and internal hostnames.
3. Push to a **public** GitHub repository and make the applicant's GitHub profile public.
4. Enable GitHub Actions and obtain a passing multi-platform CI run.
5. Create release candidate `v1.0.0-rc1` with the wheel, source archive, portable `.pyz`, and checksums; promote a stable tag only after review.
6. Open a small public roadmap and at least one good-first-issue or policy-discussion issue.
7. Document actual maintainer work: issue triage, review, releases, security response, tests, and user support.
8. Add only real metrics. For a pre-adoption repository, state “pre-release” or “newly released” rather than implying usage.
9. Have the OpenAI organization ID ready if requesting API credits.
10. Review the official form immediately before submission because fields and program terms can change.

## Current form fields

Prepare:

- first and last name;
- email associated with the ChatGPT account;
- public GitHub username;
- public repository URL;
- primary/core maintainer role;
- why the repository qualifies (maximum 500 characters);
- interest in Codex Security and/or project API credits;
- OpenAI organization ID;
- intended use of API credits (maximum 500 characters);
- anything else (maximum 500 characters).

Applications are reviewed on a rolling basis; the form says selected applicants are notified by email.

## Draft: maintainer role

> Primary maintainer. I designed the architecture, maintain the deterministic audit policy and security boundary, review contributions, triage issues, manage releases, and verify cross-platform tests and documentation.

Edit this so it describes work actually performed at submission time.

## Draft: why this repository qualifies — 481 characters

> I am the primary maintainer of Uriel, a new MIT-licensed, offline-first research integrity harness. It gives researchers and OSS maintainers deterministic claim/evidence validation, reproducible execution receipts, adversarial checks, and content-addressed audit packages without requiring paid AI. The project targets a clear ecosystem gap: inspectable research provenance and honest, accessible pre-submission review. Current usage metrics: [ADD REAL METRICS OR SAY PRE-RELEASE].

Before pasting, replace the bracketed text. A clean early-stage ending is:

> The first public release is new; adoption evidence will be reported as it becomes available.

That replacement may require shortening another sentence to stay under 500 characters.

## Draft: API-credit use — 450 characters

> I would use credits only for Uriel's open-source maintenance: adversarial review of pull requests, regression-fixture generation, cross-platform failure analysis, security and confinement review, documentation checks, release notes, issue triage, and evaluation of optional review adapters. AI output would remain outside Uriel's deterministic trust boundary; citations, tests, security findings, and release artifacts would be verified before merge.

## Draft: anything else — 443 characters

> Uriel is intentionally useful with zero runtime dependencies and no AI account, so researchers with limited money or connectivity are first-class users. Optional model support is provider-neutral, privacy-aware, and default-deny for sensitive work. A Uriel Blessing is narrowly defined as a verifiable policy pass—not peer review, proof of truth, or editorial approval. Roadmap and maintenance evidence: [LINK TO ISSUES/RELEASES/CONTRIBUTING].

## Strong application evidence to build next

- passing Linux, macOS, and Windows CI;
- tagged releases and signed checksums;
- issues showing policy discussion and responsive maintenance;
- external users reproducing the example Blessing;
- integrations or citations from research/software projects;
- documented security and root-confinement review;
- benchmarks that report both detected defects and false positives;
- contributor activity and clear governance.

## Git publication

Use [the publishing guide](PUBLISH_TO_GITHUB.md). On Windows, extract the GitHub-ready source ZIP and double-click `PUBLISH_TO_GITHUB.cmd`. It uses GitHub's official browser sign-in, creates the public repository, configures repository metadata, runs local checks, commits, and pushes without asking for a password or token.

After the public CI matrix is green, create `v1.0.0-rc1` as described in [the release procedure](RELEASE.md).
