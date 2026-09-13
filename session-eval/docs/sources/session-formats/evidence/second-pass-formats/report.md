## Evidence and borrow list

| Name | License evidence | Input format | Output / server dependency | Borrowable surface |
|---|---|---|---|---|
| Harbor ATIF RFC + validator [s1][s2] | Harbor repository LICENSE is Apache-2.0 [s2] | One JSON ATIF trajectory document; RFC reference implementation accepts a dict, JSON string, or file path [s1] | Pydantic models validate and serialize trajectories; no Phoenix or OTel collector is part of the validator path (implication of the file/path API) [s1] | Canonical root/step/tool/observation/metrics schema; `schema_version`, `agent.name/version`, `trajectory_id`, embedded subagents, context boundaries, and validator rules |
| Arize OpenInference [s3][s4] | Repository page identifies Apache License 2.0 [s4] | Not a JSONL parser: semantic conventions describe span attributes; repository says the specification is transport- and file-format-agnostic [s4] | `openinference.span.kind` includes `AGENT`, `TOOL`, `LLM`, `CHAIN`, `EVALUATOR`, etc.; destinations can be Phoenix, Arize AX, or any OTel-compatible collector [s3][s4]. An OTel server is optional for a local/static exporter (implication) | Project ATIF agent/tool/model events to `AGENT`/`TOOL`/`LLM` spans; carry `session.id`, `agent.name`, `graph.node.id/parent_id`, tool names/args, messages, token/cost/evaluation attributes |
| `kolkov/ccdiag` [s5][s6] | Repository and fetched LICENSE identify MIT [s5][s6] | Claude Code session JSONL paths, including `~/.claude/projects/`; optional proxy writes per-session JSONL [s5] | Analyze detects orphaned tool calls, stuck tools, errors, interruptions, and token usage; JSON output supports CI. Recover emits handoff/messages/actions/full text. No Phoenix/OTel server required for local commands [s5] | Reuse orphan/tool-result pairing, error/interruption checks, token totals, and recovery categories as check taxonomy before ATIF/HTML emission |
| `simonw/claude-code-transcripts` [s7][s8] | README badge and fetched LICENSE identify Apache-2.0 [s7][s8] | Claude Code JSON or JSONL; local sessions under `~/.claude/projects`; `all` can include agent sessions [s7] | Generates `index.html` plus paginated `page-*.html`; `--json` can archive original source. Local browser/static output; no Phoenix/OTel server [s7] | Borrow source discovery, project/session archive indexes, pagination, static HTML layout, optional raw-source retention, and subagent inclusion flag |
| Agent Skills specification [s9] | Fetched specification does not state a software license; treat license as an unresolved legal field | Skill directory with required `SKILL.md` (YAML frontmatter + Markdown), optional scripts/references/assets [s9] | Metadata is loaded first, body/resources progressively; no server or OTel requirement [s9] | Validate `name`/`description`; preserve optional `license`, `compatibility`, arbitrary string-map `metadata`, and put `metadata.version` in a separate skill-provenance record rather than conflating it with runtime agent version |
| Vercel `skills` CLI update design [s10] | Fetched AGENTS.md is implementation documentation and does not state the repository license; do not vendor code until separately verified | GitHub/local skills plus global `~/.agents/.skill-lock.json` and checked-in `skills-lock.json` [s10] | Lock format v3 stores `skillFolderHash` (GitHub tree SHA) and `skillPath`; `check/update` fetches the latest tree SHA and compares, reinstalling changed skills [s10] | Exact-content longitudinal tracking: record tree SHA, source/path, commit/ref, observation time, and evaluation run ID alongside semver |

## ATIF shape relevant to coding-agent ingestion

The fetched Harbor RFC is an active JSON specification (current changelog v1.8) [s1]. Root metadata includes required `schema_version`, required `agent` object, required `steps`, optional `session_id`, `trajectory_id`, `final_metrics`, `continued_trajectory_ref`, `extra`, and embedded `subagent_trajectories`. `agent.name` and `agent.version` are required; `model_name`, tool definitions, and custom `extra` are optional [s1].

