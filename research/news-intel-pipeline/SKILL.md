---
name: news-intel-pipeline
description: "Automated daily intelligence gathering pipeline for AI practitioners. RSS/API ingest, LLM scoring, Obsidian delivery. Project at /Users/brooks/Code/news."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [intelligence, news, rss, lancedb, obsidian, gemini, openrouter, daily-brief]
---

# News Intel Pipeline

Automated daily intelligence gathering system at `/Users/brooks/Code/news`.
Runs at 6AM via launchd. Delivers brief to Obsidian vault and iMessage for score >= 90.

## Three-Document Model

Each day produces two documents in Obsidian Daily folder, Sundays produce a third:

| Document | Filename | Purpose |
|----------|----------|---------|
| Intelligence Brief | YYYY-MM-DD.md | What happened in AI today |
| Signal Queue | YYYY-MM-DD-signal-queue.md | What to do about it (actionable proposals) |
| Weekly Digest | Intelligence/Weekly/YYYY-WNN.md | Strategic patterns across the week (Sundays) |

## Architecture

```
RSS/API → Ingest → Extract → Dedupe → Score → Summarize → Store → Deliver
                                                    ↓
                                              Lens Pass (score >= 80)
                                                    ↓
                                           Route (Linear / beads)
                                                    ↓
                                        Signal Queue document
```

- Sources: HN Algolia, LangChain, HuggingFace, OpenAI, arXiv cs.CL/AI, GitHub releases (vLLM, Ollama, Letta, Zep, NetworkX), Bellingcat, Neo4j, and more
- Scoring + Summarization + Lens: `google/gemini-3-flash-preview` via OpenRouter (thinking disabled, ~2.5s/call)
- Lens pass: `src/lens.py` — Gemini 3 Flash asks what each 80+ item means for Rúnir and Varda specifically
- Action routing: `src/route.py` — TICKET_CANDIDATEs → Linear (MIM team) or beads (Varda)
- Storage: SQLite (metadata/operational) + LanceDB (vectors, hot 90 days)
- Delivery: Obsidian at `~/Documents/Obsidian Vault PARA/PARA/Resources/Intelligence/Daily/`
- Scheduling: launchd plist `com.brooks.news-intel` (6AM daily), `com.brooks.news-intel-weekly` (Sunday 7AM)

## Key Files

- `run.py` — main orchestrator with degraded mode
- `run.sh` — venv + .env wrapper
- `install.sh` — loads launchd plist
- `src/score.py` — keyword pre-filter + Gemini LLM scoring
- `src/summarize.py` — Gemini summarization (structured JSON)
- `config/sources.yaml` — all source definitions
- `config/keywords.yaml` — relevance taxonomy per domain/product
- `.env` — OPENROUTER_API_KEY, OPENROUTER_BASE_URL, SCORING_MODEL

## Running Manually

```bash
cd /Users/brooks/Code/news
source .venv/bin/activate
set -a && source .env && set +a
python run.py
```

## Model Switching — Learned the Hard Way

MiniMax-M2.7-highspeed is a reasoning model. Even with max_tokens=8192 it sometimes
returns only <think>...</think> with no JSON after — especially on short excerpts or
non-English content. Switching to Gemini 3 Flash via OpenRouter eliminated this entirely.

