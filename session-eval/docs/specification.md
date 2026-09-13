---
summary: Authoritative session-eval ideal state and acceptance requirements.
read_when:
  - Defining, implementing or evaluating session-eval behavior.
---
# Session-eval specification

Contract revision: 1. Scope: local retrospective evaluation of coding-agent sessions and skill revisions. Implementation is tracked in `skills-2ol`; no runtime completion is asserted here. [Index](index.md) defines authority; [decisions](decisions.md) distinguishes adopted scope from research proposals.

## Ideal state

A user selects sessions or a time window and obtains an evidence-linked retrospective: what occurred, what failed, what remains unmeasurable, how skills and runs compare, and what concrete correction to consider. The product must not collapse into an importer with charts, nor pretend observational correlations establish causation.

Portable skill instructions invoke a shared local CLI implementation. Claude, Codex, Pi, OMP and Grok are input formats, not mandatory execution hosts. Implementation currently occurs in OMP. Native extensions are optional conveniences, not a second evaluator or compatibility guarantee. WorkGraph lifecycle control is a different product.

## Requirement semantics

Required = core completion criterion. Optional = implementable without blocking core; once invoked its acceptance applies. Deferred = not authorized for implementation without a new decision. Rejected = outside this product. Unresolved = evidence or decision missing; do not assume support. [Ownership map](requirement-map.md) assigns every Required and Optional row.

Each requirement below includes behavior, evidence/failure boundary and an observable acceptance scenario. All findings follow SE-EVIDENCE-001 and SE-PRIVACY-001. Detailed contracts are normative refinements, not replacements for these requirements.

## Required

| ID | Behavior and acceptance scenario | Governing contract |
|---|---|---|
| SE-DOC-001 | One indexed canonical store with source dossiers, decisions, stable IDs and task links. A fresh reader can follow each requirement to its owner and rationale; conflicting instructions block the affected task rather than being silently selected. | [Index](index.md), [task conformance](task-conformance.md) |
| SE-PORT-001 | Skill + shared CLI usable without OMP native workflow or Grok server. Exercise the eventual CLI from an ordinary terminal on local files; missing dependencies fail explicitly. Pi-derived formats are feature-detected, not assumed identical. | [Skill](../SKILL.md), [ingest](../references/ingest-formats.md) |
| SE-INGEST-001 | Discover and normalize Claude/Codex/Pi/OMP/Grok primary streams, enriching from sidecars. Missing requested harness is a coverage gap, malformed records counted, unknown fields retained privately. Exercise one sample per harness plus malformed/unknown-schema samples; do not replace the primary stream with its index. | [Ingest](../references/ingest-formats.md) |
| SE-INGEST-002 | Preserve event order, tool pairing, observed parent/child/attempt/continuation relationships and explicit terminal/live/unknown state. Exercise nested agents and an unpaired call in ended versus live streams; never invent missing lineage or infer completion from EOF alone. | [Ingest](../references/ingest-formats.md) |
| SE-EVIDENCE-001 | Findings identify source path, snapshot hash, parser version, line/event range and evidence hash. Stable native identity is separate from display names; changed source bytes create a new snapshot. Exercise repeat ingest and changed-file ingest: an identical consumed manifest (paths, roles and bytes) retains snapshot identity; changed manifests cannot overwrite the former receipt. | [Ingest](../references/ingest-formats.md), [report](../references/report-contract.md) |
| SE-PRIVACY-001 | Default local processing; no raw prompts, tool payloads, secrets or terminal output in exported receipts/HTML. Preserve source pointers, redact before serialization, HTML-escape labels. Exercise synthetic secret and markup payloads: output contains neither secret nor executable markup. No provider disclosure without explicit scope/recipient approval; no source mutation. | [Ingest](../references/ingest-formats.md), [judges](../references/judge-contract.md) |
| SE-USAGE-001 | Unknown usage/cost remains unknown, never zero; counts from overlapping streams are not double-counted. Exercise absent usage and repeated aggregate usage records; receipt reports coverage and provenance rather than fabricated totals. | [Ingest](../references/ingest-formats.md) |
| SE-CHECK-001 | Execute the versioned deterministic catalog with evidence-bound results and explicit applicability. Exercise malformed input, repeated failing tool calls, ordinary tool error and unavailable evidence; infrastructure/parse failure is not a behavioral pass. Empty coverage cannot establish successful evaluation. | [Checks](../references/check-catalog.md) |
| SE-CHECK-002 | Evaluate available repository/task evidence for command outcomes and completion-claim contradictions without mutating or assuming present checkout state equals historical state. Exercise a claimed successful check contradicted by recorded exit evidence, and a session lacking that evidence; classify contradiction versus unknown. Reuse WorkGraph scoring only when requested. | [Checks](../references/check-catalog.md) |
| SE-JUDGE-001 | Provide opt-in completeness, grounding, tool-selection and friction rubrics with model/rubric/snapshot identity and anchored explanations. Exercise opt-out with zero provider calls, an authorized judgment and missing-evidence/provider-error cases; latter stay unknown and never become pass. Opt-in execution does not authorize arbitrary external disclosure. | [Judges](../references/judge-contract.md) |
| SE-SKILL-001 | Registry records skill identity/path/content digest and optional version; activation evidence carries source and confidence. Historical loaded digest is distinct from current on-disk digest. Exercise authoritative activation, low-confidence mention, missing skill and edited skill; never attribute current content to a past load without evidence. | [Skill](../SKILL.md), [report](../references/report-contract.md) |
| SE-TREND-001 | Immutable receipts support baseline/candidate comparisons with explicit cohort and coverage, improved/regressed/equal/unmeasurable counts. Different catalogs or incomparable populations cannot silently produce a quality delta; infrastructure failures are separate from behavioral denominators. Exercise two skill revisions, missing usage and incompatible catalogs. | [Report](../references/report-contract.md) |
| SE-REPORT-001 | Emit redacted receipt.json and self-contained offline report.html with verdict, coverage, trends, skills, sessions, failures, comparisons, recommendations and provenance. Bounded drilldown exposes structural lineage/evidence links, not raw transcripts. Open the real report offline and inspect empty, malformed and normal cases. | [Report](../references/report-contract.md) |
| SE-CORRECT-001 | Each actionable finding may yield a concrete first-party skill/adapter proposal with target, rationale, evidence, confidence and verification. Insufficient evidence produces an explicit limitation, not an invented patch. Exercise an evidenced recurring failure and an unmeasurable case; generating recommendations changes no source or skill. | [Report](../references/report-contract.md) |
| SE-VERIFY-001 | End-to-end conformance identifies the canonical revision and evidence for all Required rows; partial execution is not completion. Exercise real ingestion → checks → report → history, with judge execution only under authorization; document unexecuted paths and block unsupported core completion. | [Task conformance](task-conformance.md) |

