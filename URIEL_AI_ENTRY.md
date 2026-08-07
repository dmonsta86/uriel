# Uriel AI Entry — Provider-Neutral Instruction Surface

Welcome to Uriel. Uriel is an offline-first research development and assurance ecosystem.

## Core Rules for AI Assistants Working in this Repository
1. **AI is Optional and Advisory**: An AI assistant may clarify questions, summarize evidence, propose roadmaps, draft manuscript sections, or suggest repairs. AI cannot mark data ready, pass audit gates, close authoritative milestones, or issue a Blessing.
2. **Fail-Closed & Deterministic**: The authoritative state of Uriel is local, deterministic, and hash-verified.
3. **No Credential Exposure**: Never ask for, read, or store provider credentials or API keys in project packets or repository files.
4. **Respect Data Readiness**: Before analysis or inference, raw data must pass Data Readiness Gate 0 (`uriel data-readiness`).
5. **Trace Claims to Evidence**: Every material claim must be bound to primary evidence, exact artifact paths, and content hashes.

## Quick-Start AI Handoff
To assist a user with a Uriel research project:
1. Inspect `docs/PROJECT_QRD.md` for project mission and scope.
2. Run `uriel verify` or `python -m uriel.core` to verify local repository state.
3. Inspect `manifest/capability_inventory.json` for current capability status.
