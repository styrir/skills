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
.venv/bin/deep-search-mcp web-search --query "dark matter direct detection 2025" --provider parallel --limit 5
.venv/bin/deep-search-mcp web-fetch --url https://arxiv.org/abs/2502.18005
.venv/bin/deep-search-mcp query-docs --target "python json documentation" --query "JSONEncoder"
.venv/bin/deep-search-mcp follow-references --content "See https://example.com" --fetch --limit 10
```

## Code Retrieval

```bash
.venv/bin/deep-search-mcp index-codebase --root .
.venv/bin/deep-search-mcp search-code --root . --query "render_report_bundle validation gates" --limit 10
.venv/bin/deep-search-mcp get-indexing-status --root .
.venv/bin/deep-search-mcp clear-index --root .
```

## P0 Ledgers

```bash
.venv/bin/deep-search-mcp init-run --out-dir /tmp/deep-search-run --query "What changed?" --mode standard
.venv/bin/deep-search-mcp register-source --dir /tmp/deep-search-run --json '{"raw_url":"https://example.com","title":"Example","source_type":"web","source_quality":"B"}'
.venv/bin/deep-search-mcp record-evidence --dir /tmp/deep-search-run --json '{"source_id":"<source_id>","quote":"Example quote.","locator":"p1"}'
.venv/bin/deep-search-mcp record-claim --dir /tmp/deep-search-run --json '{"section_id":"summary","claim_type":"factual","text":"Example quote.","cited_source_ids":["<source_id>"],"evidence_ids":["<evidence_id>"]}'
```

## P2 Gates

```bash
.venv/bin/deep-search-mcp plan-research-lanes --query "Which components validate report delivery?"
.venv/bin/deep-search-mcp route-question-type --question "Find papers about retrieval quality" --mode deep
.venv/bin/deep-search-mcp score-node --json '{"node_id":"candidate-1","relevance":5,"authority":4,"rigor":4,"independence":4,"coherence":5}'
.venv/bin/deep-search-mcp temporal-diff --json '[{"claim":"API is available","status":"confirmed"}]'
```

## Report Gate

```bash
.venv/bin/deep-search-mcp verify-claims --dir /tmp/deep-search-run --strict
.venv/bin/deep-search-mcp verify-citations --report /tmp/deep-search-run/report.candidate.md --strict --no-network
.venv/bin/deep-search-mcp validate-report --report /tmp/deep-search-run/report.candidate.md
.venv/bin/deep-search-mcp render-report-bundle --dir /tmp/deep-search-run --draft-report /tmp/deep-search-run/report.candidate.md --strict
```

`render-report-bundle` writes `report.md` only after gates pass. Failed drafts remain as `report.candidate.md`.
