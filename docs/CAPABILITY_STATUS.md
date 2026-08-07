# Uriel Forge Capability Status

Commit: `748cecce9b69161c1a2a135d4c80c133c06a1274`

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
