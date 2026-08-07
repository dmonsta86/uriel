<p align="center">
  <img
    src="docs/assets/uriel-forge-banner.png"
    alt="Uriel Forge — evidence-bound research development and assurance"
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

# Uriel Forge

> **Notice**: 本文档为AI复核翻译版本（AI_SECOND_PASS_REVIEWED）。非常欢迎母语人士提供校对与修正。

### Forge rough questions into research that can show its work.

> **Every idea deserves its strongest fair hearing.**  
> **Every claim must survive its strongest fair challenge.**

Uriel Forge is an offline-first research development and assurance toolkit for
people starting with either a rough question or an existing project.

It helps clarify what is actually being claimed, preserves the original idea,
checks whether data are ready before analysis, binds important claims to
evidence, exposes contradictions and material omissions, creates concrete
repair paths, and prepares durable research and submission artifacts.

Its job is not to make work sound certain. Its job is to make the evidence
traceable, the uncertainty honest, and the next move clear.

```text
Interpret generously.
Test rigorously.
Report honestly.
```

---

## Why Uriel exists

Research can fail long before a final statistical test.

A worthwhile idea can be ignored because it was expressed badly. A weak claim
can survive because it was expressed beautifully. A project can stall because
a tool identified a problem but did not explain how to repair it.

Uriel is built to resist all three failures:

1. **Develop the idea before judging it.**  
   Poor wording is not evidence of poor thinking.

2. **Verify the evidence before trusting the claim.**  
   Prestige, confidence, citation volume, and polished prose do not create
   scientific authority.

3. **Turn every nonterminal failure into a path forward.**  
   A blocked result should say what remains useful, what is missing, what Uriel
   already prepared, and exactly what would unblock the work.

> **Intellectual dishonesty—omitting disconfirming evidence, posturing with decorative prose, or handwaving unlikely edge cases—is the Achilles' heel of academic research. Uriel Forge undoes this intentionally: it strips framing, forces claims to bind directly to primary evidence, preserves counter-evidence, and proves exact-version reproducibility before any conclusion is accepted.**

> **Infallibility is the north star. Auditable honesty is the contract.**

Uriel does not claim absolute truth. It aims for the strongest practically
attainable assurance within the declared scope—and fails closed when a critical
link cannot be verified.

---

## What Uriel can help you do

| Starting point | What Uriel does | What you receive |
|---|---|---|
| A rough question | Preserves the original wording, reconstructs the strongest testable interpretation, records rivals and disconfirming evidence | A seed brief, clarified question, minimum useful test, and roadmap |
| An existing project | Performs metadata-first preflight, supports read-only review, and can build a verified working copy | A project map, gap register, source-invariance receipt, and integration plan |
| A dataset | Requires record identity and a versioned sorting specification before analysis | A Data Readiness receipt, normalized generation, blockers, and recheck path |
| A paper or proposal | Maps claims to artifacts, evidence, uncertainty, framing, omissions, and contrary results | A repair packet, limitations, evidence requests, and stronger scoped claims |
| Reviewer or editor feedback | Converts every actionable item into a tracked revision or production obligation | A response matrix, revision plan, form guide, packet, and deterministic archive |
| A substantial milestone | Applies the Forge Method contract for requirements, blockers, evidence, tests, and closure | A verifiable closure bundle once the Forge engine ships |

---

## Current audited capability status

This table reflects the independently audited public-beta snapshot. It should
change only when the exact public commit earns a stronger status.

