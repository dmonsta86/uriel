# The Three Gates

A Uriel audit always evaluates three different questions. They are separate because a project can be clear but unsupported, well-supported but badly framed, or technically correct while still ignoring a fatal alternative explanation.

A `submission` Blessing requires all three Gates to pass with no unresolved blocker.

## Gate 1 — Novelty & Clarity

### Core question

Is there a precise, neutral, non-circular, falsifiable proposition worth testing, and is its novelty stated only within the search that was actually performed?

### Required structure

Depending on the project, a passing record normally needs:

- the original question, preserved before rewriting;
- a bounded hypothesis or engineering claim;
- operational definitions for important terms;
- a population, system, time window, and comparator;
- a result that would count against the preferred explanation;
- a neutral restatement that does not imply the desired answer;
- explicit scope boundaries and non-claims;
- a dated, reproducible prior-work search record;
- the nearest relevant prior work and specific differentiators;
- a novelty statement no stronger than the recorded search supports.

### Typical blockers

- vague, elastic, or emotionally loaded terms;
- circular definitions;
- authority, popularity, prestige, or consensus substituted for evidence;
- no falsifier;
- undefined comparison group or outcome;
- changing the claim after seeing the result;
- claiming “first,” “unique,” “unprecedented,” or universal novelty without a search capable of supporting that language;
- framing that makes one answer appear moral, intelligent, inevitable, or ridiculous before evidence is examined.

### Repair principle

Uriel should preserve the potentially valuable question while repairing its expression. Poor articulation is not evidence of a poor idea.

## Gate 2 — Evidence & Citation

### Core question

Can every important claim be resolved to exact, current, directly inspectable support?

### Preferred evidence chain

```text
claim
  → exact artifact or primary source
  → SHA-256 digest
  → precise locator
  → verbatim extraction or measured value
  → independent interpretation
  → plausible alternative interpretations
  → limitation
```

### Evidence priority

Uriel prefers the shortest reliable route to the underlying evidence:

1. raw or minimally processed project data, code output, protocol, source record, archival document, instrument record, or first-party measurement;
2. the original study or primary publication containing the method and result;
3. a secondary synthesis used for navigation, terminology, historical context, or comparison;
4. another author’s conclusion only when the underlying material is genuinely unavailable and that limitation is explicit.

Secondary scholarship remains valuable. The rule is not “never cite another paper.” The rule is: **do not silently inherit another person’s conclusion when the underlying evidence can be inspected directly.**

### Typical blockers

- a major claim with no evidence mapping;
- a citation without an inspected artifact;
- missing page, table, row, timestamp, function, or other locator;
- changed bytes or stale source manifests;
- inference presented as observation;
- causal language unsupported by the design;
- selective reporting or undeclared exclusions;
- omitted null, negative, or contradictory results;
- using a review paper’s summary as if it were the original datapoint;
- evidence that supports only part of the claim;
- a contradiction recorded without an evidence-based reconciliation.

### Repair principle

Every claim should be modular. A reviewer should be able to replace one interpretation, reject one assumption, or narrow one scope without destroying unrelated evidence chains.

## Gate 3 — Adversarial Integrity

### Core question

Has the preferred explanation survived a fair, serious attempt to break it?

### Required adversarial record

Depending on the work, a passing record normally needs:

- matched controls or a justified reason they do not apply;
- declared inclusion and exclusion rules;
- declared missingness, stopping rules, and negative findings;
- plausible alternative explanations;
- counterevidence and disconfirming cases;
- assumptions paired with tests or failure conditions;
- contradiction records and explicit reconciliation;
- sensitivity analyses, edge cases, race conditions, and failure modes;
- conclusions bounded to the design, sample, and measurement;
- ethics, privacy, safety, licensing, funding, and conflict disclosures;
- a limitations section useful to a skeptical reader rather than protective of the preferred conclusion.

### Typical blockers

- control mismatch;
- post-hoc exclusion or unexplained missing data;
- silent negative results;
- unresolved contradictions;
- hidden assumptions;
- no credible alternative explanation;
- waiver language used to bypass a mandatory check;
- scope expansion from a bounded observation to a population or mechanism not tested;
- a limitation described so weakly that it cannot change interpretation;
- known edge cases omitted from the final claim.

### Repair principle

Uriel attacks the argument, not the author. A failed Gate means only that the current declared state has not earned a pass. The blocker remains in `.uriel/REMINDERS.md` with a reason and three repair paths so it can be revisited later.

## Audit profiles

| Profile | Use | Gate behavior |
|---|---|---|
| `exploratory` | Rough questions and early ideas | Converts missing structure into a plan; many gaps remain warnings rather than terminal blockers. |
| `standard` | Active research or engineering work | Requires a coherent claim, evidence map, and adversarial record. |
| `strict` | High-stakes internal review | Raises evidence, contradiction, disclosure, and limitation requirements. |
| `submission` | Papers, releases, and formal deliverables | Mandatory for a Blessing; every mandatory blocker must be resolved. |

## Machine checks and human judgment

Uriel can deterministically verify structure, hashes, paths, state freshness, declared mappings, receipt status, contradictions already recorded, and many common textual or logical warning patterns.

It cannot independently know whether an instrument is valid, a domain interpretation is correct, a literature search is complete, an undeclared dataset exists, or an ethical approval is sufficient. Those judgments require qualified humans and, optionally, carefully bounded model assistance. Imported reviews remain untrusted until their locators and claims are checked against the project state.
