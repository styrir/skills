# Setja

Setja is a TypeScript-first context construction and injection layer for AI agents.

It is designed as a **CLI-first runtime** with thin skill and adapter layers on top.

It turns raw, local project artifacts into small, curated context that agents can use safely and consistently.

```text
workspace -> Setja build -> context -> Setja inject -> agent
                           \-> optional Rúnir capture/recall
```

Setja is intentionally **not** a memory system. It shapes what matters **now**. If you want cross-session persistence and recall, Setja can optionally talk to Rúnir through a narrow adapter boundary.

## TL;DR

Most users only need this:

```bash
npm link
setja prepare --product "summarize what matters for a PM handoff"
```

`setja prepare` will bootstrap any missing Setja scaffold automatically. `setja init` still exists, but it is now an optional explicit scaffold/debug command instead of a required first step.

If `codex` is already installed and on your `PATH`, Setja's default `auto` mode can use it automatically for model-backed summarization. You do **not** need extra environment variables for the common path.

If `setja` is not found on your shell `PATH`, run:

```bash
npm link
```

from the Setja repo first.

## What this repo gives you

- a CLI for `init`, `build`, `inject`, and `prepare`
- a Hexis-aware build path that decides what to include and emphasize
- a pluggable summarization layer with deterministic and OpenAI-compatible modes
- a screenshot/image pipeline that can stay local or use a vision-capable model
- an optional Rúnir adapter that enriches injection without making Rúnir a hard dependency
- thin adapters for Codex, Claude Code, and Emdash

The CLI is the canonical execution surface. Skills and environment adapters should stay as thin invocation layers that run the CLI instead of re-implementing Setja behavior.

For normal usage, Setja is optimized around **model-backed summarization**. The recommended default is:

1. **agent-subprocess** when you want Setja to spawn the same local agent tooling/model family via a CLI contract
2. **local vision-capable or remote OpenAI-compatible endpoint**
3. `outline` as a resilient fallback for tests and no-endpoint operation

## Quick start

### Install the CLI

```bash
npm install
npm run build
npm link
```

That makes `setja` available globally on your machine.

If you skip `npm link`, commands like `setja init` will fail with `command not found`.

### Initialize a target project

Inside the target repo:

```bash
setja init
```

### Put local artifacts under `workspace/`

Typical inputs:

- `workspace/research/*.md`
- `workspace/html/*.html`
- `workspace/screenshots/*`

### Generate the current-task context package

Shortest useful commands:

```bash
setja prepare
setja prepare --product
setja prepare --product "summarize what matters for a PM handoff"
setja inject --debug "what looks risky or inconsistent?"
```

Use the long form only when you want it:

```bash
setja build --hexis=product
setja inject --hexis=product --query="summarize what matters for a PM handoff"
```

## Read these first

- [`docs/vision.md`](docs/vision.md) — what Setja is for, where it fits, and what success looks like
- [`docs/architecture.md`](docs/architecture.md) — actual module layout, data flow, and extension points
- [`docs/operating-model.md`](docs/operating-model.md) — how Setja is meant to be used in a real project
- [`docs/runir-integration.md`](docs/runir-integration.md) — the clean boundary between Setja and Rúnir

## What Setja is not

- not a vector store
- not a knowledge graph
- not a long-term memory database
- not a replacement for Rúnir
- not a generic repo crawler

## Commands

```bash
setja init
setja build --hexis=default
setja inject --hexis=product --query="review the UI architecture"
setja prepare --hexis=product --query="build a launch plan"
```

`prepare` runs `build` and then `inject`.

### Ergonomic shorthands

These are supported and recommended:

```bash
setja build --product
setja inject --debug "what looks risky or inconsistent?"
setja prepare --product "summarize what matters for a PM handoff"
```

Shorthand behavior:

- `--product` → `--hexis=product`
- `--debug` → `--hexis=debug`
- `--default` → `--hexis=default`
- positional trailing text on `inject` / `prepare` becomes the task query

## Typical target-project layout

```text
context/
  index.md
  system.md
  architecture.md
  decisions/
  state/
  guides/

workspace/           # ignored by git
  assets/
  html/
  research/
  screenshots/
  scratch/

hexis/
  default.yaml
  product.yaml
  debug.yaml
```

## Configuration

Create a `.env` in either the Setja repo or the target project. See `.env.example` for the full list.

### Summarization

