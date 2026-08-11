# Setja Skill Reference

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
2. Do not scan `workspace` directly during reasoning when Setja is the intended path.
3. Keep `context` small and useful.
4. Use Hexis to control relevance and emphasis.
5. Treat Rúnir as optional enrichment, not a hard dependency.
6. Run the CLI for `init`, `build`, `inject`, and `prepare` instead of re-implementing them in prompt logic.
7. Prefer `prepare` for the normal first-run path; reserve `init` for explicit scaffold setup/debugging.

## Anti-patterns

- raw repo crawling
- dumping all notes into context
- mixing long-term memory concerns into Setja
