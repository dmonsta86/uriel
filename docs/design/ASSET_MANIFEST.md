# Public asset manifest

Every path below is repository-relative and checked by the public-identity
gate. The active README image for each locale is also hash-bound by
`docs/i18n/manifests/*.json`.

## Active hero images

- `docs/assets/the-forge-of-uriel/hero.png`
- `docs/assets/i18n/ar/uriel-forge-hero.png`
- `docs/assets/i18n/es/uriel-forge-hero.png`
- `docs/assets/i18n/fr/uriel-forge-hero.png`
- `docs/assets/i18n/hi/uriel-forge-hero.png`
- `docs/assets/i18n/ja/uriel-forge-hero.png`
- `docs/assets/i18n/pt-BR/uriel-forge-hero.png`
- `docs/assets/i18n/zh-Hans/uriel-forge-hero.png`

The English asset is the locked gold reference. Each non-English asset is a
distinct 3840 × 2160 explainer poster with the public status
`LOCALIZED_AI_REVIEWED`; visible generated text retains the explicit boundary
`AI_ASSISTED_REQUIRES_NATIVE_REVIEW`.

## Visual provenance and reproduction

- `globalization/visual_sources.json` binds the verified source archive,
  source members, source hashes, independent scores, and exact alt text.
- `docs/i18n/visual_manifests/*.json` binds each published image, its source,
  review boundary, score, copy, prompt, renderer, and final hash.
- `globalization/image_prompts/*.md` contains the preferred art-only
  regeneration prompts.
- `globalization/image_copy/*.json` contains deterministic Core-8 overlay copy
  for future corrected editions.
- `scripts/render_localized_heroes.py` performs confined, offline,
  deterministic normalization and supports both full-poster and art-only
  inputs.
- `docs/design/LOCALIZED_VISUAL_PROTOCOL.md` defines the safe install, review,
  manifest, recovery, and publication sequence.

The generated full-poster sources remain in the hash-verified source archive;
they are not duplicated as stale art layers in the repository.

## Design variants retained for reuse

- `docs/assets/the-forge-of-uriel/variants/hero-evidence-variant.png`
- `docs/assets/the-forge-of-uriel/variants/hero-research-variant.png`
- `docs/assets/variants/01_uriel_forge_forging_ideas_through_evidence.png`
- `docs/assets/variants/02_uriel_forge_the_evidence_workshop.png`
- `docs/assets/variants/03_uriel_forge_the_evidence_foundry.png`
- `docs/assets/variants/04_uriel_forge_the_evidence_blacksmith.png`

## Reproduction prompts

- `docs/design/visual-prompts/01_PRIMARY_HERO_PROMPT.txt`
- `docs/design/visual-prompts/02_EVIDENCE_VARIANT_PROMPT.txt`
- `docs/design/visual-prompts/03_RESEARCH_VARIANT_PROMPT.txt`
- `docs/design/visual-prompts/localized/ar.txt`
- `docs/design/visual-prompts/localized/en.txt`
- `docs/design/visual-prompts/localized/es.txt`
- `docs/design/visual-prompts/localized/fr.txt`
- `docs/design/visual-prompts/localized/hi.txt`
- `docs/design/visual-prompts/localized/ja.txt`
- `docs/design/visual-prompts/localized/pt-BR.txt`
- `docs/design/visual-prompts/localized/zh-Hans.txt`

The historical root-level banner aliases were byte-identical to the active
English hero and are intentionally not part of the public asset surface.
