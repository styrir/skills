# Review of the AI-Q report on Jev use cases

Run: deep-AIQ lane (`StyrirSearch:deep-AIQ`) on the Berlin AI-Q server, job `42c28aad-dbef-4108-bc28-9f632fb88816`, 2026-10-12, about 41 minutes. The report cites 14 sources, but its run state recorded only 4 sources. Checked by Claude Code against the cited pages and `../final-briefing.md`.

## Verdict

The structure is useful, and the catalog of categories and patterns is broadly right. **Don't quote its numbers or deployment claims without the corrections below.** It treated viral posts as cookbooks, cited at least two claims it couldn't source, and missed most of the community tooling that is closest to our own work.

## Claims checked

| Claim in report | Status | Notes |
|---|---|---|
| Primer: three question types, $0.042/M input, free output, 32k state + longest question, 255 options, 2–10 score levels | **Confirmed** | Matches TypeSafe docs and our briefing. |
| Latency 70–500 ms | **Confirmed as TypeSafe's figure** | OpenRouter shows P50 0.13 s. We measured 380–730 ms end to end through Requesty. |
| Nine jaggedness failure modes, including Choice option order | **Mostly confirmed** | TypeSafe lists 9 (last reviewed 2026-10-02). Its #7 is *contradictory instructions and criteria*; the report says "cross-question consistency", which came from our prompt. #8 option order (leans toward the first option) is real and **missing from our briefing**. |
| Torq: prompt sensitivity, class collapse on security triage | **Confirmed** | Torq (2026-09-25): Jev 20–21% accuracy and 3% malicious F1 on GUIDE-Microsoft IDS, against Gemini Flash ~46–50% and Torq Reflex 70–80%. It's a vendor test of zero-shot use outside Jev's intended scope. |
| Thoughtworks RAG patterns and the 0.9 / 0.6 confidence bands | **Confirmed** | Routing before retrieval, chunk scoring, a "do we have enough context?" Noul, and per-claim checks after generation. |
| KodeKloud `jev-ops-triage` (alert triage, CI failure classifier, command guardrail, K8s shadow mode) | **Confirmed** | A tutorial, not a deployment. Cost example: 50k alerts/day ≈ $1.26/day. |
| `jev-review` staged code review | **Confirmed** | An experiment with 5 commits. The report's quote "Local-first reference implementation… not a production deployment" is paraphrased, not verbatim. |
| kamchatka assisted shell | **Confirmed** | Listed in awesome-typesafe-jev. |
| "384 stories × 15 brands in 24.9 s for $0.19" | **Misattributed** | From a viral X post by @elvissun (2026-09-18) about an open-source PR-agent setup (newsjack.sh), not an OpenRouter moderation cookbook. Self-reported and unverified. |
| "1,700 emails triaged for $0.18" | **Unsourced** | Not found in any cited page or by search. |
| Neon `pg_redact` PII detection with Jev | **Unsourced** | Not in the source list, and not found by search. |
| LangGraph multi-agent orchestrator video | **Not checked** | The YouTube source is listed but wasn't fetched. |
| "No documented production case studies" | **Too strong** | awesome-typesafe-jev lists BTK's *production* SEO audit studies (1,204 pages per run, jev-1.13.0) and a production e-commerce comment-triage case study. There are still few production reports and almost all are self-reported. |

## Gaps: use cases the report missed

From the awesome-typesafe-jev list, Firecrawl, and a Hyperstack write-up. These cover the closest prior art for `jev-guard`, WorkGraph and session-eval:

- **Agent hooks:** `jev-belay` (Claude Code Stop hook that checks "done" claims, fails open), `jev-commit` (pre-commit check of message vs diff; blocks only on credentials), `jev-lint` (fuzzy team-rule linter for Claude Code and Codex edits, fails open), `jev-skill-router` (UserPromptSubmit skill suggestion in shadow mode).
- **Routers:** Codex Jev Router (subagent routing with a fallback when Jev fails), and Hermes Jev Skills (model routing, passage filtering, skill selection, shadow mode). The latter is directly relevant to our Hermes setup.
- **Eval:** `pytest-jev` (semantic assertions on LLM output), Second Thought (calibration plus a human-review queue), and LangChain's "Jev-as-a-Judge for Agent Evals". Hyperstack cites that LangChain post for an average of $0.00035 and 0.44 s per call against judges of up to $0.028 and 2.8 s. That's relevant to `session-eval`; the LangChain post itself wasn't checked.
- **Reranking:** TypeSafe's rerank cookbook (legal retrieval top-1 accuracy from 5% to 18%, top-10 from 38% to 62%, 1,200 calls for $0.0645), and a hierarchical classification cookbook.
- **Browser and UI:** PlotVeil (spoiler gating that fails closed, so comments stay hidden).
- **Caution for ranking (news-intel P1):** `jev-orderby-bench` found that sorting by a Jev probability passed on topic membership but **failed 4 of 6 conditions** on human-graded product relevance. Ties at 0.99 and batching changed the rankings. Test the ranking itself before swapping the news-intel scorer (`skills-6z3.5`).
- **Independent calibration audits:** `jev-calibration-audit` (option order, abstention), `jev-fanout-bench` (batched vs separate calls), `jev-measured`.

## Takeaways for our work

1. Add *option order* and *contradictory criteria* to the weak spots in our Jev skill and briefing. For routing Choices, reorder the options and check the answer stays the same.
2. Before `skills-6z3.5`, calibrate on our own labeled feed and test the ranking, not just the threshold.
3. Compare `jev-guard` with `jev-belay`, `jev-commit` and `jev-lint`; they made the same fail-open choices.
4. About the lane itself: on a niche, fast-moving topic, deep-AIQ found few sources and passed off a viral post as documentation. Use it for breadth and structure, and check every number before relying on it.