- `SETJA_SUMMARIZER=auto` to prefer a configured agent subprocess backend first, then a configured local/remote OpenAI-compatible model, and finally fall back to `outline`
- `SETJA_SUMMARIZER=agent-subprocess` to require a subprocess-backed agent summarizer
- `SETJA_SUMMARIZER=openai-compatible` to require an OpenAI-compatible chat/vision endpoint
- `SETJA_SUMMARIZER=outline` for deterministic local summaries when you explicitly want the fallback path
- `SETJA_LLM_BASE_URL`
- `SETJA_LLM_API_KEY`
- `SETJA_LLM_MODEL`
- `SETJA_VISION_MODEL` (optional override for screenshot/image summaries)
- `SETJA_AGENT_BACKEND=codex` to spawn Codex non-interactively as a summarizer subprocess using JSON artifact files
- `SETJA_AGENT_MODEL` (optional override for the spawned subprocess model)

### Sensible defaults

Setja now defaults to:

- `SETJA_SUMMARIZER=auto`

In `auto` mode, Setja prefers:

1. a configured **agent subprocess** backend
2. a configured **OpenAI-compatible** endpoint
3. `outline` fallback

If `codex` is installed and available on `PATH`, `auto` can infer the Codex subprocess backend without extra configuration.

### Recommended model-first setup

#### 1. Zero-config common path

If `codex` is installed and on `PATH`, you can often use Setja with no extra summarizer config at all:

```bash
setja prepare --product "summarize what matters for a PM handoff"
```

#### 2. Explicit Codex subprocess mode

If you want Setja to use the same local agent tooling that invoked the skill/session, pin the subprocess mode:

```bash
SETJA_SUMMARIZER=auto
SETJA_AGENT_BACKEND=codex
SETJA_AGENT_MODEL=gpt-5.4
```

Setja will write JSON request/schema artifacts, spawn `codex exec` in a narrow read-only subprocess contract, and read back structured JSON output.

#### 3. OpenAI-compatible local or remote endpoint

If you routinely work with frontier models, point Setja at a **local vision-capable endpoint** or remote OpenAI-compatible endpoint:

```bash
SETJA_SUMMARIZER=auto
SETJA_LLM_BASE_URL=http://localhost:1234/v1
SETJA_LLM_MODEL=your-best-local-or-proxied-model
SETJA_VISION_MODEL=your-best-local-or-proxied-vision-model
```

That keeps the CLI environment-agnostic while still making image understanding and stronger synthesis the normal operating mode. `outline` remains the fallback for tests, offline use, and no-endpoint situations.

### Force a specific mode

```bash
SETJA_SUMMARIZER=agent-subprocess
SETJA_SUMMARIZER=openai-compatible
SETJA_SUMMARIZER=outline
```

Use forced modes when debugging config, testing fallback behavior, or pinning a deployment environment.

### Optional Rúnir integration

- `SETJA_RUNIR_ENABLED=true`
- `SETJA_RUNIR_BASE_URL=http://localhost:3000`
- `SETJA_RUNIR_CAPTURE_PATH=/hooks/capture`
- `SETJA_RUNIR_RECALL_PATH=/hooks/recall`
- `SETJA_RUNIR_API_KEY=...` (optional)

## Agent adapters

- [`skills/setja/SKILL.md`](skills/setja/SKILL.md)
- [`adapters/codex.md`](adapters/codex.md)
- [`adapters/claude.md`](adapters/claude.md)
- [`adapters/emdash.yaml`](adapters/emdash.yaml)

These adapters exist for ergonomics. They should run the CLI, not fork the runtime logic.

## Bundled skill

This repo includes a portable Codex-native bundled skill:

- `skills/setja/SKILL.md`
- `skills/setja/references/usage.md`

It is intentionally implemented with **progressive disclosure**:

- `SKILL.md` stays small for discovery/loading
- detailed rules live under `references/`

For project-local Codex discovery in this repo, the same skill is mirrored under:

- `.codex/skills/setja/SKILL.md`

If you zip or ship this repo elsewhere, the important portable skill bundle is:

- `skills/setja/`

## Example flow

Inside a target project:

```bash
# add local artifacts under workspace/
setja prepare --hexis=product --query="summarize what matters for a PM handoff"
```

`setja prepare` self-heals missing `context/`, `workspace/`, and `hexis/` scaffold files before it builds and injects. Reach for `setja init` only when you want to seed the scaffold explicitly without running the rest of the flow.

Shorter equivalents:

```bash
setja prepare
setja prepare --product
setja prepare --product "summarize what matters for a PM handoff"
setja inject --debug "what looks risky or inconsistent?"
```

## Design choice: TypeScript-only core

The core repo is TypeScript-only on purpose.

That keeps Setja portable across Codex, Claude Code, and Emdash, and keeps the logic in one place. If you later need notebooks, training, or experimental CV work, use the reserved `experiments/` lane instead of pulling Python into the core.
