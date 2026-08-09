# Uriel research lifecycle

This document records the research-lifecycle layer on top of the existing
deterministic core. The intake, bounded AI-surface, workbench, checkpoint,
decision, repair, and submission portions are current beta surfaces. Evidence
Ingress now has a bounded immutable-intake implementation on `main`; Data Desk
profiling/generations, Paper Builder, and advanced export work remain planned.
The checklist at the bottom is the authoritative boundary for this document.

The core promise is unchanged: Uriel certifies only that one exact recorded
project state passed a named, inspectable policy. The lifecycle layer helps a
person move from an uncertain question to the strongest honest project the
available evidence can support, and then through submission, revision, and
production.

## Product promise

Uriel should not behave like a fault-finding chatbot. It should:

1. identify what the person is actually trying to learn;
2. recover a promising idea from weak wording;
3. distinguish fatal problems from repairable gaps;
4. fill safe gaps from supplied material;
5. propose evidence, controls, tests, and pivots;
6. build the files needed to continue;
7. guide the person through submission or revision;
8. preserve a reproducible record of what was examined.

Every blocking finding must include what was observed, why it matters, what
remains valuable, the smallest repair, the best practical path, the larger
opportunity if supported, and the evidence needed.

## Entry points

### Uriel Lens (current advisory, zero-install surface)

A user attaches or pastes a project and uses one prompt. The response is
advisory and read-only. Lens can map visible claims, gaps, contradictions, and
next steps. It cannot issue a Blessing, inspect files it was not given, bind a
review to artifact hashes, or preserve an audit ledger.

### Uriel Seed (current intake surface)

Turns a rough question into a viable research project: restate the strongest
plausible idea, mark assumptions and unknowns, ask the smallest necessary
clarification, identify a narrow viable version, identify a larger supported
opportunity, and propose the minimum useful test. Poor expression is not
treated as poor thinking.

## Full harness

### Research Workbench (current beta surface)

Plans and records the project: research-plan records, claim/evidence maps,
durable refused/deferred finding reminders, and the constructive Diamond Path:

```text
recover question
→ separate observation/interpretation/claim
→ record rival explanations
→ create minimum viable design
→ fill safe gaps
→ propose pivot
→ map route to the Three Gates
```

The Diamond Path is a transformation workflow, not a Blessing, and does not
relax any audit gate. When the original claim is unsupported, Uriel offers a
concrete pivot: narrower claim, different outcome or comparison, observational
study, replication, methods paper, dataset/resource paper, negative result,
software/tool paper, or review/evidence map.

### Evidence Ingress (bounded local intake) and Data Desk (planned)

The target Data Desk will inventory, sort, normalize, hash, and index data with
immutable generation-based checkpoints, a declarative ephemeral/exclusion
policy with human reasons, absence-fact delta classification (deletion is a
fact, not a conclusion about corruption), an exact duplicate ledger, an
SQLite index, and an independent read-only verifier. Anomaly detection will
create a review queue of leads, not scientific findings. Scale claims will only
be made with measured benchmark receipts.

The current local-only intake path is:

```text
cd PROJECT
uriel --json data plan --root . --source FILE > artifacts/import-plan.json
uriel data import --root . --source FILE --plan artifacts/import-plan.json
uriel data verify-import --root . --receipt .uriel/data/receipts/import/PLAN_SHA256.json
```

`data plan` remains no-write and path-private. `data import` requires that exact
saved plan, streams the selected UTF-8 file once, seals content-addressed bytes,
and publishes immutable records with the receipt last. `data verify-import`
recomputes the managed bytes and record bindings. None of these commands marks
the artifact ready for analysis or grants Gate 0 authority. Deterministic
profiles, generations, reconciliation, and Gate 0 integration remain planned.

### Paper Builder (planned)

The planned Paper Builder will maintain a canonical, transparent manuscript directory
(sections, tables, figures, supplements, statements, style, manifest) instead of
treating DOCX or PDF as the source of truth. The standard-library core always emits Markdown,
UTF-8 text, HTML, JSON/JSONL, CSV/TSV, SQLite, checksum manifests, and ZIP
packets. A conservative deterministic `docx-lite` writer is provided only if
it can be validated as Office Open XML; PDF support is always print-ready HTML
plus detected optional engines, never a silent install. Every export records a
receipt: source generation, format, adapter, command, output hash, warnings,
and validation result.

### Submission Guide (current beta surface)

Understands the full lifecycle from idea to archival record:

```text
idea → project → manuscript → internal review → ready for submission
→ submitted → editorial update → revision → resubmission → acceptance
→ production → archival record
```

A user can import an editor email, decision letter, reviewer comments, or
submission-system export. Uriel creates an immutable decision-import record
(source hash, received date, venue, manuscript identifier, explicit status
language, inferred decision class, confidence, deadline, reviewer/editor
sections, unresolved ambiguity, user confirmation). AI may suggest a decision
class; deterministic state changes only after the explicit language or user
confirmation.

Supported decision classes include acknowledged, submitted,
administrative_check, under_review, review_invitation, major_revision,
minor_revision, revise_and_resubmit, conditional_acceptance, accepted,
accepted_in_production, proofs_received, published, desk_rejection,
rejected_with_feedback, rejected_resubmit_elsewhere, withdrawn, and unknown.

