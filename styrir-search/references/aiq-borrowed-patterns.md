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

## `deep_search_local` Minimum Bundle

`deep_search_local` is report-grade and local. Require:

- `plan.json` with `mode: "deep_search_local"` and non-empty `facets[]`.
- `research-notes/*.md`.
- `source-registry.json` with non-empty `sources[]`.
- `consolidated-findings.md` with section headings, substantive findings, and `[s1]`-style source-id citations that exist in the registry.
- `report.md` with substantive final prose, section headings, `[s1]`-style source-id citations, and a Sources section.
- `gate-result.json` with `gateStatus: "pass"`.

The artifact gate is structural, not a truth verifier. It blocks empty, malformed, uncited, and thin bundles; it also warns when registered sources are not cited. It does not prove that claims are true.

Run `npm run artifact-gate -- <mode> <run-dir>` before final synthesis.
