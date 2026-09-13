---
name: session-eval
description: Portable contract for ingesting coding-agent session logs (Claude Code, Codex, Pi, Grok, Oh My Pi), tracking Styrir skill activations, running a code-first check catalog, and eventually emitting a self-contained HTML trend report without standing up Phoenix or any SaaS.
---

# Session Eval

Intended first-party Styrir skill. Local files in, redacted JSON receipts plus one self-contained HTML dossier out through a shared local CLI; no Phoenix server, no OTel collector, no cloud account, and no OMP-native workflow or Grok server prerequisite.

The portable ingest implementation is `python3 session-eval/scripts/ingest.py`. It is stdlib-only, reads explicit local `--path` inputs (or the documented host roots), accepts repeatable `--harness` filters and `--since`, and writes the normalized `styrir-session-eval/v0` receipt under `--out` (default `.styrir/runs/<date>-session-eval`). Ingest emits no report, evaluator, judge, ATIF, or history artifacts; downstream stages consume the same receipt.

[Canonical index](docs/index.md) · [authoritative specification](docs/specification.md)

Phoenix, Langfuse, Opik, Inspect, Harbor, and eval-dashboards informed the shape. This skill does not wrap them. License boundary: `references/license-boundary.md`.

## When to use

- "how are our agents doing"
- "track Styrir skills over time"
- "analyze this Claude/Codex/Pi/Grok/OMP session"
- "which skills fire, fail, or drift"
- "HTML report of sessions this week"

Do not use this to stand up Arize Phoenix, ship traces to a vendor, or score WorkGraph publication evidence (that remains `workgraph-eval-score`).

## Portable implementation interface

Run the shared local ingest command from the skills repository (or pass absolute paths):

```bash
python3 session-eval/scripts/ingest.py \
  --harness claude --path /path/to/session.jsonl \
  --out /path/to/output
```

Repeat `--harness`/`--path` as needed, or omit both to use the canonical discovery roots and all five adapters. `--since` defaults to the last seven days by file mtime; pass `--since all` for an explicitly bounded historical fixture. The command never requires OMP native workflow or a Grok server and records missing requested harnesses as coverage gaps.

The CLI accepts local session paths or a time window, harness filters, skill roots, and an output root. It reads primary streams directly, enriches them with sidecars, and emits the redacted `styrir-session-eval/v0` `receipt.json` described by `references/report-contract.md`; report, checks, judges, and history remain downstream stages. The executable is intentionally a small stdlib entry point so optional host integrations invoke this same interface rather than implementing a second evaluator.

The portable path is an ordinary terminal invocation on local files. A missing requested harness is a coverage gap; a missing implementation dependency fails explicitly. OMP-native workflow and Grok server integrations are optional conveniences that may invoke this same interface, never prerequisites or alternate evaluator logic.

## Inputs

| Input | Default |
|---|---|
| `HARNESSES` | All discovered of `claude`, `codex`, `pi`, `omp`, `grok`, `workgraph` |
| `SINCE` | Last 7 days by file mtime |
| `PATHS` | Canonical globs in `references/ingest-formats.md` |
| `SKILL_ROOTS` | First-party root `~/Code/skills` plus `~/.claude/skills`, `~/.codex/skills`, `~/.pi/agent/skills`, `~/.omp/agent/skills`, `~/.grok/skills`, and project `.claude/skills`, `.pi/skills`, and `.omp/skills` when present |
| `CHECKS` | Catalog in `references/check-catalog.md` (deterministic on; LLM-judge off unless asked) |
| `OUT` | `.styrir/runs/<date>-session-eval/` under the repo being reviewed, else cwd |

The first-party root in `SKILL_ROOTS` defaults to `~/Code/skills` and is configurable. Host-specific roots are discovery inputs, not proof that a skill was loaded.

## Workflow

1. **Discover.** Enumerate session files from `references/ingest-formats.md`. Record glob, count, oldest/newest mtime, parse errors, native identity, and an immutable source snapshot. Missing harness = explicit gap, not a zero score.
2. **Ingest.** Stream JSONL/JSON. One adapter per harness. Normalize to the record below, including parser/version, lifecycle evidence, lineage, and usage provenance. Preserve unknown fields privately. Pair tool calls by id; classify unpaired as `tool.unpaired`; EOF alone is never terminal.
3. **Skills.** Build a registry from `SKILL.md` frontmatter plus content digest. Join activations from Grok `prompt_context.json`, Claude skill paths, and tool-argument mentions (low confidence). Compare digest to previous snapshot; historical loaded digest is distinct from the current on-disk digest.
4. **Check.** Run deterministic checks first (`references/check-catalog.md`). LLM judges are opt-in under [`references/judge-contract.md`](references/judge-contract.md) and must name model, rubric id, and evidence spans; only explicitly authorized redacted evidence references may be supplied.
5. **Report.** Write immutable `receipt.json` (machine) and `report.html` (human) per `references/report-contract.md`. Reuse workgraph-dossier rules: one self-contained HTML file, no CDN, no JS required, stable element ids, malformed events counted not dropped. Keep prior receipts in history; never overwrite a receipt for a changed source snapshot.
6. **Correct.** For each failing skill or recurring check, propose a concrete SKILL.md or adapter change. Do not edit third-party skills in `~/.omp/agent/skills` or `.omp/skills`. First-party fixes belong in `~/Code/skills`.

