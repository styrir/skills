---
name: meetcal-operations
description: Operate and deploy the Styrir MeetCal scheduling app — DB/audit inspection, user access (approve/reject/disable), backups, and Berlin production deploys.
version: 1.2.0
author: Hermes Agent
metadata:
  hermes:
    tags: [MeetCal, Styrir, calendar, PostgreSQL, Prisma, audit-logs, operations, deploy, backups, users]
---

# MeetCal Operations

Use this skill when the user asks about the Styrir/MeetCal scheduling app, the "meeting cal", meeting links, calendar sync status, meeting audit history, who changed a meeting, admin users, disabling users, database backups, or deploying MeetCal to production.

## Paths

| Role | Path |
|------|------|
| Source repo (local) | `/Users/brooks/Code/meeting-calendar` (git `master` → `origin/master`) |
| Berlin production app | `/srv/styrir/apps/meetcal` (**not a git checkout**) |
| Berlin service | `meetcal.service` → `127.0.0.1:8903` |
| Public URL | `https://cal.styrir.com` (Cloudflare Tunnel → nginx → meetcal) |
| Prod DB | PostgreSQL 17 database `meetcal` on Berlin localhost |

## Default approach

1. **Check the application database first.** Do not assume Google Calendar OAuth is the source of truth when the user says "meeting cal", "MeetCal", or asks when a meeting link was added. MeetCal stores meeting records and audit logs in its own DB.
2. Work from the app directory:
   - Prod: `/srv/styrir/apps/meetcal`
   - Local: `/Users/brooks/Code/meeting-calendar`
3. Load DB connection details from the local app env without printing secrets:
   - `set -a && . ./.env && set +a`
   - Use `$DATABASE_URL` with `psql` or a secret-safe Node/`pg` script.
4. Inspect `meetings` for current state, `audit_logs` for change history, and `users` for actor email/name/status.
5. Report the answer directly, with the relevant timestamp(s) and the distinction between:
   - the meeting record creation/update time
   - `LINK_ADDED` audit time, if present
   - Google Calendar sync time (`last_sync_at`), if the user means when the calendar was updated

## Key schema facts

MeetCal uses Prisma/PostgreSQL. Important tables:

- `meetings`
  - `title`
  - `document_link`
  - `start_time`, `end_time`
  - `created_at`, `updated_at`
  - `created_by_id`, `assignee_id`
  - `google_calendar_event_id`
  - `sync_status`, `last_sync_at`, `last_sync_error`, `last_sync_payload`
- `audit_logs`
  - `meeting_id`
  - `user_id`
  - `action`
  - `changes`
  - `timestamp`
- `users`
  - `email`, `name`, `friendly_name`
  - `role` (`ADMIN` \| `EDITOR` \| `VIEWER`)
  - `status` (`INVITED` \| `PENDING` \| `APPROVED` \| `REJECTED` \| `DISABLED`)
- `app_settings`
  - `primary_timezone`, `primary_timezone_label`

Audit actions include `CREATED`, `EDITED`, `MOVED`, `STATUS_CHANGED`, `LINK_ADDED`, `LINK_REMOVED`, and `DELETED`.

## User access / disable

Admin UI: `/admin/users`.

| Status | Meaning | Access |
|--------|---------|--------|
| `APPROVED` | Active | Full app (role-gated) |
| `INVITED` | Invited, may access like approved after signup path | App access |
| `PENDING` | Awaiting approval | `/auth/pending` |
| `REJECTED` | Never approved | `/auth/rejected` |
| `DISABLED` | Had access; revoked | `/auth/disabled`; sessions deleted on disable |

**Disable semantics (product rule):**
- Disable blocks login/app access but **keeps the user row**.
- Meetings created by or assigned to a disabled user **remain visible** in the shared calendar (history).
- `getMeetingsForRange` does **not** filter out disabled creators/assignees.
- Active Auth.js sessions are deleted on disable so access ends immediately.
- Personal ICS feed (`/api/calendar/feed`) returns **403** for non-active statuses.
- Settings default-assignee picker only lists `APPROVED` users.
- Guards: cannot disable self; cannot disable last approved admin; only `APPROVED`/`INVITED` can be disabled.
- Enable restores `APPROVED`. Inviting an existing disabled user still auto-approves via `inviteUser`.

Server actions: `disableUser`, `enableUser`, `approveUser`, `rejectUser` in `src/app/actions/admin-actions.ts`.

See `references/user-status-and-disable.md`.

## Timestamp pitfall

In the observed MeetCal DB, Prisma DateTime columns are `timestamp without time zone`, and values should be treated as UTC instants for reporting. PostgreSQL session timezone may be the server timezone (for example `Europe/Berlin`), while the app timezone may be `app_settings.primary_timezone` (for example `America/New_York`).

For user-facing answers about meeting times, prefer app timezone conversion:

```sql
timezone((SELECT primary_timezone FROM app_settings LIMIT 1), timestamp_col AT TIME ZONE 'UTC')
```

Avoid using `timestamp_col AT TIME ZONE 'Europe/Berlin'` unless the user specifically asks for server-local time.

## References

