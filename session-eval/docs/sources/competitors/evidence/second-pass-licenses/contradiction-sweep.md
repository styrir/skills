# Contradiction sweep: license, open-core, and patent proof gaps

## Langfuse versus the pinned Phoenix comparison

| Claim in pinned Phoenix page | Current fetched evidence | Status for the report |
|---|---|---|
| Langfuse puts Prompt Playground behind a paywall | Langfuse's handbook lists the playground as MIT-licensed [s4]. Self-hosted pricing lists Playground as Open Source = Yes [s5]. | Resolved in favor of the current first-party pages. The Phoenix page has no publication or version marker and should not be repeated as current fact. |
| Langfuse puts LLM-as-a-Judge behind a paywall | Langfuse's handbook lists evaluations as MIT-licensed [s4]. Self-hosted pricing lists LLM-as-judge evaluators as Open Source = Yes [s5]. | Resolved in favor of the current first-party pages. |
| Langfuse requires ClickHouse, Redis, and S3-compatible storage | Langfuse's current handbook architecture names ClickHouse, Redis/Valkey, and S3/blob storage as the self-host stack [s4]. | Broadly corroborated as an architecture/deployment concern, not a license contradiction. Exact required-versus-optional details remain version-sensitive. |
| Langfuse relies on outside instrumentation libraries | Current self-host pricing lists native framework integrations, Python/JavaScript SDKs, OpenTelemetry, LiteLLM proxy logging, and a custom API [s5]. | Narrowed rather than fully resolved. The current table does not establish whether Langfuse maintains first-party auto-instrumentation for every provider, so avoid an absolute either/or claim. |

## Open-source labels versus legal boundaries

- Phoenix's pinned README uses the open-source label [s11], while its pinned LICENSE is Elastic License 2.0 [s12] and prohibits offering a substantial feature set as a hosted or managed service [s12]. Treat Phoenix as source-available/self-hostable, not as a permissive dependency for a competing hosted Styrir service.
- Langfuse's root LICENSE is mixed: MIT Expat outside the explicitly marked EE paths and `ee/LICENSE` inside those paths [s3]. Its current handbook says core tracing, evaluations, prompt management, experiments, annotation, and playground are MIT, while SCIM, audit logging, and data retention policies require a commercial license [s4]. Use the precise label “MIT-core with commercial EE modules,” not an unqualified whole-monorepo MIT claim.
- OpenLLMetry's repository is Apache-2.0 and is an OpenTelemetry instrumentation/export layer [s2]. The fetched source does not establish the Traceloop destination/platform license or self-hosting rights. Do not infer platform rights from the SDK/repository license.
- Helicone's fetched official page states Apache-2.0 and supports a self-hosting posture [s6]. The fetched deployment overview proves Manual, Docker Compose, Kubernetes, and cloud deployment methods [s7] but does not prove feature parity, session support, evaluator execution, or static HTML output.

## Ragas agent_evals status

The Ragas repository README marks `agent_evals` as Coming Soon [s8], while the current official guide supplies `ragas quickstart agent_evals`, a math-agent evaluation, a binary correctness metric, and datasets/experiments/logs structure [s9]. Record this as a documentation/release-status contradiction. Borrow the template structure and metric idea, but do not call the template a stable released surface until a versioned CLI/release check resolves the conflict.

## Patent title-only record

Phoenix's IP_NOTICE names U.S. Patent Nos. 11,315,043 and 11,615,345 [s14]. The fetched combined Google Patents query returned only the generic shell [s10]. Search discovery reported the same title for both requested records:

- **US 11,315,043 — Systems and methods for optimizing a machine learning model**
- **US 11,615,345 — Systems and methods for optimizing a machine learning model**

These are title-only provisional entries from search discovery, not fetched patent records. Direct record pages remain an explicit gap: `https://patents.google.com/patent/US11315043/en` and `https://patents.google.com/patent/US11615345/en`. No abstract, claim, scope, or legal conclusion is asserted.

## Compact decision table

| Entity | License / proof | Self-host, UI, eval, session status | Borrowable surface and boundary |
|---|---|---|---|
| Inspect AI | MIT in raw LICENSE [s1] | Harness role, output/HTML, and agent-session support were not established by the fetched license-only source | Re-check repository/package docs before borrowing; MIT notice retention applies. |
| OpenLLMetry / Traceloop | OpenLLMetry repository Apache-2.0 [s2]; Traceloop destination/platform terms are a proof gap | OTEL instrumentation/export is documented; no UI or static HTML proof in fetched source | Borrow vendor-neutral span/export boundary; do not assume Traceloop platform rights. |
| Langfuse | MIT outside marked EE paths; EE paths use `ee/LICENSE` [s3] | OSS self-host includes agent traces/graphs, sessions, Playground, LLM-as-judge, custom dashboards, unlimited usage [s4][s5]; Assistant marker is `--` in both self-host columns [s5] | Strong borrow reference for session/trace/eval/dashboard schema; keep EE governance modules and static HTML semantics separate. |
| Helicone | Apache-2.0 [s6] | Manual, Compose, Kubernetes, and cloud self-host methods [s7]; feature/session/evaluator/HTML details remain gaps | Borrow deployment choices and explicit OSS boundary; fetch feature pages before claiming parity. |
| Ragas | Apache-2.0 repository metadata [s8] | Agent-evals guide exists [s9], but README says Coming Soon [s8]; no UI/static HTML proof | Borrow local agent.py/evals.py plus datasets/experiments/logs and binary correctness; treat release status as unresolved. |
| Arize Phoenix baseline | README says open-source [s11], but LICENSE is ELv2 with hosted-service restriction [s12] | Local comparison reference only | Do not vendor Phoenix into a hosted Styrir product. |
| Patent records | Title-only search discovery; direct Google Patents fetch gap [s10][s14] | Not applicable | Retain numbers and titles only; no claim/abstract reuse. |
