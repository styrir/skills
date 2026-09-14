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
- `skills-2ol.9` verifies the completed required composition, including the opt-in judge feature. Optional export does not block it. User direction for this epic asked the runner to execute both Optional rows as well (ATIF implemented; WorkGraph adjunct implemented) without promoting them to core blockers.

These are data dependencies, not permission to launch WorkGraph. Implementation occurs through OMP in the skills repository. No dependency on `ops-0iu`, `ops-sud` or `ops-bm7` is introduced.

## skills-2ol.9 runner mapping

Executable: `python3 session-eval/scripts/conformance.py --out OUT [--cli PATH] [--judge-evidence RECEIPT]`. Evidence rules: [task conformance](task-conformance.md). This map is ownership, not a PASS table.

| Requirement | Named runnable scenario | Expected observable | Execution owner |
|---|---|---|---|
| SE-DOC-001 | `docs_walk` | Specification, index, decisions, and this map exist; all 15 Required + 2 Optional IDs present | runner |
| SE-PORT-001 | `five_harness` | Shared CLI invoked via ordinary `python3`; missing `session_eval.py` fails explicitly | runner |
| SE-INGEST-001 | `five_harness`, `malformed`, `missing_harness` | Five harnesses found; malformed counted; missing requested harness is a coverage gap | runner |
| SE-INGEST-002 | `nested`, `ended_unpaired`, `live_unpaired`, `eof_unpaired` | Observed lineage retained; ended unpaired `tool.unpaired=fail`; live `not_applicable`; EOF not terminal | runner |
| SE-EVIDENCE-001 | `repeat_ingest`, `changed_ingest` | Identical manifest keeps snapshot identity; changed bytes new snapshot; former receipt not overwritten; finding `snapshot_hash` = aggregate `run.source_snapshot.sha256` | runner |
| SE-PRIVACY-001 | `secret_markup` | Synthetic secret and unescaped markup absent from receipt/HTML | runner structural; parent visual/provider |
| SE-USAGE-001 | `usage_absent`, `five_harness` | Pi usage unknown not zero; Codex repeated aggregates not doubled | runner |
| SE-CHECK-001 | `malformed`, `loop_fail`, `ordinary_error`, `empty` | Parse infra fail; four-call loop fail; single error does not loop; empty `hard_pass=false` | runner |
| SE-CHECK-002 | `claim_contradict`, `claim_completion` | `claim.command_outcome=fail`; `claim.completion=unknown` not `not_applicable` | runner |
| SE-JUDGE-001 | `five_harness`, `judge_evidence` | Default `provider_calls=0`; `--judge-evidence` consumed if present; else unknown never pass | runner consume; parent live judge |
| SE-SKILL-001 | `skill_unchanged`, `skill_edited`, `skill_mention`, `skill_missing` | Unchanged load keeps historical=current; edited load keeps historical≠current; mention is not authoritative; missing skill is explicit | runner |
| SE-TREND-001 | `trend_revisions`, `repeat_ingest` | Comparison object with compatible/unmeasurable; no silent quality delta | runner |
| SE-REPORT-001 | `five_harness`, `empty`, `malformed` | `receipt.json` + `report.html`; required section ids | runner artifacts; parent offline open |
| SE-CORRECT-001 | `recurring_unpaired`, `empty` | Recurring first-party unpaired yields a non-null target/action/rationale/evidence/verification row; empty yields a limitation-only row; sources unchanged | runner |
| SE-VERIFY-001 | all of the above | Canonical revision + every Required row recorded; unexecuted paths documented | runner enumerates; parent epic audit |
| SE-WORKGRAPH-001 | `workgraph` | Existing `workgraph-eval-score` on red-baseline; `hard_pass=false` remains visible; binary not invoked when unrequested | runner |
| SE-EXPORT-001 | `atif_export` | One ATIF document per run for Claude/Grok; pinned ATIF-v1.8 fields; no Phoenix/OTel | runner |

Commands are recorded by the runner when parent executes it. This documentation tranche does not execute those commands.

## Non-required candidates

Deferred/rejected/unresolved research candidates are explicitly listed in [specification](specification.md) and [decisions](decisions.md). They do not need speculative implementation Beads. Promotion requires a decision and ownership mapping before code changes.

## Closeout rule

An operator mirror is satisfied only when the corresponding product behavior has evidence, not merely because this map exists. Completed research/draft tasks remain historical; runtime tasks remain open until their acceptance scenarios pass. Use [task conformance](task-conformance.md) for every claimed completion.
