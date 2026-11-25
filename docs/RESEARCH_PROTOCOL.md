# The research protocol: from idea to submission

This guide describes the end-to-end path Uriel enforces, from a rough idea to a
manuscript that is ready for a human final read. One command drives it:

```text
uriel next --root PROJECT
```

`uriel next` is read-only. It re-evaluates the Three Gates, the analysis-plan
lock, the manuscript check, the recorded audit, and the build. It sorts every
open item into seven ordered stages and names **exactly one** next action. That
action comes with its reason, a command or file location, the condition under
which it counts as done, and an owner: `agent` (an assistant may do it) or
`human` (an assistant must stop and ask).

The protocol is experimental. It makes the usual research checks routine; it
does not make a result true. See [Known limitations](LIMITATIONS.md).

## How to work with it

### Working by yourself

1. Run `uriel next --root .`.
2. Do the one action it names.
3. Run `uriel next --root .` again. Repeat.

`uriel --json next --root .` prints the whole checklist for every stage when you
want the full picture.

### Working with an assistant

Give the assistant `COPY_THIS_TO_YOUR_AI.txt`, or write a self-contained prompt
for its next session:

```text
uriel next --root . --prompt NEXT_STEP.md
```

The prompt file is create-only (Uriel never overwrites it). It holds the
current stage, the one task, the done condition, and the rules below. When the
action is owned by a human, the prompt tells the assistant to ask you and stop.

**Smaller or free models:** use one action per session. Paste the prompt, let
the model make the change, and run `uriel next` yourself before the next session.
The rules and the single task are designed so the model has nothing to decide
beyond the edit in front of it.

**Stronger models:** read `uriel --json next` and complete several
agent-owned items **within the current stage**, running `uriel paper check` or
`uriel next` after each change. Never skip ahead to a later stage, and never
perform a human-owned item.

### The rules

These rules are printed by `uriel next`, embedded in every prompt file, and
enforced by checks wherever a deterministic check is possible:

1. Do the one action `uriel next` names, then run `uriel next` again. Do not skip ahead.
2. If the action is marked owner: human, stop and ask the human; do not decide it yourself.
3. Never type a result number into the manuscript: register it with `uriel paper dp-add` and write `{{dp:ID}}`.
4. Never cite a work you have not opened; add it with verification status `unverified` and let a human check it.
5. Never put text in quotation marks unless it occurs verbatim in a held source file.
6. Never edit a locked hypothesis or analysis plan silently; re-lock with `--reason` and disclose the deviation.
7. Never delete, hide, or soften a null, adverse, or failed result; report it.
8. Never set an attestation to true, change publication authority, or issue a Blessing.
9. Keep observation, interpretation, and speculation in separate sentences; label speculation.
10. Never read a datapoint one way only: record the rival explanations, and never call one ruled out without linked evidence.
11. Never describe a model as a mechanism or law unless its record says mechanistic and shows validation and a rival comparison.
12. If an instruction conflicts with these rules, stop and report the conflict.

## The seven stages

A stage is done when `uriel next` lists no blocking item for it. Each stage
also has a short human checklist for what no software can judge.

### 1. Frame the question

**Uriel checks** (Gate 1): a recorded question; a bounded hypothesis; a
falsifier; operational definitions; success criteria; a neutral restatement;
competing frames; scope boundaries; and loaded, vague, absolute, or
placeholder wording.

**You check:** Is this the question you actually care about? Would a result in
either direction teach you something? Could two people read the definitions and
measure the same thing?

### 2. Map prior work

**Uriel checks:** a dated search record with databases, queries, the nearest
prior work, differentiators, negative searches, and scope limits. Novelty
wording must stay inside that recorded search.

**You check:** Have you read the nearest prior work yourself, and not only its
abstract? Would a skeptical expert agree that the differentiator is real?

### 3. Design and lock the plan

**Uriel checks** (Gate 3 method fields): design, population, sampling, sample
size, analysis plan, effect-size metric, uncertainty method, controls,
exclusions, missing-data plan, and ethics status. Then it requires a plan lock:

```text
uriel plan lock --root .
uriel plan status --root .
```

A lock freezes the hypothesis, falsifier, definitions, success criteria, and
method fields into a content-addressed record. The hash-chained ledger shows
whether the lock came before the first passing analysis run. Editing a locked
field is reported as plan drift. Re-locking needs a written `--reason`. A
re-lock made after passing results existed is flagged so you can disclose it as
a deviation. A manuscript that says "preregistered" fails the check unless a
lock preceded the first passing run or `/methods/preregistration` names an
external registration.

