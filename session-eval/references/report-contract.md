---
summary: Session-eval receipt.json and report.html contract, comparisons, recommendations, and provenance.
read_when:
  - Implementing or evaluating session-eval receipts, HTML reports, trends, or recommendations.
---

# Report contract

Future contract. This document specifies intended receipt and HTML behavior. It does not assert that artifacts have been emitted or that any evaluation has run.

Authority: [canonical store](../docs/index.md), [specification](../docs/specification.md), and [requirement map](../docs/requirement-map.md) (`skills-2ol.3` renders [SE-REPORT-001](../docs/specification.md); `skills-2ol.4` owns [SE-TREND-001](../docs/specification.md) with this renderer; `skills-2ol.8` owns [SE-CORRECT-001](../docs/specification.md) recommendation semantics). Normalized runs remain [SKILL.md](../SKILL.md). Checks remain [check-catalog.md](check-catalog.md). Judges remain [judge-contract.md](judge-contract.md). Ingest paths remain [ingest-formats.md](ingest-formats.md).

Two artifacts per evaluation, written under `OUT`:

| file | audience |
|---|---|
| `receipt.json` | machines, trend store, later diffs |
| `report.html` | humans |

Phoenix's UI is a live React/GraphQL SPA with no static HTML export in source. Do not copy it. Pattern to reimplement: `~/Code/agent-ops/bin/workgraph-dossier` (inline CSS, no CDN, no JS required, stable ids, malformed lines counted). Chart ideas to reimplement independently: time bars, pass-rate lines, skill ranking, baseline vs candidate counts. Render charts as inline SVG. Historical observations: [Phoenix dossier](../docs/sources/phoenix/index.md), [competitors dossier](../docs/sources/competitors/index.md).

eval-dashboards `eval-report/v1` (MIT, v0.x) is a useful *row shape* to study. Pin any borrowed field names in `receipt.json` rather than depending on their CLI. This receipt keeps schema label `styrir-session-eval/v0` (no breaking-version change; the runtime is not implemented).

## Requirement coverage

| Spec ID | This contract must make executable |
|---|---|
| [SE-EVIDENCE-001](../docs/specification.md) | Findings identify source path, snapshot hash, parser version, line/event range, evidence hash. Native identity ≠ display name. Changed bytes → new snapshot; former receipt is not overwritten. |
| [SE-PRIVACY-001](../docs/specification.md) | Redact before serialization. HTML-escape labels. No raw prompts, tool payloads, secrets, or terminal output. |
| [SE-SKILL-001](../docs/specification.md) | Registry rollup of identity/path/digest/optional version; activation source and confidence; historical loaded digest ≠ current on-disk digest. |
| [SE-TREND-001](../docs/specification.md) | Immutable receipts; baseline/candidate comparisons with explicit cohort, catalog, and redaction compatibility; improved/regressed/equal/unmeasurable; infra out of behavioral denominators. |
| [SE-REPORT-001](../docs/specification.md) | Redacted `receipt.json` + self-contained offline `report.html` with the required sections; bounded structural drilldown; empty/malformed/normal cases. |
| [SE-CORRECT-001](../docs/specification.md) | Recommendations with target, action, rationale, evidence, verification, confidence; limitations when unmeasurable; no source or skill writes. |

## Immutable source identity

Identity fields are owned by [SKILL.md](../SKILL.md). Reports must not invent a parallel identity.

| Identity | Rule |
|---|---|
| Native | `run.harness` + `run.native_identity`. Fallback source stem only when native id is absent. |
| Display | `run.display_name` is presentation-only and may change. |
| Snapshot | `run.source_snapshot.sha256` over the consumed manifest (`files[]` path, role, sha256). Identical consumed manifest → same snapshot. Path/role rename or changed bytes → new snapshot. |
| Parser | `run.parser` and `run.parser_version` are always present (adapter-owned). |
| Finding pointer | Each exported finding copies [SKILL.md](../SKILL.md) `evidence[]` items: `source_path`, `snapshot_hash`, `parser_version`, `event_range` `{start_line, end_line}`, `evidence_hash`. |

