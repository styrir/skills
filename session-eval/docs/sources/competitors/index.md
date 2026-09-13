---
summary: Historical competitor and agent-evaluation research bundles preserved for session-eval source review.
read_when:
  - Reviewing preserved competitor, evaluator, licensing, or hosted-boundary evidence before applying the canonical session-eval specification.
---

# Competitor source dossiers

The [session-eval specification](../../specification.md) is the normative authority. This page is a navigation index for historical evidence only; it does not replace or amend that specification. The source bytes below are snapshots from the 2026-09-13 session-observation run and must not be treated as a competing maintained specification.

## Source identity and evidence class

All three bundles were captured from `/Users/brooks/Code/agent-ops/.styrir/runs/2026-09-13-session-obs/` and are preserved without source-file edits. The evidence classes are intentionally separate:

| Bundle | Source identity | Evidence class | Scope recorded by the bundle |
|---|---|---|---|
| [`competitors`](evidence/competitors/) | `.../session-obs/competitors` | Online bounded StyrirSearch:plus evidence, with separately identified local reads | Eight searches and ten successful external reads covering competitor products; pinned Phoenix and installed Langfuse metadata were local reads excluded from the external-fetch count. |
| [`agent-session-eval`](evidence/agent-session-eval/) | `.../session-obs/agent-session-eval` | Online bounded StyrirSearch:plus evidence | Eight searches and ten fetched official/repository sources covering agent-evaluation harnesses, trajectory viewers, and static dashboards. |
| [`second-pass-licenses`](evidence/second-pass-licenses/) | `.../session-obs/second-pass-licenses` | Online bounded StyrirSearch:plus evidence, with separately identified local reads | Eight searches and ten external reads for license/open-core boundaries; local Phoenix README/LICENSE/comparison/IP_NOTICE reads and title-only patent discovery are recorded separately in the source registry. |

The online bundles contain source registries and ledgers identifying fetched URLs. Local observations are not silently presented as online evidence: each local source is marked `sourceType: local` in the preserved registry.

## `competitors` bundle

### Preserved files

| File | Role |
|---|---|
| [`architecture.txt`](evidence/competitors/architecture.txt) | Historical architecture synthesis. |
| [`contradiction-sweep.md`](evidence/competitors/contradiction-sweep.md) | Historical OSS/source-available/hosted-boundary sweep and residual gaps. |
| [`gate-result.json`](evidence/competitors/gate-result.json) | Saved historical gate result: `pass`, 83 entries, 14 sources, 10 proof gaps; not rerun for this snapshot. |
| [`ledger.json`](evidence/competitors/ledger.json) | Historical evidence ledger, proof gaps, and source records. |
| [`plan.json`](evidence/competitors/plan.json) | Historical bounded-search plan and accounting. |
| [`request.json`](evidence/competitors/request.json) | Historical research request and source-scope metadata. |
| [`source-registry.json`](evidence/competitors/source-registry.json) | Historical registry for ten external and four local source records. |
| [`summary.txt`](evidence/competitors/summary.txt) | Historical run summary and external/local read accounting. |

### Observed findings

- The preserved architecture groups evidence into self-hostable platforms, local evaluator/SDK layers, and agent-facing connectors; it records a file-native normalization, evaluator, and HTML/report direction while marking Phoenix's ELv2 hosted-service boundary.
- The contradiction sweep records Phoenix as source-available/self-hostable rather than a permissive dependency for a competing hosted service, and records unresolved or narrowed claims for Langfuse, Ragas, and Helicone.

### Limits and proof gaps

The bundle's own [`contradiction-sweep.md`](evidence/competitors/contradiction-sweep.md) and [`ledger.json`](evidence/competitors/ledger.json) are authoritative for its unresolved items. They include reserved follow-ups for first-party Langfuse licensing/self-hosting, Helicone feature evidence, OpenLLMetry/Traceloop terms, Weave reporting/self-managed terms, Promptfoo and Ragas/TruLens session/report details, Evidently agentic tracing schema, and independent license review. The saved gate warning notes that some observations may bundle multiple facts. No follow-up research is added here.

## `agent-session-eval` bundle

### Preserved files

