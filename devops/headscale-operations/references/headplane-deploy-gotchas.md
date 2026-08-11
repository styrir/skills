# Headplane on Berlin next to Headscale (gotchas)

Layout: `/opt/headscale/` compose with `headscale`, `headplane`, `caddy`; optional demoted `headscale-ui` under profile `legacy-ui`.

## Working shape

- Headplane: `ghcr.io/tale/headplane:latest`, loopback `127.0.0.1:8093:3000`
- Public: https://headscale.styrir.com/admin via Caddy on `127.0.0.1:8092` then nginx/LE
- `server.base_url`: `https://headscale.styrir.com` (**no** `/admin` suffix)
- `headscale.url`: `http://headscale:8080`
- `headscale.api_key`: from `headscale apikeys create` (file `/opt/headscale/headplane/api.key`, 0600)
- `cookie_secret`: 32+ chars; `cookie_secure: true` behind HTTPS

## Config schema trap

Headplane 0.7.x may require:

```yaml
integration:
  kubernetes:
    enabled: false
    validate_manifest: true
    pod_name: "headscale"   # required string even when disabled
  proc:
    enabled: false
  docker:
    enabled: true
    container_label: "me.tale.headplane.target=headscale"
    socket: "unix:///var/run/docker.sock"
```

Missing `pod_name` → crash loop: `integration.kubernetes.pod_name must be a string`.

## Docker integration name collision

Using `container_name: headscale` fails when `headscale-ui` exists:

```text
Found multiple containers with name headscale
Integration Docker is not available
```

Docker name filter is substring-ish. Fix:

1. Label the real control plane: `me.tale.headplane.target=headscale`
2. Configure Headplane with `container_label` only (no `container_name`)
3. Stop/demote `headscale-ui` (`profiles: ["legacy-ui"]`, `restart: "no"`)

Success log:

```text
Using container: /headscale (ID: …)
Connected to Headscale 0.28.0
```

## Caddy routing

Prefer explicit admin matcher so catch-all does not steal `/admin`:

```caddy
@admin path /admin /admin/*
handle @admin {
  reverse_proxy headplane:3000 {
    header_up Host {host}
    header_up X-Forwarded-Proto https
  }
}
redir /web /admin permanent
redir /web/* /admin permanent
handle {
  reverse_proxy headscale:8080 { ... }
}
```

Verify:

```bash
curl -sI -H 'Host: headscale.styrir.com' http://127.0.0.1:8092/admin/login   # 200 Headplane
curl -sI -H 'Host: headscale.styrir.com' http://127.0.0.1:8092/web          # 301 → /admin
curl -skI --resolve headscale.styrir.com:443:127.0.0.1 https://headscale.styrir.com/admin/login
```

## Headscale CLI dialect (v0.28 on Berlin)

| Action | Command |
|---|---|
| Register interactive | `headscale nodes register --user brooks --key <k>` |
| Mint preauth | `headscale preauthkeys create -u 1 -e 1h` |
| List preauth | `headscale preauthkeys list` (**no** `-u`) |
| Expire preauth | `headscale preauthkeys expire -i <id>` |
| Rename display | `headscale nodes rename -i <id> <name>` |

There is **no** `headscale auth …` on this build. Probe `--help` before assuming newer docs.

## hsctl

- On box: `/usr/local/bin/hsctl`
- Remote: `scripts/hsctl-remote.sh` / `~/.local/bin/hsctl`
- Mutating register paths require `--yes`
