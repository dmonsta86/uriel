# The Forge Method

## Purpose

The Forge Method proves whether a substantial, named body of work is actually
ready.

It is intended for:

- feature branches;
- releases;
- data generations;
- manuscripts;
- submissions and revisions;
- evidence-source integrations;
- security hardening;
- other milestones where “done” must be auditable.

## The method

### 1. Define the mission

State:

```text
What must be delivered
What is out of scope
What success means
Which exact version is being evaluated
```

### 2. Define requirements and gates

Separate:

```text
Hard gates — required for the result
Soft gates — useful but legitimately deferrable
```

### 3. Record blockers

Every blocker includes:

```text
Evidence
Affected requirement
Owner
Repair
Safe fallback
Completion condition
```

### 4. Create work packages

Break the milestone into small units with:

```text
Allowed files
Expected output
Exact verification
Pass and failure conditions
```

### 5. Attach evidence

Every closure claim points to a receipt, artifact, log, manifest, or checksum.

### 6. Verify

Run the complete planned test set against the exact bound version.

### 7. Attempt to refute the result

An independent pass tries to disprove each positive closure claim.

Uncertainty is not converted into PASS.

### 8. Close or continue

Valid outcomes include:

```text
COMPLETE
COMPLETE_WITH_DEFERRED_SOFT_GATES
BLOCKED_WITH_PATH
FAILED
STALE
ABORTED
```

A changed bound version makes the result stale.

## Standard bundle

```text
MISSION.md
REQUIREMENT_BASELINES.json
GATE_REGISTER.csv
BLOCKER_REGISTER.csv
WORK_PACKAGES.csv
TEST_PLAN.md
DECISION.md
AUDIT_RESULTS.md
CLOSURE_LEDGER.csv
forge.json
RESULT.json
evidence/
SHA256SUMS.txt
```

## Relationship to the Blessing

Forge proves milestone closure.

The Blessing proves the exact research artifact passed Uriel's strict research
integrity gates.

A Forge bundle may support a Blessing, but cannot grant one.
