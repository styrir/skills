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

## Local AI-Q server

AI-Q v2.2.1 runs on this Mac from `~/Code/aiq` via Docker Compose; use `aiqBaseUrl: "http://127.0.0.1:8180"` (UI on 3180). Models run on NVIDIA's hosted API (free tier, ~40 RPM), so no GPU is needed. Keys stay in Infisical and are injected at start, never written to `deploy/.env`:

```bash
cd ~/Code/aiq/deploy/compose && infisical run --projectId 402716ac-2805-4864-b3ce-e11b838f78b3 --env prod --silent -- infisical run --projectId 2588c473-4c4c-4b5a-b0f5-e261184b6b53 --env dev --silent -- docker compose --env-file ../.env -f docker-compose.yaml -f docker-compose.local.yaml up -d
```

The first project is styrir (`NVIDIA_API_KEY`); the second is runir dev (`TAVILY_API_KEY`). If `curl -sf http://127.0.0.1:8180/health` fails, the server is down: start it or fall back to the handoff-only manifest.
