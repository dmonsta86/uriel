# Contributing to Uriel

Uriel welcomes researchers, students, librarians, reproducibility engineers, journal staff, software maintainers, statisticians, philosophers of science, and people asking their first serious question.

## First principles

A contribution must not make a PASS easier merely to reduce friction. New checks should be:

1. deterministic or explicitly marked untrusted;
2. explainable in plain language;
3. supported by tests with both pass and fail fixtures;
4. scoped so the output does not claim more than the check establishes;
5. constructive, with exactly three repair paths for a blocker;
6. insensitive to credentials, prestige, confidence, age, and writing polish;
7. conservative about privacy and provider export.

## Local setup

```bash
python -m venv .venv
# Linux/macOS
. .venv/bin/activate
# Windows PowerShell
# .venv\Scripts\Activate.ps1

python -m pip install -e .
python -m unittest discover -s tests -v
python scripts/build_portable.py
python dist/uriel.pyz --version
```

No third-party runtime package may be added without a compelling reason, a threat analysis, and a dependency-free fallback. Development helpers may be proposed separately, but the committed test suite must run with `unittest` from the standard library.

## Pull requests

Keep changes focused. Include:

- the failure mode being addressed;
- an example that currently escapes detection or is falsely blocked;
- tests proving the new behavior;
- documentation for any schema or policy change;
- migration notes when a manifest field changes;
- an explicit statement of what the check still cannot establish.

Policy changes require a `POLICY_VERSION` update when they can change whether the same project passes.

## Adding a finding

A blocker should include:

- stable code;
- Gate number;
- neutral subject;
- exact reason;
- evidence pointers;
- exactly three non-duplicative repair options;
- tests for detection, non-detection, reminder persistence, and resolution.

Do not encode ideological conclusions or domain disputes as universal deterministic rules. Where a field lacks consensus, make the check configurable, record the choice, or restrict it to missing disclosure rather than choosing a side silently.