Each step has required `step_id`, `source` (`system`, `user`, or `agent`), and `message`; optional fields include timestamp, model name, reasoning, structured `tool_calls`, an `observation.results` array, metrics, `extra`, and `llm_call_count` [s1]. Tool results correlate with calls via `tool_call_id` and `source_call_id`; metrics include prompt/completion/cached tokens, cost, token IDs, and logprobs [s1]. v1.7 introduced document-level `trajectory_id` and embedded subagent trajectories; v1.8 added audio [s1].

Recommended adapter mapping: emit one ATIF JSON document per source session (not one JSON object per source JSONL line); preserve original line/event IDs and unknown provider fields under `extra`; make tool-use/result correlation explicit; represent context compaction with the RFC's `context_management` metadata; set `agent.version` to the harness/runtime version and store skill provenance in `agent.extra` or root/step `extra`.

## OpenInference projection

OpenInference's fetched specification requires `openinference.span.kind` and defines `AGENT` as encompassing LLM and Tool calls; `TOOL`, `LLM`, `CHAIN`, `EVALUATOR`, and other kinds are also defined [s3]. It defines session, agent, graph-node, tool-call, message, token, cost, and evaluation attributes, including `session.id`, `agent.name`, `graph.node.id`, `graph.node.parent_id`, `tool.name`, and flattened message/tool arrays [s3]. The repository README explicitly says the conventions complement OpenTelemetry, are transport/file-format agnostic, and work with Phoenix, Arize AX, or any OTel-compatible backend [s4].

Therefore use OpenInference as an optional export/projection, not as the raw-file ingestion contract: `ATIF agent step -> AGENT span`, model invocation -> `LLM`, each executable action -> `TOOL`, orchestration -> `CHAIN`, checks/evals -> `EVALUATOR`; attach parent/child relationships from session and graph IDs. Static HTML and file validation remain useful when no collector is configured.

## Claude Code parser surfaces

`ccdiag` is a genuine analyzer rather than only a viewer: its README documents parsing local Claude JSONL, orphan tool-use/result detection, stuck/error/interrupted checks, token accounting, CI-friendly JSON, and recovery modes for messages/actions/handoff/full output [s5]. Its optional proxy also records token/cache/cost/latency/session/model/error metrics in per-session JSONL, but that proxy is not required to inspect existing files [s5].

`claude-code-transcripts` accepts both JSON and JSONL, discovers `~/.claude/projects`, provides `local`, `json`, and `all` commands, can include agent sessions, and emits a browsable static archive (`index.html` and paginated pages) [s7]. It also offers `--json` to retain source alongside rendered pages [s7]. This is the strongest directly fetched borrow for static HTML; it is not an OTel/Phoenix integration.

## Skill version tracking over time

The Agent Skills spec makes `metadata` optional and arbitrary, and shows `metadata.version` as an example; no version field is required [s9]. Treat semver as a human release label, not an immutable identity. The Vercel implementation documents a stronger exact-state mechanism: lockfile v3 records a GitHub tree SHA for the skill folder (`skillFolderHash`) and path; update checks compare the current tree SHA via the GitHub Trees API and reinstall on mismatch [s10].

For each report/eval run, persist a provenance tuple such as `{skill_name, metadata_version, skill_folder_hash, git_ref_or_commit, source_path, observed_at, agent_runtime_version, model, harness_version, run_id}`. Compare both semver and hash: semver communicates intent, while the tree/content hash catches unlabelled edits. In ATIF, keep `agent.version` for the agent/harness and put this tuple under `agent.extra.skill_versions` or root `extra`; in OpenInference, expose the stable session/agent identity and prompt/template version fields where available. Evaluate fixed tasks with `skill-vN`/baseline labels and retain pass rate, score, tokens, latency, and artifact links per run.

## Contradiction sweep

