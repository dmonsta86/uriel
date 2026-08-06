# `uriel.project.json` reference

The project manifest is an editable accountability record. Runtime validation is dependency-free; JSON Schemas are also shipped for editors.

## Core identity

- `title`, `kind`, `question`: what is being studied or claimed.
- `hypothesis.statement`: the bounded proposition.
- `hypothesis.falsifier`: an observation that would count against it.
- `operational_definitions`: exact meanings and measurement rules.
- `success_criteria`: predeclared pass conditions.

## Framing and novelty

- `framing_review.neutral_restatement`: lower-temperature wording.
- `competing_frames`: good-faith alternative formulations.
- `loaded_terms_reviewed`: words checked for embedded judgment.
- `scope_boundaries`: where the claim stops.
- `novelty_review`: dated databases, queries, nearest prior work, differences, negative searches, and search limits.

A novelty search record supports a bounded statement such as “not found in the declared searches as of DATE.” It never supports “no one has ever done this” without impossible universal coverage.

## Claims

Each claim has a stable ID and contains:

- statement and claim type;
- importance (`major` claims receive stricter evidence checks);
- population/setting/timeframe scope;
- falsifier and reasoning;
- evidence, counterevidence, assumption, and adversarial-test IDs;
- reconciliation of contrary material.

## Evidence

Every evidence record should contain:

- a project-local regular-file path;
- the exact SHA-256 digest computed by `uriel add-evidence`;
- source type and whether it is primary;
- a stable source locator and within-source data location;
- direct extraction (datum, value, short excerpt, or executable observation);
- independent interpretation, kept separate from the source author’s conclusion;
- evidence-specific limitations;
- supported and counterevidenced claim IDs.

Restricted data can be represented by a content-hashed access receipt and exact access description, but the audit must not claim independent raw-data verification when the bytes are unavailable.

## Methods and adversarial record

Declare design, population, sampling, sample size, analysis plan, effect-size metric, uncertainty, causal identification, controls, exclusions, missing-data plan, preregistration, and reproduction command.

Then record assumptions, alternatives, contradictions, adversarial tests, reviewer objections, limitations, ethics, funding/conflicts, known counterevidence, omitted data, and negative results.

## Submission

Venue suggestions are not endorsements. Verify current official scope, article type, fees/waivers, reporting checklist, ethics, data/code policy, license, portal, and deadline immediately before submission.
