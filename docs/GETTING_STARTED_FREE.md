# Getting started for free

Last verified: **2026-08-06**. Model names, free pools, prices, and privacy terms change; confirm current official pages before use.

## Route A — no AI, no account, no network

This is the complete trusted path, not a reduced demo.

```bash
git clone <repository-url>
cd uriel
python -m pip install -e .

uriel intake "Could the apparent effect come from the way the control was selected?" --root ../my-study
cd ../my-study
uriel audit --profile exploratory
```

Add direct source artifacts under `sources/`, generated results under `artifacts/`, and edit `uriel.project.json`. Repeat the audit until each claim is explicit and supported.

## Route B — one portable file

From a machine with the repository:

```bash
python scripts/build_portable.py
```

Copy `dist/uriel.pyz` to any machine with Python 3.9+:

```bash
python uriel.pyz intake "My question" --root my-project
```

## Route C — compatible external agent with a currently free model

Install compatible external agent using one of its official methods:

```bash
# macOS/Linux installer
curl -fsSL https://compatible external agent.ai/install | bash

# Node.js
npm install -g compatible external agent-ai

# macOS/Linux Homebrew
brew install anomalyco/tap/compatible external agent
```

Windows users can use WSL (recommended by compatible external agent), Chocolatey, Scoop, or npm:

```powershell
choco install compatible external agent
# or
scoop install compatible external agent
# or
npm install -g compatible external agent-ai
```

Then:

```bash
cd /path/to/your/uriel-project
compatible external agent
# In the TUI: /connect
# Then: /models
```

As of 2026-08-06, compatible external agent lists **web AI session V4 Flash Free** and several other models as limited-time free. The free list can disappear or change, and compatible external agent warns that data collected during several free periods may be used to improve the model. **web AI session V4 Pro is listed in the paid low-cost compatible external agent Go catalog, not the current free list.**

Use the free pool in short, bounded bursts:

```bash
uriel prompt clarity --root . --provider compatible external agent
uriel prompt primary-evidence --root . --provider compatible external agent
compatible external agent models
```

Start with one claim, one contradiction, or one source. Save scarce context for synthesis only after the evidence table is clean.

The direct adapter is optional:

```bash
uriel assist adversarial-review \
  --root . \
  --model PROVIDER/MODEL \
  --acknowledge-external
```

It calls compatible external agent with an attached hash-bound prompt and imports only the required review JSON. The model still cannot pass a Gate.

## Route D — compatible external agent with an offline local model

compatible external agent supports local OpenAI-compatible servers, including configurations for Ollama, LM Studio, llama.cpp, and similar tools. The exact hardware-appropriate model is deliberately not hard-coded in Uriel.

Typical `compatible external agent.json` fragment for Ollama:

```json
{
  "$schema": "https://compatible external agent.ai/config.json",
  "provider": {
    "ollama": {
      "npm": "@ai-sdk/openai-compatible",
      "name": "Ollama (local)",
      "options": {"baseURL": "http://127.0.0.1:11434/v1"},
      "models": {
        "YOUR_LOCAL_MODEL": {"name": "Local research helper"}
      }
    }
  }
}
```

Keep the server bound to loopback, disable sharing, inspect logs/plugins, and confirm the application does not upload prompts or telemetry.

## Route E — web chat with zero initial investment

Generate a prompt, inspect it, and paste it manually into an available web model:

```bash
uriel prompt repair-review --root . --provider generic --show
```

For small usage pools:

1. Ask for source-discovery queries, not a final paper.
2. Verify sources yourself and save the exact primary evidence locally.
3. Ask the next session to analyze only the verified evidence record.
4. Use Uriel offline between bursts so model context is not your memory system.

## Higher-capability final review

For users who already have access, the suggested final adversarial pass is **GPT-5.6 Sol Pro** for the highest-capability single-model ChatGPT review, **GPT-5.6 Sol with `ultra` mode** where coordinated multi-agent work is available, **Extra High** for the highest standard Sol reasoning slider in ChatGPT, or **`max` reasoning** where the API/Codex surface exposes it. This is a capability recommendation, not an endorsement or requirement.

Do not spend premium usage reformatting JSON or extracting obvious values. Reserve it for:

- finding a hidden assumption across many claims;
- reconciling genuinely contradictory primary data;
- designing decisive adversarial tests;
- checking whether the strongest interpretation survives alternate framing;
- final submission-level red-team review.

Every model output remains untrusted until direct artifacts and locators are verified.
