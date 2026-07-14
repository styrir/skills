---
name: ask
description: Use when the user asks to consult another model — ask Codex, ask Claude, get a second opinion, model-to-model review, brainstorm with another model, or run a plan/build review gate — with realtime streamed progress instead of a black-box wait.
---

# Ask — unified, observable model consultation

One skill for consulting another model from either harness (Claude Code asking Codex, Codex asking Claude, or any registered provider). Every consultation streams: a raw JSONL trace you can `tail -f`, compact progress lines on stderr, and a final Markdown artifact. No silent redirects, no "it's working, wait and see."

## Invocation

Always go through the runner (it resolves defaults, preflight, adapters, artifacts):

```bash
<skill-dir>/scripts/ask.sh <provider> [-m model] [-d workdir] [-o outdir] [-b budget-usd] [--research] [--build] (-p prompt-file | "prompt text")
```

Examples:

```bash
scripts/ask.sh codex -p brief-review.md                      # Codex review, default model, streamed
scripts/ask.sh claude -b 5 "Second opinion on this plan: …"  # Claude advisor with budget cap
scripts/ask.sh codex -m gpt-5.6-terra -d ~/Code/gefa -o .pipeline/safelight/review -p build-review.md  # -m overrides the registry default
scripts/ask.sh claude --research -p build-review.md          # Reviewer may use bounded web/Context7 research
scripts/ask.sh grok -p brief-review.md                       # Grok review (read-only tools), streamed
scripts/ask.sh grok --build -d ~/Code/gefa -p build-brief.md # Grok as builder: write-enabled, auto-approved
```

While it runs: progress lines appear on stderr; the raw provider stream is at `<outdir>/trace.jsonl` (`tail -f` it from anywhere). The run ends by printing `artifact: <path>` and `summary: <path>`.

Every run also writes `<outdir>/summary.md` next to `artifact.md` — **orchestrators should read summary.md, not the full artifact** (token discipline directive 2026-07-10). Review passes get the `VERDICT:` line plus the numbered findings only; scout/build passes get the trailing JSON/JSONL summary records (or the last assistant paragraph), capped at 50 lines. It is derived from the same stream data as artifact.md — no extra model calls — and artifact.md remains the full record. Blocked runs write the blocker reason to summary.md as well.

## Providers and defaults

Defaults live in **`providers.json` — the single place to update as models improve or get deprecated.** Do not hardcode models in prompts or scripts.

| Provider | Default model | Tier | Route |
|---|---|---|---|
| claude | opus | stream-json | `claude -p --output-format stream-json` → `claude-stream-surface.ts` |
| codex | gpt-5.6-sol | stream-json | `codex exec --json` → `codex-stream-surface.ts` |
| grok | (grok CLI config default) | stream-json | `grok --prompt-file --output-format streaming-json` → `grok-stream-surface.ts` |
| gemini | (CLI default) | final-json | `omc ask gemini` fallback |
| antigravity / cursor | (CLI default) | text-tee | `omc ask <provider>` fallback |

Tiers: **stream-json** = realtime adapter (trace + progress + artifact); **final-json** = structured output only at the end; **text-tee** = no structured output, raw tee. A new provider starts at the lowest honest tier and earns an adapter (`scripts/<provider>-stream-surface.ts` built on `stream-core.ts`).

