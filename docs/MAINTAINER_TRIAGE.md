# Maintainer triage

## First pass

1. Check privacy and security.
2. Confirm version/commit.
3. Confirm reproduction.
4. Classify ground truth.
5. Assign type, area, status, and severity.
6. Link duplicate reports.
7. Decide: confirmed, needs information, unresolved candidate, out of scope.
8. Create a regression fixture when confirmed.

## Scientific-audit severity

Base severity on effect on:

```text
Data Readiness
claim status or scope
Gate decision
Blessing eligibility
publication/submission packet
source integrity
privacy or security
```

Not on rhetorical impact.

## Fix closure

A fixed issue records:

```text
commit
test
release
migration or staleness impact
public correction where necessary
```
