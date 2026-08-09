# The Forge of Uriel Capability Status

Catalog fingerprint: `157c38b84eec572215b999e42be4dd0e323916fe98214ab036bf43596c69a81c`

Status meanings:

- `SHIPPED`: supported core behavior with a public CLI contract.
- `BETA`: usable and tested, with interfaces or policy still allowed to evolve.
- `EXPERIMENTAL`: available for careful evaluation; not a claim of scientific authority.
- `PLANNED`: named boundary only; no implementation is claimed.

| Capability | Status | Verified entry point | Platforms | Evidence | Notes |
|---|---|---|---|---|---|
| Deterministic project core and packaging | `SHIPPED` | `uriel start / uriel verify / uriel doctor` | Windows, macOS, Linux | `src/uriel/core.py`, `src/uriel/cli.py`, `tests/test_core.py`, `tests/test_packaging.py` | Offline-first project confinement, content-addressed records, receipts, and zero runtime dependencies. |
| Data Readiness and Gate 0 | `BETA` | `uriel readiness` | Windows, macOS, Linux | `src/uriel/data_readiness.py`, `tests/test_data_readiness.py` | Dataset identity, sorting, normalization, reconciliation, staleness, and order-invariance checks. |
| Three Integrity Gates | `BETA` | `uriel audit` | Windows, macOS, Linux | `src/uriel/gate_contract.py`, `src/uriel/audit.py`, `tests/test_gate_contract.py`, `tests/test_audit.py` | Scope and claim language, direct evidence, and adversarial robustness with fail-closed repair guidance. |
| Strict Blessing and independent verifier | `EXPERIMENTAL` | `uriel blessing / uriel verify-blessing` | Windows, macOS, Linux | `src/uriel/strict_blessing.py`, `src/uriel/independent_verify.py`, `tests/test_strict_blessing.py`, `tests/test_blessing.py` | Content-addressed attestation of recorded gate decisions and exact bound artifacts; not independent scientific validation. |
| Research lifecycle, workbench, repair, and submission | `BETA` | `uriel intake / uriel workbench / uriel burst / uriel submit` | Windows, macOS, Linux | `src/uriel/workbench.py`, `src/uriel/surfaces.py`, `src/uriel/gap_register.py`, `src/uriel/repair_packet.py`, `tests/test_workbench.py`, `tests/test_lifecycle_packet.py`, `tests/test_lifecycle_submission.py` | Question intake, bounded review packets, gap records, repair packets, decisions, and submission support. |
| Assurance depth, evidence microscope, and decision card | `EXPERIMENTAL` | `Python API (uriel.assurance_case, uriel.decision_card)` | Windows, macOS, Linux | `src/uriel/assurance_case.py`, `src/uriel/decision_card.py`, `tests/test_assurance_depth.py` | Exploratory assurance chains, evidence-strength records, and decision artifacts; no dedicated CLI contract yet. |
| Synthetic Forge Trial fixture and adjudicated scorer | `BETA` | `python scripts/check_forge_trial.py` | Windows, macOS, Linux | `src/uriel/forge_trials.py`, `tests/test_forge_trials.py` | Validates the sealed synthetic fixture and scores supplied adjudicated findings; it does not claim a detector was run. |
| Evidence ingress and Data Desk | `EXPERIMENTAL` | `uriel data plan / import / inspect / diff / reconcile / verify-generation` | Windows, macOS, Linux | `src/uriel/data_contracts.py`, `src/uriel/data_ingress.py`, `src/uriel/data_desk.py`, `tests/test_data_contracts.py`, `tests/test_data_ingress.py`, `tests/test_data_desk.py`, `tests/test_cli.py` | Bounded local immutable intake, structural generations, per-record delta ledgers, derived indexes, preserve-all reconciliation, and deep verification; no scientific finding or Gate 0 authority. |
| Operational Forge Method closure engine | `PLANNED` | `n/a (planned capability)` | Windows (planned), macOS (planned), Linux (planned) | — | The Forge of Uriel is the public identity; a general automatic milestone-closure engine is not implemented. |
| Built-in local-model adapter | `PLANNED` | `n/a (planned capability)` | Windows (planned), macOS (planned), Linux (planned) | — | External and local models can consume bounded prompts today; Uriel does not ship an inference provider. |
| Desktop GUI and native installer | `PLANNED` | `n/a (planned capability)` | Windows (planned), macOS (planned), Linux (planned) | — | The supported product is currently CLI/Python-first. |
