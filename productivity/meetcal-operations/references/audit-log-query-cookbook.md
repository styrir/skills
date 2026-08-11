# MeetCal audit-log query cookbook

Use from `/srv/styrir/apps/meetcal` after sourcing the local app env without printing it:

```bash
cd /srv/styrir/apps/meetcal
set -a && . ./.env && set +a
```

## Basic DB check

```bash
psql "$DATABASE_URL" -X -q -P pager=off -c "\dt"
```

## App timezone

```sql
SELECT primary_timezone, primary_timezone_label
FROM app_settings
LIMIT 1;
```

## Link-added audit entries for a day

Replace the date literals as needed. This treats Prisma `timestamp without time zone` values as UTC and reports in the app timezone.

```sql
WITH tz AS (
  SELECT primary_timezone FROM app_settings LIMIT 1
)
SELECT
  timezone((SELECT primary_timezone FROM tz), al.timestamp AT TIME ZONE 'UTC') AS link_added_app_time,
  al.timestamp AS link_added_utc_timestamp,
  m.title,
  timezone((SELECT primary_timezone FROM tz), m.start_time AT TIME ZONE 'UTC') AS meeting_start_app_time,
  u.email AS actor_email,
  al.changes
FROM audit_logs al
JOIN meetings m ON m.id = al.meeting_id
LEFT JOIN users u ON u.id = al.user_id
WHERE al.action = 'LINK_ADDED'
  AND al.timestamp >= TIMESTAMP '2026-07-13 00:00:00'
  AND al.timestamp <  TIMESTAMP '2026-07-14 00:00:00'
ORDER BY al.timestamp;
```

## Today's meetings and all related audit entries

Useful when `LINK_ADDED` returns zero rows but current meetings have `document_link` set.

```sql
WITH tz AS (
  SELECT primary_timezone FROM app_settings LIMIT 1
)
SELECT
  m.title,
  timezone((SELECT primary_timezone FROM tz), m.start_time AT TIME ZONE 'UTC') AS start_app_time,
  timezone((SELECT primary_timezone FROM tz), m.created_at AT TIME ZONE 'UTC') AS created_app_time,
  timezone((SELECT primary_timezone FROM tz), m.updated_at AT TIME ZONE 'UTC') AS updated_app_time,
  timezone((SELECT primary_timezone FROM tz), m.last_sync_at AT TIME ZONE 'UTC') AS last_sync_app_time,
  m.document_link IS NOT NULL AS has_link,
  m.sync_status,
  al.action,
  timezone((SELECT primary_timezone FROM tz), al.timestamp AT TIME ZONE 'UTC') AS audit_app_time,
  al.changes
FROM meetings m
LEFT JOIN audit_logs al ON al.meeting_id = m.id
WHERE m.start_time >= TIMESTAMP '2026-07-13 00:00:00'
  AND m.start_time <  TIMESTAMP '2026-07-14 00:00:00'
ORDER BY m.start_time, al.timestamp;
```

## Current meeting rows for a day

```sql
WITH tz AS (
  SELECT primary_timezone FROM app_settings LIMIT 1
)
SELECT
  id,
  title,
  timezone((SELECT primary_timezone FROM tz), start_time AT TIME ZONE 'UTC') AS start_app_time,
  timezone((SELECT primary_timezone FROM tz), created_at AT TIME ZONE 'UTC') AS created_app_time,
  timezone((SELECT primary_timezone FROM tz), updated_at AT TIME ZONE 'UTC') AS updated_app_time,
  document_link IS NOT NULL AS has_link,
  CASE WHEN document_link IS NULL THEN NULL ELSE left(document_link, 60) END AS link_prefix,
  sync_status,
  timezone((SELECT primary_timezone FROM tz), last_sync_at AT TIME ZONE 'UTC') AS last_sync_app_time,
  last_sync_error
FROM meetings
WHERE start_time >= TIMESTAMP '2026-07-13 00:00:00'
  AND start_time <  TIMESTAMP '2026-07-14 00:00:00'
ORDER BY start_time;
```

## Interpretation notes

- `LINK_ADDED` row present: report that audit timestamp as the link-add time.
- No `LINK_ADDED`, but `has_link = true`: say the DB has no explicit link-add audit entry. Use `created_at` if the link appears present at creation time, and include `last_sync_at` if the user cares about when the calendar received the link.
- `last_sync_at` is not the edit time; it is the app's Google Calendar sync completion time.
