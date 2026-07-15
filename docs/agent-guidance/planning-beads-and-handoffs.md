---
summary: "Skills-repo task workflow: Beads on the machine-wide shared Dolt server, progressive-disclosure artifacts, handoffs, recovery, and conservative closeout."
read_when:
  - "You are starting substantive work and need to create or claim a bead."
  - "You are planning or decomposing an epic."
  - "You are creating .pipeline artifacts or a session handoff."
  - "bd cannot find the skills database or connect to the shared server."
  - "You are preparing to close, sync, commit, or hand off work."
---

# Planning, Beads, and Handoffs — Skills

Run `bd prime` at session start for the current Beads command reference. This document contains the repository-specific policy that `bd prime` does not know.

## Architecture and Ownership

The `skills` repository is one project attached to the machine-wide Dolt SQL server:

| Property | Contract |
|---|---|
| Repository | `/Users/brooks/Code/skills` |
| Beads database | `skills` |
| Issue prefix | `skills-` |
| Dolt endpoint | `127.0.0.1:3308` |
| Server owner | launchd label `com.beads.shared-dolt` |
| Server data | `~/.beads/shared-server/dolt/` |
| Server log | `~/.beads/shared-server/sql-server.log` |
| Dolt remote | `origin` → `git+ssh://git@github-styrir/styrir/skills.git` |
| Git remote | `origin` → `git@github-styrir:styrir/skills.git` |

The physical server is shared; the logical database is not. Each repository gets a distinct database and prefix. Never use `beads_global` as this repository's issue tracker, attach another repository to `skills`, or copy another repo's `.beads/` directory here.

The server lifecycle is external to `bd`:

```yaml
dolt:
  shared-server: true
  auto-start: false
```

Do not run `bd dolt start`, a raw `dolt sql-server`, or a per-project server against this repo. Those can compete with the launchd-managed process.

## Progressive-Disclosure State Model

Use each state surface for one job:

| Surface | Owns | Does not own |
|---|---|---|
| Beads (`skills-*`) | Durable scope, acceptance criteria, dependencies, status, follow-ups | Long investigation narratives or raw model traces |
| `.pipeline/<topic>/` | Resumable execution state: briefs, plans, model traces, review artifacts, state/metrics ledgers | Canonical long-term task status |
| `docs/plans/` | Durable implementation contracts and approved specifications | Live task status |
| `docs/reviews/` | Durable review synthesis and decision traceability | Replacement copies of raw reviewer output |
| Handoff document, when needed | Curated investigation trail, decisions, verification evidence, exact resume point | Follow-up scope that belongs in a bead |

A new session should be able to recover both dimensions: Beads answers **what work is active**; `.pipeline/` and durable docs answer **what phase it reached and why**.

## Session Start

From the repository root:

```bash
bd prime
bd status
bd ready
bd list --status=open
```

Before implementation, claim an existing bead or create one:

```bash
bd create \
  --title="<concise outcome>" \
  --type=task \
  --priority=2 \
  --description="<what changes and why>" \
  --acceptance="<observable done conditions>"

bd update <id> --claim
```

Use numeric priorities `0` through `4`; lower is more urgent. Avoid `bd edit`, which opens an interactive editor. Use `bd update` flags instead.

The one exception to “bead first” is first-time tracker bootstrap: initialize the database, then immediately create and claim the bootstrap bead before making repository-policy edits.

## Epic Decomposition

Do not implement directly from an epic-sized bead. Create concrete children and wire dependencies first:

```bash
bd create --title="Epic: <area>" --type=epic --priority=2 \
  --description="<scope and acceptance boundaries>"

bd create --title="<slice>" --type=task --parent=<epic-id> --priority=2 \
  --description="<specific slice>" --acceptance="<literal done condition>"

bd dep add <later-child> <earlier-child>
bd show <epic-id>
bd ready
```

Claim only the unblocked child being implemented.

## Shared-Server Bootstrap

### This checkout

This checkout is the designated creator of database `skills`. Its repo-local `.beads/config.yaml` and `.beads/metadata.json` bind it to the external server and database. The database itself lives under the shared server root, not `.beads/dolt/`.

### Later clones or recovery

Once the `refs/dolt/data` remote has been seeded, a new clone must use `bd bootstrap` to adopt the existing database history. Do not independently run schema migration or create another `skills` database from JSONL.

```bash
chmod 700 .beads
bd bootstrap
bd doctor
bd status
```

Use `bd init` only when deliberately creating a brand-new project database. The first-init shape for this architecture is:

```bash
bd init --non-interactive \
  --server \
  --shared-server \
  --external \
  --server-host 127.0.0.1 \
  --server-port 3308 \
  --database <unique-database> \
  --prefix <unique-prefix> \
  --remote <git-compatible-dolt-remote>

bd config set dolt.auto-start false
```

Use one designated migrator for any future schema upgrade. Other clones bootstrap from the migrated remote; they do not migrate independently.

## Connection and Health Verification

Use repository-aware checks:

```bash
bd config show
bd dolt remote list
bd status
bd doctor
```

Expected facts:

