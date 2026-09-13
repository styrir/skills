---
name: session-eval
description: Ingest coding-agent session logs (Claude Code, Codex, Pi, Grok, Oh My Pi) and Styrir skill activations, run a code-first check catalog, and emit a self-contained HTML trend report. Use when tracking agent quality over time, auditing skills, reviewing session failures, or comparing harness runs without standing up Phoenix or any SaaS.
---

# Session Eval

First-party Styrir skill. Local files in, JSON receipts plus one HTML dossier out. No Phoenix server, no OTel collector, no cloud account.

Phoenix, Langfuse, Opik, Inspect, Harbor, and eval-dashboards informed the shape. This skill does not wrap them. License boundary: `references/license-boundary.md`.

## When to use

- "how are our agents doing"
- "track Styrir skills over time"
- "analyze this Claude/Codex/Pi/Grok/OMP session"
- "which skills fire, fail, or drift"
- "HTML report of sessions this week"

Do not use this to stand up Arize Phoenix, ship traces to a vendor, or score WorkGraph publication evidence (that remains `workgraph-eval-score`).

## Inputs

Infer from the machine when possible. State gaps instead of guessing.

| Input | Default |
|---|---|
| `HARNESSES` | All discovered of `claude`, `codex`, `pi`, `omp`, `grok`, `workgraph` |
| `SINCE` | Last 7 days by file mtime |
| `PATHS` | Canonical globs in `references/ingest-formats.md` |
| `SKILL_ROOTS` | `~/Code/skills`, `~/.claude/skills`, `~/.codex/skills`, `~/.grok/skills`, project `.claude/skills` |
| `CHECKS` | Catalog in `references/check-catalog.md` (deterministic on; LLM-judge off unless asked) |
| `OUT` | `.styrir/runs/<date>-session-eval/` under the repo being reviewed, else cwd |

Never dump raw prompts, tool arguments, credential pins, or terminal output into the HTML report. Redact by default; keep byte/line pointers into the source file.

## Workflow

1. **Discover.** Enumerate session files from `references/ingest-formats.md`. Record glob, count, oldest/newest mtime, parse errors. Missing harness = explicit gap, not a zero score.
2. **Ingest.** Stream JSONL/JSON. One adapter per harness. Normalize to the record below. Preserve unknown fields. Pair tool calls by id; cap unpaired as `tool.unpaired`.
3. **Skills.** Build a registry from `SKILL.md` frontmatter plus content digest. Join activations from Grok `prompt_context.json`, Claude skill paths, and tool-argument mentions (low confidence). Compare digest to previous snapshot.
4. **Check.** Run deterministic checks first (`references/check-catalog.md`). LLM judges are opt-in and must name model, rubric id, and evidence spans.
5. **Report.** Write `receipt.json` (machine) and `report.html` (human) per `references/report-contract.md`. Reuse workgraph-dossier rules: one self-contained HTML file, no CDN, no JS required, stable element ids, malformed events counted not dropped.
6. **Correct.** For each failing skill or recurring check, propose a concrete SKILL.md or adapter change. Do not edit third-party skills in `~/.omp/agent/skills` or `.omp/skills`. First-party fixes belong in `~/Code/skills`.

Until `scripts/` exist, run steps 1–6 with repo tools (Read/Grep/Glob) and write the two artifacts by hand from this contract. Do not call Phoenix CLI/`px setup`.

## Normalized record

Every ingested session becomes one run object. Adapters must fill these or set them `unknown` (never silent zero).

```text
run.id              harness + native session id
run.harness         claude | codex | pi | omp | grok | workgraph
run.source_path     absolute path of the primary stream
run.started_at
run.ended_at
run.cwd
run.model
run.tokens          {input, output, cache_read, cache_create, total, unknown}
run.cost_usd        number | unknown
run.skills[]        {name, path, digest, source, confidence}
run.turns[]         {id, role, tool_calls[], errors[], source_line}
run.checks[]        {id, status, kind, evidence}
```

`unknown` is distinct from `0`. Pi/OMP sampled logs often have no usage fields.

## Non-goals

- Do not vendor or host Phoenix (Elastic License 2.0; patents named in its `IP_NOTICE`).
- Do not require OpenTelemetry. Ingest JSONL first; optionally assemble an ATIF-shaped trajectory; OTel/OpenInference export is later and optional.
- Do not parse WorkGraph `stages/**/full.md` into the HTML report.
- Do not treat `~/.omc/sessions` or `.omo/evidence` as transcripts.
- Do not POST session contents anywhere.

## Related local tools

| Tool | Role |
|---|---|
| `~/Code/claude-dashboard` | Claude-only live UI + `sync_sessions.py` / `sync_skills.py` |
| `kolkov/ccdiag` (MIT) | Claude JSONL diagnostics; study, do not absorb as the skill |
| `simonw/claude-code-transcripts` (Apache-2.0) | Claude JSONL → static HTML pages; study pagination |
| `~/Code/agent-ops/bin/workgraph-dossier` | Self-contained HTML pattern for `.pipeline/<slug>` |
| `~/Code/agent-ops/bin/workgraph-eval-score` | Deterministic WorkGraph evidence replay, not harness transcripts |
| `~/Code/refs/observability/phoenix` | Reference clone only (ELv2) |

## References

- `references/ingest-formats.md` — harness path globs and fields
- `references/check-catalog.md` — checks, pass/fail, CODE vs LLM
- `references/report-contract.md` — HTML/JSON artifacts
- `references/license-boundary.md` — what we may copy vs reimplement
