# Codex–Fable Review Synthesis: Voice-Preserving Humanizer

**Status:** Final synthesis of dual-approved plan  
**Plan:** `docs/plans/voice-preserving-humanizer.md`  
**Final plan SHA-256:** `bc26bca227c496e90e2d219de096d88b1ad6f3a7e0a77120f998cec0b6d62dbe`  
**Substantive dual-acceptance SHA-256:** `640ba67f7993cda9c52d9f987127e8fc5a8566818269c6c5b681bb076e17a3fb`  
**Date:** 2026-07-15

## 1. Purpose

This document synthesizes the independent Codex and Fable review artifacts into one implementation-facing ledger.

It does **not** replace, paraphrase away, or mutate the raw reviewer outputs. The raw artifacts remain immutable evidence. The approved plan remains the normative product specification. This synthesis explains:

- where the reviewers agreed;
- which risks each reviewer uniquely exposed;
- how disagreements were adjudicated;
- which exact contracts entered the approved plan;
- which choices remain intentionally non-blocking;
- how implementation work must trace back to the accepted review record.

## 2. Canonical source order

If sources appear to conflict, use this order:

1. `docs/plans/voice-preserving-humanizer.md` — normative requirements.
2. This synthesis — rationale, traceability, and implementation interpretation.
3. Terminal Codex and Fable artifacts — independent review evidence.
4. Earlier review artifacts — historical context for repaired findings.
5. Raw traces and prompts — forensic execution record.

The synthesis cannot weaken a plan requirement. A raw reviewer suggestion that was not incorporated into the dual-approved plan is not independently normative.

## 3. Terminal review artifacts

| Role | Ask lane | Model | Artifact | SHA-256 | Verdict |
|---|---|---|---|---|---|
| Technical reviewer | `codex` | `gpt-5.6-sol` | `.pipeline/voice-preserving-humanizer/review/codex-dual-r5/artifact.md` | `d45ab84186f68a32858082d36fe7f7ce05a69598152875d0901ebd21e9793581` | `ACCEPT` |
| Adversarial reviewer | `claude` | `claude-fable-5` | `.pipeline/voice-preserving-humanizer/review/fable-dual-r5/artifact.md` | `c023dce3c254332f227c8918e06403a4722ed3dd3a85fe951c3e5b0bd4781e83` | `ACCEPT` |
| Metadata ratifier | `codex` | `gpt-5.6-sol` | `.pipeline/voice-preserving-humanizer/review/codex-final-ratification/artifact.md` | `b04623f06a51b7a69fa78741c1c91f25224084e63e0daf0ad0e45c77a8254fdd` | `ACCEPT` |
| Metadata ratifier | `claude` | `claude-fable-5` | `.pipeline/voice-preserving-humanizer/review/fable-final-ratification/artifact.md` | `f2de9afc2bd0274077c3a3db35989b9bd40c7366797e489d3a06692697ed951b` | `ACCEPT` |

The Fable reviewer used the Claude Ask provider lane with the explicit model override `claude-fable-5`. It was not run through Codex.

## 4. Reviewer roles

### 4.1 Codex

Codex acted as the technical consistency and implementability reviewer. Its recurring concerns were:

- complete machine contracts;
- deterministic ownership of offsets, hashes, state, and approvals;
- unambiguous failure and review codes;
- testable acceptance rules;
- consistency between evaluation denominators and thresholds;
- builder choices that could create incompatible implementations.

Its terminal acceptance specifically confirmed:

- deterministic precedence between `LOW_CONFIDENCE_PROPOSAL` and `MODEL_REQUESTED_REVIEW`;
- complete subject and evidence binding;
- coverage of multi-edit, multi-sample, multi-pattern, touching-region, and document-level findings;
- no remaining concrete acceptance bypass or undefined v1 choice.

### 4.2 Fable

Fable acted as the adversarial falsification reviewer. Its recurring concerns were:

- trust inversions in model-supplied offsets, statistics, and evidence;
- silent protected-span or entity drift;
- privacy leakage through unresolved backend routing;
- evaluation designs that could pass identity output, memorization, or weak baselines;
- review approvals that could resolve unseen findings;
- apparently deterministic mechanisms whose literal specification was non-injective or incomplete.

Its terminal acceptance specifically confirmed:

- coalescing of same-code/same-subject evidence;
- canonical evidence-bound finding IDs;
- approval display and binding of the complete evidence set;
- deterministic model-declared-review handling;
- no remaining path to acceptance past an undisplayed finding, unconsented backend, or deterministic failure.

## 5. Synthesis method

The convergence process did not average reviewer prose or select whichever verdict was more convenient. It used the following rule:

1. Freeze one plan hash.
2. Dispatch independent Codex and Fable reviews.
3. Normalize findings into concrete failure scenarios.
4. Merge compatible findings.
5. Send actual disagreements to Codex for bounded adjudication.
6. Revise the plan, not the raw artifacts.
7. Freeze a new hash and rerun both reviewers.
8. Treat timeout, malformed output, or missing artifact as no verdict.
9. Stop only when both reviewers accepted the same substantive hash.
10. Ratify the metadata-only final file separately.

## 6. Converged issue ledger

| ID | Concern | Principal source | Final disposition | Plan location | State |
|---|---|---|---|---|---|
| DR-01 | Model-generated byte ranges and hashes | Fable | Model emits anchor-based `edit-proposal.v1`; orchestrator alone resolves ranges and digests | §5.4, §7.3 | Resolved |
| DR-02 | Missing accepted-output authority | Fable | `scripts/humanize.py` is the sole `prepare`/`resolve`/`finalize` state machine and output authority | §5.4, §7 | Resolved |
| DR-03 | Subjective AI-residue claims | Both | Stable pattern IDs, deterministic countable matchers, corpus-relative evidence, contextual verifier decisions, durable per-edit audits | §5.4, §7.2 | Resolved |
| DR-04 | Scalar or unstable voice scoring | Fable | Independent corpus-envelope warnings with sample-sufficiency rules; no composite voice score | §7.4, §9.5 | Resolved |
| DR-05 | Rewriting without a valid profile | Fable | Revision modes fail with `PROFILE_REQUIRED_FOR_REVISION`; no-profile operation is diagnose-only | §5.1, §5.2 | Resolved |
| DR-06 | Protected-span fragmentation | Both | Total extractor order, independent detection on original source, containment expansion, crossing-overlap rejection | §7.1 | Resolved |
| DR-07 | Non-deterministic or duplicate sentinels | Both | Source-derived per-index sentinel hashes, full-set collision regeneration, replayable prepared state | §7.1 | Resolved |
| DR-08 | Protected-sentinel reordering | Codex | Every sentinel retains relative source order; v1 rejects reordering with `SENTINEL_ORDER_CHANGED` | §7.1 | Resolved |
| DR-09 | Silent token/entity drift | Fable | Differential scans plus conservative entity hierarchy and fail-closed review codes | §7.1, §9.3 | Resolved |
| DR-10 | Weak or gameable evaluation | Both | Strong prompt baseline, stock baselines, profile ablation, exactly ten blinded groups, explicit preferences, fixed gates | §9 | Resolved |
| DR-11 | Profile memorization | Fable | Six-token post-restoration scan over maximal contiguous changed regions, including touching edits | §9.3 | Resolved |
| DR-12 | Missing semantic-verification isolation | Fable | Fresh-context semantic verifier required in v1; second backend only with separate consent | §7.4, §10 | Resolved |
| DR-13 | Raw data sent through unresolved routes | Both | Exact backend resolution and consent before profile, revision, and verification handoffs; dynamic routing limited to sanitized data | §6.3, §10 | Resolved |
| DR-14 | Generic profile maxims becoming voice constraints | Both | Acceptable-alternative genericity test, two-sample evidence, counterevidence, user confirmation, fail-closed demotion | §6.1, §6.2 | Resolved |
| DR-15 | Elevated vocabulary protected indiscriminately | Both | High-register protection is corpus/glossary-relative and tested against ornamental inflation | §5.2, §11 | Resolved |
| DR-16 | Ungoverned `review_required` transition | Fable | User-only `voice-review-approval.v1`; exact source/candidate/finding binding; replay rejection | §5.4 | Resolved |
| DR-17 | Multi-edit finding ownership | Codex | Deterministic finding IDs and complete ordered `subject_edit_ids`; no arbitrary owner edit | §5.4, §9.3 | Resolved |
| DR-18 | Evidence-ID collision and unseen approval | Fable | Same-code/same-subject coalescing plus sorted evidence IDs in canonical finding hash and approval display | §5.4, §9.3 | Resolved |
| DR-19 | Model-declared review at high confidence | Codex | Total precedence: low confidence → `LOW_CONFIDENCE_PROPOSAL`; otherwise model flag → `MODEL_REQUESTED_REVIEW` | §5.4 | Resolved |
| DR-20 | Final metadata changed accepted bytes | Both | Substantive hash accepted first; final metadata-only hash independently ratified | Appendix A and ratification artifacts | Resolved |

## 7. Explicit conflict resolutions

### 7.1 Semantic verifier independence

- Strong form considered: always use a second model/backend.
- Final decision: fresh context is mandatory; a different backend is optional and requires separate configuration and consent.
- Reason: fresh-context isolation addresses reviser contamination without forcing additional disclosure of private text.

### 7.2 Genericity testing

- Fable proposal: test profile hypotheses against a matched non-author or generic sample.
- Codex objection: that would introduce an unplanned classifier corpus and additional v1 architecture.
- Final decision: require a contrast between two independently acceptable realizations. If negating the hypothesis necessarily means bad writing, the hypothesis is generic and becomes `descriptive_only`.

