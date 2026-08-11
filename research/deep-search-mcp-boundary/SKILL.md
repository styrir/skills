---
name: deep-search-mcp-boundary
description: "Use when deciding whether to operate deep-search-mcp through the CLI or its optional MCP server wrapper, especially for Hermes vs MCP-native clients."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [research, deep-search, mcp, cli, wrappers]
    related_skills: [deep-search-cli, native-mcp, mcporter]
---

# Deep Search MCP Boundary

## Overview

Use this subskill when the question is about interface choice. For Hermes workflows, the CLI is canonical. The MCP server is a compatibility wrapper for clients that cannot call shell commands or explicitly need MCP tools.

## CLI Default

```bash
cd /Users/brooks/Code/refs/deep-search
.venv/bin/deep-search-mcp --help
```

Why CLI first:

- explicit commands in the transcript
- raw JSON output is easy to audit
- no server lifecycle friction
- no MCP tool-schema/context bloat
- simpler provider/environment debugging

## MCP Wrapper

```bash
cd /Users/brooks/Code/refs/deep-search
export PARALLEL_API_KEY="[REDACTED]"
export DEEP_SEARCH_WEB_SEARCH_ENDPOINT=provider:parallel
PYTHONPATH=src python -m deep_search_mcp.mcp_server
```

The MCP server exposes the same P0/P1/P2 functions and inherits provider behavior from the environment.

## When to Use MCP

- A client is MCP-native and cannot call shell commands.
- The user explicitly asks for an MCP integration or server configuration.
- You are testing parity between MCP tools and CLI commands.

## Pitfalls

1. Treating MCP as primary in Hermes; use CLI unless asked otherwise.
2. Debugging provider failures through MCP first; test CLI first to isolate environment issues.
3. Letting MCP tool schemas consume context during a raw-output audit.

## Verification Checklist

- [ ] Interface choice stated: CLI or MCP.
- [ ] CLI parity considered before MCP-specific debugging.
- [ ] Provider environment set before server startup.
