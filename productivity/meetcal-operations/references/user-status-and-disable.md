# MeetCal user status and disable

## Status enum

`UserStatus`: `INVITED` | `PENDING` | `APPROVED` | `REJECTED` | `DISABLED`

Migration that added disable: `prisma/migrations/20260811021500_add_user_status_disabled/`.

## Product rules

- **Disable ≠ delete.** Keep user + all meetings (created/assigned) for historical calendar visibility.
- Calendar queries (`getMeetingsForRange`) do not filter meetings by creator/assignee status.
- Disable clears Auth.js `sessions` for that `userId` immediately.
- Disabled users hitting app routes go to `/auth/disabled`.
- ICS feed token access returns 403 when status is not active (`DISABLED` / `REJECTED` / `PENDING`).
- Admin settings assignee list is `status = APPROVED` only.

## Admin actions

| Action | From → To | Notes |
|--------|-----------|--------|
| Approve | PENDING → APPROVED | |
| Reject | PENDING → REJECTED | |
| Disable | APPROVED/INVITED → DISABLED | No self-disable; no last-admin disable |
| Enable | DISABLED → APPROVED | User must sign in again |
| Invite existing | any existing → APPROVED | Also marks invitation used |

## UI

`/admin/users` (`users-table.tsx`):
- Status badge shows `Disabled` (not raw `DISABLED`) with muted styling.
- Disable button (Ban icon) for approved/invited non-self rows.
- Enable button (RotateCcw) for disabled rows.
- Surfaces server error messages (e.g. last admin) inline.

## Quick DB checks (secret-safe)

```sql
SELECT status, count(*) FROM users GROUP BY 1 ORDER BY 1;
SELECT id, email, role, status FROM users ORDER BY created_at;
-- meetings for a user still present after disable:
SELECT count(*) FROM meetings
WHERE created_by_id = $1 OR assignee_id = $1;
```
