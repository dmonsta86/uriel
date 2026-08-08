#!/usr/bin/env python3
"""Recompute the synthetic trial's clean descriptive summary."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "INPUT"

with (INPUT / "PARTICIPANTS.csv").open(encoding="utf-8", newline="") as f:
    participants = {row["participant_id"]: row for row in csv.DictReader(f)}

rows = []
with (INPUT / "OUTCOMES.csv").open(encoding="utf-8", newline="") as f:
    for row in csv.DictReader(f):
        if row["notes"] == "duplicate export row from manual correction sheet":
            continue
        pid = "P021" if row["participant_id"] == "P201" else row["participant_id"]
        task = float(row["task_time_seconds"])
        if pid == "P008" and row["week"] == "3":
            task = 144.0
        rows.append({
            "participant_id": pid,
            "week": int(row["week"]),
            "accuracy": None if row["accuracy_percent"] == "" else float(row["accuracy_percent"]),
            "task_time": task,
            "stress": float(row["stress_score_1_to_7"]),
        })

week4 = [row for row in rows if row["week"] == 4]

def avg(values):
    values = [value for value in values if value is not None]
    return mean(values)

result = {}
for condition in ("plant", "control"):
    group = [
        row for row in week4
        if participants[row["participant_id"]]["condition"] == condition
    ]
    result[condition] = {
        "accuracy_n": sum(row["accuracy"] is not None for row in group),
        "week4_accuracy_mean": avg([row["accuracy"] for row in group]),
        "accuracy_change_mean": avg([
            None if row["accuracy"] is None else
            row["accuracy"] - float(participants[row["participant_id"]]["baseline_accuracy_percent"])
            for row in group
        ]),
        "week4_task_time_mean_seconds": avg([row["task_time"] for row in group]),
        "task_time_improvement_mean_seconds": avg([
            float(participants[row["participant_id"]]["baseline_task_time_seconds"]) - row["task_time"]
            for row in group
        ]),
        "week4_stress_mean": avg([row["stress"] for row in group]),
    }

print(json.dumps(result, indent=2, sort_keys=True))
