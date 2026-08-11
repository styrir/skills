---
name: structured-search-agent
description: "Bounded web research with evidence ledger output. Produces a YAML ledger with strict observation/inference separation, confidence levels, and source attribution. Used by Scout agents in the mixed-model pipeline before writing a Builder Brief. Also usable standalone for any structured research task."
version: 1.0.0
author: Hermes Agent (ported from OpenClaw structured-search skill)
metadata:
  hermes:
    tags: [research, scout, evidence, search, ledger]
    related_skills: [scout-profile, mixed-model-development, tavily-search, tavily-extract]
---

# Structured Search Agent

Run bounded web research and produce a rigorous evidence ledger YAML.

Ported from OpenClaw `structured-search` skill. Uses Hermes CLI tools (tavily CLI or
web_search/web_extract) instead of MCP tools.

---

## When to Use

- Scout agent needs external dependency/API/library research before writing a Builder Brief
- Keeper needs to populate mission brief with upstream findings
- Any task requiring sourced, auditable research with observation/inference separation

---

## Config (inline or YAML)

```yaml
topic: "SurrealDB embeddings provider abstraction"
objective: "Find current best practices for provider abstraction patterns in embedding clients"
entities: ["SurrealDB", "Ollama", "Nomic"]
signal_types: ["api_changes", "breaking_changes", "best_practices", "examples"]
period:
  lookback_days: 90
depth: standard
budget:
  max_search_queries: 10
  max_sources_to_extract: 8
output:
  path: ".pipeline/research-embeddings.yaml"
  format: yaml
  include_source_appendix: true
```

---

## Execution Flow

### 1. Validate Config
- `topic` not empty
- `objective` not empty
- Budget values set (defaults: max_search_queries=10, max_sources_to_extract=8)
- Note entities, signal_types, lookback_days

### 2. Generate Search Queries
Stay within `max_search_queries` budget.

**If entities provided:**
- 1-2 queries per entity, tailored to objective
- 1-2 cross-cutting queries comparing entities or covering the landscape

**If entities NOT provided:**
- 3-4 broad landscape queries
- 2-3 specific drills on objective aspects
- Reserve 2-3 for follow-up after seeing initial results

**All queries should:**
- Include current year or recent time markers when relevant
- Target primary sources (official sites, docs, announcements)
- Be specific enough to avoid generic results

### 3. Execute Searches
Use tavily CLI or web_search tool:
```bash
tvly search "<query>" --json
# or: web_search(query="...")
```

For each result: record URLs, snippets, flag primary sources and substantive pages worth extraction.

**Adaptive:** After first 4-6 searches, review gaps. Use remaining budget for targeted follow-up.

### 4. Extract Key Pages
From collected URLs, select the most promising. Budget: `max_sources_to_extract`.

Priority order:
1. Official/primary sources (docs, announcements, changelogs)
2. Substantive analysis (not news blurbs)
3. Pages with technical specs, code examples, concrete data
4. Comparisons covering multiple entities

```bash
tvly extract "<url>" --json
# or: web_extract(urls=["url1", "url2"])
```

Skip: generic listicles, paywalled pages, clearly outdated content.

### 5. Extract Discrete Observations
Process all content. One observation = one fact. Never bundle.

For each observation:
- **entity** — which entity this relates to
- **signal_type** — category (map to config signal_types or create descriptive ones)
- **source_url** — URL where found
- **source_type** — `official | news | blog | analysis | academic | social | legal | product | comparison`
- **date_observed** — from source if available, else today
- **confidence** — `high` (primary source) | `medium` (reputable secondary) | `low` (unverified/conflicting)
- **observation** — FACTUAL ONLY. What happened. No interpretation.
- **possible_implication** — INFERENCE ONLY. What this might mean. 1-2 sentences.

### 6. Build Evidence Ledger YAML
```yaml
meta:
  search_id: "search-YYYY-MM-DD-<topic-slug>"
  topic: "<from config>"
  objective: "<from config>"
  period_start: "<today minus lookback_days>"
  period_end: "<today>"
  collected_at: "<today>"
  total_queries_run: <actual count>
  total_sources_extracted: <actual count>

entries:
  # === ENTITY NAME ===
  - entity: "EntityName"
    signal_type: "api_changes"
    observation: "Factual statement only. No 'suggests', 'indicates', 'means'."
    possible_implication: "Analyst interpretation of what this fact means."
    source_url: "https://..."
    source_type: official
    date_observed: "YYYY-MM-DD"
    confidence: high
    relevance: pending

proof_gaps:
  - description: "What could not be found"
    attempted_queries:
      - "query 1"
      - "query 2"

sources:
  - url: "https://..."
    title: "Page title"
    source_type: official
```

### 7. Quality Rules (Non-Negotiable)

1. **One observation per entry.** Multiple facts = multiple entries.
2. **Observation is factual only.** No "suggests", "indicates", "means", "implies".
3. **possible_implication is where inference lives.** Separate field, separate purpose.
4. **Every entry needs a source_url.** No URL = no entry.
5. **Date everything.** Use source dates, fall back to today.
6. **proof_gaps are mandatory.** Every search has gaps — document them.
7. **Don't pad.** 5 solid entries beats 20 entries with filler.
8. **Confidence = source quality.** Primary/official = high. Established publication = medium. Unverified = low.

### 8. Save and Report
Save ledger to the configured output path.
Report: entry count, entities covered, unique sources, key proof gaps, output path.

---

## Pre-Configuring Directed Searches

For complex architectural research, Keeper can pre-write a YAML search config file before dispatching Scout. Scout reads it and follows it exactly. This ensures the right search angles are covered without Scout improvising.

Config file pattern — save to .pipeline/search-config-<topic>.yaml:
```yaml
topic: "..."
objective: "..."
entities: [...]
signal_types: [...]
searches:
  - query: "specific directed query 1"
  - query: "specific directed query 2"
  # ... up to max_search_queries
period:
  lookback_days: 180
depth: deep
budget:
  max_search_queries: 14
  max_sources_to_extract: 10
output:
  path: ".pipeline/research-<topic>.yaml"
  format: yaml
  include_source_appendix: true
```

Scout task instruction: "Read the search config at <path>. Execute ALL search queries defined in it."
Attach config to ticket before dispatching Scout.

## Integration with Scout

After executing search, Scout references the ledger in Builder Brief:
- **Item 3** (Architecture Patterns): cite upstream patterns found in research
- **Item 9** (Anti-patterns): add anti-patterns discovered from changelogs/known issues
- **Item 10** (Success criteria): include any version-specific verification steps found

---

## Anti-Patterns

- ❌ Bundling multiple facts into one observation entry
- ❌ Including interpretation in the `observation` field
- ❌ Omitting the `proof_gaps` section
- ❌ Using a URL as an entry without actually extracting/reading the page
- ❌ Exceeding budget without noting it in meta
- ❌ Setting confidence=high for non-primary sources
