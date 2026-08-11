---
name: styrir-search
description: Use when choosing or running a bounded local-agent search mode, routing between direct search, Styrir Search, Styrir Plus, local deep-search handoff, and NVIDIA AI-Q handoff, normalizing evidence ledgers, or validating citations.
---

# Styrir Search

## Overview

Use Styrir Search for search work that needs more structure than one Tavily/Exa call but should stay cheaper and more bounded than full deep research. The core artifacts are a route decision, a JSON evidence ledger, and a deterministic gate result.

Start with `scripts/styrir-route.ts` when the mode is not obvious. Use `scripts/styrir-ledger-normalize.ts` when adapting a Hermes-style or YAML ledger into the canonical JSON shape. Use `scripts/styrir-handoff-manifest.ts` when the route points at local deep search or NVIDIA AI-Q. Keep `references/provider-matrix.md` and `references/handoff-manifest.md` alongside the route output whenever the lane depends on provider choice or handoff packaging.

## Mode Picker

Use one of these modes:

| Mode | Use for | Default budget | Status |
| --- | --- | ---: | --- |
| `direct_search` | quick lookup or one narrow source set | 1-2 searches, 0-2 fetches | ready |
| `styrir_search` | normal bounded research with an evidence ledger | 4-6 searches, 4-6 fetches | ready |
| `styrir_plus` | contested/current decisions needing more coverage | 6-10 searches, 6-10 fetches | ready |
| `deep_search_local` | report-grade/high-stakes work that should stay below a full external deep-search spend | local handoff manifest | ready as handoff |
| `nvidia_aiq_handoff` | report-grade/high-stakes work with explicit budget and operator approval for NVIDIA AI-Q | external handoff or configured REST target | ready as fail-closed handoff |

`aiq_deep_tbd` is still accepted as a legacy compatibility marker. New route decisions should use `nvidia_aiq_handoff`.

Read `references/modes-and-recipes.md` when the mode, budget, or escalation boundary is not obvious.

## Slash Presets

Codex currently exposes one default prompt per skill. Use the sibling wrapper skills below to make common Styrir lanes visible in the slash picker while keeping this folder as the shared implementation:

| Slash label | Skill token | Forced mode |
| --- | --- | --- |
| `StyrirSearch:simple` | `$styrir-search-simple` | `styrir_search` |
| `StyrirSearch:plus` | `$styrir-search-plus` | `styrir_plus` |
| `StyrirSearch:deep-local` | `$styrir-search-deep-local` | `deep_search_local` |
| `StyrirSearch:deep-AIQ` | `$styrir-search-deep-aiq` | `nvidia_aiq_handoff` |

When one of these wrappers is invoked, honor its forced mode unless the user explicitly asks to re-route.

## Workflow

1. Save a request descriptor when routing is non-trivial:

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

Use `preferredProviders` as hints only. To route to a configured AI-Q target, explicitly set `forceMode: "nvidia_aiq_handoff"` and include `aiqBaseUrl`.

2. Run the route chooser and write down the selected budget before searching:

```bash
node --experimental-strip-types scripts/styrir-route.ts request.json
```

3. Plan small search facets: entity-specific, comparison, official-source, contradiction, and gap follow-up.
4. Treat search snippets as discovery only. Fetch/read a source before using it as evidence.
5. Build a JSON evidence ledger with atomic entries, source appendix, and proof gaps. If another agent produced YAML or legacy JSON, normalize it first:

```bash
node --experimental-strip-types scripts/styrir-ledger-normalize.ts legacy-ledger.yaml
```

6. Run the gate:

```bash
node --experimental-strip-types scripts/styrir-search-gate.ts path/to/ledger.json
```

7. If the gate fails, fix the ledger or report the blockers. Do not synthesize from a failed ledger unless the user explicitly asks for the blocked draft.
8. Synthesize only from ledger entries and cite source IDs or URLs from the ledger.
9. When the route is `deep_search_local` or `nvidia_aiq_handoff`, create a handoff manifest:

