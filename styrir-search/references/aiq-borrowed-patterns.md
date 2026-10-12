# AI-Q Borrowed Patterns

Use this reference when `styrir_plus` needs structured coverage or `deep_search_local` needs report-grade local artifacts.

## Borrow

- Planner -> researcher -> orchestrator sequence.
- Source registry as the authority for citeable URLs.
- Completeness checks before synthesis.
- Preserved run context across plan, notes, findings, report, and gate result.

## Do Not Borrow

- LangChain DeepAgents runtime.
- NAT deployment stack.
- Modal sandbox.
- AI-Q middleware internals.

## `styrir_plus` Minimum Bundle

`styrir_plus` remains a bounded search lane. Require:

- `plan.json` with `mode: "styrir_plus"` and non-empty `facets[]`.
- `source-registry.json` with non-empty `sources[]`.
- `ledger.json` that passes the normal Styrir ledger gate.
- `contradiction-sweep.md`.
- `gate-result.json` with `gateStatus: "pass"`.

## `deep_search_local` Run Directory

`deep_search_local` is report-grade and local. It validates the run directory that `deep-search-mcp` itself writes (`init-run` through `render-report-bundle --strict`), not a Styrir-specific bundle. Require:

- `run_manifest.json` from `init-run` (has `run_id`).
- `sources.jsonl` with at least one registered `source_id`.
- `claims.jsonl` with at least one recorded `claim_id`.
- `report.md`, which `render-report-bundle --strict` writes only after its own section, citation, claim-support, contradiction, challenge, and temporal checks pass. A `report.candidate.md` without `report.md` means the bundle failed.
- `[claim:<id>]` markers in `report.md` that resolve to `claims.jsonl`.

The artifact gate is structural, not a truth verifier. It blocks empty, malformed, uncited, and thin bundles (plus) and unrendered or unprovenanced deep-search runs (deep-local). It does not prove that claims are true.

Run `npm run artifact-gate -- <mode> <run-dir>` before final synthesis.
