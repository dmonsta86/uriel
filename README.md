<p align="center">
  <img
    src="docs/assets/the-forge-of-uriel/hero.png"
    alt="The Forge of Uriel: a vigilant scholar-smith tests a research idea at an anvil, surrounded by data readiness, evidence tracing, integrity gates, revision records, and provenance receipts."
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
### Open-source, offline-first research development and hardening

> **Is your IDEA strong enough to survive the forge?**
>
> A fair hearing for the idea. A hard test for the evidence.

The Forge of Uriel helps turn rough questions and existing projects into
structured, reproducible, submission-ready research.

It verifies data before analysis, traces important claims back to evidence,
preserves contradictions and limitations, exposes misleading framing and
unsupported conclusions, and turns failed checks into concrete repair and
submission paths.

It is not designed to make research sound stronger. It is designed to show
exactly how strong the research is—and what would make it stronger.

```text
Interpret generously.
Test rigorously.
Report honestly.
```

---

<!-- URIEL:SECTION:status:START -->
## Current release boundary

The Forge of Uriel **1.0.0-rc2** is a public release candidate of an open-source, offline-first research development and hardening toolkit.

```text
uriel --version
# uriel 1.0.0rc2
```

---

<!-- URIEL:SECTION:difference:START -->
## What makes it different

Most research tools handle one layer: literature search, writing, statistics,
citations, reproducibility, or review.

The Forge of Uriel is built to connect the chain.

### Give the idea its strongest fair hearing

Poor articulation is not evidence of poor thinking. Uriel preserves the
original question, clarifies the strongest testable version, records competing
interpretations, identifies hidden assumptions, and asks what evidence would
disprove the idea.

### Verify the data before drawing conclusions

Gate 0 prevents a data-dependent result from receiving authority until the
exact dataset generation has passed identity, sorting, normalization,
reconciliation, and staleness checks.

Before that, the honest answer is:

> **The result is not yet known.**

### Treat conclusions as claims—not inherited authority

A published conclusion, a prestigious author, a confident model, or a long
bibliography does not substitute for evidence.

Uriel asks:

```text
What exactly is being claimed?
Which artifact supports it?
Where is the supporting datapoint?
What contradicts it?
What assumptions does it depend on?
What remains unknown?
What would change the result?
```

### Challenge the finished work

The Three Gates test clarity, evidence, and adversarial integrity. Uriel looks
for omitted counter-evidence, hidden denominators, overgeneralization, causal
overreach, control mismatches, leakage, fragile assumptions, stale sources, and
summary language that exceeds the underlying result.

### Repair instead of merely criticizing

A failed check should not end with a vague rejection.

Uriel records what remains useful, identifies the smallest honest repair,
selects the strongest next move, prepares what can be prepared safely, and
states the exact condition for recheck.

---

<!-- URIEL:SECTION:intellectual-honesty:START -->
## Research should not be won by framing

Two failures repeatedly weaken research:

1. counter-evidence, null findings, limitations, or awkward datapoints disappear
   from the final story; and
2. the conclusion becomes broader or more certain than the underlying evidence
   supports.

Uriel makes those points durable. It records what was tested, what failed,
what was omitted, and what remains uncertain.

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

For the no-install single-file route, see
[`docs/GETTING_STARTED_FREE.md`](docs/GETTING_STARTED_FREE.md).

---

<!-- URIEL:SECTION:data-readiness:START -->
## Data Readiness (Gate 0)

Before analyzing data or drawing conclusions, run Data Readiness checks:

```text
uriel readiness
```

Gate 0 verifies dataset identity, ordering, normalization, missing value policies, and reconciliation. If Gate 0 fails, downstream analysis is blocked until data integrity is restored.

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
recomputes the clean summary and validates fixture integrity; it does not claim
that Uriel detected an issue unless a blind report is supplied and adjudicated.

```text
python scripts/check_forge_trial.py
```

The public Forge Method describes the workflow. A general automatic
milestone-closure engine remains planned.

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
- AI lenses are advisory and carry zero authority over deterministic gate decisions.
- A Gate or experimental Blessing reports that Uriel's recorded predicates passed for exact bound artifacts. It does not establish measurement validity, truth, journal acceptance, or peer consensus.

---

## Citation and License

Citation metadata are provided in [`CITATION.cff`](CITATION.cff). MIT License in [`LICENSE`](LICENSE).
