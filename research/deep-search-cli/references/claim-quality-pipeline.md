# Claim-quality pipeline (session reference)

Use this when the task moves beyond source discovery into auditable claim validation, counter-evidence, and report publication gates.

## Commands added/tested

```bash
# Extract candidate factual claims from prose without writing ledgers
.venv/bin/deep-search-mcp extract-claims \
  --text 'The sample contains 12 rows and it includes 3 columns.' \
  --section-id methods

# Extract and append claims to claims.jsonl, preserving extraction_metadata
.venv/bin/deep-search-mcp extract-claims \
  --file /tmp/run/report.candidate.md \
  --section-id findings \
  --dir /tmp/run \
  --write

# Link each claim to best matching evidence; --write updates evidence_ids/cited_source_ids idempotently
.venv/bin/deep-search-mcp link-claims-to-evidence \
  --dir /tmp/run \
  --write \
  --min-score 0.35

# Deterministic NLI-style proxy
.venv/bin/deep-search-mcp entailment-check \
  --claim 'Alpha increased in 2024' \
  --evidence 'Alpha decreased in 2024.'

# Active counter-evidence retrieval; dry-run must not mutate ledgers
.venv/bin/deep-search-mcp retrieve-counter-evidence \
  --dir /tmp/run \
  --all \
  --limit 3 \
  --provider parallel \
  --dry-run

# Provenance scoring across coverage/support/entailment/citation/source-quality/independence/challenge penalty
.venv/bin/deep-search-mcp provenance-soundness --dir /tmp/run
```

## Acceptance bar

- Extracted claims should include `extraction_metadata` (`bundle_id`, `bundle_index`, `source_span`, `detectors`) when written.
- Linking with `--write` should be idempotent: no duplicate `evidence_ids` or `cited_source_ids` after repeated runs.
- `retrieve-counter-evidence --dry-run` should report found contradictions without changing `sources.jsonl`, `evidence.jsonl`, or `challenge_relations.jsonl`.
- Recorded counter-evidence must flow through `red_team_node`, creating unresolved challenge relations.
- `render-report-bundle` should still block if unresolved challenge relations, contradictions, temporal blockers, unsupported segments, unmarked factual claims, or strict citation/claim failures remain.

## Verification recipe

```bash
.venv/bin/python -m pytest -q
.venv/bin/python -m pip wheel . -w /tmp/deep-search-wheel
.venv/bin/deep-search-mcp extract-claims --text 'The sample contains 12 rows and it includes 3 columns.' --section-id methods
.venv/bin/deep-search-mcp entailment-check --claim 'Alpha increased in 2024' --evidence 'Alpha decreased in 2024.'
```

Useful smoke result shape:

```text
extract-claims: count=2 for the bundled sample sentence
entailment-check: label=contradicted, contradiction_signals includes direction_mismatch
pytest: all tests passed
wheel build: succeeded
```

## Review pattern

For substantial deep-search-mcp feature work, run an Opus/Claude critical pass after tests and fix review findings before the final verdict. Ask for blockers, non-blocking issues, test gaps, and verdict. Then re-run tests/build and a final review pass if material fixes were made.
