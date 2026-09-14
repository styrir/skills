---
summary: Versioned deterministic session-eval check catalog, applicability, evaluator results, and SE-CHECK-002 claim checks.
read_when:
  - Implementing or evaluating session-eval checks, hard_pass, or command/completion-claim contradictions.
---

# Check catalog

Runtime owner: `session-eval/scripts/evaluate.py` (`skills-2ol.6`). This catalog remains the sole owner of named checks, applicability, observation predicates, and suite `hard_pass` arithmetic. Presence of that runtime is not evidence that acceptance scenarios have been executed.

Authority: [canonical store](../docs/index.md), [specification](../docs/specification.md), and [requirement map](../docs/requirement-map.md) (`skills-2ol.6` for SE-CHECK-001/002 and SE-WORKGRAPH-001; `skills-2ol.7` for named judges). This file is the sole owner of named checks, applicability, observation predicates, and suite `hard_pass` arithmetic. It does not own the normalized run record ([SKILL.md](../SKILL.md)), ingest adapters ([ingest-formats.md](ingest-formats.md)), judge rubrics ([judge-contract.md](judge-contract.md)), or receipt/HTML layout ([report-contract.md](report-contract.md)).

Catalog identity: `session-eval-check-catalog/v1`. Receipt schema remains `styrir-session-eval/v0` ([report-contract.md](report-contract.md)). Incompatible catalog identities cannot produce a quality delta. Judges consume this evaluation-result contract; they do not define a second result type.

Inspired by Phoenix evaluator *categories* and WorkGraph `hard_fail` / `expected_behavior` split. Independent wording and independent implementation. Do not copy Phoenix prompt YAMLs or evaluator source. Historical observations: [Phoenix dossier](../docs/sources/phoenix/index.md), [competitors dossier](../docs/sources/competitors/index.md).

## Implementation status

`skills-2ol.6` implements every `kind=code` row against ingest `styrir-session-eval/v0` receipts and hash-verified frozen snapshots (`out/.private/snapshots/<file-sha256>/...`). Public API: `evaluate_receipt(...)` plus standalone `python3 session-eval/scripts/evaluate.py --receipt ...`. Claim extraction uses versioned `CLAIM_LANGUAGE_VERSION` markers; skill registry rows consume supplied registry evidence or report `unknown`/`registry_unavailable` and do not reimplement history. Requested WorkGraph scoring invokes existing `/Users/brooks/Code/agent-ops/bin/workgraph-eval-score score --evidence --manifest --allowlist`; unrequested invocations are zero. Focused CLI smoke: `session-eval/scripts/smoke_evaluate.py`. This section does not record a passing run.

## Requirement coverage

| Spec ID | This catalog must make executable |
|---|---|
| [SE-CHECK-001](../docs/specification.md) | Versioned deterministic catalog; evidence-bound results; explicit applicability; infra/parse failure is not a behavioral pass; empty coverage is not successful evaluation. |
| [SE-CHECK-002](../docs/specification.md) | Command-outcome and completion-claim contradiction checks on *available session evidence only*; contradiction versus unknown; no checkout mutation; current tree is not historical state; not a Git/Beads/WAL policy engine. |
| [SE-WORKGRAPH-001](../docs/specification.md) | Optional requested adjunct invokes existing `workgraph-eval-score`; records result/errors; does not duplicate publication rules or ingest `stages/**/full.md`. |

Judges are named here so the default suite can exclude them. Rubric inputs, steps, pass/fail/unknown, provider approval, and identity live only in [judge-contract.md](judge-contract.md) ([SE-JUDGE-001](../docs/specification.md)).

## Status, class, kind, channel

Result `status` values: `pass`, `fail`, `not_applicable`, `unknown`.

