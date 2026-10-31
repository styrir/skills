---
name: verk
description: Use Verk for durable agent task tracking, resuming contracts, leases, checkpoints, proof and handoffs across local repositories. Use when the user mentions Verk, asks what work is active, or repository guidance calls for task tracking. Beads is decommissioned for this operator; do not run bd or repair or synchronize its stores.
---

# Verk

Verk is the task authority for this operator. It is a local CLI over one SQLite store, normally `~/.verk`, with no server or sync. Work is contracts with acceptance, attempts, leases, checkpoints and receipts. Use its public CLI; never edit its database or fabricate completion.

## Codex desktop

Use the bundled session wrapper for every Verk command:

```sh
python3 <skill-dir>/scripts/verk.py --repo /absolute/project/path brief --json
```

Resolve `<skill-dir>` from this skill's location. `--repo` selects the real repository, not this chat's artifact directory. Read its guidance and the brief before choosing work. The wrapper calls the installed `~/.local/bin/verk` or `verk-check` with argument arrays, preserving quoted text. It sets `VERK_ACTOR=codex:<current-thread>` and `VERK_SESSION` from the host's `CODEX_THREAD_ID` (or `CODEX_SESSION_ID`), rather than acting as the operator. If identity or the executable is missing, stop and report it; do not silently call the CLI as the operator.

This is a chat workflow, not a persistent side panel or an edit-enforcement hook. The packaged plugin adds an opt-in Stop follow-up for explicitly requested closeouts. Read [desktop integration](references/desktop.md) when changing hooks, packaging a plugin, comparing Claude Code/Pi integration, or diagnosing discovery.

## Work lifecycle

Use the wrapper with these Verk arguments; replace example IDs with IDs returned by the CLI.

- Orient: `brief --json`; use `brief --all --json` only when cross-project work matters. Inspect the chosen contract with `view vk-123 --json`.
- Start before editing: `start vk-123 --json`. Resume the existing contract when it matches. For new authorized work, `add "Concrete outcome" --kind code --accept "Observable acceptance" --start --json`. Keep a stable `--idempotency-key` for a retried write; after an uncertain result, inspect state before retrying.
- Keep scope current: `set vk-123 --accept "Updated acceptance" --if-version N`; `need vk-123 vk-122` for a prerequisite. `drop` withdraws work only when the user or current scope authorizes that withdrawal.
- When pausing or handing off: `checkpoint --next "Exact next step" --open "Unresolved question" --decided "Decision and basis" --json`. This releases the lease; `--keep` retains it. Omitted open/decided lists carry forward; use `--open=` or `--decided=` to clear them. An ordinary conversational reply is not necessarily yielding work.
- Ask a judgment question with `ask "Question" --clears-when "Condition" --blocks vk-123 --json`, or `--about vk-123` when work can continue.
- Attach document evidence with checkpoint `--proof repo-relative-path-or-url`. File proof must be inside the actual repository, committed at HEAD and unchanged. Uncommitted or external reports belong in the checkpoint text as pending evidence, not in --proof. Proof does not manufacture a receipt or replace a required check.
- Code checks: inspect the contract's approved policy, then use wrapper `check test --id vk-123` (the `check` wrapper route calls `verk-check`). Required check names come from `view`, never a guessed command. Evidence requires a committed, clean worktree. Preserve unrelated changes; if a clean tree or commit is unavailable, run appropriate raw tests, report their result separately and checkpoint the proof gap. Do not label the contract satisfied without a Verk receipt.

If a lease lapses, re-read the contract and explicitly `start` it again before editing. Do not infer a live lease from a prior successful call. Existing repository publication rules and the user's current instructions still govern commits and pushes; Verk does not add publication authority.

## Close ready work

Before implementation, identify which acceptance clauses need source checks,
installed behavior, live interaction or operator confirmation. Record evidence
as it is observed, including failures and remaining limits. Before review,
commit a concise qualification record for every non-source acceptance clause:
diagnosis and basis, source revisions/check results, installed artifact identity,
observed live results, separately labeled operator confirmations, and unresolved
limits. Do not copy raw captured content, screenshots, secrets or private paths.
The independent reviewer must receive this record at the reviewed revision;
chat-only claims and a passing unit test are insufficient for live acceptance.
Use the [qualification evidence guide](references/qualification.md) to collect it.

After committing and checking the work, run:

```sh
python3 <skill-dir>/scripts/closeout.py --repo /absolute/project/path --id vk-123 --qualification path/to/committed/qualification.md --wait 30
```

For acceptance confined to source behavior, explicitly use `--source-only`
instead, with `--proof path/to/committed/file` for review-only code. The helper
requires this choice before submitting ready work; it does not guess from prose.

The helper runs approved checks unless a current-HEAD review already covers them through `verk-check`, or attaches committed path proof when the current policy is review-only, then calls `reconcile`. An empty checks list is valid: it does not prevent independent review or a receipt. Do not invent a check, change policy, or approve your own review to close work.

Read the structured outcome. `receipt` names a receipt covering current HEAD. `review_pending` means the existing independent reviewer still has work; wait or inspect the review, repair findings and request closeout again. `needs_action` and command errors remain unfinished. Exit 3 means pending/action needed, not success. Tests, commit, source publication, installation and live acceptance remain separate evidence.

The declaration and committed proof paths are recorded in Verk before checks or review.
Only the latest pending explicit request leaves a session-scoped marker in `~/.cache/verk-closeout/`. A newer pending closeout supersedes the previous hook request; Verk retains both tasks. The plugin Stop hook consumes it once, refuses changed/dirty work and reports the current result. It never runs tests at Stop, answers reviews, changes policy or starts a permanent service. Ordinary turns with no request do nothing. Hook trust is the operator's action; if the host has not loaded/trusted the hook, use the foreground helper and report that qualification limit. The marker/result files are disposable requests and observations; Verk remains the authority.

## Operator boundaries

The wrapper deliberately refuses `answer`, `bind`, `snapshot`, `migrate`, and setup `--apply`. These are outside an ordinary author session. Do not change review mode, approve policy, freeze or restore the store, answer the operator's decisions, or grant yourself a reviewer identity. Show the decision or setup plan to the operator instead. This wrapper does not serve designated reviewer sessions.

For an unbound repository, wrapper `setup --json` is a read-only plan. Show what it proposes and leave the apply action to the operator. A setup request is not permission to approve policy on their behalf.

Beads guidance in older AGENTS files is stale for this operator. Do not run `bd`, Dolt recovery/sync, automatic imports or a competing tracker. Preserve legacy evidence; use Verk's current binding and policy. Report actual refusals and their next step without bypassing them.
