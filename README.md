<p align="center">
  <img
    src="docs/assets/uriel-forge-banner.png"
    alt="Uriel Forge — evidence-bound research development and assurance"
    width="100%"
  >
</p>

# Uriel Forge

### Evidence-bound research development and assurance

> **Every idea deserves its strongest fair hearing.**  
> **Every claim must survive its strongest fair challenge.**

Uriel Forge helps turn rough questions and existing projects into clear,
reproducible, submission-ready research.

It checks data readiness before anyone draws conclusions, traces important
claims back to evidence, exposes contradictions and material omissions, builds
research and submission packets, and records exactly why a milestone is—or is
not—ready.

AI is optional. Uriel's authoritative state is local, deterministic, and
fail-closed. An AI may help clarify, draft, organize, and propose. It cannot
mark data ready, pass an integrity gate, change publication authority, close an
authoritative Forge result, or issue a Blessing.

```text
Interpret generously.
Test rigorously.
Report honestly.
```

---

## What can I do with Uriel?

### Bring a rough idea

Uriel helps recover the strongest clear, testable version without confusing
poor wording with poor thinking.

### Review an existing project safely

Existing projects are read-only by default. Uriel can prepare a separate review
workspace or a verified working copy before changes are made.

### Prepare data before analysis

Uriel blocks data-dependent interpretation until the exact data generation has
passed identity, sorting, normalization, reconciliation, and independent
verification.

Before that, the answer is:

> **Not yet known.**

### Trace every important claim

Material claims can be linked to:

- exact artifacts and locations;
- hashes and versions;
- supporting and contrary evidence;
- scope and uncertainty;
- measurement and transformation lineage;
- independent evidence families.

### Build the paper and submission

Depending on the capability status of the current release, Uriel can help
prepare research plans, manuscripts, limitations, data-availability statements,
figures, tables, form entries, reviewer responses, revision plans, and
submission archives.

### Prove when a milestone is finished

The Forge Method creates a durable closure bundle containing:

```text
mission
requirements
hard and soft gates
blockers
work packages
test plan
decisions
evidence
closure receipts
final result
```

It does not merely say “done.” It records why.

---

## Current capability status

<!-- URIEL_CAPABILITY_STATUS:START -->
| Capability | Status | Entry Point | Platforms | Verified Commit | Notes |
|---|---|---|---|---|---|
| Deterministic project core & packaging | **SHIPPED** | `uriel init / uriel verify` | Windows, macOS, Linux | `HEAD` | Offline-first, content-addressed project management and receipts. |
| Data Readiness & Gate 0 | **BETA** | `uriel readiness / python -m uriel.data_readiness` | Windows, macOS, Linux | `HEAD` | Strict raw data hash binding, readiness check, order invariance. |
| Three Integrity Gates (Gates 1, 2, 3) | **BETA** | `uriel audit / python -m uriel.gate_contract` | Windows, macOS, Linux | `HEAD` | Gate 1 (Frame), Gate 2 (Evidence & Calculation), Gate 3 (Adversarial Challenge). |
| Strict Blessing Integration & Independent Verifier | **EXPERIMENTAL** | `uriel blessing / python -m uriel.strict_blessing` | Windows, macOS, Linux | `HEAD` | Requires Gate 0 PASS, 3 Gate PASS, positive evaluators, independent verifier PASS. |
| Research Lifecycle, Workbench & Free-Model Burst Surfaces | **BETA** | `uriel workbench / uriel burst` | Windows, macOS, Linux | `HEAD` | Read-only bounded AI surfaces, Gap Register, Repair Packets. |
| Assurance Depth, Evidence Microscope & Decision Card | **EXPERIMENTAL** | `python -m uriel.assurance_case` | Windows, macOS, Linux | `HEAD` | 4-Layer Assurance Chain, Evidence Strength Vector, Decision Card & Proof Bundle. |
| Evidence Ingress & Data Desk | **PLANNED** | `n/a (planned capability)` | Windows (Planned), macOS (Planned), Linux (Planned) | `HEAD` | Planned safe ingestion and data desk reconciliation. |
| Uriel Forge Method Engine | **PLANNED** | `n/a (planned milestone closure engine)` | Windows (Planned), macOS (Planned), Linux (Planned) | `HEAD` | Uriel Forge is public display branding; operational Forge closure engine is planned. |
| Generic Local-Model Adapters | **PLANNED** | `n/a (planned local inference adapter)` | Windows (Planned), macOS (Planned), Linux (Planned) | `HEAD` | Planned provider-neutral local inference wrapper. |
| Desktop Native GUI & Installer | **PLANNED** | `n/a (planned native application)` | Windows (Planned), macOS (Planned), Linux (Planned) | `HEAD` | Standalone native GUI application; currently CLI/Python-first. |
<!-- URIEL_CAPABILITY_STATUS:END -->

