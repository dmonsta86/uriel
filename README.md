<p align="center">
  <img
    src="docs/assets/the-forge-of-uriel/hero.png"
    alt="The Forge of Uriel shown as a vigilant wingless scholar-smith testing a research idea at an anvil, surrounded by idea formation, Data Readiness, deterministic sorting, evidence tracing, counter-evidence, integrity gates, repair, submission, and verification receipts."
    width="100%"
  >
</p>

<p align="center">
  <a href="https://github.com/dmonsta86/uriel/actions/workflows/ci.yml">
    <img alt="CI" src="https://github.com/dmonsta86/uriel/actions/workflows/ci.yml/badge.svg">
  </a>
  <img alt="Status: public beta" src="https://img.shields.io/badge/status-public%20beta-f59e0b">
  <img alt="Python 3.9+" src="https://img.shields.io/badge/python-3.9%2B-3776AB">
  <a href="LICENSE">
    <img alt="License: MIT" src="https://img.shields.io/badge/license-MIT-22c55e">
  </a>
  <img alt="Runtime dependencies: zero" src="https://img.shields.io/badge/runtime%20dependencies-0-0f766e">
</p>

<p align="center">
  🌐 <strong>Languages:</strong>
  <a href="README.md">English</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.pt-BR.md">Português (Brasil)</a> |
  <a href="README.zh-Hans.md">简体中文</a> |
  <a href="README.ar.md">العربية</a> |
  <a href="README.hi.md">हिन्दी</a> |
  <a href="README.ja.md">日本語</a>
</p>

# The Forge of Uriel

<!-- URIEL:SECTION:mission:START -->
### Offline-first research assurance for evidence-bound work

> **Is your IDEA strong enough to survive the forge?**
>
> A fair hearing for the idea. A hard test for the evidence.

The Forge of Uriel is an offline-first, zero-runtime-dependency Python CLI for
researchers, reviewers, and maintainers who need a verifiable local record. It
binds project state to hashes, traces material claims to source artifacts,
keeps counter-evidence and limitations visible, and turns failed checks into
specific repair paths.

Use it to answer **what is supported, what is not, and what should happen
next**. Core verification needs no account, cloud service, or AI. Uriel is not
a truth machine, autonomous researcher, statistics package, or substitute for
domain expertise, ethics review, legal review, or scientific judgment. Neither
software nor AI output grants research authority.

