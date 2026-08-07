# Uriel Project QRD

**Document type:** Quality Requirements Document  
**Project:** Uriel  
**Public category:** Evidence-bound research development and assurance ecosystem  
**Status:** Target product contract; shipped capability must be generated from
the live repository and verified before public claims are updated.

---

## 1. Product definition

Uriel is an offline-first research development and assurance ecosystem.

It helps a person:

1. develop a rough question into a clear, testable research project;
2. review an existing project without risking the original files;
3. obtain and organize evidence through controlled, provenance-aware paths;
4. verify data identity, sorting, normalization, joins, and completeness before
   analysis;
5. map every material claim to direct evidence;
6. expose framing choices, omissions, contradictions, and misleading summaries;
7. create a research roadmap and complete safe next steps;
8. build manuscripts, figures, tables, limitations, and submission packets;
9. respond to editorial decisions, revisions, acceptance, and production;
10. audit an exact project version through Gate 0 and Three integrity gates;
11. close substantial milestones through Uriel Forge;
12. issue a verifiable Blessing only when every mandatory condition passes.

AI is optional.

An AI may assist with interpretation, clarification, drafting, candidate
analysis, and planning. It cannot mark data ready, change publication
authority, pass an audit gate, close an authoritative Forge result, or issue a
Blessing.

---

## 2. Mission

Uriel is built in service of truth in research.

It does not claim to possess truth or remove human judgment. It is designed to
make material framing, omissions, contradictions, stale evidence, unsupported
inference, and misleading summaries visible, traceable, and unable to receive
an authoritative PASS while unresolved.

Its public creed is:

> **Every idea deserves its strongest fair hearing. Every claim must survive
> its strongest fair challenge.**

Its operating standard is:

```text
Interpret generously.
Test rigorously.
Report honestly.
```

---

## 3. Problem

Research can fail long before a final statistical test.

Common failures include:

- a worthwhile idea being lost because it was expressed poorly;
- a polished claim receiving more deference than its evidence deserves;
- data being analyzed before identity, sorting, joins, exclusions, or
  transformations are verified;
- conclusions being inherited from secondary summaries instead of rebuilt from
  primary evidence;
- contradictory, null, negative, or inconvenient evidence being omitted;
- a title, abstract, conclusion, press summary, or submission field exceeding
  what the body establishes;
- a project appearing complete without a reproducible closure record;
- an AI model confusing fluent prose with scientific authority;
- users giving up because the system identifies a problem but does not produce
  a path forward;
- sensitive projects being copied, uploaded, or modified without a clear
  safety boundary.

Uriel addresses these as one connected research-lifecycle problem.

---

## 4. Primary users

Uriel is intended for:

- students and first-time researchers;
- independent and underfunded researchers;
- experienced researchers;
- research software engineers;
- open-source maintainers;
- reviewers and editors;
- people with a question but little formal research vocabulary;
- teams preparing manuscripts, revisions, datasets, or software papers.

The interface must remain approachable without reducing backend rigor.

---

## 5. Product routes

### 5.1 Uriel Desktop

A graphical route for ordinary users.

It lists projects, shows Data Readiness and Gate states, presents a roadmap,
explains blockers, opens packets, and optionally runs a compatible local model.

The GUI is a client of the same deterministic core. It does not implement
scientific authority separately.

### 5.2 Uriel CLI and Python

For automation, CI, reproducible workflows, advanced users, and integration.

### 5.3 Uriel Lens

A zero-install, copy-paste advisory prompt.

Lens can clarify, map visible evidence, identify gaps, and propose next steps.
It cannot bind unseen files, seal data, preserve an authoritative ledger, or
issue a Blessing.

### 5.4 Generic AI entry

Every managed workspace can generate:

```text
URIEL_START_HERE.md
URIEL_AI_ENTRY.md
COPY_THIS_TO_YOUR_AI.txt
URIEL_PROJECT.json
NEXT_PROMPT.txt
```

Any compatible AI with access to the supplied workspace may follow those
instructions.

No coding-agent brand is required or recommended by the core product.

### 5.5 Local model

A compatible local model is an optional add-on.

The deterministic core remains useful without it. Local model capability is
hardware- and evaluation-gated, project-local, bounded, and advisory.

---

## 6. Research lifecycle

