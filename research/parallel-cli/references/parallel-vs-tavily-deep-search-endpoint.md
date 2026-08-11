# Parallel vs Tavily for Deep Search-style endpoints

Use this when evaluating Parallel as a backend for a local `DEEP_SEARCH_WEB_SEARCH_ENDPOINT`-style router, especially when comparing it with Tavily.

## Endpoint-fit conclusion

Parallel is useful, but neither Parallel Task API nor Parallel Search API is a direct drop-in for a simple GET endpoint contract like:

```text
GET /search?q=<query>&limit=<n>
-> {"results":[{"title":"...","url":"...","snippet":"..."}]}
```

Reasons:
- Parallel Search API uses POST JSON and `x-api-key` auth.
- Parallel Task API is asynchronous, task/research-oriented, and returns structured/cited task outputs rather than a plain search-result list.
- A local normalizing adapter/router is the right integration boundary.

Deep Search repo note: `/Users/brooks/Code/refs/deep-search` now has an in-process Parallel Search adapter. Configure it with `PARALLEL_API_KEY` plus `DEEP_SEARCH_WEB_SEARCH_ENDPOINT=provider:parallel`, or call `deep-search-mcp web-search --provider parallel`. The adapter keeps stdlib-only dependencies, sends POST `/v1/search`, normalizes `results[].excerpts` into `snippet`, includes the original query as `objective`, clamps `max_results` to 50, and bounds `search_queries[0]` to 200 characters.

Recommended router shape:

```text
DEEP_SEARCH_WEB_SEARCH_ENDPOINT=http://127.0.0.1:8765/search

GET /search?q=...&limit=...
  -> Parallel Search API by default
  -> Tavily when search+extract/content depth matters
  -> local SearXNG as no-key fallback

POST/GET /task or explicit orchestration command
  -> Parallel Task API for structured async research/enrichment
```

Normalize every backend to:

```json
{
  "results": [
    {"title": "...", "url": "...", "snippet": "..."}
  ]
}
```

## Cost comparison snapshot

Parallel Search API:
- $0.005/request
- $5 per 1,000 searches
- Pricing page advertised up to 16,000 free requests.

Tavily Search:
- 1,000 free API credits/month.
- PAYG: $0.008/credit.
- Basic search: 1 credit/request = $8 per 1,000 on PAYG.
- Advanced search: 2 credits/request = $16 per 1,000 on PAYG.
- Volume plans reduce basic search down toward $5 per 1,000 at Growth tier.

Plain search comparison:
- Parallel Search is cheaper than Tavily PAYG basic: $5 vs $8 / 1K.
- Parallel Search is much cheaper than Tavily PAYG advanced: $5 vs $16 / 1K.
- Parallel Search is roughly equal to Tavily Growth basic: $5 vs $5 / 1K.

Parallel Task API:
- Published range: $5 to $2,400 per 1,000 task runs.
- Per run: $0.005 to $2.40 depending on processor.
- Best for structured web research, enrichment, reports, citations, reasoning, confidence, and async workflows.

Tavily Research:
- Dynamic credit pricing.
- Mini: 4–110 credits/request.
- Pro: 15–250 credits/request.
- At PAYG $0.008/credit: Mini ≈ $0.032–$0.88; Pro ≈ $0.12–$2.00.

Research comparison:
- Parallel lower processors can be cheaper and more predictable for repeated structured enrichment.
- Tavily may be simpler for search/extract ergonomics and content retrieval.
- Parallel high-end Ultra processors can exceed Tavily Research costs, but provide heavier async research depth.

## Recommendation pattern

Do not replace Tavily blindly with Parallel.

Use:
- Parallel Search API as the default cheap production search backend behind an adapter.
- Tavily for search + page extraction/content depth workflows.
- Parallel Task API for P2 orchestration, structured research, enrichment, and cited async reports.
- SearXNG as local no-key fallback.

Avoid presenting Parallel Task API as just another web search endpoint. It is a higher-level research/enrichment primitive.
