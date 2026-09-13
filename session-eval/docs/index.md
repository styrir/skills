---
summary: Canonical session-eval document store, authority and navigation.
read_when:
  - Starting or reviewing any session-eval task.
---
# Session-eval canonical document store

This project owns the portable session-retrospective skill and its supporting local implementation. Product epic: `skills-2ol`; operator/research epic: `agent-ops:ops-4af`. Documentation reconciliation: `skills-2ol.5`. This store specifies intended behavior; it is not evidence that the runtime is implemented.

## Authority

1. [Specification](specification.md): required behavior, scope, acceptance and stable requirement IDs.
2. [Decisions](decisions.md): rationale, dispositions and explicit supersession. Changes to decisions and affected requirements must land together.
3. Detailed [ingest](../references/ingest-formats.md), [checks](../references/check-catalog.md), [judges](../references/judge-contract.md), [report](../references/report-contract.md), and [license](../references/license-boundary.md) contracts refine the specification; they cannot override it silently.
4. [SKILL.md](../SKILL.md): operating entry point, not a second requirement store.
5. [Task conformance](task-conformance.md) and [requirement ownership](requirement-map.md): how Beads deliver and verify the contracts.
6. Source dossiers below: non-normative findings, not automatic product commitments.

If two maintained documents disagree, report the conflict and reconcile them before implementing the affected behavior. Do not choose the easiest interpretation. Bead notes, historical research, examples and code cannot silently amend normative requirements. Beads own live status; tables here own requirement-to-task relationships, not volatile completion counts.

## Source dossiers

| Dossier | Evidence grouped here |
|---|---|
| [Phoenix](sources/phoenix/index.md) | Pinned clone architecture, evaluator model, UI/integrations and source-reuse limits |
| [Competitors and agent-evaluation research](sources/competitors/index.md) | Online comparison, agent-session evaluation, second-pass license research |
| [Session formats](sources/session-formats/index.md) | Local harness inventory and online second-pass trajectory research |

Each dossier has a provenance manifest and exact historical evidence snapshots. The original operator run is `~/Code/agent-ops/.styrir/runs/2026-09-13-session-obs/`; it remains unchanged. Snapshots are intentionally retained for portability and must not be edited as maintained guidance. New research gets a new provenance record. Gate receipts record past checks, not fresh validation or resolution of every proof gap.

## Maintenance

Organize knowledge by owning project, then source/tool. Keep one maintained home per contract; link rather than copy it to harness directories or other repositories. A shared source dossier may later have one shared owner, but project adoption decisions stay here. Do not create a second store during this tranche or change styrir-init templates.

Every behavioral task cites requirements and records the canonical Git revision (plus file digests for uncommitted changes). A proposed change requires a decision entry, affected contracts, ownership mapping and acceptance updates in the same tranche. Never recycle a requirement ID; superseded requirements point to their replacements.

See the [ingest planning walkthrough](ingest-walkthrough.md) for an example that distinguishes documentation readiness from unexecuted runtime evidence.
