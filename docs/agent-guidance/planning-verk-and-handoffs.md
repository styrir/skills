---
summary: "Shared-skills task workflow using Verk contracts, leases, checkpoints and verified receipts."
read_when:
  - "Starting substantive work, planning dependencies or handing off a contract."
  - "Verifying task completion or resolving stale Beads guidance."
---

# Planning, Verk and handoffs

Verk owns durable task state. Beads is decommissioned for this operator. Legacy
Beads files are evidence, not an active tracker or a recovery target. Do not
run bd, restart Dolt for task tracking, import old stores or push task refs.

Read [Verk](../../verk/SKILL.md). Use its session
wrapper from the actual repository. This checkout is already bound to `skills`.

Start with brief, inspect the matching contract, and start it before editing.
Create a new contract only for authorized work that does not already match one.
Break large outcomes into concrete child contracts with explicit prerequisites;
use the actual CLI help for parent/needs flags. Do not treat a title or chat
acknowledgment as acceptance.

A checkpoint records the exact next step, open questions and decisions. It
releases the lease unless --keep. Omitted lists carry forward; clear a list
explicitly when needed. Preserve proof paths and verification limits. If a
lease lapses, re-read and explicitly start before continuing edits.

Verk does not run checks or publish source. Approved checks are produced through
verk-check, on a committed clean tree, and adjudicated against the contract's
policy. A raw passing test or Git commit alone is not a Verk receipt. If unrelated
dirty work or a current no-commit instruction prevents check admission, preserve
that work, run scoped tests as appropriate and checkpoint the remaining gate.
Do not fabricate a close operation or mark the contract satisfied manually.

Operator decisions, setup application, policy approval, review-mode changes,
store freeze/restore and reviewer identity remain outside an author session.
For an unbound repo show a read-only setup plan and the exact operator action;
do not approve it on their behalf.

Git publication is separate. Follow the repository's existing non-force source
publication authority and current user constraints. Never force-push, replace a
remote, absorb unrelated changes or claim publication from a local receipt.
There is no Dolt synchronization step for Verk.

Durable task status belongs in Verk, execution artifacts in .pipeline/ or an
existing ignored workspace, and maintained specifications in docs/. Handoffs
should supplement a checkpoint with only the investigation context it needs.
