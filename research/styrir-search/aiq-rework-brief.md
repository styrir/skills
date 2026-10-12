# Brief: reworking the StyrirSearch deep-AIQ lane

Date: 2026-10-12. Status: **reviewed and confirmed** (independent review: approve with changes; all changes applied, see "Review log"). Tracking: `skills-r5e`.

## Summary

The deep-AIQ lane runs end to end, but it produces weak results slowly. Most of the causes can be fixed. Inferred causes are marked as such.

- **Performance.** Our one full research run took about 41 minutes. About 20 of those went to four model calls, each cut off at about 300 s and then resent unchanged [E2]. The evidence suggests these were **long generations hitting a time limit of about 300 s**, not stalled calls. For example, the writer's retry legitimately took 292 s to produce 9,943 tokens [E2]. The free-tier rate limit was not the bottleneck: we made 2.3 requests per minute on average and saw no 429 errors [E1]. AI-Q v2.2.1 has no per-call timeout setting, and every research batch waits for its slowest researcher [C4, C7].
- **Citations.** The report body contains **no inline citations** [E4, N3], even though AI-Q's writer prompt requires them [N3]. The unsourced and misattributed figures in the report were therefore **never cited**. They weren't cited and then removed. Separately, AI-Q's citation check removed 12 of the 26 bibliography entries [E4]. Why the writer skips inline markers has not been determined.
- **Retrieval depth.** Researchers saw only search snippets: 2 Tavily results per query, and no full-page fetch [E3, C1]. The run found 88 sources and cited 14 [E3]. Our skill doesn't save the record of what was found and cited, so we only have it for this run because the runner was written by hand [S3]. Retrieval is close to AI-Q's hard limit of 100 source-tool calls per job, so more depth has to come from better searches, not more of them [E3, C6].
- **No safety net in our skill.** It has no runner, no handling of failed or cancelled jobs, no check on AI-Q's output, and no rule for when AI-Q is a poor fit [S1, S2, S7, S9].
- **Gap to NVIDIA's best result.** NVIDIA's top DeepResearch Bench entry scored 55.95. It combined GPT-5.2 for orchestration, a fine-tuned researcher, two pipelines merged into one, paper search, a 12,000 s budget, and **an LLM rewrite of each report after the run** [N1, N4]. Our report looks like their earlier v1 entry (40.52) [N2, N3]. Some of that is within reach on v2.2.1: paper search, a rewrite step on our side, and trying a frontier writer. The full ensemble setup is not.

## Evidence base

| Source | What it is |
|---|---|
| Run `42c28aad` | Deep job of 2026-10-12, about 41 min, on Berlin. Files: `research/jev/aiq-use-cases-20261012/` (`request.json`, `manifest.json`, `submit.json`, `state.json`, `report.md`, `review.md`). The question covered more than 13 categories. |
| Berlin `aiq-agent` logs | 10:40–11:24Z, 2,367 lines, read only. Excerpt kept at `scratchpad/clean.log` for this session; not committed. |
| Berlin config | `/srv/styrir/apps/aiq/configs/config_web_default_llamaindex.yml` (upstream default, unchanged) |
| Our skill | `styrir-search/scripts/*.ts`, `styrir-search/references/*.md`, `styrir-search-deep-aiq/SKILL.md` |
| AI-Q v2.2.1 | `~/Code/aiq` at tag `v2.2.1`; `drb1` branch fetched read-only; docs.nvidia.com/aiq-blueprint |
| NVIDIA reference reports | DeepResearch Bench leaderboard (HF space `muset-ai/DeepResearch-Bench-Leaderboard`), 50 English tasks per entry. The metrics script was ad hoc (see plan item 9). |

Citation keys: **S** = skill, **E** = run evidence, **C** = Berlin config and server, **N** = NVIDIA reference, **U** = upstream API, **R** = `review.md`.

## Findings

### A. Our client skill (`skills` repo)

