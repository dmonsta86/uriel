# Strict Blessing — Low-Context Implementation Contract

This file is the mandatory acceptance test for any low-context worker
implementing or extending the Strict Blessing surface
(STRICT_BLESSING_CONTRACT.md section 17 requirement 33).

A low-context worker MAY claim the task complete ONLY after:

1. The full mandatory regression suite passes on a clean checkout:
   `python -m unittest discover -s tests -p "test_*.py"`
2. The Strict Blessing mandatory suite passes in isolation:
   `python -m unittest tests.test_strict_contract_mandatory`
3. The pre-existing strict-blessing suite passes in isolation:
   `python -m unittest tests.test_strict_blessing`
4. No production CLI flag bypasses a gate: `uriel audit --force` and
   `uriel blessing issue --skip-gates` must both exit non-zero.
5. The worker names the exact acceptance test it ran in its completion
   summary. A completion summary without the exact test command and its
   pass output is not a completion.

Failure modes that are NEVER acceptable as "done":

- "The code is written" without the exact test output.
- A passing parser or import check instead of the real suite.
- Editing the acceptance test to match the implementation instead of
  proving the implementation satisfies the contract.
- Marking a task complete while any item of `tests/test_strict_contract_mandatory.py`
  (section 17.1-17.35) is skipped or failing.

The acceptance gate for any Strict Blessing change is:
`python -m unittest tests.test_strict_contract_mandatory tests.test_strict_blessing`
