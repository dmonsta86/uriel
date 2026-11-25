# JSON Schemas

These editor-facing Draft 2020-12 schemas mirror the files packaged under `uriel.schemas`. Runtime validation intentionally uses the Python standard library and does not require a JSON Schema library.

Forge contracts include:

- `uriel.forge_run.v1`: immutable run/state snapshots;
- `uriel.forge_deferral.v1`: typed soft-gate deferrals;
- `uriel.forge_continuation.v1`: evidence-bound forward-path packets;
- `uriel.forge_public_summary.v1`: generated metadata-only summaries; and
- `uriel.forge_sanitized_export.v1`: closed sanitized-export manifests.

The forward request is a bounded operation envelope documented in
[`docs/FORGE_FORWARD.md`](../docs/FORGE_FORWARD.md); its normalized canonical
digest is embedded in the durable continuation record.

Research Verbatim Ledger contracts include:

- uriel.research_verbatim_consent.v1: explicit mode and offer-preference state;
- uriel.research_verbatim_entry.v1: exact text, provenance, isolation, links,
  optional separate summary, and integrity hashes;
- uriel.research_verbatim_ledger.v1: one aggregate isolated store;
- uriel.research_verbatim_export.v1: an explicit exact-wording export; and
- uriel.research_verbatim_drift_review.v1: non-persistent advisory drift output.
- uriel.paper_review.v1: a read-only, hash-bound manuscript review that combines
  consented verbatim fidelity, declared claim/evidence coverage, bounded
  closest-prior-work coverage, and an explicit material-change confirmation
  state without rewriting or granting scientific authority.

Research protocol and Paper Builder contracts include:

- `uriel.paper.v1`: the manuscript manifest (title, article type, ordered
  sections with kinds and number policies, word limits);
- `uriel.datapoints.v1`: reported numbers bound to artifact digests, exact
  locators, declared values, sanity kinds, GRIM inputs, and relations;
- `uriel.references.v1`: cited works with verification status and optional
  held, hash-bound source copies;
- `uriel.paper_check.v1`: a read-only check report with levelled, located
  findings and exactly three repairs each;
- `uriel.paper_build.v1`: a build receipt binding every input, artifact, held
  source, and output digest;
- `uriel.plan_lock.v1`: a content-addressed analysis-plan lock; and
- `uriel.next_step.v1`: the read-only seven-stage protocol state with one next
  action.