| File | Role |
|---|---|
| [`contradiction-sweep.md`](evidence/agent-session-eval/contradiction-sweep.md) | Historical harness-specific versus general-boundary sweep. |
| [`gate-result.json`](evidence/agent-session-eval/gate-result.json) | Saved historical gate result: `pass`, 48 entries, 10 sources, 5 proof gaps; not rerun for this snapshot. |
| [`ledger.json`](evidence/agent-session-eval/ledger.json) | Historical evidence ledger, proof gaps, and source records. |
| [`plan.json`](evidence/agent-session-eval/plan.json) | Historical facet plan. |
| [`request.json`](evidence/agent-session-eval/request.json) | Historical research request and source-scope metadata. |
| [`source-registry.json`](evidence/agent-session-eval/source-registry.json) | Historical registry for ten fetched official/repository sources. |

### Observed findings

- The preserved contradiction sweep separates native log ingestion from normalized reporting, raw-trace viewers from quality reports, Harbor artifact presence from trial score, and benchmark-specific submission policy from generic checks.
- It records `eval-report/v1` rows and suite manifests as a check-taxonomy reference, with eval-dashboards and source-specific viewers as distinct report surfaces.

### Limits and proof gaps

The bundle's [`contradiction-sweep.md`](evidence/agent-session-eval/contradiction-sweep.md) and [`ledger.json`](evidence/agent-session-eval/ledger.json) record that native Claude Code, Codex, Pi, and Grok schemas and community-analyzer licenses were not established by this fetch set; Inspect, SWE-bench/Terminal-Bench licensing, direct raw-session ingestion by eval-dashboards, and cross-harness score equivalence remain gaps. Search snippets were discovery only and were not used as evidence. No follow-up research is added here.

## `second-pass-licenses` bundle

### Preserved files

| File | Role |
|---|---|
| [`architecture.txt`](evidence/second-pass-licenses/architecture.txt) | Historical license/open-core architecture synthesis. |
| [`contradiction-sweep.md`](evidence/second-pass-licenses/contradiction-sweep.md) | Historical license, open-core, and patent proof-gap sweep. |
| [`gate-result.json`](evidence/second-pass-licenses/gate-result.json) | Saved historical gate result: `pass`, 44 entries, 14 sources, 8 proof gaps; not rerun for this snapshot. |
| [`ledger.json`](evidence/second-pass-licenses/ledger.json) | Historical evidence ledger, proof gaps, and source records. |
| [`plan.json`](evidence/second-pass-licenses/plan.json) | Historical bounded-search plan and accounting. |
| [`report.md`](evidence/second-pass-licenses/report.md) | Historical second-pass report with inline plan, registry, ledger, and contradiction artifacts. |
| [`request.json`](evidence/second-pass-licenses/request.json) | Historical research request and source-scope metadata. |
| [`source-registry.json`](evidence/second-pass-licenses/source-registry.json) | Historical registry for ten external/legal and four local source records. |
| [`summary.txt`](evidence/second-pass-licenses/summary.txt) | Historical run summary and external/local read accounting. |

### Observed findings

- The preserved sweep resolves the Phoenix comparison claims in favor of current first-party Langfuse pages for Playground and LLM-as-a-judge, while retaining a deployment-architecture concern and narrowing the instrumentation claim.
- It records Inspect AI and OpenLLMetry as permissive license evidence, Langfuse as MIT outside explicitly marked EE paths, Helicone as Apache-2.0 with feature gaps, and a Ragas README versus agent-evals guide release-status conflict.
- The patent entries are explicitly title-only discovery records; the direct Google Patents record pages remain a gap, with no abstract, claim, scope, or legal conclusion asserted.

### Limits and proof gaps

The bundle's [`contradiction-sweep.md`](evidence/second-pass-licenses/contradiction-sweep.md), [`ledger.json`](evidence/second-pass-licenses/ledger.json), and [`report.md`](evidence/second-pass-licenses/report.md) retain all eight proof gaps and the legal/patent boundary. In particular, the fetched evidence does not establish Traceloop platform terms, Helicone feature/session/evaluator/HTML parity, or direct patent records. The saved gate result is historical and was not rerun. No legal conclusion or new research is added here.

## Provenance

[`provenance.json`](provenance.json) is the dossier manifest with schema `session-eval-source-provenance/v1`. It records 23 preserved regular files, each original absolute path, relative snapshot path, byte count, and SHA-256 digest. The manifest and snapshots are evidence receipts, not normative requirements.
