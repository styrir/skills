# Check catalog

Status values: `pass`, `fail`, `not_applicable`, `unknown`.

Missing evidence on a `hard_fail` check → `fail` with `observed=evidence_missing`.
Missing pattern on `expected_behavior` → `not_applicable` (does not fail the run).

`kind`: `code` (deterministic) or `llm` (opt-in judge). Default suite is all `code` checks. LLM judges require an explicit ask plus `judge.model` and `judge.rubric_id` on the receipt.

Inspired by Phoenix evaluator *categories* and WorkGraph `hard_fail` / `expected_behavior` split. Independent wording and independent implementation. Do not copy Phoenix prompt YAMLs.

## Ingest

| id | class | kind | fail when |
|---|---|---|---|
| `ingest.parse_error` | hard_fail | code | JSONL line is not an object |
| `ingest.schema_unknown_ok` | expected_behavior | code | (informational) unknown fields preserved |
| `ingest.sidecar_not_stream` | hard_fail | code | Adapter treated SQLite/index as the only source while the stream exists |

## Session

| id | class | kind | fail when |
|---|---|---|---|
| `session.identity_missing` | hard_fail | code | No native session id and no fallback stem |
| `session.incomplete` | expected_behavior | code | Stream has no terminal result / `task_complete` / ended_at (live sessions are N/A) |
| `session.clock_skew` | expected_behavior | code | Mixed epoch-seconds vs ISO in one Grok session without normalization |

## Tools

| id | class | kind | fail when |
|---|---|---|---|
| `tool.unpaired` | hard_fail | code | tool_use without tool_result after session end |
| `tool.result_error` | expected_behavior | code | `is_error` / `isError` true (count; does not alone fail the suite) |
| `tool.repeat_loop` | hard_fail | code | Same tool+normalized args ≥ 4 consecutive times with no progress marker |
| `tool.secret_pattern` | hard_fail | code | Source line matches key/token regex (record hash + line, never the secret) |

## Tokens and cost

| id | class | kind | fail when |
|---|---|---|---|
| `tokens.unknown_not_zero` | hard_fail | code | Adapter wrote `0` where the harness has no usage field |
| `tokens.accounting_present` | expected_behavior | code | Usage object present and internally consistent (Claude usage vs result; Grok usage.json vs updates) |

## Skills

| id | class | kind | fail when |
|---|---|---|---|
| `skill.registry_unreadable` | hard_fail | code | SKILL.md path listed in context but file missing or no `name:` frontmatter |
| `skill.digest_drift` | expected_behavior | code | Content digest changed vs last snapshot (report; do not fail) |
| `skill.opaque_third_party` | expected_behavior | code | Activation path is outside `~/Code/skills` (flag for review, do not auto-edit) |
| `skill.activation_untracked` | expected_behavior | code | Session used a skill-like tool with no digestable SKILL.md |

## WorkGraph adjunct (only if `.pipeline/<slug>` ingested)

Reuse `workgraph-eval-score` rather than reimplementing its hard_fail set. This skill may *invoke* that binary on a run dir and attach the `workgraph-eval-result` object. It must not duplicate publication scoring.

| id | class | kind | fail when |
|---|---|---|---|
| `closeout.full_md_leaked` | hard_fail | code | Report HTML included `stages/**/full.md` |
| `closeout.eval_score_fail` | hard_fail | code | `workgraph-eval-score` `hard_pass=false` when that tool was requested |

## Opt-in LLM judges

Independent rubrics. Name them locally; do not transplant Arize YAML.

| id | class | kind | fail when |
|---|---|---|---|
| `judge.completeness` | expected_behavior | llm | User requests left pending/blocked/ignored without disclosure |
| `judge.grounding` | expected_behavior | llm | Claims contradict files the session actually read |
| `judge.tool_selection` | expected_behavior | llm | Wrong tool for the stated step |
| `judge.friction` | expected_behavior | llm | Assistant caused avoidable user re-prompting |

LLM rows must include `explanation` plus `evidence` spans (`source_path`, line range). They never set suite `hard_pass` unless the user promotes a judge to blocking.

## Suite verdict

`hard_pass` is true iff every `hard_fail` check is `pass` or `not_applicable`.
`feedback_outcome` may be a judge label. A judge `pass` with `hard_pass=false` is not a contradiction.
