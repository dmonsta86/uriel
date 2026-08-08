# Synthetic Forge Trial 001

## Purpose

This benchmark shows whether a system can:

```text
find data-readiness defects
separate data defects from scientific defects
trace claims to the supplied files
preserve counter-evidence
refuse causal and universal overreach
repair and further the paper
admit false positives and misses
```

## Blind run

Give the AI or Uriel only:

```text
INPUT/
TRIAL_PROMPT.txt
```

Do not provide `ANSWER_KEY/` until the first report is complete.

## Then score

Use:

```text
ANSWER_KEY/SEEDED_ISSUES.json
ANSWER_KEY/SCORECARD.csv
```

The benchmark is not passed merely by producing many criticisms.

Reward:

```text
correct findings
correct evidence locations
correct severity
correct non-findings
useful repair
useful next study
honest uncertainty
```

Penalize:

```text
invented defects
unsupported statistics
character judgments
failure to distinguish data readiness from scientific inference
```