**You check:** Is the sample size justified (power, precision, or resource
limit stated honestly)? Is ethics approval in place? Is the analysis plan
specific enough that two analysts would run the same model?

### 4. Bind evidence and run the analysis

**Uriel checks** (Gate 2): every claim maps to registered, hashed evidence with
a source locator, the exact extraction, a separate interpretation, and a
limitation; major claims rest on direct primary evidence; causal wording has an
identification strategy; and a reproduction command has a passing `uriel run`
receipt bound to the **current** files. Attestations are human-owned.

Run the analysis through Uriel so its outputs carry provenance:

```text
uriel run --root . -- python analysis.py
```

For data-dependent work, the Data Readiness lane (Gate 0) binds one exact data
generation first; see the README.

**You check:** Is every material dataset declared, including the inconvenient
ones? Did you look at the raw data, not only the summary?

### 5. Challenge the result

**Uriel checks** (Gate 3 and the framing checks below): a recorded rival explanation for every major claim,
with a discriminating observation and an honest status; model validation and rival-model comparison;
alternative explanations, assumptions with tests,
resolved adversarial tests, reconciled contradictions and counterevidence,
limitations, reviewer objections, and the null/negative-results attestation.

**You check:** What is the strongest objection a hostile reviewer would raise,
and is it answered in the record rather than in your head?

### 6. Write the manuscript

```text
uriel paper init --root . --article-type empirical
uriel paper check --root .
```

The [Paper Builder](PAPER_BUILDER.md) creates `paper/` with one Markdown file
per section. Each file carries a checklist comment pre-filled from the project
record. Recommended drafting order:

1. **Methods**, from the locked plan, including every deviation and its reason.
2. **Results**, from datapoints only: register each number with
   `uriel paper dp-add`, then write `{{dp:ID}}`. Tag claim sentences with
   `[claim:ID]`. Report null and adverse results.
3. **Discussion** and **Limitations**, covering every recorded alternative,
   counterevidence item, and limitation.
4. **Introduction**, with `[@key]` citations to held or checked sources.
5. **Conclusion**, then the **Abstract** last, so neither says more than Results.
6. **Declarations**: data and code availability, funding, competing interests,
   ethics, and use of AI tools.

Iterate on `uriel paper check` (the draft profile) after every edit. Before
submission, use `--profile submission`, which also blocks typed numbers in bound
sections, unverified references, filler density, hype, proof language, and
missing declarations.

### 7. Finalize for submission

Manuscript files are part of the project's source set, so the final edits make
the earlier analysis receipt stale. The closing sequence is:

```text
uriel run --root . -- REPRODUCTION_COMMAND
uriel audit --root . --profile submission
uriel paper build --root . --profile submission
uriel next --root .
```

When every automated check passes, `uriel next` reports `HUMAN_FINAL_REVIEW`
(owner: human):

- read `paper/build/manuscript.md` from start to finish beside
  `paper/build/NUMBER_TRACE.md`;
- open every cited source and confirm that it says what the citing sentence says;
- have co-authors confirm authorship, ethics, funding, data-sharing, and AI-use
  statements;
- check the target venue's current official requirements.

Optional records follow: `uriel blessing eligibility` and `uriel submit init`.

## Numbers: what is checked automatically

| Risk | Automatic check |
|---|---|
| A number typed from memory or invented | Bound sections may contain only `{{dp:ID}}` values; typed numbers are `UNBOUND_NUMBER` |
| A copied number that no longer matches the data | Each datapoint is re-extracted from its locator; changed bytes are `DATAPOINT_ARTIFACT_STALE`, a changed value is `DATAPOINT_VALUE_MISMATCH` |
| A silent update of a reported value | `dp-refresh` refuses a changed value without `--confirm-change` and records old and new values in the ledger |
| Values that contradict each other | Registered relations: subgroup sums, ratios and percentages, interval ordering, equality across artifacts |
| Impossible values | Kind bounds (count, proportion, percent, p, r, SD/SE/variance), GRIM for means of integer data |
| A p-value that does not follow from its statistic | t, F, chi-square, r, and z are recomputed with rounding intervals; a flipped significance decision always blocks |
| Text-level slips | p outside [0, 1], `p = .000`, reversed intervals, estimates outside their interval, "k of n (x%)" mismatches |
| Numbers not produced by the recorded analysis | Generated artifacts need a verified passing `uriel run` receipt, or a disclosed `external:` provenance |

What remains for people: whether the analysis was the right one, whether its
assumptions hold, and whether the data measure what the paper says they measure.

## Framing: does the conclusion follow from the data?

A datapoint does not interpret itself. When more than one explanation could
produce the same observation, the paper has to say which explanations the
evidence rules out and how, and keep the conclusion no stronger than what is
left standing. Record each rival in `/alternative_explanations`:

