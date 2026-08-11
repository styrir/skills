# MeetCal Berlin deploy notes

## Layout

- App: `/srv/styrir/apps/meetcal` — **no `.git`** (cutover copy from DO era).
- Env: `/srv/styrir/apps/meetcal/.env` mode `0600` (preserve on every sync).
- Unit: `/etc/systemd/system/meetcal.service`
  - `WorkingDirectory=/srv/styrir/apps/meetcal`
  - `npx next start -H 127.0.0.1 -p 8903`
- Backups app dir: `/srv/styrir/apps/meetcal/backups/` (7-day prune)
- Durable dumps: `/srv/styrir/backups/meetcal/`
- Daily timer: `meetcal-db-backup.timer` → `/usr/local/sbin/meetcal-db-backup`

## Why not `git pull` on the server

Production was migrated as a filesystem copy, not a clone. Site/Varda under `/srv/styrir/apps/{site,varda}` may have git; meetcal does not. Prefer local git + rsync until the prod tree is re-homed as a proper checkout.

## deploy.sh caveat

Repo `deploy.sh` assumes it runs **inside** a clean git `master` tree with tests/lint. On Berlin bare tree that preflight fails. Use the rsync + migrate/build/restart sequence in SKILL.md instead (or reintroduce git and adapt deploy.sh later).

## SSH

```bash
ssh -i /Users/brooks/.ssh/id_ed25519 -o IdentitiesOnly=yes -o BatchMode=yes \
  -o ConnectTimeout=15 root@82.22.174.79
```

## Post-deploy smoke

```bash
systemctl is-active meetcal
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8903/calendar
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8903/auth/disabled
# enum check without secrets:
# SELECT enumlabel FROM pg_enum e JOIN pg_type t ON t.oid=e.enumtypid
# WHERE t.typname = 'UserStatus' ORDER BY enumsortorder;
```

Expect calendar/admin routes to return `307` (auth redirect) or `200` when healthy.
