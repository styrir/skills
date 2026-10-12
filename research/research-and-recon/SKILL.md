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

## Product-price research: exact-variant verification

For shopping and deal-finding requests, treat the requested configuration as a hard constraint, not a suggestion. Before comparing prices, normalize the product identity across:

- exact model/SKU or manufacturer part number;
- body-only versus kit, and the precise included lens/accessories;
- color, finish, and limited/special-edition status;
- new, open-box, refurbished, used, or private-sale condition;
- VAT, shipping, import charges, currency, and destination eligibility.

Search broadly, but report only offers that satisfy every stated constraint. A cheaper body-only unit, standard-color unit, or lensless unit is not an answer to a kit/edition request; label it separately as a non-matching fallback if useful. When no qualifying offer is found, say so plainly and provide the nearest verified offer with the exact shortfall (price difference and any shipping/import uncertainty).

Use a product-comparison page only for discovery when possible; verify the retailer/listing page or a current indexed offer before presenting it as purchasable. Dynamic marketplaces often expose stale or incomplete prices, so mark those prices as requiring checkout verification. Prefer a small evidence table containing seller, exact configuration, condition, displayed price, shipping/tax caveat, and URL over a long undifferentiated list.

## Specialized lane: text-transformation and humanizer tools

When evaluating paraphrasers, style rewriters, translation chains, detector-evasion tools, or writing skills:

- trace the real code path and enumerate every external recipient of the text;
- quarantine first, then inspect the manifest and advertised entry point before running installers, CLIs, tests, package scripts, or containers;
- search for downloader/launcher chains, shell execution, encoded commands, IP literals, install hooks, and code unrelated to the repository's stated purpose;
- verify installation only after pre-execution triage, using the declared CLI, focused tests, and full tests;
- inspect whether quality claims have a reproducible corpus, detector version, scoring code, and command;
- measure meaning and voice preservation, not only detector scores;
- distinguish a standalone tool from an agent skill and recommend a wrapper only when orchestration adds value;
- defang suspicious URLs in every rendered surface because desktop previewers may fetch raw URLs even inside code blocks.

For Brooks, high-register diction is protected content: never equate “humanized” with casualized or simplified prose. Evaluate whether the transformation preserves precise erudition, rhetorical cadence, technical terminology, modality, and authorial idiosyncrasy. Prefer constrained direct editing with a semantic/register audit over blind back-translation; aggressive translation chains should be explicit opt-ins with privacy and drift warnings.

Detailed checklist: `references/text-transformation-tool-evaluation.md`.
Untrusted-source triage, URL defanging, and download-prompt incident verification: `references/untrusted-repository-and-url-safety.md`.

## Common pitfalls

- Treating snippets as proof; always open or extract the source before concluding
- Mixing the observation with the inference
- Using the wrong tool for the question (e.g. docs lookup when you need OSINT)
- Forgetting to record gaps; missing evidence is part of the result
- Repeating vendor detector verdicts without locating the evaluation corpus and scoring path
- Calling locally executed software “local” when it sends text to external LLM or translation providers
- Installing a repository as a skill when it is actually a standalone executable with no `SKILL.md`
- Treating quarantine as permission to execute before reading the real entry point and startup side effects
- Repeating a hostile URL verbatim; renderers may auto-fetch it even when formatted as code

## Absorbed sibling gotchas

- `find-docs`: resolve the library ID first, then query the doc ID; keep queries specific
- `duckduckgo-search`: `max_results` is keyword-only in the Python API; empty results often mean rate limiting
- `perplexity-search`: great for synthesis, not for finding exact URLs; keep the query concise and cite the returned sources
- `competitive-gap-analysis`: clone references outside the project tree, compare against actual code paths, and turn findings into prioritized actions
- `domain-intel`: this is passive reconnaissance only; use it for subdomains, WHOIS, DNS, SSL, and availability, not content extraction

## Related support material

Store session-specific source lists, query recipes, extracted notes, repeatable probes, and reusable prompts in the active project or generated research workspace—not inside this canonical skill unless they become durable shared guidance.