| Field | Values | Meaning |
|---|---|---|
| `class` | `hard_fail` \| `expected_behavior` | `fail` on `hard_fail` can falsify `hard_pass`. `fail` on `expected_behavior` is counted and reported only. |
| `kind` | `code` \| `llm` | Default suite = every `kind=code` check that is in scope. `llm` rows are opt-in judges. |
| `channel` | `behavior` \| `infra` | Behavioral denominators use `behavior` only. Parse, IO, adapter, and provider-infrastructure faults use `infra`. |

`kind=llm` checks require an explicit ask plus `judge.model` and `judge.rubric_id` on the receipt. Opt-out produces zero provider calls and leaves those rows `not_applicable`. Judges never enter `hard_pass` unless the user promotes a named judge to blocking.

## Applicability and observation

Evaluate in this order. Do not mix a pass predicate into a fail column.

1. **Applicability.** If applicability is established false, status is `not_applicable`. If applicability itself cannot be established, status is `unknown`. Missing *pattern* is `not_applicable` only when the relevant source coverage is complete enough to establish that the subject never occurred.
2. **Evidence availability.** If the check is applicable and the evidence required by the pass/fail predicates is absent or unreadable, status is `unknown`. `unknown` is never `pass`.
3. **Fail predicate.** If applicable and `fail when` matches recorded evidence, status is `fail`.
4. **Pass predicate.** If applicable and `pass when` matches recorded evidence, status is `pass`.
5. **Contradiction.** If both pass and fail would match, status is `fail` and `error` records `predicate_conflict`.

Missing evidence is not an applicable hard-fail. An applicable hard-fail `fail` requires recorded evidence that satisfies `fail when`.

EOF, a last JSONL line, a closed file handle, or a parser reaching end-of-stream is **not** terminal session evidence and **not** by itself `session end` for unpaired-tool checks ([SE-INGEST-002](../docs/specification.md)).

Terminal evidence is an explicit harness terminal/result/`task_complete` event or an authoritative `ended_at` (or equivalent) on session metadata. An explicit live/open marker establishes `live`, not terminal. Session state is `run.lifecycle.state`: `terminal` | `live` | `unknown` ([SKILL.md](../SKILL.md)). `unknown` includes EOF-only streams. This catalog must not invent a parallel lifecycle vocabulary.

## Evaluator result

Every check emits one [SKILL.md](../SKILL.md) `run.checks[]` object. Catalog semantics for `class`, `channel`, `observed`, and `error` live here; field names and evidence pointers are not forked.

```json
{
  "id": "tool.unpaired",
  "class": "hard_fail",
  "kind": "code",
  "channel": "behavior",
  "status": "fail",
  "observed": "unpaired_after_explicit_end",
  "evidence": [
    {
      "source_path": "/abs/session.jsonl",
      "snapshot_hash": "sha256:0",
      "parser_version": "v1",
      "event_range": { "start_line": 10, "end_line": 40 },
      "evidence_hash": "sha256:1"
    }
  ],
  "error": null
}
```

| Field | Rule |
|---|---|
| `id` | Catalog id. Stable; never recycle. |
| `status`, `kind`, `class`, `channel`, `observed`, `error`, `evidence[]` | [SKILL.md](../SKILL.md) `run.checks[]`. `observed` is a short machine token (not prose, not raw payloads). |
| `evidence[]` items | `source_path`, `snapshot_hash`, `parser_version`, `event_range.start_line`/`end_line`, `evidence_hash`. `snapshot_hash` is the aggregate `run.source_snapshot.sha256` of the consumed path/role/content-hash manifest and is identical for every file in that snapshot ([SE-EVIDENCE-001](../docs/specification.md), [judge-contract.md](judge-contract.md)). Per-file content digests live only in `run.source_snapshot.files[].sha256`. `source_path` must name a member of that manifest. `evidence_hash` is the SHA-256 of the verified frozen snapshot bytes covering `event_range`. `parser_version` is `run.parser_version`. `run.parser` and `run.parser_version` are always present (adapter-owned). |
| `error` | Null on a clean behavioral observation. Infra/parse/provider failures set `error` and must not be stored as a behavioral `pass`. |

`error` object when present:

