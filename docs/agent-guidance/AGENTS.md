---
summary: "Index and maintenance rules for the skills repository's progressive-disclosure agent guidance."
read_when:
  - "You are adding, renaming, or removing a document under docs/agent-guidance/."
  - "You need to locate the detailed workflow for Beads, planning, artifacts, handoffs, or closeout."
---

# Agent Guidance DOX

## Purpose

Owns task-scoped operating guidance that would make root `AGENTS.md` too large. Root guidance stays a router; detailed procedures live here.

## Ownership

- Root `AGENTS.md` owns project-wide rules and the top-level task-routing table.
- `docs/AGENTS.md` owns documentation-wide structure and contracts.
- This file owns the routing table and maintenance rules for `docs/agent-guidance/`.

## Local Contracts

- Every guidance document must include YAML `summary:` and `read_when:` frontmatter.
- Keep guidance operational: state when to read it, what authority it has, exact safe commands, and verification steps.
- Do not copy generated Beads blocks into guidance documents; reference `bd prime` for volatile CLI detail.
- Keep machine-specific facts only when they define a durable local operating contract.

## Work Guidance

- Add a new guidance document only when an existing document would become ambiguous or cover an unrelated workflow.
- Update the routing table whenever a guidance document is added, renamed, or removed.
- Correct stale procedures in place instead of surrounding them with historical caveats.

## Verification

- Verify all routing-table paths exist.
- Run `git diff --check` for documentation-only changes.
- For Beads guidance changes, run the connection/configuration checks defined in the Beads runbook.

## Routing Table

| If you are working on... | Read |
|---|---|
| Beads issue lifecycle, the shared Dolt server, first-clone bootstrap, Dolt/Git sync, `.pipeline/` artifacts, handoffs, or session closeout | `planning-beads-and-handoffs.md` |

## Child DOX Index

None. Files here are task-scoped references, not additional owned subtrees.
