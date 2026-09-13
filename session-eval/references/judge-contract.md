---
summary: Opt-in session-eval judge rubrics, approval/privacy, identity, and pass/fail/unknown rules.
read_when:
  - Implementing or evaluating opt-in completeness, grounding, tool-selection, or friction judges.
---

# Judge contract

Future contract. This document specifies intended opt-in judge behavior. It does not assert that any provider was called, that any rubric was scored, or that a runtime judge exists. No calls are authorized by the existence of this file.

Authority: [canonical store](../docs/index.md), [specification](../docs/specification.md), and [requirement map](../docs/requirement-map.md) (`skills-2ol.7` owns [SE-JUDGE-001](../docs/specification.md); provider boundary also [SE-PRIVACY-001](../docs/specification.md)). Named judge ids live in [check-catalog.md](check-catalog.md). Results use that catalog's evaluation-result object (same `run.checks[]` record as [SKILL.md](../SKILL.md)). This file owns rubric inputs, steps, pass/fail/unknown, evidence, approval, and identity. It does not own the normalized run record, the deterministic catalog, or receipt/HTML layout ([report-contract.md](report-contract.md)).

Rubric set identity: `session-eval-judge-rubrics/v1`. Independent wording. Do not copy Phoenix classification YAML or evaluator source. Historical category observations only: [Phoenix dossier](../docs/sources/phoenix/index.md), [competitors dossier](../docs/sources/competitors/index.md).

## Default: opt-out, zero calls

The default suite is deterministic `kind=code` checks. All four judges stay `not_applicable` with **zero provider calls** unless the user explicitly opts in and names:

