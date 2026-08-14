# Research Verbatim Ledger

The Research Verbatim Ledger is an opt-in local record of project-defining
user wording. It helps a researcher compare later manuscripts, claims,
roadmaps, or summaries with an exact earlier baseline. It is not a transcript
recorder, evidence that a claim is true, or permission for Uriel to rewrite
research output.

## Consent is off by default

Every user and every initialized Uriel project starts in OFF. Merely writing a
detailed, novel, long-lived, or accuracy-sensitive prompt never captures it.
An integration may make one discreet offer:

> This sounds like an original project baseline where your exact wording may
> matter later. Keep this statement verbatim for this project? Nothing is
> saved unless you opt in.

The offer creates no entry and records no message content. Uriel stores only a
non-content offer preference so it can avoid repeating the offer. A decline,
prior offer, or disabled state suppresses later offers for that user and
project. Removing the complete ledger also removes that preference and returns
the scope to a fresh OFF state.

Inspect or change consent at any time:

~~~text
uriel verbatim status --root ../my-study --user researcher-1
uriel verbatim consent --root ../my-study --user researcher-1 --mode manual --confirm
uriel verbatim disable --root ../my-study --user researcher-1
~~~

The --user value is used only to derive a stable SHA-256 isolation key. The
raw user reference is not stored in the ledger.

## Three modes

- manual saves one user-selected message after entry confirmation.
- assisted may propose a likely baseline, prediction, mechanism, correction,
  or major refinement in memory; every proposed entry still needs confirmation.
- project is an explicit per-project opt-in for ongoing qualifying research
  statements. A project capture must still be marked as a qualifying baseline,
  prediction, mechanism, correction, or major refinement.

An opt-in never crosses to another user or project. Manual capture remains
available from any active mode because it is an explicit selected-message
action.

## Capture exact wording

For a direct selected message:

~~~text
uriel verbatim capture --root ../my-study --user researcher-1 \
  --text "My prediction is that the effect remains below five percent." \
  --source-ref message-42 --mode manual --confirm-entry --project-research
~~~

For multiline or punctuation-sensitive text, put the exact UTF-8 bytes in a
project-local file and use --text-file. Uriel decodes those bytes without
line-ending, Unicode, or whitespace normalization.

Each accepted entry contains:

- stable entry ID;
- user and project isolation keys;
- visible user-message reference and capture timestamp;
- exact text and its SHA-256;
- declared EXACT_UTF8_V1 normalization rules;
- capture mode and optional label;
- optional REFINES, CORRECTS, or SUPERSEDES links;
- an optional separately labeled advisory summary; and
- a whole-entry integrity hash.

Exact text and summaries are different fields with different hashes. Uriel
refuses a summary that simply substitutes for exact text. It also refuses
hidden/system/provider content, unrelated conversation, and text that matches
conservative credential patterns.

## Review, search, drift, export, and removal

~~~text
uriel verbatim review --root ../my-study --user researcher-1
uriel verbatim search --root ../my-study --user researcher-1 "five percent"
uriel verbatim drift --root ../my-study --user researcher-1 \
  --entry rvl-ENTRY_ID --later-text-file artifacts/manuscript-claim.txt
uriel verbatim export --root ../my-study --user researcher-1 \
  --destination exports/verbatim-ledger.json
uriel verbatim remove-entry --root ../my-study --user researcher-1 \
  rvl-ENTRY_ID --confirm
uriel verbatim remove-ledger --root ../my-study --user researcher-1 --confirm
~~~

Drift review reports PRESERVED_MEANING, OMISSION, CONTRADICTION, OVERSTATEMENT,
and UNRESOLVED_AMBIGUITY through conservative lexical signals. Only an exact
normalized comparison receives preserved-meaning status; changed wording
retains unresolved ambiguity. The review returns hashes and linked entry IDs,
persists nothing, edits neither text, and never treats the user's wording as
scientific proof.

An export contains exact wording and may be sensitive. Uriel writes it only to
a fresh explicit project-relative path outside private .uriel state. Review
classification and destination before sharing. Selected-entry removal changes
only that isolated ledger. Whole-ledger removal uses closed, non-recursive file
membership and refuses unknown files instead of deleting them.

## Storage and privacy boundary

State is created lazily under:

~~~text
.uriel/research-verbatim/
  user-<sha256>/
    project-<sha256>/
      consent.json
      ledger.json
~~~

Consent, each entry, and the aggregate ledger are hash-verified before reads or
content-preserving mutations. Disable does not need to read exact entries, and
whole-ledger removal validates path and closed membership rather than requiring
damaged content to verify. The store is local, ignored by Git with the rest of
.uriel, and uses
Uriel's existing root-confinement and atomic-write primitives. It adds no cloud
store, telemetry, provider call, global cross-user index, or background
capture. The ordinary project provenance ledger is deliberately not used for
verbatim metadata, so another user scope cannot discover entry IDs through it.
Entries remain local until explicit selected-entry or whole-ledger removal;
there is no automatic expiry, cloud copy, or background retention service.

## Programmatic route

~~~python
from uriel import ResearchVerbatimLedger

ledger = ResearchVerbatimLedger("../my-study", "researcher-1")
ledger.set_mode("MANUAL", explicit_opt_in=True)
saved = ledger.capture(
    "My baseline prediction is bounded.",
    source_message_ref="message-42",
    capture_mode="MANUAL",
    confirmed=True,
    project_research_statement=True,
)
ledger.verify()
~~~

The Python facade and CLI call the same implementation. This feature is local
software integrity support; users remain responsible for retention, backup,
device access, lawful processing, domain interpretation, and whether an export
may leave the project boundary.