1. **OTel-required vs file-log-native (resolved by scope):** Harbor ATIF is a JSON file schema with a Pydantic/path validator [s1]; `ccdiag` and `claude-code-transcripts` consume local JSONL and emit local diagnostics/HTML [s5][s7]. OpenInference is explicitly transport/file-format agnostic and can target any OTel-compatible collector [s3][s4]. The architecture should not require Phoenix merely to ingest, validate, or render; make OTel export optional.
2. **ATIF JSON document vs source JSONL:** ATIF's required root `steps` array is a document-level schema [s1], whereas Claude input is line-delimited events [s5][s7]. The adapter must stream lines, correlate IDs, then assemble one trajectory document (or explicitly shard trajectories); never treat each line as an ATIF root.
3. **ATIF runtime version vs skill version:** ATIF requires `agent.version` [s1], while Agent Skills only permits arbitrary optional `metadata.version` [s9]. Keep separate namespaces; do not place the SKILL.md semver in `agent.version`.
4. **Semver vs tree hash:** `metadata.version` is optional and human-readable [s9]; Vercel's `skillFolderHash` is a Git tree SHA used for update detection [s10]. Record both plus commit/ref and run ID; neither alone describes model/harness changes.
5. **ATIF versioned evolution:** RFC status is active with v1.8 current, while its illustrative example still declares `ATIF-v1.5`; v1.7 also documents breaking subagent-reference semantics [s1]. Pin and validate against a chosen Harbor model version, preserve `schema_version`, and test migrations explicitly rather than inferring from the example.

## Proof gaps / unresolved items

- No directly fetched primary source in this pass establishes a Codex rollout JSONL community parser's license or stable public API; keep Codex parser claims from this wave out of the ledger until its README and LICENSE are fetched.
- No fetched Agent Skills repository LICENSE or Vercel CLI LICENSE was included in the ten-fetch budget; the spec/CLI docs are useful evidence but not permission to vendor implementation code.
- The fetched ATIF RFC describes a reference validator and comparative examples, but does not itself document a ready-made Claude/Codex JSONL-to-ATIF exporter. Implement the adapter as a new boundary or verify a separately fetched converter.
- No fetched primary skill-evaluator run artifact establishes a common longitudinal benchmark schema; use the explicit provenance tuple and fixed-task baseline/treatment records as a project-level convention until an evaluator source is separately validated.

## Inline plan.json

```json
{
  "question": "What is the ATIF / OpenInference coding-agent trajectory format, which OSS tools parse Claude Code JSONL (~/.claude/projects/*.jsonl), Codex rollout JSONL, and how do projects track agent skill versions over time?",
  "objective": "Borrowable parsers and skill-version tracking after local session-format inventory",
  "lane": "exploratory_topic",
  "forceMode": "styrir_plus",
  "mode": "styrir_plus",
  "facets": [
    "ATIF spec and Harbor validator",
    "OpenInference agent/tool span conventions",
    "OSS Claude Code JSONL analyzers and static HTML converters",
    "SKILL.md metadata/version and exact-content update tracking",
    "OTel/server dependency versus file-native contradiction sweep"
  ],
  "budgets": {"maxSearchQueries": 10, "maxFetches": 10, "searchQueriesRun": 8, "sourcesFetched": 10},
  "sourceScope": ["official docs", "GitHub repositories", "OpenInference/ATIF specs"],
  "deliverables": ["named parser/spec license and input format", "Phoenix/OTel dependency note", "compact borrow list", "proof gaps"]
}
```

## Inline source-registry.json

```json
{
  "sources": [
    {"id":"s1","url":"https://github.com/harbor-framework/harbor/blob/main/rfcs/0001-trajectory-format.md","title":"Harbor RFC 0001: Agent Trajectory Interchange Format (ATIF) Specification","sourceType":"repo","fetched":true},
    {"id":"s2","url":"https://github.com/harbor-framework/harbor/blob/main/LICENSE","title":"Harbor LICENSE","sourceType":"repo","fetched":true},
    {"id":"s3","url":"https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md","title":"OpenInference Semantic Conventions","sourceType":"repo","fetched":true},
    {"id":"s4","url":"https://github.com/Arize-ai/openinference","title":"Arize-ai/openinference README and repository metadata","sourceType":"repo","fetched":true},
    {"id":"s5","url":"https://github.com/kolkov/ccdiag","title":"ccdiag Claude Code Session Analyzer, Recovery & Proxy Tool","sourceType":"repo","fetched":true},
    {"id":"s6","url":"https://github.com/kolkov/ccdiag/blob/main/LICENSE","title":"ccdiag LICENSE","sourceType":"repo","fetched":true},
    {"id":"s7","url":"https://github.com/simonw/claude-code-transcripts/blob/main/README.md","title":"claude-code-transcripts README","sourceType":"repo","fetched":true},
    {"id":"s8","url":"https://github.com/simonw/claude-code-transcripts/blob/main/LICENSE","title":"claude-code-transcripts LICENSE","sourceType":"repo","fetched":true},
    {"id":"s9","url":"https://agentskills.io/specification","title":"Agent Skills Specification","sourceType":"official","fetched":true},
    {"id":"s10","url":"https://github.com/vercel-labs/skills/blob/main/AGENTS.md","title":"Vercel skills CLI update and lockfile design notes","sourceType":"repo","fetched":true}
  ]
}
```

