# Known limitations and honest claim ceiling

Uriel can make a research record harder to overstate and easier to verify. It cannot mechanize scientific truth.

## What a pass means

A Gate pass means the declared project state satisfied the implemented policy checks for that profile and policy version. A Blessing means a fresh submission-profile audit passed and the packaged bytes verify against the recorded digests.

## What a pass does not mean

- the hypothesis is true;
- the work is globally novel;
- the literature search is complete;
- the statistical model is appropriate for every context;
- the underlying instrument or dataset is unbiased;
- no relevant data was withheld outside the project;
- a quotation or interpretation is correct unless a reviewer checks it;
- research ethics, law, privacy, or licensing requirements are satisfied;
- the work survived independent peer review;
- a journal or conference should accept it;
- an author or reviewer identity was cryptographically verified.

## Detector limitations

The fallacy/framing detector uses conservative text patterns plus declared structure. It can miss sophisticated defects and can flag innocent wording. Findings therefore explain the triggering text and offer repair paths rather than asserting bad faith.

The novelty gate verifies that a search record exists and is bounded; it cannot prove universal absence of prior work. A domain expert and current primary-source search remain necessary.

The evidence gate can verify bytes and mappings, but cannot know whether an undeclared artifact exists. Mandatory attestations create accountability; they do not create omniscience.

## Certificate design

Version 1 uses SHA-256 content addressing, not public-key author signatures. The standalone verifier checks internal package integrity. Live verification additionally checks the local source state and ledger. Public trust should combine Uriel with signed Git tags/releases and an independent archive.

## Maturity

This is an initial release candidate with a bounded passing fixture and cross-platform CI configuration. It needs public false-positive/false-negative datasets, discipline-specific validation, usability studies, and independent security review before anyone should mandate it for publication.
