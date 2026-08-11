---
name: deep-search-report-delivery
description: "Use when validating and publishing deep-search-mcp reports through verify-claims, verify-citations, validate-report, and render-report-bundle --strict."
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

Use this subskill when a candidate research report must be validated and published. `render-report-bundle --strict` is the publishing gate; do not manually rename failed candidates into `report.md`.

## Commands

```bash
cd /Users/brooks/Code/refs/deep-search
.venv/bin/deep-search-mcp verify-claims --dir /tmp/deep-search-run --strict
.venv/bin/deep-search-mcp verify-citations --report /tmp/deep-search-run/report.candidate.md --strict --no-network
.venv/bin/deep-search-mcp validate-report --report /tmp/deep-search-run/report.candidate.md
.venv/bin/deep-search-mcp render-report-bundle \
  --dir /tmp/deep-search-run \
  --draft-report /tmp/deep-search-run/report.candidate.md \
  --strict
```

## Workflow

1. Draft to `report.candidate.md`.
2. Put `[claim:<claim_id>]` on the same line as every factual claim in the body.
3. Keep non-factual framing, transitions, and section headings separate from factual claim lines where possible; this reduces false `unsupported_segments` failures and makes audit easier.
4. Run `verify-claims --strict` against the run directory.
5. Run `verify-citations --strict --no-network` against the candidate.
6. Run `validate-report`.
7. Run `render-report-bundle --strict`.
8. Publish only if `render-report-bundle` writes `report.md`.

## Gate interpretation

A passed citation check only proves citation syntax/resolution. It is not enough by itself. Treat the bundle gate as the release gate because it combines report structure, claim support, citation checks, claim-marker coverage, unsupported segment detection, unresolved contradictions, unresolved red-team challenges, and temporal blockers.

If `render-report-bundle --strict` fails, surface its blocking fields directly:

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
5. Using fake demo bibliography titles such as `Example` in strict citation tests; `verify-citations --strict --no-network` can flag them with `E_HALLUCINATION_REGEX`. Use a real URL/title pair for strict smoke tests.

## Verification Checklist

- [ ] `verify-claims --strict` passed.
- [ ] `verify-citations --strict --no-network` passed.
- [ ] `validate-report` passed.
- [ ] `render-report-bundle --strict` passed and wrote `report.md`.
- [ ] Failed candidates remained candidates.
