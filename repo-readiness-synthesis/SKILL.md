---
name: repo-readiness-synthesis
description: Synthesize a repo's tasks, commits, sessions, and docs into an evidence-grounded release-readiness punch list. Use when judging whether a project is ready to ship a release, beta, launch, or migration, or what's left before shipping.
---

# Repo Readiness Synthesis

Synthesize the recent state of a repository into a grounded punch list of what must happen to make a target milestone real. The deliverable is a synthesis and prioritized punch list, not a rewrite of the architecture.

This skill is repo-agnostic. Do not assume any specific product, architecture, task tracker, release name, or domain model unless the user provides it or you find it in repository evidence. When in doubt, discover it from the repo and state plainly what you could not determine.

## When to use this

Use this whenever someone wants to know if a project is close to a release, beta, launch, demo, migration, or any readiness target, and what the highest-leverage next steps are. Typical phrasings: "are we ready to ship?", "what's left before the beta?", "do a readiness review", "give me a punch list", "what are the blockers for the launch?".

## Invocation inputs

Infer these from the repo where possible; ask the user only when an input is genuinely required and cannot be discovered. State explicitly anything you could not determine.

- `PROJECT_NAME` — the project or repo name.
- `REPO_PATH` / `REPO_IDENTIFIER` — local path, GitHub repo, or workspace identifier.
- `TARGET_MILESTONE` — the release, beta, version, launch, demo, migration, or readiness target being evaluated. If undefined, propose a minimal one (see below) and label it proposed.
- `PRIMARY_BRANCH` / `ACTIVE_BRANCH` — default branch and current working branch, if relevant.
- `TASK_TRACKER` — the system this repo uses: Beads, GitHub issues, Linear, Jira, TODO docs, project boards, local issue files, etc.
- `PROJECT_CONTEXT` — standing architectural or product constraints supplied by the user or found in canonical docs.
- `KNOWN_RESOLVED_WORK` — work that should not be reopened unless new evidence proves a regression.
- `IMPORTANT_PATHS` — known locations for docs, sessions, handoffs, memory, agent notes, task files, or generated artifacts.
- `OUTPUT_FORMAT` — deliverable format; defaults to Markdown. Override for docx, PDF, a tracker issue, etc.
- `OUTPUT_LOCATION` — where to write the report; defaults to the session's working/output area, not the repo under review.

## How to run the review

Gather evidence across four sources (below), reconcile them against each other, then produce the report described in `references/report-template.md`. Prefer built-in project, repository, and semantic search tools over raw shell `grep`/`ls`/`sed` when better repo-aware tools exist.

Run the four evidence passes plus a final verification pass. If subagents are available, delegate each pass to a subagent and work in parallel; if not, do the passes yourself and say the review was single-agent. See "Subagent orchestration" below.

Proceed end to end. Do not ask whether to continue once you have enough information. Pause only when the work genuinely requires user-only input, a credential or access grant, a destructive action, a real scope change, or a choice between incompatible product directions with no deciding evidence.

## Evidence sources to examine

For each source, note what you inspected and what was expected but unavailable — that record becomes the "Evidence inspected" section of the report.

### 1. Task state

Inspect the project's active task system, whatever it is. Use the repo's native terminology in the final answer (say "beads" if it uses Beads, "issues" if GitHub issues; reconcile if it uses several).

Look for open, recently closed, blocked, stale, duplicated, or ambiguous tasks; tasks implying unfinished product, technical, migration, or operational decisions; tasks that appear already resolved and should not be reopened; and missing tasks implied by code, docs, tests, sessions, or release criteria. Determine which items are milestone blockers, which are post-milestone follow-ups, and which are no-ops. Flag task/code/doc/session mismatches and tasks that need clearer acceptance criteria.

### 2. Git commits and code

Inspect recent activity relevant to the milestone: commits on the active branch (and primary branch for comparison), commit messages, diffs, changed files, and pull requests / review comments / merge status where available.

Summarize what actually changed. Identify unfinished code paths; default-off, dark-launched, feature-flagged, or experimental functionality; migrations; test gaps; operational gaps; and incomplete integrations. Separate functionality that appears complete and verified from functionality that appears present but unvalidated. Flag mismatches between task status and committed code, and code/doc/test contradictions.

### 3. Sessions, chats, and handoffs

Inspect persisted agent/session artifacts where present. Do not assume any exist — inspect what is actually there. Common locations include `.claude/`, `.codex/`, `.cursor/`, `.aider/`, `.beads/`, `docs/`, `notes/`, `handoffs/`, `sessions/`, `memory/`, and `planning/`.

Identify decisions that exist only in session or chat memory; repeated concerns, recurring gotchas, and unresolved questions; session artifacts implying work not yet materialized into tasks; and session conclusions contradicted by current code, tests, or docs. Recommend which decisions should become tasks, become canonical docs, or be discarded/deferred. Treat chat/session memory as durable truth only once it has been promoted into docs, tasks, or code.

