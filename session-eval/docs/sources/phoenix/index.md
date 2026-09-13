---
summary: "Historical, source-only Phoenix architecture and UI scout findings preserved at reported HEAD e127482."
read_when:
  - "You need Phoenix architecture, evaluation, UI, plugin, or license observations for session-eval context."
  - "You need to trace a Phoenix observation to its preserved source artifact and provenance hash."
---

# Phoenix source dossier

This directory preserves the two Phoenix scout bundles as **historical, non-normative evidence**. The reports identify the inspected Phoenix revision as HEAD `e127482` and the local source clone as `/Users/brooks/Code/refs/observability/phoenix` (also addressable as `~/Code/refs/observability/phoenix`). The original run bundles are under `/Users/brooks/Code/agent-ops/.styrir/runs/2026-09-13-session-obs/phoenix-arch` and `/Users/brooks/Code/agent-ops/.styrir/runs/2026-09-13-session-obs/phoenix-ui`.

**Normative authority:** [`../../specification.md`](../../specification.md). This dossier records what the reports observed; it does not set session-eval requirements or amend any contract.

## Preserved snapshots

Every regular file present in each named source bundle was copied byte-for-byte. No session logs were copied. [`provenance.json`](provenance.json) inventories each snapshot's original absolute path, dossier-relative snapshot path, SHA-256 digest, and byte count.

### `phoenix-arch`

- [`architecture.txt`](evidence/phoenix-arch/architecture.txt) — 774 bytes; compact two-plane architecture summary.
- [`report.md`](evidence/phoenix-arch/report.md) — 24,464 bytes; module/evaluation, license, reuse, gap, and boundary report.
- [`summary.txt`](evidence/phoenix-arch/summary.txt) — 773 bytes; scout outcome summary.

### `phoenix-ui`

- [`report.md`](evidence/phoenix-ui/report.md) — 12,189 bytes; UI, chart, plugin/CLI, Harbor, borrow-list, and proof-gap report.
- [`summary.txt`](evidence/phoenix-ui/summary.txt) — 454 bytes; UI scout outcome summary.

## Observed architecture and evaluation findings

The `phoenix-arch` report describes a coupled ingestion/serving and evaluation platform. The serving plane uses OTLP HTTP/gRPC and OpenInference normalization, a typed span graph, database-backed traces and sessions, and FastAPI REST, GraphQL, UI, MCP, PXI, and CLI surfaces. Its trace model carries stable IDs, parent relationships, timestamps, status, attributes, events, exceptions, MIME-tagged input/output, and token usage. Session turns are derived from traces/root-span input and output, so the report treats that shape as a conceptual bridge rather than a file-native session model.

The report also records versioned datasets and experiment runs, evaluator results and annotations, online PXI selection/settling/checkpoint behavior, and Harbor's deterministic task/attempt/trajectory identity. Its check catalog distinguishes LLM-judge classification evaluators (grounding, correctness/completeness, retrieval, conversation/safety, and tool behavior) from deterministic exact-match, regex, precision/recall, and arbitrary code evaluators. The report's conclusion is that typed evidence, immutable/version-pinned runs, explicit evaluator results, bounded execution, deterministic identity, and machine-readable reporting are useful patterns to study independently; Phoenix's platform implementation and exact evaluator assets are not treated as session-eval code.

See the report's [`1. Module map and product surfaces`](evidence/phoenix-arch/report.md#1-module-map-and-product-surfaces), [`2. License matrix and reuse boundary`](evidence/phoenix-arch/report.md#2-license-matrix-and-reuse-boundary), [`3. Borrow list: ideas/patterns versus copy-code`](evidence/phoenix-arch/report.md#3-borrow-list-ideaspatterns-versus-copy-code), [`4. Gaps versus the first-party Styrir target`](evidence/phoenix-arch/report.md#4-gaps-versus-the-first-party-styrir-target), and [`5. Proof gaps and boundaries`](evidence/phoenix-arch/report.md#5-proof-gaps-and-boundaries) sections for the complete historical account. The compact [`architecture.txt`](evidence/phoenix-arch/architecture.txt) and [`summary.txt`](evidence/phoenix-arch/summary.txt) preserve the same two-plane and gap conclusions in abbreviated form.

## Observed UI, reporting, and agent-surface findings