Codex specifics (verified 2026-07-09): GPT-5.6 ships as three tiers — **Sol** (flagship, the registry default), **Terra** (balanced), **Luna** (fast/cheap) — slugs `gpt-5.6-sol|terra|luna`. Sol requires codex CLI ≥ 0.144 and the runner passes `--disable multi_agent_v2` (its injected spawn_agent tool collides with Sol's reserved `collaboration.spawn_agent`; openai/codex#26753).

Grok specifics (grok CLI 0.2.93, verified 2026-07-09): the model default lives in the grok CLI config (grok-4.5 at verification time), so leave `-m` off to use it; the stream carries only `thought`/`text` token deltas plus `end` — tool calls do not surface, so progress is coarser than codex/claude; `-b` budget caps are not enforced (no CLI flag); auth is the cached `grok login` OAuth (preflight runs `grok models` and blocks with instructions if signed out). Review passes run with a read-only tool allowlist (`read_file,grep,list_dir`). `--research` cannot extend that allowlist — naming `web_search`/`web_fetch` under `--tools` pulls `run_terminal_cmd` into the toolset with `enabled_background=false` + `auto_background_on_timeout=true` and session creation fails its params constraint (grok 0.2.93) — so the research pass instead runs the default toolset with `--disallowed-tools` stripping shell/edit/subagent/interactive tools: same read-only file surface plus `web_search`/`web_fetch` (verified 2026-07-10). The `end` progress line includes the session id and a ready-made `grok -r <id>` resume command for follow-ups.

## Grok as builder (`--build`)

Grok is also wired as a **builder**, not just a reviewer: `--build` (alias `--write`) drops the read-only allowlist and runs grok's full default toolset with `--always-approve`, because headless runs cannot answer approval prompts. Same streaming surface: trace, progress, artifact, and a resumable session id.

```bash
scripts/ask.sh grok --build -d <repo> -o .pipeline/<topic>/build/<slice> -p build-brief.md
```

Builder-pass rules:

- `--build` is an explicit orchestrator routing decision per slice (record it in the build brief, like any builder-model choice); never the default for a consultation.
- `-d` is required — the runner blocks `--build` without an explicit workdir, since auto-approved writes land wherever it points. For risky or untrusted briefs, point `-d` at a disposable worktree.
- Review the resulting diff before it merges — the standard pipeline review gates still apply to grok-built slices.
- `--build` is grok-only for now; other providers block with a clear artifact rather than silently running write-enabled.
- `--research` is a review-pass option; in build mode its appendix is skipped (grok's default toolset already includes web tools).

## Optional reviewer research

Use `--research` or `--with-research-tools` only when current external evidence may change the review: dependency/API behavior, framework docs, provider limits, web-visible facts, or contradiction checks. The runner appends a research appendix to the saved prompt. For Claude, it also expands the review tool surface from local `Read/Grep/Glob/Bash` to include WebSearch, WebFetch, deferred MCP discovery, Context7, and Parallel Search MCP patterns. Codex gets the same prompt contract and should use configured tools/skills when available.

Research-enabled reviewers should still start from local files, prefer `$styrir-search` for bounded web research, use Context7 for current library/API/CLI/cloud docs, fetch/read sources before citing them, keep search budgets small, and report unavailable tools instead of inventing citations.

## Model pairing

- If Codex authored the work, ask Claude for the second opinion; if Claude authored it, ask Codex.
- For brainstorming rather than review, ask for options, tradeoffs, and questions instead of findings.
- Reusable prompt shapes: `references/review-prompts.md`.

## Pipeline integration (gefa/runir Canonical Execution Pipeline)

For brief and arch/code review gates, set `-o .pipeline/<topic>/review/<gate>` so review hops are tail-able exactly like scout and build hops. Ad-hoc consultations default to `.ask/<provider>-<slug>-<timestamp>/`.

## Guardrails

- Get explicit user approval before sending local files to an external provider; never pass secrets in prompts.
- Do not ask the consulted model to edit files during a review pass; ask for findings and concrete plan edits. Write-enabled runs go through `--build` only.
- Do not enable `--research` by default; it expands network-facing capability and should be an explicit reviewer choice.
- **Never claim a blocked run happened.** Auth/CLI failures produce a blocker artifact stating exactly what did not run and the next action (the runner does this automatically; relay its message).
- Do not change harness default-model settings to influence an advisor — consultation goes through this runner, never through settings mutation.
- Do not use dangerous bypass flags unless the user explicitly approves the risk.
- Relay the artifact path and key findings after every run.

## Relationship to other skills

- Supersedes `~/.codex/skills/ask-codex` (now a pointer here) and absorbs `claude-ask-direct`'s no-settings-mutation rule.
- `omc ask` remains the documented fallback route for providers without a streaming adapter; do not hand-assemble raw CLI flags for those providers.
- Replay a saved trace without re-running: `node --experimental-strip-types scripts/<adapter> --from-file <trace.jsonl> <artifact.md> [prompt.md]`.
