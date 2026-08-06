# Model guide: spend intelligence where it changes the result

Uriel is model-optional. The preferred workflow is **deterministic first, semantic help second, direct verification last**.

| Task | Lowest-cost useful route | Stronger route | Never delegate |
|---|---|---|---|
| Clarify a rough question | Uriel intake templates; small free model | GPT-5.6 Sol Medium/High | Deciding that the author is unserious |
| Generate literature queries | Free OpenCode model or web chat | Sol High/Extra High; API/Codex `max` | Claiming novelty from generated queries alone |
| Extract a specific datum | Manual source reading | Strong model with the source attached | Exact locator and artifact verification |
| Find contradictions/control mismatches | Several narrow free-model passes | Sol Pro, `ultra`, Extra High, or API/Codex `max` | Final adjudication without the underlying data |
| Final submission challenge | Human checklist + deterministic audit | Sol Pro, `ultra`, Extra High, or API/Codex `max` | Ethics approval, truth, authorship responsibility |

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