## Inline ledger.json

```json
{
  "meta": {
    "searchId": "search-2026-09-13-second-pass-formats",
    "mode": "styrir_plus",
    "totalQueriesRun": 8,
    "totalSourcesFetched": 10,
    "budget": {"maxSearchQueries": 10, "maxFetches": 10}
  },
  "entries": [
    {"id":"e1","entity":"Harbor ATIF","signalType":"trajectory_schema","observation":"Harbor RFC 0001 defines ATIF as a JSON specification with root schema_version, agent, and steps fields; current changelog is v1.8.","possibleImplication":"Use ATIF as the normalized file-native trajectory target.","sourceId":"s1","sourceUrl":"https://github.com/harbor-framework/harbor/blob/main/rfcs/0001-trajectory-format.md","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.99},
    {"id":"e2","entity":"Harbor ATIF","signalType":"trajectory_schema","observation":"ATIF AgentSchema requires agent.name and agent.version; StepObject requires step_id, source, and message, and permits reasoning_content, tool_calls, observation, metrics, extra, and llm_call_count.","possibleImplication":"Preserve agent runtime version separately from skill version and map tool/result events into structured steps.","sourceId":"s1","sourceUrl":"https://github.com/harbor-framework/harbor/blob/main/rfcs/0001-trajectory-format.md","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.98},
    {"id":"e3","entity":"Harbor ATIF","signalType":"subagent_and_context","observation":"ATIF v1.7 adds trajectory_id, embedded subagent_trajectories, and context_management conventions; v1.8 adds audio content.","possibleImplication":"Represent delegated OMP/agent sessions and compaction boundaries without producer-specific heuristics.","sourceId":"s1","sourceUrl":"https://github.com/harbor-framework/harbor/blob/main/rfcs/0001-trajectory-format.md","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.92},
    {"id":"e4","entity":"Harbor","signalType":"license","observation":"The fetched Harbor LICENSE is Apache License 2.0.","possibleImplication":"Apache-2.0 schema/model code is a candidate for borrowing subject to attribution and compatibility review.","sourceId":"s2","sourceUrl":"https://github.com/harbor-framework/harbor/blob/main/LICENSE","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.85},
    {"id":"e5","entity":"OpenInference","signalType":"transport_and_backend","observation":"The OpenInference README describes the specification as transport- and file-format-agnostic, complementary to OpenTelemetry, and usable with JSON, ProtoBuf, DataFrames, or other formats.","possibleImplication":"Do not make an OTel collector a prerequisite for local normalization or static HTML.","sourceId":"s4","sourceUrl":"https://github.com/Arize-ai/openinference","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.99},
    {"id":"e6","entity":"OpenInference","signalType":"span_conventions","observation":"The fetched semantic convention defines required openinference.span.kind values including AGENT, TOOL, LLM, CHAIN, and EVALUATOR, plus session.id, agent.name, graph.node.id, graph.node.parent_id, tool, message, token, cost, and evaluation attributes.","possibleImplication":"Offer an optional ATIF-to-OpenInference projection for OTel-compatible consumers.","sourceId":"s3","sourceUrl":"https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.98},
    {"id":"e7","entity":"OpenInference","signalType":"license","observation":"The fetched OpenInference repository metadata identifies Apache License 2.0.","possibleImplication":"Apache-2.0 conventions/instrumentation are candidates for borrowing with attribution review.","sourceId":"s4","sourceUrl":"https://github.com/Arize-ai/openinference","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.83},
    {"id":"e8","entity":"ccdiag","signalType":"claude_jsonl_parser","observation":"ccdiag is a Go CLI that analyzes Claude Code session JSONL, including files under ~/.claude/projects, and offers recover/analyze/proxy modes.","possibleImplication":"Reuse its input discovery and stream-oriented diagnostic boundary for Claude ingestion.","sourceId":"s5","sourceUrl":"https://github.com/kolkov/ccdiag","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.96},
    {"id":"e9","entity":"ccdiag","signalType":"checks_and_outputs","observation":"ccdiag documents orphaned tool-call detection, stuck/error/interrupted checks, token usage, CI JSON output, and recovery outputs named handoff, messages, actions, and full.","possibleImplication":"Borrow a pre-normalization check taxonomy and machine-readable diagnostics in the static report.","sourceId":"s5","sourceUrl":"https://github.com/kolkov/ccdiag","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.95},
    {"id":"e10","entity":"ccdiag","signalType":"license","observation":"The fetched ccdiag repository metadata and LICENSE identify the MIT License.","possibleImplication":"MIT parser/check logic is a candidate for selective borrowing with attribution.","sourceId":"s6","sourceUrl":"https://github.com/kolkov/ccdiag/blob/main/LICENSE","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.84},
    {"id":"e11","entity":"claude-code-transcripts","signalType":"claude_jsonl_to_html","observation":"claude-code-transcripts converts Claude Code JSON or JSONL session files to mobile-friendly HTML, with local/json/all commands and local discovery under ~/.claude/projects.","possibleImplication":"Borrow static HTML archive and source-session discovery patterns.","sourceId":"s7","sourceUrl":"https://github.com/simonw/claude-code-transcripts/blob/main/README.md","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.98},
    {"id":"e12","entity":"claude-code-transcripts","signalType":"static_report","observation":"The converter emits index.html and paginated page-*.html files; --json retains the original session file and --include-agents includes agent session files in an all-session archive.","possibleImplication":"Use static pages and optional raw JSON retention without Phoenix or OTel infrastructure.","sourceId":"s7","sourceUrl":"https://github.com/simonw/claude-code-transcripts/blob/main/README.md","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.96},
    {"id":"e13","entity":"claude-code-transcripts","signalType":"license","observation":"The fetched README license badge and LICENSE identify Apache-2.0.","possibleImplication":"Apache-2.0 HTML conversion patterns are candidates for borrowing with attribution.","sourceId":"s8","sourceUrl":"https://github.com/simonw/claude-code-transcripts/blob/main/LICENSE","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.84},
    {"id":"e14","entity":"Agent Skills","signalType":"skill_format","observation":"The Agent Skills specification requires a skill directory containing SKILL.md with YAML frontmatter and Markdown; name and description are required, while license, compatibility, metadata, and allowed-tools are optional.","possibleImplication":"Ingest SKILL.md metadata and body as versioned skill artifacts rather than assuming a mandatory version field.","sourceId":"s9","sourceUrl":"https://agentskills.io/specification","sourceType":"official","dateObserved":"2026-09-13","confidence":"high","relevance":0.96},
    {"id":"e15","entity":"Agent Skills","signalType":"skill_versioning","observation":"The specification defines metadata as an arbitrary string-to-string map and shows metadata.version in an example, but does not require a version field.","possibleImplication":"Use metadata.version when present and supplement it with immutable content provenance.","sourceId":"s9","sourceUrl":"https://agentskills.io/specification","sourceType":"official","dateObserved":"2026-09-13","confidence":"high","relevance":0.98},
    {"id":"e16","entity":"Vercel skills CLI","signalType":"skill_versioning","observation":"Vercel skills lock format v3 stores skillFolderHash, a GitHub tree SHA for the skill folder, and skillPath in ~/.agents/.skill-lock.json.","possibleImplication":"Tree SHA is an exact skill-content identity suitable for longitudinal reports.","sourceId":"s10","sourceUrl":"https://github.com/vercel-labs/skills/blob/main/AGENTS.md","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.97},
    {"id":"e17","entity":"Vercel skills CLI","signalType":"update_detection","observation":"The documented check/update flow fetches the latest GitHub tree SHA, compares it with skillFolderHash, and reinstalls changed skills.","possibleImplication":"Track semver and hash independently and emit an update event when either changes.","sourceId":"s10","sourceUrl":"https://github.com/vercel-labs/skills/blob/main/AGENTS.md","sourceType":"repo","dateObserved":"2026-09-13","confidence":"high","relevance":0.95}
  ],
  "proofGaps": [
    {"description":"No fetched primary source in this pass establishes a Codex rollout JSONL community parser license or stable API.","attemptedQueries":["Codex rollout JSONL parser GitHub OpenAI sessions"]},
    {"description":"Agent Skills and Vercel CLI license files were not fetched within the ten-fetch budget.","attemptedQueries":["SKILL.md version tracking agent skill evaluation GitHub","agent skills benchmark SKILL.md eval over time GitHub open source"]},
    {"description":"No fetched primary source documents a ready-made Claude/Codex JSONL-to-ATIF exporter; Harbor documents the target schema and validator only.","attemptedQueries":["Agent Trajectory Interchange Format ATIF Claude Code JSONL converter"]},
    {"description":"No fetched primary source establishes a shared longitudinal SKILL.md evaluator artifact schema.","attemptedQueries":["agent skills benchmark SKILL.md eval over time GitHub open source"]}
  ],
  "sources": [
    {"id":"s1","url":"https://github.com/harbor-framework/harbor/blob/main/rfcs/0001-trajectory-format.md","title":"Harbor RFC 0001 ATIF","sourceType":"repo","fetched":true},
    {"id":"s2","url":"https://github.com/harbor-framework/harbor/blob/main/LICENSE","title":"Harbor LICENSE","sourceType":"repo","fetched":true},
    {"id":"s3","url":"https://github.com/Arize-ai/openinference/blob/main/spec/semantic_conventions.md","title":"OpenInference Semantic Conventions","sourceType":"repo","fetched":true},
    {"id":"s4","url":"https://github.com/Arize-ai/openinference","title":"Arize-ai/openinference README and repository metadata","sourceType":"repo","fetched":true},
    {"id":"s5","url":"https://github.com/kolkov/ccdiag","title":"ccdiag README and repository metadata","sourceType":"repo","fetched":true},
    {"id":"s6","url":"https://github.com/kolkov/ccdiag/blob/main/LICENSE","title":"ccdiag LICENSE","sourceType":"repo","fetched":true},
    {"id":"s7","url":"https://github.com/simonw/claude-code-transcripts/blob/main/README.md","title":"claude-code-transcripts README","sourceType":"repo","fetched":true},
    {"id":"s8","url":"https://github.com/simonw/claude-code-transcripts/blob/main/LICENSE","title":"claude-code-transcripts LICENSE","sourceType":"repo","fetched":true},
    {"id":"s9","url":"https://agentskills.io/specification","title":"Agent Skills Specification","sourceType":"official","fetched":true},
    {"id":"s10","url":"https://github.com/vercel-labs/skills/blob/main/AGENTS.md","title":"Vercel skills CLI update and lockfile design","sourceType":"repo","fetched":true}
  ]
}
```

