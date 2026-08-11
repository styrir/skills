# macOS Tailscale client + Headscale

## Preferred join

```bash
# On Berlin:
hsctl join-command --os macos --user 1 --ttl 1h --yes

# On Mac — use full app binary (plain /usr/local/bin/tailscale often crashes):
/Applications/Tailscale.app/Contents/MacOS/Tailscale up \
  --login-server https://headscale.styrir.com \
  --authkey <PREAUTH> \
  --reset
```

## Interactive break-glass (causes browser loop until approved)

GUI: Option (⌥) → Debug → Add Account → `https://headscale.styrir.com`

Then approve on Berlin:

```bash
hsctl approve-latest --user brooks --yes
# or
hsctl register --user brooks --key '<key-from-url>' --yes
```

Or Headplane: https://headscale.styrir.com/admin → Machines → Add Device.

## Known crash

```
Tailscale/BundleIdentifiers.swift:47: Fatal error: The current bundleIdentifier is unknown to the registry
```

Use the app binary path, not the bare `tailscale` symlink, after any official-control-plane history.

## Hostname note

macOS name `BA MacBook Pro` is rejected by Headscale (spaces). Display name can still be `macbook-pro`; internal hostname may show as `invalid-*`.

## DNS / proxy

`headscale.styrir.com` must remain protocol-safe for Noise (DNS-only / direct TLS). Cloudflare orange-cloud breaks client registration.
