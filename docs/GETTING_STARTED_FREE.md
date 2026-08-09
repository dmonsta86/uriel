# Getting started for free

Model names, free pools, prices, and privacy terms change; confirm current
official pages before use. Uriel does not depend on any such offer.

## Route A — no AI, no account, no network

This is the complete trusted path, not a reduced demo.

```bash
git clone <repository-url>
cd uriel
python -m pip install --no-deps --no-build-isolation .

uriel start --root ../my-study --kind new_idea --title "Control-selection study" --question "Could the apparent effect come from the way the control was selected?"
uriel audit --root ../my-study --profile exploratory
```

The distribution package is `uriel-research`; the Python import and CLI command
are both `uriel`.

Add direct source artifacts under `sources/`, generated results under `artifacts/`, and edit `uriel.project.json`. Repeat the audit until each claim is explicit and supported.

## Route B — one portable file

From a machine with the repository:

```bash
python scripts/build_portable.py
```

Copy `dist/uriel.pyz` to any machine with Python 3.9+:

```bash
python uriel.pyz start --root my-project --kind new_idea --title "My study" --question "What would change my conclusion?"
```

## Route C — provider-neutral external agent with a free or local model

Generate a bounded prompt, inspect it locally, and then paste it into the
compatible tool of your choice:

```bash
uriel prompt clarity --root ../my-study --provider generic --show
uriel prompt primary-evidence --root ../my-study --provider generic --show
```

Start with one claim, contradiction, or source. Uriel produces a hash-bound
review prompt; model output remains advisory and cannot pass a Gate.

## Route D — provider-neutral agent with an offline local model

Local OpenAI-compatible inference tools (such as Ollama, LM Studio, llama.cpp, and similar tools) may be used offline. The exact hardware-appropriate model is deliberately not hard-coded in Uriel.

Keep the server bound to loopback (`127.0.0.1`), disable sharing, inspect logs/plugins, and confirm the application does not upload prompts or telemetry.

```bash
uriel prompt adversarial-review --root ../my-study --provider local --show
```

## Route E — web chat with zero initial investment

Generate a prompt, inspect it, and paste it manually into an available web model:

```bash
uriel prompt repair-review --root ../my-study --provider generic-web --acknowledge-external --show
```

For small usage pools:

1. Ask for source-discovery queries, not a final paper.
2. Verify sources yourself and save the exact primary evidence locally.
3. Ask the next session to analyze only the verified evidence record.
4. Use Uriel offline between bursts so model context is not your memory system.

## Higher-capability final review

For a final adversarial pass, use the strongest authorized model already
available to you on one compact, redacted packet. The single maintainer-tested
optional configuration is documented in `AI_USAGE_AND_PRIVACY.md`; it is not
an endorsement, requirement, privacy guarantee, or substitute for a human
domain reviewer.

Do not spend premium usage reformatting JSON or extracting obvious values. Reserve it for:

- finding a hidden assumption across many claims;
- reconciling genuinely contradictory primary data;
- designing decisive adversarial tests;
- checking whether the strongest interpretation survives alternate framing;
- final submission-level red-team review.

Every model output remains untrusted until direct artifacts and locators are verified.
