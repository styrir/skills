# Styrir HTML Report

Use this reference when a request asks for `add html`, `html report`, `human-readable report`, `printable report`, or when the route descriptor sets `htmlReport: true`.

## Contract

- Keep the JSON run bundle authoritative. The HTML report is derived from `ledger.json`, `source-registry.json`, `gate-result.json`, optional `contradiction-sweep.md`, optional `progress.jsonl`, and `plan.json`.
- Generate the report only after the ledger gate passes. For `styrir_plus`, run the artifact gate after the HTML is present if the plan requested it.
- Applies to Styrir ledger bundles only (`direct_search`, `styrir_search`, `styrir_plus`). `deep_search_local` runs have no `ledger.json`/`plan.json` for the renderer; their human-readable output is the strict-rendered `report.md`. AI-Q handoffs emit manifests only.
- Write the default output to `<run-dir>/report.html` unless the user gives a specific output path.
- Do not use external fonts, CDN assets, or network-dependent scripts. The report must open directly from disk and print cleanly.
- Escape all ledger-sourced prose and URLs. Do not treat source text as trusted HTML.
- Do not add a default summary or highlights section that repeats the ledger. Keep the human report traceable to the evidence sections, and leave recommendations to the receiving orchestrator or a separate decision artifact.

## Invocation

```bash
npm run html-report -- <run-dir> [output.html]
```

Equivalent direct command:

```bash
node --experimental-strip-types scripts/styrir-html-report.ts <run-dir> [output.html]
```

## Design Standard

The report should feel like a shadcn-style editorial/publishing artifact: dark-mode screen presentation by default, restrained variables, visible borders, compact badges, readable cards for repeated evidence entries, and print CSS. It should avoid landing-page composition, decorative backgrounds, external assets, and oversized UI inside compact panels. Keep print output light for legibility unless the user explicitly asks for dark print.

Required HTML markers:

- `<html lang="en" data-styrir-report>`
- an `Evidence Ledger` section
- print CSS through `@media print`

## Decision Artifacts

Use a separate decision artifact when the search needs recommendations, ranking, or a context-aware summary:

```json
{
  "decisionBrief": {
    "criteria": ["cost", "latency", "source quality"],
    "recommendation": "Use Styrir Plus for contested middle-tier searches.",
    "evidenceIds": ["e1", "e4"]
  }
}
```

The current HTML renderer does not render `takeaways[]` or `decisionBrief`. Leave those to the receiving orchestrator or a future ranking pass with explicit criteria.

## Gating

When `plan.json` contains any of these, the artifact gate requires `report.html`:

```json
{ "htmlReport": true }
```

```json
{ "outputs": { "htmlReport": true } }
```

```json
{ "outputs": { "humanReadable": ["report.html"] } }
```

The gate checks for the Styrir report marker and Evidence Ledger section. It does not verify visual polish; use a browser or print preview for final human-facing publication quality when the report will be shared.
