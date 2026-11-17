# Shared UI skills installation — 2026-11-17

Contract: vk-2862. The operator authorized completing the setup in the default
agents skills directory. This supersedes the earlier pilot's project-only
installation boundary for this destination, not for other harness configuration.

## Delivered

Added design-policy and whole-directory links for Emil break-ui,
review-animations and pick-ui-library through the existing agents manifest.
Emil is pinned to 0f2e23b32bb1265e84cff8d3e75785fec953fb1b from
https://github.com/emilkowalski/skills.git. Source and all relative resources,
including the sibling choreograph reference, remain in the intact checkout.
The policy routes to existing provider-specific Impeccable, optional enabled
Taste, and connected Mobbin. Cook remains explicitly requested and bounded.
No provider build, hook, connector, or other harness configuration was changed.

## Observed checks

- Skill creator validation passed using its bundled validator with PyYAML.
- test_installation.py passed: manifest pin alignment, actual existing linker,
  whole-directory resources, idempotence, and rollback preserving an unrelated file.
- Live linker dry run showed four new paths and no replacements. Apply and check
  passed, with the pre-existing conversion link unchanged.
- Fresh installed Codex app-server skills/list with forceReload discovered all
  four new skills enabled at their real source paths, and existing Impeccable enabled.
- Existing Taste was discovered disabled. The policy respects that setting and
  uses Impeccable instead; no setting was changed to force activation.
- All three exposed Emil skills resolve to the pinned HEAD. Git status including
  ignored and untracked files was empty. Markdown file references resolve from
  each real upstream skill directory.

## Evidence limits

This verifies the live default-directory registration, read paths, and reversible
link operation. It does not claim a new model-driven UI build, universal implicit
selection, or live Claude/Grok/Hermes activation. The November 13 second pilot
previously exercised native explicit reads and A/B/A rollback; those results are
historical, not substitutes for this installation's observations. Upstream
explicit-invocation metadata is preserved; this policy also keeps the two
specialist lookup/review skills request-driven across consumers.

Rollback is scoped to the four newly introduced manifest entries and links,
as recorded in installation.json. Existing provider installs remain owned by
their existing installers. Required repository test and independent review
results are recorded in Verk against the committed revision.
