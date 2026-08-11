# Setja Vision

## Why Setja exists

Most AI-assisted projects have the same structural problem:

- there are raw artifacts the agent should be able to benefit from
- those artifacts are often local-only and intentionally not committed to Git
- agents either cannot see them, or they see too much and consume them badly

That creates a familiar failure mode: the repo contains the canonical code, but the *useful local reality* lives in screenshots, HTML prototypes, notes, research scraps, and other working material that the agent either ignores or misreads.

Setja exists to solve that exact gap.

It gives a project a **local workspace layer** for raw material and a **curated context layer** for agent consumption. The missing middle is a controlled build step that decides what should become context and what should remain raw.

## Core idea

```text
raw project artifacts -> Setja build -> curated context -> Setja inject -> agent
```

Setja is therefore a **present-time context system**.

It does not try to be memory, search, or long-term recall. It determines what matters for the current task and packages it in a form agents can use reliably.

## What problem it is really solving

The real problem is not “where do I store files that Git should ignore?”

The real problem is:

> How do I preserve local, project-specific working material in a form that agents can actually use without turning the repo into a junk drawer or asking the agent to crawl everything blindly?

Setja answers that by separating three concerns:

- **workspace** — raw local artifacts
- **context** — curated agent-facing material
- **Hexis** — the interpretive frame that decides what matters for this build

## Design goals

1. **Small, deliberate context**
   Agents should consume a curated context package, not arbitrary repo state.

2. **Local-first project reality**
   A project should have a place for HTML prototypes, screenshots, research, and scratch material that is useful but not meant for GitHub.

3. **Portable across agent environments**
   The core logic should work the same way under Codex, Claude Code, and Emdash.

4. **Compatible with memory systems without becoming one**
   Setja can optionally capture to / recall from Rúnir, but it should remain useful without any external memory system.

5. **Deterministic by default, richer when configured**
   It should work with a local outline summarizer, and become smarter when an LLM or vision-capable endpoint is configured.

## Non-goals

Setja is intentionally not trying to be:

- a knowledge graph
- a vector database
- a long-term memory layer
- a repo-wide code understanding engine
- a generic orchestration framework

Those may exist around Setja, but they are not Setja itself.

## What success looks like

A successful Setja workflow has these properties:

- local project artifacts live in a clear ignored workspace
- the project always has a current, curated context surface
- agents use the same context construction path no matter which environment runs them
- Hexis lets the same project material be framed differently for product, engineering, debugging, or research work
- Rúnir integration stays optional and cleanly bounded

## Architectural boundary with Rúnir

This distinction matters:

- **Setja** decides what matters *right now*
- **Rúnir** remembers what mattered *across time*

That boundary keeps both systems legible.

If Setja were renamed or treated like Rúnir, people would reasonably assume it owns persistence, cross-session recall, or memory ranking. It does not. It is the context construction layer that can feed those systems when needed.
