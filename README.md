# Uriel

A research record and checklist tool: keep what you tested, what it showed, and what remains, so nobody doubles back.

Uriel records research questions, evidence, predictions, negative-result audits and decisions in an editable note tree. Use a self-hosted Trilium Notes instance or an offline Markdown folder. It does not decide whether science is correct, run an AI service, or publish your research.

- Distribution package: `uriel-research`
- Python import and CLI command: `uriel`
- Python 3.9+, MIT, no runtime dependencies. The research-record workflow is beta; Trilium integration is experimental.

## 1. Install

```sh
python -m pip install uriel-research
```

For this unreleased candidate, clone the repository and install the checkout with available build tooling:

```sh
python -m pip install --no-deps --no-build-isolation .
```

## 2. Choose one authoritative record

Save the exact research question in a UTF-8 file named `question.txt`. Choose evidence-neutral mode to test competing explanations without assuming any is correct, or exploratory mode to investigate mechanisms under a stated assumption.

```sh
uriel record init --folder research-record --project demo --question-file question.txt --mode evidence-neutral
```

For Trilium, create an ETAPI token in the application and supply it through the environment variable `URIEL_ETAPI_TOKEN`, not a command argument or file. Choose a unique project key and the ID of the desired parent note.

```sh
uriel trilium connect --url http://127.0.0.1:37740
uriel trilium init --url http://127.0.0.1:37740 --project demo --parent root --question-file question.txt --mode evidence-neutral
```

The tree contains Question, Current picture, Leads, Conclusions register, Ruled out, Gaps and tensions, Decisions and direction history, Sources and data, and Manuscript. Stable keys survive note renames and moves. Read an existing section before replacing its prose; conflicting edits are retained for review. The ETAPI update limitation and safer proposal workflow are explained in [Research records](docs/RESEARCH_RECORD.md).

## 3. Load material

Preview placements and confirm the saved plan. Exact-byte duplicate imports reuse their original records; PDFs are kept as attachments.

```sh
uriel record import --folder research-record observations.csv notes.md --plan import.json
uriel record import --folder research-record --plan import.json --confirm
uriel record verify --folder research-record --save-baseline baseline.json
```

Replace `record` with `trilium` and use `--url` and `--project` for a live tree. The top-level commands below accept the same location arguments. ZIP export and import preserve stable identities and do not silently replace differing notes.

## 4. Work through leads and conclusions

```sh
uriel checklist start --folder research-record
uriel check-before-push "proposed explanation" --folder research-record
uriel record add lead-1 --folder research-record --file lead.json
uriel record freeze prediction-1 --folder research-record --file prediction.json
uriel checklist mid-before --folder research-record --lead lead-1 --prediction prediction-1 --attestations confirmations.json
uriel record result result-1 --folder research-record --file result.json
uriel record conclude conclusion-1 --folder research-record --file conclusion.json
uriel checklist mid-after --folder research-record --lead lead-1 --result result-1 --prior CHECKLIST_KEY --attestations confirmations.json
uriel summary --for-successors --folder research-record
```

Prepare the JSON files using the [record fields](docs/RESEARCH_RECORD.md), and substitute the mid-before receipt key for CHECKLIST_KEY. A frozen prediction includes a published control, expected effect size and criteria. A null closes a hypothesis only under the recorded sensitivity and audit conditions; otherwise it is a limit or remains untested. The checklists record missing items and where to fix them. Manual confirmations must identify the reviewer and evidence. See [worked example and record fields](docs/RESEARCH_RECORD.md).

## 5. Prepare a manuscript

```sh
uriel checklist pre-submission --folder research-record
```

Trace material claims to labelled evidence, preserve limitations and counter-evidence, reproduce numbers, inspect manuscript preflight findings, check venue policies, disclose AI assistance accurately and obtain human approval. A clean checklist means only that its defined checks were recorded as satisfied. It is not independent scientific validation.

## Advanced and experimental tools

Existing project commands remain available. Use them where needed rather than as prerequisites for the research record: Data Desk and Gate 0, Gate 1, Gate 2 and Gate 3 integrity checks, [Paper Builder](docs/PAPER_BUILDER.md), [plan lock and research protocol](docs/RESEARCH_PROTOCOL.md), optional adversarial checks, and [manuscript preflight](docs/PAPER_PREFLIGHT.md). The legacy Forge Method, Forge Trials, Next-Move ratings and Strict Blessing (The Blessing of Uriel, a content-addressed attestation) are optional. Synthetic trial fixtures verify the scoring machinery; this does not claim that Uriel detected every seeded issue. See [capabilities](docs/CAPABILITY_STATUS.md), [limitations](docs/LIMITATIONS.md), and [privacy](docs/AI_USAGE_AND_PRIVACY.md).

For existing legacy projects: `uriel start --root .`, `uriel status --root .`, and `uriel verify --root .` remain supported.

[Contribute](CONTRIBUTING.md) ? [License](LICENSE) ? [Report a security issue](SECURITY.md)
