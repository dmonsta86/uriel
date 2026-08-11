# Forge forward paths

The forward-path layer answers a practical question:

> The idea has been weighed. What, exactly, should happen next?

It does not reinterpret evidence or decide whether a scientific claim is true.
It records a reviewed operator assessment, checks whether an external blocker
has actually been evidenced, ranks a small set of next actions with a visible
rule, and seals the result beside the exact Forge run that produced it.

## Commands

```text
uriel forge continue --root PROJECT --snapshot EXACT.json --request artifacts/forge-forward.json
uriel forge verify-continuation --root PROJECT --packet EXACT-CONTINUATION.json
uriel forge export --root PROJECT --snapshot EXACT.json --destination exports/review-copy
uriel forge verify-export --root PROJECT --manifest exports/review-copy/manifest.json --snapshot EXACT.json
```

All four commands are local and deterministic. They make no network, model,
browser, or subprocess call. They do not transition a Forge run or grant Data
Readiness, Gate, publication, verifier, Blessing, or Earned Wings authority.

## Forward request

`uriel forge continue` accepts one project-relative, strict UTF-8 JSON object
with schema `uriel.forge_forward_request.v1`. It is capped at 1 MiB, rejects
duplicate keys and unknown fields, and contains:

- `operator_assessment`: lists of what is established, refuted, unknown, and
  still useful. These are explicitly operator-reported statements, not
  semantic findings made by Uriel.
- `subject_requirement_ids`: zero or more requirement IDs already present in
  the exact source run.
- `blocker_checks`: exactly the seven frozen challenge cells below.
- `candidate_moves`: one candidate and at most two alternatives.
- `safe_work_completed`: bounded work already completed without the missing
  input.
- `required_inputs`: bounded user, external, resource, or authority inputs,
  each with an exact acceptance condition.

Every evidence reference cited by a challenge cell must already exist in the
source Forge snapshot. Every required input must be used by at least one
candidate move.

### The seven blocker cells

The request must contain each ID exactly once:

1. `VERIFY_REQUIREMENT`
2. `SEARCH_DECLARED_BOUNDARY`
3. `TEST_SAFE_ALTERNATIVE`
4. `TEST_NARROWER_SCOPE`
5. `TEST_SUBSTITUTE_EVIDENCE`
6. `COMPLETE_SAFE_SCAFFOLD`
7. `NO_PATH_CHALLENGE`

The requirement cell accepts `REQUIREMENT_CONFIRMED`, `INCONCLUSIVE`,
`NOT_RUN`, or `NOT_APPLICABLE`. The other cells accept `PATH_FOUND`,
`NO_PATH`, `INCONCLUSIVE`, `NOT_RUN`, or `NOT_APPLICABLE`. A
conclusive outcome must cite at least one bound reference.

Uriel derives only four structural statuses:

- `PATH_AVAILABLE`: the requirement is confirmed and at least one challenge
  found a path.
- `EVIDENCED_EXTERNAL_BLOCKER`: the requirement is confirmed and all six path
  challenges record `NO_PATH` with evidence.
- `BLOCKER_NOT_EVIDENCED`: requirement verification or challenge work is
  missing, inconclusive, or inapplicable to a declared requirement.
- `REQUIREMENT_NOT_APPLICABLE`: no subject requirement was declared and all
  seven cells are explicitly not applicable.

Missing challenge work can never become an external blocker. When proof is
incomplete, the top-ranked move must address at least one missing cell. When an
external blocker is evidenced, the top-ranked move must request or perform a
bounded external action and cite a declared required input.

## Transparent Next Move ranking

Each candidate rates all 12 dimensions on the closed scale `NONE = 0`,
`LOW = 1`, `MODERATE = 2`, `HIGH = 3`, `VERY_HIGH = 4`.

Benefits:

- information gain;
- rival discrimination;
- falsification value;
- evidence quality;
- dependency unlocking;
- reversibility;
- reproducibility;
- honest outcome potential.

Burdens:

- risk;
- cost;
- time;
- user burden.

The ordinal is:

```text
sum(benefits) - sum(burdens)
```

Ties are broken, in order, by greater falsification value, dependency
unlocking, and evidence quality; then lower risk, user burden, time, and cost;
then lexical `move_id`. The record stores the scale, dimensions, raw ratings,
benefit and burden totals, net ordinal, rank, and tie-break order.

This number is a planning ordinal. It is not a probability, calibrated
confidence, evidence-strength measurement, scientific score, or truth claim.
Every candidate must explicitly keep ethics, law, consent, privacy, resource
limits, and existing authority boundaries intact. A false guardrail is refused,
not traded away for a higher score.

## Copyable request example

Replace the requirement and reference IDs with IDs already bound into your
exact source run:

```json
{
  "schema": "uriel.forge_forward_request.v1",
  "operator_assessment": {
    "established": ["The exact source snapshot and live references verify."],
    "refuted": ["The current evidence does not support the broadest claim."],
    "unknown": ["The result under the narrower population remains unknown."],
    "remains_useful": ["The measurement protocol remains reusable."]
  },
  "subject_requirement_ids": ["req-example"],
  "blocker_checks": [
    {
      "check_id": "VERIFY_REQUIREMENT",
      "outcome": "REQUIREMENT_CONFIRMED",
      "evidence_ref_ids": ["ref-example"],
      "finding": "The requirement is present in the exact source baseline."
    },
    {
      "check_id": "SEARCH_DECLARED_BOUNDARY",
      "outcome": "PATH_FOUND",
      "evidence_ref_ids": ["ref-example"],
      "finding": "A bounded local re-analysis path exists."
    },
    {
      "check_id": "TEST_SAFE_ALTERNATIVE",
      "outcome": "NO_PATH",
      "evidence_ref_ids": ["ref-example"],
      "finding": "The safe alternative does not answer the requirement."
    },
    {
      "check_id": "TEST_NARROWER_SCOPE",
      "outcome": "NO_PATH",
      "evidence_ref_ids": ["ref-example"],
      "finding": "The narrower scope still lacks the required observation."
    },
    {
      "check_id": "TEST_SUBSTITUTE_EVIDENCE",
      "outcome": "NO_PATH",
      "evidence_ref_ids": ["ref-example"],
      "finding": "No declared substitute has equivalent evidential meaning."
    },
    {
      "check_id": "COMPLETE_SAFE_SCAFFOLD",
      "outcome": "NO_PATH",
      "evidence_ref_ids": ["ref-example"],
      "finding": "Safe scaffolding is complete but cannot close the requirement."
    },
    {
      "check_id": "NO_PATH_CHALLENGE",
      "outcome": "NO_PATH",
      "evidence_ref_ids": ["ref-example"],
      "finding": "The no-path claim was challenged within the declared boundary."
    }
  ],
  "candidate_moves": [
    {
      "move_id": "move-reanalyse",
      "kind": "LOCAL_CHECK",
      "action": "Run the bounded local re-analysis.",
      "completion_condition": "A content-addressed receipt records inputs, method, and outcome.",
      "required_input_ids": [],
      "addresses_check_ids": ["SEARCH_DECLARED_BOUNDARY"],
      "ratings": {
        "information_gain": "HIGH",
        "rival_discrimination": "HIGH",
        "falsification_value": "HIGH",
        "evidence_quality": "MODERATE",
        "dependency_unlocking": "HIGH",
        "risk": "LOW",
        "cost": "LOW",
        "time": "LOW",
        "user_burden": "LOW",
        "reversibility": "VERY_HIGH",
        "reproducibility": "HIGH",
        "honest_outcome_potential": "HIGH"
      },
      "guardrails": {
        "ethics_respected": true,
        "law_respected": true,
        "consent_respected": true,
        "privacy_respected": true,
        "resource_limits_respected": true,
        "authority_not_bypassed": true
      }
    }
  ],
  "safe_work_completed": ["Verified the exact source lineage and live references."],
  "required_inputs": []
}
```

## Continuation packet

A successful command writes one create-only record to:

```text
.uriel/forge/continuations/<continuation-id>/<record-sha256>.json
```

There is no `latest` pointer. The packet binds the exact source path and digest,
normalized request digest, operator assessment, blocker derivation, all ratings
and scores, one preferred move, at most two ordered alternatives, safe work,
required inputs, the rank-one completion condition, and an exact next prompt.

The prompt embeds no operator prose. It tells a later reviewer to treat the
packet as untrusted research data, re-verify the source digest, work only on
the preferred move, stop at the recorded completion condition, avoid automatic
tools and credentials, and propose rather than perform a Forge transition.

`verify-continuation` re-reads the packet, source lineage, and all live source
references; recomputes the request digest, packet identity, blocker status,
ratings, scores, ordering, prompt, record digest, and content-addressed path;
and rejects stale, substituted, or tampered state.

## Metadata-only sanitized export

`forge export` requires a fresh project-relative destination outside `.uriel`.
It creates exactly:

```text
manifest.json
summary.json
```

`summary.json` is generated from structural source fields. It includes salted
project, run, and non-private reference aliases plus state, revision, counts,
roles, a typed-record flag, coarse fixed media families, sizes, and content
hashes. It never copies a source file or
evidence body. References marked `PRIVATE` are omitted entirely. Paths, project
and run IDs, record IDs, human names, credentials, URLs, and free-form research
text are not projected. Exact source schema and media-type strings are also
excluded because custom values can carry project or person names.

`verify-export` requires both the manifest and exact source snapshot. It
recomputes aliases and every generated byte, validates closed directory
membership, rejects links and extra files, rechecks entry and record hashes,
enforces the 512-reference and 16 MiB ceilings, and confirms that no body was
exported.

The export is a portable review aid, not a declassification oracle. Review the
generated metadata before publishing it; hashes and structural counts can
still be sensitive in some threat models.