If you ever need to switch LLM models in this pipeline:
- Score + summarize both use SCORING_MODEL env var (default: google/gemini-3-flash-preview)
- Both use OPENROUTER_API_KEY + OPENROUTER_BASE_URL
- Set extra_body={"thinking": {"type": "disabled"}} to skip Gemini reasoning overhead
- max_tokens=256 for scoring, 512 for summaries — no reasoning means no token bloat
- Gemini sometimes wraps JSON in ```json fences — strip with lstrip/rstrip before parsing
- MiniMax is kept in .env as a reference but is no longer used

## Pitfalls Learned

- LanceDB transaction files are massive in git — gitignore `data/intelligence.lance/`, `data/briefs/`, `logs/`
- 48h cutoff on RSS feeds is essential — feeds like HuggingFace return 700+ items otherwise
- arXiv RSS republishes the same ~430 papers every day — use max_age_hours: 24 in sources.yaml or dedupe will discard them all anyway but it wastes scoring budget
- per-source max_age_hours config is the right pattern — add it to sources.yaml, default 48h, override per-source
- Gemini 3 Flash requires `extra_body={"thinking": {"type": "disabled"}}` via OpenRouter to skip reasoning for classification tasks. Without this it may still reason and latency jumps.
- MiniMax-M2.7-highspeed is a reasoning model — we tried it first. Problem: `<think>` block consumes tokens before JSON answer. With max_tokens=1024 the think block fills budget and JSON never appears. Bumping to 8192 helps but calls take 10-12s each at 412 items = 70 min total. Switched to Gemini 3 Flash (~2.5s/call, no reasoning overhead). MiniMax is wrong tool for high-volume classification.
- Variable name collision: function named `llm_score` and local variable named `llm_score` in same scope — Python UnboundLocalError. Rename local to `llm_score_val`.
- OpenAI.com blocks scraping (403). HN Algolia returns 0 hits if rate-limited or timestamp filter is too tight.
- MemGPT repo moved from `cpacker/MemGPT` to `letta-ai/letta` — GitHub returns 301 redirect which httpx does not follow by default
- Dedupe table persists across runs — correct behavior on daily runs, but clear it for testing: `DELETE FROM dedupe_seen; DELETE FROM raw_items; DELETE FROM scored_items; DELETE FROM summaries`
- Brief summary wording matters: "Items processed: 468" with only 4 new items looks broken. Use "Sources checked: N" and "New today (after dedupe): N" so the numbers tell the right story.
- `run_stats` must include `items_deduped` from run.py for the brief to display it — verify the key name matches between run.py stats dict and brief.py lookup
- `claude --model claude-opus-4-7 --permission-mode bypassPermissions --print '...'` with foreground timeout=600 is the current correct invocation. background+pty can hang on permission/trust dialogs. --print mode with stdin pipe works fine.
- `--flag` text in `-p 'prompt'` causes exit 1 — Claude CLI intercepts `--labels`, `--priority`, `--team` etc. as its own flags. Write prompt to `/tmp/task.txt` first: `printf '%s' "$PROMPT" > /tmp/task.txt && claude ... -p "$(cat /tmp/task.txt)"`.
- `raw_items` table must store `title TEXT` (not just title_hash) so Signal Queue and retroactive queries can show human-readable titles without depending on LanceDB. Add to schema and migrate via migrate_run_log().
- LanceDB does not auto-migrate columns — adding fields to LANCE_SCHEMA only works on new tables. For existing tables: drop and recreate (`db.drop_table("items")` then `init_lancedb()`). This clears vector data, so do it intentionally.
- Signal Queue requires a spec-review-pipeline pass before build — the first implementation missed: proposal-status two-join SQL (single JOIN produces duplicate rows when both linear_runir and beads_varda proposals exist for same URL), shell escaping for linearis/bd commands (shlex.quote() required — apostrophes in titles break raw f-string interpolation), partial-actioned rendering (partially-actioned items stay in main queue showing only pending commands, not in Already Actioned section), sort order determinism (must be final_score DESC, confidence DESC, url ASC — url is the stable tiebreaker ensuring live and retroactive runs produce identical order). This cost 4 rounds of Opus/Codex review to fix after the fact. Always spec first for medium/large features.
- Signal Queue retroactive generation: `python -m src.generate_signal_queue [--date YYYY-MM-DD] [--stdout]` reconstructs the document from SQLite alone (no LanceDB, no live pipeline). Requires `title TEXT` column in raw_items — stored by log_raw_item() on each run. The two-join SQL pattern: `LEFT JOIN action_proposals ap_runir ON ap_runir.url_hash = ri.url_hash AND ap_runir.target = 'linear_runir'` + separate join for beads_varda — gives one row per item with independent per-target status columns. This pattern is the correct way to check proposal status anywhere in the codebase.
- `.gitignore` escaping: using `>>` to append to .gitignore in bash will write literal `\n` if you use `echo "a\nb"` — use write_file tool instead to write proper newlines

## Source Health (as of 2026-03-25)

Working: HN Algolia, LangChain, HuggingFace, OpenAI, vLLM, Ollama, Letta, Zep, NetworkX, arXiv, Bellingcat, Neo4j
Broken/empty: Pinecone RSS (returns HTML), LlamaIndex (malformed XML), Obsidian Roundup (malformed XML), TigerGraph (malformed XML), Modal, Replicate, Together AI

## Cost

~$0.15-0.30/day at normal volume (20-50 items/day after dedupe). First run on full backlog ~$2.
