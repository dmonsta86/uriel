# Free and low-cost AI quick start

_Checked against official provider pages on 2026-08-06. Availability, identifiers, quotas, prices, privacy terms, and retention policies can change. Run current model-list commands and read current terms before sending work._

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

## Route B — compatible external agent free models

compatible external agent is an open-source terminal/desktop/IDE agent. Its official model list currently advertises several limited-time free models, including **web AI session V4 Flash Free**. The official free list does **not** currently describe web AI session V4 Pro as free; do not promise that it is. Free pools can be small or temporary.

Install compatible external agent using its current official instructions. Examples shown by compatible external agent include:

```console
# macOS/Linux install script
curl -fsSL https://compatible external agent.ai/install | bash

# Cross-platform Node installation
npm install -g compatible external agent-ai

# Windows alternatives shown by compatible external agent
choco install compatible external agent
# or
scoop install compatible external agent
```

Then, inside the Uriel repository or a Uriel project:

```console
compatible external agent models
compatible external agent
```

Select a current free model in the UI, or copy its exact `provider/model` identifier:

```console
uriel assist clarity \
  --root my-project \
  --model EXACT_PROVIDER/EXACT_FREE_MODEL \
  --acknowledge-external
```

Uriel’s adapter uses compatible external agent’s non-interactive `run` command, attaches the generated prompt file, and requires the exact `provider/model` form. Raw output is preserved. Only a valid, current-hash-bound JSON review is imported.

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
uriel prompt --root my-project primary-evidence --provider web AI session-web --show
uriel prompt --root my-project adversarial-review --provider sol-mode --show
```

The prompt contains a review contract and privacy warning. For confidential, unpublished, personal, regulated, contract-restricted, or export-controlled material, use a verified local deployment or an institutionally approved service instead.

## Route D — low-cost compatible external agent Go

compatible external agent currently advertises Go at **$5 for the first month and $10/month afterward**, with usage limits and the ability to continue on free models after the paid pool is reached. Treat the price and limits as current information, not a permanent promise.

This can be useful for short release bursts, but Uriel never requires it.

## Strong final-pass recommendation

For the hardest repository-wide or manuscript-wide challenge, prefer the highest model you already have legitimate access to:

1. **GPT-5.6 Sol + `ultra` mode**, where available, for coordinated multi-agent work;
2. **GPT-5.6 Sol Pro** for the highest-capability single-model option in ChatGPT;
3. **GPT-5.6 Sol at Extra High** for the highest standard Sol reasoning slider in ChatGPT;
4. **GPT-5.6 Sol with `max` reasoning** where the API/Codex surface exposes it;
5. a capable free/cheap model in several narrow passes;
6. a human domain expert using the same review contract.

“Sol 5.6 ULTRA” is best described precisely as **GPT-5.6 Sol used with OpenAI’s `ultra` mode**. `ultra` is a multi-agent mode, not a separate truth guarantee. The final authority remains the inspectable artifact, reproducible run, and accountable human interpretation.

## Privacy-safe defaults in this repository

`compatible external agent.json` sets sharing to `disabled`. The included `uriel-reviewer` agent denies editing and shell execution. Web access requires approval. These are guardrails, not a substitute for reading the provider’s current policy.

## What Uriel will tell you needs AI or a human

Deterministic code can verify file bytes, links, manifests, receipts, schema fields, known textual patterns, internal claim mappings, and declared completeness. It cannot independently establish:

- whether the literature search was semantically exhaustive;
- whether a novel idea has obscure prior art in every language or private archive;
- whether an extraction faithfully represents a complex source without inspecting it;
- whether the methods are valid for every discipline;
- whether an ethical or legal judgment is correct;
- whether a claim is true in the world.

For those tasks, `uriel capability` records a local default-deny request, and `uriel prompt` creates a bounded handoff.
