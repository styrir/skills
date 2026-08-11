---
name: styrir-search-deep-local
description: Use when the user chooses StyrirSearch:deep-local, asks for local report-grade search, wants a deep-search handoff manifest, or needs more structure without NVIDIA AI-Q/external spend.
---

# StyrirSearch:deep-local

Preset wrapper for local deep-search handoff.

**REQUIRED BASE SKILL: styrir-search.** Load and use the base Styrir Search skill, then treat this wrapper as an explicit route override:

```json
{
  "forceMode": "deep_search_local"
}
```

Use for a local deep-search handoff manifest.

Follow the base workflow for `deep_search_local`: create the route decision, package a handoff manifest, preserve source scope and proof gaps, and point to the local deep-search gates. This lane is still local and bounded; do not convert it to NVIDIA AI-Q unless the user explicitly asks to re-route.