- `references/audit-log-query-cookbook.md` — link-add / audit SQL
- `references/user-status-and-disable.md` — DISABLED semantics and admin actions
- `references/berlin-deploy.md` — non-git prod tree, rsync deploy, smoke checks

## Common query: when was a meeting link added today?

See `references/audit-log-query-cookbook.md` for copyable SQL.

Interpretation rules:

- If `audit_logs.action = 'LINK_ADDED'` exists, that is the explicit link-add time.
- If no `LINK_ADDED` entry exists but `meetings.document_link IS NOT NULL`, the link may have been present at creation time or added during an edit path that did not emit `LINK_ADDED`. Check the `CREATED` audit row and `created_at`; also check `updated_at` and `last_sync_at`.
- If the user asks when the link was added "for the calendar", include `last_sync_at` because that indicates when the meeting record was synced to Google Calendar.



## Database backups (Berlin production)

Live app path: `/srv/styrir/apps/meetcal`
DB: PostgreSQL 17 database `meetcal`
Backup script: `/srv/styrir/apps/meetcal/scripts/db-backup.sh` (custom-format `pg_dump`, retain **7 days** in app `backups/`)

### Automation (installed 2026-08-11)

- Wrapper (sources `.env`, never prints secrets): `/usr/local/sbin/meetcal-db-backup`
- systemd timer: `meetcal-db-backup.timer` — daily ~04:00 Europe/Berlin (`OnCalendar=*-*-* 04:00:00`, `Persistent=true`, `RandomizedDelaySec=3m`)
- systemd service: `meetcal-db-backup.service` (oneshot, `Requires=postgresql.service`)
- Logs: `journalctl -u meetcal-db-backup.service`
- App dump dir (pruned at 7 days): `/srv/styrir/apps/meetcal/backups/`
- Longer-lived copy location (manual/catchup): `/srv/styrir/backups/meetcal/`

### Status checks

```bash
systemctl is-active meetcal-db-backup.timer
systemctl list-timers meetcal-db-backup.timer --no-pager
ls -lht /srv/styrir/apps/meetcal/backups/ | head
journalctl -u meetcal-db-backup.service -n 40 --no-pager
```

### Manual backup (secret-safe)

```bash
/usr/local/sbin/meetcal-db-backup "reason-label"
# or via unit:
systemctl start meetcal-db-backup.service
```

Do **not** use the legacy DO cron path `/root/openclaw/projects/meeting-calendar/scripts/db-backup.sh` — that schedule is dead on Berlin.

### Note on prune

`db-backup.sh` deletes `meetcal_*.dump` files in the app backups dir older than 7 days. After a long outage, catchup dumps replace the old series; keep any pre-outage dumps you still need under `/srv/styrir/backups/meetcal/` (outside the prune path).

## Production deploy (Berlin)

**Critical pitfall:** `/srv/styrir/apps/meetcal` is a **bare deploy tree without `.git`**. `git pull` will fail. Do not assume `./deploy.sh` alone is enough from a remote git checkout on the server.

Source of truth: local git repo `/Users/brooks/Code/meeting-calendar` on `master`.

### Safe deploy sequence

1. Land changes in the local repo; run `npm run test` and `npm run lint`; commit and `git push origin master`.
2. Pre-deploy DB backup on Berlin (or let the sequence below do it):
   ```bash
   ssh root@82.22.174.79 'cd /srv/styrir/apps/meetcal && /usr/local/sbin/meetcal-db-backup pre-deploy'
   ```
3. Rsync source **preserving prod `.env`** (never overwrite secrets):
   ```bash
   rsync -az --delete \
     --exclude node_modules --exclude .next --exclude .git \
     --exclude .env --exclude '.env.*' --exclude backups \
     --exclude .agents --exclude .codex --exclude .omc --exclude .omx --exclude .beads \
     -e 'ssh -i /Users/brooks/.ssh/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes' \
     /Users/brooks/Code/meeting-calendar/ root@82.22.174.79:/srv/styrir/apps/meetcal/
   ```
4. On Berlin:
   ```bash
   cd /srv/styrir/apps/meetcal
   unset DATABASE_URL   # avoid shell contamination with staging URLs
   bash scripts/db-backup.sh pre-deploy
   npx prisma migrate deploy   # NEVER prisma db push
   npx prisma generate
   npm run build
   systemctl restart meetcal
   ```
5. Verify:
   ```bash
   systemctl is-active meetcal
   curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8903/calendar   # expect 307 or 200
   ```

DB rules (non-negotiable, also in repo `AGENTS.md`):
- Never `prisma db push` on any MeetCal DB.
- Always backup before schema changes / deploy.
- Create migrations with `prisma migrate`; apply with `migrate deploy`.

See `references/berlin-deploy.md`.

## Safety and secrecy

- Never print `.env` contents or raw `DATABASE_URL`.
- Do not expose OAuth tokens, Google document links beyond short prefixes unless the user explicitly needs them.
- Read-only inspection queries are fine. Confirm before modifying records, replaying sync jobs, or changing env/config.
- On deploy, always exclude `.env` / `.env.*` from rsync.
