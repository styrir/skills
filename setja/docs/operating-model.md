# Setja Operating Model

This document explains how Setja is meant to be used in a real project, not just how the code works.

## The intended workflow

Setja assumes a target project has two distinct realities:

1. the **shareable repo reality**
2. the **local working reality**

The shareable repo reality belongs in source, docs, and tracked context. The local working reality belongs in `workspace/` and is intentionally ignored by Git.

Setja gives you a disciplined way to move from the second into the first without treating them as the same thing.

## The core loop

### 1. Run Setja prepare

```bash
setja prepare --hexis=default --query="brief a new agent on this project"
```

This is the normal path. `setja prepare` will self-heal missing scaffold, rebuild guides, and print the injected context packet.

If folders or seed files are missing, Setja recreates them automatically. `setja init` still exists, but only as an optional explicit scaffold/debug command.

At this point, the target project has a place for:

- local research
- HTML prototypes
- screenshots
- scratch material
- curated agent-facing context
- Hexis profiles

### 2. Put raw material into `workspace/`

Examples:

- `workspace/research/competitor-notes.md`
- `workspace/html/landing-page.html`
- `workspace/screenshots/mobile-onboarding.png`

The important rule is that these are **inputs**, not the thing the agent should read directly.

### 3. Choose a Hexis profile

Examples in this repo:

- `default`
- `product`
- `debug`

A Hexis profile controls two different things:

- **selection** — what can enter the build
- **framing** — what the summarizer should emphasize

This means the same workspace can produce meaningfully different context packages depending on the task.

### 4. Build curated context

```bash
setja build --hexis=product
```

This creates or refreshes guide documents under `context/guides/`.

In practice, this is the step that converts “local working material” into “agent-usable project context.”

### 5. Inject for the current task

```bash
setja inject --hexis=product --query="prepare a PM handoff"
```

This prints a structured markdown envelope containing:

- baseline project context
- built guide summaries
- boosted deeper docs selected from `context/` via Hexis `boost`
- optional Rúnir recall, if configured

That final envelope is what an agent should be given for the task.

## What should live where

### `workspace/`
Use this for raw or provisional material:

- downloaded reference material
- prototype HTML
- screenshots
- notes that are not yet curated
- scratch experiments

### `context/`
Use this for durable, agent-facing project material:

- project overview
- system description
- architecture description
- decision records
- state snapshots
- built guide outputs

### `hexis/`
Use this for interpretive frames.

A good Hexis profile should answer:

- what files matter for this mode?
- what should be ignored?
- what does the summarizer need to emphasize?
- what deeper context docs should be boosted into local injection?

## How to think about Hexis in practice

Hexis is not just a folder filter.

It is the active frame that tells Setja how to interpret the workspace for a task.

A useful mental model is:

- **default** — balanced project understanding
- **product** — user value, clarity, tradeoffs, priorities
- **debug** — anomalies, constraints, failure signals, edge conditions

That is why Hexis metadata travels into the summarizer and, when enabled, into Rúnir capture/recall as well.

Boost targets also affect local injection directly. File boosts pull in exact docs; directory boosts expand eligible markdown files under that subtree; overlaps are deduped deterministically; and boosted additions are bounded so the prompt stays compact.

## Deterministic vs model-assisted operation

Setja should remain useful with no API key and no external model.

That is why `outline` exists as a deterministic local summarizer.

In real use, the recommended posture is **model-first**:

- prefer an **agent subprocess** when you want Setja to spawn the same local agent tooling/model family through a file-based CLI contract
- prefer a configured local or remote OpenAI-compatible endpoint
- use a vision-capable model for screenshots/images when available
- let deterministic `outline` mode serve as the fallback for tests, offline use, or missing endpoint configuration

The workflow should not collapse if no model is available, but frontier-model-backed summarization should be treated as the primary operating mode rather than an edge case.

## How Setja should be invoked by agents

Agents should treat Setja as the *only approved route* from raw project material into task context.

The correct pattern is:

1. `setja prepare --hexis=<name> --query="<task>"` for the normal one-command path
2. `setja build` / `setja inject` only when you want explicit control or debugging
3. reason over the injected envelope

The wrong pattern is:

- recursively reading `workspace/`
- reconstructing the build manually inside agent prompts
- treating the repo as if every file were equally useful

## When to use Rúnir

Use Setja alone when you need a clean, local context layer.

Add Rúnir when you want:

- cross-session continuity
- selective recall from prior work
- optional persistence of built context beyond the current project state

Even then, keep the responsibility split intact:

- Setja constructs the present context package
- Rúnir provides relevant prior memory

## Practical usage patterns

### Product review

```bash
setja build --hexis=product
setja inject --hexis=product --query="what matters for roadmap prioritization?"
```

### Debug review

```bash
setja build --hexis=debug
setja inject --hexis=debug --query="what looks risky or inconsistent?"
```

### General project briefing

```bash
setja prepare --hexis=default --query="brief a new agent on this project"
```

## Good operational habits

- keep `context/index.md` current
- use `workspace/` for real working material, not just leftovers
- keep Hexis profiles few and meaningful
- rerun `build` when the local working material changes materially
- avoid treating `context/guides/*` as hand-authored docs unless you intend to own them manually