## Inline contradiction-sweep.md

```markdown
# Contradiction sweep

- **OTel-required vs file-log-native — resolved by scope.** Harbor ATIF is a JSON schema and local Pydantic validator. `ccdiag` and `claude-code-transcripts` consume local Claude JSONL and produce local diagnostics/static HTML. OpenInference is transport/file-format agnostic and can export to an OTel-compatible collector. Make OTel/Phoenix optional, not an ingestion prerequisite.
- **ATIF JSON document vs source JSONL.** Source logs are line-delimited events; ATIF is a root document with a `steps` array. Stream and correlate input lines, then assemble one ATIF trajectory per logical session (or explicitly shard); do not map each JSONL line to an ATIF root.
- **ATIF agent version vs SKILL.md version.** ATIF requires `agent.version`; Agent Skills only permits arbitrary optional `metadata.version`. Keep harness/runtime and skill identity in separate fields.
- **Semver vs exact content.** `metadata.version` is a human label; Vercel's `skillFolderHash` is a Git tree SHA used for update detection. Store both with source/path, commit/ref, observed time, and evaluation run ID.
- **ATIF version drift.** RFC status is active and changelog v1.8, but the illustrative trajectory still says `ATIF-v1.5`; v1.7 changes subagent reference resolution. Pin schema/model versions and validate explicitly.

## Residual proof gaps

1. Codex rollout parser and license were not fetched in this ten-fetch wave.
2. Agent Skills and Vercel CLI LICENSE files were not fetched; do not vendor their implementations based on docs alone.
3. No ready-made Claude/Codex JSONL-to-ATIF exporter was established by fetched primary sources.
4. No common longitudinal SKILL.md evaluator artifact schema was established; use a fixed-task baseline/treatment record plus the provenance tuple as a project convention.
```

