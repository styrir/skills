# GPT Researcher retrieval backend (`deep_search_local`)

GPT Researcher deep mode can serve as an opt-in source finder for `deep_search_local`. It finds candidate sources; it never writes evidence. The 2026-11-01 bake-off (styrir-os `agent-guidance/research/gpt-researcher-bakeoff-20261101/comparison.md`, Verk vk-2539) qualified it with conditions, and this backend keeps them.

## Selecting it

Set `"retrievalBackend": "gpt_researcher_deep"` in the route request. The route never infers it. With no `forceMode`, the flag selects `deep_search_local`. Combining it with any other `forceMode` is an error. The decision then uses `styrir-search-gate`, has no deep-search-cli handoff, and reports `ledger.json` as its source of truth.

## Running it

```bash
GPTR_PYTHON=/path/to/venv/bin/python npm run gptr-retrieve -- request.json <run-dir> [--cap-usd 1]
```

- **Python:** a venv with `gpt-researcher==0.16.0` (GPT Researcher v3.7.0, the version the bake-off qualified). Check the install with `$GPTR_PYTHON scripts/gptr_deep_sources.py --check`, which makes no network calls.
- **Keys:** the npm script wraps the run in `infisical run` (`styrir` project, `prod`, `/providers`). The adapter reads only the injected `nanogpt` and `tavily` secrets and ignores ambient `OPENAI_API_KEY` and `TAVILY_API_KEY`. GPT Researcher's child process gets an allowlisted environment, so no other secret reaches it.
- **Settings:** NanoGPT models (STRATEGIC `openai/gpt-6.1-sol`, SMART `openai/gpt-6.1-terra`, FAST `openai/gpt-6-luna`, embedding `text-embedding-3-small`), Tavily retriever, `keyword` context filter, breadth 4, depth 2, concurrency 4. These are fixed in `GPTR_SETTINGS`.

## What it does

1. Reads the NanoGPT balance and refuses to start if the balance is below the cap.
2. Runs `scripts/gptr_deep_sources.py`, which calls `conduct_research()` and writes only `{url, title}` per source. It never calls `write_report()` or reads the research context, so no report text exists to leak into observations.
3. Re-fetches every returned URL itself through Tavily extract and saves the text to `fetched/NNN.txt`. Statuses are `ok`, `empty`, `failed`, `error` and `missing`; anything other than `ok` counts as dead.
4. Types each source by domain rule (`classifySource`), using the gate's `sourceType` vocabulary.
5. Asks `openai/gpt-6-luna` on NanoGPT, one page at a time, whether the re-fetched page is on-topic. A failed or unparseable answer is recorded as `unknown` and the source is kept.
6. Drops dead pages, and drops off-topic pages unless they are primary (`legal`, `official`, `academic`). A primary page judged off-topic is kept but ranked last among primaries.
7. Ranks primary sources first, then keeps GPT Researcher's order, and writes `candidate-sources.json`.

## Outputs

- `candidate-sources.json` has `candidates[]` and `dropped[]`. Candidates use the ledger `sources[]` shape (`id`, `url`, `title`, `sourceType`, `fetched: true`) plus `rank`, `primary`, `verdict` and `textFile`. Dropped rows keep their reason (`dead` or `off_topic`) so a person or agent can rescue one.
- `retrieval-manifest.json` records status, settings, judge model, counts and spend. Spend is the before/after balance delta, split into `gptrCostUsd` and `judgeCostUsd`, with `capHit`, `overCap` and `pendingUsageAfter`. GPT Researcher's own cost estimate is recorded as `gptrCostEstimateUsd` for comparison only; it undercounted by 1.5–2.7× in the bake-off.
- `fetched/` holds the re-fetched page text. Write ledger observations from these files, never from GPT Researcher output.

Then write the ledger bundle as for `styrir_plus` (plan, source registry, ledger, contradiction sweep). Run `styrir-search-gate` and `styrir-artifact-gate.ts styrir_plus <run-dir>`. The `deep_search_local` artifact gate expects a deep-search-mcp run directory and does not apply here.

## Spend cap

The default cap is $1 per run, measured as the change in NanoGPT balance. While GPT Researcher runs, the adapter polls the balance every 20 seconds and stops the run if the cap is reached. Reported usage can lag, so a run can overshoot by up to one interval's spend; the final reading still sets `overCap` and exits non-zero. The breadth and depth settings are what really bound spend: $0.43–0.76 per run in the bake-off. Tavily is not metered here. A deep run makes about 60 basic searches plus the extract calls. Those cost nothing on the free Researcher plan, but about $0.47 per run at pay-as-you-go rates.

## Budget semantics

The route's `deep_search_local` budget (10 searches, 10 fetches) covers the ledger you write from the candidates. The searches and re-fetches inside this backend are outside that budget. Record them in the ledger plan's allocation note, as the bake-off did.

The gate blocks when `meta.totalQueriesRun` exceeds `budget.maxSearchQueries`, or `meta.totalSourcesFetched` exceeds `budget.maxFetches`. So do not copy the route's `maxFetches: 10` into a ledger that registers 80 candidates. Use the bake-off's `build_bundle.py` values:

- `meta.mode`: `"styrir_plus"`.
- `meta.totalQueriesRun`: only your own targeted searches (0 if none). Keep it within the route's 10.
- `budget.maxSearchQueries`: the route's 10.
- `meta.totalSourcesFetched`: the length of the ledger's `sources[]`, meaning the candidates you register plus your own fetches.
- `budget.maxFetches`: the same count.

## Measured off-topic judge quality

These figures come from cached bake-off pages (re-fetched text), scored against the bake-off's hand-labelled off-topic lists, before the primary-source exemption was added:

| Question | Pages judged | Hand-labelled off-topic | Caught | Hand-kept pages judged off-topic | Judge cost |
|---|---:|---:|---:|---:|---:|
| Q2 native orb | 107 | 10 | 8 | 1 (a YouTube video) | $0.009 |
| Q1 cockpit prior art | 183 | 7 | 2 | 6 (`slsa.dev` FAQ, which is now typed official and exempt; two tavily.com company pages; a CVE roundup; two product-docs posts) | $0.016 |

The judge catches the gross misses, such as animation-maker sites and wrong-sense pages, and keeps vocabulary-expanded sub-topics. The bake-off's labels were lenient on tangential pages, so the two disagree at the margin. Treat `dropped[]` as a first pass, not a verdict. A plain term-overlap filter was tried first and rejected: it would have dropped most on-topic Q2 pages, because GPT Researcher's sub-queries widen the vocabulary well beyond the question's words.

## Conditions carried from the bake-off

1. It is a source finder, not a curator. Candidates still need a person or agent to read them and write ledger entries.
2. Its report is not evidence. The backend never produces one.
3. Breadth does not replace targeted searches for known authoritative sources. Add facets for specifications or rulings you expect, because the bake-off runs missed A2A, MCP, OpenTelemetry and W3C Web Audio.
4. Measure cost from the provider balance, and budget for Tavily credits.
5. Ranking and filtering exist because writing ledger entries for 80–180 sources was the real cost.
