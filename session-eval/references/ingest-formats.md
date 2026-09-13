# Ingest formats

Observed 2026-09-13 on this machine. Sampled records, not a full dump. Treat schema drift as unknown fields, not parse failure.

Primary stream wins. Sidecars enrich. Never replace the stream with SQLite-only views.

Claude community parsers (study, do not become the skill): `kolkov/ccdiag` (MIT) and `simonw/claude-code-transcripts` (Apache-2.0).

Optional export: after pairing, assemble **one ATIF-shaped JSON document per session** (Harbor RFC 0001: `schema_version`, `agent{name,version}`, `steps[]`). Do not map each JSONL line to an ATIF root. Pin schema version. OTel/OpenInference projection is a later optional lane.


## Adapter table

| Harness | Glob | Format | Identity | Tokens | Skills | Existing parser |
|---|---|---|---|---|---|---|
| Claude Code | `~/.claude/projects/<encoded-project>/*.jsonl` | One JSON object per line | `sessionId`; filename stem is fallback | Assistant `message.usage.{input,output,cache_read_input,cache_creation_input}_tokens`; terminal `result.total_cost_usd` | Project `.claude/skills/**/SKILL.md`; mentions in tool args | `~/Code/claude-dashboard/scripts/sync_sessions.py`, `sync_skills.py` |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` | Envelope `timestamp`, `ordinal`, `type`, `payload` | `session_meta.payload.session_id` / `id` | `event_msg.token_count` and `token_usage_record` | Mostly textual/tool-arg mentions | Index: `~/.codex/session_index.jsonl`; DBs `state_5.sqlite`, `thread_history_1.sqlite` |
| Pi | `~/.pi/agent/sessions/<encoded-cwd>/*.jsonl` | Version-3 envelope | Initial `session.id` | Often absent in sampled files → `unknown` | Tool-arg / path mentions | None locally |
| Oh My Pi | `~/.omp/agent/sessions/<encoded-cwd>/*.jsonl` plus nested `<ts>_<id>/<agent>.jsonl` | Pi-shaped v3 + OMP custom events | Session id in path and `session.id` | Sidecar `agent.db` `usage_history` is quota, not per-session | Same as Pi | `agent.db.threads.rollout_path`; `history.db` titles |
| Grok Build | `~/.grok/sessions/<url-encoded-cwd>/<id>/` | Several JSONL + JSON files | `summary.json` `info.id` or older `session_info.id` | `usage.json` session/turn totals; `updates` `_meta.totalTokens` | `prompt_context.json` lists loaded skill files | `session_search.sqlite` |
| WorkGraph | `<repo>/.pipeline/<slug>/` | `run.yaml` + `events.jsonl` + stage handoffs | slug | not a chat transcript | bead/skill only if named in handoff | `workgraph-dossier`, `workgraph-eval-score` |

## Do not ingest as transcripts

| Path | What it is |
|---|---|
| `~/.claude/history.jsonl` | Prompt index (`display`, `sessionId`), not assistant/tool transcript |
| `~/.omc/sessions/*.json` | Orchestration metadata (`session_id`, `ended_at`, `reason`, agent counts) |
| `<repo>/.omo/evidence/**` | Evidence receipts, not conversation |
| `~/.grok/workflows/*.rhai` | Workflow source |
| WorkGraph `stages/**/full.md` | Worker evidence; exclude from HTML |

## Grok file set (per session dir)

- `chat_history.jsonl` — `type` in `system|user|assistant|reasoning|tool_result`; assistant `tool_calls`
- `events.jsonl` — ISO `ts`
- `updates.jsonl` — may use epoch seconds; session/update chunks, `tool_call`, `_meta.totalTokens`
- `summary.json` — accept both `info.*` and `session_info.*`
- `signals.json`
- `usage.json` — `sessionId`, `session.{inputTokens,outputTokens,cachedReadTokens,cacheCreationTokens,reasoningTokens,totalTokens,modelCalls,turnCount,primaryModelId,modelUsage}`, `turns[]`
- `prompt_context.json` — loaded skill files (highest-confidence skill join)

## Pairing rules

- Claude: `tool_use.id` ↔ user `tool_result.tool_use_id`; honor `is_error`
- Codex: `custom_tool_call.call_id` ↔ `custom_tool_call_output`
- Pi/OMP: `toolCall.id` ↔ `toolResult.toolCallId`; OMP also emits `customType: tool_execution_start`
- Grok: assistant `tool_calls[].id` ↔ `tool_result`
- Unpaired after stream end → check `tool.unpaired` (fail), not a dropped event

## Redaction

Default redact: user/assistant text, tool arguments/results, credential_pin hashes, system prompts, terminal output. Store `source_path` + line/ordinal + sha256 of the raw line if a check needs a later audit. HTML gets labels and counts, not payloads.
