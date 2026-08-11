# skills

Canonical source for Styrir-owned agent skills shared across Claude Code, Codex, Hermes, and related harnesses.

## Active skills

| Skill | Purpose |
|---|---|
| `ask/` | Observable model-to-model consultation through provider-aware CLI adapters, JSONL traces, and Markdown artifacts. |
| `devops/headscale-operations/` | Operate the Styrir Headscale control plane and safely join or approve clients. |
| `productivity/meetcal-operations/` | Inspect and operate MeetCal database, audit-log, backup, and calendar-sync state. |
| `red-teaming/macos-app-defender-lab/` | Authorized macOS application self-red-team and hardening workflow. |
| `repo-readiness-synthesis/` | Evidence-grounded repository readiness reviews across tasks, commits, sessions, and documentation. |
| `research/` | Canonical research-tool skills for Context7, Deep Search, provider setup, report delivery, paper writing, and related retrieval workflows. |
| `setja/` | TypeScript context-construction and agent-injection layer with templates and harness adapters. |
| `styrir-init/` | Safely initialize or adopt a repository with local Git, Beads/Dolt, GitNexus, DOX guidance, and the Styrir generated-workspace layout. |
| `styrir-search/` | Bounded Styrir research routing, evidence ledgers, gates, and deep-search handoff packaging. |
| `styrir-search-{simple,plus,deep-local,deep-aiq}/` | Slash-preset wrappers for the common Styrir Search lanes. |
| `voice-preserving-humanizer/` | Revise AI-assisted prose while preserving author voice; dual-approved plan scaffolded, implementation in progress (`skills-cfw`). |

Each skill uses `SKILL.md` as its entry contract. Inspect that file and its linked `scripts/`, `references/`, `templates/`, or `assets/` before changing behavior.

## Local installation

Harnesses should link to this checkout instead of carrying divergent copies:

```bash
ln -sfn ~/Code/skills/<name> ~/.claude/skills/<name>
ln -sfn ~/Code/skills/<name> ~/.codex/skills/<name>
ln -sfn ~/Code/skills/<name> ~/.grok/skills/<name>
```

Hermes skills may link into a category directory, for example:

```bash
ln -sfn ~/Code/skills/repo-readiness-synthesis \
  ~/.hermes/skills/software-development/repo-readiness-synthesis
```

## Repository workflow

- Read `AGENTS.md` first.
- Use Beads for durable task state; run `bd prime` for the current command contract.
- The `skills` Beads database uses the machine-wide shared Dolt server and backs up to `refs/dolt/data` on `styrir/skills`.
- Detailed planning, sync, handoff, and recovery guidance lives in `docs/agent-guidance/planning-beads-and-handoffs.md`.
- Keep secrets out of the repository. Credentials belong in environment variables or the macOS Keychain.

## Migration boundary

The pre-Styrir skills repository is retained locally as an archive. It is not the source of truth. Content moves from that archive only through an explicit, reviewed migration; runtime state, generated harness artifacts, and obsolete skill families are not imported implicitly.