| # | Finding | Evidence |
|---|---|---|
| S1 | **No runner.** The manifest is four curl lines with `<job-id>` and `<run-dir>` placeholders. It has no poll interval or timeout and doesn't capture the job ID, so every agent writes its own loop. | `styrir-handoff-manifest.ts:78-81` |
| S2 | **Incomplete terminal states, and no failure, cancel or resume handling.** The docs list uppercase statuses (`SUCCESS/FAILURE/INTERRUPTED`), but Berlin returns lowercase: `"success"` from a live GET and `"submitted"` in `submit.json`. The skill never treats `interrupted` as finished. A `failure` can still carry a report. | `handoff-manifest.ts:80`; `aiq rest-api.md:211-220` |
| S3 | **The skill keeps only the report text.** `/state` holds `sources{found, cited, found_urls, cited_urls}`, plus citation use and tool calls, and the skill never fetches it. AI-Q's route outputs list only `route-decision.json` and `handoff-manifest.json`. This run has `state.json` only because its runner was written by hand. | `handoff-manifest.ts:81`; `styrir-route.ts:306`; `rest-api.md:272-315` |
| S4 | **A missing report turns into the text "None".** The code reads `["report"]` without checking `has_report`, and exits 0. | `handoff-manifest.ts:81`; `rest-api.md:417-439` |
| S5 | **The request shape is fixed.** It always asks for `deep_researcher` and never sets `data_sources`, `job_id` or `expiry_seconds`. The source scope is sent as plain prose. | `handoff-manifest.ts:73-76` |
| S6 | **The objective is never sent, and user premises leak into findings.** `objective` doesn't reach the request, so claims written into the question come back looking like findings. | `handoff-manifest.ts:107, 127`; `review.md:15` |
| S7 | **No artifact gate for AI-Q.** `ArtifactMode` covers only plus and deep-local, and the route sets `gate: "handoff-only"`. | `styrir-artifact-gate.ts:7`; `styrir-route.ts:401` |
| S8 | **The route promises outputs nobody produces.** It marks the contradiction sweep `"required"` and makes `ledger.json` the source of truth, but AI-Q produces neither. | `styrir-route.ts:402`, `:312` |
| S9 | **AI-Q is reachable only through `forceMode`, and there's no poor-fit guidance.** `inferMode` never returns `nvidia_aiq_handoff`. This run's lesson (niche, fast-moving topics) isn't in the routing docs. | `styrir-route.ts:316-347`; `review.md:44` |
| S10 | **AI-Q budgets mean nothing.** `maxSearchQueries: 10` and the other budget fields are never sent. The real limits are wall-clock time and the server's caps. | `styrir-route.ts:85`; `resource_limits.py:18-33` |
| S11 | **Some docs disagree with the code.** They talk about external spend and budget approval, and say to "treat the shipped wrapper as a convenience path until … configured". SKILL.md promises a health gate the code doesn't run. (The "not wired" blocker at `handoff-manifest.ts:147` fires only when there's no `aiqBaseUrl`, which is correct, so keep it.) | `modes-and-recipes.md:77, 86, 90, 174`; `styrir-search/SKILL.md:171` |
| S12 | **The health check looks only at the HTTP status.** `curl -sf` passes on any 2xx. The classifier that reads the response body runs only in tests, and `db` and `dask_available` are never checked. | `handoff-manifest.ts:85-103` |
| S13 | **Tests never call the server or decode the request body.** They only look for substrings. Quote escaping, the poll contract and null reports are untested. | `styrir-handoff-manifest.test.ts:152-176` |

### B. Run evidence (job `42c28aad`)

| # | Finding | Evidence |
|---|---|---|
| E1 | **Time by phase:** orchestrator 1.3 min; planner 3.3 min; research batches 3.7, 13.5 and 6.3 min; writer 11.7 min; finalize 0.7 min. There were 94 LLM calls, all to Nemotron 3 Ultra, using 1,758,096 prompt and 58,638 completion tokens; 92 `advanced_web_search_tool` calls plus 16 `knowledge_search` calls; and no 429s. | Berlin logs 10:41:17–11:22:10 |
| E2 | **Four calls were resent identically after about 300 s:** two in batch 2, one in batch 3 and one in the writer. Calls that did finish ran long: the writer's retry took 11:16:33→11:21:25 for 9,943 completion tokens, and the batch-2 fallback took 11:00:07→11:03:00 for 3,125. The likely cause is generations longer than about 300 s hitting a client or gateway time limit *(inferred)*. The cut-off attempts logged no token counts, so the reason isn't directly visible. Every batch waits for its slowest researcher: in batch 2, five finished by 10:55:57 and the sixth at 11:03:00. The "tools-disabled JSON" fallback fired twice, and LangChain warned that Ultra "is not known to support tools", which may explain those fallbacks *(inferred)*. | Logs 10:50:10→10:55:06→11:00:07, 11:03:43→11:08:44, 11:11:28→11:16:30; log line 2236; `custom_middleware:159`; log line 33 |
| E3 | **Retrieval was shallow and close to the cap.** Each Tavily advanced search returned 2 results, and there was no fetch tool. The run found 88 distinct URLs (86 in the verification registry) and cited 14. It made 108 source-tool calls in total, against a cap of 100 source-tool calls per job, and ran 17 researcher queries against a cap of 20 *(the precise accounting depends on how AI-Q counts calls)*. The 16 `knowledge_search` calls went to a collection that doesn't exist (`test_collection` not found). Only 2 of the 17 researcher notes survive in the state. | Logs 10:43:43; `state.json`; `resource_limits.py:29` |
| E4 | **The final report has no inline citations.** It has 0 `[n]` markers before `## Sources`. The final citation check removed 12 bibliography entries (`url_not_in_registry`). The verifier strips only orphaned markers, so the *writer* most likely emitted none *(inferred; `state.json` holds only the post-verification output)*. The Neon page was retrieved but never cited. | Logs 11:22:09; `citation_verification.py:1022, 1498`; `report.md` |
| E5 | **The context is bloated.** Orchestrator prompts reached 59–69k tokens because they carry a 42k-character notes blob. Finalize used 431k prompt tokens to produce 380 completion tokens. Writer prompts grew from 4.8k to 30k over 24 sequential `read_file` calls. The planner also ran 18 web searches itself. | `[Tokens]` log lines |

