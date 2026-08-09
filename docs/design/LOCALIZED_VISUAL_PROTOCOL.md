# Localized visual protocol

This protocol is the maintainer contract for Core-8 README artwork. It keeps
localization equal in visual quality without confusing generated text,
AI-assisted review, native-language review, or project authority.

## Locked boundaries

- The English gold hero is a locked reference. Do not simplify or replace it
  to manufacture parity.
- Every non-English README owns a distinct locale-specific image.
- A visual score is evidence of visual quality only. It is not translation
  authority, scientific authority, or native-language approval.
- Generated text must retain `AI_ASSISTED_REQUIRES_NATIVE_REVIEW` until a named
  native-language review is recorded.
- Visual processing is local, offline, and deterministic. Image generation is
  an optional external input and is never started by Uriel itself.

## Current publication states

`GOLD_REFERENCE`
: Locked English reference bytes.

`LOCALIZED_AI_REVIEWED`
: A distinct localized poster passed the visual gate and an independent
  AI-assisted copy screen. Visible text still requires native review.

`LOCALIZED_VERIFIED`
: Reserved for a future edition whose exact visible text has named
  native-language review evidence and whose manifest binds the corrected final
  bytes. Do not use this status merely because a model produced fluent text.

## Preferred production path

Use two stages for new or corrected editions:

1. Generate art from `globalization/image_prompts/<locale>.md`. The art must
   contain no words, letters, numbers, pseudo-writing, logos, or UI text.
2. Render reviewed copy from `globalization/image_copy/<locale>.json` with
   `scripts/render_localized_heroes.py`.

The full-poster path exists for reviewed supplied posters. It preserves
embedded typography and therefore cannot claim deterministic typography.

## Safe install

The renderer has no implicit bulk mode. Every source is explicit,
repository-confined, link-free, and hash-pinned.

Art-only source:

```text
python scripts/render_localized_heroes.py --candidate es=path/to/art.png --source-sha256 es=<lowercase-sha256>
```

Full-poster source:

```text
python scripts/render_localized_heroes.py --poster es=path/to/poster.png --source-sha256 es=<lowercase-sha256>
```

For multiple locales, repeat both source options. Never reuse one locale's
bytes under another locale name. Remove transient candidates after the final
hash is recorded.

The renderer:

- accepts PNG input only;
- enforces minimum source dimensions and a 16:9 aspect ratio;
- bounds input sizes and detects changes during reads;
- rejects external, linked, and reparse-point paths;
- disables browser networking and uses a fresh temporary profile;
- renders at exactly 3840 × 2160;
- publishes atomically, with the final image written last;
- makes no AI or network call and consumes no model usage.

## Review gate

Each localized poster must pass all of these conditions:

```text
overall                       >= 90 / 100
composition parity            >= 13 / 15
character and expression      >= 14 / 15
research-story coverage       >= 18 / 20
detail density                >=  9 / 10
lighting and materials        >=  8 / 10
cultural subtlety             >=  9 / 10
text-safe composition         >=  4 / 5
accessibility and contrast    >=  4 / 5
brand continuity              =   5 / 5
negative constraints          =   5 / 5
English reference gap         <=  3 points
```

Record the independent score in `globalization/visual_sources.json`. Record
the language-review boundary separately; never infer it from the visual score.

## Manifest update

After a reviewed visual changes:

1. Update `globalization/visual_sources.json` with the source archive/member,
   source hash, dimensions, alt text, score, and review boundary.
2. Refresh manifests with `scripts/update_localization_manifests.py`.
3. Run `scripts/check_localization_integrity.py`.
4. Run the focused localization tests.
5. Run the complete release check before pushing.

The updater binds README, image, source registry, prompt, copy, renderer, and
visual-manifest hashes. The checker rejects stale hashes, wrong dimensions,
duplicate heroes, unsafe paths, hidden PNG metadata, score regressions,
generated-review overclaims, and leftover candidate or art-layer files.

## Git and recovery

- Work on the canonical `main` checkout only.
- Inspect `git status --short` before and after every bounded visual package.
- Do not use destructive reset or checkout commands to clean unrelated work.
- Do not commit transient candidates, staging folders, downloaded archives,
  local absolute paths, provider instructions, credentials, or private notes.
- Create and verify a full-history Git bundle before pushing a material visual
  replacement. Store it outside the repository.
- Commit the visual package only after focused and full release checks pass.
- Push `main`, then verify local `HEAD`, `origin/main`, and the remote commit
  identifier agree.

If any boundary cannot be satisfied, keep the previous published image and
record the candidate as rejected. Missing review evidence is not permission to
lower the status gate.
