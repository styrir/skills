---
summary: Evaluate every session-eval task against its canonical requirements.
read_when:
  - Starting implementation, reviewing a change or closing a session-eval Bead.
---
# Task conformance

Applies to SE-DOC-001 and SE-VERIFY-001. Read [specification](specification.md), [decisions](decisions.md) and the task's rows in [requirement map](requirement-map.md).

This document defines the evidence shape and the skills-2ol.9 runner. It is not a populated passing receipt. Missing evidence is `not_evaluated` or `unknown`, never pass. Parent integrates sibling modules, executes the runner, and performs the offline-browser and authorized-judge observations the runner cannot claim.

## Before implementation

Record the task ID, affected requirement IDs, canonical Git revision, applicable contract paths and acceptance scenarios in the Bead. If contracts are uncommitted, record their SHA-256 digests as well. Read complete governing sections, not only task summaries. Identify historical evidence assumptions and privacy boundaries. A contradictory instruction is a blocker for that behavior until reconciled, not authority to narrow scope.

## During implementation

For a necessary deviation, name the requirement, source evidence, proposed decision and acceptance change. Obtain approval for new scope or consequential actions where required; update the canonical decision, specification, detailed contracts and Bead together. Do not edit historical source snapshots. A code change is not a decision record.

## End-to-end runner (skills-2ol.9)

Pinned interface (parallel-wave contract `conformance`):

```bash
python3 session-eval/scripts/conformance.py --out OUT [--cli PATH] [--judge-evidence RECEIPT]
```

The runner:

1. Writes a synthetic, reproducible five-harness corpus under `OUT/fixtures/corpus/` (durable; not a disappearing tempfile).
2. Invokes the **actual** shared CLI pinned as `python3 session-eval/scripts/session_eval.py --path PATH --harness HARNESS --since all --out OUT` plus optional `--skill-root`, `--first-party-root`, `--history-root`, `--baseline`, `--atif`, and `--workgraph{,-manifest,-allowlist,-bin}`.
3. Never passes `--judge-provider`, `--judge-model`, `--judge-recipient`, `--judge-auth-env`, or `--judge-rubric`. It does not request or invoke providers.
4. Accepts separately produced approved judge evidence only via `--judge-evidence`. Absent that proof, SE-JUDGE-001 stays `unknown`/`blocked` and must not become `pass`.
5. Writes `OUT/evidence/requirements.json` and `requirements.md` with commands, input/output SHA-256, canonical Git revision, expected vs observed, status, and explicit limits.
6. Does not claim epic PASS. Closeout remains Main/CLOSEOUT after independent review.

Default `--cli` is `session-eval/scripts/session_eval.py` beside the runner. A missing CLI is an explicit missing-implementation failure, not a stubbed schema.

### Corpus cases (all synthetic)

| Case | Scenario name | Intent |
|---|---|---|
| Five harnesses + unknown field + malformed lines | `five_harness` | SE-INGEST-001 / SE-PORT-001 |
| Empty directory | `empty` | empty coverage, `hard_pass=false` |
| Malformed JSONL mixed with valid | `malformed` | parse counted; infra not behavioral pass |
| Nested parent/child agents | `nested` | SE-INGEST-002 lineage |
| Ended unpaired / live unpaired / EOF unpaired | `ended_unpaired`, `live_unpaired`, `eof_unpaired` | pairing vs lifecycle |
| Pi without usage | `usage_absent` | unknown, never zero |
| Secret + markup payloads | `secret_markup` | SE-PRIVACY-001 |
| Skill unchanged / edited / mention / missing | `skill_unchanged`, `skill_edited`, `skill_mention`, `skill_missing` | SE-SKILL-001 four controls |
| Four-call loop / ordinary error | `loop_fail`, `ordinary_error` | SE-CHECK-001 |
| Contradicted pytest claim / completion with no acceptance set | `claim_contradict`, `claim_completion` | SE-CHECK-002 |
| Recurring first-party unpaired | `recurring_unpaired` | SE-CORRECT-001 actionable positive control |
| Missing requested harness | `missing_harness` | coverage gap |
| Repeat ingest / changed bytes | `repeat_ingest`, `changed_ingest` | SE-EVIDENCE-001 |
| `--atif` on Claude+Grok population | `atif_export` | SE-EXPORT-001 |
| Existing `workgraph-eval-score` on red-baseline | `workgraph` | SE-WORKGRAPH-001 |
| Baseline/candidate | `trend_revisions` | SE-TREND-001 |

Finding `evidence.snapshot_hash` must equal aggregate `run.source_snapshot.sha256`. File bytes hashes belong only on `source_snapshot.files[].sha256`. `evidence_hash` is the exact frozen span.

### Shared CLI contract the runner expects

JSON stdout from `session_eval.py`: `{receipt:<immutable path>, report:<html path>, hard_pass, infra_ok, coverage, ...}`. Receipt schema `styrir-session-eval/v0`, catalog `session-eval-check-catalog/v1`. Normal default: no provider calls. Report/receipt generated for normal/empty/malformed. Missing implementation dependency fails explicitly.

WorkGraph flags, when used, point at the real binary `/Users/brooks/Code/agent-ops/bin/workgraph-eval-score` and `tests/workgraph-eval/fixtures/red-baseline` plus acceptance-manifest and mutation-allowlist. The runner does not reimplement scoring, launch runs, or ingest `stages/**/full.md`.

## Verification record

