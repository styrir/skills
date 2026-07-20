# Profile schema

**Plan:** §6 · **DR:** DR-05, DR-14

## File

`$VOICE_PROFILE_DIR/<name>/profile.yaml`

## Required concepts

- `profile_version`, `name`
- `corpus_manifest` with `included_in_profile` flags
- `hypotheses` with evidence from ≥2 included samples, counterevidence, and genericity check
- `style_features` populated by deterministic analysis (`null` until measured)
- `protected_preferences.glossary` / `preserve` / `avoid`

## Enforceability

An hypothesis is `enforceable` only when observable; evidenced by ≥2 included samples; counterevidence recorded; genericity check has an independently acceptable contrast; `quality_inversion: false`; and `user_confirmed_author_specific: true`. Otherwise force `descriptive_only`. Using a non-enforceable hypothesis as a revision constraint returns `UNENFORCEABLE_PROFILE_HYPOTHESIS`.

## Held-out samples

Freeze ≥2 held-out authentic samples before profile generation. They must not inform profiles, prompts, thresholds, or repairs.
