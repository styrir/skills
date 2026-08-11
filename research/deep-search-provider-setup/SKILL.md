---
name: deep-search-provider-setup
description: "Use when configuring or verifying deep-search-mcp providers, especially Parallel Search credentials, stdlib fallback behavior, and safe secret handling."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [research, deep-search, providers, parallel, credentials]
    related_skills: [deep-search-cli, parallel-cli]
---

# Deep Search Provider Setup

## Overview

Use this subskill when a Deep Search task depends on provider configuration rather than research synthesis itself.

The canonical production path is Parallel Search through the in-repo provider adapter:

```bash
cd /Users/brooks/Code/refs/deep-search
export PARALLEL_API_KEY="[REDACTED]"
export DEEP_SEARCH_WEB_SEARCH_ENDPOINT=provider:parallel
.venv/bin/deep-search-mcp web-search --query "deep search systems" --provider parallel --limit 5
```

## When to Use

- Verifying `--provider parallel` works.
- Diagnosing `PARALLEL_API_KEY` availability.
- Explaining provider boundaries: Parallel provider vs stdlib fallback.
- Preventing credential leakage in command output or docs.

## Procedure

1. Work from `/Users/brooks/Code/refs/deep-search`.
2. Check for `.venv/bin/deep-search-mcp`; if missing, use `PYTHONPATH=src python -m deep_search_mcp.cli`.
3. Check both the live process environment and `${HERMES_HOME:-~/.hermes}/.env` before saying a key is missing.
4. Never print the key. Report only presence, prefix, or length.
5. Smoke-test with a low-limit search:

```bash
.venv/bin/deep-search-mcp web-search \
  --query "deep-search-mcp provider smoke test" \
  --provider parallel \
  --limit 1
```

6. Inspect JSON for provider identity, results, search id, or usage metadata.

## Provider Rules

- `--provider parallel` maps to `DEEP_SEARCH_WEB_SEARCH_ENDPOINT=provider:parallel` for that command.
- If no endpoint/provider is configured, `web_search` falls back to stdlib DuckDuckGo HTML search.
- Parallel `search_queries[0]` is bounded to 200 characters; the full query is preserved as `objective`.
- Parallel `max_results` is clamped to 50.

## Pitfalls

1. Concluding the key is missing because a subprocess did not inherit Hermes secrets.
2. Printing or committing real API keys.
3. Confusing `parallel-cli` vendor workflows with the in-repo `provider:parallel` adapter.
4. Forcing global editable installs into Homebrew-managed Python.
5. Treating a leading macOS stderr line such as `Error: Device not configured (os error 6)` as fatal when the command exits 0 and valid JSON follows; parse from the first `{` and verify `exit_code` plus JSON provider/results before retrying or changing providers.

## Verification Checklist

- [ ] Provider path explicitly reported: `parallel`, configured endpoint, or stdlib fallback.
- [ ] No credential value printed.
- [ ] Smoke test returned JSON.
- [ ] Failure mode preserved exactly if debugging provider errors.