```bash
node --experimental-strip-types scripts/styrir-handoff-manifest.ts request.json
```

10. For `styrir_plus` or `deep_search_local` artifact bundles, run the artifact gate:

```bash
node --experimental-strip-types scripts/styrir-artifact-gate.ts styrir_plus path/to/run-dir
node --experimental-strip-types scripts/styrir-artifact-gate.ts deep_search_local path/to/run-dir
```

Read `references/ledger-contract.md` when creating a ledger, debugging gate failures, or adapting another agent's YAML ledger into the Styrir JSON shape. Read `references/provider-matrix.md` before choosing providers, `references/aiq-borrowed-patterns.md` before creating plus/deep-local artifact bundles, and `references/handoff-manifest.md` before packaging a deep-search or NVIDIA handoff.

## Evidence Rules

- One observation per entry.
- `observation` is factual only; put interpretation in `possibleImplication`.
- Every entry needs a `sourceId`, `sourceUrl`, `sourceType`, `dateObserved`, and `confidence`.
- Every cited source must exist in `sources[]` and have `fetched: true`.
- `proofGaps[]` is mandatory, even when the gap is minor.
- High confidence is only for primary/official-quality sources.
- Budgets are hard limits. If the work needs more, switch mode or escalate.

## Scripts

Run all deterministic checks after editing the skill:

```bash
npm test
```

Available scripts:

- `npm run route -- request.json`: choose a mode and budget.
- `npm run normalize -- ledger.yaml`: convert legacy JSON/YAML into canonical Styrir JSON.
- `npm run normalize:ledger -- ledger.yaml`: legacy alias for the canonical normalizer.
- `npm run gate -- ledger.json`: validate a canonical ledger.
- `npm run artifact-gate -- styrir_plus <run-dir>`: validate mode-specific Styrir artifact minima.
- `npm run handoff -- request.json`: create a local deep-search or NVIDIA AI-Q handoff manifest.

The deterministic gate checks only things it can prove without a model:

- missing or unfetched sources,
- citation/source appendix mismatches,
- inference language inside observations,
- high confidence on non-primary source types,
- missing proof gaps,
- search/fetch budget overages,
- malformed dates and required fields.

The artifact gate additionally checks mode-specific run bundles: `styrir_plus` must include a normal Styrir ledger that passes the ledger gate, and `deep_search_local` must include substantive findings/report prose, source-id citations that exist in `source-registry.json`, a Sources section, and a passing gate result. It may warn on registered sources that are never cited. These gates validate structure and provenance, not claim truth.

## Escalation

Escalate out of Styrir Search when:

- contradictions are unresolved and material,
- no primary source is available for a decision that needs one,
- the needed budget exceeds `styrir_plus`,
- the user needs a reusable/public/report-grade artifact,
- the request is high-stakes or heavily time-sensitive.

Use `deep_search_local` when the user wants more structure than Styrir Plus without triggering a full external deep-search spend. Use `nvidia_aiq_handoff` as a fail-closed AI-Q lane: manifest-only by default, REST command manifest only when a local `aiqBaseUrl` is explicitly configured.

For NVIDIA AI-Q, fail closed: if `aiqBaseUrl` is absent, unhealthy, or malformed, produce a manifest-only handoff. If `aiqBaseUrl` is present, the manifest may include REST health-check, async job, poll, and report commands, but the operator must run the health check before claiming execution.

## Common Mistakes

- Do not cite search snippets as evidence.
- Do not let the model invent ledger URLs.
- Do not collapse observation and implication into one prose field.
- Do not call this "verified" in the entailment sense; the gate validates structure and provenance, not claim truth.
- Do not expand the lite controller into a deep-research clone. Escalate instead.
- Do not treat `nvidia_aiq_handoff` as executable unless a local `aiqBaseUrl` is explicitly configured and health-checked.
