# AI usage and privacy

## Provider-neutral by design

Uriel does not require an online AI, coding agent, account, or provider-specific
workspace format.

A managed workspace may generate:

```text
URIEL_AI_ENTRY.md
COPY_THIS_TO_YOUR_AI.txt
NEXT_PROMPT.txt
```

Any compatible AI with access to the supplied files may assist.

`uriel burst` creates local files only; it never uploads them or calls a model.
Its default selected-record budget is 32,000 bytes. The hard limits are 1 MiB
of selected-record JSON, 16 KiB for the task instruction, 100 explicitly named
legacy record files, and 1 MiB plus 128 KiB for the complete packet. A
generation packet additionally requires explicit rows and columns, permits at
most 1,000 rows, and refuses any generation without an active independently
verified Gate 0 receipt. These are ceilings, not recommended targets.

Legacy source work is also bounded before hashing or reading: 16 MiB per file
and 64 MiB in total. Burst history is limited to 100 packets and each child
binds its parent's checksum-manifest SHA-256. Every packet declares advisory
read-only capabilities: no network, shell, packet writes, or project writes,
with requested output limited to 128 KiB and 15 minutes. Uriel records and
verifies that contract; the model host remains responsible for enforcement.

## Authority boundary

An AI may propose and draft.

It cannot:

- mark data ready;
- set evidence strength;
- change publication authority;
- pass a gate;
- close an authoritative Forge result;
- issue a Blessing.

## Local model

A compatible local model may be used on suitable hardware.

Local operation can reduce external exposure, but “local” does not remove the
need for project isolation, bounded context, model provenance, resource limits,
and prompt-injection defenses.

## Web AI

Before uploading unpublished or sensitive work:

- review retention and training terms;
- remove unnecessary identifiers;
- use a bounded packet;
- avoid credentials and restricted data;
- keep the authoritative state local.
- inspect `00_INSTRUCTION.md`, `STATE.json`, and `AI_SURFACE.json` before upload;
- prefer `--redact` when values are not necessary for the declared task.

## Maintainer-tested configuration

For the deepest Strict Forge, assurance, and adversarial passes, the maintainer
recommends:

```text
GPT-5.6 Sol with ultra mode
```

This is an optional maintainer recommendation.

It is not:

- a dependency;
- an exclusive integration;
- a guarantee;
- a privacy or retention endorsement;
- required for ordinary Uriel use.

Other compatible AIs can be used.

## Static documentation

Do not put current prices, free-tier promises, plan availability, or
provider-policy claims in the README. Those change over time.
