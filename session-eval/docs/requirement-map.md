---
summary: Stable requirement ownership and implementation dependency map.
read_when:
  - Claiming a session-eval Bead or checking scope coverage.
---
# Requirement ownership

[Specification](specification.md) owns requirements; Beads own live status. This table is not a progress report. Product epic: `skills-2ol`. Operator epic: `agent-ops:ops-4af`. Documentation tranche: `skills-2ol.5`. IDs are never reused.

| Requirement | Disposition | Primary owner | Supporting owners / operator link |
|---|---|---|---|
| SE-DOC-001 | Required | skills-2ol.5 | All task closeouts; ops-4af |
| SE-PORT-001 | Required | skills-2ol.2 | skills-2ol.9 end-to-end proof |
| SE-INGEST-001 | Required | skills-2ol.2 | ops-4af.9 |
| SE-INGEST-002 | Required | skills-2ol.2 | ops-4af.9 |
| SE-EVIDENCE-001 | Required | skills-2ol.2 | skills-2ol.3/6/7 preserve anchors and identity |
| SE-PRIVACY-001 | Required | skills-2ol.2 | skills-2ol.3 renderer escaping, skills-2ol.7 provider boundary, skills-2ol.9 end-to-end proof |
| SE-USAGE-001 | Required | skills-2ol.2 | ops-4af.9 |
| SE-CHECK-001 | Required | skills-2ol.6 | Deterministic check execution |
| SE-CHECK-002 | Required | skills-2ol.6 | Available historical command/task evidence only |
| SE-JUDGE-001 | Required | skills-2ol.7 | Feature required; execution opt-in |
| SE-SKILL-001 | Required | skills-2ol.4 | ops-4af.11 |
| SE-TREND-001 | Required | skills-2ol.4 | skills-2ol.3 renders comparisons; ops-4af.11 |
| SE-REPORT-001 | Required | skills-2ol.3 | ops-4af.10 |
| SE-CORRECT-001 | Required | skills-2ol.8 | skills-2ol.3 renders proposals |
| SE-VERIFY-001 | Required | skills-2ol.9 | Consumes evidence from all Required implementation owners |
| SE-WORKGRAPH-001 | Optional | skills-2ol.6 | Reuse agent-ops workgraph-eval-score |
| SE-EXPORT-001 | Optional | skills-2ol.10 | ops-4af.12; not a core completion blocker |

## Dependency contract

- `skills-2ol.5` reconciles the contracts consumed by implementation.
- `skills-2ol.2` ingestion consumes those contracts.
- `skills-2ol.6` checks, `skills-2ol.4` skill history and `skills-2ol.10` optional export consume normalized ingestion.
- `skills-2ol.7` judges consume the common evaluation-result contract implemented by checks.
- `skills-2ol.8` recommendations consume deterministic findings. Judge findings are optional inputs through that same contract, not a hard scheduling dependency.
- `skills-2ol.3` final renderer consumes checks, skill-history and recommendation outputs. Judge rows render via the shared result contract; judges need not block its implementation.
- `skills-2ol.9` verifies the completed required composition, including the opt-in judge feature. Optional export does not block it.

These are data dependencies, not permission to launch WorkGraph. Implementation occurs through OMP in the skills repository. No dependency on `ops-0iu`, `ops-sud` or `ops-bm7` is introduced.

## Non-required candidates

Deferred/rejected/unresolved research candidates are explicitly listed in [specification](specification.md) and [decisions](decisions.md). They do not need speculative implementation Beads. Promotion requires a decision and ownership mapping before code changes.

## Closeout rule

An operator mirror is satisfied only when the corresponding product behavior has evidence, not merely because this map exists. Completed research/draft tasks remain historical; runtime tasks remain open until their acceptance scenarios pass. Use [task conformance](task-conformance.md) for every claimed completion.
