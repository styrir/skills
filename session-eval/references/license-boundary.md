# License boundary

Not legal advice. This is an engineering split so agents do not vendor the wrong tree.

Phoenix clone: `~/Code/refs/observability/phoenix` HEAD `e127482` (arize-phoenix 12.11.0 / release 20.11.0). Root `LICENSE` is Elastic License 2.0. `IP_NOTICE` names US patents 11,315,043 and 11,615,345.

## Do not

- Vendor `src/phoenix/` server, UI, GraphQL, DB, MCP, PXI, or `packages/phoenix-evals` (also ELv2).
- Offer a hosted service that exposes a substantial set of Phoenix features.
- Copy Phoenix classification YAML prompts or evaluator implementations.
- Call `px setup` / Phoenix MCP from this skill.
- Assume Python `phoenix-otel` / `phoenix-client` are clean Apache: package metadata says Apache-2.0, package `IP_NOTICE` still says ELv2. Legal review before any source reuse. Independent reimplementation is the default.

## Study and reimplement (ideas only)

- Evaluator result shape: name, score, label, explanation, kind (`code`/`llm`/`human`), direction.
- Code-first then LLM for nuance.
- Immutable snapshots + run identity separate from display names.
- Session/turn grouping without requiring a root OTel span.
- Chart catalog: traffic, latency, tokens, errors, annotation means, baseline vs candidate.
- Harbor-style split of infra failure vs behavioral score; best-effort artifacts must not flip a task fail.

## Prefer permissive OSS when copying code

First-wave Styrir Plus (`ops-4af.2`, gated ledger under agent-ops `.styrir/runs/2026-09-13-session-obs/competitors/`):

| Project | License (fetched) | Borrow surface |
|---|---|---|
| Harbor | Apache-2.0 | Multi-agent eval runner, trial `result.json` + artifact manifest |
| OpenHands trajectory-visualizer | MIT | Raw trajectory timeline (optional drill-down) |
| OpenHands/benchmarks | MIT | Benchmark identity + SDK pin in metadata |
| eval-dashboards | MIT (v0.x) | Static HTML + `eval-report/v1` row fields; pin version |
| Promptfoo | MIT | Local eval + web viewer; not a session ingest |
| TruLens | MIT | Agent evaluator *categories*; independent code |
| Ragas | Apache-2.0 | Metrics library; README still says `agent_evals` Coming Soon while the official guide documents `ragas quickstart agent_evals` — treat release status as unresolved |
| Evidently | Apache-2.0 | HTML report export pattern |
| Opik | Apache-2.0 | Full self-host platform reference; do not take a dependency unless we decide to |
| LangWatch | Apache core + EE split | Self-host core only if we ever integrate |
| Helicone | Apache-2.0 | Self-host methods (manual/Compose/K8s/cloud) fetched; feature/session/HTML parity still a gap |
| OpenLLMetry | Apache-2.0 repo | Vendor-neutral OTel instrumentation; Traceloop *platform* terms not fetched |
| Inspect AI | MIT (raw LICENSE) | Harness/docs surface; confirm package docs before copying more than license |
| W&B Weave | Apache SDK; platform commercial | SDK-only; account-gated UI |
| Langfuse | MIT outside `ee/`; `ee/LICENSE` for EE | Current handbook/pricing: Playground, LLM-as-judge, sessions, agent traces are OSS self-host. Phoenix comparison page is stale on paywalls. EE = SCIM/audit/retention. |
| Harbor ATIF RFC | Apache-2.0 | File-native trajectory JSON; no Phoenix/OTel required |
| OpenInference spec | Apache-2.0 | Optional span projection; not an ingest prerequisite |
| kolkov/ccdiag | MIT | Claude `~/.claude/projects` JSONL diagnostics/recovery CLI |
| simonw/claude-code-transcripts | Apache-2.0 | Claude JSON/JSONL → paginated static HTML |

## Local first-party code we already own

- `~/Code/claude-dashboard` — Claude JSONL → SQLite; reuse parsers, do not absorb Mission Control.
- `~/Code/agent-ops/bin/workgraph-dossier` — HTML dossier pattern.
- `~/Code/agent-ops/bin/workgraph-eval-score` — WorkGraph hard_fail suite.

## Second-pass (ops-4af.8, gated)

Ledgers: agent-ops `.styrir/runs/2026-09-13-session-obs/second-pass-licenses/` and `second-pass-formats/`.

- Langfuse paywall claims on the pinned Phoenix comparison page are **not current**. First-party Langfuse handbook/pricing list Playground and LLM-as-judge as MIT/OSS Yes.
- Phoenix remains ELv2 source-available/self-hostable, not a permissive hosted-product dependency.
- Patent numbers stay on file. Title-only search discovery (not fetched records): both US 11,315,043 and US 11,615,345 surfaced as “Systems and methods for optimizing a machine learning model”. Direct Google Patents pages were not fetched; no claims/abstracts are used.
- Skill provenance: Agent Skills `metadata.version` is optional human semver; pair with content digest / Git tree hash (Vercel `skillFolderHash` pattern, independently reimplemented).
- Pipeline: JSONL → normalized file-native trajectory (ATIF-shaped) → HTML. Optional later OpenInference/OTel export.

Still open: Codex community parser license; Agent Skills / Vercel CLI LICENSE files; JSONL-to-ATIF exporter (we write our own); Helicone feature parity pages.