Implementation is present at `session-eval/scripts/ingest.py`; until downstream checks and rendering exist, manual source inspection with repo tools (Read/Grep/Glob) and the ingest CLI's redacted receipt are not conformance evidence for those later requirements.

## Normalized record

Every ingested session becomes one run object. This is the intended record contract; adapters must always fill their own parser name/version and known values, and set unavailable historical source fields or relationships to the literal `unknown` (never silent zero or an omitted relationship). The Required `SE-PORT-001`, `SE-INGEST-001`, `SE-INGEST-002`, `SE-EVIDENCE-001`, `SE-PRIVACY-001`, `SE-USAGE-001`, and `SE-SKILL-001` rows in `docs/specification.md` are the source of truth; this entry and the ingest reference refine, not replace, them.

```text
run.id                  stable local identity: harness + native identity; fallback source stem only when native id is absent
run.harness             claude | codex | pi | omp | grok | workgraph
run.native_identity     {id, kind, source} | unknown
run.display_name        source-provided title/label for humans | unknown
run.parser              adapter-owned parser name (always present)
run.parser_version      adapter-owned parser version (always present)
run.source_path         absolute path of the primary stream
run.source_snapshot     {sha256, files[]}
  files[]               {path, role: primary|sidecar, sha256}
run.started_at
run.ended_at
run.cwd
run.model
run.tokens              {input, output, cache_read, cache_create, total, unknown}
run.cost_usd            number | unknown
run.usage_provenance[]  {source_path, line_or_event_range, field, kind, record_identity, evidence_hash}
run.skills[]            {name, path, digest, source, confidence}
run.lineage              {parent: ref|unknown, children: ref[]|unknown, attempt: {id, number}|unknown, continuation_of: ref|unknown, continued_by: ref[]|unknown}
run.turns[]             {id, role, tool_calls[], errors[], source_line, lineage}
run.checks[]            {id, status, kind, class, channel, observed, error, evidence[] {source_path, snapshot_hash, parser_version, event_range: {start_line, end_line}, evidence_hash}}
run.lifecycle            {state: terminal|live|unknown, evidence[] {source_path, snapshot_hash, parser_version, event_range: {start_line, end_line}, kind, evidence_hash}}
```

`unknown` is distinct from `0`, `[]`, and a missing value. An empty relationship list means the adapter observed no related records; `unknown` means it could not establish the relationship. Pi/OMP sampled logs often have no usage fields, and usage/cost remain unknown rather than zero.

`run.source_snapshot` is immutable. Its `sha256` is computed from the ordered list of every primary and sidecar file used, with each file's path, role, and content hash recorded in `files[]`. Repeating ingest with an identical consumed manifest (the same paths, roles, and bytes) retains the same native identity and snapshot identity. A path/role rename is a changed manifest and creates a new snapshot even when bytes remain identical; changed bytes likewise create a new snapshot, even when the native session id is unchanged. The new receipt must not overwrite the former receipt.

`run.native_identity` is harness-provided identity, never a human title or display label. `run.display_name` is presentation-only and may come from a title sidecar, filename, or fallback label. `run.lineage` and each nested `turns[].lineage` record only observed parent/child, attempt, and continuation links; each unknown link stays explicitly `unknown`, and adapters must never invent lineage.

`run.lifecycle.state=terminal` requires explicit terminal evidence (for example a terminal result, `task_complete`, or authoritative ended metadata). An explicitly live stream is `live`; an ended file with no terminal marker is `unknown`. EOF or file closure alone is not terminal. Lifecycle and every check retain source path plus line/event ranges and hashes so evidence is auditable without exporting payloads.

`run.usage_provenance[]` identifies whether a value came directly from the primary stream, an aggregate record, or a sidecar and carries the source range/record identity and evidence hash. Overlapping streams and repeated aggregate usage records are deduplicated by stable source identity and field/range rather than added twice; quota/account sidecars are not silently treated as per-session usage.

The private normalized/source representation may retain unknown historical source fields (fields not recognized by the parser) for later adapter upgrades; parser name/version remain adapter-owned and present. Exported receipts and HTML remain redacted: no raw prompts, tool payloads, secrets, terminal output, or unknown raw values; preserve only approved structural fields, pointers, counts, and hashes.

## Non-goals

- Do not vendor or host Phoenix (Elastic License 2.0; patents named in its `IP_NOTICE`).
- Do not require OpenTelemetry. Ingest JSONL first; optionally assemble an ATIF-shaped trajectory; OTel/OpenInference export is later and optional.
- Do not parse WorkGraph `stages/**/full.md` into the HTML report.
- Do not treat `~/.omc/sessions` or `.omo/evidence` as transcripts.
- Do not POST raw session contents anywhere. Opt-in judges follow [`references/judge-contract.md`](references/judge-contract.md) and may receive only explicitly authorized redacted evidence references; provider disclosure requires explicit scope and recipient approval.

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
- `references/judge-contract.md` — opt-in judges and redacted evidence references
- `references/license-boundary.md` — what we may copy vs reimplement
- `docs/index.md` — canonical document store and authority
- `docs/specification.md` — normative requirements and acceptance scenarios
