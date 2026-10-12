---
name: styrir-search-deep-aiq
description: Use when the user chooses StyrirSearch:deep-AIQ, explicitly wants a NVIDIA AI-Q handoff, approves the external/operator path, has a configured local AI-Q target, or needs an AI-Q manifest.
---

# StyrirSearch:deep-AIQ

Preset wrapper for NVIDIA AI-Q target or handoff.

**REQUIRED BASE SKILL: styrir-search.** Load and use the base Styrir Search skill, then treat this wrapper as an explicit route override:

```json
{
  "forceMode": "nvidia_aiq_handoff"
}
```

Use for a configured NVIDIA AI-Q target or handoff manifest.

Follow the base workflow for `nvidia_aiq_handoff`: create the handoff manifest, preserve question, objective, source scope, and blockers. If `aiqBaseUrl` is absent, leave `commands` empty and fail closed. If `aiqBaseUrl` is present, include REST health-check and async job commands, and do not claim execution until the health check succeeds.

## AI-Q server (Berlin)

AI-Q v2.2.1 runs on Berlin (`root@82.22.174.79`) at `/srv/styrir/apps/aiq`; use `aiqBaseUrl: "http://100.64.0.2:8180"` (Tailscale only; UI on `:3180`). It binds only 127.0.0.1 and the tailnet IP because AI-Q has no auth. Models run on NVIDIA's hosted API (free tier, ~40 RPM), so no GPU is needed.

- Keys: Infisical styrir / prod / `/aiq` (`NVIDIA_API_KEY`, `TAVILY_API_KEY`, nothing else). `styrir-aiq-env.timer` (every 15 min) renders them to root-only `/srv/styrir/shared/env/aiq.env` and recreates `aiq-agent` when they change.
- The compose override and runbook live in the `styrir-server` repo (`aiq/`); deploy changes from there. Restart: `cd /srv/styrir/apps/aiq/deploy/compose && docker compose --env-file ../.env -f docker-compose.yaml -f docker-compose.berlin.yaml up -d` (project name `aiq` is pinned in the override).
- If `curl -sf http://100.64.0.2:8180/health` fails, the server or tailnet is down: fall back to the handoff-only manifest.
- Treat AI-Q reports like any other lane: test runs cited stale NVIDIA pages for version and model facts, so verify citations.
