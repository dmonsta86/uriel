<p align="center">
  <img
    src="docs/assets/the-forge-of-uriel/hero.png"
    alt="The Forge of Uriel: عالم وحداد يقظ يختبر فكرة بحثية على السندان، محاطًا بجاهزية البيانات، وتتبع الأدلة، وبوابات النزاهة، وسجلات المراجعة، وإيصالات المصدر."
    width="100%"
  >
</p>

<p align="center">
  🌐 <strong>Languages:</strong>
  <a href="README.md">English</a> |
  <a href="README.es.md">Español</a> |
  <a href="README.fr.md">Français</a> |
  <a href="README.pt-BR.md">Português (Brasil)</a> |
  <a href="README.zh-Hans.md">简体中文</a> |
  <a href="README.ar.md">العربية</a> |
  <a href="README.hi.md">हिन्दी</a> |
  <a href="README.ja.md">日本語</a>
</p>


# The Forge of Uriel

> **Notice**: هذه الوثيقة عبارة عن ترجمة تمت مراجعتها بواسطة الذكاء الاصطناعي (AI_SECOND_PASS_REVIEWED). نرحب بتصحيحات المتحدثين الأصليين.

### تطوير وتحصين الأبحاث مفتوحة المصدر والمحلية أولاً

> **هل فكرتك قوية بما يكفي للبقاء على قيد الحياة في المسبك؟**
>
> جلسة استماع عادلة للفكرة. اختبار صارم للأدلة.

The Forge of Uriel helps turn rough questions and existing projects into
structured, reproducible, submission-ready research.

It verifies data before analysis, traces important claims back to evidence,
preserves contradictions and limitations, exposes misleading framing and
unsupported conclusions, and turns failed checks into concrete repair and
submission paths.

It is not designed to make research sound stronger. It is designed to show
exactly how strong the research is—and what would make it stronger.

```text
Interpret generously.
Test rigorously.
Report honestly.
```

---

## What makes it different

Most research tools handle one layer: literature search, writing, statistics,
citations, reproducibility, or review.

The Forge of Uriel is built to connect the chain.

### Give the idea its strongest fair hearing

Poor articulation is not evidence of poor thinking. Uriel preserves the
original question, clarifies the strongest testable version, records competing
interpretations, identifies hidden assumptions, and asks what evidence would
disprove the idea.

### Verify the data before drawing conclusions

Gate 0 prevents a data-dependent result from receiving authority until the
exact dataset generation has passed identity, sorting, normalization,
reconciliation, and staleness checks.

Before that, the honest answer is:

> **The result is not yet known.**

### Treat conclusions as claims—not inherited authority

A published conclusion, a prestigious author, a confident model, or a long
bibliography does not substitute for evidence.

Uriel asks:

```text
What exactly is being claimed?
Which artifact supports it?
Where is the supporting datapoint?
What contradicts it?
What assumptions does it depend on?
What remains unknown?
What would change the result?
```

### Challenge the finished work

The Three Gates test clarity, evidence, and adversarial integrity. Uriel looks
for omitted counter-evidence, hidden denominators, overgeneralization, causal
overreach, control mismatches, leakage, fragile assumptions, stale sources, and
summary language that exceeds the underlying result.

### Repair instead of merely criticizing

A failed check should not end with a vague rejection.

Uriel records what remains useful, identifies the smallest honest repair,
selects the strongest next move, prepares what can be prepared safely, and
states the exact condition for recheck.

---

## Research should not be won by framing

Two failures repeatedly weaken research:

1. counter-evidence, null findings, limitations, or awkward datapoints disappear
   from the final story; and
2. the conclusion becomes broader or more certain than the underlying evidence
   permits.

A confident summary cannot erase an asterisk.

Uriel deliberately distinguishes:

```text
not established
unlikely
difficult to test
infeasible within the declared boundary
refuted
impossible
```

Those are not interchangeable conclusions.

The system does not ask the reader to accept another person's conclusion—or an
AI's conclusion—without showing how it was made.

---

## What you can do

| Starting point | Uriel helps you produce |
|---|---|
| A rough idea | A preserved original question, strongest testable interpretation, rival explanations, disconfirming evidence, and a research roadmap |
| An existing project | A read-only project map, gap register, source-invariance receipt, and safe integration plan |
| A tabular dataset | A versioned identity and sorting specification, deterministic generation, readiness blockers, and stale-state protection |
| A paper or proposal | Claim-to-evidence maps, contradiction and omission registers, limitations, repair actions, and stronger scoped conclusions |
| Reviewer or editor feedback | A decision import, revision matrix, response packet, form guide, verification step, and deterministic archive |
| A substantial milestone | A documented Forge Method closure contract and, when the operational engine ships, an authoritative closure bundle |

