# Ingest formats

[Canonical index](../docs/index.md) · [authoritative specification](../docs/specification.md) · [normalized record](../SKILL.md)

This is the adapter/reference contract for the portable shared local CLI at `../scripts/ingest.py`. Claude, Codex, Pi, Oh My Pi, and Grok are input formats, not mandatory execution hosts. OMP-native workflow and a Grok server are optional integrations, never prerequisites or alternate evaluator logic.

The Required `SE-PORT-001`, `SE-INGEST-001`, `SE-INGEST-002`, `SE-EVIDENCE-001`, `SE-PRIVACY-001`, `SE-USAGE-001`, and `SE-SKILL-001` rows in [the specification](../docs/specification.md) are the source of truth. This reference refines those rows and the normalized record in [SKILL.md](../SKILL.md); it cannot silently override them.

Observed 2026-09-13 on this machine. Sampled records, not a full dump. Treat schema drift as unknown fields, not parse failure. A requested but absent harness is an explicit coverage gap, not a zero; malformed records are counted and retained as parse evidence.

Primary stream wins. Sidecars enrich. Never replace the stream with SQLite-only views.

Claude community parsers (study, do not become the skill): `kolkov/ccdiag` (MIT) and `simonw/claude-code-transcripts` (Apache-2.0).

Optional export: after pairing, assemble **one ATIF-shaped JSON document per session** (Harbor RFC 0001: `schema_version`, `agent{name,version}`, `steps[]`). Do not map each JSONL line to an ATIF root. Pin schema version. OTel/OpenInference projection is a later optional lane. Implementation and pin status: [ATIF export](#atif-export-se-export-001).

## Adapter table

| Harness | Glob | Format | Native identity | Tokens | Skills | Existing parser |
|---|---|---|---|---|---|---|
| Claude Code | `~/.claude/projects/<encoded-project>/*.jsonl` | One JSON object per line | `sessionId`; filename stem is fallback | Assistant `message.usage.{input,output,cache_read_input,cache_creation_input}_tokens`; terminal `result.total_cost_usd` | Project `.claude/skills/**/SKILL.md`; mentions in tool args | `~/Code/claude-dashboard/scripts/sync_sessions.py`, `sync_skills.py` |
| Codex | `~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl` | Envelope `timestamp`, `ordinal`, `type`, `payload` | `session_meta.payload.session_id` / `id` | `event_msg.token_count` and `token_usage_record` | Mostly textual/tool-arg mentions | Index: `~/.codex/session_index.jsonl`; DBs `state_5.sqlite`, `thread_history_1.sqlite` |
| Pi | `~/.pi/agent/sessions/<encoded-cwd>/*.jsonl` | Version-3 envelope | Initial `session.id` | Often absent in sampled files → `unknown` | Tool-arg / path mentions | None locally |
| Oh My Pi | `~/.omp/agent/sessions/<encoded-cwd>/*.jsonl` plus nested `<ts>_<id>/<agent>.jsonl` | Pi-shaped v3 + OMP custom events | Session id in path and `session.id` | Sidecar `agent.db` `usage_history` is quota, not per-session | Same as Pi | `agent.db.threads.rollout_path`; `history.db` titles |
| Grok Build | `~/.grok/sessions/<url-encoded-cwd>/<id>/` | Several JSONL + JSON files | `summary.json` `info.id` or older `session_info.id` | `usage.json` session/turn totals; `updates` `_meta.totalTokens` | `prompt_context.json` lists loaded skill files | `session_search.sqlite` |
| WorkGraph | `<repo>/.pipeline/<slug>/` | `run.yaml` + `events.jsonl` + stage handoffs | slug | not a chat transcript | bead/skill only if named in handoff | `workgraph-dossier`, `workgraph-eval-score` |

The table's identity column is native identity only. A title, filename label, or history entry is a separate `run.display_name` and must never replace native identity. Pi-derived formats are feature-detected by envelope/version and event shape; do not assume Pi and OMP are identical.

## Adapter record and snapshots

Each adapter emits the normalized record defined in [SKILL.md](../SKILL.md), always supplying its own parser name/version and filling known historical source fields. Unavailable historical source fields or relationships are the literal `unknown`, never zero, an empty value, or a guessed fallback. In particular, every record carries:

- `run.parser` and `run.parser_version` with the adapter's own name and version (always present; `unknown` applies only to unavailable historical source fields);
- `run.source_path` for the absolute primary stream path;
- `run.source_snapshot` with an immutable `sha256` plus an ordered `files[]` list of every consumed primary and sidecar file, each with `path`, `role`, and content `sha256`;
- `run.native_identity` separate from presentation-only `run.display_name`;
- `run.lifecycle` with `state: terminal|live|unknown` and evidence objects containing `source_path`, `snapshot_hash`, `parser_version`, `event_range: {start_line, end_line}`, `kind`, and `evidence_hash`, plus `run.lineage` links for observed parent/child, attempt, and continuation relationships; and
- `run.usage_provenance[]` naming direct, aggregate, or sidecar origin with source range, record identity, and evidence hash.

The snapshot hash is computed from the ordered path/role/content-hash list, not from a display name or mtime. Repeating ingest with an identical consumed manifest (the same paths, roles, and bytes) retains the same native and snapshot identities. A path/role rename is a changed manifest and creates a new snapshot even when bytes remain identical; changed bytes likewise create a new snapshot even when the native session id is unchanged. The new receipt is immutable and must not overwrite the prior receipt in history. A source path is an evidence pointer, not a snapshot identity.

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

## Lifecycle, lineage, and pairing

Preserve source event order and record evidence ranges for lifecycle decisions. `run.lifecycle.state=terminal` requires an explicit terminal result, `task_complete`, or authoritative ended metadata. An explicit live marker yields `live`; an ended file with no terminal marker remains `unknown`. **EOF or file closure is not terminal.** Do not infer completion, parentage, attempts, or continuations from missing records, filenames, ordinals, or EOF. Every unestablished relationship is explicitly `unknown`; an observed relationship may be recorded under `run.lineage` or nested `turns[].lineage`, whose parent/children/attempt/continuation fields each preserve that explicit unknown. Every evidence object retains its source path, line/event range, kind, and evidence hash.

Pairing rules:

- Claude: `tool_use.id` ↔ user `tool_result.tool_use_id`; honor `is_error`
- Codex: `custom_tool_call.call_id` ↔ `custom_tool_call_output`
- Pi/OMP: `toolCall.id` ↔ `toolResult.toolCallId`; OMP also emits `customType: tool_execution_start`
- Grok: assistant `tool_calls[].id` ↔ `tool_result`
- An unpaired call after an explicitly terminal stream → `tool.unpaired` (fail), not a dropped event. A file ending at EOF without terminal evidence remains live/unknown per lifecycle evidence; preserve the pending call and do not turn EOF alone into a terminal failure.

## Usage and sidecar enrichment

Usage and cost are evidence-bound. A missing field is `unknown`, never zero. Record `run.usage_provenance[]` for every known value, including whether it came from a primary event, aggregate record, or sidecar. Overlapping views of a stream and repeated aggregate usage records are deduplicated by stable source identity plus source record/field/range; they are not added twice. OMP `agent.db` `usage_history` is quota/account evidence, not per-session usage, unless a future adapter can prove the narrower scope.

## Skill joins and redaction

The skill registry records skill identity, path, content digest, and optional version. Activation evidence records source and confidence: Grok `prompt_context.json` and an explicit loaded path are stronger than a textual/tool-argument mention. A historical loaded digest is distinct from the current on-disk digest; never attribute current content to a past load without activation evidence. Missing or edited skills remain explicit evidence gaps.

Unknown historical source fields (fields not recognized by the parser) may be retained in private source/normalized state for future adapter upgrades, but raw unknown values are not exported. Redact before serializing receipts or HTML: user/assistant text, tool arguments/results, `credential_pin` hashes, system prompts, terminal output, secrets, and any other sensitive payload. Store `source_path` plus line/ordinal/event range and sha256 of the raw line only when a check needs later audit. HTML gets escaped labels, structural links, and counts, not payloads. Do not POST raw session contents anywhere. Opt-in judges follow the `references/judge-contract.md` contract ([link](judge-contract.md)) and may receive only explicitly authorized redacted evidence references; provider disclosure requires explicit scope and recipient approval. Do not mutate source files.

## ATIF export (SE-EXPORT-001)

Status: implemented by the standalone exporter `../scripts/atif.py`. This is optional after ingest; it is not a core completion blocker and does not require Phoenix, OpenTelemetry, or a Harbor runtime.

Pinned upstream schema: Harbor ATIF-v1.8 at commit `88fdbc9d42e907c0414654f041ece5eaf798f538`. RFC: `rfcs/0001-trajectory-format.md`. Reference models: `src/harbor/models/trajectories/`. License: Apache-2.0 (`LICENSE` at that commit). The independent JSON Schema and provenance live at `../schemas/atif-v1.8.schema.json` and `../schemas/atif-v1.8.provenance.json`. Harbor Python sources are not vendored.

Contract:

- One redacted ATIF document per normalized `styrir-session-eval/v0` run. Downstream modules consume the ingest receipt; this exporter does not invent a second session schema.
- Preserve source chronology (`steps[].step_id` sequential from 1 in ingest turn order), native identity (`session_id` / `extra.source.native_identity`), observed lineage (`extra.lineage`), and paired `tool_calls[].tool_call_id` ↔ `observation.results[].source_call_id` structure.
- `agent.name` is the harness; `agent.version` is the ingest parser version, never a SKILL.md semver.
- Known usage/cost is copied into `final_metrics` only when numeric. Harbor `total_prompt_tokens` is all prompt tokens including cached: emit it only when `input`, `cache_read`, and `cache_create` are all known, summing those disjoint receipt fields, or using `input` alone when a harness total already includes cache (`total == input + output` and cache is a nonempty subset of input). If any prompt-side component is unknown, omit `total_prompt_tokens` rather than treating `input` as the Harbor total. `total_cached_tokens` is cache hits (`cache_read`) only. Unknown metrics are omitted and recorded under `final_metrics.extra.token_coverage` / `prompt_token_basis` / `extra.unknowns`; they are never zeroed.
- Message text, tool arguments, and observation content are omitted. `message` is the empty string required by ATIF; `arguments` is `{}`; result `content` is absent. Each omission is marked in `extra.redaction`.
- Repeat export of an unchanged receipt reuses the immutable writer and does not rewrite history.

Public API:

- `to_atif(run) -> dict`
- `export_atif(receipt, out) -> (documents, manifest_path)`
- `validate_atif(document) -> list[str]` (pinned official constraints; empty means pass)
- `validate_with_harbor(document, harbor_src=None)` (optional official Pydantic `Trajectory` when a Harbor checkout at the pin is supplied)
- CLI: `python3 session-eval/scripts/atif.py --receipt receipt.json --out DIR [--validate] [--harbor-src HARBOR_CHECKOUT]`

Parent-runnable official validation:

```bash
python3 session-eval/scripts/atif.py --receipt receipt.json --out DIR --validate
HARBOR_SRC=/path/to/harbor@88fdbc9d42e907c0414654f041ece5eaf798f538 \
  python3 session-eval/scripts/atif.py --receipt receipt.json --out DIR --validate --harbor-src "$HARBOR_SRC"
python3 session-eval/scripts/smoke_atif.py
```

The smoke exercises Claude and Grok synthetic samples through ingest then export. It fails if raw synthetic secrets/markup appear, if unknown metrics become zero, if step ids are unordered, or if a second export changes history.
