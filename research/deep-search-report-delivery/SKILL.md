---
name: deep-search-report-delivery
description: "Use when validating and publishing deep-search-mcp reports through verify-claims, verify-citations, validate-report, and strict render-report-bundle."
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [research, deep-search, reports, citations, validation, publishing]
    related_skills: [deep-search-cli, deep-search-p0-ledgers, deep-search-p2-orchestration]
---

# Deep Search Report Delivery

## Overview

Use this subskill when a candidate research report must be validated and published. `render-report-bundle` with `"strict":true` is the publishing gate; do not manually rename failed candidates into `report.md`.

## Commands

```bash
cd /Users/brooks/Code/refs/deep-search
.venv/bin/deep-search-mcp verify-claims --json '{"directory":"/tmp/deep-search-run","strict":true}'
.venv/bin/deep-search-mcp verify-citations --json '{"report":"/tmp/deep-search-run/report.candidate.md","strict":true,"network":false}'
.venv/bin/deep-search-mcp validate-report --json '{"report":"/tmp/deep-search-run/report.candidate.md"}'
.venv/bin/deep-search-mcp render-report-bundle --json '{"directory":"/tmp/deep-search-run","draft_report":"/tmp/deep-search-run/report.candidate.md","strict":true}'
```

## Workflow

1. Draft to `report.candidate.md`.
2. Put `[claim:<claim_id>]` on the same line as every factual claim in the body.
3. Keep non-factual framing, transitions, and section headings separate from factual claim lines where possible; this reduces false `unsupported_segments` failures and makes audit easier.
4. Run `verify-claims` with `"strict":true` against the run directory.
5. Run `verify-citations` with `"strict":true,"network":false` against the candidate.
6. Run `validate-report`.
7. Run `render-report-bundle` with `"strict":true`.
8. Publish only if `render-report-bundle` writes `report.md`.

## Gate interpretation

A passed citation check only proves citation syntax/resolution. It is not enough by itself. Treat the bundle gate as the release gate because it combines report structure, claim support, citation checks, claim-marker coverage, unsupported segment detection, unresolved contradictions, unresolved red-team challenges, and temporal blockers.

If `render-report-bundle` with `"strict":true` fails, surface its blocking fields directly:

- `missing_claim_ids`
- `unknown_claim_markers`
- `unmarked_claim_ids`
- `unsupported_segments`
- `unresolved_contradiction_ids`
- `unresolved_challenge_relation_ids`
- `temporal_blocker_claim_ids`

## Raw Output Rule

When the user asks for artifacts or audit evidence, report raw gate output exactly as produced. Do not add markdown wrappers, cleaned summaries, or presentation formatting to raw artifacts.

## Pitfalls

1. Publishing `report.candidate.md` manually after validation failure.
2. Running citation validation with network access when the intended gate is offline/no-network.
3. Summarizing away blocking gate details.
4. Claiming publication succeeded without verifying `report.md` exists.
5. Using fake demo bibliography titles such as `Example` in strict citation tests; `verify-citations` with `"strict":true,"network":false` can flag them with `E_HALLUCINATION_REGEX`. Use a real URL/title pair for strict smoke tests.

## Verification Checklist

- [ ] `verify-claims` with `"strict":true` passed.
- [ ] `verify-citations` with `"strict":true,"network":false` passed.
- [ ] `validate-report` passed.
- [ ] `render-report-bundle` with `"strict":true` passed and wrote `report.md`.
- [ ] Failed candidates remained candidates.