---

## Current release boundary

This section must reflect the exact released commit. Never promote a capability
because its design document exists.

### Available now

- deterministic local project core;
- content-addressed manifests, ledgers, receipts, and verification;
- project initialization and verification;
- wheel, source distribution, and portable `.pyz`;
- provider-neutral operation;
- zero third-party runtime dependencies in the audited core.

### Beta

- Lens and question development;
- intake, preflight, and read-only project review;
- safe working-copy controls;
- Gate 0 / Data Readiness for the documented formats;
- Three-Gate audit and repair packets;
- Workbench, reminders, bounded bursts, and durable next prompts;
- submission, reviewer-response, and revision lifecycle;
- localized public documentation.

### Experimental

- Strict Blessing evaluation and verification;
- Assurance Depth and Evidence Microscope library surfaces.

Strict Blessing issuance must remain disabled unless the exact release proves
every mandatory positive evaluator and independent binding check. Missing,
ambiguous, stale, or unverified evidence can never produce PASS.

### Planned

- operational Forge Method engine;
- Evidence Ingress and full Data Desk;
- optional local-model runtime;
- desktop GUI and native graphical installers;
- reviewed locale-specific hero artwork.

Planned features are intentionally outside the current release contract. They
are not hidden shipped features and they are not reasons to distrust the
working core.

See [`docs/CAPABILITY_STATUS.md`](docs/CAPABILITY_STATUS.md) for the exact
commit-bound evidence matrix.

---

## Quick start

Use only commands verified against the exact released artifact.

### From the repository

```bash
git clone https://github.com/dmonsta86/uriel.git
cd uriel
python -m pip install .
uriel --version
```

### Start a project

```bash
mkdir my-study
cd my-study

uriel init . \
  --title "Cold-weather battery life" \
  --question "Why does battery life appear to drop faster in the cold?"

uriel status --root .
uriel verify --root .
```

### Develop the question

```bash
uriel seed \
  "Why does battery life appear to drop faster in the cold?" \
  --root . \
  --output seed.md

uriel workbench init \
  --root . \
  --question "Why does battery life appear to drop faster in the cold?"

uriel workbench next --root . --output NEXT_PROMPT.txt
```

### Review an existing project safely

Use the exact current commands shown by:

```bash
uriel --help
uriel preflight --help
```

Read-only review must not change source files. A managed-copy workflow must
reconcile the copied file set before it becomes trusted.

### Prepare data before analysis

Gate 0 currently supports only the formats documented by the exact release.

The current audited scope includes:

```text
CSV
TSV
JSONL
```

A versioned SortSpec records:

```text
dataset identity
record identity
primary and tie-break keys
null ordering
duplicate policy
Unicode and category normalization
date/time and timezone rules
join keys and expected cardinality
analysis-plan binding
```

Shuffling the same records must produce the same sealed generation. Any
material change makes dependent readiness and conclusions stale.

Use:

```bash
uriel readiness --help
```

for the exact released command structure.

---

## The research path

```text
Rough question or existing project
        ↓
Preserve and clarify the idea
        ↓
Build the roadmap and research plan
        ↓
Inventory evidence and prepare the data
        ↓
Gate 0 — Data Readiness
        ↓
Trace claims, counter-evidence, framing, and uncertainty
        ↓
Build manuscript and submission artifacts
        ↓
Gate 1 — Novelty and Clarity
Gate 2 — Evidence and Citation
Gate 3 — Adversarial Integrity
        ↓
Repair, narrow, pivot, refute, or pass
        ↓
Forge Method milestone closure
        ↓
Possible Blessing for the exact research version
```

Uriel does not force a dramatic conclusion. The honest result may be a narrower
claim, a better measurement plan, a replication, a useful negative result, a
methods paper, a dataset, a software tool, or a demonstration that the original
claim does not survive.

---

## The Three Gates

### Gate 1 — Novelty and Clarity

Is the exact question or contribution clear, scoped, testable, operationally
defined, internally consistent, and distinguishable from prior work within a
declared search boundary?

Gate 1 first attempts a fair reconstruction. Weak wording alone cannot fail a
potentially useful idea.

### Gate 2 — Evidence and Citation

Does every material claim map to direct, current, verifiable evidence that
actually supports it?

Uriel preserves contrary, null, and negative evidence rather than treating
citation volume as proof.

