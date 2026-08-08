# The Forge Trials

The **Forge Trials** are reproducible fixtures for evaluating research-review
workflows. A fixture can validate its own inputs, answer key, rubric, and clean
recomputation. Detector performance exists only after a blind report is mapped
to the answer key and adjudicated.

---

## 1. Synthetic Gold Standard Trial: `synthetic-001`

`synthetic-001` is the first official Synthetic Gold Standard Forge Trial.
Its 24 seeded issues are fully known to the answer key and hidden during a
blind run.

- **Location**: [`benchmarks/forge_trials/synthetic-001/`](../benchmarks/forge_trials/synthetic-001/)
- **Input Folder**: [`benchmarks/forge_trials/synthetic-001/INPUT/`](../benchmarks/forge_trials/synthetic-001/INPUT/)
- **Answer Key Folder**: [`benchmarks/forge_trials/synthetic-001/ANSWER_KEY/`](../benchmarks/forge_trials/synthetic-001/ANSWER_KEY/)

### Separation Rule
`INPUT` and `ANSWER_KEY` are kept strictly separated. The answer key is never altered or overfitted to artificially boost Uriel's score.

### Seeded issues in the answer key (not automatic detections)
The synthetic manuscript and dataset contain 24 seeded flaws across 5 risk categories:
1. **Gate 0 (Data Readiness & Integrity)**: Duplicate participant IDs, malformed join keys, unit mismatches (Fahrenheit vs Celsius room temperatures), excluded baseline records.
2. **Gate 1 (Scope & Claim Language)**: Causal overreach in title ("Indoor Plants Dramatically Reduce Cognitive Fatigue"), overgeneralized population scope.
3. **Gate 2 (Evidence & Citation Lineage)**: Abstract claim mismatches, unsupported subgroup statistics.
4. **Gate 3 (Adversarial Robustness & Limitations)**: Omitted null results in task-time metrics, hidden confounding variables, unaddressed alternative explanations.
5. **Repair & Next Study Planning**: Concrete, deterministic repair targets to produce an honest, publication-ready revision.

### Truth boundary

Run the fixture-integrity check with:

```text
python scripts/check_forge_trial.py
```

That command verifies required files, unique issue identifiers, the 100-point
scorecard, hashes, and the clean-summary recomputation. It deliberately reports
`detector_status: NOT_RUN` and no precision, recall, or release verdict.

To calculate detector metrics, first perform a blind run using only `INPUT/`
and `TRIAL_PROMPT.txt`. Afterward, a human adjudicator maps supported report
findings to answer-key issue IDs. Only those supplied IDs are scored.

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
