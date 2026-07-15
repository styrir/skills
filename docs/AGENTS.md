# Documentation DOX

## Purpose

Owns durable documentation under `docs/`, including implementation plans, review syntheses, and task-scoped agent guidance.

## Ownership

- Root `AGENTS.md` owns project-wide rules and the top-level routing contract.
- This file owns documentation structure below `docs/`.
- `docs/agent-guidance/AGENTS.md` owns progressive-disclosure operating guidance.

## Local Contracts

- Keep durable contracts, decisions, and reproducible evidence here; keep transient execution state in `.pipeline/` and durable task state in Beads.
- Add YAML `summary:` and `read_when:` frontmatter to task-scoped guidance documents.
- Do not duplicate root rules in every document. Route readers to the narrowest applicable source.
- Preserve raw reviewer/model artifacts separately from their synthesis. A synthesis must identify source artifacts and their checksums.
- Avoid volatile inventories unless a document is explicitly an evidence snapshot.

## Work Guidance

- Put implementation specifications under `docs/plans/`.
- Put durable cross-review reconciliations under `docs/reviews/`.
- Put agent operating procedures under `docs/agent-guidance/`.
- Update the Child DOX Index when adding, moving, or removing an owned documentation subtree.

## Verification

- Documentation-only changes: run `git diff --check`.
- Guidance/index changes: verify every routed path exists and the DOX chain is internally consistent.
- JSON examples and machine-readable ledgers must parse with their standard parser.

## Child DOX Index

| Scope | Child DOX | Covers |
|---|---|---|
| `agent-guidance/` | `docs/agent-guidance/AGENTS.md` | Progressive-disclosure workflow, Beads/shared-server operation, planning, artifacts, and closeout. |
