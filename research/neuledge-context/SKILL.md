---
name: neuledge-context
description: Query local-first versioned documentation via neuledge/context CLI. Use when you need accurate, version-specific API docs for installed packages (Next.js, React, TypeScript). Faster and more accurate than Context7 for supported packages.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [docs, research, nextjs, react, typescript, local-first]
---

# Neuledge Context CLI

Local-first documentation index. Docs are stored as SQLite .db files, queried at sub-10ms.
No cloud, no rate limits, version-specific.

## Installed Packages

- next@16.2.1
- react@latest
- typescript@latest
- python@3.13  (built from cpython/Doc, tag v3.13.2)
- node@22      (built from nodejs/node/doc/api, tag v22.14.0)

Apple frameworks (SwiftUI, AppKit, UIKit) are NOT in the registry — use developer.apple.com directly for those.

## Usage

### Query docs
  npx @neuledge/context query "next@16.2.1" "your topic here"
  npx @neuledge/context query "react@latest" "hooks useEffect dependencies"
  npx @neuledge/context query "typescript@latest" "generic constraints"
  npx @neuledge/context query "python@3.13" "asyncio event loop"
  npx @neuledge/context query "node@22" "fs readFile promises"

Note: must use full package@version name, e.g. "next@16.2.1" not just "next".

### List installed packages
  npx @neuledge/context list

### Browse registry for new packages
  npx @neuledge/context browse <name>

### Install a package from registry
  npx @neuledge/context install npm/<name>

### Build from a git repo (for packages not in registry)
  npx @neuledge/context add https://github.com/org/repo

## When to use this vs other tools

- next/react/typescript questions → use this (version-accurate, local)
- Apple framework questions (SwiftUI, AppKit, UIKit) → use developer.apple.com
- Packages not in registry → use web_search or web_extract as fallback
- Context7 docs lookups → use the Context7 CLI directly (`npx ctx7@latest ...`), not `skill_view("context7-cli")` — there is no separate Hermes skill wrapper installed by default

## Pitfalls

- Query requires exact package@version string — "next" alone returns "Package not found"
- Free plan: 3 indexing jobs/month — don't waste slots on test crawls
- Do NOT add as MCP server — use this skill instead to control when it's invoked
- Context7 CLI vs Hermes skill wrappers are separate things. If `skill_view("context7-cli")` fails, that does NOT mean ctx7 is broken. Check `npx ctx7@latest --help` first. The local wrapper skill may simply be missing while the CLI still works.
- If the local Hermes wrappers are missing but upstream ships them, vendor them from `https://github.com/upstash/context7/tree/master/skills` into `~/.hermes/skills/research/` rather than assuming the tool is unavailable. Upstream wrappers: `context7-cli`, `find-docs`.
