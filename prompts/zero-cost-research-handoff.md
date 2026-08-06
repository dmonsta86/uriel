# Zero-cost research handoff

Paste the output of `uriel prompt TASK --provider chatgpt-web --show` into an authorized web model. Ask it to return only the JSON contract. Then:

1. verify every locator against the underlying source;
2. preserve permissible source bytes or an access receipt;
3. run `uriel add-evidence` for real artifacts;
4. import the review only after its source/project hashes match;
5. rerun the deterministic audit.

The model is a search and critique assistant, not the source of record.