Corrections to `review.md`: `artifacts.sources` holds four *field names*, not four sources. The Neon `pg_redact` page was retrieved but not cited.

### C. Berlin server configuration (`styrir-server` repo `aiq/`, plus `/srv/styrir/apps/aiq/configs`)

| # | Finding | Evidence |
|---|---|---|
| C1 | Deep research uses only `advanced_web_search_tool`, which is Tavily with `max_results: 2`, and excludes the 5-result basic tool. NVIDIA's leaderboard setup also used 2 results, so result count alone doesn't explain the quality gap. | config `:164-167`, `:230-231`; drb1 `config_ensemble.yml` |
| C2 | Paper search is commented out. It needs `SERPER_API_KEY`. | config `:180-185` |
| C3 | `knowledge_layer` is enabled by default although no collection exists. | `GET /v1/data_sources` (`default_enabled: true`); logs 10:43:43 |
| C4 | There's **no per-call LLM timeout setting** in v2.2.1's model config. `llm_timeout` applies only to the intent call. Calls get `num_retries: 5`. | `configuration-reference.md:119-130`; config `:49-109` |
| C5 | Research concurrency is 6, with up to 5 concurrent source-tool calls. | `agent.py:60`; `source_tool_batching.py:40-41` |
| C6 | Per-job hard caps: 3600 s, 20 queries, 100 source-tool calls. They can be lowered but not raised. | `resource_limits.py:18-33`; `production.md:270-280` |
| C7 | Research batches wait for every researcher via `asyncio.gather` with no timeout. Skipping a straggler needs a code change. | `tools/research.py:167` |

### D. Comparison with NVIDIA's reference reports

| # | Finding | Evidence |
|---|---|---|
| N1 | NVIDIA published full reports for two AI-Q versions. `nvidia-aiq-nemotron-gpt52-updated` scored 55.95: it was #1 when submitted and is 11th of 45 now. The v1 entry, `nvidia-aiq-research-assistant`, scored 40.52. Neither entry has a published FACT (citation-accuracy) score. | HF space `data/leaderboard.csv`, `data/raw_data/*.jsonl`; HF blog `nvidia/how-nvidia-won-deepresearch-bench` |
| N2 | Medians for the current entry, v1 and our run: about 11–12k / 4.1–4.3k / 4.4k words; 43.5 / 13.5 / 14 distinct URLs; 7 / 0 / 31 tables. The current entry reads as analytic prose with tables; ours is mostly tables and bullets. **Caveat:** NVIDIA's leaderboard reports were rewritten by an LLM after the run (N4), so this compares post-processed output with raw output. | Scout metrics, recomputed independently in review |
| N3 | Inline citations per 1,000 words: current entry about 20–23, v1 0, ours 0 in the body. AI-Q's writer prompt requires inline `[1]` citations. | `writer.j2:89` |
| N4 | The leaderboard setup used GPT-5.2 for orchestrator, planner and merger; a fine-tuned Nemotron-3-Super researcher (`max_tokens: 128000`); two pipelines plus an LLM merger; a 12,000 s timeout; and **a step that rewrites each report with Claude Opus** (`rewrite_prompt.py`). v2.2.1's own benchmark config uses Ultra in every role with paper search. (Its `max_loops` key isn't read anywhere in v2.2.1's source.) | drb1 README step 4; drb1 `config_ensemble.yml`; `frontends/benchmarks/deepresearch_bench/configs/config_deep_research_bench.yml:20-63` |
| N5 | NVIDIA's sources are mostly primary or scholarly (doi.org, ScienceDirect, IEEE, arXiv, PMC). Ours are 14% social and mostly blogs. Part of that is our topic; part is that paper search is off. | Scout domain counts |