**First time here?** Jump to the [Quick Start](#quick-start), then review the
[capability status](docs/CAPABILITY_STATUS.md) and [known limitations](docs/LIMITATIONS.md).

```text
Interpret generously.
Test rigorously.
Report honestly.
```

---

<!-- URIEL:SECTION:status:START -->
## Current release boundary

The Forge of Uriel **1.0.0-rc2** is the current tagged public release candidate;
`main` contains the latest reviewed changes. The deterministic project core and
packaging are shipped. Data Readiness and the Three Gates are beta. Data Desk,
the operational Forge, AI handoffs, and Blessing packages remain experimental.

This is public-beta software, not infrastructure that should be mandated for
publication. It still needs broader domain trials, usability evidence, and
independent security review. See the exact [capability status](docs/CAPABILITY_STATUS.md),
[known limitations](docs/LIMITATIONS.md), and [public roadmap](docs/ROADMAP.md).

```text
uriel --version
# uriel 1.0.0rc2
```

---

<!-- URIEL:SECTION:difference:START -->
## What makes it different

Uriel connects work that is usually split across notebooks, prose, data checks,
and review:

1. preserve the original question and state its strongest testable form;
2. bind the exact project and data generation before analysis;
3. map each material claim to direct evidence, counter-evidence, and limits;
4. challenge overreach and leave a reproducible repair or continuation path.

A publication, prestigious author, confident model, or long bibliography does
not substitute for evidence. Uriel asks:

```text
What exactly is being claimed?
Which artifact supports it?
Where is the supporting datapoint?
What contradicts it?
What assumptions does it depend on?
What remains unknown?
What would change the result?
```

Gate 0 blocks authority for a data-dependent result until one exact generation
passes its declared identity, ordering, reconciliation, and staleness checks.
The Three Gates then test scope, direct evidence, and adversarial integrity.
Until the relevant checks pass, the honest result remains **unknown**.

Failures are durable and constructive: they identify what remains useful, the
smallest honest repair, and the exact recheck condition. The experimental
continuation and Next Move mechanics live in the [Forge Method](docs/FORGE_METHOD.md)
and [Forge Forward guide](docs/FORGE_FORWARD.md), including their explicit
no-authority limits.

---

<!-- URIEL:SECTION:intellectual-honesty:START -->
## Research should not be won by framing

Uriel keeps counter-evidence, null findings, exclusions, limitations, and
uncertainty attached to the record. It also flags conclusions whose scope or
certainty exceeds their declared evidence. The checks make those facts easier
to inspect; they do not decide whether the underlying science is true.

---

<!-- URIEL:SECTION:quick-start:START -->
## Quick Start

From a repository checkout, install without runtime dependencies or an
isolated network build:

```text
python -m pip install --no-deps --no-build-isolation .
uriel start --root ../my-study --kind new_idea --title "My study" --question "What would change my conclusion?"
uriel status --root ../my-study
uriel verify --root ../my-study
```

Distribution package: `uriel-research`

Python import and CLI command: `uriel`

What to expect:

- `start` creates a confined local project and lists its onboarding files;
- `status` reports the project identity, offline mode, ledger state, and open
  reminders;
- `verify` re-hashes the declared source, ledger, and receipts and reports
  `"verified": true` when those exact records are internally consistent.

These commands do not upload the project, call a model, or establish that a
scientific conclusion is correct. The verified path has been exercised from a
fresh installed distribution on synthetic temporary projects.

For the no-install single-file route, see
[`docs/GETTING_STARTED_FREE.md`](docs/GETTING_STARTED_FREE.md).

For deeper use, continue with [Is Uriel right for me?](docs/getting-started/IS_URIEL_RIGHT_FOR_ME.md),
the [architecture](docs/ARCHITECTURE.md), [threat model](docs/THREAT_MODEL.md),
[Three Gates](docs/THREE_GATES.md), and [maintainer playbook](docs/MAINTAINER_PLAYBOOK.md).

---

<!-- URIEL:SECTION:data-readiness:START -->
## Data Readiness (Gate 0)

The experimental local `uriel data` workflow can seal and structurally inspect
one explicitly selected UTF-8 CSV, TSV, JSON, JSONL, text, or Markdown file.
It preserves exact bytes and conflicts, executes no formulas, guesses no units
or meanings, creates no scientific findings, and grants no Gate 0 authority.
Gate 0 begins only after you declare record identity for one exact generation.

After `uriel data inspect` returns a generation ID, create and check its
generation-bound SortSpec:

```text
uriel readiness init-sort-spec --root ../my-study --generation <GENERATION_ID> --keys id
uriel readiness check --root ../my-study --generation <GENERATION_ID>
uriel readiness status --root ../my-study --generation <GENERATION_ID>
```

The readiness receipt binds raw lineage, parser and policy versions, ordering,
duplicate/null rules, analysis plan, and exact SortSpec. Missing, stale,
tampered, or ambiguous state blocks the result. Detailed contracts and limits
are in [Known Limitations](docs/LIMITATIONS.md).

---

<!-- URIEL:SECTION:forge-forward:START -->
## Continue an incomplete Forge run

The experimental Forge commands operate on exact content-addressed paths--never
on an ambiguous mutable "latest" run:

```text
uriel forge continue --root ../my-study --snapshot <EXACT_SNAPSHOT> --request artifacts/forge-forward.json
uriel forge verify-continuation --root ../my-study --packet <EXACT_CONTINUATION>
uriel forge export --root ../my-study --snapshot <EXACT_SNAPSHOT> --destination exports/review-copy
uriel forge verify-export --root ../my-study --manifest exports/review-copy/manifest.json --snapshot <EXACT_SNAPSHOT>
```

Continuation packets remain private under ignored `.uriel/forge/` state.
Sanitized exports contain generated structural metadata, not evidence bodies,
and still require human review before publication. See the
[Forge Method](docs/FORGE_METHOD.md) for request shape, scoring, blocker proof,
verification, and refusal boundaries.

---

<!-- URIEL:SECTION:gates:START -->
## The Three Gates

### Gate 1 — Scope and Claim Language

Evaluates whether central claims are precisely bounded, terminology is consistent, and overgeneralized or causal leaps are eliminated.

### Gate 2 — Data Readiness and Direct Evidence

Requires that every material claim is backed by direct, traceable evidence and verified data generations.

### Gate 3 — Adversarial Robustness and Limitations

Exposes rival explanations, framing biases, omitted counter-evidence, and applicability limits.

---

<!-- URIEL:SECTION:blessing:START -->
## The Blessing of Uriel

The Blessing of Uriel is an experimental, content-addressed attestation package.
It binds an exact project generation to Uriel's recorded gate decisions,
receipts, limitations, and independent verifier recomputation.

A Blessing means those recorded predicates passed for those exact bound
artifacts. It is not independent scientific validation, a cryptographic author
signature, peer review, or proof that the underlying measurements are true.

---

<!-- URIEL:SECTION:ai:START -->
## Use Uriel with or without AI

### Maintainer note

The Forge of Uriel was developed with extensive use of GPT-5.6 Sol in `ultra`
mode, which the maintainer recommends for its deepest long-horizon research and
adversarial passes.

That is an experience report—not a dependency, exclusive integration, privacy
endorsement, guarantee, or substitute for deterministic verification. Other
capable AI systems can be used.

### A compatible AI

A compatible AI may help clarify, organize, draft, and critique.

It may not:

```text
mark Data Readiness PASS
pass an integrity gate
change publication authority
override a deterministic failure
issue a Blessing
```

---

<!-- URIEL:SECTION:privacy:START -->
## Safety and privacy

Core commands are local and make no telemetry, background upload, provider, or
account call. Optional external AI use is a separately acknowledged advisory
path; its output cannot pass a Gate or issue a Blessing. Review the project's
classification and disclosure boundary before exporting anything.

Uriel is designed around:

```text
read-only defaults
exact-root confinement
explicit consent
verified managed copies
immutable generations
```

---

<!-- URIEL:SECTION:trials:START -->
## The Forge Trials

The bundled synthetic Forge Trial is a reproducible fixture with 24 sealed
answer-key issues and a 100-point adjudication rubric. Its release check
validates fixture integrity; it does not claim that Uriel detected an issue
unless a blind report is supplied and adjudicated.

```text
python scripts/check_forge_trial.py
```

The public Forge Method describes the workflow. Its experimental local
run/state/verifier spine is now available:

```text
uriel forge init --root PROJECT --request INIT.json
uriel forge transition --root PROJECT --snapshot EXACT.json --to-state SCOPED --rationale "Scope reviewed"
uriel forge verify --root PROJECT --snapshot EXACT.json
```

It writes immutable private snapshots and grants no upstream authority.
Canonical `main` also provides evidence-bound continuation packets,
blocker-proof checks, transparent Next Move ranking, and metadata-only
sanitized exports. These paths remain experimental and independently
verifiable.

See [`docs/FORGE_TRIALS.md`](docs/FORGE_TRIALS.md) and [`benchmarks/forge_trials/synthetic-001/`](benchmarks/forge_trials/synthetic-001/).

---

<!-- URIEL:SECTION:community:START -->
## Contributing

Contributions that improve correctness, portability, accessibility, security, documentation, translations, and research workflows are welcome.

Start with:

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SUPPORT.md`](SUPPORT.md)
- [`SECURITY.md`](SECURITY.md)

---

<!-- URIEL:SECTION:limitations:START -->
## Known Limitations

The Forge of Uriel is built to enforce intellectual honesty and evidence lineage, but it has defined boundaries:

- Uriel cannot invent missing data or supply lab measurements.
- Data Desk reports bounded structural and lexical observations. It is not a
  statistics engine, semantic validator, or substitute for inspecting source
  measurements and methods.
- AI lenses are advisory and carry zero authority over deterministic gate decisions.
- A Gate or experimental Blessing reports that Uriel's recorded predicates passed for exact bound artifacts. It does not establish measurement validity, truth, journal acceptance, or peer consensus.

---

## Citation and License

Citation metadata are provided in [`CITATION.cff`](CITATION.cff). MIT License in [`LICENSE`](LICENSE).