```json
{
  "kind": "parse",
  "channel": "infra",
  "message": "JSONL line is not an object"
}
```

`error.kind`: `parse` \| `io` \| `adapter` \| `provider` \| `internal` \| `predicate_conflict`. No retry policy is specified; a provider or IO fault is recorded once as `error` and the behavioral status is `unknown` unless the row is itself an infra check (then `fail` when that infra predicate matches).

Unknown events and raw payloads remain in private ingest memory/source. Exported receipts carry pointers and redacted labels only ([SE-PRIVACY-001](../docs/specification.md)).

## Suite verdict

Let **D** be the set of `class=hard_fail`, `channel=behavior`, `kind=code` (plus user-promoted judges) results whose `status` is `pass` or `fail`. Let **U** be hard gates whose applicability or required evidence is unresolved (`status=unknown`).

- `hard_pass` is `true` iff `D` is non-empty, every member of `D` is `pass`, and `U` is empty.
- If `D` is empty (no sessions, nothing applicable, or every applicable hard gate is `unknown`/`not_applicable`), `hard_pass` is `false`. Vacuous success is forbidden.
- An unknown hard gate is not a proven behavioral failure, but it prevents a clean gate verdict. Report it in coverage; never remove it to obtain a pass.
- `expected_behavior` results never enter `D`, unless a named judge is explicitly promoted.
- Infra results never enter behavioral denominators. `infra_ok` is `true` iff every applicable infra gate is resolved without failure and no evaluation `error` occurred. Unknown infra evidence or missing requested inputs prevents overall success.
- A judge `pass` with `hard_pass=false` is not a contradiction. `feedback_outcome` may be a judge label.

Receipts expose `hard_pass`, `infra_ok`, and coverage (`sessions_ingested`, decided versus unknown hard gates, `empty`, missing requested inputs). Overall evaluation success requires non-empty coverage, no missing requested inputs or unresolved hard gates, `hard_pass=true`, and `infra_ok=true`. Do not collapse those into a single unnamed flag.

## Loop rule (`tool.repeat_loop`)

Scope: tool-call sequence of one agent identity (parent and each child/attempt separately). Do not merge nested agents into one counter.

**Normalized args.** Build a canonical digest of the tool arguments as recorded in the session snapshot:

1. If args are JSON/object-like, parse; otherwise treat as a single string.
2. Sort object keys lexicographically; preserve array order, scalar types and exact string values.
3. Do not drop argument keys or normalize whitespace inside strings: paths, commands, nonces and timestamps may be semantically meaningful tool arguments.
4. Exclude event-envelope call IDs/timestamps from the argument object, but never remove identically named keys actually present inside the tool arguments.
5. Digest the canonical form. Equality of digests is equality of normalized args.

Do not reconstruct historical Git index, Beads, or WAL contents to normalize args. Paths are compared as recorded strings, not resolved against today's checkout.

**Consecutive.** Count adjacent tool invocations in that agent sequence with the same tool name and equal normalized-args digest. A progress marker resets the counter to 0.

**Progress markers** (reset):

- intervening user turn
- different tool name
- unequal normalized-args digest
- nested-agent boundary (switch of agent id / parent / attempt)
- explicit session terminal event
- a tool result on this call with `is_error`/`isError` false whose result-payload evidence hash differs from the immediately previous same-tool result hash

**Not progress:** identical error payloads; retries with the same normalized args; clock advancing; EOF; unpaired calls; current checkout diffs.

**Fail when** the consecutive count is ≥ 4 with no progress marker. Ordinary single (or few) tool errors are `tool.result_error` only; they do not satisfy this fail predicate.

**Unknown evidence or order.** A missing successful result hash, unavailable arguments, or unresolved cross-stream order is decided by every permitted concrete completion: all fail → `fail`; all pass → `pass`; mixed → `unknown`. A possible reset cannot be assumed absent. A proven independent failure is not erased by earlier or irrelevant uncertainty. Same-stream source order is authoritative; cross-stream order uses timestamps or native links only, never filename, global line, or mtime order. Equal timestamps across streams remain unordered.

