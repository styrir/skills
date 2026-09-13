# Report contract

Two artifacts per run, written under `OUT`:

| file | audience |
|---|---|
| `receipt.json` | machines, trend store, later diffs |
| `report.html` | humans |

Phoenix's UI is a live React/GraphQL SPA with no static HTML export in source. Do not copy it. Pattern to copy: `~/Code/agent-ops/bin/workgraph-dossier` (inline CSS, no CDN, no JS required, stable ids, malformed lines counted). Chart ideas to reimplement: time bars, pass-rate lines, skill ranking, baseline vs candidate counts. Render charts as inline SVG.

eval-dashboards `eval-report/v1` (MIT, v0.x) is a useful *row shape* to study. Pin any borrowed field names in `receipt.json` rather than depending on their CLI.

## receipt.json

```json
{
  "schema": "styrir-session-eval/v0",
  "generated_at": "ISO-8601",
  "since": "ISO-8601",
  "harnesses_requested": ["claude", "codex", "pi", "omp", "grok"],
  "harnesses_found": ["claude", "grok"],
  "runs": [],
  "skills": [],
  "checks": [],
  "hard_pass": true,
  "parse_errors": 0,
  "proof_gaps": []
}
```

- `runs[]` are the normalized records from `SKILL.md`.
- `skills[]` include `name`, `path`, `digest`, `activations`, `hard_fail_count`, `last_seen`.
- `checks[]` are rolled up by `id` with counts of pass/fail/n_a/unknown.
- Sort keys for determinism when emitting test fixtures. Do not read the wall clock inside a golden-file test; production reports may stamp `generated_at`.

## report.html

Required sections and ids:

| id | content |
|---|---|
| `verdict` | hard_pass, run count, parse_errors |
| `coverage` | harnesses found vs requested; gaps |
| `trends` | SVG: sessions/day, hard_fail/day, tokens where known |
| `skills` | table of skill digest, activations, fail counts; opaque third-party flagged |
| `sessions` | table of run.id, harness, model, tokens, checks failed; link to `source_path` not transcript |
| `failures` | grouped by check id with evidence pointers |
| `footer` | generator name, catalog version, redaction notice |

Rules:

- One file. Inline CSS. No network. No session prompt text.
- Stable ids for annotation (`session-<id>`, `check-<id>`, `skill-<digest8>`).
- Malformed JSONL: show count, do not silently drop.
- WorkGraph dossiers stay at `.pipeline/<slug>/dossier.html`; this report may *link* them.

## Trend store

Keep prior `receipt.json` files as immutable snapshots under `OUT/history/`. Charts read the snapshot list. Do not mutate old receipts. Baseline policy: last receipt with `hard_pass=true` is champion unless the user names another.
