# Styrir Search Ledger Contract

Use this reference when constructing a ledger or debugging `scripts/styrir-search-gate.ts` output.

## Minimal Ledger

```json
{
  "meta": {
    "searchId": "search-YYYY-MM-DD-topic",
    "mode": "styrir_search",
    "totalQueriesRun": 6,
    "totalSourcesFetched": 5,
    "budget": {
      "maxSearchQueries": 6,
      "maxFetches": 6
    }
  },
  "entries": [
    {
      "id": "e1",
      "entity": "EntityName",
      "signalType": "api_changes",
      "observation": "Factual statement only.",
      "possibleImplication": "Separate interpretation.",
      "sourceId": "s1",
      "sourceUrl": "https://example.com",
      "sourceType": "official",
      "dateObserved": "2026-07-02",
      "confidence": "high",
      "relevance": 0.82
    }
  ],
  "proofGaps": [
    {
      "description": "What could not be confirmed",
      "attemptedQueries": ["query text"]
    }
  ],
  "sources": [
    {
      "id": "s1",
      "url": "https://example.com",
      "title": "Source title",
      "sourceType": "official",
      "fetched": true
    }
  ]
}
```

When citing sources in `deep_search_local` prose artifacts, use bracketed source IDs from the registry in the `s<number>` family, such as `[s1]` or `[s2]`. Other bracketed editorial markers, such as `[sic]` or `[TODO]`, are not treated as citations.

## Allowed Values

Modes:

- `direct_search`
- `styrir_search`
- `styrir_plus`
- `deep_search_local`
- `nvidia_aiq_handoff`
- legacy accepted: `aiq_deep_tbd`, `structured_search`, `structured_plus`, `deep_research`

The normalizer maps legacy `structured_search` to `styrir_search`, `structured_plus` to `styrir_plus`, `deep_research` to `deep_search_local`, and `aiq_deep_tbd` to `nvidia_aiq_handoff`.

Source types:

- `official`
- `news`
- `blog`
- `analysis`
- `academic`
- `social`
- `legal`
- `product`
- `comparison`
- `repo`
- `memory`
- `local`

Confidence:

- `high`
- `medium`
- `low`

High confidence is only accepted for `official`, `legal`, `product`, `academic`, `repo`, or `local` source types.

## Gate Result

The gate writes JSON:

```json
{
  "gateStatus": "pass",
  "blockers": [],
  "warnings": [],
  "counts": {
    "entries": 2,
    "sources": 2,
    "proofGaps": 1
  }
}
```

Exit codes:

- `0`: pass
- `1`: fail or runtime error

Warnings do not fail the gate. Blockers fail it.

## Normalizing Legacy Ledgers

Use the normalizer before running the gate when a ledger came from Hermes, another agent, or YAML:

```bash
node --experimental-strip-types scripts/styrir-ledger-normalize.ts legacy-ledger.yaml
```

The YAML parser is intentionally constrained. It supports simple maps, block lists, and `- key: value` list items with continued fields. It rejects flow YAML such as inline objects/lists, tabs, malformed indentation, and scalar list items with nested content.

The normalizer preserves explicit source appendix entries, assigns stable generated IDs where missing, maps entries to sources by `sourceId` or URL, and only defaults `fetched: true` for explicit source appendix entries without an explicit fetched flag. Synthesized sources still need real fetch/read evidence before the final gate should pass.

## What The Gate Does Not Prove

The gate does not prove that a source semantically entails the observation. It proves that the ledger has bounded budget accounting, fetched citations, required fields, separated inference, and basic source-confidence compatibility. For entailment, contradiction resolution, or publication-grade trust, escalate to the deep tier.
