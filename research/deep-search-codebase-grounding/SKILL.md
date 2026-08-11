---
name: deep-search-codebase-grounding
description: "Use when using deep-search-mcp to index or search local codebases and return snippet-bearing code evidence for research, debugging, or handoff."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [research, deep-search, code-search, indexing, snippets]
    related_skills: [deep-search-cli, codebase-orientation]
---

# Deep Search Codebase Grounding

## Overview

Use this subskill when the research question depends on local code behavior. Prefer raw `search-code` results with path, line number, line text, snippets, and preview text over mental reconstruction.

## Commands

```bash
cd /Users/brooks/Code/refs/deep-search
.venv/bin/deep-search-mcp index-codebase --root .
.venv/bin/deep-search-mcp search-code --root . --query "render_report_bundle validation gates" --limit 10
.venv/bin/deep-search-mcp get-indexing-status --root .
.venv/bin/deep-search-mcp clear-index --root .
```

## Workflow

1. Identify the repo root and run `index-codebase --root <repo>`.
2. Run targeted `search-code` queries for symbols, concepts, or error strings.
3. Preserve path, line, snippet, and preview in the handoff.
4. If modifying `/Users/brooks/Code/refs/deep-search`, obey its AGENTS.md GitNexus rules before edits.

## GitNexus Boundary for deep-search repo

When editing symbols in `/Users/brooks/Code/refs/deep-search`, run impact analysis before editing and detect changes before commit, per AGENTS.md. Deep Search code retrieval helps find context; it does not replace repo-specific safety rules.

## References Corpus Questions

When the user asks about the Deep Search "references corpus" or competitive tools from prior audits, first search/read `/Users/brooks/Code/refs/deep-search/deep-search-mcp-research-artifact.md`. That artifact is the local corpus index and may contain repo-relative paths for audited references even when the individual competitor repo directories are not currently present in the checkout. Use `deep-search-mcp search-code` for broad discovery, then `read_file` on the artifact for exact supporting passages. Disclose the boundary if conclusions are based on the composite artifact rather than direct current source files.

## Pitfalls

1. Using shell grep instead of snippet-bearing `search-code` during a Deep Search evaluation.
2. Reporting code behavior without path/line evidence.
3. Editing symbols before repo-specific impact analysis.
4. Confusing indexed stale results with current filesystem state; rerun indexing if needed.
5. Treating corpus paths inside `deep-search-mcp-research-artifact.md` as currently checked-out files without verifying; they can be artifact-recorded paths from prior audits.

## Verification Checklist

- [ ] Index status checked or index refreshed.
- [ ] Search results include path and snippet evidence.
- [ ] For references-corpus questions, the composite artifact was searched/read and the artifact-vs-live-source boundary was disclosed.
- [ ] Repo-specific safety rules followed before edits.
