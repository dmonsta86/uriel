# OpenAI Codex for Open Source application guide

_Checked against the official application page on 2026-08-06._

The program is for maintainers of **active open-source projects**. The form currently asks for first name, last name, ChatGPT-account email, public GitHub username, public repository URL, the maintainer’s role, a required “why this repository qualifies” answer capped at 500 characters, interest in Codex Security and/or API credits, a required OpenAI Organization ID, a required API-credit-use answer capped at 500 characters, and an optional “anything else” answer capped at 500 characters. Applications are reviewed on a rolling basis.

OpenAI says it looks for meaningful usage, broad adoption, **or clear importance to the software ecosystem**, plus evidence of active maintenance such as pull-request review, issue triage, and releases. Selected maintainers may receive six months of ChatGPT Pro including Codex, possible API credits, and conditional Codex Security access.

## Do not apply with invented traction

A new project can explain clear ecosystem importance, but it should not pretend to have users, stars, contributors, publication mandates, or maintenance workload it does not yet have. A stronger application has:

- a public repository and public maintainer profile;
- a tagged release and passing public CI;
- a clear security policy, contribution guide, issue templates, and roadmap;
- several real issues or pull requests showing active maintenance;
- at least one independent user, pilot, integration, or domain review;
- a precise explanation of how Codex would reduce actual maintainer work.

## Pre-application checklist

```text
[ ] Repository is public
[ ] GitHub profile is public
[ ] LICENSE is present
[ ] Public CI is green on the claimed matrix
[ ] Release 1.0.0-rc1 or later is tagged
[ ] README makes honest non-claims
[ ] Security and contribution policies are present
[ ] Issues/roadmap show active maintenance
[ ] No private paths, keys, names, emails, hostnames, or unpublished data remain
[ ] Application statements are supported by public repository evidence
```

## Draft role answer

Adapt only with true facts:

> I am Uriel’s primary maintainer and original systems architect. I define the deterministic audit policy, review contributions, triage integrity and usability issues, maintain releases and CI, and steward the security boundary between the offline verifier and optional AI adapters.

## Draft “why this repository qualifies” answer — new project, under 500 characters

> Uriel is a zero-runtime-dependency, offline-first research integrity harness that binds claims to exact artifacts, execution receipts, adversarial checks, and content-addressed certificates. Codex would help maintain cross-platform tests, review security-sensitive confinement changes, triage discipline-specific adapters, and make rigorous research tooling usable by people without institutional budgets. Adoption claims are intentionally limited to public evidence.

Current draft character count: **467**. Recount immediately before submission because edits change it:

```console
python -c "s=open('answer.txt',encoding='utf-8').read().strip(); print(len(s))"
```

## Draft API-credit-use answer — under 500 characters

> API credits would support opt-in open-source maintenance outside Uriel’s offline trust core: adversarial regression fixtures, cross-platform issue reproduction, schema-migration review, pull-request review, release checks, and source-discovery leads for human verification. Model output would never grant a Blessing; deterministic policy, hashes, reproducible receipts, and inspectable evidence remain authoritative.

Current draft character count: **416**.

## Optional “anything else” answer — under 500 characters

> Uriel is designed for low-resource users: stock Python, zero runtime dependencies, a portable offline build, and provider-neutral prompt export for free, local, or paid tools. It does not endorse providers and warns users not to disclose sensitive research. Codex support would strengthen maintainer workflows without making paid AI a requirement for Uriel users.

Current draft character count: **363**.

## Stronger later-stage answer template

Replace bracketed fields only with verifiable public facts:

> Uriel is maintained by [N] core maintainer(s), used by [VERIFIABLE USERS/PROJECTS], and has shipped [N] releases since [DATE]. Its offline verifier and optional AI boundary create recurring review work across [OS/PYTHON MATRIX], security issues, schemas, and research-domain adapters. Codex would reduce PR review, reproduce reported failures, harden confinement, and automate release evidence while preserving human accountability.

## How to use a Codex award responsibly

- Add regression tests before accepting generated security fixes.
- Keep model-generated changes visibly reviewed by a maintainer.
- Use Codex for issue reproduction, test generation, documentation drift, release checks, and bounded refactors.
- Never let Codex issue or approve a Uriel Blessing.
- Report API credits and program support transparently in project disclosures.