Only capabilities with a working entry point, passing tests, packaged files,
documented limitations, and supported-platform evidence may be marked SHIPPED.
<!-- URIEL_CAPABILITY_STATUS:END -->

---

## The research path

```text
Question or existing project
        ↓
Clarify the idea and define the claim
        ↓
Build the roadmap and research plan
        ↓
Acquire and organize evidence
        ↓
Gate 0 — Verify data before analysis
        ↓
Build the manuscript and submission packet
        ↓
Gate 1 — Novelty and Clarity
Gate 2 — Evidence and Citation
Gate 3 — Adversarial Integrity
        ↓
Forge milestone closure
        ↓
Possible Blessing for the exact research version
```

The capability table above states which parts are available in the current
public release.

---

## The Forge Method

The Forge Method is for substantial milestones—not every tiny edit.

Use it for:

- a feature branch;
- a data-generation seal;
- a methods freeze;
- a manuscript;
- a submission or revision packet;
- a release candidate;
- a new evidence-source adapter;
- a security hardening pass.

A Standard Forge bundle records:

```text
MISSION.md
REQUIREMENT_BASELINES.json
GATE_REGISTER.csv
BLOCKER_REGISTER.csv
WORK_PACKAGES.csv
TEST_PLAN.md
DECISION.md
AUDIT_RESULTS.md
CLOSURE_LEDGER.csv
forge.json
RESULT.json
evidence/
SHA256SUMS.txt
```

A milestone cannot close while a required gate is missing, a blocker is
unresolved, evidence does not verify, or the exact bound version has changed.

---

## Data before conclusions

No verified data-dependent result exists until Gate 0 passes for the exact
generation.

Changing any material:

```text
data
record identity
schema
sorting rule
duplicate rule
join
exclusion
transformation
analysis plan
```

invalidates dependent readiness and conclusions.

Uriel does not confuse:

- more citations with independent evidence;
- more rows with valid data;
- more decimals with accuracy;
- more confident language with stronger support.

---

## The Three Gates

### Gate 1 — Novelty and Clarity

Is the exact question or contribution clear, scoped, testable, internally
consistent, and honestly framed?

### Gate 2 — Evidence and Citation

Does every material claim map to direct, current, verifiable evidence that
actually supports it?

### Gate 3 — Adversarial Integrity

Does the work survive credible alternatives, confounders, control mismatches,
edge cases, sensitivity checks, contradictions, limitations, and reviewer
challenge?

A failed gate is a project state—not a judgment of the person.

Uriel produces a repair packet showing:

- what failed;
- what remains useful;
- the smallest honest repair;
- the strongest next move;
- the exact condition for recheck.

---

## The Blessing of Uriel

A Blessing is Uriel's strictest exact-version research audit.

It means the bound version passed:

```text
Gate 0
Gate 1
Gate 2
Gate 3
Independent verification
Certificate binding
```

with no unresolved blocking finding.

A Blessing does **not** mean:

- eternal or universal truth;
- guaranteed publication;
- replacement for peer review, ethics review, or specialist judgment;
- immunity from new evidence.

