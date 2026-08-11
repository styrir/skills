# Join and approve runbook

## Default (preauth)

1. `hsctl preauth mint --user 1 --ttl 1h`
2. Give client the one-shot key (or `hsctl join-command --os macos --yes`)
3. Client: `tailscale up --login-server https://headscale.styrir.com --authkey … --reset`
4. `hsctl nodes list` → Connected online

## Interactive stuck on /register

1. Prefer `hsctl approve-latest --user brooks --yes` (keys rotate)
2. Or copy key from URL path after `/register/`
3. Or Headplane Machines → Add Device
4. Browser loop stops once registered

## Admin UI

- URL: https://headscale.styrir.com/admin
- Auth: Headscale API key (`docker exec headscale headscale apikeys create --expiration 90d`)
- Legacy `/web` demoted; redirects toward `/admin`

## Stop spam only

Quit Tailscale on the client. Does not register the node.
