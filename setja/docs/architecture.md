# Setja Architecture

This document describes the repo as it exists today, not as a hypothetical future framework.

## Top-level structure

```text
src/
  bin/
  core/
  pipeline/
  adapters/

skills/
adapters/
templates/
example-project/
experiments/
```

## Architectural layers

### 1. CLI surface

**File:** `src/bin/setja.ts`

The CLI is intentionally small. It translates command-line intent into calls on the core execution functions:

- `init`
- `build`
- `inject`
- `prepare`

`prepare` ensures the scaffold exists, then runs `build` followed by `inject`.

The CLI should stay thin. It is not the right place for summarization, filtering, or memory logic.

### 2. Core execution layer

**Files:**
- `src/core/init.ts`
- `src/core/build.ts`
- `src/core/inject.ts`
- `src/core/context.ts`
- `src/core/hexis.ts`
- `src/core/config.ts`
- `src/core/hooks.ts`
- `src/core/types.ts`
- `src/core/fs.ts`

This is the real heart of Setja.

#### `init.ts`
Creates the working shape inside a target project:

- `context/`
- `workspace/`
- `hexis/`

and seeds starter context and Hexis files.

The same scaffold creation logic is also reused by `prepare`, so first-run usage no longer depends on a separate mandatory `init` step.

#### `build.ts`
Runs the context construction phase.

Responsibilities:

- load the selected Hexis profile
- discover relevant files under `workspace/`
- filter them through Hexis include/ignore rules
- send each artifact family through the appropriate pipeline
- write summarized results into `context/guides/*.md`
- trigger optional hooks and optional Rúnir capture

Artifact families currently supported:

- research files
- HTML files
- screenshot/image files

#### `inject.ts`
Builds the final agent-facing envelope.

Responsibilities:

- load the baseline context docs (`context/index.md`, `system.md`, `architecture.md`)
- include generated guide outputs under `context/guides/` when present
- include boosted deeper context docs using Hexis `boost` targets
- dedupe overlapping selections deterministically
- cap boosted additions to a bounded number of whole docs
- optionally request relevant recall from Rúnir
- emit a single structured markdown payload for the agent

#### `context.ts`
Contains the logic for:

- writing summary files
- loading core context files
- building the final injection envelope

This file is central because it defines the shape of what the agent actually sees.

It now also contains the selection/composition logic that merges baseline docs, generated guides, and Hexis-boosted deeper docs into one deterministic injection set.

#### `hexis.ts`
Loads Hexis YAML profiles and applies include/ignore filtering.

Today, Hexis does two important things:

- controls what can enter the build
- provides framing metadata (`summary_style`, `focus`, `boost`) used by the summarization layer and downstream injection

`boost` is interpreted locally as ordered inclusion hints: files include that exact document, directories expand to eligible markdown docs, and overlaps are resolved by first-win merge order plus lexical path order within each target.

This is the first version of Hexis, but it already provides the key boundary: build behavior should be parameterized by a profile, not hard-coded to a single project stance.

#### `config.ts`
Resolves environment variables into a typed runtime config.

This centralizes all external dependencies:

- summarizer mode
- LLM endpoint settings
- vision model override
- Rúnir settings

#### `hooks.ts`
A lightweight extension surface for lifecycle hooks.

Current stages:

- `afterBuild`
- `beforeInject`

This is the right place for custom local behavior without baking all extensions into the core.

### 3. Pipeline layer

**Files:**
- `src/pipeline/research-summary.ts`
- `src/pipeline/html-to-md.ts`
- `src/pipeline/image-analysis.ts`
- `src/pipeline/llm-summary.ts`

The pipeline layer transforms raw artifacts into summary text suitable for `context/guides/*`.

#### `research-summary.ts`
Summarizes research notes and text-like files.

#### `html-to-md.ts`
Summarizes HTML artifacts into a form usable by an agent.

This is intentionally not a full visual layout engine. It is the current context-extraction path for HTML inputs.

#### `image-analysis.ts`
Produces summaries for screenshots and images.

This can operate in a metadata-only mode or call a vision-capable model through the pluggable summarizer surface.

#### `llm-summary.ts`
Defines the summarization abstraction.

Two modes currently exist:

- `outline` — deterministic local summarization
- `openai-compatible` — calls a configured chat/vision endpoint

This file is important because it keeps “how we summarize” behind a stable interface instead of scattering model calls across the repo.

### 4. External adapters

**Files:**
- `src/adapters/runir.ts`
- `skills/setja.md`
- `adapters/codex.md`
- `adapters/claude.md`
- `adapters/emdash.yaml`

#### `src/adapters/runir.ts`
This is the only place where the core repo knows how to talk to Rúnir.

It exposes two narrow operations:

- capture built context after `build`
- recall relevant memory before `inject`

This narrow adapter is the main architectural safeguard that prevents Setja from drifting into “half a memory system.”

#### Skill + environment adapters
The canonical skill lives in `skills/setja.md`.

Environment-specific files describe when and how Codex, Claude Code, and Emdash should invoke Setja. They should remain thin, because the real logic belongs in the CLI and core runtime.

## End-to-end data flow

```text
workspace/*
  -> file discovery
  -> Hexis filtering
  -> pipeline summarization
  -> context/guides/*.md
  -> optional Rúnir capture
  -> injection envelope assembly
  -> optional Rúnir recall enrichment
  -> agent-facing markdown payload
```

## Why the architecture is shaped this way

There are three deliberate separations here:

### Raw vs curated
Setja never asks the agent to consume `workspace/` directly. The build phase exists specifically to turn raw material into something more stable and legible.

### Context vs memory
Setja owns the current-task package. Rúnir owns recall across time. Mixing those concerns would make both systems harder to reason about.

### Spec vs environment adapter
The logic should not be reimplemented differently in Codex, Claude Code, and Emdash. The same Setja runtime should sit underneath all of them.

## Extension points that make sense

The highest-value extension points are:

1. **Hexis sophistication**
   richer inclusion rules, ranking, and stance selection

2. **Pipeline quality**
   better HTML understanding, layout-awareness, stronger image interpretation

3. **Injection shaping**
   tighter control over envelope size and prioritization

4. **Rúnir adapter contract**
   a more explicit capture/recall schema once the target hooks stabilize

## Extensions that should be resisted

These are the likely ways to make Setja messy:

- embedding a full memory policy inside Setja
- letting environment adapters grow their own logic forks
- turning `inject` into a repo crawler
- mixing experimental Python pipelines into the core runtime