```text
Question or observation
        ↓
Uriel Seed
        ↓
Charitable reconstruction and testable project
        ↓
Uriel Workbench
        ↓
Evidence Ingress + Data Desk
        ↓
Gate 0 — Data Readiness
        ↓
Paper Builder
        ↓
Three-Gate audit
        ↓
Submission Guide
        ↓
Revision / acceptance / production
        ↓
Forge milestone closure
        ↓
Possible Blessing for an exact research version
```

These modules may be introduced across multiple releases. The README must mark
their verified availability accurately.

---

## 7. Main subsystems

### Uriel Seed

Turns rough, childlike, informal, or partially formed questions into:

- literal interpretation;
- strongest defensible interpretation;
- smallest testable version;
- larger supported opportunity;
- operational definitions;
- rival explanations;
- minimum useful test;
- disconfirming evidence;
- one clarification batch.

### Uriel Lens

Provides a provider-neutral, no-install advisory review.

### Uriel Workbench

Stores:

- research questions;
- hypotheses and rivals;
- operational definitions;
- controls;
- analysis plans;
- claims;
- evidence;
- limitations;
- decisions;
- blockers;
- roadmaps;
- durable next steps.

### Uriel Evidence Ingress

Obtains evidence through:

- local artifacts;
- reviewed source adapters;
- official structured APIs or bulk channels;
- strict source/resource policies;
- immutable quarantine;
- deterministic parsing;
- provenance and rights receipts;
- bounded evidence capsules.

It is not a default autonomous general crawler.

### Uriel Data Desk

Handles:

- immutable source generations;
- identity and schema;
- duplicate ledgers;
- deterministic sorting;
- normalization;
- joins;
- missingness;
- exclusions;
- transformations;
- SQLite indexing;
- independent verification;
- resumability.

### Uriel Paper Builder

Uses transparent source files for:

- manuscript sections;
- metadata;
- references;
- figures;
- tables;
- supplements;
- statements;
- manifests.

It produces portable baseline formats and optional richer exports through
explicit adapters.

### Uriel Submission Guide

Handles:

- submission forms;
- character counts;
- venue requirements supplied from official sources;
- cover letters;
- revision matrices;
- reviewer responses;
- rejection/pivot planning;
- conditional acceptance;
- acceptance and production packets;
- archives and checksums.

### Uriel Forge

Closes substantial milestones through:

- mission;
- requirements;
- hard/soft gates;
- blockers;
- work packages;
- evidence;
- test plans;
- independent refutation;
- closure ledger;
- exact result.

Forge completion is not the same as a scientific Blessing.

### Uriel Audit and Blessing

Required sequence:

```text
Gate 0 — Data Readiness
Gate 1 — Novelty and Clarity
Gate 2 — Evidence and Citation
Gate 3 — Adversarial Integrity
Independent verification
Certificate binding
```

A Blessing is a strict exact-version result. It is not universal truth,
acceptance, peer review, or immunity from future evidence.

---

## 8. Truth and evidence contract

### 8.1 Data before conclusions

No data-dependent prediction, trend, effect, comparison, association, ranking,
forecast, positive signal, negative signal, or conclusion is authoritative
before the exact data generation passes Data Readiness.

Before that:

```text
The result is not yet known.
```

### 8.2 Direct evidence

Primary data and primary sources are preferred when reasonably available.

Another paper's conclusion is not a substitute for its underlying evidence.

### 8.3 Claim-specific evidence floors

Every material claim is classified, for example:

```text
descriptive
comparative
associational
predictive
causal
mechanistic
generalization
reproducibility
software behavior
safety/security
novelty
```

Each class has a minimum evidence floor.

### 8.4 Assurance depth

Critical claims can be traced through:

```text
claim
result
aggregate/subgroup
record
measurement
transformation
source/acquisition
```

Depth is driven by materiality and decision risk, not by endless detail.

### 8.5 Certainty ceiling

The language used for a claim cannot exceed its weakest critical evidence and
uncertainty state.

---

## 9. Twin Duties Contract

### Charitable reconstruction

A poorly articulated idea is not rejected before its strongest fair,
testable interpretation is attempted.

### Adversarial verification

A polished claim receives no protection from:

- prestige;
- credentials;
- jargon;
- citation count;
- confidence;
- attractive figures;
- model agreement.

Once the claim is confirmed, it must survive the same evidence and adversarial
standards as every other claim.

---

## 10. Framing, omissions, and summary integrity

Uriel maintains:

- a Framing Register;
- an Omission Register;
- claim/evidence records;
- Summary Fidelity receipts;
- cross-section and packet consistency receipts.

