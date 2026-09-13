# Contradiction sweep

- **OTel-required vs file-log-native — resolved by scope.** Harbor ATIF is a JSON schema and local Pydantic validator. `ccdiag` and `claude-code-transcripts` consume local Claude JSONL and produce local diagnostics/static HTML. OpenInference is transport/file-format agnostic and can export to an OTel-compatible collector. Make OTel/Phoenix optional, not an ingestion prerequisite.
- **ATIF JSON document vs source JSONL.** Source logs are line-delimited events; ATIF is a root document with a `steps` array. Stream and correlate input lines, then assemble one ATIF trajectory per logical session (or explicitly shard); do not map each JSONL line to an ATIF root.
- **ATIF agent version vs SKILL.md version.** ATIF requires `agent.version`; Agent Skills only permits arbitrary optional `metadata.version`. Keep harness/runtime and skill identity in separate fields.
- **Semver vs exact content.** `metadata.version` is a human label; Vercel's `skillFolderHash` is a Git tree SHA used for update detection. Store both with source/path, commit/ref, observed time, and evaluation run ID.
- **ATIF version drift.** RFC status is active and changelog v1.8, but the illustrative trajectory still says `ATIF-v1.5`; v1.7 changes subagent reference resolution. Pin schema/model versions and validate explicitly.

## Residual proof gaps

1. Codex rollout parser and license were not fetched in this ten-fetch wave.
2. Agent Skills and Vercel CLI LICENSE files were not fetched; do not vendor their implementations based on docs alone.
3. No ready-made Claude/Codex JSONL-to-ATIF exporter was established by fetched primary sources.
4. No common longitudinal SKILL.md evaluator artifact schema was established; use a fixed-task baseline/treatment record plus the provenance tuple as a project convention.
