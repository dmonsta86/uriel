# Research records

The research record is a beta Markdown workflow and an experimental Trilium ETAPI workflow. Choose one authoritative project tree. The same commands work in both backends. No model service is required, and local use requires no network. ETAPI reference: https://docs.triliumnotes.org/user-guide/advanced-usage/etapi.

## Start

Save the author's question as UTF-8, including any meaningful punctuation and line breaks. Use `uriel record init --folder research-record --project my-project --question-file question.txt --mode evidence-neutral`. The question is stored verbatim and hashed. The project mode is immutable within that record; use a separate project key for a distinct exploratory branch. Existing consented Research Verbatim Ledger entries can be copied using `uriel record import-verbatim --root legacy-project --user USER --folder research-record --confirm`. This is an explicit copy, not automatic capture or consent.

For Trilium, set the environment variables `URIEL_ETAPI_TOKEN` (secret) and optionally `URIEL_TRILIUM_URL` (server URL). Use `uriel trilium connect --url http://127.0.0.1:37740` to test the connection. All live commands need a stable `--project` key; initialize under the chosen `--parent` ID. Non-loopback HTTP and redirects are refused. HTTPS is required for a remote server. Notes use stable IDs and project/key labels; editable Markdown content is stored in code notes.

The nine sections are Question, Current picture, Leads, Conclusions register, Ruled out, Gaps and tensions, Decisions and direction history, Sources and data, and Manuscript. Structured records are Markdown notes containing JSON. The Current picture and Manuscript are coherent prose, not an accumulating transcript.

## Material and edits

- `uriel record import file.md file.csv file.pdf --folder research-record --plan import.json` previews suggested placement, reason, path, and hash. Review or change the section and reason in the plan. `uriel record import --folder research-record --plan import.json --confirm` reads the same bytes again and creates canonical records. PDF bytes are attachments; other supported UTF-8 files are preserved verbatim. Repeated exact-byte imports do not duplicate records.
- `uriel record read current --folder research-record` prints the content and expected revision. Save its output (or use `uriel --json record read current ...`); pass that JSON to `uriel record rewrite current --folder research-record --file revised.md --expected expected.json`. Superseded local prose is preserved in history. A stale revision, rename, or move preserves the existing note and creates a conflict note.
- Trilium does not provide an atomic conditional content PUT in its documented ETAPI. By default, a matching revision produces a proposal note under Decisions, with the previous and proposed text. Review and apply it in place in Trilium. If the operator has ensured an exclusive edit window (no other editor), `--exclusive-write` permits compare-before-write and a server revision backup; it is not a guarantee against a concurrent non-cooperative editor. Folder writes likewise use a cooperative lock, not a lock on external editors.
- `uriel record verify --folder research-record --save-baseline baseline.json` records current note hashes, paths/parents and revision expectations. Later `uriel record verify --folder research-record --baseline baseline.json` reports drift; intentional changes are still drift until reviewed. `uriel record export record.zip --folder research-record` creates a private export. `uriel record import-zip record.zip --folder other-record --confirm` restores stable keys; an existing differing note is preserved as a conflict. Exports contain research content. Never commit them to a public repository.

Use the equivalent `trilium` subcommand with `--url` and `--project` for live operations. The top-level checklist, summary and duplicate-search commands accept those location flags directly.

## Record fields

`uriel record add KEY --file record.json --folder research-record` creates structured records. A lead needs `kind: "lead"`, `idea`, `status` (idea, queued, waiting on data, done; running derives from assignment), `owner`, and optional `aliases`. A claim uses `kind: "claim"`, `statement`, `evidence` (record keys) and exactly one `label`:

| Label | Required detail |
|---|---|
| direct observation | instrument, uncertainty |
| derived statement | theorem, premises |
| empirically tested law | tested_range |
| chosen model or approximation | assumptions |
| hypothesis or analogy | hypothesis |
| unknown | reason |

The existing causal/associational claim-class checks remain independent of these epistemic labels. A decision needs `verbatim`, `tried`, `workarounds`, `result`. A gap needs `counter_evidence`, `unaddressed`, `tension`, `discriminating_test`. A ruled-out entry needs a `conclusion` key classified Closed and `why`.

