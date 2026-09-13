---
summary: Session-eval adoption decisions and supersession ledger.
read_when:
  - Resolving scope conflicts or proposing a requirement change.
---
# Decisions

Revision 1, reconciled 2026-09-13 under `skills-2ol.5`. The user authorized organizing preserved scouting, reconciling requirements and mapping tasks; this does not authorize runtime execution, automatic corrections or external disclosure. [Specification](specification.md) is the behavioral authority. This ledger records adoption rationale, not fresh findings about third-party products.

| Decision | Disposition | Rationale, source and requirement consequence |
|---|---|---|
| SE-DEC-001 | Adopted | Canonical project-owned document store, organized by source/tool. Research snapshots remain historical; Beads link requirements rather than carry a competing spec. User-approved plan; SE-DOC-001. |
| SE-DEC-002 | Adopted; supersedes Grok launch recipe | Portable skill + shared local CLI, adapters for five harnesses; current implementation in OMP. The earlier `skills-2ol`/`ops-4af.9` Grok WorkGraph ship recipe is superseded in maintained task fields. Historical research snapshots are not rewritten. SE-PORT-001. Phoenix UI report §2 offers integration ideas, not a mandatory host. |
| SE-DEC-003 | Adopted | Local-file-native session/turn/tool/lineage model and immutable source identity. Phoenix architecture §3 items 1–2, 5–7, 10 and §4; local format inventory and second-pass formats. SE-INGEST-001/002, SE-EVIDENCE-001, SE-USAGE-001. |
| SE-DEC-004 | Adopted | Code-first checks plus opt-in evidence-bound retrospective judges. Phoenix architecture §3 items 3–4 and §4; existing check catalog. Keep infrastructure and behavioral failures separate. SE-CHECK-001/002, SE-JUDGE-001. General autonomous repository-policy reconstruction is deferred, not hidden under the checks task. |
| SE-DEC-005 | Adopted | Skill identity/digest, attribution confidence and comparable history. Phoenix architecture §4 skill-history gap and second-pass research; correlation is not causation. SE-SKILL-001, SE-TREND-001. |
| SE-DEC-006 | Adopted | Static offline report with comparisons, structural evidence drilldown and actionable recommendations. Phoenix UI §4 and existing report contract; no copied SPA and no raw conversation embedded. SE-REPORT-001, SE-CORRECT-001. Interactive chart gestures and live streaming remain deferred. |
| SE-DEC-007 | Adopted | Default local/redacted operation. Source pointers rather than exported payloads; explicit recipient/data approval before any external judge. License boundary and Phoenix architecture §4 privacy/provenance. SE-PRIVACY-001. |
| SE-DEC-008 | Optional | ATIF export after normalization; no OTel server prerequisite. Second-pass formats and existing ops-4af.12; SE-EXPORT-001. Requested WorkGraph scoring is delegated, never duplicated; SE-WORKGRAPH-001. |
| SE-DEC-009 | Deferred | PXI-style continuous runner, deterministic sampling, scheduling, retries and admission. Phoenix architecture §3 items 8–9 and §4 reconciliation inspire future work, but a user-invoked retrospective does not require another orchestrator. Revisit with separately approved operating requirements. |
| SE-DEC-010 | Rejected | Phoenix server/UI/evaluator implementation vendoring, required cloud services, automatic skill mutation, duplicated WorkGraph engine. Preserve license/ownership/privacy boundaries; independent implementation. |
| SE-DEC-011 | Unresolved | Python Phoenix client/OTel metadata versus IP_NOTICE discrepancy; third-party parser/license gaps; unsampled Pi-derived schemas. Dossiers preserve the evidence limitations. No dependency adoption, legal clearance or compatibility claim follows from this document. |
| SE-DEC-012 | Adopted | Every implementation task produces a requirement conformance record pinned to canonical revision; documentation checks are not runtime proof. User-approved task-evaluation goal; SE-VERIFY-001 and SE-DOC-001. |
| SE-DEC-013 | Adopted; refines original catalog | Missing evidence is an unknown observation, not a proven behavioral failure, but an unresolved hard gate prevents hard_pass. Missing requested input or infrastructure uncertainty prevents overall success. This replaces the draft's conflation of absent evidence with observed failure without weakening closeout. Recovered attempts are distinct from unresolved failures; a new skill revision is evaluated in a new session, not by rewriting old outcomes. SE-CHECK-001/002, SE-TREND-001 and SE-CORRECT-001. |

## Research coverage

All original research bundles have an explicit use; gate `pass` does not mean all proof gaps were resolved.

| Original bundle | Canonical dossier | Use / disposition |
|---|---|---|
| phoenix-arch | [Phoenix](sources/phoenix/index.md) | Architecture and license boundaries; DEC-003/004/005/007/009/010/011 |
| phoenix-ui | [Phoenix](sources/phoenix/index.md) | Reports, integrations, baseline and drilldown ideas; DEC-002/006; live SPA deferred |
| competitors | [Competitors](sources/competitors/index.md) | Comparative borrow surfaces, not feature parity promises; DEC-004/006/010/011 |
| agent-session-eval | [Competitors](sources/competitors/index.md) | File-native evaluation and trajectory references; DEC-003/004/008 |
| second-pass-licenses | [Competitors](sources/competitors/index.md) | Correct stale paywall claims and retain unresolved reuse limits; DEC-007/010/011 |
| session-formats | [Formats](sources/session-formats/index.md) | Local adapter/pairing evidence; DEC-003 |
| second-pass-formats | [Formats](sources/session-formats/index.md) | Trajectory export, skill provenance and parser gaps; DEC-003/005/008/011 |

The [license boundary](../references/license-boundary.md) is engineering policy, not legal advice. Historical scout summaries may say the scout could not write or run gates; separately saved gate receipts document the parent session's later checks. Neither is silently rewritten.

## Change procedure

A new decision identifies affected requirement IDs, evidence, tradeoff, acceptance change and owning Beads. Update the specification and detailed contracts in the same tranche. Superseded decisions retain their IDs and name replacements. A historical source recommendation is not permission to add scope. Deferred and unresolved candidates need explicit disposition before implementation; do not create runtime shims for stale task instructions.
