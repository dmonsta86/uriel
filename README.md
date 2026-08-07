<p align="center">
  <img
    src="docs/assets/uriel-banner.png"
    alt="Uriel — Question assumptions. Trace evidence. Strengthen research."
    width="100%"
  >
</p>

# Uriel

### Evidence-bound research development and assurance

> **Every idea deserves its strongest fair hearing. Every claim must survive its strongest fair challenge.**

Uriel helps people turn rough questions and existing projects into structured, reproducible, submission-ready research.

It verifies data identity, sorting, provenance, and analysis prerequisites before interpretation; traces material claims to evidence; exposes framing, omissions, contradictions, and misleading summaries; builds research, manuscript, and submission packets; and audits exact project versions through strict integrity gates.

AI is optional. Uriel's authoritative state is deterministic, local, and fail-closed. An AI may help clarify, draft, and propose. It cannot mark data ready, pass a gate, change publication authority, close an authoritative milestone, or issue a Blessing.

> **Interpret generously. Test rigorously. Report honestly.**

---

## Project status

| Capability | Status | Verified entry point | Platforms | Notes |
|---|---|---|---|---|
| Deterministic project core | `SHIPPED` | `uriel init / uriel verify / python -m uriel.core` | Windows, macOS, Linux | Offline-first, content-addressed, zero network dependencies. |
| Data Readiness & Gate 0 | `SHIPPED` | `uriel data-readiness / python -m uriel.data_readiness` | Windows, macOS, Linux | Strict raw data hash binding, receipt verification, order invariance. |
| Three Integrity Gates (Gates 1, 2, 3) | `SHIPPED` | `uriel gate / uriel audit / python -m uriel.gate_contract` | Windows, macOS, Linux | Gate 1 (Frame), Gate 2 (Evidence & Calculation), Gate 3 (Adversarial Challenge). |
| Strict Blessing Integration & Independent Verifier | `SHIPPED` | `uriel blessing / python -m uriel.strict_blessing` | Windows, macOS, Linux | Requires Gate 0 PASS, 3 Gate PASS, independent verifier PASS. Fail-closed. |
| Research Lifecycle, Workbench & Free-Model Burst Surfaces | `SHIPPED` | `uriel workbench / uriel burst / python -m uriel.workbench` | Windows, macOS, Linux | Read-only bounded AI surfaces, Gap Register, Repair Packets. |
| Evidence Ingress & Data Desk | `SHIPPED` | `uriel ingress / python -m uriel.ingress` | Windows, macOS, Linux | Safe ingestion, provenance tracking, data table reconciliation. |
| Assurance Depth, Evidence Microscope & Decision Card | `SHIPPED` | `uriel assurance / python -m uriel.assurance_case` | Windows, macOS, Linux | 4-Layer Assurance Chain, Evidence Strength Vector, Decision Card & Backend Proof Bundle. |
| Generic Local-Model Adapters | `BETA` | `python -m uriel.local_ai (optional module)` | Windows, macOS, Linux | Provider-neutral local inference wrapper; strictly optional. |
| Desktop Native GUI & Installer | `PLANNED` | `n/a (in active development)` | Windows (Planned), macOS (Planned), Linux (Planned) | Standalone native GUI application; currently CLI/Python-first. |

---

## What Uriel is for

### Start with a question
Uriel helps recover the strongest clear, testable version of an idea—even when the original question is informal, uncertain, or difficult to articulate.

### Review an existing project safely
Existing work is read-only by default. Uriel can create a separate review workspace or a verified managed copy before changes are made.

### Prepare data before analysis
Uriel does not offer a data-dependent prediction or conclusion until the exact data generation passes identity, sorting, normalization, reconciliation, order-invariance, and independent verification.

Before that, the result is:

> **Not yet known.**

### Trace claims to evidence
Material claims are linked to exact artifacts, locations, hashes, scope, contrary evidence, uncertainty, and source lineage.

### Build the paper and submission
Uriel can organize a manuscript, limitations, availability statements, figures, tables, citations, cover letters, forms, reviewer responses, revision plans, and production packets.

### Prove when a milestone is complete
Uriel Forge turns a meaningful research or software milestone into a mission-bound, gate-checked, evidence-backed closure bundle.

---

## The Uriel research lifecycle

```text
Question or existing project
        ↓
Seed / Lens
        ↓
Workbench
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
Forge closure
        ↓
Possible Blessing
```

---

## Data before conclusions

No verified data-dependent result exists until Gate 0 passes for the exact generation.

Changing any material data, record identity, schema, sort rule, duplicate rule, join, exclusion, transformation, or analysis plan invalidates dependent readiness and conclusions.

Uriel never treats more rows, more citations, more decimals, or more confident language as stronger evidence by themselves.

---

## The Three Gates

### Gate 1 — Novelty and Clarity
Is the exact question or contribution clear, scoped, testable, internally consistent, and honestly framed?

### Gate 2 — Evidence and Citation
Does each material claim map to direct, current, verifiable evidence that actually supports it?

### Gate 3 — Adversarial Integrity
Does the work survive credible alternatives, confounders, control mismatches, edge cases, sensitivity checks, contradictions, limitations, and reviewer challenge?

A failed gate is a project state—not a judgment of the person. Uriel creates a repair packet showing what failed, what remains useful, the strongest path forward, and the exact recheck condition.

---

## The Blessing of Uriel

A Blessing is Uriel's strictest exact-version audit result. It means the bound project passed:
- Gate 0 (Data Readiness)
- Gate 1 (Novelty & Clarity)
- Gate 2 (Evidence & Calculation)
- Gate 3 (Adversarial Integrity)
- Independent verification
- Certificate binding

with no unresolved blocking finding.

A Blessing does **not** mean absolute or eternal truth, universal applicability, or guaranteed publication. It means that the declared version survived Uriel's published checks under its recorded scope and limitations.

---

## Two levels of explanation

Uriel is thorough in the backend and concise in the frontend.

The default Decision Card shows status, what is established, what is not established, why, strongest next move, what Uriel prepared, what is needed from you, and what would change the result. The complete proof bundle remains available behind it.

---

## Use Uriel with or without AI

### No AI
The deterministic core manages projects, manifests, data readiness, gates, packets, receipts, indexes, and verification locally.

### Local model
A compatible local model can optionally help with clarification, candidate analysis, drafting, and roadmap suggestions on suitable hardware. It has no scientific or publication authority.

### Compatible web AI
Uriel can produce a bounded, redacted packet and one instruction for a compatible web AI. Review the provider's privacy, retention, and training terms before uploading unpublished or sensitive material.

### Maintainer recommendation for deepest passes
For the deepest Strict Forge, assurance, and adversarial passes, the maintainer specifically recommends:

```text
GPT-5.6 Sol with ultra mode
```

This is an optional tested recommendation—not a dependency, exclusive integration, privacy endorsement, or guarantee. Uriel does not promote or require another online provider in its main public documentation.

---

## Start

### Python / CLI (Available Now)
```bash
pip install uriel
uriel init --title "My Research Project" --question "My Research Question"
uriel data-readiness
uriel audit --profile submission
```

### Generic AI Handoff
After initializing or opening a managed workspace, you may provide any compatible AI with:
```text
COPY_THIS_TO_YOUR_AI.txt
```
The authoritative provider-neutral orientation remains:
```text
URIEL_AI_ENTRY.md
```

---

## Safety model

Uriel is designed around read-only defaults, exact-root confinement, verified managed copies, explicit consent, immutable generations, atomic writes, checksums, no hidden network, no telemetry, no automatic AI-provider installation, and prompt-injected content treated as data.

---

## License

MIT. See `LICENSE`.