- `judge.model` (model identity string)
- `judge.rubric_id` (one of the four ids below, or an explicit list)
- provider approval as defined in [Approval](#approval-and-privacy)

Opt-in execution of a named judge does **not** authorize arbitrary external disclosure, additional providers, prompt upload, or retries. Absent approval, treat the ask as incomplete: status `unknown`, `error.kind=internal`, still zero calls.

There is no retry, sampling, settle, or automatic re-call policy. One authorized attempt per (run snapshot, rubric_id, model, approval). Provider/transport/parse failure → `status=unknown`, never `pass`. Missing evidence → `status=unknown`, never `pass`.

## Shared result and identity

Each judge emits the [check-catalog.md](check-catalog.md) evaluation result (`id`, `status`, `kind=llm`, `class=expected_behavior`, `channel=behavior`, `observed`, `evidence[]`, `error`) plus the identity block below on the same object. Do not create a parallel judge-result schema.

```json
{
  "id": "judge.completeness",
  "class": "expected_behavior",
  "kind": "llm",
  "channel": "behavior",
  "status": "unknown",
  "observed": "provider_error",
  "evidence": [],
  "error": { "kind": "provider", "channel": "infra", "message": "provider returned an error" },
  "judge": {
    "rubric_id": "judge.completeness",
    "rubric_set": "session-eval-judge-rubrics/v1",
    "model": "named-model",
    "provider": "named-provider",
    "explanation": "Anchored explanation with evidence pointers only."
  }
}
```

| Identity field | Rule |
|---|---|
| `id` … `error` | Same [SKILL.md](../SKILL.md) `run.checks[]` object as deterministic checks. |
| `judge.rubric_id` | Catalog id (equals `id`). |
| `judge.rubric_set` | This contract's rubric-set identity. |
| `judge.model` / `judge.provider` | As approved. Never inferred from environment defaults. |
| Snapshot / parser | On each `evidence[]` item: `snapshot_hash` = `run.source_snapshot.sha256`, `parser_version` = `run.parser_version`. `run.parser` and `run.parser_version` are always present. Native run identity remains [SKILL.md](../SKILL.md); display names are not identity. |
| `judge.explanation` | Required on `pass` and `fail`. Anchored to `evidence[]` spans. No raw prompts, tool payloads, secrets, or terminal output. |
| `evidence[]` | [SKILL.md](../SKILL.md) pointers: `source_path`, `snapshot_hash`, `parser_version`, `event_range` `{start_line, end_line}`, `evidence_hash`. |

Judges never enter suite `hard_pass` unless the user promotes a named judge to blocking ([check-catalog.md](check-catalog.md)). A judge `pass` with `hard_pass=false` is not a contradiction.

Recommendations may consume judge rows through this same result contract; they are optional inputs, not a scheduling dependency ([requirement-map.md](../docs/requirement-map.md) `skills-2ol.8`).

## Approval and privacy

No provider disclosure without explicit scope and recipient approval ([SE-PRIVACY-001](../docs/specification.md)).

Required approval object (stored on the receipt, not a live credential):

```json
{
  "granted": true,
  "provider": "named-provider",
  "model": "named-model",
  "recipient": "named-endpoint-or-local-runtime",
  "scope": ["structural_claims", "evidence_pointers"],
  "purpose": ["judge.completeness"],
  "runs": ["harness:native-id"]
}
```

| Rule | Requirement |
|---|---|
| Closed by default | Missing, partial, or mismatched approval → zero calls. |
| Scope is a whitelist | Only listed field classes may leave the machine. `structural_claims` and `evidence_pointers` never include raw user/assistant text, tool arguments/results, secrets, or terminal output. |
| Secrets | Never in scope. Key/token matches are `tool.secret_pattern` pointers only. |
| Raw content | Raw session content is never a permitted scope class for this interface. Only explicitly authorized redacted semantic summaries/structural evidence and pointers may be supplied. Insufficient permitted evidence yields `unknown`, not a request to upload the transcript. |
| Source mutation | Forbidden. Judges are read-only over the snapshot. |
| Export | Receipts/HTML remain redacted regardless of what was approved for a provider call. |
| Calls | Documentation only here. Implementation later must refuse to call when approval is absent. |

Unknown events remain in private ingest memory/source. Exported artifacts carry pointers and redacted labels only.

## Common evaluation steps

For every authorized judge:

1. Confirm opt-in, `rubric_id`, model, and approval. If any is missing → `unknown`, zero calls.
2. Bind inputs listed for that rubric from the **current snapshot only**. Do not read the live worktree, current SKILL.md bytes, Git, Beads, or WAL to fill gaps.
3. If a required input is absent → `unknown`, zero calls (or no additional calls).
4. Perform at most one provider attempt with the approved scope.
5. Map the provider response onto `pass` / `fail` / `unknown` using that rubric. Unparseable or errored responses are `unknown`.
6. Attach `evidence[]` spans and an explanation that cites those spans. Do not embed payloads.

Source hashes and tool names alone cannot establish semantic completeness, grounding or friction. Inputs may include locally prepared, redacted semantic summaries tied to exact source spans, only when the approved scope includes them. If extracting the relevant request/claim/outcome would require unsupported inference or disallowed payload disclosure, return `unknown`; do not invent pre-classified markers to make a judge callable.

EOF is not terminal. Lifecycle and pairing follow [SKILL.md](../SKILL.md) and [check-catalog.md](check-catalog.md).

## Rubric: `judge.completeness`

**Question.** Were active user requests fulfilled, or explicitly disclosed as pending, blocked, failed, or ignored?

**Inputs** (structural, from the snapshot):

- ordered user-originated request markers (turn ids, `event_range`, role)
- subsequent assistant/tool outcome markers for each request
- explicit withdrawal/cancel markers, if any
- lifecycle state (`terminal` \| `live` \| `unknown`)
- disclosure markers (assistant stated that work remains pending/blocked/failed/ignored)

Do not require raw request text in the exported result. Under default approval, the provider sees redacted structural lists (request ids, outcome class, disclosure present/absent), not prompt bodies.

**Steps:**

1. Enumerate user-originated requests that were not withdrawn.
2. For each, classify from recorded outcomes: `fulfilled` \| `pending` \| `blocked` \| `failed` \| `ignored`.
3. For every non-`fulfilled` item, test whether a disclosure marker exists in a later assistant turn.
4. Ignore EOF. A `live` session may still have undisclosed pending items.

**Pass.** Every active request is `fulfilled`, or is non-fulfilled **and** disclosed.

**Fail.** At least one active request is pending, blocked, failed, or ignored **without** disclosure.

**Unknown.** Requests cannot be enumerated; outcome evidence is missing; approval/provider/parse error; or lifecycle is `unknown` and remaining work cannot be distinguished from an open stream.

**Evidence.** For each judged request: request span + outcome span + disclosure span or an explicit missing-disclosure pointer. `observed` tokens: `all_disclosed_or_fulfilled` \| `undisclosed_unmet_request` \| `requests_unenumerable` \| `provider_error`.

## Rubric: `judge.grounding`

**Question.** Do assistant claims about files, commands, or test results contradict evidence this session actually read or recorded?

**Inputs:**

- assistant claim markers about repository/files/commands/tests (turn ids and ranges)
- read/retrieve/tool-result markers the session actually recorded (tool names, paths as recorded strings, result `is_error`, evidence hashes)
- the same `run.source_snapshot` (not the live tree)

**Steps:**

1. Collect factual claims that can be checked against recorded reads or command outcomes.
2. Collect read/result evidence from the same snapshot.
3. Mark a claim `contradicted` when recorded evidence in that snapshot disagrees (file content the session read, command exit/`is_error`, test output the session recorded).
4. Mark a claim `unverified` when the session did not record supporting or contradicting evidence. Unverified is not fail.
5. Do not open files from the current checkout to prove or disprove a claim.

**Pass.** At least one claim is evaluable, every judged claim has supporting recorded evidence, and none is contradicted. Claims outside the selected scope are disclosed as unjudged.

**Fail.** At least one claim contradicts files or results the session actually read/recorded.

**Unknown.** Any selected claim lacks enough readable evidence to decide and no selected claim is contradicted; no claims can be isolated; or approval/provider/parse error. A wholly unverified claim set is never pass.

**Evidence.** Claim span + contradicting or supporting recorded span. `observed`: `no_contradiction` \| `claim_contradicted` \| `claims_unevaluable` \| `provider_error`.

This rubric does not judge patch correctness against a mutable worktree and is not a Git policy engine.

## Rubric: `judge.tool_selection`

**Question.** Was the selected tool appropriate for the stated step, given tools actually available in this session?

**Inputs:**

- stated-step markers (user or assistant step language as structural ids/ranges)
- selected tool name for that step
- inventory of tools actually offered/used in this snapshot (names only)
- pairing status of the selected call (paired / unpaired / unknown)

**Steps:**

1. Identify the stated next step and the tool that was selected for it.
2. Compare against the session's recorded tool inventory. Do not assume a global tool catalog.
3. Fail only when the selected tool is wrong for that step *and* a more appropriate tool from the recorded inventory was available (example: a dedicated file-read tool was available and the step was to read a file, but a general shell was selected instead).
4. Invocation argument correctness is out of scope here (not a transplanted third-party tool-invocation rubric).
5. Unpaired calls follow [check-catalog.md](check-catalog.md); this judge does not re-score `tool.unpaired`.

**Pass.** Selected tool is appropriate for the stated step among recorded available tools.

**Fail.** Wrong tool for the stated step while a better recorded available tool existed.

**Unknown.** Stated step missing, tool inventory missing, selection missing, or approval/provider/parse error.

**Evidence.** Step span + selected-tool span + (on fail) the unused better-tool inventory pointer. `observed`: `appropriate_selection` \| `wrong_tool_available_better` \| `selection_unevaluable` \| `provider_error`.

## Rubric: `judge.friction`

**Question.** Did the assistant cause avoidable user re-prompting?

**Inputs:**

- user turns after assistant turns (ids, ranges, structural relation: restatement / correction / unblock)
- preceding assistant behavior markers (ignored instruction, missing disclosure, asked the user to repeat known context)
- single-turn sessions (no follow-up user turn)

**Steps:**

1. Identify user follow-ups that restate, correct, or unblock the assistant.
2. Attribute a follow-up as avoidable when recorded assistant behavior caused it (ignored a stated constraint, omitted a required disclosure, asked for information already in the snapshot).
3. Do not count new user requirements, genuine plan changes, or harness UI chrome as friction.
4. A single-turn session with no follow-up is not fail.

**Pass.** No avoidable user re-prompting attributable to the assistant.

**Fail.** At least one avoidable re-prompt caused by the assistant.

**Unknown.** Follow-ups exist but cause cannot be attributed; user side missing; approval/provider/parse error.

**Evidence.** User follow-up span + preceding assistant span. `observed`: `no_avoidable_reprompt` \| `avoidable_reprompt` \| `friction_unevaluable` \| `provider_error`.

## Future acceptance scenarios

Documentation-level only. None is claimed executed. No scenario here is permission to call a provider.

| Scenario | Expected judge outcome |
|---|---|
| Default run / explicit opt-out | All four rows `not_applicable`; zero provider calls; no approval object required |
| User asks for judges but omits provider, model, recipient, or scope | `unknown`, `error.kind=internal`; zero calls |
| Approval present, completeness authorized, snapshot has an undisclosed unmet request | After one authorized attempt: `judge.completeness` `fail` with request/disclosure evidence spans |
| Approval present, required read evidence missing for a grounding claim | `judge.grounding` `unknown`; never `pass` |
| Provider returns an error or unparseable body | `unknown`, `error.kind=provider`; no retry; never `pass` |
| Opt-in for completeness only | Other three judges remain `not_applicable`; no calls for them |
| Judge `pass` on a run whose deterministic `hard_pass` is false | Not a contradiction; judge does not flip `hard_pass` unless promoted |

## Non-goals

- Actual provider calls in this tranche
- Retries, sampling, admission control, or online settle loops
- Automatic skill edits or prompt uploads
- A second evaluation-result schema
- Using the live checkout as grounding evidence