## Claim checks (SE-CHECK-002)

These checks compare *claims recorded in the session* with *command/tool outcomes recorded in the same snapshot*. They are not a historical Git, Beads, or WAL policy engine. Complete mutable policy reconstruction remains deferred ([specification](../docs/specification.md) research dispositions).

Forbidden:

- mutating the checkout, index, Beads, WAL, or session files
- treating the present working tree, `git status`, or current SKILL.md bytes as the historical state
- inferring test/lint/patch correctness from files that the session did not record
- launching or stopping WorkGraph runs

When a claim depends on Git/Beads/WAL/policy truth that the snapshot does not contain, emit `status=unknown` and a `proof_gaps` entry (`claim.historical_policy_unavailable`). That gap is disclosure, not a pass.

WorkGraph scoring is reused only when requested ([SE-WORKGRAPH-001](../docs/specification.md)); it is not implied by these claim checks.

## Catalog

`unknown when` is omitted when it is only the global evidence-availability rule.

### Ingest

| id | class | kind | channel | applicable when | pass when | fail when |
|---|---|---|---|---|---|---|
| `ingest.parse_error` | hard_fail | code | infra | A requested primary stream is opened | Every attempted JSONL/JSON record parsed as an object | A line/record was not an object |
| `ingest.schema_unknown_ok` | expected_behavior | code | behavior | A parsed object contains fields not in the adapter schema | Unknown fields were retained in private ingest memory | Adapter dropped unknown fields |
| `ingest.sidecar_not_stream` | hard_fail | code | infra | A sidecar index/SQLite exists *and* the primary stream exists | Adapter treated the stream as primary and used the sidecar only to enrich | Adapter treated SQLite/index as the only source while the stream exists |

Malformed records are counted. They do not become behavioral `pass`. Unknown fields are retained privately and redacted on export.

### Session

| id | class | kind | channel | applicable when | pass when | fail when |
|---|---|---|---|---|---|---|
| `session.identity_missing` | hard_fail | code | behavior | A session record was produced | `run.native_identity` is present, or fallback source stem was used because native id is absent | Neither native identity nor fallback stem is present |
| `session.incomplete` | expected_behavior | code | behavior | Session state is not `live` | Explicit terminal evidence is present (`lifecycle.state=terminal`) | No explicit terminal evidence (including EOF-only → `unknown` lifecycle) |
| `session.clock_skew` | expected_behavior | code | behavior | One Grok session contains mixed epoch-seconds and ISO timestamps | Adapter normalized them to one scale | Mixed scales remain unnormalized |

`session.incomplete` never uses EOF as pass evidence. Live sessions are `not_applicable`. `run.display_name` is not identity.

### Tools

| id | class | kind | channel | applicable when | pass when | fail when |
|---|---|---|---|---|---|---|
| `tool.unpaired` | hard_fail | code | behavior | Session state is `terminal` | Every `tool_use` has a paired result | A `tool_use` has no paired result after explicit terminal evidence |
| `tool.result_error` | expected_behavior | code | behavior | At least one tool result is present | No result has `is_error`/`isError` true | A result has `is_error`/`isError` true (count; does not enter `D`) |
| `tool.repeat_loop` | hard_fail | code | behavior | The agent sequence contains at least one tool call | Consecutive same-tool+normalized-args run is &lt; 4 or a progress marker reset it | Consecutive count ≥ 4 with no progress marker |
| `tool.secret_pattern` | hard_fail | code | behavior | A structured credential-bearing field is present | No key/token regex match in those field values, or the match is allowlisted | A credential-bearing field value matches the key/token regex and is not allowlisted |

`tool.unpaired` is `not_applicable` when state is `live`, and `unknown` when state is `unknown` (EOF is not terminal). Do not drop unpaired events.

`tool.result_error` counts ordinary tool errors. Repeated failing calls with the same normalized args are `tool.repeat_loop`.