### 7.3 Memorization threshold

- Initial Codex preference: eight tokens to reduce technical false positives.
- Fable preference: six tokens as the safer privacy boundary.
- Final decision: six normalized tokens because the result is review, not automatic rejection; technical false positives are handled through exact exclusions and user approval.

### 7.4 Dynamic-route consent

- Permissive option considered: explicit consent to a changing backend for raw text.
- Final decision: raw corpus, source, excerpts, and verifier passages require immediate exact backend resolution. Dynamic routing is limited to fixtures, hash-approved redactions, and overlap-scanned profile summaries without excerpts.

### 7.5 High-register protection

- Overbroad option rejected: preserve elevated or rare vocabulary categorically.
- Final decision: protect corpus- or glossary-attested diction and aliases; source-only high-register language still requires contextual evidence of precision.

## 8. Jointly approved implementation contract

Implementation must treat the following as non-negotiable:

1. The active model proposes edits; it does not own document assembly.
2. Deterministic code owns protection, targeting, offsets, hashes, evidence recomputation, restoration, verification gates, audits, and final output.
3. Every accepted output is reproducible from recorded handoff responses.
4. Every raw-text handoff is consented against its actual resolved backend.
5. No semantic model can override a deterministic failure.
6. Every review state has a deterministic finding, complete evidence set, exact subject, and user-only resolution path.
7. Evaluation cannot pass through identity output, memorization, weak comparison, or hidden aggregation.
8. High-register preservation follows author evidence rather than generic simplicity or rarity rules.
9. Raw evaluation output remains exactly as produced and outside Git.
10. Upstream-inspired code is copied only after provenance, license, static, and semantic review.

## 9. Non-blocking choices retained for implementation

Fable explicitly classified these as non-blocking because every permitted choice remains fail-closed:

- exact internal field-name serialization beyond the canonical JSON requirements;
- token/entity finding subject granularity;
- consent-scope vocabulary for diagnose-only runs;
- concrete `run_id` generation;
- genre-specific profile subprofiles;
- routine value of a separately consented second verifier backend;
- optional local embeddings;
- optional interactive diff view;
- profile-schema migration policy;
- future harness support for enforceable ephemeral transcripts.

An implementation decision for these items must be documented, but it does not reopen the approved plan unless it weakens an accepted gate.

## 10. Implementation traceability rule

Every implementation task, test, and review finding should cite:

- one plan section;
- one synthesis ledger ID (`DR-01` through `DR-20`);
- the relevant schema or rejection/review code;
- the test that proves the requirement.

If implementation exposes a contradiction:

1. stop the affected task;
2. record the concrete failure path;
3. do not weaken the gate locally;
4. amend the plan through a new frozen-hash Codex–Fable convergence loop.

## 11. Acceptance state

### Substantive plan

- Hash: `640ba67f7993cda9c52d9f987127e8fc5a8566818269c6c5b681bb076e17a3fb`
- Codex: `ACCEPT`
- Fable: `ACCEPT`

### Final metadata plan

- Hash: `bc26bca227c496e90e2d219de096d88b1ad6f3a7e0a77120f998cec0b6d62dbe`
- Codex ratification: `ACCEPT`
- Fable ratification: `ACCEPT`

### Unresolved blockers

None.

---

## Appendix A: Review summary

Codex and Fable did not merely agree on a verdict. Their final artifacts independently confirmed the same safety properties from different directions:

- Codex confirmed implementability, total review-state coverage, and exact subject/evidence binding.
- Fable confirmed resistance to evidence collision, unseen approval, unconsented routing, and deterministic-gate bypass.

The result is complementary rather than redundant assurance.

## Appendix B: Critical pass

The strongest criticism of this synthesis is that a polished agreement matrix can create false confidence. Two models accepting a detailed plan does not prove that the implementation will satisfy it.

Countermeasures:

- raw artifacts remain available;
- every synthesized claim points to a plan section;
- implementation must produce mechanical tests and raw outputs;
- acceptance gates remain fail-closed;
- implementation deviations trigger a new review loop rather than informal reinterpretation.

## Appendix C: Assumptions and actions

### Assumptions

- The approved plan remains the normative source.
- Raw Ask artifacts and traces remain immutable.
- Implementation has not yet begun.
- No commit or push is implied by this synthesis.

### Actions taken

- Preserved separate Codex and Fable artifacts.
- Verified terminal artifact identities and hashes.
- Separated technical-review and adversarial-review contributions.
- Recorded agreement, unique findings, conflict resolutions, and implementation rules.
- Created a machine-readable companion ledger under `.pipeline`.

### Next action

Obtain Brooks's implementation authorization, then scaffold the skill and require every implementation task to cite its plan section and synthesis ledger ID.