History: keep prior `receipt.json` files as immutable snapshots under `OUT/history/`. Charts read the snapshot list. Do not mutate old receipts. A new snapshot MUST be a new history entry. Same bytes/manifest MUST NOT overwrite a former receipt under a different hash.

Champion (default): the latest compatible history receipt with `hard_pass=true`, `infra_ok=true`, `coverage.empty=false`, no missing requested inputs and no unknown hard gates, unless the user names another. A user-named incomplete/incompatible baseline is labeled and cannot silently produce a quality delta.

## Coverage and `hard_pass`

Do not treat empty coverage as overall success ([check-catalog.md](check-catalog.md)).

| Field | Rule |
|---|---|
| `coverage.empty` | `true` when no session was ingested or behavioral hard-fail denominator `D` is empty. |
| `hard_pass` | Catalog arithmetic: non-empty decided behavioral gates, all pass, and no unknown hard gates. |
| `infra_ok` | Catalog arithmetic: all applicable infrastructure gates resolved without failure and no evaluation error. Separate from `hard_pass`. |
| `parse_errors` | Count of malformed records. Counted, not dropped, not a behavioral pass. |

Verdict HTML must show `hard_pass`, coverage, `parse_errors`, and `infra_ok` together. Unknown usage/cost stays unknown, never a charted zero ([SE-USAGE-001](../docs/specification.md) via ingest). Infra rows are excluded from behavioral trend denominators.

## receipt.json

Documented `styrir-session-eval/v0` shape (future implementation):

```json
{
  "schema": "styrir-session-eval/v0",
  "catalog_id": "session-eval-check-catalog/v1",
  "generated_at": "ISO-8601",
  "since": "ISO-8601",
  "harnesses_requested": ["claude", "codex", "pi", "omp", "grok"],
  "harnesses_found": ["claude", "grok"],
  "coverage": {
    "sessions_ingested": 0,
    "sessions_malformed": 0,
    "applicable_hard_fail_decided": 0,
    "applicable_hard_fail_unknown": 0,
    "missing_requested_inputs": [],
    "empty": true
  },
  "hard_pass": false,
  "infra_ok": true,
  "feedback_outcome": null,
  "redaction": { "policy": "default-local", "applied": true },
  "runs": [],
  "skills": [],
  "checks": [],
  "comparisons": [],
  "recommendations": [],
  "parse_errors": 0,
  "proof_gaps": [],
  "provenance": {
    "parser": "adapter-owned-name",
    "parser_version": "adapter-owned-version",
    "snapshots": []
  }
}
```