| Capability | Status | What that means today |
|---|---|---|
| Deterministic core, manifests, ledger, receipts, and verification | **SHIPPED** | Independently built, installed, and exercised through `init`, `status`, and `verify` on Linux |
| Wheel, source distribution, and portable `.pyz` | **SHIPPED** | Built and executed in a clean environment |
| Zero-install Lens | **BETA** | Packaged and tested; effectiveness across model families has not been benchmarked |
| New-project intake, read-only review, and safe-copy controls | **BETA** | Strong unit coverage; native end-to-end receipts are still being expanded |
| Gate 0 — Data Readiness | **BETA** | Real implementation and tests; public commands and native workflows are under final hardening |
| Three-Gate audit and repair packets | **BETA** | Useful audit engine exists; positive check coverage is being tightened |
| Workbench, bounded bursts, reminders, and next-step packets | **BETA** | Implemented and exercised in an installed workflow |
| Submission lifecycle | **BETA** | Decision import, planning, response packets, guidance, verification, and archives exist |
| Assurance-depth and Evidence Microscope helpers | **EXPERIMENTAL** | Library components exist; a complete public proof-bundle workflow is not yet shipped |
| Strict Blessing issuance | **EXPERIMENTAL — DISABLED UNTIL HARDENED** | Mandatory checks must prove every PASS with direct evidence; silence may never count as proof |
| Evidence Ingress and full Data Desk | **PLANNED** | Designed, not shipped in the audited snapshot |
| Deterministic Forge Method engine | **PLANNED** | The contract and documentation exist; the engine, CLI, schemas, and verifier are still to be implemented |
| Local-model runtime | **PLANNED** | Provider-neutral design exists; no runtime ships yet |
| Desktop GUI and native installers | **PLANNED** | Not part of the audited public package |

The project is intentionally honest about this boundary: **a specification is
not a shipped capability, and green unit tests are not the same as native
end-to-end proof.**

---

## The research path

```text
Rough question or existing project
        ↓
Clarify the idea without replacing it
        ↓
Build the research plan and roadmap
        ↓
Inventory evidence and prepare the data
        ↓
Gate 0 — Data Readiness
        ↓
Map claims to evidence, uncertainty, framing, and omissions
        ↓
Build the manuscript and submission packet
        ↓
Gate 1 — Novelty and Clarity
Gate 2 — Evidence and Citation
Gate 3 — Adversarial Integrity
        ↓
Repair, narrow, pivot, refute, or pass
        ↓
Forge milestone closure
        ↓
Possible Blessing for the exact research version
```

Uriel does not force a grand conclusion. A useful outcome may be a narrower
claim, a better measurement plan, a replication, a negative result, a methods
paper, a dataset, a software tool, or a precise demonstration that the original
claim does not survive.

---

## Quick start

### Install from the repository

```bash
git clone https://github.com/dmonsta86/uriel.git
cd uriel
python -m pip install .
uriel --version
```

Uriel has no third-party runtime dependencies. Development and build tools are
optional extras.

### Start with a question

```bash
mkdir my-study
cd my-study

uriel init . \
  --title "Cold-weather battery life" \
  --question "Why does battery life appear to drop faster in the cold?"

uriel seed \
  "Why does battery life appear to drop faster in the cold?" \
  --root . \
  --output seed.md

uriel workbench init \
  --root . \
  --question "Why does battery life appear to drop faster in the cold?"

uriel workbench next --root . --output NEXT_PROMPT.txt
uriel status --root .
```

Uriel preserves the original question and writes durable state rather than
leaving the project trapped inside one chat session.

### Review an existing project without changing it

```bash
uriel preflight --root /path/to/project

uriel consent set \
  --root /path/to/project \
  --mode read_only \
  --confirm explicit_user

uriel workspace review \
  --root /path/to/project \
  --output /path/to/separate-review-workspace
```

Read-only means no source edits. Sensitive filenames, links, reparse points,
cloud-synced paths, and unexpected scope are surfaced rather than silently
accepted.

### Prepare tabular data before analysis

```bash
uriel readiness init-sort-spec \
  --root . \
  --dataset data/records.csv \
  --keys record_id

uriel readiness check \
  --root . \
  --dataset data/records.csv

uriel readiness status \
  --root . \
  --dataset data/records.csv
```

Current Gate 0 support covers CSV, TSV, and JSONL. Record identity must be
declared. Row order is not accepted as identity.

---

## Data before conclusions

No data-dependent conclusion is authoritative until the exact input generation
has passed Gate 0.

Changing any material:

```text
data
record identity
schema
sort rule
duplicate policy
join
exclusion
transformation
analysis plan
```

invalidates dependent readiness and conclusions.

Before readiness, the correct answer is neither hopeful nor discouraging:

> **The result is not yet known.**

Uriel does not confuse:

- more citations with independent evidence;
- more rows with valid data;
- more decimals with accuracy;
- statistical significance with sound design;
- model agreement with verification;
- confident language with stronger support.

