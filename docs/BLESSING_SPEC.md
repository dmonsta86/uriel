# `URIEL-BLESSING-v1` specification

## Purpose

A Blessing is a portable, content-addressed statement that one declared project state passed Uriel's `submission` profile under one named policy version.

## Preconditions

Issuance fails unless:

- dependency-free schema validation reports no errors;
- all Three Gates pass under the submission profile;
- the source manifest verifies;
- every included execution receipt verifies;
- at least one required executable workload has a fresh PASS receipt when applicable;
- no blocker reminder remains open;
- the audit hashes match the exact project and source state;
- no mandatory Gate waiver is present.

## Package contents

A package contains at minimum:

- `blessing.json` — signed-by-content payload and envelope hashes;
- `package-manifest.json` — SHA-256 for every immutable package file except the manifest and envelope as specified by the verifier;
- `project.json`;
- `source-manifest.json`;
- `audit.json`;
- `ledger-pre-issuance.jsonl`;
- verified receipt files;
- `certificate.svg` and `certificate.txt`;
- `qr.svg`;
- `verify.py` and `VERIFY.md`;
- submission-support drafts.

## Identifier

`blessing_id` is the SHA-256 of canonical JSON containing the core payload fields. Canonical JSON is UTF-8, sorted by key, compact, and newline-terminated.

The QR stores a compact payload beginning with:

```text
URIEL-BLESSING-v1:
```

The QR does not contact a server. It allows a verifier to compare the displayed payload with `blessing.json` or a future registry chosen by the project owner.

## Verification levels

- **Package verification:** every content hash and payload relationship checks inside the copied package.
- **Live-project verification:** package project/source hashes match the current project and an issuance event exists in the current hash-chained ledger.
- **Historical package:** package verifies but the live project has changed. This is not a failure; it must be described as a Blessing of the packaged historical state.

## Non-claims

The payload records that the Blessing is not identity proof, universal novelty proof, peer review, ethics approval, or a guarantee of truth. Omissions outside the declared source set cannot be detected from hashes alone.
