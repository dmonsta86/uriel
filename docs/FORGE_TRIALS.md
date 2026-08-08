# The Forge Trials

The **Forge Trials** are reproducible demonstrations and benchmark cases that test how **The Forge of Uriel** evaluates research papers, verifies data readiness, traces claims to evidence, and generates concrete repair paths.

They demonstrate what Uriel detects, what it refutes, what it preserves, and how it furthers research.

---

## 1. Synthetic Gold Standard Trial: `synthetic-001`

`synthetic-001` is the first official Synthetic Gold Standard Forge Trial. Its ground truth is fully known and deterministically verified.

- **Location**: [`benchmarks/forge_trials/synthetic-001/`](benchmarks/forge_trials/synthetic-001/)
- **Input Folder**: [`benchmarks/forge_trials/synthetic-001/INPUT/`](benchmarks/forge_trials/synthetic-001/INPUT/)
- **Answer Key Folder**: [`benchmarks/forge_trials/synthetic-001/ANSWER_KEY/`](benchmarks/forge_trials/synthetic-001/ANSWER_KEY/)

### Separation Rule
`INPUT` and `ANSWER_KEY` are kept strictly separated. The answer key is never altered or overfitted to artificially boost Uriel's score.

### Seeded Issues & Detections (24 Seeded Flaws)
The synthetic manuscript and dataset contain 24 seeded flaws across 5 risk categories:
1. **Gate 0 (Data Readiness & Integrity)**: Duplicate participant IDs, malformed join keys, unit mismatches (Fahrenheit vs Celsius room temperatures), excluded baseline records.
2. **Gate 1 (Scope & Claim Language)**: Causal overreach in title ("Indoor Plants Dramatically Reduce Cognitive Fatigue"), overgeneralized population scope.
3. **Gate 2 (Evidence & Citation Lineage)**: Abstract claim mismatches, unsupported subgroup statistics.
4. **Gate 3 (Adversarial Robustness & Limitations)**: Omitted null results in task-time metrics, hidden confounding variables, unaddressed alternative explanations.
5. **Repair & Next Study Planning**: Concrete, deterministic repair targets to produce an honest, publication-ready revision.

---

## 2. Recent Open-Paper Trial Proposals

In addition to synthetic benchmark cases, Uriel documents candidate open-access research papers for real-world stress testing. These candidates are documented as trial proposals (not prejudged targets) under verified open-access licenses (CC BY).

### Proposal 1: Peer Reviewer Citation Influence
- **Journal**: eLife (2025)
- **DOI**: `10.7554/eLife.108748.4`
- **License**: CC BY 4.0
- **Data Availability**: Openly available linked repository
- **Focus**: Matched observational design, causal language discipline, planned vs unplanned analyses, open peer-review tracking.

### Proposal 2: Transparency of Research Practices in Cardiovascular Literature
- **Journal**: eLife (2025)
- **DOI**: `10.7554/eLife.81051`
- **License**: CC BY 4.0
- **Data/Scripts**: Linked Open Science Framework project
- **Focus**: Reproducibility terminology, sampling flow, method-results consistency, potential vs actual reproduction.

### Proposal 3: CellSeg3D — Self-Supervised 3D Cell Segmentation
- **Journal**: eLife (2025)
- **DOI**: `10.7554/eLife.99848.4`
- **License**: CC BY 4.0
- **Data/Code**: Labeled data on Zenodo, public code repositories
- **Focus**: Paper/code/data consistency, benchmark selection, independent reproducibility, model comparison claims.

---

## Public Report Rule

For any real-world paper trial, public reports must disclose:
- Candidate finding vs confirmed finding
- Exact evidence location
- Human adjudication & author response (when available)
- False-positive and unresolved status
- Version and license information

Candidate software findings **must never** be presented as proven author errors, misconduct, or author intent.
