---
name: styrir-search-plus
description: Use when the user chooses StyrirSearch:plus, asks for broader bounded search, needs contested or multi-facet coverage, or wants a contradiction sweep without deep-search escalation.
---

# StyrirSearch:plus

Preset wrapper for broader Styrir Search.

**REQUIRED BASE SKILL: styrir-search.** Load and use the base Styrir Search skill, then treat this wrapper as an explicit route override:

```json
{
  "forceMode": "styrir_plus"
}
```

Use for contested or multi-facet search with a contradiction sweep.

Follow the base workflow: route with `styrir_plus`, reserve follow-up budget, fetch/read sources before citing them, build or normalize the ledger, run `styrir-search-gate`, and report unresolved contradictions. Do not escalate to `deep_search_local` or `nvidia_aiq_handoff` unless the user explicitly asks to re-route.