Revision workflows make every reviewer/editor comment an individually
addressable item with action classification, evidence location, proposed
repair, dependency and priority, a response-to-reviewers draft, a revised
manuscript checklist, an unresolved-question batch, and a response packet with
checksum manifest. Comments are classified as required change, requested
clarification, requested evidence, methodological concern, interpretation
concern, formatting/editorial, question, positive observation with no action,
or conflict/impossible request. A positive remark is never turned into fake
work; a conflicting request is surfaced and resolved explicitly.

Rejection handling separates fatal scientific defect, repairable defect,
venue mismatch, scope mismatch, presentation failure, missing evidence,
editorial preference, and unsupported or unclear criticism, then produces the
smallest honest repair path and resubmission packet. Venues are never
recommended without current official requirements.

## Standalone packets

Every major workflow ends by creating a standalone, coherent packet that can
be understood without the chat that produced it, with one primary instruction
file:

```text
00_READ_ME_FIRST.md
```

The standard numbered layout is stable across generations:

```text
00_READ_ME_FIRST.md            06_COVER_OR_RESPONSE_LETTER.md
01_PROJECT_OR_DECISION_SUMMARY.md  07_SUBMISSION_FIELDS.json
02_REQUIRED_ACTIONS.csv        08_FORM_WALKTHROUGH.md
03_REVISION_OR_COMPLETION_PLAN.md  09_FILE_CHECKLIST.md
04_CLAIM_EVIDENCE_MAP.csv      10_LIMITATIONS_AND_UNKNOWNS.md
05_RESPONSE_TO_REVIEWERS.md    11_NEXT_INSTRUCTION.md
```

plus `artifacts/`, `references/`, `tables/`, `figures/`, `schemas/`,
`MANIFEST.json`, and `SHA256SUMS.txt`. Only files relevant to the current
state need to be present; numbering stays stable.

`00_READ_ME_FIRST.md` tells any AI what the packet represents, which files are
authoritative, what it may and may not infer, the current submission state,
unresolved questions, the task, the exact output files to update, and that it
must not invent evidence or issue a Blessing.

A packet is not marked ready while it contains TODO, TBD, PLACEHOLDER,
UNKNOWN_REQUIRED, UNCITED_CLAIM, MISSING_ATTACHMENT,
UNVERIFIED_REQUIREMENT, or CHARACTER_LIMIT_EXCEEDED. Packet preflight emits
one of:

```text
READY
READY_WITH_DISCLOSED_LIMITATIONS
REVISION_REQUIRED
BLOCKED
```

New output becomes a new immutable generation linked to its predecessor; an
earlier packet is never silently overwritten.

## Publication authority

Checkpoint-level publication-authority states:

```text
not_assessed
not_ready
internal_review_ready
submission_ready
submission_authorized
submitted
revision_required
resubmission_ready
conditionally_accepted
accepted
production_ready
published
withdrawn
```

No AI suggestion can grant `submission_authorized`, `accepted`, or
`published`. Those require user confirmation and/or a bound external artifact
(decision letter, acceptance email, production notice) whose hash is recorded.

## Generation and checkpoint model

Each authoritative inventory or packet generation records:

```text
generation ID
parent generation
created timestamp
source manifest hash
record stream hash
record count
delta summary
ephemeral-policy version
publication-authority state
verification receipts
```

Historical generations are immutable and never rewritten. Delta classes are:

```text
added
modified
absent
volatile
excluded
duplicate
unchanged
unknown
```

"Absent" means the file was present in a prior generation and is not present
now — a fact, not a conclusion.

## AI and privacy boundary

- Provider-neutral and advisory only. Uriel never endorses a provider.
- Bounded AI surfaces expose only the records required for a task, with a
  surface manifest, generation binding, row/byte limits, redaction policy,
  content hashes, an allowed task, a no-authority declaration, and an
  acceptance receipt. An AI surface cannot write scientific authority or
  issue a Blessing.
- Free/rate-limited models get resumable burst context packets
  (`burst-001/`, `burst-002/`, ...) so the user never has to summarize a
  previous session. Each burst carries state, source manifest, selected
  records, output requirements, `NEXT_PROMPT.txt`, and checksums.
- Before material goes to a web model, Uriel shows the retention/privacy
  notice and offers a redacted or metadata-only packet.
- The deterministic audit and Blessing boundary remain authoritative and
  unchanged.

## Planned CLI surface

Commands are added per phase; the deterministic core modules stay
authoritative. Planned module map (see the implementation priority document):

```text
checkpoints  delta        ephemeral    publication  surfaces
ai_packets   seed         workbench    data_desk    manuscript
exports      submission   forms        packet      decisions
reviewer_response
```

Planned command groups:

```text
uriel seed
uriel workbench init|plan|status|next
uriel data inventory|diff|dedupe|normalize|index|query|verify
uriel paper init|outline|build|check|export|package
uriel submit init|import-decision|plan|build-response|guide|verify|archive|status|next-prompt
```

Every command supports `--json`, `--root`, `--output`, `--dry-run`, and
`--force` only where safe and explicit. Ordinary writes are atomic. Uriel
works without any AI provider.

## Implementation status

- [x] Phase 1 — architecture and public contract (this document)
- [x] Phase 2 — schemas and immutable packet model
- [x] Phase 3 — submission lifecycle core
- [x] Phase 4 — bounded minimum-prompt and free-AI workflow
- [x] Phase 5 — workbench, decisions, and publication authority
- [ ] Phase 6 — Data Desk
- [ ] Phase 7 — Paper Builder and exports
- [x] Phase 8 — release, portability, and security baseline (broader independent review remains)