`tool.secret_pattern` scans named credential fields (`api_key`, `secret`, `password`, `token`, and aliases), not every JSONL line. Allowlisted example/placeholder values and SKILL.md path fragments do not fail. Records `evidence_hash` + `event_range`. Never write the secret, raw line, or payload into the result, receipt, or HTML. Not applicable when no credential field is present.

### Tokens and cost

| id | class | kind | channel | applicable when | pass when | fail when |
|---|---|---|---|---|---|---|
| `tokens.unknown_not_zero` | hard_fail | code | infra | Adapter emitted token/cost fields for a stream | Absent usage remains `unknown` (not `0`) | Adapter wrote `0` where the harness has no usage field |
| `tokens.accounting_present` | expected_behavior | code | behavior | A usage object is present on the stream or sidecar | Usage is internally consistent and overlapping streams are not double-counted | Usage is present but inconsistent or double-counted |

Absence of usage is `not_applicable` for `tokens.accounting_present` and must remain `unknown` on the run record, never a silent zero ([SE-USAGE-001](../docs/specification.md) via ingest).

### Skills

| id | class | kind | channel | applicable when | pass when | fail when |
|---|---|---|---|---|---|---|
| `skill.registry_unreadable` | hard_fail | code | behavior | A joinable SKILL.md path is listed from a named path key (`path`, `skill_path`) | File exists and has `name:` frontmatter | File missing or no `name:` frontmatter |
| `skill.digest_drift` | expected_behavior | code | behavior | Two comparable registry snapshots for the same skill identity exist | Snapshot content digests are equal | Content digest changed between those snapshots |
| `skill.opaque_third_party` | expected_behavior | code | behavior | An activation path and resolvable ownership are present | Resolved source is under the configured first-party root | Resolved source is outside the configured first-party root |
| `skill.activation_untracked` | expected_behavior | code | behavior | Session used a skill-like tool or path mention | A digestable SKILL.md exists for that activation | No digestable SKILL.md |

`skill.digest_drift` reports; it does not enter `D`. Never attribute current on-disk content to a past load without activation evidence ([SE-SKILL-001](../docs/specification.md)). Registry field ownership remains [SKILL.md](../SKILL.md).

The configured first-party root defaults to `~/Code/skills`, but may differ on another machine. A harness symlink into that root is first-party, not automatically opaque. Unresolved ownership/digest evidence is `unknown`; a current registry snapshot does not establish which historical bytes were loaded.

### Claims (SE-CHECK-002)

| id | class | kind | channel | applicable when | pass when | fail when | unknown when |
|---|---|---|---|---|---|---|---|
| `claim.command_outcome` | hard_fail | code | behavior | An unambiguous command/check outcome claim is recorded | Final recorded outcome of the identified command/attempt agrees with the claim | Final recorded outcome of the identified command/attempt contradicts the claim | Command identity, attempt association or final outcome is ambiguous/missing |
| `claim.completion` | hard_fail | code | behavior | An unambiguous completion claim is recorded | Every identified acceptance check has a successful final attempt before the claim | An identified check's final attempt before the claim failed with no recorded recovery | Acceptance-check set, attempt association or final outcomes cannot be established |

`not_applicable` only when complete-enough source coverage establishes that no such claim occurred. A recorded completion claim remains applicable even when it names no acceptance checks; that missing set yields `unknown` and keeps the hard gate unresolved. Ambiguous claim detection also remains `unknown`, not `not_applicable`.

Claims are taken from recorded assistant/user-visible completion or command-status language. Deterministic extraction must use a versioned set of explicit markers/patterns and unambiguous command/attempt references; ambiguous prose is `unknown`, not invented semantic certainty. A prior failure followed by a recorded successful retry is not a contradiction of a later success claim. `is_error=false` alone does not establish exit zero or fulfillment of all acceptance checks; require the outcome appropriate to the claim. Do not shell out, consult current Git status, or assume every error anywhere in the snapshot contradicts completion.

