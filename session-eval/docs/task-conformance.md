---
summary: Evaluate every session-eval task against its canonical requirements.
read_when:
  - Starting implementation, reviewing a change or closing a session-eval Bead.
---
# Task conformance

Applies to SE-DOC-001 and SE-VERIFY-001. Read [specification](specification.md), [decisions](decisions.md) and the task's rows in [requirement map](requirement-map.md). This is a human/agent review procedure, not a claim that an automated gate already exists.

## Before implementation

Record the task ID, affected requirement IDs, canonical Git revision, applicable contract paths and acceptance scenarios in the Bead. If contracts are uncommitted, record their SHA-256 digests as well. Read complete governing sections, not only task summaries. Identify historical evidence assumptions and privacy boundaries. A contradictory instruction is a blocker for that behavior until reconciled, not authority to narrow scope.

## During implementation

For a necessary deviation, name the requirement, source evidence, proposed decision and acceptance change. Obtain approval for new scope or consequential actions where required; update the canonical decision, specification, detailed contracts and Bead together. Do not edit historical source snapshots. A code change is not a decision record.

## Verification record

Store task-scoped execution evidence under `.styrir/runs/<run-id>/` in the skills checkout and link it from the Bead. Keep durable curated review findings here only when they are useful beyond that execution. Never make the session transcript the only evidence location.

A conformance record contains:

- Task ID, canonical revision and any uncommitted contract digests.
- Evaluated requirement IDs and exact contract section references.
- Commands/scenarios actually executed, input identity, output/artifact paths and digests.
- For each requirement: expected behavior, observed behavior, result (`pass`, `fail`, `not_evaluated`, or justified `not_applicable`) and limitations.
- Approval references for optional provider use; no credentials or raw sensitive payloads.
- Deviations and links to the decisions resolving them.

| Requirement | Expected behavior | Observed evidence | Result |
|---|---|---|---|
| Applicable stable ID | Contract section and scenario | Actual command/output or artifact, with identity | Explicit result and limitation |

This is a shape definition, not a populated passing receipt. Missing evidence is `not_evaluated`, never pass. Optional invocation can be `not_applicable` when not selected, but an unimplemented Required opt-in feature cannot be waived by switching it off. Tests against mock forwarding or source wording cannot prove runtime behavior.

## Documentation verification

For a documentation-only tranche:

1. Verify every maintained relative document link resolves, including anchors.
2. Parse JSON examples and provenance manifests.
3. Compare each historical snapshot's bytes/digest with the original; report missing originals, do not fabricate verification.
4. Compare the requirement set to the ownership map and actual Bead fields; inspect dependencies for cycles and stale launch instructions.
5. Check that every Required capability has observable acceptance and a concrete owner.
6. Run repository-required whitespace checks on the scoped changes.
7. Walk a real task as a fresh reader. Record documentation readiness separately from runtime execution.

These checks establish documentation integrity only. A correct index or catalog does not prove an evaluator works.

## Runtime verification and closeout

Exercise the actual changed paths. For the engine, use local authorized/synthetic samples that cover meaningful edge cases; do not create files with live secrets. For HTML, open the real generated report and inspect normal/empty/error states offline. For a bug fix, demonstrate the original failure no longer occurs. A missing fixture is a proof gap; it is not a reason to report the harness as supported.

Close a task only when all its applicable requirements are evidenced. For an incomplete task, preserve the evidence and exact outstanding criteria in Beads. Update related contracts in the same tranche, and follow the skills repository Git+Dolt publication policy. Do not close operator mirrors merely because a documentation phase ended. End-to-end closure evaluates every Required row; optional export and deferred research do not gate core completion.
