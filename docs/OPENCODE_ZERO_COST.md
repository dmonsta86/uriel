# Start Uriel with OpenCode at zero or very low cost

This guide was checked against official OpenCode documentation on **2026-08-06**. Free models, identifiers, quotas, and privacy terms are temporary and can change. Run `opencode models` and read the current Zen page before use.

## 1. Install Uriel

From the repository:

```bash
python -m pip install .
uriel --version
```

Or build the portable file:

```bash
python scripts/build_portable.py
python dist/uriel.pyz --version
```

## 2. Install OpenCode

Official install options currently include:

```bash
curl -fsSL https://opencode.ai/install | bash
```

or:

```bash
npm install -g opencode-ai
```

On Windows, OpenCode currently recommends WSL for the best compatibility. Native alternatives include Chocolatey, Scoop, and npm.

Official installation page: https://opencode.ai/docs/

## 3. Connect a provider and inspect models

Run:

```bash
opencode
```

Use `/connect`, then inspect exact current identifiers:

```bash
opencode models
```

As of 2026-08-06, the OpenCode Zen page listed limited-time free options including:

- DeepSeek V4 Flash Free;
- MiMo-V2.5 Free;
- Laguna S 2.1 Free;
- Ling-3.0-flash Free;
- LongCat-2.0 Free;
- North Mini Code Free;
- Nemotron 3 Ultra Free;
- Big Pickle.

This is not a promise that any model remains available. Some listed free endpoints have explicit collection or improvement-use exceptions. Do not send personal or confidential data merely because an endpoint costs zero.

Current list and privacy notes: https://opencode.ai/docs/zen/

## 4. Use the included Uriel reviewer

This repository includes `.opencode/agents/uriel-reviewer.md`, a no-edit reviewer. OpenCode supports per-project agents in `.opencode/agents/`.

Generate a bounded prompt:

```bash
uriel prompt clarity --root my-study --provider opencode --acknowledge-external
```

Start OpenCode in the repository or project directory and invoke:

```text
@uriel-reviewer Read .uriel/prompts/clarity-HASH.md and return only the required JSON object.
```

Save the result under `.uriel/review-inbox/review.json`, then:

```bash
uriel review-import .uriel/review-inbox/review.json --root my-study
```

The import checks that the review names the exact project and source hashes. It does not trust the citations.

## 5. Optional one-command adapter

After choosing the exact current `provider/model` identifier:

```bash
uriel assist clarity \
  --root my-study \
  --model opencode/MODEL-ID \
  --acknowledge-external
```

The adapter uses `shell=False`, preserves raw output, validates the JSON contract, and imports it. Provider authentication and network behavior remain outside Uriel Core.

## 6. Work in bursts

Small free pools are enough to begin when each request is narrow:

1. **Clarity burst:** one question, three faithful formulations, no literature search.
2. **Primary-source burst:** one claim, locate the earliest accessible primary source.
3. **Extraction burst:** one source, exact page/table/row and minimal quotation or value.
4. **Counterevidence burst:** one claim, actively search for disconfirming data.
5. **Control burst:** compare population, measurement, exclusions, and baseline.
6. **Synthesis burst:** only after local verification, assemble the claim-evidence map.

Do not spend scarce tokens asking a model to rewrite material Uriel can validate deterministically.

## 7. Stronger-model option

For the most difficult final adversarial review, the project recommends **GPT-5.6 Sol Pro** for the highest-capability single-model ChatGPT option, **GPT-5.6 Sol with `ultra` mode** for eligible coordinated multi-agent work, **Extra High** for the highest standard Sol reasoning slider in ChatGPT, or **`max` reasoning** where the API/Codex surface exposes it. Lower-cost or free models remain useful for bounded tasks.

This is not an endorsement. Review privacy and cost, and remember that no model output can issue a Uriel Blessing.

Official references checked 2026-08-06:

- https://developers.openai.com/api/docs/models/gpt-5.6-sol
- https://developers.openai.com/api/docs/guides/latest-model
- https://openai.com/index/previewing-gpt-5-6-sol/
- https://openai.com/index/gpt-5-6/
