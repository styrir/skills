---
name: headscale-operations
description: Operate the Styrir Headscale control plane on Berlin (headscale.styrir.com) — hsctl, Headplane admin UI, preauth joins, interactive register approval, macOS Tailscale client quirks.
version: 1.1.0
author: Hermes Agent
metadata:
  hermes:
    tags: [headscale, tailscale, vpn, berlin, admin, preauth]
---

# Headscale Operations (Styrir / Berlin)

Use when managing **headscale.styrir.com** on Berlin (`82.22.174.79`), joining Tailscale clients, approving registrations, minting preauth keys, or using the Headplane admin UI.

## Architecture (current)

| Piece | Role |
|---|---|
| `headscale` container | Control plane v0.28 (Noise / TS2021) |
| `headplane` container | Admin UI at **https://headscale.styrir.com/admin** |
| `caddy` on `127.0.0.1:8092` | Path split: `/admin*` → Headplane, else → headscale |
| nginx + LE on host | Public 443 for DNS-only `headscale.styrir.com` |
| `hsctl` | Operator CLI on Berlin (`/usr/local/bin/hsctl`) |
| User | `brooks` (id **1**) |

Default join path: **preauth**. Interactive `/register/<key>` is break-glass only.

## Safety

1. Never auto-approve anonymous registrations.
2. Prefer single-use short-TTL preauth keys (`1h` default).
3. Do not print full preauth/API keys into chat, beads, or memory after one-shot display.
4. Do not orange-cloud the Headscale hostname (Noise/WebSocket POSTs break). DNS-only / direct TLS path is required.
5. `register` and `approve-latest` require `--yes`.
6. Do not restart headscale casually during active work without saying so — clients briefly reconnect.

## Operator entry points

### A. CLI on Berlin (preferred for agents)

```bash
ssh -o BatchMode=yes -i ~/.ssh/id_ed25519 root@82.22.174.79 'hsctl status'
ssh -o BatchMode=yes -i ~/.ssh/id_ed25519 root@82.22.174.79 'hsctl nodes list'
ssh -o BatchMode=yes -i ~/.ssh/id_ed25519 root@82.22.174.79 'hsctl preauth mint --user 1 --ttl 1h'
ssh -o BatchMode=yes -i ~/.ssh/id_ed25519 root@82.22.174.79 'hsctl register --user brooks --key KEY_OR_URL --yes'
ssh -o BatchMode=yes -i ~/.ssh/id_ed25519 root@82.22.174.79 'hsctl approve-latest --user brooks --yes'
ssh -o BatchMode=yes -i ~/.ssh/id_ed25519 root@82.22.174.79 'hsctl join-command --os macos --yes'
```

Local wrapper (if installed): `scripts/hsctl-remote.sh` → same commands over SSH.

### B. Headplane UI (humans)

1. Open https://headscale.styrir.com/admin
2. Log in with a Headscale **API key** (`headscale apikeys create --expiration 90d` on Berlin).
3. Machines → manage nodes; Add Device / register machine key from `/register/<key>` when interactive join is stuck.
4. Mint preauth keys in UI when available.

API key material lives on Berlin only: `/opt/headscale/headplane/api.key` (mode 0600). Do not commit.

### C. Legacy `/web` UI

Demoted. Compose profile `legacy-ui` only. `/web` redirects to `/admin`.

## Workflows

### Default: join a known Mac without browser spam

```bash
ssh ... 'hsctl join-command --os macos --user 1 --ttl 1h --yes'
# Then on the Mac (full app binary — plain tailscale may crash):
/Applications/Tailscale.app/Contents/MacOS/Tailscale up \
  --login-server https://headscale.styrir.com \
  --authkey <PREAUTH> \
  --reset
```

### Break-glass: browser stuck on Machine registration page

Page shows:

```bash
headscale nodes register --key <KEY> --user USERNAME
```

Approve latest from logs:

```bash
ssh ... 'hsctl approve-latest --user brooks --yes'
```

Or paste URL/key:

```bash
ssh ... 'hsctl register --user brooks --key https://headscale.styrir.com/register/<KEY> --yes'
```

Or Headplane → Machines → Add Device with the key tail.

Keys rotate ~every 20 minutes while unapproved (`New followup node registration`). Always use the **latest** key.

### Stop browser spam without joining

Quit/disable Tailscale on the client. Do not leave interactive login spinning.

### Rename node display name

```bash
ssh ... 'hsctl rename --id 1 --name macbook-pro'
```

Note: OS hostname `BA MacBook Pro` is rejected by Headscale (spaces); internal hostname may stay `invalid-*`. Display **Name** is what matters in `nodes list`.

## macOS client pitfalls

See `references/macos-client.md` (absorbed from cloudflare-operations headscale debug notes):

