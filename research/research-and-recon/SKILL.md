---
name: research-and-recon
description: "Umbrella workflow for web research, docs lookup, competitive analysis, OSINT/domain reconnaissance, and evidence-led source discovery. Use this when you need to find, compare, or verify information across public sources rather than a single API/tool."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [research, recon, osint, docs, web, competitive-analysis, citations, source-discovery]
    related_skills: [deep-search-cli, tavily-cli, structured-search-agent, mixed-model-development]
---

# Research and Recon

This umbrella covers the full research workflow: locating sources, extracting content,
verifying domain facts, and turning findings into decision-grade notes.

## Absorbed sibling skills

- `find-docs` — current developer docs / library lookup workflow
- `duckduckgo-search` — fallback web search when the primary web tool is unavailable
- `perplexity-search` — synthesis-first web search for broad research sweeps
- `competitive-gap-analysis` — compare a reference implementation against ours and turn gaps into actions
- `domain-intel` — passive domain reconnaissance (WHOIS, DNS, SSL, subdomains)

## When to use

Use this skill when you need to:
- locate authoritative docs or API references
- search the web for current, grounded information
- compare products, repos, or architectures and extract action items
- perform passive OSINT / domain intelligence
- separate evidence from inference before handing results to planning or implementation

## Core workflow

1. Define the question precisely. Prefer a narrow, testable prompt.
2. Pick the right search/extraction path:
   - docs lookup for API syntax or library behavior
   - web search for discovery and broad comparison
   - extraction for a known URL
   - passive domain intel for DNS/WHOIS/SSL/subdomains
3. Capture evidence with URLs, snippets, timestamps, or command output.
4. Separate facts from interpretation.
5. Write the result so it can be turned into a spec, brief, or task list.

## Tool choice guide

Source-specific lanes absorbed into this umbrella:
- `arxiv` — academic paper discovery by keyword, author, category, or ID.
- `blogwatcher` — RSS/Atom/blog monitoring for ongoing source tracking.
- `llm-wiki` — build/query interlinked markdown knowledge bases for LLM/wiki-style research.
- `polymarket` — read-only prediction-market lookups for markets, prices, orderbooks, and history.
- `youtube-content` — transcript extraction and transformation into summaries, threads, or briefs.

- `deep-search-cli` when you need CLI-first auditable research runs, JSON ledgers, source/evidence/claim gates, code/docs retrieval, or Parallel-backed search through the local `deep-search-mcp` adapter
- `tavily-cli` when you have Tavily available and want search/extract/crawl/research
- `find-docs` when you need current library docs quickly
- `duckduckgo-search` when you need a free fallback search path
- `perplexity-search` when you want synthesized research with citations
- `domain-intel` when the question is about a domain, DNS, SSL certs, or availability

## Prompt patterns

### Fast conflict/news sweep with xAI/Grok or synthesis-first search

When a fast search tool tends to over-index on viral or OSINT/social posts, include explicit source-balancing instructions in the query. Example:

> Balance sources across: (1) primary official sources such as government/military, UN/IAEA/NATO/EU/US officials; (2) established wires/news; (3) OSINT analysts and geolocated evidence. Do not rely only on viral posts. Separate confirmed primary-source claims from OSINT claims and unverified reports. Include source-type labels and note disagreements or gaps.

Use this especially for live wars, crises, elections, sanctions, and fast-moving security events. Treat the model's answer as a source-discovery/synthesis pass, then verify decision-critical claims against primary or wire sources.

## Output standard

A good research result includes:
- source list with URLs or command transcripts
- short fact statements, one per bullet
- explicit gaps / unanswered questions
- a clear recommendation or next step

## Common pitfalls

- Treating snippets as proof; always open or extract the source before concluding
- Mixing the observation with the inference
- Using the wrong tool for the question (e.g. docs lookup when you need OSINT)
- Forgetting to record gaps; missing evidence is part of the result

## Absorbed sibling gotchas

- `find-docs`: resolve the library ID first, then query the doc ID; keep queries specific
- `duckduckgo-search`: `max_results` is keyword-only in the Python API; empty results often mean rate limiting
- `perplexity-search`: great for synthesis, not for finding exact URLs; keep the query concise and cite the returned sources
- `competitive-gap-analysis`: clone references outside the project tree, compare against actual code paths, and turn findings into prioritized actions
- `domain-intel`: this is passive reconnaissance only; use it for subdomains, WHOIS, DNS, SSL, and availability, not content extraction

## Related support material

Store session-specific source lists, query recipes, extracted notes, repeatable probes, and reusable prompts in the active project or generated research workspace—not inside this canonical skill unless they become durable shared guidance.