The `phoenix-ui` report describes a live React/Vite SPA backed by GraphQL. Its observed surfaces include project workspaces; trace and span tables/details; session turns and annotations; dashboards and project metrics; dataset/experiment comparison; and evaluator drilldowns. The chart catalog covers traffic, traces, latency percentiles, cost, token details, model rankings, LLM/tool spans and errors, annotations, confusion matrices, and dataset/experiment metrics with filtering, persistence, and responsive layout behavior.

Its static-vs-live conclusion is explicit: the inspected source serves a React shell and makes GraphQL requests/subscriptions; no data-bearing static HTML trend-report exporter was found in the searched app/server paths. Span downloads were observed for JSON/OTLP/trace data. The report therefore records, as an inference rather than a requirement, that a local dossier would need an independently rendered self-contained artifact rather than Phoenix's SPA shell.

The report records separate Claude and Codex plugin contracts for the Phoenix MCP, a separately invokable `px` CLI, and installable tracing/evals skill trees. It also describes Harbor's four-step regression-triage task: aggregate experiment correctness, identify an exact candidate-failure set, locate a trace/exception, and persist a regression split under a gated mutation step. Its borrow-list conclusion highlights declarative metric catalogs, local trend controls, responsive panels, comparison semantics, evidence drilldown, static-first artifacts, strict verifiers, CLI setup discipline, and trajectory normalization as patterns to study independently.

See the report's [`1. UI surfaces, charts, and static HTML`](evidence/phoenix-ui/report.md#1-ui-surfaces-charts-and-static-html), [`2. Claude/Codex plugin, skill, and CLI contract`](evidence/phoenix-ui/report.md#2-claudecodex-plugin-skill-and-cli-contract), [`3. Harbor evaluation meaning`](evidence/phoenix-ui/report.md#3-harbor-evaluation-meaning), [`4. Borrow list for a local Styrir HTML dossier`](evidence/phoenix-ui/report.md#4-borrow-list-for-a-local-styrir-html-dossier), and [`5. Proof gaps`](evidence/phoenix-ui/report.md#5-proof-gaps) sections. The compact [`summary.txt`](evidence/phoenix-ui/summary.txt) preserves the live-SPA/no-static-export, MCP/CLI/skills, and Harbor conclusions in abbreviated form.

## License observations and unresolved discrepancy

The architecture report records the root `arize-phoenix` package and Python `arize-phoenix-evals` as Elastic License 2.0, with an `IP_NOTICE` naming Arize and US patents 11,315,043 and 11,615,345. It records Python `arize-phoenix-otel` and `arize-phoenix-client` as Apache-2.0 in package metadata and `LICENSE` files while their package `IP_NOTICE` files still state ELv2. That is an observed license discrepancy, **not resolved here** and not a legal determination. The report also notes that JavaScript package metadata and observed license files are not a complete transitive notice/SBOM audit, and that vendor/dependency areas need separate review.

The reports' reuse boundary is correspondingly cautious: they distinguish independent architectural ideas from Phoenix server/UI/database/GraphQL/MCP/PXI implementation and exact Phoenix eval prompt assets, and explicitly leave license resolution to an appropriate legal owner. Read the complete historical [`license matrix and reuse boundary`](evidence/phoenix-arch/report.md#2-license-matrix-and-reuse-boundary) and [`borrow list`](evidence/phoenix-arch/report.md#3-borrow-list-ideaspatterns-versus-copy-code) before using these observations.

## Scope and limitations

- This is **source-only evidence**. The reports state that no Phoenix server was started, no live OTLP/API/MCP request was made, and no evaluator or Harbor run was executed; runtime behavior is therefore **not independently verified**.
- The architecture scout mapped modules rather than exhaustively reading every server/database/UI implementation. The UI scout bounded absence claims to the searched source trees; generated Vite bundles, uninspected revisions, and external hosted deployments were not authoritative evidence.
- The reports state that project-wide tests, formatters, linters, builds, and package-manager actions were not run. This dossier adds no runtime or publication claim.
- “No generic adapter” and “no static exporter” are bounded findings about the inspected paths, not universal claims about all Phoenix versions or deployments.
- Recommendations and implications in the preserved reports remain report observations/inferences, not session-eval requirements. The specification pointer above is the only normative route.
