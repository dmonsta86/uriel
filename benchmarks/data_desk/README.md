# Data Desk synthetic-size receipt

`synthetic-tabular-10000-v1.json` is one measured local observation of Uriel's
bounded plan → import → inspect → independent-generation-verify path over a
deterministically generated 10,000-row, four-column CSV.

It is not a throughput, maximum-capacity, latency-SLA, hardware-equivalence, or
real-dataset claim. Timings are expected to vary. The release gate verifies the
fixture identity, implementation binding, result, claim boundary, and presence
of positive measurements; it does not enforce a speed threshold.

Regenerate intentionally from the repository root:

```text
python scripts/benchmark_data_desk.py --report benchmarks/data_desk/synthetic-tabular-10000-v1.json --replace
python scripts/check_data_desk_benchmark.py
```
