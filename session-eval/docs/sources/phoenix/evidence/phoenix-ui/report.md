## 1. UI surfaces, charts, and static HTML

### Human-facing observability surfaces

- **Project workspace** (`ProjectPage.tsx`): tabs for spans, traces, sessions, configuration, and metrics; project-scoped time range, streaming refresh, and validated URL filter DSL.
- **Trace table/detail** (`TracesTable.tsx`, `TraceDetails.tsx`, `SpanDetails.tsx`): sortable/paginated root traces, expandable nested span trees, operational columns (status, kind, latency, tokens, cost, inputs/outputs, metadata, annotations), resizable detail drawer, URL-selected trace/span, span Info/Attributes/Events tabs, exception event details, prompt playground/add-to-dataset/download actions.
- **Span table** (`SpansTable.tsx`): span-level filters and the same trace/span drilldown path.
- **Session views** (`SessionsTable.tsx`, `SessionDetails.tsx` and related views): session ID, turns, first/last messages, trace count, start/end, P50/P99 latency, token/cost and annotations; drawer tabs for conversation turns, traces, and annotations.
- **Dashboards/metrics** (`DashboardsPage.tsx`, `ProjectMetricsPage.tsx`): project selector and connected time range, then metric panels arranged in rows.
- **Dataset/experiment surfaces** (`DatasetPage.tsx`, `ExperimentsPage.tsx`, `ExperimentComparePage.tsx`): dataset examples/versions/evaluators/metrics; experiment status and error details; compare grid, list, and metrics modes.
- **Evaluator surfaces** (`pages/dataset/evaluators/` and global evaluator pages): evaluator configuration, spans, metrics, and evaluator trace drilldown.

### Chart catalog and visual encodings

The project catalog defines these named metrics and archetypes:

- `traffic`: spans by status, stacked time-series bars (`SpanCountTimeSeries`).
- `traces`: overall trace volume, stacked OK/error time-series bars (`TraceCountTimeSeries`).
- `latency`: trace latency percentiles, lines for P50/P75/P90/P95/P99/P99.9/max (`TraceLatencyPercentilesTimeSeries`).
- `cost`: estimated USD, stacked prompt/completion bars (`TraceTokenCostTimeSeries`).
- `top_models_by_cost`: horizontal stacked bars ranked by model.
- `tokens`: prompt/completion token usage, stacked bars.
- `top_models_by_tokens`: horizontal stacked model ranking.
- `prompt_token_details` and `completion_token_details`: stacked detail bars by input/cache/audio and output/reasoning/audio token categories.
- `llm_spans`, `llm_span_errors`, `tool_spans`, `tool_span_errors`: status/count/error time-series bars, using span-kind filters for LLM or TOOL.
- `span_annotations`, `trace_annotations`, `session_annotations`: annotation means as lines or annotation-label distributions as stacked bars; dynamic annotation names are discovered by level.

Additional chart components include:

- `AnnotationSummary.tsx`: compact mean score/label summary with mini Recharts pie chart and tooltip.
- `ConfusionMatrix.tsx`: density-colored actual-vs-predicted matrix with row/column/grand totals, percentages, TP/FN/FP/TN labels, linear/log scale, and legend.
- Dataset/experiment metric charts: average run latency, stacked cost, stacked prompt/completion tokens, error rate, and annotation-score lines/distributions with baseline references.
- `TableMetricsCharts.tsx` and `MetricsChartSelector.tsx`: chart catalog search, selected/available sections, drag reordering, per-project/table persistence, vertical resizing, responsive horizontal strip with minimum panel width, and click/drag time-range brush. Tooltips and legends synchronize within the relevant chart group.

### Static-vs-live result

Observed source behavior is a **live SPA**, not a self-contained report renderer:

