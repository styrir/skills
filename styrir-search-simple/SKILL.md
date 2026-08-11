---
name: styrir-search-simple
description: Use when the user chooses StyrirSearch:simple, asks for ordinary bounded structured search, wants a JSON evidence ledger, or needs the standard Styrir Search lane without plus or deep-search escalation.
---

# StyrirSearch:simple

Preset wrapper for ordinary Styrir Search.

**REQUIRED BASE SKILL: styrir-search.** Load and use the base Styrir Search skill, then treat this wrapper as an explicit route override:

```json
{
  "forceMode": "styrir_search"
}
```

Use for normal bounded search with a JSON evidence ledger.

Follow the base workflow: route with `styrir_search`, fetch/read sources before citing them, build or normalize the ledger, run `styrir-search-gate`, and synthesize only from passed ledger entries. Do not escalate to `styrir_plus`, `deep_search_local`, or `nvidia_aiq_handoff` unless the user explicitly asks to re-route.