Material unresolved items block the relevant gate.

Compression is allowed. Distortion is not.

---

## 11. Forward-Path requirement

Uriel must not end with a generic “cannot continue.”

A failed or incomplete state must produce:

- what is established;
- what is refuted;
- what remains unknown;
- what remains useful;
- the preferred next move;
- up to two alternatives;
- what Uriel already prepared;
- the exact completion condition;
- the next prompt or command;
- a blocker proof when progress cannot continue.

A terminal no-path result requires an adversarial attempt to find a narrower,
alternative, lawful, ethical, evidence-producing route.

---

## 12. Communication contract

### Frontend

The default interface is a concise Decision Card:

- status;
- what is established;
- what is not established;
- why;
- strongest next move;
- what Uriel prepared;
- what the user must supply;
- what would change the result;
- link to proof.

### Backend

The proof bundle remains exhaustive, structured, hash-bound, and independently
verifiable.

Uriel is thorough behind the scenes and concise in front of the user.

---

## 13. Voice and posture

Uriel is:

```text
calm
precise
patient
plainspoken
constructive
firm about evidence
never condescending
never theatrical
```

A failed result explains:

```text
why it does not pass
what remains useful
the smallest repair
the strongest next move
the exact completion condition
```

---

## 14. Offline-first definition

Offline-first means:

- the authoritative core runs locally;
- projects, manifests, receipts, gates, packets, and indexes do not require an
  online AI;
- AI is optional;
- a local model can assist on compatible hardware;
- online evidence acquisition and online AI use are explicit, task-bound, and
  consented;
- Uriel never pretends a local model's training memory is current evidence.

It does not mean that current literature can be obtained without a local
corpus, imported snapshot, or approved network acquisition.

---

## 15. AI neutrality and recommendation

Uriel is not tied to an AI provider, coding agent, or web service.

Public onboarding must use generic language:

```text
compatible AI
local model
web AI
filesystem-capable coding agent
```

Public tracked files must not depend on a provider-specific workspace format.

### Named high-capability recommendation

The maintainer's specific recommendation for the deepest strict Forge,
assurance, and adversarial passes is:

```text
GPT-5.6 Sol with ultra mode
```

This is:

- an optional maintainer recommendation;
- not a dependency;
- not an exclusive integration;
- not an endorsement of provider privacy or retention practices;
- not a guarantee;
- not required for ordinary Uriel use.

No other online provider or product should be promoted in the main public
documentation.

---

## 16. Security and privacy

Core principles:

```text
exact-root confinement
read-only first
safe managed copy
explicit consent
no hidden network
no telemetry
no silent provider installation
no credential access
atomic writes
immutable generations
hash verification
links/reparse refusal
bounded AI surfaces
prompt-injection content treated as data
```

Private research scaffolding is reused only at the level of reviewed,
sanitized, licensed generic patterns or small approved components.

---

## 17. Project status model

The public README must use a generated capability table:

```text
SHIPPED
BETA
EXPERIMENTAL
PLANNED
DEFERRED
```

Every status requires:

- feature name;
- version or branch;
- command/UI entry;
- exact verification;
- supported platforms;
- known limitations.

No target capability may be described as currently available without evidence
from the exact public commit.

---

## 18. Non-goals

Uriel is not:

- a truth oracle;
- an automatic peer-review replacement;
- a general autonomous web crawler;
- a journal acceptance guarantee;
- an AI provider;
- a cloud account platform;
- a surveillance tool;
- a full IDE;
- a citation-count confidence engine;
- a system that hides uncertainty to make users feel better;
- a system that gives up because a model ran out of context.

---

## 19. Release quality

A public release claim requires:

- all mandatory tests;
- privacy sweep;
- package builds;
- fresh installation;
- entry points;
- schemas;
- installer tests;
- supported native CI;
- documentation command tests;
- no private material;
- no stale provider-specific onboarding;
- exact capability inventory;
- Forge closure for the release milestone where required.

---

## 20. Success definition

Uriel succeeds when a person can begin with a rough question or an existing
project and leave with:

- a clearer, fairer research question;
- an honest map of what is known and unknown;
- correctly prepared data;
- traceable evidence;
- a practical roadmap;
- a stronger manuscript or submission;
- a durable record of every critical decision;
- a concise explanation;
- a complete proof bundle;
- no authoritative claim stronger than the evidence.
