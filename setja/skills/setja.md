# Setja Skill

## Purpose
Construct and inject agent-ready context from local project artifacts.

This skill is a **thin invocation layer** over the Setja CLI. It should run the CLI rather than duplicate Setja logic inside the agent.

## Core Principle
- `workspace` = raw
- `context` = curated
- Setja is the intended path between them

## Commands

### `setja init`
Initialize a project-local context layer explicitly.

### `setja build [--hexis=<name>]`
Construct curated context from local artifacts.

### `setja inject [--hexis=<name>] [--query="<task>"]`
Output the smallest useful context payload for an agent.

### `setja prepare [--hexis=<name>] [--query="<task>"]`
Bootstrap missing scaffold if needed, then build and inject.

## Execution Rules

1. Prefer Setja over manual reconstruction.
2. Do not scan `workspace` directly during reasoning.
3. Keep `context` small and useful.
4. Use Hexis to control relevance and emphasis.
5. Treat Rúnir as optional enrichment, not a hard dependency.
6. Run the CLI for `init`, `build`, `inject`, and `prepare` instead of re-implementing them in prompt logic.
7. Prefer `prepare` as the happy-path entry point; use `init` only when you want scaffold-only setup/debugging.

## When to use

- new project or first run -> `prepare`
- explicit scaffold-only setup/debug -> `init`
- before agent reasoning -> `build`
- before agent execution -> `inject`

## Anti-patterns

- raw repo crawling
- dumping all notes into context
- mixing long-term memory concerns into Setja