### E. Upstream features we can use from the client today

| # | Feature | Evidence |
|---|---|---|
| U1 | SSE stream with replay and reconnect. It emits `job.status`, `job.update` (a retry signal), `tool.*`, `artifact.update`, and a heartbeat every 30 s. | `rest-api.md:32-33, 222-249, 445-459` |
| U2 | `/state` for the record of sources found and cited | `rest-api.md:272-315` |
| U3 | `/report/edit`: a cheap follow-up revision, including a rewrite or citation pass, without a new deep run | `rest-api.md:136-178` |
| U4 | `/cancel` | `rest-api.md:251-270` |
| U5 | `job_id` is collision-checked (a duplicate returns 409, so re-attach instead of resubmitting). `expiry_seconds` accepts 600–604,800. `data_sources` scopes the sources. | `jobs.py:299-310, 983`; `rest-api.md:92, 110-112, 600-621` |
| U6 | 429 and 503 responses carry `Retry-After`. A 413 means the input is over 32,768 characters. | `rest-api.md:106-114` |
| U7 | Async submit goes straight to the deep agent, and the clarifier only runs in the `/chat` workflow, so the client must send a fully scoped question *(inferred from config)*. | config `:202-209`, `:238` |

## Recommended plan

Ordered by impact relative to effort. **Repo** says where each change lands. Effects are expected, not yet measured.

| P | Change | Repo | Expected effect | Basis |
|---|---|---|---|---|
| 1 | **Runner `styrir-aiq-run.ts`.** Checks health with the classifier and `db=="ok"`. Submits with a deterministic `job_id` and re-attaches on a 409. Follows the SSE stream, falling back to polling every 30 s, and gives up at 70 minutes. Compares statuses case-insensitively, treats `interrupted` as terminal, and cancels on timeout. Writes `submit.json`, `status.json`, `state.json` and `report.md` (checking `has_report`), and records `job.update` retry events. Adds an opt-in live smoke test (`AIQ_LIVE=1`, shallow job). | skills | Reliable, resumable, auditable runs, plus the retry data needed for item 3 | S1–S4, S12, S13, U1–U5 |
| 2 | **Artifact gate for `nvidia_aiq_handoff`, warn mode first.** Flags a body with no inline `[n]`, any `[n]` that doesn't resolve, and cited URLs missing from `state.json` `cited_urls`. Flags numeric claims for review and reports the found and cited counts. Switch it to fail-closed once item 6 produces cited bodies. Set the route's `gate` and `outputs` honestly. | skills | Makes uncited reports visible without blocking every run today | S7, S8, E4, N3 |
| 3 | **Diagnose the ~300 s cutoffs before tuning anything.** Use the retry events from item 1 and a single-call reproduction to find which layer cuts at 300 s (LangChain NVIDIA client, httpx, or the API gateway). Then: raise or align that limit for writer calls, cap `max_tokens` on structured ResearchNotes calls, and file the straggler behaviour upstream (C7). Don't shorten timeouts: the writer legitimately needs about 300 s. | styrir-server + upstream issue | Plausibly most of the 20 lost minutes *(not measured)* | E2, C4, C7 |
| 4 | **Narrow and shape the request.** Send the objective and the expected output shape. Wrap user premises as "unverified premises to check". Choose deep or shallow, set `expiry_seconds`, and send `data_sources: ["web_search"]` (or remove `knowledge_layer` on the server). Split broad questions (this one had more than 13 categories) into several jobs so each stays inside the 20-query and 100-tool caps. | skills (+ server for C3) | Fewer laundered premises, about 16 fewer wasted calls, more depth per topic | S5, S6, U7, E3, C3, C6 |
| 5 | **Paper search.** Add `SERPER_API_KEY` to Infisical `styrir/prod/aiq`, add it to the `styrir-refresh-aiq-env` key list, and enable `paper_search_tool`. It costs tool calls from the same cap of 100. | styrir-server | More primary and scholarly sources | C2, N5 |
| 6 | **Investigate inline citations, and add a client-side refiner.** Test whether the Ultra writer ignores `writer.j2:89` (for example, run one job with a frontier writer). Separately, try a post-run pass, either `/report/edit` or a client LLM rewrite like NVIDIA's `rewrite_prompt.py`, that adds inline citations against `state.json` `cited_urls` and drops or flags uncited claims. | styrir-server / skills | Cited report bodies, which is what lets the item 2 gate go fail-closed | E4, N3, N4, U3 |
| 7 | **Routing guidance and doc cleanup.** Say when AI-Q is a poor fit: niche or fast-moving topics, exact numbers, narrow domains. In those cases use deep-local, or follow AI-Q with a plus contradiction pass. Fix the stale spend and convenience-path text and the health-gate promise. Keep the "not wired" blocker for the no-URL case. | skills | The right lane gets chosen, and the docs stop misleading | S9–S11 |
| 8 | **Model experiment.** Try `config_frontier_models.yml`, or a frontier model only for the writer and orchestrator, on a fixed question, using the item 9 measurement protocol. | styrir-server | The biggest quality lever available on v2.2.1 *(inferred from N4)* | N4 |
| 9 | **Measurement script.** Commit a metrics script covering words, distinct URLs and domains, inline citations per 1,000 words in the body, found and cited counts, wall time, and retry events. Use it for N2, N3 and all acceptance checks. | skills | Reproducible comparisons | Review issue 4 |
| 10 | **Context trimming.** Cover the orchestrator notes blob and the writer's repeated reads. File upstream, or change config if the setting is exposed. | upstream | Lower latency and token use | E5 |