### WorkGraph adjunct (optional)

In scope only when the user requested WorkGraph scoring **and** a `.pipeline/<slug>` run dir was ingested. Invoke the existing `workgraph-eval-score` binary on that run dir. Attach the returned `workgraph-eval-result` object (or its errors). Do not reimplement its hard_fail set, publication rules, or lenses. Do not launch or stop runs. Do not read `stages/**/full.md` into reports.

| id | class | kind | channel | applicable when | pass when | fail when |
|---|---|---|---|---|---|---|
| `closeout.full_md_leaked` | hard_fail | code | infra | This evaluation emitted `report.html` | HTML does not include `stages/**/full.md` contents | Report HTML included `stages/**/full.md` |
| `closeout.eval_score_fail` | hard_fail | code | behavior | User requested `workgraph-eval-score` and the binary produced a result | Attached result has `hard_pass=true` | Attached result has `hard_pass=false` |

If the binary is requested but fails to execute, record `error.kind=io` (or `internal`), status `unknown` on `closeout.eval_score_fail`, and keep the failure visible. Do not treat a missing adjunct result as behavioral `pass`.

### Opt-in LLM judges

Named here so the catalog is complete. Rubrics, approval, and identity: [judge-contract.md](judge-contract.md).

| id | class | kind | channel |
|---|---|---|---|
| `judge.completeness` | expected_behavior | llm | behavior |
| `judge.grounding` | expected_behavior | llm | behavior |
| `judge.tool_selection` | expected_behavior | llm | behavior |
| `judge.friction` | expected_behavior | llm | behavior |

Default: `not_applicable`, zero provider calls. They never set suite `hard_pass` unless the user promotes a judge to blocking.

## Future acceptance scenarios

These remain documentation-level scenarios. `smoke_evaluate.py` is the executable proof path; it is not claimed executed here.

| Scenario | Expected catalog outcome |
|---|---|
| Malformed JSONL line among otherwise valid records | `ingest.parse_error` `fail` (infra); malformed counted; behavioral checks on that record not `pass`; suite `infra_ok=false` |
| Four consecutive same-tool same-normalized-args failures with no progress marker | `tool.repeat_loop` `fail`; `tool.result_error` also `fail` (expected_behavior, counted only) |
| A single ordinary `is_error` tool result | `tool.result_error` `fail`; `tool.repeat_loop` `pass` or `not_applicable`; does not falsify `hard_pass` |
| Applicable hard_fail whose required evidence is absent | that check `unknown`, not a proven behavior failure; `hard_pass=false` even when another hard gate passed |
| One requested harness missing, or zero sessions ingested | Missing harness is an explicit coverage gap and prevents overall success; zero sessions additionally means coverage empty and hard_pass=false |
| Stream ends at EOF with unpaired tools and no terminal event | session state `unknown`; `tool.unpaired` `unknown`; `session.incomplete` `fail` (expected_behavior); EOF not treated as end |
| Explicit terminal event with unpaired `tool_use` | `tool.unpaired` `fail` |
| Claimed successful check with recorded non-zero exit in the same snapshot | `claim.command_outcome` `fail` |
| Completion/success claim with no recorded exit or test evidence | `claim.command_outcome` / `claim.completion` `unknown`; `proof_gaps` includes historical-policy unavailability when Git/Beads/WAL would be required; no live `git status` used |
| Present checkout contradicts a historical claim but the snapshot has no exit evidence | still `unknown`; checkout must not be consulted |
| User requested WorkGraph score on a known-failing receipt | attached `workgraph-eval-result` remains visible; `closeout.eval_score_fail` `fail` when `hard_pass=false` |
| WorkGraph not requested | both adjunct checks `not_applicable`; binary not invoked |

## Non-goals

- Automatic patch-correctness judgment against a mutable worktree
- Full Git/Beads/WAL policy reconstruction
- Provider calls (judges)
- Source mutation, auto-writes, or skill edits
- Duplicating the normalized run schema or receipt layout
