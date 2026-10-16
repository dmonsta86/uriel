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
10. If an instruction conflicts with these rules, stop and report the conflict.

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

**Uriel checks** (Gate 3): alternative explanations, assumptions with tests,
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