Use `freeze KEY --file ...` with lead, hypothesis, control_source (source key), control_result, effect_size, effect_derivation, unit and acceptance_criteria. Frozen records are hashed and timestamped. Use `assign LEAD --file ...` with owner, question, inputs, prediction, deliverable, verification, duplicate_review, reused, changes, missing, and checklist (the complete mid-before receipt key); a deterministic create-only task key prevents two initial assignments to the same lead.

Use `result KEY --file ...` with lead, source, result, unit, mode, observed_at (UTC timestamp), null (boolean), effect_estimate, sensitivity, sensitivity_basis, prediction, control_reproduced, control_evidence, acceptance_met, acceptance_evidence and an audit mapping. Assigned tasks also require the matching owner and verification fields. Each audit entry contains a boolean `pass` and an evidence/reason string:

- statistic_response
- right_observable
- resolution_smoothing
- selection_dust_calibration
- shared_calibration
- equations_units_signs
- covariance

Predicted size must exceed sensitivity in the same units, with a recorded control and acceptance evidence. Missing or late predictions are exploratory. The tool cannot know when a person first saw data; timestamps are a record, not independent proof of preregistration. A null without the required evidence remains Untested (underpowered or undetermined) or Upper limit only when an explicit upper_limit and limit_scope are recorded. A non-null can be Allowed, not preferred; it is not automatically confirmed.

Use `conclude KEY --file ...` with lead, result, classification, logical_steps, alternatives, workarounds, would_change, thoroughness, reviewer, mode, coincidence and multi_factor (both booleans). If coincidence is true, record condition_reached, local_state_change, consequence, recurrence. If multi_factor is true, include single_factor_baselines, add_one, leave_one_out, combined_result, combined_null. The deterministic audit decides the class, not the prose. A conclusion without a result may only be Untested or Not yet built. A task owner cannot be its own reviewer.

## Checklists

Run `uriel checklist start`, `uriel checklist mid-before`, `uriel checklist mid-after`, and `uriel checklist pre-submission` against the same record. For mid-before supply --lead and --prediction; for mid-after supply --lead, --result and --prior (the corresponding mid-before receipt key). Each returns and stores a receipt with missing items, stable keys and locations. Use `--attestations confirmations.json` for checks requiring human or independent review; the file maps the exact displayed check name to `{"confirmed": true, "by": "reviewer", "evidence": "specific record or artifact"}`. Resolve a conflict by reviewing both versions, applying an agreed change, and adding a decision record with conflict (the conflict key), resolution, reviewer and the normal decision fields. The checklist blocks on unresolved conflicts. A receipt reports only completeness of the defined fields. It does not prove evidence authenticity, source interpretation, mathematical validity, manuscript coverage, authorship or venue acceptance. Manuscript preflight is a deterministic advisory text scan; review figures and sources separately.

Use `uriel check-before-push "idea or alias"` before starting a lead and `uriel summary --for-successors` for a grouped register and active leads. Lexical search is not semantic equivalence or proof of absence.

## Worked example

Run `python examples/research_record.py demo-record` in a clean directory. It uses synthetic measurements of a simple linear relation, with a known zero-offset control and a frozen five-unit shift prediction. It records the synthetic source, tests the predicted offset with a one-unit sensitivity, audits the null, registers a Closed conclusion for that synthetic case, and finds the same lead via an alias. It makes no claim about real-world experimental validation.

## Compatibility and status

The existing Uriel workspace, data ingress, integrity gates, paper builder, plan lock, statistics lint, rival-model scrutiny, adversarial mode, and attestation commands remain available as optional tools. Their project format is separate; the research record does not automatically convert legacy files except for explicit import and the consented ledger copy.

ETAPI integration is tested against a standard-library mock, not a deployed Trilium instance. Stable labels, revision checks, Markdown code notes and attachments must be validated against the intended server version before using the tool with irreplaceable research. Assignments are create-only; reassignment and reopening are not implemented. ZIP restores content and project placement where the parent is part of the tree, not external Trilium parent relationships. There is no atomic cross-note transaction; a failed import may be partial and can be retried using stable keys.
