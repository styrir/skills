---
name: deep-search-cli
description: "Use when operating deep-search-mcp as a CLI-first research substrate. Router skill: load only the relevant Deep Search subskill for provider setup, P1 retrieval, code grounding, P0 ledgers, P2 gates, report delivery, or MCP boundary."
version: 1.2.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [research, deep-search, cli, retrieval, citations, evidence, orchestration, parallel]
    related_skills:
      - deep-search-provider-setup
      - deep-search-p1-retrieval
      - deep-search-codebase-grounding
      - deep-search-p0-ledgers
      - deep-search-p2-orchestration
      - deep-search-report-delivery
      - deep-search-mcp-boundary
      - research-and-recon
      - parallel-cli
      - structured-search-agent
---

# Deep Search CLI

## Purpose

This is the umbrella/router skill for `deep-search-mcp`. Keep this file small so `/deep-search-cli ...` does not inject the full operating manual.

Canonical path:

```text
Hermes skill -> deep-search-mcp CLI -> core Python functions -> provider adapters
```

MCP is only an optional compatibility wrapper. For Hermes, default to CLI calls because command transcripts and JSON outputs are easier to audit.

## Progressive Disclosure

Use this skill to choose the next skill/file, not to hold every command.

Load the relevant subskill with `skill_view` when the task matches:

| Task | Load |
| --- | --- |
| Parallel key, provider failures, stdlib fallback | `deep-search-provider-setup` |
| Web search, docs fetch, citations, source discovery | `deep-search-p1-retrieval` |
| Local code indexing/search with snippets | `deep-search-codebase-grounding` |
| Run manifests, source/evidence/claim ledgers | `deep-search-p0-ledgers` |
| Planning, routing, scoring, contradiction/red-team/temporal checks | `deep-search-p2-orchestration` |
| Claim extraction, evidence auto-linking, entailment checks, counter-evidence retrieval, provenance soundness | `deep-search-p0-ledgers`, `deep-search-p2-orchestration`, `deep-search-report-delivery`; see `references/claim-quality-pipeline.md` |
| Claim/citation/report validation and publication gate | `deep-search-report-delivery` |
| CLI-vs-MCP interface choice or server wrapper setup | `deep-search-mcp-boundary` |

Long command reference, preserved from the original monolithic skill: `references/command-reference.md`.

Gated/auditable report workflow: `references/gated-report-mode.md`.

Claim-quality pipeline commands and acceptance tests: `references/claim-quality-pipeline.md`.

## Default CLI Pattern

```bash
cd /Users/brooks/Code/refs/deep-search
.venv/bin/deep-search-mcp plan-research-lanes --query "<question>"
.venv/bin/deep-search-mcp web-search --query "<query>" --provider parallel --limit 5
.venv/bin/deep-search-mcp web-fetch --url <url>
```

If the venv executable is unavailable:

```bash
PYTHONPATH=src python -m deep_search_mcp.cli --help
```

## Skill-Efficacy Test Rules

When the user invokes `/deep-search-cli` to test this skill:

1. Do not reflexively load broad sibling skills such as `arxiv`, `research-and-recon`, or `parallel-cli`.
2. Use `deep-search-mcp` CLI first.
3. Prefer visible `terminal` calls for the first few commands so the user can audit the flow.
4. Use `execute_code` only to batch many CLI calls or reduce large JSON outputs; avoid unused imports and print a compact execution ledger.
5. If any non-DeepSearch tool contributes sources or claims, disclose that boundary in the final answer.

For a clean slash-command/router regression test, run `/reload-skills`, then `/reset`, then invoke `/deep-search-cli <task>` in a fresh session. If the active Hermes default model is not the one being tested, launch the session with explicit `--provider` and `-m` flags so the banner/session metadata match the test target. The expected trace is: router skill only at invocation, then the narrow task subskill (usually `deep-search-p1-retrieval` for web research), with provider/setup subskills loaded only after an actual provider/setup failure. See `references/slash-command-efficacy-test.md`.

## Output Quality Bar

For `/deep-search-cli` smoke tests, the answer should be rich enough to prove that routing produced a substantive source-led synthesis, not just a command transcript. A good quick briefing should include: domain-appropriate framing, multiple source families, fetched-source-backed numerical claims where relevant, an explicit source ledger, and a short boundary note naming the DeepSearch/provider path.

Do not confuse that with a gated DeepSearch report. If the user asks whether the output is “rich enough,” asks to “fix” synthesis trust, or uses terms like gated, auditable, claim-level, provenance, validation, verification, high-confidence, publication, or artifact, switch to gated report mode rather than only answering in prose.

Gated report mode requires loading `deep-search-p0-ledgers`, `deep-search-p2-orchestration`, and `deep-search-report-delivery`; creating a real run directory; recording source/evidence/claim ledgers; drafting `report.candidate.md` with `[claim:<claim_id>]` markers for every factual claim; running contradiction/red-team/temporal checks as appropriate; and publishing only through `render-report-bundle --strict`. When the newer claim-quality pipeline is available, prefer `extract-claims`, `link-claims-to-evidence`, `entailment-check`, `retrieve-counter-evidence`, and `provenance-soundness` before final bundle rendering; see `references/claim-quality-pipeline.md`. See `references/gated-report-mode.md` for the full workflow and acceptance bar.

Mode distinction:

- Slash-command/router smoke test: source-led synthesis plus visible DeepSearch CLI trace is enough.
- Expert quick briefing: breadth, source diversity, and citations are enough if claims are not mission-critical.
- Gated/reusable report: must produce claim/evidence/source ledgers, contradiction checks, citation validation, and strict bundle validation.

Session-specific example and rubric: `references/slash-command-efficacy-test.md`.

## Source Boundary

ArXiv URLs can appear in two ways:

- Deep Search path: `deep-search-mcp web-search --provider parallel` returns arXiv URLs, then `web-fetch` fetches concrete pages.
- External path: direct arXiv Atom/API calls from another skill or custom code.

During `/deep-search-cli` tests, use the Deep Search path unless explicitly asked otherwise.

## Verification Checklist

- [ ] `deep-search-mcp` CLI was the primary path.
- [ ] Relevant subskill was loaded only when needed.
- [ ] Provider path was explicit: `parallel`, configured endpoint, or stdlib fallback.
- [ ] Important claims use fetched content, not search snippets alone.
- [ ] No real credentials were printed or written.
- [ ] Non-DeepSearch sources/tools were disclosed.

## Absorbed P2 Orchestration (planning and quality gates)
Use for lane planning, routing, node scoring, contradiction/red-team/temporal checks.

**Key commands (condensed from absorbed subskill):**
- `deep-search-mcp plan-research-lanes --query "..." `
- `deep-search-mcp route-question-type --question "..." --mode deep`
- `deep-search-mcp score-node --json '{...}'`
- `deep-search-mcp detect-contradictions --dir <dir> --json '[...]'`
- `deep-search-mcp red-team-node --dir <dir> --claim-id '...' `
- `deep-search-mcp temporal-diff --dir <dir> --json '[...]'`

**Workflow:** Start with plan-research-lanes for nontrivial; score nodes; run contradiction/red-team/temporal for high-confidence; preserve gate JSON in audit handoffs.

**Pitfalls:** Treating P2 planning as source evidence; skipping checks for contested claims; hiding gate failures.

The full original `deep-search-p2-orchestration` skill has been archived under this umbrella. See .archive/deep-search-p2-orchestration for the complete version if needed.

## Default CLI Pattern
