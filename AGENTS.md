# Agent Instructions — Skills

Read this first. Keep this file concise; detailed task guidance lives under `docs/agent-guidance/`.

## Repository Contract

This repository is the source of truth for agent skills shared across Claude Code, Codex, Hermes, and related harnesses. Edit skills here; harness directories should link to this tree rather than carry divergent copies.

- Treat each skill's `SKILL.md` as its entry contract and inspect its linked files before changing behavior.
- Preserve compatibility pointers for superseded skills unless removal is explicitly requested.
- Keep secrets out of the repository. Credentials belong in environment variables or the macOS Keychain.
- Do not absorb or reformat unrelated dirty working-tree changes.
- Use non-interactive flags for shell operations that may prompt.
- A completed, verified tranche must be committed and published before closeout: follow the configured non-force Git publication workflow and verify its ref. Task state stays in local Verk; there is no Beads/Dolt synchronization. This is standing authority for ordinary non-force publication; ask before destructive history rewrites, force pushes, or creating/changing remotes.

## Task Routing

| If you are working on... | Read |
|---|---|
| Verk, task planning, `.pipeline/` artifacts, handoffs, or closeout | `verk/SKILL.md`, then `docs/agent-guidance/planning-verk-and-handoffs.md` |
| WorkGraph shipping Test / `.grok/quality-gates.yaml` | `.grok/quality-gates.yaml` (JSON-compatible YAML 1.2; `workgraph-quality-gates`) |
| Adding, moving, or validating durable documentation | `docs/AGENTS.md` |
| The Ask skill or provider/model routing | `ask/SKILL.md`, `ask/providers.json`, and the relevant files under `ask/scripts/` |
| Setja runtime, CLI, package, adapters, or bundled skill | `setja/AGENTS.md`, then the relevant entry contract or source files |
| Another skill | That skill's `SKILL.md`, then its referenced `scripts/`, `references/`, `templates/`, or `assets/` files |

## Verk posture

The operator decommissioned Beads. Use Verk for durable task state, including
when an older document still mentions bd. Do not run bd, repair its databases,
restart its services, migrate old stores or synchronize Dolt task refs.

This checkout is bound to the local Verk project `skills`. Read `verk/SKILL.md`
and use its session-scoped wrapper: brief and view, start before edits,
checkpoint at handoff, and verify receipts before calling a contract satisfied.
Operator decisions and policy approval remain the operator's actions.

## Child DOX Index

- `docs/AGENTS.md` — owns durable documentation and progressive-disclosure guidance below `docs/`.
- `setja/AGENTS.md` — owns the Setja TypeScript runtime, package, tests, documentation, templates, adapters, and bundled skill.
