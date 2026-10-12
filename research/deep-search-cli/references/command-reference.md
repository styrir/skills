# Deep Search CLI Command Reference

This file holds the longer command reference so `SKILL.md` can stay small when loaded by `/deep-search-cli`.

## Invocation

Known repo:

```bash
cd /Users/brooks/Code/refs/deep-search
```

Preferred local executable if the repo venv exists:

```bash
.venv/bin/deep-search-mcp --help
```

Portable fallback:

```bash
PYTHONPATH=src python -m deep_search_mcp.cli --help
```

## Environment

Parallel provider:

```bash
export PARALLEL_API_KEY="[REDACTED]"
export DEEP_SEARCH_WEB_SEARCH_ENDPOINT=provider:parallel
```

Do not print real keys. If the terminal environment lacks the key, check `${HERMES_HOME:-~/.hermes}/.env` before declaring it missing.

## P1 Retrieval

```bash
.venv/bin/deep-search-mcp web-search --json '{"query":"dark matter direct detection 2025","provider":"parallel","limit":5}'
.venv/bin/deep-search-mcp web-fetch --json '{"url":"https://arxiv.org/abs/2502.18005"}'
.venv/bin/deep-search-mcp query-docs --json '{"target":"python json documentation","query":"JSONEncoder"}'
.venv/bin/deep-search-mcp follow-references --json '{"content":"See https://example.com","fetch":true,"limit":10}'
```

## Code Retrieval

```bash
.venv/bin/deep-search-mcp index-codebase --json '{"root":"."}'
.venv/bin/deep-search-mcp search-code --json '{"root":".","query":"render_report_bundle validation gates","limit":10}'
.venv/bin/deep-search-mcp get-indexing-status --json '{"root":"."}'
.venv/bin/deep-search-mcp clear-index --json '{"root":"."}'
```

## P0 Ledgers

```bash
.venv/bin/deep-search-mcp init-run --json '{"out_dir":"/tmp/deep-search-run","query":"What changed?","mode":"standard"}'
.venv/bin/deep-search-mcp register-source --json '{"directory":"/tmp/deep-search-run","raw_url":"https://example.com","title":"Example","source_type":"web","source_quality":"B"}'
.venv/bin/deep-search-mcp record-evidence --json '{"directory":"/tmp/deep-search-run","source_id":"<source_id>","quote":"Example quote.","locator":"p1"}'
.venv/bin/deep-search-mcp record-claim --json '{"directory":"/tmp/deep-search-run","section_id":"summary","claim_type":"factual","text":"Example quote.","cited_source_ids":["<source_id>"],"evidence_ids":["<evidence_id>"]}'
```

## P2 Gates

```bash
.venv/bin/deep-search-mcp plan-research-lanes --json '{"query":"Which components validate report delivery?"}'
.venv/bin/deep-search-mcp route-question-type --json '{"question":"Find papers about retrieval quality","mode":"deep"}'
.venv/bin/deep-search-mcp score-node --json '{"node":{"node_id":"candidate-1","relevance":5,"authority":4,"rigor":4,"independence":4,"coherence":5}}'
.venv/bin/deep-search-mcp temporal-diff --json '{"observations":[{"claim":"API is available","status":"confirmed"}]}'
```

## Report Gate

```bash
.venv/bin/deep-search-mcp verify-claims --json '{"directory":"/tmp/deep-search-run","strict":true}'
.venv/bin/deep-search-mcp verify-citations --json '{"report":"/tmp/deep-search-run/report.candidate.md","strict":true,"network":false}'
.venv/bin/deep-search-mcp validate-report --json '{"report":"/tmp/deep-search-run/report.candidate.md"}'
.venv/bin/deep-search-mcp render-report-bundle --json '{"directory":"/tmp/deep-search-run","draft_report":"/tmp/deep-search-run/report.candidate.md","strict":true}'
```

`render-report-bundle` writes `report.md` only after gates pass. Failed drafts remain as `report.candidate.md`.