It means the declared version survived Uriel's published checks under its
recorded scope and limitations.

---

## Concise in front, complete underneath

The default user view is a Decision Card:

```text
Status
What is established
What is not established
Why
Strongest next move
What Uriel prepared
What is needed from you
What would change the result
```

The full proof remains available behind it:

- claim/evidence maps;
- data and transformation lineage;
- uncertainty records;
- framing and omission registers;
- test receipts;
- adversarial results;
- hashes and manifests.

---

## Use Uriel with or without AI

### No AI

The deterministic core can manage verified project state, manifests, receipts,
data readiness, audit gates, packets, and closure records locally—subject to
the current capability table.

### Compatible local model

An optional local model may help with clarification, candidate analysis,
drafting, and roadmap suggestions on suitable hardware.

It has no authority to pass a gate or issue a Blessing.

### Compatible web AI

Uriel can prepare a bounded, redacted packet and one instruction for a
compatible web AI.

Review that service's privacy, retention, and training terms before uploading
unpublished or sensitive work.

### Maintainer-tested high-capability configuration

For the deepest Strict Forge, assurance, and adversarial passes, the maintainer
recommends:

```text
GPT-5.6 Sol with ultra mode
```

This is optional. It is not a dependency, exclusive integration, privacy
endorsement, or guarantee. Other compatible AIs can be used.

---

## Start

<!-- URIEL_QUICKSTART:START -->
### 1. Initialize a Managed Workspace
```bash
uriel init my-study --title "Study Title" --question "Research Question"
```

### 2. Check Project & Audit Status
```bash
uriel status --root my-study
```

### 3. Verify Local Project Integrity
```bash
uriel verify --root my-study
```

### 4. Initialize Research Workbench
```bash
uriel workbench init --root my-study --question "Research Question"
```
<!-- URIEL_QUICKSTART:END -->

A managed workspace may include:

```text
URIEL_AI_ENTRY.md
COPY_THIS_TO_YOUR_AI.txt
NEXT_PROMPT.txt
```

These files are provider-neutral.

---

## Safety model

Uriel is designed around:

```text
read-only defaults
exact-root confinement
verified managed copies
explicit consent
immutable generations
atomic writes
checksums
no hidden network
no telemetry
no automatic AI-provider installation
prompt-injected content treated as untrusted data
```

Keep an independent backup of important work.

---

## Origin

Uriel grew out of a research workflow developed in practice while the
maintainer was working toward a first published paper.

The project turns that hard-earned process into a reusable, auditable system.
That history is a maintainer account—not a claim that Uriel guarantees
publication or has already been validated for every field.

---

## Why the name?

Uriel is associated with light, wisdom, and illumination. The project uses that
symbolism in a secular way.

The forge is now the central image: raw questions and incomplete projects enter;
clear claims, verified evidence, reproducible work, and honest next steps come
out.

---

## Principles

- Every idea gets a fair chance to become clear.
- No claim gets a free pass once it is.
- Primary evidence is preferred over inherited conclusions.
- Missing evidence remains missing.
- Contradictory evidence remains visible.
- Before data readiness, the result is not yet known.
- A failed state must produce a useful path forward.
- Concise explanations must preserve the full truth boundary.
- Authority comes from verified artifacts and explicit decisions—not model
  confidence.

---

## Documentation

- [Project QRD](docs/PROJECT_QRD.md)
- [The Forge Method](docs/FORGE_METHOD.md)
- [Capability Status](docs/CAPABILITY_STATUS.md)
- [AI Usage and Privacy](docs/AI_USAGE_AND_PRIVACY.md)
- [Research Lifecycle](docs/LIFECYCLE.md)
- [Getting Started for Free](docs/GETTING_STARTED_FREE.md)
- [Privacy & Models](docs/PRIVACY_AND_MODELS.md)
- [Contributing](CONTRIBUTING.md)

---

## License

MIT. See [`LICENSE`](LICENSE).