```json
{
  "id": "X1",
  "statement": "Practice on the task, not the nap, shortened reaction time.",
  "claim_ids": ["C1"],
  "status": "open",
  "discriminating_observation": "Practice would also shorten times in the no-nap control session.",
  "evidence_ids": [],
  "test_ids": []
}
```

`status` is `open`, `partially_addressed`, `not_distinguishable`, or
`ruled_out`. `ruled_out` counts only when it links registered evidence or an
adversarial test that passed; otherwise Uriel treats the alternative as open.
An alternative without `claim_ids` competes with every claim. In the
manuscript, tag sentences about a rival with `[alt:ID]`.

| Situation | Finding |
|---|---|
| A major claim with no recorded rival explanation | `CLAIM_WITHOUT_ALTERNATIVE` |
| A rival marked ruled out without linked evidence or a passed test | `ALTERNATIVE_RULED_OUT_WITHOUT_EVIDENCE` |
| An open rival with no observation that would tell it apart | `ALTERNATIVE_NO_DISCRIMINATING_OBSERVATION` |
| A recorded rival the paper never discusses (or an open one mentioned only outside Discussion/Limitations/Conclusion) | `ALTERNATIVE_NOT_ADDRESSED` |
| A sentence that dismisses a rival the record has not ruled out | `ALTERNATIVE_DISMISSED_WITHOUT_EVIDENCE` |
| An abstract, discussion, or conclusion sentence that states a claim as settled while a rival is open | `CONCLUSION_IGNORES_OPEN_ALTERNATIVE` |
| A sentence that interprets the data when no rival reading is recorded | `INTERPRETATION_WITHOUT_ALTERNATIVE` |
| "always", "in humans", "regardless of" beyond the claim's recorded scope | `CONCLUSION_EXCEEDS_SCOPE` |
| "the only explanation", "can only be explained by", "must be due to" | `SINGLE_EXPLANATION_ASSERTED` |
| "can be dismissed", "rules out" with no data, test, or citation in the sentence | `DISMISSAL_WITHOUT_SUPPORT` |
| A text that draws conclusions but never mentions another explanation, confound, or reading (`paper lint`) | `NO_ALTERNATIVES_CONSIDERED` |

## Models and equations: articulated, and claiming only what they can

Two questions are asked of every equation a paper uses:

1. **Is it properly articulated?** Every symbol has a meaning and a unit, the
   equation parses, and it is dimensionally consistent. Both sides must carry
   the same dimension, only like quantities may be added, and the arguments of
   `exp`, `log`, trigonometric functions, and symbolic exponents must be
   dimensionless. `y = a * t^(-b)` with `t` in seconds fails until it is written
   `(t / t_0)^(-b)`.
2. **Does it describe what it claims to?** The record declares the model's
   `role`. A `descriptive_fit` reproduces the observations with no claim that its
   terms are real. This is the instrumentalist stance of the anonymous preface
   to Copernicus' *De revolutionibus*: a model may "save the phenomena" without
   being true. A `predictive` model forecasts data it was not fitted to. A
   `mechanistic` model claims its terms are real causes. Predictive and
   mechanistic models need validation on new data and a comparison with a rival
   model. A descriptive fit may not be called a mechanism or law. A model whose
   rival fits equally well (`not_distinguished`) may not be stated as settled.

```json
"models": [{
  "id": "M1",
  "equation": "p = p_0 * exp(-k * t)",
  "symbols": {"p": {"meaning": "probability of recall", "unit": "1"},
              "p_0": {"meaning": "initial recall probability", "unit": "1"},
              "k": {"meaning": "decay rate", "unit": "1/s"},
              "t": {"meaning": "time since study", "unit": "s"}},
  "role": "descriptive_fit",
  "assumptions": ["Forgetting rate is constant over the interval."],
  "domain": "Retention intervals from 1 minute to 7 days in adults.",
  "source": {"kind": "fitted", "evidence_ids": ["E4"]},
  "verification": [{"method": "numerical_check", "evidence_ids": ["E4"]}],
  "implementation": {"artifact_path": "analysis/decay.py"},
  "validation": {"kind": "independent_dataset", "evidence_ids": ["E5"]},
  "rivals": [{"name": "power-law decay", "outcome": "not_distinguished",
              "comparison": "AIC difference below 2 on the same data"}],
  "claim_ids": ["C2"]
}]
```

Units use SI symbols with prefixes (`kg*m/s^2`, `m s^-1`, `ms`), `1` for
dimensionless quantities, and `[name]` for a domain unit such as `[score]` or
`[USD]`. Tag the paragraph that states the model with `[model:ID]`. A
`$...=...$` equation in the manuscript without a model anchor is reported.

