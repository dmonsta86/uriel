# Privacy and optional AI

## No endorsement

Uriel may document practical model options, but it does not endorse OpenCode, OpenAI, DeepSeek, a local-model package, or any other provider. Availability, quality, pricing, retention, training use, jurisdiction, security controls, and terms can change after this document is written.

Before using any external service, verify its current official terms and your project authorization.

## Data classification

Set `privacy.classification` in `uriel.project.json`:

- `public` — already intentionally public, while still respecting copyright and licenses;
- `internal` — non-public working material with low sensitivity;
- `confidential` — unpublished, contract-limited, personal, commercially sensitive, or embargoed material;
- `restricted` — regulated, export-controlled, safety-critical, highly identifying, or explicitly forbidden from third-party processing.

Set `privacy.external_ai` to `allow`, `ask`, or `deny`. `ask` is the default.

## Minimum-disclosure rule

Do not send a whole repository merely because a model accepts large context. Export one bounded claim, definition, table, or source question at a time. Remove:

- names and direct identifiers;
- credentials, tokens, private URLs, and internal hostnames;
- raw participant data;
- unpublished patent or embargoed material;
- contract-prohibited sources;
- exact local paths when an evidence id and hash are sufficient.

## Recommended path for sensitive work

1. Run Uriel Core entirely offline.
2. Use a human reviewer under the project's confidentiality rules.
3. If model assistance is justified, prefer an offline model on an authorized machine.
4. Bind the resulting review to the exact source/project hashes.
5. Verify every locator and finding locally before changing the manifest.

“Local” is not automatically safe: inspect the model package, server binding, logs, plugins, update mechanism, and whether the application contacts remote services.

## Free services and training use

A zero-price model can be funded through data collection or evaluation. Treat “free” as a price label, not a privacy guarantee. OpenCode's current free-model page explicitly warns that data collected during several free periods—including DeepSeek V4 Flash Free—may be used to improve the model. Never upload sensitive project content merely to avoid payment.