| Field | Ownership / rule |
|---|---|
| `runs[]` | [SKILL.md](../SKILL.md) normalized records. Do not redefine fields here. Export redacts payloads; pointers and structural fields remain. |
| `skills[]` | Registry rollup, not a second skill schema: `name`, `path`, `digest`, optional `version`, `activations` (source + confidence counts), `hard_fail_count`, `last_seen`, `historical_loaded_digest`, `current_on_disk_digest`. Never attribute current on-disk content to a past load without activation evidence. |
| `checks[]` | Rollup by catalog `id` with counts of `pass` / `fail` / `not_applicable` / `unknown`, plus `class`, `kind`, `channel`. Per-run detail stays on `runs[].checks[]`. |
| `comparisons[]` | [Comparisons](#comparisons). Use an explicitly named baseline or the compatible champion policy above; empty only when no eligible baseline exists, with the reason in `proof_gaps`. |
| `recommendations[]` | [Recommendations](#recommendations). Always present (may be empty only when there are no findings *and* no limitations to record; an unmeasurable evaluation still emits limitation rows). |
| `proof_gaps[]` | Including `claim.historical_policy_unavailable` when SE-CHECK-002 cannot reconstruct Git/Beads/WAL policy. |
| `provenance.snapshots[]` | `{native_identity, source_path, sha256, parser, parser_version}` for each consumed snapshot. |
| `redaction.policy` | Comparison key. Default `default-local`. |

Sort keys for determinism when emitting test fixtures. Do not read the wall clock inside a golden-file test; production reports may stamp `generated_at`.

Unknown events stay in private ingest memory/source. Exported receipts contain neither secrets nor unknown raw values.

## Comparisons

A quality delta is allowed only when **all** compatibility gates pass. Otherwise every behavioral count is `unmeasurable` and no improved/regressed/equal figure is emitted.

| Gate | Compatible when |
|---|---|
| Catalog | `catalog_id` (and check-id set) equal on baseline and candidate |
| Cohort | Explicit population: same harness filter or documented intersection; skill-revision comparisons name both digests |
| Redaction | `redaction.policy` equal |

```json
{
  "baseline_receipt": "history/example.json",
  "candidate_receipt": "receipt.json",
  "cohort": {
    "harnesses": ["claude"],
    "skill_digests": ["sha256:aaa", "sha256:bbb"],
    "compatible": true
  },
  "catalog": {
    "baseline": "session-eval-check-catalog/v1",
    "candidate": "session-eval-check-catalog/v1",
    "compatible": true
  },
  "redaction_policy": {
    "baseline": "default-local",
    "candidate": "default-local",
    "compatible": true
  },
  "counts": {
    "improved": 0,
    "regressed": 0,
    "equal": 0,
    "unmeasurable": 0
  },
  "unmeasurable_reasons": []
}
```

| Rule | Requirement |
|---|---|
| Denominator | Pair observations by explicit comparable subject/check identity; pass→fail is regressed, fail→pass improved, equal decided states equal. Unmatched or unknown observations are unmeasurable. Across different session populations show labeled aggregate rates/counts with coverage, not invented one-to-one outcomes. Infra failures are separate. |
| Missing usage | Token/cost metrics are `unmeasurable`, never a zero delta. |
| Two skill revisions | Compare by content digest, not display name. Historical loaded digest remains distinct from current on-disk digest. |
| Incompatible catalogs or cohorts | `compatible=false`; `counts.unmeasurable` covers the attempted population; no silent quality delta. |

## Recommendations

Required receipt array and required HTML section `recommendations`. Generating recommendations MUST NOT write sources, skills, or adapters ([SE-CORRECT-001](../docs/specification.md)). Automatic skill editing remains rejected.

Each row:

```json
{
  "id": "rec-001",
  "target": {
    "kind": "skill",
    "path": "/Users/brooks/Code/skills/example/SKILL.md",
    "digest": "sha256:aaa",
    "name": "example"
  },
  "action": "State that tool_use without a paired result after explicit terminal evidence is a failure.",
  "rationale": "Recurring tool.unpaired fails on this first-party digest.",
  "evidence": [
    {
      "check_id": "tool.unpaired",
      "source_path": "/abs/session.jsonl",
      "snapshot_hash": "sha256:0",
      "parser_version": "v1",
      "event_range": { "start_line": 10, "end_line": 40 },
      "evidence_hash": "sha256:1"
    }
  ],
  "verification": "Run a new comparable session with the revised skill and verify explicit terminal evidence plus paired tool results. Preserve the original snapshot and its failing result; re-ingesting it must not rewrite history.",
  "confidence": "high",
  "limitation": null
}
```

| Field | Rule |
|---|---|
| `target` | First-party skill or adapter only (`kind`: `skill` \| `adapter`), determined by resolved source under the configured first-party root. A harness symlink to that root is first-party; unresolved or external ownership is not an edit target. |
| `action` | Concrete change to propose. Null iff `limitation` is set. |
| `rationale` | Why this target, tied to check ids. Null iff `limitation` is set. |
| `evidence` | Finding pointers (same shape as [SKILL.md](../SKILL.md) check evidence, plus `check_id`). |
| `verification` | Observable check/receipt condition that would confirm the change. Null iff `limitation` is set. |
| `confidence` | `high` \| `medium` \| `low` \| `none`. |
| `limitation` | Required when evidence is insufficient. No invented patch. `target`/`action`/`rationale`/`verification` are null; `confidence` is `none`. |

Judge rows MAY inform a recommendation through the shared check result; they are optional inputs, not required ([requirement-map.md](../docs/requirement-map.md)). Deterministic findings are sufficient.

## report.html

One self-contained offline file. Inline CSS. No network. No session prompt text, tool payloads, secrets, or terminal output. No JavaScript required. Openable as a `file:` document.

Required sections and ids:

| id | content |
|---|---|
| `verdict` | `hard_pass`, coverage (including `empty`), `infra_ok`, run count, `parse_errors` |
| `coverage` | Harnesses found vs requested; gaps; unknown usage called out as unknown |
| `trends` | SVG: sessions/day, hard_fail/day, tokens where known (omit or mark unmeasurable when unknown) |
| `skills` | Table of skill digest, optional version, activations (source/confidence), fail counts; opaque third-party flagged; historical vs on-disk digest |
| `sessions` | Table of `run.id`, harness, native identity, display name, model, tokens, checks failed; link to `source_path` not transcript |
| `failures` | Grouped by check id with evidence pointers |
| `comparisons` | Cohort/catalog/redaction gates and improved/regressed/equal/unmeasurable counts |
| `recommendations` | Target, action, verification, confidence, evidence pointers, or explicit limitations |
| `provenance` | Generator name, `catalog_id`, parser name/version, snapshot hashes, redaction notice |
| `footer` | Same provenance summary for print/offline reading |

Stable ids for annotation: `session-<id>`, `check-<id>`, `skill-<digest8>`, `rec-<id>`, `compare-<n>`.

### Drilldown

Bounded drilldown exposes **structural metadata only**:

- `run.lineage` parent/child/attempt/continuation refs (including explicit `unknown`)
- tool pairing ids (call id ↔ result id), unpaired marker
- lifecycle state and evidence pointers
- check `evidence[]` pointers

It does not embed raw transcripts, prompts, arguments, results, or terminal output. Specialized raw viewers, if any, are out of scope; this report may link `source_path` only.

### Source escaping

Every interpolated label, path, check id, skill name, harness id, display name, and native id from source MUST be HTML-escaped before insertion. Synthetic markup in a session label must render as text, never as elements. Secrets never appear; `tool.secret_pattern` shows hash + range only.

Malformed JSONL: show count, do not silently drop.

WorkGraph dossiers stay at `.pipeline/<slug>/dossier.html`; this report may *link* them. It must not inline `stages/**/full.md`.

## Future acceptance scenarios

Documentation-level only. None is claimed executed.

| Scenario | Expected report outcome |
|---|---|
| Empty evaluation (no sessions) | `coverage.empty=true`, `hard_pass=false`, required HTML sections still present; recommendations contain a limitation row, not an invented patch |
| Malformed JSONL mixed with valid runs | `parse_errors` > 0; malformed counted; valid runs reported; offline HTML opens without network |
| Normal ingested run with decided hard-fail passes | `hard_pass` follows catalog; verdict shows coverage nonempty |
| Repeat ingest of identical snapshot bytes/manifest | Same snapshot identity; history not overwritten |
| Changed source bytes, same native id | New snapshot and new history entry; former receipt remains |
| Two skill revisions, same catalog/cohort/redaction | Comparison counts improved/regressed/equal/unmeasurable by digest |
| Missing usage on otherwise comparable receipts | Token trend unmeasurable, not zero |
| Different `catalog_id` | Comparison `compatible=false`; no quality delta |
| Recurring first-party `tool.unpaired` | Recommendation with target, action, evidence, verification, confidence; sources unchanged |
| Completion claim with no recorded outcomes | Limitation recommendation; `proof_gaps` includes historical-policy unavailability |
| Markup/secret in display names | Escaped text in HTML; secret absent |

## Non-goals

- Auto-writing skills, adapters, or session files
- Provider uploads
- Live SPA, CDN, or required JavaScript
- A second normalized run schema
- Treating vacuous `hard_pass` as champion or overall success
