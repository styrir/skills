# Continuous browser opens to Headscale `/register/<key>`

## What it is

Official Tailscale client interactive web auth against Headscale:

- URL: `https://headscale.styrir.com/register/<KEY>`
- Stock Headscale HTML: **Machine registration**
- Instruction (v0.28): `headscale nodes register --key <KEY> --user USERNAME`
- Footer: Powered by Headscale

This page is **not** Headplane (`/admin`) and has **no** approve button.

## Why the browser keeps opening

1. Client NeedsLogin / pending machine auth with `AuthURL` set.
2. No preauth key was supplied on `up`/`login`.
3. Admin has not approved the pending key (or keeps approving **stale** rotated keys).
4. Client re-launches the browser until success or the app is stopped.

## Key rotation

While unapproved, server logs look like:

```text
New followup node registration using key: <KEY>
```

Roughly every ~20 minutes a new key appears. Approving an old chat/screenshot key yields:

```text
Cannot register node: node not found in registration cache
```

Always take the **latest** key:

```bash
hsctl approve-latest --user brooks --yes
# equivalent:
# docker logs headscale 2>&1 | grep -Eo 'registration using key: [A-Za-z0-9_-]+' | tail -1
```

`hsctl register` accepts bare key or full register URL and normalizes the path tail.

## Dual state trap

A node (e.g. macbook-pro `100.64.0.1`) can show **Connected online** while the GUI still spams `/register` from a second login/account attempt. Treat the spam as a separate pending registration: approve-latest or cancel/quit the client login.

## Operator responses

| Goal | Action |
|---|---|
| Stop tabs only | Quit/disable Tailscale on the client |
| Finish join | `hsctl approve-latest --user brooks --yes` or Headplane Machines → Add Device |
| Never see this again | Preauth default: `hsctl join-command --os macos --yes` |

Do not auto-approve every pending key from a daemon.