Out of reach on v2.2.1: the full leaderboard setup (ensemble, merger, 12,000 s budget) needs the `drb1` branch, because v2.2.1 caps runs at 3600 s [N4, C6]. The rewrite step is within reach (item 6).

**Costs and rollback.**
- Paper search needs a Serper plan.
- The frontier-model profile needs an `OPENAI_API_KEY` and is billed per token.
- More searches spend Tavily credits.
- All server changes go through the `styrir-server` `aiq/` override and the config under `/srv/styrir/apps/aiq/configs`. Roll back with git there and the runbook's deploy command, keeping a copy of the default config before editing.
- Paid keys are an owner decision (open question 3).

## Acceptance measures

Use the item 9 script on a **baseline** (job `42c28aad` plus two more runs of the same question on the current setup). Then measure again after items 1–4, and again after item 6. Run at least 3 times per condition and report the median, because a single run of this pipeline isn't a measurement.

| Metric | Baseline (job `42c28aad`) | Target |
|---|---|---|
| Wall time | ~41 min | Set after item 3's diagnosis |
| Retry events from ~300 s cutoffs | 4 | 0 after item 3 |
| Wasted `knowledge_search` calls | 16 | 0 after item 4 |
| Found vs cited sources | 88 / 14 | Report both; no fixed target |
| Inline citations per 1,000 words (body) | 0 | ≥ 10 after item 6 |
| `review.md` problem classes recurring (misattributed, uncited figures, missed list contents) | 3 | Fewer, checked by a manual review of one run |

## Open questions

1. Which layer enforces the ~300 s limit, and is it configurable without code changes (E2, C4)?
2. Does the Ultra writer omit inline markers, or does something before verification strip them (E4)? `state.json` holds only the verified output, so this needs a run with the writer's draft captured.
3. Are paid keys (Serper; OpenAI for frontier roles) acceptable for this lane?
4. How does AI-Q count its 100 source-tool calls, and do the planner's searches count toward that cap (E3)?

## Review log

An independent reviewer (critic agent) checked about 75% of the citations, including against the logs, the live server and the leaderboard data. Verdict: approve with changes. Every change was applied after the orchestrator confirmed the claims in the source:
- **Blocker.** The draft said the ~300 s waits were stalls and proposed shortening timeouts. The writer's legitimate 292 s / 9,943-token call shows they're long generations. There's no per-call timeout setting, and skipping a straggler needs code (`research.py:167`). Item 3 was rewritten.
- **Citation story.** The body had 0 markers, so the claims were uncited, not removed. The draft in `state.json` isn't available. E4 and item 6 were rewritten.
- **Retrieval caps.** The run was near the cap of 100 source-tool calls, and NVIDIA's setup also used 2 results per search. Item 4 now leads with scoping.
- **Acceptance.** Now baseline plus a median of at least 3 runs, using a committed metrics script.
- **Out of reach.** The drb1 Claude Opus rewrite step is reachable from the client side. Added to item 6, with a caveat on N2.
- **Minor.** Gate in warn mode first. S3 reworded. "Not wired" blocker kept. Citations fixed (U7, 409 at `jobs.py:983`, `max_tokens` wording, 86 vs 88). The `max_loops` note, costs, rollback and the tools warning were added.