---

## The Three Gates

### Gate 1 — Novelty and Clarity

Is the exact question or contribution:

- clearly stated;
- scoped;
- testable;
- internally consistent;
- operationally defined;
- honestly framed;
- distinguishable from prior work within a declared search boundary?

Gate 1 must first attempt a fair reconstruction. Poor articulation alone is not
a valid reason to discard an idea.

### Gate 2 — Evidence and Citation

Does every material claim map to evidence that:

- actually supports it;
- is direct or primary where reasonably available;
- has an exact artifact and location;
- preserves conflicting, null, and negative evidence;
- represents scope and uncertainty honestly;
- is current and reproducible?

Another paper's conclusion is not a substitute for the evidence beneath it.

### Gate 3 — Adversarial Integrity

Does the work survive:

- credible rival explanations;
- confounders and control mismatches;
- leakage and circular evaluation;
- edge cases and sensitivity checks;
- omitted limitations;
- changed assumptions;
- reviewer counterarguments;
- independent verification?

A failed gate is a project state—not a judgment of the person.

Uriel's constructive failure path should answer:

```text
What failed?
Why does it matter?
What remains useful?
What is the smallest honest repair?
What is the strongest next move?
What exact condition allows recheck?
```

---

## The Blessing of Uriel

A Blessing is intended to be Uriel's strictest exact-version research audit.

Its target contract requires:

```text
Gate 0 — Data Readiness
Gate 1 — Novelty and Clarity
Gate 2 — Evidence and Citation
Gate 3 — Adversarial Integrity
Independent verification
Certificate binding
Zero unresolved blockers
```

A Blessing does **not** mean:

- absolute or permanent truth;
- universal applicability;
- guaranteed publication;
- replacement for peer review, ethics review, or specialist judgment;
- immunity from later evidence.

### Current safety status

Strict Blessing issuance is **experimental and should remain disabled** in the
audited public-beta snapshot. The ongoing hardening work is replacing
absence-of-failure defaults with explicit, check-specific positive evidence.

Historical packages may remain verifiable, but they must not be confused with
the final strict certificate contract.

---

## The Forge Method

The public product is named **Uriel Forge** because its purpose is to turn
unfinished material into work that has been shaped, tested, and proved.

The dedicated Forge Method engine is currently planned. Its contract is already
defined:

1. State what the milestone must deliver.
2. State what is out of scope.
3. Define hard and soft requirements.
4. Record blockers, ownership, and completion conditions.
5. Divide work into small, testable packages.
6. Attach evidence to every closure claim.
7. Run the planned tests.
8. Run an independent attempt to refute the positive result.
9. Close the exact version—or preserve a precise path forward.

A Forge result answers:

```text
What did we intend to finish?
What actually changed?
What evidence proves it?
What remains incomplete?
Is this exact version ready?
```

Forge closure will remain separate from the Blessing: one proves milestone
completion; the other proves an exact research artifact passed Uriel's strict
research-integrity gates.

See [The Forge Method](docs/FORGE_METHOD.md).

---

## Concise in front, complete underneath

The default output should be a Decision Card:

```text
Status
What is established
What is not established
Why
Strongest next move
What Uriel already prepared
What is needed from the user
What would change the result
```

Behind it, Uriel preserves the proof:

- claim/evidence maps;
- manifests and hashes;
- data and transformation lineage;
- uncertainty and reversal conditions;
- framing and omission registers;
- execution receipts;
- adversarial results;
- repair and submission packets.

The front end should be calm and readable. The backend should be exhaustive and
verifiable.

---

## Use Uriel with or without AI

### No AI

The authoritative core is local and deterministic. It can manage project state,
manifests, receipts, readiness, evidence records, repair packets, Workbench
state, and submission state without an online model.

### Any compatible AI

A managed workspace can generate provider-neutral files such as:

```text
URIEL_AI_ENTRY.md
COPY_THIS_TO_YOUR_AI.txt
NEXT_PROMPT.txt
```

A compatible AI may help clarify, organize, draft, and propose. It receives no
scientific authority.

### Compatible local model

A future optional local-model layer is designed for bounded, project-local
assistance on suitable hardware. It is not part of the audited public package
yet.

