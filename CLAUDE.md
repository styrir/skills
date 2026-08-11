# Claude Code Instructions

Read `AGENTS.md` first. It is the project-wide source of truth and routes detailed guidance through `docs/agent-guidance/`. This file retains only the managed Beads integration required by Claude Code.

<!-- bd-doctor-divergence: ok -->

<!-- BEGIN BEADS INTEGRATION v:1 profile:minimal hash:6cd5cc61 -->
## Beads Issue Tracker

This project uses **bd (beads)** for issue tracking. Run `bd prime` to see full workflow context and commands.

### Quick Reference

```bash
bd ready              # Find available work
bd show <id>          # View issue details
bd update <id> --claim  # Claim work
bd close <id>         # Complete work
```

### Rules

- Use `bd` for ALL task tracking — do NOT use TodoWrite, TaskCreate, or markdown TODO lists
- Run `bd prime` for detailed command reference and session close protocol
- Use `bd remember` for persistent knowledge — do NOT use MEMORY.md files

**Architecture in one line:** issues live in a local Dolt DB; sync uses `refs/dolt/data` on your git remote; `.beads/issues.jsonl` is a passive export. See https://github.com/gastownhall/beads/blob/main/docs/SYNC_CONCEPTS.md for details and anti-patterns.

## Agent Context Profiles

The managed Beads block is task-tracking guidance, not permission to override repository, user, or orchestrator instructions.

- **Repository default — tranche publisher**: After each completed and verified tranche, close or update its Beads, commit the coherent Git change, push Beads/Dolt to `origin`, push Git to `origin`, verify both, and leave the checkout clean.
- **Minimal**: Keep tool instruction files as pointers to `bd prime`; the same tranche-publication policy still applies.
- **Explicit pause**: A current user or orchestrator instruction to avoid a commit or push temporarily overrides the default for that tranche. Destructive history rewrites, force pushes, and remote creation or replacement always require separate confirmation.

## Session Completion

This protocol applies when ending a Beads implementation workflow. It is subordinate to explicit user, repository, and orchestrator instructions.

1. **File issues for remaining work** - Create beads for anything that needs follow-up
2. **Run quality gates** (if code changed) - Tests, linters, builds
3. **Update issue status** - Close finished work, update in-progress items
4. **Publish the tranche** unless a current instruction explicitly pauses publication:
   ```bash
   git status
   git pull --rebase
   bd dolt push --remote origin
   git push origin HEAD
   git status
   ```
5. **Hand off** - Summarize changes, validation, issue status, and any blocked sync/commit/push step

**Critical rules:**
- Explicit user or orchestrator instructions override this Beads block.
- This repository grants standing authority for ordinary tranche commits and non-force pushes to its configured origins.
- If a required sync or push is blocked, keep the tranche open, preserve the local state, and report the exact command and error.
<!-- END BEADS INTEGRATION -->
