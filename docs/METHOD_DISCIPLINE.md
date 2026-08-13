# Method discipline after the idea is weighed

Uriel is not a statistical package and it does not choose a researcher's model,
prior, source, or conclusion. Its job is to make those choices visible,
reproducible, bounded, and honest after an idea has received a fair hearing.

This is the recommended method record for analyses that contain an observation
rule, competing assumptions, or uncertainty that could change the conclusion.
It is deliberately domain-neutral. A researcher may use a survival model,
Bayesian model, qualitative comparison, simulation, or another method; Uriel
records the method and verifies its declared evidence boundary without claiming
that the method is scientifically correct.

## The five-part record

### 1. State what could be observed

Declare the estimand, observation window, inclusion rule, and what counts as an
unobserved, censored, missing, or otherwise unresolved observation. Do not turn
an absence of observation into a negative result without stating that rule.

For a time-to-event analysis, the record should distinguish:

- the event that was actually observed;
- the deadline or window that was actually searched;
- observations that ended before the event could be seen; and
- observations that were never eligible for the analysis.

Uriel can bind the analysis plan and the resulting workload receipt. It does
not implement a domain-specific likelihood or silently repair an observation
rule.

### 2. Declare priors and assumptions separately from evidence

Prior odds, model weights, and other starting assumptions belong in the method
and assumption records. They are not evidence and must not be presented as if
they were observed facts.

Record why the assumption was selected, what alternative would be reasonable,
and how the result changes under that alternative. Keep the prior choice
separate from the source extraction and from the final interpretation.

Uriel can preserve and audit that separation. It does not select a preferred
prior or ship a universal prior table.

### 3. Preserve a sensitivity table, not only a headline number

Every material assumption or exclusion should have a named scenario. A useful
sensitivity record identifies the scenario, changed inputs, resulting output,
direction or status, and the condition under which the comparison is valid.

The table must retain scenarios that weaken, reverse, or fail to identify the
headline conclusion. A single best-case number is not a sensitivity analysis.

The table may be produced by a user-owned workload or another verified tool.
Uriel binds the exact input and output artifacts, the reproduction command, and
the limitations; it does not convert the table into a calibrated truth score.

### 4. Validate the exact source and the meaning used from it

An evidence row should contain the project-relative artifact, SHA-256, stable
source locator, smallest direct extraction, independent interpretation, and
evidence-specific limitation. The extraction and interpretation remain separate.

Hash binding proves which bytes were used. It does not by itself prove that the
right sentence, row, unit, or semantic token was interpreted correctly. For
important claims, record the exact token, value, row, page, or other semantic
anchor checked by the researcher, and preserve a negative case that should
fail if the anchor changes.

### 5. Carry the result forward without laundering uncertainty

After the method has run, Uriel's normal route is:

```text
exact source -> declared method -> reproducible workload -> Gates
             -> established / refuted / unknown / still useful
             -> bounded Next Move -> immutable continuation or export
```

The Forge forward path is the handoff after weighing. It records what remains
useful without turning an unresolved result into a pass, a blocker, or a claim
of scientific truth. A Blessing, when earned, attests to the exact recorded
project state and its implemented checks; it does not bless a hypothesis.

## Uriel's adoption boundary

The following method elements are supported as protocol, not as imported
project authority:

| Element | Uriel disposition | What Uriel adopts | What remains outside Uriel |
| --- | --- | --- | --- |
| Censored-observation likelihood | `USEFUL` | Explicit observation/censoring rules, bound analysis plan, reproducible result artifact | Domain-specific likelihood implementation and scientific interpretation |
| Prior-odds correction | `USEFUL` | Separate prior/assumption declaration and comparison of alternative priors | Choosing priors or treating prior odds as evidence |
| Sensitivity-table discipline | `USEFUL` | Named scenarios, retained adverse cases, exact table/output binding, and limitation reporting | A universal sensitivity score or automatic conclusion about robustness |
| Exact-source validation | `USEFUL` | Existing hash/path/locator checks plus an explicit semantic-anchor review boundary | Automatic semantic judgment, source-authority transfer, or network retrieval |

This is intentionally a small integration. The four elements improve how a
project records and tests a method, but they do not turn Uriel into the owner
of another research branch's claims, data, sources, or conclusions. If a
project cannot supply the declared observation rule, source anchor, or adverse
sensitivity case, Uriel should report the gap and stop short of a stronger
verdict.

## Minimal operator checklist

Before accepting a method result into a project:

1. Can a reader state exactly what was observed and what was censored?
2. Are priors, assumptions, and evidence in separate records?
3. Does the sensitivity table include cases that could weaken the result?
4. Can every important value be found in the exact hashed source artifact?
5. Can the workload be rerun from the recorded source generation?
6. Are established, refuted, unknown, and still-useful conclusions separated?
7. Does the next action have a concrete completion condition?

If any answer is no, the honest output is a repair path or an unknown—not a
stronger-sounding conclusion.
