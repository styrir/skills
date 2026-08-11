---
name: setja
description: >-
  Use when Codex should construct curated agent context from local project
  artifacts via the Setja CLI. This skill is a thin wrapper: it tells Codex
  when to run `setja init`, `setja build`, `setja inject`, or `setja prepare`,
  and to avoid reimplementing Setja logic in prompt text.
---

# Setja Skill

## Purpose
Use the Setja CLI as the canonical path from raw local artifacts to curated agent context.

## Core Rule
Run the CLI. Do not recreate Setja behavior manually inside the skill.

## Use this when
- a project needs Setja bootstrap or scaffold inspection
- local artifacts under `workspace/` should be turned into curated context
- an agent needs a task-focused injected context envelope
- the user wants the full build+inject flow in one step

## Default flow
1. `setja prepare --hexis=<name> --query="<task>"` for the normal bootstrap + build + inject path
2. `setja build --hexis=<name>` when local artifacts changed and you want to refresh guides without injecting yet
3. `setja inject --hexis=<name> --query="<task>"` when the agent needs the smallest useful context package
4. `setja init` only when you want scaffold-only setup/debugging without running the rest of the flow

## Ergonomic shortcuts
- `setja prepare` uses the default Hexis profile with no task string
- `setja prepare --product "..."` uses the product profile with a positional task query
- `setja inject --debug "..."` uses the debug profile with a positional task query

## Constraints
- Do not scan `workspace/` directly when Setja should be the context path.
- Keep long-term memory concerns outside Setja unless Rúnir enrichment is explicitly configured.
- Treat this skill as a thin invocation layer over the CLI-first runtime.
- Remember that local injection is Hexis-aware: baseline docs come first, generated guides follow, then boosted deeper docs are added in deterministic bounded order.

## More detail
- Command guidance, usage rules, and anti-patterns: [references/usage.md](references/usage.md)
