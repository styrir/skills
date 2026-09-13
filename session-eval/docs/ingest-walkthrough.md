---
summary: Planning-only walkthrough of ingest task acceptance against canonical requirements.
read_when:
  - Starting skills-2ol.2 or evaluating whether its scope is implementation-ready.
---
# Ingest task walkthrough

Task: `skills-2ol.2`. Documentation reconciliation: `skills-2ol.5`. This walkthrough specifies how to evaluate the real task; it does not execute ingestion and contains no passing runtime receipt.

## Fresh-reader route

1. [Index](index.md) establishes authority and the distinction between historical findings and requirements.
2. [Specification](specification.md) assigns SE-PORT-001, SE-INGEST-001/002, SE-EVIDENCE-001, SE-PRIVACY-001 and SE-USAGE-001 to ingestion.
3. [Requirement map](requirement-map.md) connects those IDs to `skills-2ol.2`, operator mirror `ops-4af.9` and downstream consumers.
4. [Skill](../SKILL.md) owns the normalized record; [ingest formats](../references/ingest-formats.md) owns paths, source authority, pairing and privacy.
5. [Format dossier](sources/session-formats/index.md) explains observed formats and sampling limits; [Phoenix dossier](sources/phoenix/index.md) explains identity/lineage inspiration without requiring Phoenix.
6. [Task conformance](task-conformance.md) specifies the evidence needed before closing the Bead.

## What to implement

A shared local ingestion entry point and five format adapters, producing the documented normalized data with source provenance and redacted exports. No report renderer, judge, workflow launcher, server installation, automatic skill edits or provider upload is part of this task. A missing CLI is not replaced by a hand-written passing receipt.

| Requirement | Scenario to execute when implemented | Required observation | Current runtime result |
|---|---|---|---|
| SE-PORT-001 | Ordinary terminal invocation against explicit local input paths with native workflow unavailable | Same normalized contract, no dependency on native extension/Grok host | Not evaluated |
| SE-INGEST-001 | One primary-stream sample per harness, malformed JSONL, unknown event fields, missing requested harness | Five format results plus counted parse errors and explicit coverage gap; indexes never replace streams | Not evaluated |
| SE-INGEST-002 | Nested/child record, continuation/attempt evidence, ended stream with missing result, same missing result in live/unknown stream | Observed lineage retained; ended unpaired identified; EOF alone does not establish terminal state or fabricate edges | Not evaluated |
| SE-EVIDENCE-001 | Same bytes ingested twice, then changed source bytes | Stable identity for same snapshot, new identity for changed snapshot; anchors/parser version retained; no overwritten receipt | Not evaluated |
| SE-PRIVACY-001 | Synthetic secret and HTML-like payload in user/tool content | No secret/raw payload in exported output; source unchanged; source pointers retained and proof loss visible | Not evaluated |
| SE-USAGE-001 | No usage fields; repeated aggregate usage in primary/sidecar streams | Unknown stays unknown; duplicate aggregates do not inflate totals; provenance identifies accounting source | Not evaluated |

## Fixture and evidence boundary

Use synthetic or explicitly authorized local samples; do not commit live session transcripts. The source-format inventory is a design input, not a test fixture. If a harness sample is unavailable, report it as a proof gap and keep that requirement unverified. Canonical documents do not authorize disclosure of user sessions to a provider.

## Completion decision

The documented route gives the implementer scope, non-goals, governing contracts, source rationale and concrete acceptance cases. Actual closure requires those scenarios and recorded output identities pinned to the then-current canonical revision. This tranche checks document links, requirement ownership and source provenance only. It does not close `skills-2ol.2`, `ops-4af.9` or any other runtime task.