## Optional

| ID | Boundary and acceptance | Owner contract |
|---|---|---|
| SE-WORKGRAPH-001 | Requested adjunct invokes existing workgraph-eval-score and records its result/errors without duplicating publication rules or reading full.md into reports. Exercise a known failing receipt; failure remains visible. No launching/stopping runs. | [Checks](../references/check-catalog.md) |
| SE-EXPORT-001 | One ATIF document per normalized session against an explicitly pinned schema. Exercise Claude and Grok chronology/identity and validate required fields. No Phoenix/OTel server prerequisite. | [Ingest](../references/ingest-formats.md) |

## Research dispositions beyond core

| Candidate | Disposition | Reason / reconsideration condition |
|---|---|---|
| Host-specific extension commands, hooks, MCP | Deferred | Portable core first; define exact host API and user permission boundary before integration. |
| Continuous online runner, settle scheduling, automatic retries, sampling and admission control | Deferred | Research suggestions, not required for a user-invoked retrospective. Revisit with a separate operational contract. |
| Complete mutable WAL/Beads/Git policy reconstruction and automatic patch correctness judgment | Deferred | Preserve observed evidence now; general policy truth needs versioned policies and historical state unavailable in many logs. SE-CHECK-002 must disclose those gaps. |
| Automatic skill editing or provider uploads | Rejected | Recommendations are read-only; changes/disclosure require separate explicit authority. |
| Phoenix server/UI vendoring, required cloud account, duplicated WorkGraph engine | Rejected | Independent file-native implementation, existing ownership and licensing boundaries. |
| OpenInference/OTel export, live SPA, interactive chart editing | Deferred | Static offline report and optional ATIF satisfy current scope. |
| Disputed package licenses, unverified third-party parser compatibility | Unresolved | Preserve proof gaps in source dossiers; no code reuse or compatibility promise based on search snippets. |

Research provenance: [Phoenix](sources/phoenix/index.md), [competitors](sources/competitors/index.md), [formats](sources/session-formats/index.md). Adoption rationale and superseded host instructions are in [decisions](decisions.md). No disposition deletes historical evidence.