Store task-scoped execution evidence under `.styrir/runs/<run-id>/` in the skills checkout and link it from the Bead. Keep durable curated review findings here only when they are useful beyond that execution. Never make the session transcript the only evidence location. The runner's `--out` tree is the machine-readable form of that record.

A conformance record contains:

- Task ID, canonical revision and any uncommitted contract digests.
- Evaluated requirement IDs and exact contract section references.
- Commands/scenarios actually executed, input identity, output/artifact paths and digests.
- For each requirement: expected behavior, observed behavior, result (`pass`, `fail`, `not_evaluated`, or justified `not_applicable`) and limitations. Judge-absent rows use `unknown` and must not be rewritten to `pass`.
- Approval references for optional provider use; no credentials or raw sensitive payloads.
- Deviations and links to the decisions resolving them.

| Requirement | Expected behavior | Observed evidence | Result |
|---|---|---|---|
| Applicable stable ID | Contract section and scenario | Actual command/output or artifact, with identity | Explicit result and limitation |

This is a shape definition, not a populated passing receipt. Missing evidence is `not_evaluated`, never pass. Optional invocation can be `not_applicable` when not selected, but an unimplemented Required opt-in feature cannot be waived by switching it off. Tests against mock forwarding or source wording cannot prove runtime behavior.

## Coverage matrix: runner vs parent

| Requirement | Runner assertions | Parent must still observe |
|---|---|---|
| SE-DOC-001 | Spec/index/decisions/map present; all Required+Optional IDs in the specification | Fresh-reader walk; conflicting-instruction blocking |
| SE-PORT-001 | Ordinary `python3` invocation of shared CLI; missing CLI fails explicitly | None beyond integration of `session_eval.py` |
| SE-INGEST-001 | Five harnesses, malformed counted, missing harness coverage gap | None |
| SE-INGEST-002 | Nested lineage; ended unpaired fail; live/EOF not terminal-inferred | None |
| SE-EVIDENCE-001 | Repeat snapshot identity; changed bytes new snapshot; finding `snapshot_hash` aggregate | None |
| SE-PRIVACY-001 | Synthetic secret/markup absent from receipt/HTML/ATIF | Approval binding on a real provider; visual XSS check |
| SE-USAGE-001 | Absent usage stays unknown; repeated Codex aggregates not doubled | None |
| SE-CHECK-001 | Parse infra fail; loop fail; ordinary error expected_behavior; empty `hard_pass=false` | None |
| SE-CHECK-002 | Contradicted command `fail`; completion without acceptance set `unknown` | None |
| SE-JUDGE-001 | Default zero provider calls; `--judge-evidence` consumed if supplied; else unknown | Authorized live judgment under interactive approval |
| SE-SKILL-001 | Unchanged, edited, mention, and missing as separate controls | None |
| SE-TREND-001 | Comparison object present; incompatible cohort cannot silently delta | None |
| SE-REPORT-001 | `receipt.json` + `report.html` exist; required section ids present | **Open the real report offline** (normal/empty/malformed/markup-secret). Do not treat HTML grep as visual PASS. |
| SE-CORRECT-001 | Recurring first-party unpaired yields actionable proposal; empty/unmeasurable yields a limitation; sources unchanged | None |
| SE-VERIFY-001 | Enumerates every Required row with commands/hashes/revision | Epic audit after sibling integration; CLOSEOUT |
| SE-WORKGRAPH-001 | Real `workgraph-eval-score` on known-failing red-baseline; failure remains visible | None |
| SE-EXPORT-001 | `--atif` documents for Claude/Grok; no secret in ATIF | Optional Harbor Pydantic pin check |

Provisional browser fixtures under `skills/.styrir/runs/session-eval-implementation/skills-2ol.3/browser-initial/` are not final PASS. Consume final verified evidence only.

## Documentation verification

For a documentation-only tranche:

1. Verify every maintained relative document link resolves, including anchors.
2. Parse JSON examples and provenance manifests.
3. Compare each historical snapshot's bytes/digest with the original; report missing originals, do not fabricate verification.
4. Compare the requirement set to the ownership map and actual Bead fields; inspect dependencies for cycles and stale launch instructions.
5. Check that every Required capability has observable acceptance and a concrete owner.
6. Run repository-required whitespace checks on the scoped changes.
7. Walk a real task as a fresh reader. Record documentation readiness separately from runtime execution.

These checks establish documentation integrity only. A correct index or catalog does not prove an evaluator works.

## Runtime verification and closeout

Exercise the actual changed paths. For the engine, use local authorized/synthetic samples that cover meaningful edge cases; do not create files with live secrets. For HTML, open the real generated report and inspect normal/empty/error states offline. For a bug fix, demonstrate the original failure no longer occurs. A missing fixture is a proof gap; it is not a reason to report the harness as supported.

Close a task only when all its applicable requirements are evidenced. For an incomplete task, preserve the evidence and exact outstanding criteria in Beads. Update related contracts in the same tranche, and follow the skills repository Git+Dolt publication policy. Do not close operator mirrors merely because a documentation phase ended. End-to-end closure evaluates every Required row; optional export and deferred research do not gate core completion. User direction for this epic asked the skills-2ol.9 runner to **include** both Optional rows (ATIF implemented; WorkGraph adjunct implemented) as executable scenarios; that inclusion does not make them core blockers.

Parent-runnable command (not executed by this build):

```bash
python3 session-eval/scripts/conformance.py \
  --out .styrir/runs/session-eval-implementation/skills-2ol.9/conformance \
  --cli session-eval/scripts/session_eval.py
```

Add `--judge-evidence PATH` only when a separately produced approved judge receipt exists.
