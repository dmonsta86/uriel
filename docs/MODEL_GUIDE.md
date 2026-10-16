# Model guide: spend intelligence where it changes the result

Uriel is model-optional. The preferred workflow is **deterministic first, semantic help second, direct verification last**.

| Task | Lowest-cost useful route | Stronger route | Never delegate |
|---|---|---|---|
| Clarify a rough question | Uriel intake templates; small free model | Strong authorized model on one bounded prompt | Deciding that the author is unserious |
| Generate literature queries | Free compatible external agent model or web chat | Strong authorized model plus current primary-source search | Claiming novelty from generated queries alone |
| Extract a specific datum | Manual source reading | Strong model with the source attached | Exact locator and artifact verification |
| Find contradictions/control mismatches | Several narrow free-model passes | Strong authorized model on a compact adversarial packet | Final adjudication without the underlying data |
| Final submission challenge | Human checklist + deterministic audit | Strong authorized model followed by an independent domain reviewer | Ethics approval, truth, authorship responsibility |

## Drive any model with `uriel next`

`uriel next --root . --prompt NEXT_STEP.md` writes one self-contained task with
its reason, location, completion condition, and the protocol rules. A small or
free model handles one task per session, and you rerun `uriel next` between
sessions. A stronger model may read `uriel --json next` and finish several
agent-owned items in the current stage, rechecking after each. No model performs
an item marked `owner: human`. See [RESEARCH_PROTOCOL.md](RESEARCH_PROTOCOL.md).

When a model drafts manuscript text, run `uriel paper lint --file DRAFT.md`
before pasting it into a section. It reports assistant residue, placeholders,
filler, unsourced attribution, and inconsistent statistics with exact lines.

## Recommended escalation ladder

1. `uriel audit --profile exploratory`
2. Human fixes for schema, scope, paths, digests, and receipts
3. Free model on one bounded task
4. `uriel review-import` after manual verification
5. `uriel audit --profile strict`
6. Strong model for unresolved semantic/adversarial issues
7. Independent domain reviewer
8. `uriel audit --profile submission`

Model disagreement should become a documented contradiction or reviewer objection, not a vote. Preserve the evidence and explain the reconciliation.