- Plain `tailscale` can fatal: `BundleIdentifiers.swift … unknown to the registry`
- Prefer full `/Applications/Tailscale.app/Contents/MacOS/Tailscale`
- Emergency GUI: Option+Debug → Add Account → `https://headscale.styrir.com`
- Preauth is preferred over GUI interactive

## Diagnosis: continuous browser opens to `/register/<key>`

This is **interactive web auth**, not a random Tailscale bug.

1. Client is pointed at `https://headscale.styrir.com` **without** a preauth key.
2. Stock Headscale serves an instruction page (title **Machine registration**, “Powered by Headscale”) — **not** Headplane and **not** an approve button.
3. Page shows `headscale nodes register --key … --user USERNAME` (v0.28 vocabulary; newer docs may say `auth register`).
4. While unapproved, Headscale logs `New followup node registration using key: …` about every **20 minutes** — keys rotate; stale keys fail with `node not found in registration cache`.
5. Client keeps reopening `AuthURL` until approved **or** Tailscale is quit/disabled.

**Fix order:**

1. Quiet-only (user mid-work): quit Tailscale locally — no Berlin change.
2. Finish join: `hsctl approve-latest --user brooks --yes` (never trust a key from chat older than a few minutes without checking logs).
3. Prevent recurrence: default to `hsctl join-command --os macos --yes` / preauth; do not teach interactive `/register` as normal onboarding.

Node may already be **online** under an older session while a second interactive re-login spams the browser — still approve-latest or cancel the extra login.

See `references/registration-loop.md`.

## Headscale / Headplane deploy pitfalls (Berlin)

Captured during 2026-07 Headplane cutover — full detail in `references/headplane-deploy-gotchas.md`:

- **Headplane config schema:** even with `integration.kubernetes.enabled: false`, `pod_name` must be a string or startup fails.
- **Docker integration name collision:** `container_name: headscale` matches **both** `headscale` and `headscale-ui` → `Found multiple containers with name headscale`. Use **label only** (`me.tale.headplane.target=headscale`) and keep `headscale-ui` stopped / `profiles: [legacy-ui]`.
- **Caddy path routing:** use `handle @admin path /admin /admin/*` (or equivalent) so `/admin` is not swallowed by the catch-all headscale reverse_proxy. `/web` → `301 /admin`.
- **CLI dialect on v0.28:** `nodes register --user --key` exists; `auth` subcommand does **not**. `preauthkeys list` has **no** `-u/--user` filter; `preauthkeys create` still takes `-u` user id; `preauthkeys expire -i <id>`.
- **Headplane login** is a Headscale **API key**, not the register machine key and not OIDC unless configured.
- **Stale preauth hygiene:** expire unused/reusable keys periodically (`preauthkeys expire -i …`); do not leave long-lived reusable keys lying around.
- **Hostname spaces:** macOS `BA MacBook Pro` is rejected; display **Name** can still be `macbook-pro` while Hostname shows `invalid-*`.

## Paths on Berlin

```text
/opt/headscale/
  docker-compose.yml
  Caddyfile
  config/config.yaml          # headscale
  lib/                        # db + noise key
  headplane/config.yaml       # headplane (0600)
  headplane/api.key           # 0600
  headplane/data/
  bin/hsctl → /usr/local/bin/hsctl
```

Backups of compose/Caddyfile: `*.bak.<timestamp>` beside live files.

## Verification

```bash
ssh ... 'hsctl status'
ssh ... 'docker ps --filter name=headscale --filter name=headplane --filter name=caddy'
curl -skI https://headscale.styrir.com/admin/login   # expect 200/302 Headplane
curl -skI https://headscale.styrir.com/               # headscale landing
# Node online after join:
ssh ... 'hsctl nodes list'   # Connected=online for target
```

## Support files

- `references/join-runbook.md` — preauth vs interactive approve cheatsheet
- `references/macos-client.md` — macOS binary/GUI pitfalls
- `references/registration-loop.md` — continuous browser `/register` diagnosis
- `references/headplane-deploy-gotchas.md` — Headplane + Caddy + docker label pitfalls
- `scripts/hsctl-remote.sh` — local `hsctl` over SSH to Berlin (`~/.local/bin/hsctl`)

## Related

- Tunnel/compose bootstrap only: the `cloudflare-operations` skill and its adding-Docker-services reference.
- Historical first-join proxy/DNS debugging: the `cloudflare-operations` skill's Headscale macOS client/proxy reference (day-2 admin lives **here**, not there).
- Design/impl notes (local): `Code/devops/.pipeline/headscale-admin-longterm-2026-07-27.md`, `…/headscale-admin-impl-2026-07-27.md`

**Skill split:** `cloudflare-operations` = tunnel/DNS/proxy bootstrap. **`headscale-operations`** = day-2 control-plane admin, joins, Headplane, `hsctl`.