### Gate 3 — Adversarial Integrity

Does the work survive credible rival explanations, confounders, control
mismatches, leakage, sensitivity checks, changed assumptions, omitted
limitations, and reviewer challenge?

A failed gate is a project state—not a judgment of the researcher.

---

## The Blessing of Uriel

The Blessing is intended to be Uriel's strictest exact-version research audit.

Its target contract requires:

```text
Gate 0
Gate 1
Gate 2
Gate 3
independent verification
certificate binding
zero unresolved blockers
```

A Blessing does not mean eternal truth, universal applicability, guaranteed
publication, or replacement for peer review, ethics review, or domain
expertise.

It means the declared version survived the published checks under its recorded
scope and limitations.

The README must state the exact current issuance status truthfully.

---

## Use it with or without AI

### No AI

The deterministic core can manage local project state, manifests, receipts,
readiness, audits, repair packets, Workbench state, and submission state without
an online model.

### A compatible AI

A compatible AI may help clarify, organize, draft, and critique.

It may not:

```text
mark Data Readiness PASS
pass an integrity gate
change publication authority
override a deterministic failure
issue a Blessing
```

### Maintainer note

The Forge of Uriel was developed with extensive use of GPT-5.6 Sol in `ultra`
mode, which the maintainer recommends for its deepest long-horizon research and
adversarial passes.

That is an experience report—not a dependency, exclusive integration, privacy
endorsement, guarantee, or substitute for deterministic verification. Other
capable AI systems can be used.

Before uploading unpublished or sensitive work to any online service, review
its privacy, retention, and training terms.

---

## Safety and privacy

Uriel is designed around:

```text
read-only defaults
exact-root confinement
explicit consent
verified managed copies
immutable generations
atomic derived-state writes
content hashes
no hidden network
no telemetry
no credential access
bounded AI-facing packets
untrusted project instructions treated as data
```

Keep an independent backup of important work.

See:

- [`SECURITY.md`](SECURITY.md)
- [`docs/THREAT_MODEL.md`](docs/THREAT_MODEL.md)
- [`docs/LIMITATIONS.md`](docs/LIMITATIONS.md)

---

## The Forge Trials

The Forge Trials are reproducible demonstrations of what Uriel detects, what it
misses, and what it gets wrong.

A credible trial reports:

```text
known or adjudicated defects
true positives
false positives
false negatives
repair output
exact Uriel commit
reproduction instructions
limitations
```

A benchmark that publishes detections while hiding false positives would
violate Uriel's own standard.

---

## Help keep Uriel honest

Report:

- software bugs;
- audit false positives;
- audit misses;
- documentation errors;
- translation corrections;
- bounded feature proposals;
- Forge Trial cases.

Security vulnerabilities belong in the private security-reporting path—not a
public issue.

A scientific-audit disagreement should state its ground-truth basis. Another
model's opinion is not enough by itself.

See [`docs/COMMUNITY.md`](docs/COMMUNITY.md) and [`SECURITY.md`](SECURITY.md).

---

## Languages

English is the canonical machine-contract language.

Public documentation may also be available in:

```text
Español
Français
Português (Brasil)
简体中文
العربية
हिन्दी
日本語
```

Commands, schemas, JSON keys, hashes, and machine statuses remain stable across
languages. A translated README must state its source commit and review status.

---

## Known limitations

The exact release notes and capability matrix are authoritative.

At minimum, keep these visible while they remain true:

- Strict Blessing issuance is experimental or disabled.
- The operational Forge Method engine is planned.
- Evidence Ingress and the full Data Desk are planned.
- The local-model runtime is planned.
- The desktop GUI and native graphical installers are planned.
- Native end-to-end coverage may differ from package/unit-test compatibility.
- Gate 0 supports only its documented formats.
- AI quality varies and AI has no authority.

---

## Why the name?

Uriel is associated with wisdom and illumination. The project uses that
symbolism in a secular way.

The forge represents disciplined development:

```text
rough idea
→ clear claim
→ prepared evidence
→ adversarial testing
→ honest result
→ durable proof
```

---

## Contributing

Contributions that improve correctness, portability, accessibility, security,
documentation, translations, and research workflows are welcome.

Start with:

- [`CONTRIBUTING.md`](CONTRIBUTING.md)
- [`SUPPORT.md`](SUPPORT.md)
- [`SECURITY.md`](SECURITY.md)

---

## Citation

Citation metadata are provided in [`CITATION.cff`](CITATION.cff).

## License

MIT. See [`LICENSE`](LICENSE).