1. `src/phoenix/server/templates/index.html` supplies `<div id="root">`, manifest-derived assets, and serialized/frozen server configuration.
2. `src/phoenix/server/app.py` mounts the built static directory and falls back to the same `index.html` for client routes.
3. `js/app/src/index.tsx` creates the React root; Vite config emits the browser bundle.
4. `js/app/src/RelayEnvironment.ts` sends GraphQL POST requests and supports multipart GraphQL subscriptions, while stream state triggers refetches.

Searches across the inspected app/packages/server source for report/export/HTML serialization and chart SVG/canvas download paths found no data-bearing static HTML trend-report exporter. `SpanDownloadMenu.tsx` provides span JSON, OTLP JSON, and trace downloads only. **[INFERENCE]** A Styrir local dossier should therefore be a separate self-contained HTML artifact with embedded normalized JSON and HTML/SVG charts, rather than attempting to reuse Phoenix’s SPA shell or assuming a Phoenix report-export API. Proof gap: generated/bundled artifacts and external hosted deployments were not treated as authoritative source and could theoretically differ; no exporter was found in the inspected source trees.

## 2. Claude/Codex plugin, skill, and CLI contract

### Claude Code

`plugins/claude/arize-phoenix/.claude-plugin/plugin.json` points at `.mcp.json`; its MCP entry is streamable HTTP at `${user_config.endpoint}/mcp`. The README documents a default local endpoint of `http://localhost:6006`, a base URL with no trailing slash, browser OAuth on first use, and plugin configuration through `plugin install ... --config endpoint=...`. It bundles the `phoenix-cli`, `phoenix-evals`, and `phoenix-tracing` skill trees via symlinks to `.agents/skills`; the CLI itself remains a separately invokable `px` executable. For headless API-key operation, `px setup mcp --agent claude --header 'Authorization: Bearer ${PHOENIX_API_KEY}'` is documented.

### Codex

`plugins/codex/arize-phoenix/.codex-plugin/plugin.json` points at `.mcp.json`; the plugin declares a stdio MCP server launched by `scripts/phoenix-mcp`. The launcher normalizes an unset or placeholder endpoint to localhost, strips a trailing slash, preserves an existing `/mcp`, or appends `/mcp`, then executes `npx --yes mcp-remote`. With an API key it passes a literal header template so the key is not exposed in process arguments; without one, browser-login behavior is left to mcp-remote. Codex forwards only declared `PHOENIX_ENDPOINT` and `PHOENIX_API_KEY` variables. The Codex plugin README says it bundles MCP but not the skill files; skills are installed separately.

Both plugins target Phoenix 19.0.0+ and the `/mcp` endpoint. The shared CLI environment contract is `PHOENIX_ENDPOINT`, `PHOENIX_PROJECT`, and optional `PHOENIX_API_KEY`. `phoenix-cli/SKILL.md` documents precedence flags > environment > profile > `.env.phoenix` > defaults, OAuth/API-key profiles, trace/span/session/dataset/experiment/prompt/project/GraphQL resources, and explicit dangerous-delete gating. `px setup --no-input --format raw` writes `.env.phoenix`; instrumentation requires both an agent and `--yolo`; setup output distinguishes verified/not-verified/deferred tracing, and no trace verification exits with code 6. Setup is intentionally rerunnable (`px setup instrument`, `px setup skills`, `px setup mcp`). Phoenix Docs MCP is documented separately from the built-in Remote MCP data-operation service.

`phoenix-evals/SKILL.md` emphasizes error analysis first, code-first evaluators, custom evaluators over generic ones, binary labels over Likert where possible, and validating LLM judges against humans. `phoenix-tracing/SKILL.md` centers OpenInference instrumentation, span kinds, projects/sessions, masking/batching, and annotations. Its ATIF reference documents conversion of Claude Code/OpenHands/Gemini CLI/Codex Harbor trajectories to OTel span trees, deterministic IDs, idempotent reupload, continuation merging, and mapping of model/tool/metric/session information.

## 3. Harbor evaluation meaning