### 4. Docs and architecture

Inspect docs, briefs, handoffs, architecture and operations notes, release/migration notes, and README/AGENTS-style guidance.

Look for current release/beta criteria, architecture boundaries, product decisions, operational and test/validation requirements, deployment/migration requirements, and known risks. Identify stale, contradicted, duplicated, or superseded docs; docs that should be promoted to canonical; and missing release-readiness docs. Do not treat every doc as canonical — infer canonicity from repo conventions, recency, naming, location, references from other docs, and consistency with code.

## Standing context

Preserve project-specific constraints, but do not invent them. Before drawing conclusions, gather standing context from user instructions; `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `README.md`, or equivalents; architecture and release docs; task-tracker conventions; prior handoffs; and explicit "do not reopen" notes.

Such constraints may include canonical service boundaries, storage/persistence ownership, adapter/plugin responsibilities, generated-artifact vs source-of-truth boundaries, migration rules, release-train constraints, commit-message rules, review/critic/architecture approval gates, and testing requirements. Honor them where found. If none are found, say so explicitly rather than assuming them.

## Core principles

These are the guardrails that keep the synthesis trustworthy.

**Ground every claim.** Before reporting any conclusion, audit it against evidence from this session — tool results, files, commits, diffs, PRs, tasks, docs, tests, CI, or session artifacts. Report only work you can point to. Label inferences as inferences and unverified items as unverified. Never fabricate status: if tests failed, say so; if tests were not run, say so; if a source was skipped or unavailable, say so. State plainly what is complete and verified. See `references/report-template.md` for citation format.

**Do not reopen resolved work.** Old work, closed tasks, abandoned designs, and settled debates stay closed unless this review surfaces concrete evidence to reopen them — a regression, a task/code or doc/code mismatch, a release blocker, a user-visible gap, a migration/operational risk, or a dependency that invalidates the earlier conclusion. If reconsideration is only speculative, label it speculative and keep it out of the blocker list.

**Control scope.** The deliverable is a readiness synthesis and punch list. Do not add features, refactor code, invent abstractions, expand beyond the milestone, or design for hypothetical futures. Prefer the simplest milestone path that preserves the project's intended boundaries. Do not turn exploratory ideas into committed work without explicit materialization, do not treat generated artifacts as canonical unless the repo says they are, and do not treat chat/session memory as durable truth until it is promoted into docs, tasks, or code.

**Stay read-only by default.** Do not mutate the repository under review or its trackers — no editing code or docs, updating or closing tasks, creating branches, or committing — unless the user explicitly asks. The readiness report is the one expected artifact: write it outside the repo (see "Producing the report"). Render every recommended change as a ready-to-apply proposal, and apply proposals only on explicit request. Never perform destructive or irreversible actions without confirmation.

## Subagent orchestration

When subagents are available, delegate aggressively and work while they run. At minimum orchestrate five roles; if subagents are unavailable, run the same passes yourself and state that the review was single-agent.

- **Task-state auditor** — evidence source 1.
- **Commit and code auditor** — evidence source 2.
- **Session and chat continuity auditor** — evidence source 3.
- **Docs and architecture auditor** — evidence source 4.
- **Release-readiness verifier** — runs after the other four. Challenges overreach, removes speculative blockers, flags unsupported claims and already-done work, confirms P0 items are truly required and P1/P2 are correctly prioritized, and ensures the final answer distinguishes evidence from inference and does not reopen resolved work without evidence.

## Handling missing information

- Task tracker unavailable: say so; infer candidate tasks from commits, docs, and code; do not claim tasks exist.
- Sessions/chats unavailable: say so; do not infer hidden decisions from absent data.
- Docs unavailable: say so; treat code, tests, and tasks as stronger evidence.
- Tests not run: say so; do not claim readiness is verified.
- Milestone undefined: propose a minimal, narrow definition based on evidence and label it proposed.

## Producing the report

Write the report following `references/report-template.md` exactly — read that file when you are ready to produce output. It defines the artifact and delivery format, the 11 required sections, the milestone gate checklist, the evidence-citation format, and the writing style.

By default, deliver the report as a single Markdown file saved to `OUTPUT_LOCATION` (the working/output area, not the repo under review) named `<project>-<milestone>-readiness.md`, and print a short inline summary — the outcome paragraph plus the P0 list — so the headline is visible without opening the file. Render the recommendation sections (tasks, docs, code/tests) as ready-to-apply, copy-paste blocks that are not applied, and the gate checklist as Markdown checkboxes. Full details are in the reference.

Lead with the outcome. Be clear, not terse — avoid dense shorthand, unexplained internal labels, and arrow-chain summaries. Do not expose hidden reasoning; summarize it as evidence-backed conclusions. Write as if the output goes straight to an implementation agent, a reviewer/critic, and a human project owner. Use the project's own terminology where evidence supports it, and define any non-obvious terms.
