# Setja DOX

## Purpose

Owns Setja, the TypeScript-first CLI runtime that turns local project artifacts into curated, task-focused context for agents.

## Ownership

- `src/` owns CLI, context construction, injection, Hexis, summarization, hooks, and optional Rúnir integration.
- `test/` owns executable behavior and contract coverage.
- `docs/` owns durable architecture, operating model, vision, and Rúnir-boundary guidance.
- `skills/setja/` owns the portable bundled skill; adapters under `adapters/` remain thin invocation layers.
- `templates/` and `example-project/` own scaffold defaults and smoke-test fixtures.

## Local Contracts

- Keep the CLI as the canonical execution surface; skills and harness adapters must invoke it rather than reimplement runtime behavior.
- Keep Setja focused on present-time context shaping. Rúnir is optional and owns cross-session memory.
- Do not make agents read `workspace/` directly when Setja is the context path; build curated material under `context/` first.
- Preserve deterministic `outline` operation while treating configured model-backed summarization as the preferred normal path.
- Keep `workspace/`, `node_modules/`, `dist/`, local environment files, and external harness installations out of source control. Preserve the tested repo-local `.codex/skills/setja/` mirror and keep it byte-aligned with `skills/setja/`.
- Do not commit secrets. Configuration belongs in environment variables or local `.env` files; `.env.example` contains placeholders only.

## Work Guidance

- Read `README.md`, `docs/architecture.md`, and `docs/operating-model.md` before changing command behavior, pipeline boundaries, or user workflow.
- Read `skills/setja/SKILL.md` and its references before changing skill discovery or invocation guidance.
- Update tests and durable docs with any command, configuration, package, scaffold, injection-envelope, or adapter-contract change.
- Keep generated `dist/` and dependency trees local; validate them but do not commit them.

## Verification

From `setja/`:

```bash
npm run check
npm test
npm run build
npm pack --dry-run
```

For CLI or scaffold changes, also run the affected command against a disposable copy of `example-project/` or another temporary directory. Run `git diff --check` before closeout.

## Child DOX Index

No child DOX documents are currently required.
