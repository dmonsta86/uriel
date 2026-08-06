# Instructions for coding agents and human contributors

1. Read `README.md`, `docs/ARCHITECTURE.md`, `docs/THREAT_MODEL.md`, and `docs/LIMITATIONS.md` before changing trust-core code.
2. The Python runtime dependency count must remain zero unless a major version and documented architecture decision explicitly change it.
3. Never weaken path confinement, exact source membership, receipt binding, Gate order, or Blessing requirements to make a test pass.
4. A model review is untrusted input. Do not let review existence imply evidence, novelty, or Gate success.
5. Preserve friendly, non-condescending refusal language and exactly three repair options for blockers.
6. Add a regression test for every bug or integrity-policy change.
7. Keep Python 3.9 compatibility; do not introduce PEP 604 unions or newer-only standard-library APIs without a version change.
8. Do not add telemetry, network calls, provider SDKs, auto-sharing, or background uploads to the core.
9. Do not invent benchmark, adoption, venue, grant, or model claims.
10. Run `python scripts/release_check.py --full` before proposing release-ready status.
