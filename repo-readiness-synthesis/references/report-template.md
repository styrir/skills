# Report template

Produce the release-readiness synthesis using this structure. Open with a one-paragraph outcome summary that answers:

> Is `{PROJECT_NAME}` close to `{TARGET_MILESTONE}`, and what are the highest-leverage things to do next?

## Artifacts and delivery

The primary artifact is a single document containing all eleven sections below.

- **Format** — Markdown by default. Honor `OUTPUT_FORMAT` if the user set another (docx, PDF, a tracker issue, etc.).
- **File plus summary** — save the full report to `OUTPUT_LOCATION` (the working/output area, not the repo under review; offer to place it in the repo, but do not do so by default). Name it `<project>-<milestone>-readiness.md`, slugified — for example `acme-api-beta-readiness.md`. Also print a short inline summary: the outcome paragraph plus the P0 punch-list items, so the headline is visible without opening the file.
- **Read-only** — writing this report is expected; mutating the repo under review, its tasks, or its docs is not. Render recommended changes as ready-to-apply proposals (below) and apply them only on explicit request.

### Rendering recommendations (sections 5, 6, 8)

Make each recommended change immediately actionable, but never apply it automatically:

- **Tasks (section 5)** — a filled-in issue/ticket for the repo's native tracker: title, labels, and a body carrying the evidence and acceptance criteria, plus the exact create command where the tracker has a CLI or API (`gh issue create ...`, or the Linear/Jira/Beads equivalent).
- **Docs (section 6)** — a unified diff against the target file, or the full proposed file when it is new.
- **Code and tests (section 8)** — a unified diff or minimal patch snippet, clearly marked proposed, not committed.

Every block carries its evidence citation and is copy-paste ready so a human or agent can apply it in one step. Example of a section 5 task rendered ready-to-apply:

```
Title: Add rollback notes to migration 0007
Labels: release-blocker, db
Body:
- Migration 0007 has no down-migration.
  Evidence: db/migrations/0007_add_index.sql
- Acceptance: rollback verified on a staging snapshot.

gh issue create --title "Add rollback notes to migration 0007" \
  --label release-blocker,db --body-file -
```

## The eleven sections

Provide these in order.

## 1. Evidence inspected

List what you actually looked at: tasks, commits, pull requests, sessions/chats/handoffs, docs, and tests or CI. Include anything expected but unavailable, and any tools or sources that were unavailable or skipped. This section is what makes the rest of the report auditable.

## 2. Current state of `{PROJECT_NAME}`

What appears complete; what appears partially complete; what is dark, default-off, experimental, or unvalidated; what is unresolved; what should not be reopened; and what is inferred but not verified.

## 3. `{TARGET_MILESTONE}` definition

Proposed milestone scope and explicit non-goals; required user-visible, operational, and developer/maintainer behaviors; and the evidence required to call the milestone ready. If the repo lacked an explicit milestone definition, state the assumptions you made and label the definition proposed.

## 4. Punch list

Organize by priority:

- `P0` — must do before `{TARGET_MILESTONE}`.
- `P1` — should do before `{TARGET_MILESTONE}` if cheap.
- `P2` — defer until after `{TARGET_MILESTONE}`.

For each item include: task, priority, why it matters, evidence, acceptance criteria, suggested owner or agent role, risks if skipped, and verification method.

## 5. Task tracker reconciliation

Use the repo's native task terminology (title this "Beads reconciliation", "Issue reconciliation", etc. as appropriate). Cover tasks to close, create, update, merge/deduplicate, and leave alone; tasks that should not be reopened; and any task/code/doc/session mismatches. If no formal tracker exists, say so and provide a proposed task list without pretending it already exists. Render each task to create or change as a ready-to-apply issue/ticket block (see Artifacts and delivery).

## 6. Docs reconciliation

Docs that should become canonical; docs to update; docs that are stale or superseded; docs to archive, rename, or mark historical; missing milestone-readiness docs; and docs contradicted by code, tests, tasks, or sessions. Render each doc change as a unified diff or a full proposed file (see Artifacts and delivery).

## 7. Session/chat reconciliation

Decisions found only in sessions/chats; decisions that need materialized tasks; decisions that need canonical docs; decisions contradicted by current repo state; decisions to discard or defer; and session-derived concerns that turned out to be unsupported by evidence.

## 8. Code and test reconciliation

Code paths that appear complete; code paths that are partial or dark; tests that support readiness; tests that are missing; CI status if available; migration or deployment risks; config/flag/environment/compatibility concerns; and code/doc/task mismatches. Render each proposed code or test change as a unified diff marked proposed, not committed (see Artifacts and delivery).

## 9. Milestone gate checklist

A compact, verifiable checklist rendered as Markdown checkboxes (`- [ ]`) so it can be pasted straight into an issue or PR and checked off. It should be usable as the actual release/beta/launch/migration/demo gate. Avoid vague gates like "make it robust." Prefer concrete, checkable gates, for example:

- "Command X succeeds on fixture Y."
- "Migration Z has rollback notes."
- "Feature flag A defaults to B in environment C."
- "Issue #123 is closed with acceptance evidence."
- "Doc D reflects the current code path."

## 10. Recommended next execution plan

The first 3–7 concrete actions: the order to do them in, which can run in parallel, which need reviewer/critic/architecture/QA/human verification, which should produce task updates, which should produce doc updates, and which should produce tests or CI evidence.

## 11. Final verifier notes

What the verifier challenged; what changed after verification; what was removed as overreach; what remains uncertain; what could not be verified; and what should be revisited only if new evidence appears.

---

## Evidence citation style

Cite evidence with the most stable reference available: file path and line range, commit SHA and title, PR number, issue/bead/ticket ID, test command and result, CI run identifier, doc title and path, or session/handoff file path. Examples:

- `Evidence: docs/release/beta.md lines 42–58`
- `Evidence: commit abc1234, "Add migration dry-run mode"`
- `Evidence: issue #71 is closed but the linked test is absent`
- `Evidence: .beads/db.json shows task GEFA-42 still open`
- `Evidence: npm test failed in package api with timeout in auth.spec.ts`

If exact line references are unavailable, cite the most precise evidence you have and note that line-level citation was unavailable.

## Style requirements

Lead with the outcome. Be clear, not terse. Avoid dense shorthand, unexplained internal labels, and arrow-chain summaries. Do not expose hidden reasoning — summarize reasoning as evidence-backed conclusions. Write as if the output will be handed directly to an implementation agent, a reviewer or critic, and a human project owner. Use the project's own terminology when evidence supports it, but define any non-obvious terms. Do not assume the reader saw the raw tool output.
