# Styrir Search Modes And Recipes

Use this reference when choosing a mode, setting a budget, or designing a recipe for a local-agent search task.

## Modes

### `direct_search`

Use for one fact, one narrow source set, or quick freshness checks.

Default budget:

```json
{
  "maxSearchQueries": 2,
  "maxFetches": 2,
  "maxFollowups": 0,
  "maxConcurrency": 2
}
```

Output can be a short cited answer. A full ledger is optional unless the answer will be reused.

### `styrir_search`

Use for the normal middle tier: comparison, API/library guidance, product research, "what should we do", and any answer that should leave an audit trail.

Default budget:

```json
{
  "maxSearchQueries": 6,
  "maxFetches": 6,
  "maxFollowups": 2,
  "maxConcurrency": 3
}
```

Output should include an answer, JSON evidence ledger, proof gaps, and gate result.

### `styrir_plus`

Use when the task is still bounded but needs more coverage because it is contested, current, multi-entity, or decision-shaped.

Default budget:

```json
{
  "maxSearchQueries": 10,
  "maxFetches": 10,
  "maxFollowups": 3,
  "maxConcurrency": 3
}
```

Add planner facets, a source registry, a ledger that passes the normal Styrir gate, contradiction sweep, and gate result. Do not require report-grade notes or final report unless the route escalates.

### `deep_search_local`

Use when the request is report-grade or high-stakes but should stay local and below a full external deep-research spend. This mode produces a handoff manifest and gated-report request for a local deep-search workflow; it is still bounded and should not turn into an open-ended research marathon.

Default budget:

```json
{
  "maxSearchQueries": 10,
  "maxFetches": 10,
  "maxFollowups": 3,
  "maxConcurrency": 2
}
```

Output should include the full local bundle described in `aiq-borrowed-patterns.md`: `plan.json`, `research-notes/*.md`, `source-registry.json`, substantive `consolidated-findings.md`, cited `report.md`, and `gate-result.json`.

### `nvidia_aiq_handoff`

Use when the request should become a NVIDIA AI-Q deep-research handoff and the user has approved the likely external spend/operator path.

This mode fails closed. Without an explicit local target, return a manifest-only handoff:

```json
{
  "mode": "nvidia_aiq_handoff",
  "handoffReason": "report-grade research needed",
  "recommendedNextSystem": "NVIDIA AI-Q",
  "minimumInputs": ["question", "objective", "source scope", "budget approval", "operator target"]
}
```

With explicit `forceMode: "nvidia_aiq_handoff"` and `aiqBaseUrl`, the manifest may include REST health-check, async job, status, and final-report commands. The preferred direct contract is the AI-Q REST API (`/health`, async job creation/status/final report endpoints). Treat the shipped AI-Q skill or CLI wrapper as a convenience path until the repo path and command shape are configured.

`aiq_deep_tbd` is accepted as a legacy alias but new output should say `nvidia_aiq_handoff`.

## Route Descriptor

Use `scripts/styrir-route.ts` when the mode is not obvious:

```json
{
  "question": "Compare current docs-backed search providers",
  "objective": "Pick a default provider",
  "lane": "technical_decision",
  "requiresCurrentInfo": true,
  "requiresOfficialSources": true,
  "contestedOrHighStakes": false,
  "needsClaimLevelValidation": false,
  "needsReportArtifact": false,
  "estimatedSearchQueries": 6,
  "estimatedFetches": 6,
  "preferredProviders": ["context7", "tavily"],
  "sourceScope": ["official docs", "repo files", "existing local research skills"]
}
```

`preferredProviders` are hints only. To route to a confirmed local NVIDIA AI-Q REST target, add `forceMode: "nvidia_aiq_handoff"` and `aiqBaseUrl`.

The route output includes `gate`, `requiredReferences`, `contradictionSweep`, and `handoff.nextSystem`. `direct_search` uses `optional-ledger-gate`, `styrir_search` and `styrir_plus` use `styrir-search-gate`, `deep_search_local` uses `deep-search-strict-gates`, and `nvidia_aiq_handoff` uses `handoff-only`.

## Recipe Shape

Use this compact recipe format:

```json
{
  "id": "technical_decision",
  "mode": "styrir_search",
  "sources": {
    "web": 6,
    "repo_docs": 12,
    "runir_memory": 12
  },
  "fetchBudget": 6,
  "reserveFollowups": 2,
  "recencyDays": 180,
  "requireOfficialSource": true,
  "contradictionSweep": "off"
}
```

## Lane Guidance

| Lane | Good mode | Source emphasis |
| --- | --- | --- |
| `current_status` | `direct_search` or `styrir_search` | official/current sources |
| `latest_state` | `styrir_search` | official docs plus local memory |
| `guidance_reference` | `styrir_search` | official docs, repo docs, stable references |
| `technical_decision` | `styrir_search` or `styrir_plus` | official docs plus comparison/analysis |
| `comparison` | `styrir_search` or `styrir_plus` | both primary sources plus third-party comparison |
| `decision_trace` | `styrir_search` | local memory, repo docs, cited web |
| `exploratory_topic` | `styrir_plus` | broader web plus proof gaps |
| `gated_report_local` | `deep_search_local` | official/current sources plus contradiction sweep |
| `external_report` | `nvidia_aiq_handoff` | provider handoff brief and source scope |

## Escalation Rules

Escalate from `styrir_search` to `styrir_plus` when:

- a primary source is missing,
- the answer depends on multiple entities or conflicting sources,
- follow-up queries reveal new facets,
- proof gaps would materially change the recommendation.

Escalate from `styrir_plus` to `deep_search_local` when:

- the work needs report-grade prose,
- contradictions need active resolution,
- claim-level verification is required,
- more than 10 searches or 10 fetches are needed,
- the user asks for deep research explicitly.

Escalate from `deep_search_local` to `nvidia_aiq_handoff` when:

- the user explicitly approves the external deep-research spend,
- local bounded evidence still leaves material contradictions,
- a reusable/public/report-grade deliverable needs external parallel research,
- the operator environment has a confirmed NVIDIA AI-Q target.
