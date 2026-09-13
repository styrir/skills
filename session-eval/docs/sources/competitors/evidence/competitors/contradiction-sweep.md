# Contradiction sweep: OSS, source-available, and hosted boundaries

## Scope and classification rule

This sweep distinguishes a permissive license from a product's marketing use of “open source.” It also separates an OSS SDK or instrumentation layer from a self-hostable backend and from a hosted-only control plane. Product claims are quoted as observations; the implications below are working classifications for the Styrir skill, not legal advice.

## Resolved or mostly resolved boundaries

### Phoenix: open-source label versus Elastic License 2.0

- The pinned Phoenix README calls Phoenix an open-source AI observability platform and documents local, containerized, and cloud deployment [s11].
- The pinned LICENSE is Elastic License 2.0 and grants use, copying, distribution, and derivative-work rights subject to limitations [s12].
- The same LICENSE prohibits providing the software to third parties as a hosted or managed service when users receive access to a substantial feature set [s12].
- Opik's comparison table independently labels Phoenix source-available under ELv2 and not OSI-approved [s3].

**Working classification:** Phoenix is self-hostable and source-available, not a permissive OSI-licensed dependency for a competing hosted service. Do not recommend vendoring Phoenix as a hosted Styrir product. It can remain a separately deployed reference or integration target only after the applicable license boundary is reviewed.

### OpenLLMetry versus Traceloop platform

- OpenLLMetry's official introduction describes an open-source, OpenTelemetry-based instrumentation project and says traces can go to Traceloop or an existing observability stack [s8].

**Working classification:** Treat OpenLLMetry as an instrumentation/export layer. Do not infer that the Traceloop destination or dashboard has the same license or self-hosting rights; that remains a proof gap.

### Weave SDK versus W&B platform

- The Weave README metadata reports Apache 2.0 and describes the public toolkit's tracing and evaluation API [s9].
- The README requires a Weights & Biases account for its quick start [s9].
- Opik's comparison table labels Weave an open-source SDK/toolkit but says the self-managed platform requires a commercial license [s3].

**Working classification:** Record Weave as an OSS SDK/toolkit with a separate platform/self-managed licensing question. Do not advertise a free self-hosted Weave backend based only on the SDK README.

### LangWatch core versus enterprise modules

- LangWatch's introduction calls the product open source, says the core is Apache 2.0 and self-hostable, and points enterprise features to a separate license under `platform/app/ee` [s2].

**Working classification:** Reuse or emulate the Apache core surface only. Keep enterprise governance and identity features outside an OSS borrow list until separately reviewed.

### Evidently OSS versus Cloud extras

- Evidently's README describes an Apache-licensed OSS library and self-hostable OSS monitoring UI [s10].
- The same README assigns dataset/user management, alerting, and no-code evaluations to Evidently Cloud extras [s10].

**Working classification:** Borrow the OSS Reports, Test Suites, HTML export, and local UI; do not silently include Cloud-only collaboration or alerting features in the first-party scope.

## Unresolved contradictions requiring follow-up

### Langfuse current overview versus Phoenix comparison page

- Current Langfuse documentation calls Langfuse open source, self-hostable, and extensible, and lists production-trace scoring, LLM-as-a-judge, code evaluators, manual labels, datasets, experiments, dashboards, sessions, agent graphs, and an Agent Skill/CLI/MCP surface [s1].
- A local Phoenix comparison page claims Langfuse places Prompt Playground and LLM-as-a-Judge behind a paywall, requires ClickHouse/Redis/S3 for self-hosting, and relies on outside instrumentation [s14].
- The local comparison page has no publication or version marker. The current overview does not state the exact platform license split. An installed Langfuse Python SDK package is MIT [s13], while Opik's comparison table labels Langfuse's core MIT with commercial enterprise modules [s3].

**Status:** Unresolved. The evidence is temporally and perspectivally mixed. Use the current Langfuse overview for the listed feature surface with a license caveat, and do not repeat the Phoenix page's paywall or hosting claims as current fact until direct version-pinned Langfuse licensing and self-hosting pages are fetched.

### Ragas README versus Phoenix Ragas integration

- The current fetched Ragas README lists `agent_evals` under Coming Soon [s5].
- The local Phoenix Ragas guide demonstrates tool-call accuracy and agent-goal accuracy metrics in an agent evaluation [s14].

**Status:** Unresolved version or package-boundary conflict. Treat the current Ragas README as the narrower present claim and keep the Phoenix integration as evidence that an integration path exists, not proof that the complete agent-evals template is currently shipped.

### Helicone feature surface

- The fetched Helicone page establishes Apache 2.0 and a self-hosting/contribution rationale [s7].
- That page does not establish the tracing, evaluator, dashboard, HTML, or coding-agent-session details requested for the comparison.

**Status:** Unresolved evidence gap, not a negative feature finding. A feature-level Helicone README/docs fetch is reserved for a follow-up run.

## Proof gaps and reserved follow-ups

1. Fetch first-party Langfuse licensing and self-hosting pages and pin the product version/date.
2. Fetch Helicone README/tracing/evaluation/UI pages.
3. Fetch OpenLLMetry repository LICENSE and Traceloop platform/self-host terms.
4. Fetch first-party W&B Weave self-managed terms and HTML/report docs.
5. Fetch Promptfoo report export and agent/session docs.
6. Fetch current Ragas and TruLens docs for agent sessions, backend deployment, and HTML export.
7. Verify whether Evidently's `agentic_systems_tracing.ipynb` exposes a stable session schema.
8. Obtain an independent license review if the Styrir skill will distribute or host any third-party code.

## Bottom line

The strongest borrowable permissive surfaces are Opik's full self-hosted platform and MCP/coding-agent integrations, LangWatch's Apache core and per-session coding-agent reporting, Evidently's HTML Reports and Test Suites, Promptfoo's local eval/web-viewer/red-team loop, TruLens's OTEL step spans and agent evaluators, Ragas's metrics/test generation, and OpenLLMetry's vendor-neutral export. Phoenix remains a useful functional reference but its ELv2 hosted-service restriction is a hard boundary.