`evals/harbor/tasks/regression-triage` measures whether a headless coding/data agent can perform an end-to-end regression investigation against Phoenix, not merely whether it emits a plausible answer or reaches a single quality score.

The four steps are:

1. Aggregate `correctness` over all runs for two experiments in `qa-bot-golden`, identify the lower candidate, and emit strict JSON. Fixture ground truth is `baseline-gpt4o = 0.9` and `candidate-v2 = 0.7`.
2. Compare the baseline pass set to the candidate fail set, identify exactly `ex-005`, `ex-009`, `ex-014`, `ex-021`, `ex-026`, and `ex-030`, and infer the Spanish/español input pattern.
3. For `ex-014`, locate the candidate trace and errored span; expected span is `translate_query` with `UnsupportedLocaleError: locale 'es' is not enabled for translation`.
4. With mutations enabled, create a `regressions` dataset split containing exactly those six examples.

The step checks enforce the numeric means, exact example-key set, exact span/exception evidence, and exact persisted split contents. The task uses four 900-second agent steps plus a 120-second first-step verifier, averages multi-step reward, and records tool-call count from the message artifact. The runner preserves conversation history and tracing session identity across steps; mutation permission is controlled by step config and only enabled for the final split step. Optional remote tracing wraps the run with session/task metadata.

**Implication [INFERENCE]:** Harbor is a useful acceptance model for Styrir session-eval because it tests navigation and joins across experiment metrics → dataset examples → traces/spans, exact arithmetic and structured output, evidence-backed diagnosis, and a separately gated write operation. It also provides a pattern for measuring tool efficiency without making tool count the sole correctness criterion.

## 4. Borrow list for a local Styrir HTML dossier

1. **Declarative metric catalog:** use stable IDs, descriptions, chart archetypes, and row grouping like `chartCatalog.tsx`; make the dossier renderer data-driven.
2. **Local trend controls:** include selected metric toggles, deterministic ordering, a connected time range, and click/drag narrowing where a time series is present.
3. **Responsive chart panels:** preserve Phoenix’s minimum useful panel width and horizontal overflow/fade treatment rather than shrinking labels into unreadability.
4. **Comparison semantics:** provide grid/list/summary modes, baseline markers, and explicit improved/regressed/equal counts for skill/run comparisons.
5. **Evidence drilldown:** make a session/run row open a bounded detail view with trace tree, selected span, tool calls, exceptions, annotations, and links back to the relevant trend bucket.
6. **Static-first artifact:** embed a normalized data snapshot in HTML and render charts locally; include provenance, generation time, source/log identity, and an empty/error state when data is missing.
7. **Strict evaluation contracts:** borrow Harbor’s per-step JSON schemas, deterministic verifiers, exact set/metric checks, and mutation gating; separate read-only analysis from final state-changing actions.
8. **CLI setup discipline:** borrow explicit environment/flag/profile precedence, rerunnable setup, raw machine-readable output, and nonzero verification failure semantics from `phoenix-cli`.
9. **Trajectory normalization:** borrow ATIF’s stable IDs, parent/child and continuation merge behavior, idempotent ingestion, and explicit handling of oversized history attributes for Claude/Codex/Pi/Grok/OMP adapters.

## 5. Proof gaps

- I inspected the source-level app, server template/mount, chart components/catalogs, plugins, skill files, coding-agent docs, Harbor task/runner/fixtures/oracle, and code-generation example. I did not rely on search snippets for cited facts.
- No static HTML/report exporter or chart SVG/canvas serialization path was found in those source trees; the strongest positive export evidence is span/trace JSON and OTLP JSON in `SpanDownloadMenu.tsx`.
- Generated Vite bundles, uninspected historical revisions, and external hosted Phoenix deployments were not used as evidence. They could contain behavior not represented by the inspected source, so the absence claim is bounded to the searched source scope.
- No project-wide tests, formatters, linters, or builds were run, per scout constraints; findings are source-based architecture and contract observations.
