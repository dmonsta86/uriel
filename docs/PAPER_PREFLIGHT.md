# Manuscript preflight

`uriel paper preflight --root PROJECT --manuscript artifacts/manuscript.md`

This experimental, read-only command finds defined manuscript production issues before spending reviewer time. It needs an initialized Uriel project, one explicitly selected project-local UTF-8 manuscript, and no network, account or model. The output binds the exact manuscript and project bytes.

Checks include leaked tool citations and chat/process text, explicit unfinished placeholders, repeated prose, strong certainty phrases needing support, and selected explicit citation, label, figure and table inconsistencies. Findings identify the triggering line and excerpt. A technical word, passive voice, long sentence or use of AI is not itself a defect. Legitimate quotations or methods examples can trigger a lead and must be judged in context.

## Contract

- Input limit: 4 MiB of UTF-8 and 100,000 lines. At most 200 findings are displayed, with suppressed findings counted explicitly.
- `analyze_text(text)` is the pure Python entry point for already extracted text. The CLI's `preflight_paper` adds project confinement and content bindings.
- No manuscript or review state is written, no source is retrieved, no model is called, and no existing gate or publication authority is granted.
- A clean result means **no defined mechanical leads were found**, not that the prose is human-authored, factual, complete or ready for publication.
- Citation-key/number consistency is not citation identity, quotation accuracy or source support. Author-year conventions and discipline-specific styles still require explicit reference reconciliation.
- Word/PDF rendering, source-to-export concordance, whole-paper substantive review, and human approval are separate tasks. The text checker does not certify their completion.

## Natural scholarly writing review

Review prose for clear subjects, concrete verbs, necessary technical precision and an intelligible argument. Cut empty significance claims, stock transitions, repeated conclusions and drafting commentary. Preserve meaningful uncertainty, limitations, counterevidence, unusual but precise author wording, numerical values and attribution. Do not replace specific reasoning with generic polished prose or add invented personal experience to make writing sound human.

An authorship classifier, a detector score or agreement among several models cannot establish human origin or scientific truth. Improvements should be inspected as edits against the exact source. Ordinary applicable assistance disclosures remain truthful; stylistic refinement is not a tool for hiding the research process.

## Verification

`tests/test_paper_preflight.py` exercises clean technical prose, deliberate contamination, cross-reference defects, large manuscripts, finding limits and path/format failures. This is bounded software evidence, not measured detection performance across all disciplines.