- `dolt_mode = server`
- `dolt_database = skills`
- host `127.0.0.1`, port `3308`
- `dolt.shared-server = true`
- `dolt.auto-start = false`
- issue prefix `skills`
- Dolt remote `origin` points to `styrir/skills` through the `github-styrir` SSH alias

`bd config validate` validates the optional federation subsystem and requires a federation-class remote. This repo uses Git-backed Dolt sync, not Beads federation; do not add `federation.remote` merely to silence that validator.

Because the SQL process is managed externally, some Beads versions may emit a misleading “shared server not running” doctor warning even while database connection checks pass. Treat a successful `Dolt Connection`/query plus launchd/process evidence as authoritative.

Check the external service without starting a second server:

```bash
launchctl print "gui/$(id -u)/com.beads.shared-dolt"
lsof -nP -iTCP:3308 -sTCP:LISTEN
```

If it is down:

```bash
launchctl kickstart -k "gui/$(id -u)/com.beads.shared-dolt"
```

Then rerun `bd status`. Inspect `~/.beads/shared-server/sql-server.log` if launchd cannot restore it.

## Sync Boundaries

Git code history and Dolt issue history are separate refs and separate pushes:

- `git push` updates `refs/heads/*`.
- `bd dolt push --remote origin` updates `refs/dolt/data`.
- `.beads/issues.jsonl`, if generated, is interchange/export data—not the wire protocol or canonical backup.

This repo leaves JSONL auto-export disabled unless an integration explicitly requires it. Do not add an auto-import/export loop by default.

Never use raw `dolt push` while the shared server is running. Use `bd dolt push --remote origin` so Beads coordinates the operation.

### Temporary Beads 1.1.0 Git-remote push fallback

The current shared-server/Git-remote combination can fail with `dolt remote add ... remote already exists` while `bd dolt push --remote origin` materializes an already-correct remote. Track removal of this workaround in `skills-bjw`.

Before using the fallback, verify `bd dolt remote list` shows exactly `git+ssh://git@github-styrir/styrir/skills.git`. Do not remove the correct remote, stop the machine-wide server, or run raw `dolt push`. Use Dolt's supported SQL-server procedure:

```bash
uv run --with pymysql python - <<'PY'
import pymysql

connection = pymysql.connect(
    host="127.0.0.1",
    port=3308,
    user="root",
    password="",
    database="skills",
    autocommit=True,
)
with connection.cursor() as cursor:
    cursor.execute("CALL DOLT_PUSH('origin', 'main')")
    print(cursor.fetchall())
connection.close()
PY

git ls-remote git@github-styrir:styrir/skills.git refs/dolt/data
```

The procedure is the documented SQL-server equivalent of `dolt push`; the Git remote stores the database under `refs/dolt/data` by default. Treat status `0` plus a nonempty remote ref as success.

The repository uses the conservative profile: do not Git-commit, Git-push, or Dolt-push without explicit user authorization. Local issue writes are allowed when they are necessary to track the current task.

## Handoffs and Follow-ups

A bead must contain the durable scope and acceptance criteria. Create a handoff only when the next session needs investigation context that would make the bead unreadable:

- what was inspected;
- decisions and rejected alternatives;
- exact verification evidence;
- current artifact paths;
- the next safe command or code seam.

Create follow-up beads before ending the session. Do not leave durable work only in chat, a final reply, or an unchecked Markdown list.

## Conservative Closeout

For a locally completed task:

1. File follow-up beads for anything unfinished.
2. Run the task's tests, linters, documentation checks, or other quality gates.
3. Update or close the current bead only when its acceptance criteria are actually met.
4. Check both issue and Git state:

   ```bash
   bd show <id>
   bd dolt status
   git status --short --branch
   ```

5. Without explicit authorization, stop and report the exact Git and Dolt push commands rather than running them.
6. With authorization, keep the two sync operations explicit:

   ```bash
   bd dolt push --remote origin
   git push
   ```

7. Verify the final remote and local state.

## Recovery Guardrails

### `database "skills" not found on Dolt server`

1. Confirm this is the `skills` checkout, not another repo or worktree.
2. Run `chmod 700 .beads`.
3. Confirm the launchd server and port 3308 are healthy.
4. For a later clone, run `bd bootstrap`; for the designated initial checkout before its first remote seed, do not bootstrap from an empty remote.
5. Do not fall back to `beads_global` or import another repo's JSONL.

### Remote has no `refs/dolt/data`

This is expected only before the designated initial checkout's first authorized `bd dolt push --remote origin`. Do not fabricate history or copy an unrelated database.

### Schema mismatch

Stop. Identify the designated migrator and current remote state. Do not apply independent migrations from multiple clones or worktrees.

### Blob/ref corruption

Stop raw pushes and repeated pull/push retries. Preserve the checkout, inspect server logs, and recover only from a verified-clean database or remote ref.

## Guidance Maintenance

Keep root `AGENTS.md` as a concise router. Put detailed Beads changes in this file, then update `docs/agent-guidance/AGENTS.md` only if the routing table changes. Verify every routed path exists and run `git diff --check` after guidance edits.
