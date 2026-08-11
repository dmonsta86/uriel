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
