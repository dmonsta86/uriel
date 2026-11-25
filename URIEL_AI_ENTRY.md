# Research-record assistant entry

Read the authoritative Trilium tree (or the Markdown folder) before proposing work. Use `uriel check-before-push` and the mid-research checklist. Preserve the author's exact question, never invent evidence, use the declared mode, freeze predictions before observing results, and distinguish underpowered nulls from closed hypotheses. Record every material claim's evidence label. Use stable keys, do not overwrite changed notes, record gaps and rival explanations, and obtain human confirmation before imports or submission. Do not upload private notes or tokens. No specific assistant is required.

For detailed instructions, see [Research records](docs/RESEARCH_RECORD.md). Existing legacy-project instructions follow.

# Uriel AI Entry — Provider-Neutral Instruction Surface

Welcome to Uriel. Uriel is an offline-first research development and assurance ecosystem.

## Core Rules for AI Assistants Working in this Repository
1. **AI is Optional and Advisory**: An AI assistant may clarify questions, summarize evidence, propose roadmaps, draft manuscript sections, or suggest repairs. AI cannot mark data ready, pass audit gates, close authoritative milestones, or issue a Blessing.
2. **Fail-Closed & Deterministic**: The authoritative state of Uriel is local, deterministic, and hash-verified.
3. **No Credential Exposure**: Never ask for, read, or store provider credentials or API keys in project packets or repository files.
4. **Respect Data Readiness**: Before analysis or inference, raw data must pass Data Readiness Gate 0 (`uriel readiness --root PATH`).
5. **Trace Claims to Evidence**: Every material claim must be bound to primary evidence, exact artifact paths, and content hashes.
6. **Follow the protocol**: Run `uriel next --root PATH`, do the one action it names, and run it again. Stop and ask the human whenever the action is marked `owner: human`.
7. **Never type a result number**: Register it with `uriel paper dp-add` and write `{{dp:ID}}`; cite only sources that exist and quote only text that occurs verbatim in a held source.

## Quick-Start AI Handoff

For exact project-defining user wording, inspect
docs/RESEARCH_VERBATIM_LEDGER.md. The ledger is off by default; never capture
hidden instructions, provider content, credentials, or any user message without
the documented explicit consent transition.

To assist a user with a Uriel research project:
1. Run `uriel next --root PATH` (or read the file written by `uriel next --root PATH --prompt NEXT_STEP.md`) and follow docs/RESEARCH_PROTOCOL.md.
2. Inspect `docs/PROJECT_QRD.md` for project mission and scope.
3. Run `uriel verify --root PATH` or `uriel status --root PATH` to verify local repository state.
4. Inspect `docs/CAPABILITY_STATUS.json` for current capability status.