### Maintainer note

Uriel grew out of the workflow the maintainer used while developing a first
paper that was later published.

For the deepest long-horizon Forge, assurance, and adversarial passes, the
maintainer has found
[GPT-5.6 Sol with `ultra` mode](https://openai.com/index/gpt-5-6/)
especially effective.

That is an experience report and an optional recommendation—not a dependency,
exclusive integration, privacy endorsement, guarantee, or substitute for
Uriel's deterministic checks. Other compatible AIs can be used.

Before uploading unpublished or sensitive work to any web service, review its
retention, training, and privacy terms.

---

## Help keep Uriel strong

Found a bug, a missed issue, or a false finding? Please report it.

| What you found | Where to report |
|---|---|
| Software behaved incorrectly | **Bug report** |
| Uriel flagged something unsupported | **Audit false positive** |
| Uriel missed a known issue | **Audit miss / false negative** |
| Documentation is wrong or unclear | **Documentation correction** |
| A translation needs improvement | **Translation correction** |
| A bounded improvement idea | **Feature proposal** or **Discussions** |
| A public demonstration case | **Forge Trial proposal** |
| A security vulnerability | **Private security report — never a public issue** |

Good reports include the exact Uriel version, platform, installation type,
public command, expected and actual behavior, reproduction steps, and a minimal
synthetic or sanitized fixture.

A scientific-audit disagreement should state its ground-truth basis. Another
model's opinion is not enough by itself.

Uriel's maintenance standard is the same as its research standard:

```text
preserve the evidence
admit false positives
record misses
publish the fix
keep the regression test
```

---

## Safety model

Uriel is designed around:

```text
read-only defaults
exact-root confinement
explicit consent
verified managed copies
immutable generations
atomic writes
content hashes
no hidden network
no telemetry
no credential access
bounded AI-facing packets
prompt-injected content treated as untrusted data
```

Keep an independent backup of important work. A safety-oriented workflow is not
a substitute for backup, ethics review, legal review, or domain expertise.

Read the [Threat Model](docs/THREAT_MODEL.md),
[Security Policy](SECURITY.md), and
[Known Limitations](docs/LIMITATIONS.md).

---

## Project map

| Area | Documentation |
|---|---|
| Product contract | [Project QRD](docs/PROJECT_QRD.md) |
| Architecture | [Architecture](docs/ARCHITECTURE.md) |
| Research lifecycle | [Lifecycle](docs/LIFECYCLE.md) |
| Three Gates | [Three Gates](docs/THREE_GATES.md) |
| Blessing contract | [Blessing Specification](docs/BLESSING_SPEC.md) |
| Forge closure | [Forge Method](docs/FORGE_METHOD.md) |
| AI and privacy | [AI Usage and Privacy](docs/AI_USAGE_AND_PRIVACY.md) |
| Compatibility | [Compatibility](docs/COMPATIBILITY.md) |
| Security | [Security Policy](SECURITY.md) |
| Contribution | [Contributing](CONTRIBUTING.md) |

---

## Why the name?

Uriel is associated with light, wisdom, and illumination. The project uses that
symbolism in a secular way.

The forge is the central image:

```text
raw question
→ clear claim
→ prepared evidence
→ adversarial testing
→ honest result
→ durable proof
```

---

## Principles

- Every idea gets a fair chance to become clear.
- No claim gets a free pass once it is.
- Data are verified before they are interpreted.
- Primary evidence is preferred over inherited conclusions.
- Missing evidence remains missing.
- Contradictory evidence remains visible.
- Before Data Readiness, the result is not yet known.
- A failed state must produce a useful path forward.
- Concise explanations must preserve the full truth boundary.
- Authority comes from verified artifacts and explicit decisions—not model
  confidence.

---

## Contributing

Uriel Forge welcomes contributions that improve correctness, portability,
accessibility, security, documentation, and the research workflow.

Start with [CONTRIBUTING.md](CONTRIBUTING.md). Security issues should follow
[SECURITY.md](SECURITY.md).

---

## Citation

Citation metadata are provided in [`CITATION.cff`](CITATION.cff).

---

## License

MIT. See [`LICENSE`](LICENSE).
