# Uriel Capability Status & Inventory

| Capability | Status | Verified entry point | Platforms | Notes |
|---|---|---|---|---|
| Deterministic project core & packaging | `SHIPPED` | `uriel init / uriel verify` | Windows, macOS, Linux | Offline-first, content-addressed project management and receipts. |
| Data Readiness & Gate 0 | `BETA` | `uriel readiness / python -m uriel.data_readiness` | Windows, macOS, Linux | Strict raw data hash binding, readiness check, order invariance. |
| Three Integrity Gates (Gates 1, 2, 3) | `BETA` | `uriel audit / python -m uriel.gate_contract` | Windows, macOS, Linux | Gate 1 (Frame), Gate 2 (Evidence & Calculation), Gate 3 (Adversarial Challenge). |
| Strict Blessing Integration & Independent Verifier | `EXPERIMENTAL` | `uriel blessing / python -m uriel.strict_blessing` | Windows, macOS, Linux | Requires Gate 0 PASS, 3 Gate PASS, positive evaluators, independent verifier PASS. |
| Research Lifecycle, Workbench & Free-Model Burst Surfaces | `BETA` | `uriel workbench / uriel burst` | Windows, macOS, Linux | Read-only bounded AI surfaces, Gap Register, Repair Packets. |
| Assurance Depth, Evidence Microscope & Decision Card | `EXPERIMENTAL` | `python -m uriel.assurance_case` | Windows, macOS, Linux | 4-Layer Assurance Chain, Evidence Strength Vector, Decision Card & Proof Bundle. |
| Evidence Ingress & Data Desk | `PLANNED` | `n/a (planned capability)` | Windows (Planned), macOS (Planned), Linux (Planned) | Planned safe ingestion and data desk reconciliation. |
| Uriel Forge Method Engine | `PLANNED` | `n/a (planned milestone closure engine)` | Windows (Planned), macOS (Planned), Linux (Planned) | Uriel Forge is public display branding; operational Forge closure engine is planned. |
| Generic Local-Model Adapters | `PLANNED` | `n/a (planned local inference adapter)` | Windows (Planned), macOS (Planned), Linux (Planned) | Planned provider-neutral local inference wrapper. |
| Desktop Native GUI & Installer | `PLANNED` | `n/a (planned native application)` | Windows (Planned), macOS (Planned), Linux (Planned) | Standalone native GUI application; currently CLI/Python-first. |
