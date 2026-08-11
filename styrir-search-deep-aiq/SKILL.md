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
