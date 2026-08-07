# Uriel Forge — Project QRD

**Document type:** Quality Requirements Document  
**Public product:** Uriel Forge  
**Python distribution and CLI:** `uriel`  
**Category:** Evidence-bound research development and assurance  
**Status:** Product contract. Availability claims must be generated from the
exact public commit.

## Mission

Uriel Forge exists to improve every controllable stage of research without
claiming certainty beyond the evidence.

It must:

- help rescue worthwhile ideas from poor articulation;
- deny polished but unsupported ideas rhetorical protection;
- verify data before analysis;
- prefer direct evidence over inherited conclusions;
- expose framing, omissions, contradictions, and uncertainty;
- produce the strongest honest next move;
- build durable research and submission artifacts;
- preserve exact-version provenance;
- fail closed when a critical requirement cannot be verified.

## Main routes

```text
Desktop
CLI/Python
Zero-install Lens
Generic AI entry
Optional local model
```

No AI route is required for authoritative operation.

## Main subsystems

```text
Seed
Lens
Workbench
Evidence Ingress
Data Desk
Paper Builder
Submission Guide
Forge Method
Audit and Blessing
```

The live capability inventory determines which are shipped.

## Authority boundary

AI may:

- clarify;
- propose;
- draft;
- organize;
- identify candidate gaps;
- suggest tests;
- prepare candidate summaries.

AI may not:

- mark Data Readiness PASS;
- close a hard Forge gate;
- set publication authority;
- pass a research gate;
- issue a Blessing;
- invent evidence, citations, approvals, results, or venue requirements.

## Core truth contract

```text
Data before conclusions.
Claims before summaries.
Evidence before authority.
Adversarial challenge before PASS.
Exact versions before certificates.
```

## Forward-path contract

No failed or incomplete workflow ends with a generic “cannot continue.”

It must produce:

- what is established;
- what is refuted;
- what remains unknown;
- what remains useful;
- the preferred next move;
- at most two alternatives;
- what Uriel completed automatically;
- what the user must supply;
- the exact completion condition;
- a continuation packet.

## Communication

Frontend:

- concise;
- plain-language;
- calm;
- one preferred next move.

Backend:

- exhaustive;
- structured;
- hash-bound;
- independently verifiable.

## Security

```text
read-only first
exact-root confinement
atomic writes
immutable generations
no hidden network
no credential access
bounded AI surfaces
safe managed copies
privacy sweep
public-brand scrub
```

## Provider neutrality

Public Uriel does not depend on a coding agent or AI provider.

Provider-specific private maintenance handoffs do not enter the public
repository.

The one named maintainer recommendation is optional and nonexclusive:

```text
See docs/AI_USAGE_AND_PRIVACY.md for the maintainer-tested recommendation
```

## Non-goals

Uriel Forge is not:

- a truth oracle;
- a guaranteed-publication system;
- a replacement for peer review;
- a general autonomous crawler;
- an AI provider;
- a full IDE;
- a confidence score based on citation count;
- a system that hides uncertainty to reassure the user.
