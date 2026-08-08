# Expected high-level result

## Data Readiness

```text
FAIL / BLOCKED
```

until:

```text
duplicate P014 week 4 is resolved
P201 identity is reconciled to P021
P008 unit is corrected from minutes to seconds
P025 missing accuracy is recorded
join is performed by participant_id
exclusion policy is restored to the plan
```

## Clean descriptive results

```json
{
  "plant": {
    "accuracy_n": 15,
    "week4_accuracy_mean": 75.9333,
    "accuracy_change_mean": 2.9333,
    "week4_task_time_mean_seconds": 287.4,
    "task_time_improvement_mean_seconds": 8.0,
    "week4_stress_mean": 4.4133
  },
  "control": {
    "accuracy_n": 14,
    "week4_accuracy_mean": 73.7143,
    "accuracy_change_mean": 3.0,
    "week4_task_time_mean_seconds": 272.4,
    "task_time_improvement_mean_seconds": 18.0,
    "week4_stress_mean": 4.2467
  },
  "plant_novice": {
    "n": 4,
    "accuracy_change_mean": 0.0,
    "task_time_improvement_mean_seconds": 8.0
  },
  "control_novice": {
    "n": 4,
    "accuracy_change_mean": 3.0,
    "task_time_improvement_mean_seconds": 18.0
  }
}
```

The raw week-4 accuracy mean is only modestly higher in the plant room, while
mean change from baseline is approximately equal. The preregistered primary
outcome—task-time improvement—favors the control room in this synthetic data.

## Strongest defensible conclusion

The supplied benchmark does not establish that a desk plant improves reasoning.

At most, it contains an unverified raw difference between two confounded rooms
that disappears when change from baseline is considered, alongside a primary
timing outcome that points in the opposite direction.

## Useful next study

A randomized, counterbalanced, blinded-scoring study should vary plants within
the same rooms or balance room conditions, preserve the preregistered primary
outcome, use participant-ID joins, and define exclusions before data inspection.

## Useful paper pivot

The current artifacts could support a methods or data-quality case study about
how room confounding, outcome switching, and record-preparation defects can
create an apparently persuasive result.