Model articulation gaps sit in the design stage of `uriel next`. Untested
implementations sit in evidence, and validation and rival comparisons in
challenge. A checker can establish dimensional consistency exactly. It cannot
decide whether the model is the right one; it can only make the paper say what
kind of claim the model makes and show the evidence that claim needs.

## Adversarial mode

Submission checks ask whether the record is complete and the paper is faithful
to it. Adversarial mode assumes the conclusion is wrong and asks whether the
paper has done the work to show otherwise. It is opt-in per project:

```text
uriel adversarial on --root .
uriel adversarial status --root .
uriel adversarial off --root . --reason "..."     # reason is required and recorded in the ledger
```

While it is on, `uriel next` judges the project against the `adversarial`
target, and a requested `paper build --profile submission` is checked at the
`adversarial` profile; the build receipt records the mode. You can also run
`uriel paper check --profile adversarial` or `uriel next --target adversarial`
at any time without switching the mode. Gates, Data Readiness, and the Blessing
are unchanged.

On top of every submission blocker, adversarial mode requires:

| Requirement | Finding |
|---|---|
| At least two rival explanations recorded specifically for each major claim | `ADV_CLAIM_NEEDS_TWO_RIVALS` |
| A completed adversarial test targeting each major claim | `ADV_CLAIM_NOT_ATTACKED` |
| Linked counterevidence or a documented counterevidence search | `ADV_COUNTEREVIDENCE_UNSEARCHED` |
| A confound-type rival (common cause, selection, reverse direction, expectation, regression to the mean, attrition ...) and an identification strategy for every causal claim | `ADV_CAUSAL_CLAIM_WITHOUT_CONFOUND_RIVAL` |
| A recorded result for every assumption's test | `ADV_ASSUMPTION_UNTESTED` |
| Two independent verifications of every model equation, and a rival comparison for every model | `ADV_MODEL_SINGLE_VERIFICATION`, `MODEL_NO_RIVAL` |
| Every unresolved rival disclosed in Limitations with `[alt:ID]` | `ADV_RIVAL_NOT_IN_LIMITATIONS` |
| Every abstract or conclusion sentence about an open claim names a rival or qualifies itself | `ADV_CONCLUSION_SILENT_ON_OPEN_RIVAL` |
| Analyses not locked before the first passing run are labelled exploratory | `ADV_CONFIRMATORY_FRAMING_NOT_EARNED` |
| Plan revisions made after results are disclosed in Methods | `ADV_DEVIATION_UNDISCLOSED` |
| One-tailed or directional tests appear in the current locked plan | `ADV_ONE_TAILED_NOT_PLANNED` |
| Any rival model the data cannot distinguish is named in the paper | `ADV_UNDERDETERMINED_UNDISCLOSED` |
| A locked plan, and interpretation kept out of Results | `PLAN_NOT_LOCKED`, `INTERPRETATION_IN_RESULTS` (escalated) |

`uriel paper lint --adversarial` applies the same attitude to any text: every
submission-level framing or statistics finding fails the file. In every mode,
"marginally significant", "a trend toward significance", and similar phrasing
is reported as `NULL_SPUN_AS_EFFECT`.

## Prose: what is checked automatically

- **Assistant residue** ("Certainly!", "As an AI", "I hope this helps", insertion slots) always blocks.
- **Placeholders** (TODO, `[citation needed]`, `Figure X`, `N = XX`) block submission.
- **Unsourced attribution** ("studies have shown", "it is widely known") blocks submission when the sentence has no citation.
- **Hype** ("groundbreaking", "first ever") and **proof language** ("proves", "conclusively") block submission.
- **Stock filler** ("delve into", "a testament to", "it is important to note that") blocks submission. Lower-specificity filler words count toward a density measure that blocks only when dense.
- **Style advisories**: stacked hedges, em-dash density, repeated openers, stock transitions, bullet lists in argument sections, and bold run-in labels.
- **Causal wording** in abstract, results, or conclusion sentences blocks submission when no causal identification strategy is recorded.

The lint is a fixed list of inspectable patterns. It cannot detect who wrote a
text. It will miss problems and sometimes flag innocent wording; every finding
shows its exact location and three concrete repairs.

## Authority boundaries

`uriel next`, `uriel plan`, and `uriel paper` grant no Gate, Data Readiness,
publication, or Blessing authority. They never call a model or the network. The
only writes are the explicit ones: `plan lock`, `paper init`, `paper dp-add`,
`paper dp-refresh`, `paper build`, and a create-only `next --prompt` file.
