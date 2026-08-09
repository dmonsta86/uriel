# Free and low-cost AI quick start

Availability, identifiers, quotas, prices, privacy terms, and retention policies
can change. Read the chosen provider's current official terms before sending
work; this repository intentionally does not snapshot price or quota claims.

Uriel Core does not need AI. Use AI only where semantic search, field mapping, quotation checking, or adversarial interpretation adds value. Model output is a lead or critique, never evidence by itself.

## Route A — completely offline, zero spend

```console
python uriel.pyz intake "YOUR QUESTION" --root my-project
python uriel.pyz audit --root my-project --profile exploratory
python uriel.pyz prompt --root my-project clarity --provider local --show
```

Give the saved prompt to a local model you already operate, a human reviewer, or work through it manually. Import only the JSON contract after checking its claims and locators.

```console
python uriel.pyz review-template --root my-project clarity
python uriel.pyz review-import --root my-project .uriel/review-inbox/review.json
```

Uriel does not install or silently download a model. That keeps the base app small, understandable, and usable on old hardware.

## Route B — provider-neutral free models

Optionally use any provider-neutral terminal, desktop, or IDE agent that connects to your preferred local or free model endpoints.

Generate a provider-neutral review prompt:

```console
python uriel.pyz prompt --root my-project clarity --provider generic --show
```

Attach the generated prompt file to your local or external agent session and
preserve its raw output locally yourself. Uriel imports only a valid,
current-hash-bound JSON review into project state.

### Make a small free pool useful

Work in bursts:

1. Run the offline exploratory audit first.
2. Choose one blocker, one claim, or one source at a time.
3. Use a fast free model for structure, query generation, and obvious contradiction checks.
4. Verify every proposed source yourself and register the actual artifact.
5. Save the valid review; do not ask the model to repeat completed work.
6. Reserve the strongest model for the final, compact adversarial packet.

This is often more reliable than handing an entire unfinished field to one giant conversation.

## Route C — free web sessions

Generate a prompt and paste it into any web chat you are authorized to use:

```console
uriel prompt --root my-project primary-evidence --provider generic-web --acknowledge-external --show
uriel prompt --root my-project adversarial-review --provider sol-mode --show
```

The prompt contains a review contract and privacy warning. For confidential, unpublished, personal, regulated, contract-restricted, or export-controlled material, use a verified local deployment or an institutionally approved service instead.

## Route D — explicitly authorized external process

`uriel assist` is an optional adapter for a compatible `agent` executable. It
requires `--acknowledge-external`, passes one validated `provider/model`
identifier, uses no shell, starts in an isolated temporary working directory,
does not forward ambient credential-like environment variables, and stops at
15 minutes or 128 KiB of combined output. It is not an operating-system
sandbox; the selected executable may still perform provider transport under
the operator's authority.

```console
uriel assist --root my-project adversarial-review --model provider/model --acknowledge-external
```

## Strong final-pass recommendation

For the hardest repository-wide or manuscript-wide challenge, use the strongest
authorized model already available to you for one compact adversarial packet,
then use an independent human domain reviewer. The maintainer-tested optional
configuration is documented once in `AI_USAGE_AND_PRIVACY.md`; it is not a
dependency or truth guarantee. Final authority remains the inspectable
artifact, reproducible run, and accountable human interpretation.

## Privacy-safe defaults in this repository

Uriel's bounded prompt path redacts nonpublic projects through a narrow
metadata-only allowlist unless sensitive content is explicitly requested. The
external-process adapter requires acknowledgement, applies project external-AI
policy, validates the model identifier, isolates its working directory, does
not invoke a shell, minimizes its environment, caps prompt/output/time, and
imports only an exact hash-bound review contract. These controls reduce
accidental exposure; they do not sandbox the executable or replace current
provider-policy review.

## What Uriel will tell you needs AI or a human

Deterministic code can verify file bytes, links, manifests, receipts, schema fields, known textual patterns, internal claim mappings, and declared completeness. It cannot independently establish:

- whether the literature search was semantically exhaustive;
- whether a novel idea has obscure prior art in every language or private archive;
- whether an extraction faithfully represents a complex source without inspecting it;
- whether the methods are valid for every discipline;
- whether an ethical or legal judgment is correct;
- whether a claim is true in the world.

For those tasks, `uriel capability` records a local default-deny request, and `uriel prompt` creates a bounded handoff.
