# Gated report mode for DeepSearch CLI

Use this reference when the user wants more than a quick source-led briefing: e.g. "gated report", "auditable", "claim-level", "validate", "rich enough", "fix trust", "publication quality", "high confidence", or asks why a prior synthesis was not sufficiently grounded.

## Research-backed quality model

A gated DeepSearch report should optimize for four auditable properties:

1. Provenance coverage: every factual claim in the final report has a traceable path to source/evidence ledgers.
2. Provenance soundness: cited evidence actually supports the specific claim, not just the general topic.
3. Contradiction transparency: conflicting or counter-evidence is surfaced and resolved, not smoothed over.
4. Audit effort reduction: a reviewer can verify claims from ledgers faster than redoing the research.

Operational implications:

- Use a directed source -> evidence -> claim -> report-marker graph, even if implemented as JSONL ledgers.
- Treat search snippets as discovery only. Evidence must come from fetched content or a concrete source artifact.
- Split bundled prose into atomic factual claims, especially numbers, dates, comparisons, causality, and recommendations.
- Keep inference separate from observation; mark speculation as speculation rather than factual.
- Run verification during synthesis, not only after the final prose is written.
- Use release gates that block publication when unsupported segments, unresolved contradictions, temporal blockers, unknown claim markers, or citation failures remain.

## Mode selection

Choose the light P1 briefing mode only when the user asks for an ordinary answer or a slash-command smoke test.

Choose gated report mode when any of these are true:

- The user asks whether output is "rich enough" beyond a smoke test.
- The task mentions gated, auditable, claim-level, citations, validation, verification, provenance, confidence, report bundle, publication, or artifact.
- The topic is high-stakes/current/contested, or the answer will be reused outside the chat.
- The previous answer was criticized for trusting synthesis too much.

## Required gated workflow

1. Initialize a run directory with `init-run`.
2. Plan lanes and retrieve/fetch sources with P1 commands.
3. Register every source used for a final claim.
4. Record exact evidence quotes/paraphrases with locators; avoid recording search snippets as evidence.
5. Record atomic claims with `record-claim`, linking both `cited_source_ids` and `evidence_ids`.
6. Draft `report.candidate.md` so every factual sentence is either exactly a recorded claim or split into recorded claims. Put `[claim:<claim_id>]` on the same line as the claim text.
7. Run P2 checks:
   - `detect-contradictions` for known conflicts, with unresolved conflicts blocking publication.
   - `red-team-node` for important claims where counter-evidence exists or should be sought.
   - `temporal-diff` for time-sensitive claims.
8. Run delivery gates:
   - `verify-claims --strict`
   - `verify-citations --strict --no-network`
   - `validate-report`
   - `render-report-bundle --strict`
9. Publish only if `render-report-bundle --strict` returns pass and `report.md` exists. If it fails, report the blocking JSON fields and leave `report.candidate.md` as a candidate.

## Minimum final answer for gated mode

Report:

- run directory
- report path, or candidate path if blocked
- counts: sources, evidence rows, claims, unsupported factual claims
- gate statuses for claim, citation, report, and bundle validation
- unresolved contradiction/challenge/temporal blockers, if any
- whether any non-DeepSearch tools contributed evidence

## Acceptance bar

A gated run is acceptable only when:

- 100% of factual report claims have claim markers.
- `unsupported_segments` is empty.
- `unmarked_claim_ids` is empty.
- `unknown_claim_markers` is empty.
- `missing_claim_ids` is empty.
- strict claim verification passes, or failures are explicitly reported as blockers.
- strict no-network citation verification passes.
- `render-report-bundle --strict` writes `report.md`.

## Competitive reference map

The advanced gated-report features are not greenfield; the reference corpus already contains partial implementations/specs:

- Auto-extract factual claims from prose: `lingzhi227__agent-research-skills/skills/citation-management/scripts/harvest_citations.py` detects uncited factual sentences via `CLAIM_PATTERNS` and emits search queries.
- Auto-split bundled claims: mostly spec-level in `standardhuman__deep-research-skill` claim taxonomy / evidence ledger and in DeepSearch's atomic-claim ledger rules; still needs a local deterministic/procedural splitter.
- Auto-link claims to evidence: implemented deterministically in `199-biotechnologies__claude-deep-research-skill` via source/evidence/claim JSONL with `cited_source_ids` and `evidence_ids`.
- Semantic entailment/NLI: not present as a strong local implementation in the audited corpus; closest are deterministic lexical/number/year/entity support scoring and PaperQA-style evidence retrieval/answer grounding. True NLI remains a model/embedding-layer addition.
- Actively retrieve counter-evidence: spec/process-level in `tonyazhuuki__deep-research-skill` iterative deepening on CONTESTED claims, domain stress tests, fact-checker/domain reviewer lanes; DeepSearch has `red_team_node` to record counter-evidence once found.
- Compute provenance soundness scores: `199-biotechnologies` computes claim-support scores; the AAR paper names provenance soundness formally. A full local provenance-soundness metric would generalize support scoring over source -> evidence -> claim edges.

So helper commands are trivial, and several advanced pieces are copy/adapt work from references, not invention. The remaining hard part is productizing them into a reliable local pipeline with deterministic acceptance gates.
