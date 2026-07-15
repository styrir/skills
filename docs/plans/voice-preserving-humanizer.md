# Voice-Preserving Humanizer: Product and Implementation Plan

**Status:** Approved by Codex and Fable; awaiting Brooks's implementation authorization  
**Owner:** Brooks / Styrir personal skill library  
**Target source repository:** `/Users/brooks/Code/skills`  
**Proposed skill name:** `voice-preserving-humanizer`  
**Document date:** 2026-07-15

## 1. Decision

Build a Hermes-native, prompt-led skill for revising AI-assisted or over-smoothed prose without erasing the author's actual voice.

The skill will use `dannwaneri/voice-humanizer` as its primary conceptual base, add a constrained form of Harshaneel's HyPerAlign-inspired voice-hypothesis extraction, reuse or independently implement Untell-style protected-span handling, and treat Blader's AI-pattern catalog as advisory evidence rather than universal law.

Do not install or chain the candidate repositories as runtime dependencies. Reimplement the selected mechanisms in a small, inspectable local skill after recording attribution and license provenance.

The default optimization order is:

1. Factual and semantic fidelity.
2. Fidelity to the author's demonstrated voice.
3. Preservation of precise, high-register diction.
4. Removal of concrete AI-writing artifacts.
5. Readability where it does not conflict with the first four priorities.
6. Detector response only as optional diagnostic evidence, never as the product objective.

## 2. Problem

Most “humanizers” optimize for one of three weaker goals:

- generic naturalness;
- detector evasion;
- semantic similarity after broad paraphrase.

Those goals frequently flatten the author’s register, regularize rhythm, replace precise vocabulary with simpler synonyms, remove authentic punctuation habits, and add invented personality. Translation-chain systems introduce additional semantic and stylistic drift while sending text through several external services.

The desired product must preserve:

- sentence rhythm and sentence-length distribution;
- vocabulary level and domain-specific diction;
- rhetorical structures and recurring verbal habits;
- punctuation preferences;
- paragraph shape and transition style;
- uncertainty, modality, qualifications, and argumentative structure;
- citations, quotations, named entities, numbers, code, URLs, and technical terms;
- unusual but authentic constructions found in the author corpus.

## 3. Product principles

### 3.1 The author corpus is sovereign

A pattern demonstrated in the author corpus is not an AI tell merely because a generic checklist says it is. The skill may flag the pattern for review but must not remove it automatically.

### 3.2 High-register language is not a defect

The skill must not simplify a term solely because it is formal, uncommon, Latinate, technical, or syntactically demanding. It may suggest a replacement only when the term is inaccurate, redundant, or unsupported by the intended meaning.

### 3.3 Edit surgically

Do not rewrite a complete document when only several passages exhibit AI residue. Preserve unaffected prose byte-for-byte whenever practical.

### 3.4 Never fabricate humanity

The skill must not invent:

- personal experiences;
- autobiographical details;
- sensory observations;
- opinions not present in the source;
- quotations;
- named people, places, or events;
- evidence or citations;
- rhetorical questions or jokes merely to simulate personality.

### 3.5 Generic style rules are rebuttable

No universal ban on em dashes, semicolons, anaphora, parallelism, long sentences, formal transitions, passive voice, or any vocabulary item. A rule may apply only when the source and corpus show that the construction is anomalous, imprecise, repetitive, or externally imposed.

### 3.6 The skill is local; the model may not be

The skill files and deterministic checks run locally. Text sent to the active Hermes, Claude, Codex, or VibeProxy model follows that provider’s data path. Documentation must not describe the workflow as private or local-only unless inference is actually local.

## 4. Candidate assessment and provenance

The following repositories were inspected in quarantine on 2026-07-15.

| Candidate | Inspected commit | Use in this plan | Ruling |
|---|---|---|---|
| [`dannwaneri/voice-humanizer`](https://github.com/dannwaneri/voice-humanizer) | `1b24c4ded4237ea5bd6135f131976b61f74bb015` | Corpus-first voice review and voice-drift precedence | Primary conceptual base |
| [`harshaneel/humanize`](https://github.com/harshaneel/humanize) | `4ec797314537ec9c2105f276d4561d240a0390ba` | Hypothesis extraction from writing samples | Borrow selected mechanism only |
| [`ssamba1/untell`](https://github.com/ssamba1/untell) | `64d7fdc5a3ff9bceb0960fb24661f207bf6148e9` | Protected-span extraction/restoration and semantic gate concepts | Borrow selected mechanism only |
| [`blader/humanizer`](https://github.com/blader/humanizer) | `1b48564898e999219882660237fde01bf4843a0f` | AI-pattern taxonomy and diagnostic prompts | Advisory reference only |
| [`rudra496/StealthHumanizer`](https://github.com/rudra496/StealthHumanizer) | `1aacbda6e2f66afbdcb6714a85347307068373e9` | Possible ideas for measurable style features | No runtime dependency; defer UI concepts |
| `lynote-ai/humanize-text` | `b8e31f6ca6788b465600f42e7439138d455500bb` | Negative reference for translation-chain drift | Excluded |
| `anasu1/text-humanizer` | `20d2675e9e91ed55460452a5984a5e15753e5a86` | Security exclusion record only | Permanently excluded; hostile behavior observed |

Each of the six current voice-tool repositories inspected under `/tmp/skillspector-candidates/voice-tools/` published an MIT license file at its inspected commit, including the hostile repository whose license does not mitigate its behavior. Lynote was inspected separately and is excluded as an architectural reference. Before copying any source or substantial prompt text, create `THIRD_PARTY_NOTICES.md`, preserve copyright notices, and verify the exact copied material remains covered by the inspected license.

### 4.1 What to retain from each usable candidate

#### Dannwaneri

- Require a representative private corpus rather than a single arbitrary passage.
- Infer the author’s voice before checking generic AI patterns.
- Exempt patterns that are genuinely present in the corpus.
- Report voice drift with evidence and candidate repairs.
- Prefer review and targeted revision over wholesale regeneration.

#### Harshaneel / HyPerAlign inspiration

- Form explicit, testable hypotheses about the author.
- Separate profile inference from document revision.
- Represent confidence and supporting corpus evidence for each hypothesis.
- Do not import Harshaneel’s universal bans or detector-first benchmark objective.

#### Untell

- Detect and replace fragile spans with sentinels before revision.
- Restore protected spans exactly after revision.
- Fail closed when a protected span is missing, duplicated, or altered.
- Compare source and revision for semantic drift.
- Do not adopt its preference for plainer wording or detector-optimization loop.

#### Blader

- Use its pattern catalog to identify possible AI residue.
- Require contextual evidence before treating a pattern as a defect.
- Do not adopt blanket punctuation or vocabulary prohibitions.
- Explicitly prohibit the autobiographical fabrication seen in its showcase rewrite.

### 4.2 Exclusions

- No translation hops.
- No automatic calls to Google Translate, Niutrans, or equivalent services.
- No direct detector-evasion promise.
- No dependency on unreviewed remote scripts, executables, models, or repositories.
- No raw suspicious URL in documentation, prompts, fixtures, or reports; defang hostile addresses.
- Never acquire code from `anasu1/text-humanizer` beyond the quarantined evidence already inspected.

## 5. User contract

### 5.1 Inputs

Required:

- source text or source file;
- requested revision intent, such as “remove formulaic AI residue while preserving my voice.”
- a resolvable, validated voice profile for every mode that emits revised text.

Required only when relevant to the document:

- domain or genre;
- intended audience;
- optional list of protected terms;
- optional editing aggressiveness.

Without a resolvable profile, the skill may run only in `diagnose-only`. It labels every finding `source_only`, must not emit `voice_drift` findings, and returns `PROFILE_REQUIRED_FOR_REVISION` when revised output is requested. The profile-free ablation described in Section 9 is evaluation-only and cannot emit production output.

### 5.2 Modes

#### `conservative` — default

- Diagnose the document.
- Rewrite only passages with strong evidence of AI residue or voice drift.
- Preserve unaffected text.
- Do not change the register.

#### `high-register`

- Apply conservative behavior.
- Give exact corpus-attested terms and user-glossary terms a protection presumption; aliases and inflections must be configured explicitly in the first version.
- Treat unattested high-register language as neither automatically protected nor automatically suspicious.
- Preserve complex syntax when it is coherent and supported by the corpus.
- Flag simplification pressure as a conflict rather than silently applying it.
- Permit a source-only high-register term to change only when cataloged contextual evidence establishes inflation, redundancy, imprecision, or a user-requested change. Pattern membership or rarity alone is insufficient.

#### `technical`

- Apply high-register behavior.
- Lock technical terms, identifiers, formulas, code, citations, numbers, and definitions.
- Favor terminological consistency over conversational naturalness.

#### `diagnose-only`

- Return findings and suggested edits without producing a revised document.
- Operate without a profile only in `source_only` mode, with no `voice_drift` category and a prominent warning that voice fidelity was not evaluated.

An `aggressive` detector-oriented mode is intentionally omitted from the initial product. It may be considered later only if it cannot weaken the core guarantees.

### 5.3 Outputs

Default output:

- revised text only, suitable for direct use.

Optional audit output:

- changed passages;
- reason for each change;
- corpus evidence supporting the change;
- protected-span verification;
- semantic-drift warnings;
- unresolved conflicts;
- confidence per finding.

The audit must not be injected into the revised text. Raw model-output test artifacts must be stored exactly as produced, without presentation wrappers or Markdown decoration.

### 5.4 Machine contracts

The model returns `edit-proposal.v1`; it never supplies byte offsets, hashes, or a complete output document. `scripts/humanize.py` resolves proposals into the internal `edit-set.v1`, applies them, and is the sole authority permitted to emit an accepted revised document.

```json
{
  "schema_version": "edit-proposal.v1",
  "document_id": "draft-001",
  "mode": "conservative",
  "profile_id": "brooks-default",
  "proposals": [
    {
      "proposal_id": "proposal-001",
      "passage_id": "paragraph-003",
      "original_text": "exact normalization-sensitive text from the protected passage",
      "prefix_anchor": "optional exact text before the target",
      "suffix_anchor": "optional exact text after the target",
      "replacement_text": "replacement containing any required sentinels",
      "reason_category": "voice_drift",
      "corpus_evidence_ids": ["sample-02:paragraph-7"],
      "pattern_evidence": null,
      "protected_sentinel_ids": ["VP_SENTINEL_0004"],
      "confidence": 0.91,
      "requires_review": false
    }
  ],
  "unresolved_conflicts": []
}
```

The orchestrator assigns immutable passage IDs and spans before prompting. Omitted anchors are empty strings. A qualifying target is the exact, normalization-sensitive, contiguous sequence `prefix_anchor + original_text + suffix_anchor` within the named passage; anchors must be immediately adjacent, and the resolved edit range covers only `original_text`. Zero qualifying sequences return `EDIT_TARGET_NOT_FOUND`; more than one returns `EDIT_TARGET_AMBIGUOUS`. NFC/NFD mismatches and distant anchors fail rather than matching approximately. Malformed model output receives one schema-repair attempt and then returns `MALFORMED_EDIT_PROPOSAL`. Review precedence is deterministic: confidence below `0.80` forces `LOW_CONFIDENCE_PROPOSAL`; otherwise model-set `requires_review: true` forces `MODEL_REQUESTED_REVIEW`; confidence at least `0.80` with `requires_review: false` introduces no confidence review by itself. Both review codes bind to the resolved edit and candidate subject. Confidence never overrides a deterministic failure.

`reason_category` is one of `voice_drift`, `formulaic_ai_residue`, `clarity`, `redundancy`, or `user_requested`. Every style claim requires corpus evidence. Every `formulaic_ai_residue` proposal additionally requires `pattern_evidence`:

```json
{
  "pattern_id": "transition.stock-conclusion.v1",
  "evidence_kind": "countable",
  "source_evidence": "exact implicated source text",
  "corpus_disposition": "absent",
  "source_rate": 0.12,
  "corpus_rate": 0.01,
  "pattern_threshold": 0.08
}
```

`evidence_kind` is `countable` or `contextual`; `corpus_disposition` is `absent`, `attested`, or `insufficient_evidence`. Model-supplied rates and disposition are advisory. During `resolve`, `humanize.py` reruns the versioned catalog matcher over the source and included corpus and recomputes counts, denominators, rates, threshold result, and corpus disposition. Any mismatch returns `PATTERN_EVIDENCE_MISMATCH`. Countable patterns use their own cataloged thresholds—never a universal multiplier. An attested countable pattern produces `review_required` with `CORPUS_ATTESTED_PATTERN`; insufficient evidence returns `PATTERN_EVIDENCE_INSUFFICIENT`. Contextual patterns require exact evidence, corpus evidence or counterevidence, and a verifier decision of `confirmed`, `not_confirmed`, or `uncertain`. Non-confirmation returns `CONTEXTUAL_PATTERN_NOT_CONFIRMED`; uncertainty requires review with `CONTEXTUAL_PATTERN_UNCERTAIN`. Unknown patterns or incomplete evidence are rejected.

After unique resolution, the orchestrator generates internal `edit-set.v1`:

```json
{
  "schema_version": "edit-set.v1",
  "document_id": "draft-001",
  "source_sha256": "hex digest of the protected source",
  "edits": [
    {
      "edit_id": "edit-001",
      "proposal_id": "proposal-001",
      "passage_id": "paragraph-003",
      "start_byte": 412,
      "end_byte": 608,
      "original_sha256": "hex digest of source[start_byte:end_byte]",
      "replacement_text": "validated replacement",
      "protected_sentinel_ids": ["VP_SENTINEL_0004"]
    }
  ]
}
```

Byte ranges are UTF-8 offsets against the exact protected source and `end_byte` is exclusive. The orchestrator computes all ranges and hashes. Ranges must end on Unicode code-point boundaries and cannot bisect a sentinel. Touching edits are legal; overlapping, out-of-bounds, passage-crossing, or sentinel-interior edits are rejected. Valid edits are applied from the highest byte offset downward.

Every completed run produces `voice-audit.v1`; it is optional as user-facing output but mandatory as a private verification artifact:

```json
{
  "schema_version": "voice-audit.v1",
  "document_id": "draft-001",
  "status": "accepted",
  "source_sha256": "hex digest",
  "output_sha256": "hex digest",
  "edit_ids": ["edit-001"],
  "evidence_by_edit": [
    {
      "edit_id": "edit-001",
      "pattern_id": "transition.stock-conclusion.v1",
      "evidence_kind": "countable",
      "matcher_version": "ai-patterns.v1",
      "exact_evidence_ids": ["draft-001:paragraph-003:match-01"],
      "source_count": 2,
      "source_denominator": 17,
      "source_rate": 0.117647,
      "corpus_count": 0,
      "corpus_denominator": 103,
      "corpus_rate": 0.0,
      "threshold": 0.08,
      "corpus_disposition": "absent",
      "contextual_verifier_decision": null
    }
  ],
  "verifier": {
    "protected_spans": "pass",
    "edit_locality": "pass",
    "semantic_fidelity": "pass",
    "fresh_context": true,
    "route": "configured route",
    "resolved_backend_model": "resolved backend and model",
    "different_backend": false,
    "contextual_pattern_decisions": []
  },
  "review_findings": [],
  "review_approval_ids": [],
  "voice_metric_warnings": [],
  "warnings": [],
  "rejection_codes": []
}
```

`status` is `accepted`, `rejected`, or `review_required`. Machine-readable rejection codes include `PROFILE_REQUIRED_FOR_REVISION`, `UNENFORCEABLE_PROFILE_HYPOTHESIS`, `LOW_CONFIDENCE_PROPOSAL`, `MODEL_REQUESTED_REVIEW`, `MALFORMED_EDIT_PROPOSAL`, `EDIT_TARGET_NOT_FOUND`, `EDIT_TARGET_AMBIGUOUS`, `PREPARED_STATE_MISMATCH`, `CONSENT_INVALID`, `CONSENT_BACKEND_MISMATCH`, `BACKEND_RESOLUTION_REQUIRED`, `SOURCE_HASH_MISMATCH`, `PASSAGE_HASH_MISMATCH`, `EDIT_RANGE_INVALID`, `EDIT_OVERLAP`, `PROTECTED_SPAN_OVERLAP`, `SENTINEL_BOUNDARY_VIOLATION`, `SENTINEL_MISSING`, `SENTINEL_DUPLICATED`, `SENTINEL_ORDER_CHANGED`, `PROTECTED_CONTENT_CHANGED`, `UNVERIFIED_TOKEN_CHANGE`, `UNVERIFIED_ENTITY_CHANGE`, `PATTERN_EVIDENCE_MISMATCH`, `PATTERN_EVIDENCE_INSUFFICIENT`, `CORPUS_ATTESTED_PATTERN`, `CONTEXTUAL_PATTERN_NOT_CONFIRMED`, `CONTEXTUAL_PATTERN_UNCERTAIN`, `PROFILE_MEMORIZATION_OVERLAP`, `REVIEW_APPROVAL_INVALID`, `SEMANTIC_DRIFT`, `REGISTER_FLATTENING`, `UNSUPPORTED_FACT`, and `EDIT_OUTSIDE_AUTHORIZED_SCOPE`. Audit records use hashes and evidence identifiers; they do not contain private corpus passages by default.

Only a user-authored `voice-review-approval.v1` artifact may resolve `review_required`:

```json
{
  "schema_version": "voice-review-approval.v1",
  "approval_id": "approval-001",
  "profile_id": "brooks-default",
  "run_id": "run-001",
  "document_id": "draft-001",
  "source_sha256": "hex digest",
  "candidate_output_sha256": "hex digest",
  "finding_id": "finding-001",
  "subject_edit_ids": ["edit-001"],
  "evidence_ids": ["proposal-001"],
  "review_code": "UNVERIFIED_TOKEN_CHANGE",
  "decision": "approve",
  "approver": "user",
  "approved_at": "ISO-8601 timestamp"
}
```

Every `review_required` result first creates a `voice-audit.v1.review_findings` record. Findings sharing review code and exact subject are coalesced, with all sample IDs, alignments, pattern IDs, proposal IDs, and other disambiguating evidence identifiers stored as one sorted, deduplicated `evidence_ids` array and displayed at approval. `subject_edit_ids` may contain one, several, or no edits for document-level findings. Compute `finding_id` as SHA-256 of UTF-8 JSON containing schema version, review code, source hash, candidate-output hash, ordered subject edit IDs, subject hash/range, and sorted evidence IDs; keys are lexicographically sorted and the serialization contains no insignificant whitespace. The dedicated interactive `humanize.py approve` operation displays the exact coalesced finding, all evidence IDs, candidate diff, and review code and requires direct user confirmation before writing an approval artifact bound to that `finding_id` and complete ordered subject list. Noninteractive agents, harnesses, revisers, and verifier models cannot invoke approval. The artifact is stored under `$VOICE_PROFILE_DIR/<profile>/approvals/` with mode `0600`; the audit records its hash and identifier. Missing approval preserves the original review code; malformed, replayed, nonmatching, or incomplete-subject approval returns `REVIEW_APPROVAL_INVALID`; a user rejection remains rejected.

`scripts/humanize.py` is a deterministic state machine with `prepare`, `resolve`, and `finalize` operations. It owns consent validation, protection, prepared-state persistence, passage mapping, proposal validation, pattern-evidence recomputation, edit application, restoration, deterministic verification, review-approval validation, hashing, audit generation, and final emission. `prepare` validates consent and emits the revision handoff. `resolve` assembles the candidate, consumes and validates a fresh harness-supplied route-resolution/consent tuple, and only then emits the semantic-verification handoff. `finalize` verifies that the returned verifier backend matches the verification handoff and valid consent; mismatch returns `CONSENT_INVALID` or `CONSENT_BACKEND_MISMATCH`. Revision and fresh-context verification are nondeterministic handoffs, but their inputs and outputs must pass through the state machine. Candidate text may be staged privately; no agent or harness may hand-assemble an accepted revision. Missing verifier results, unresolved review requirements, schema failures, or deterministic failures cannot produce `status: accepted`.

## 6. Voice profile

### 6.1 Corpus requirements

A production profile should contain:

- five to ten samples;
- at least two genres when the author writes across genres;
- predominantly unassisted or lightly edited writing;
- enough text to expose sentence rhythm and vocabulary habits;
- no sensitive material that the selected model provider is not authorized to receive.

Freeze at least two held-out authentic samples before profile generation. Held-out text may not inform profiles, prompts, pattern thresholds, revisions, or repair decisions; it appears only as a blinded authorship-likeness anchor during final evaluation.

Every enforceable profile hypothesis must be observable, cite evidence from at least two included samples, and record counterevidence. It must also pass an acceptable-alternative genericity test: identify the preferred realization and a contrasting realization that is independently grammatical, coherent, factually sound, and compatible with core quality rules. If negating the claim necessarily implies unclear, inaccurate, incoherent, ungrammatical, or unsupported prose, the claim is a generic quality maxim and must be `descriptive_only`. The profile records the acceptable contrast, `quality_inversion: false`, and explicit user confirmation that the distinction is author-specific. Missing, failed, or uncertain fields force `descriptive_only`; attempting to use such a hypothesis as a revision constraint returns `UNENFORCEABLE_PROFILE_HYPOTHESIS`.

### 6.2 Profile representation

The profile should be explicit and inspectable:

```yaml
profile_version: 1
name: brooks-default
corpus_manifest:
  - id: sample-01
    path: /private/path/sample-01.md
    genre: analytical-essay
    included_in_profile: true
  - id: sample-03
    path: /private/path/sample-03.md
    genre: analytical-essay
    included_in_profile: true
  - id: heldout-01
    path: /private/path/heldout-01.md
    genre: analytical-essay
    included_in_profile: false
hypotheses:
  - id: register-01
    claim: "Prefers a precise high-register term when a plainer synonym would also be accurate."
    confidence: 0.92
    applicability: enforceable
    evidence:
      - sample-01:paragraph-3
      - sample-03:paragraph-5
    counterevidence: []
    genericity_check:
      acceptable_contrast: "Uses the plainer accurate synonym where either lexical choice would remain clear and factual."
      quality_inversion: false
      user_confirmed_author_specific: true
style_features:
  sentence_length:
    median_words: null
    p90_words: null
  paragraph_length:
    median_sentences: null
  punctuation_rates: {}
  function_word_rates: {}
  lexical_features: {}
protected_preferences:
  glossary:
    - term: epistemic
      aliases: []
      evidence:
        - sample-01:paragraph-3
  preserve:
    - semicolons when structurally useful
    - domain-specific Latinate terms when precise
  avoid:
    - generic motivational conclusions
    - invented personal anecdotes
```

Values marked `null` are populated by deterministic analysis rather than guessed by the language model.

### 6.3 Storage

The corpus must not live in the shared skills repository.

Use a configurable private directory:

```text
$VOICE_PROFILE_DIR/<profile-name>/
```

Default when the variable is unset:

```text
~/.local/share/voice-preserving-humanizer/profiles/<profile-name>/
```

The profile directory contains the corpus manifest, derived profile, and local evaluation artifacts. It must be excluded from Git, cloud sync, and published skill bundles unless the user explicitly chooses otherwise.

Consent is recorded as one local artifact per approved tuple under `$VOICE_PROFILE_DIR/<profile-name>/consent/`:

```json
{
  "schema_version": "voice-consent.v1",
  "profile_id": "brooks-default",
  "harness": "hermes",
  "provider_route": "configured route identifier",
  "resolved_backend_model": "provider and model resolved at approval time",
  "data_class": "raw_private",
  "dynamic_route": false,
  "dynamic_route_acknowledged": false,
  "approved_payload_sha256": null,
  "transcript_policy": "persistent",
  "transcript_location": "documented location or unknown",
  "purge_procedure": "documented procedure or unavailable",
  "approved_at": "ISO-8601 timestamp",
  "scope": ["profile_generation", "document_revision"],
  "approved_by": "user"
}
```

Consent is valid only for the recorded profile, harness, route, resolved backend/model, data class, transcript policy, and scope. A change to any tuple field requires renewed consent; consent is never reused across harnesses merely because they share a proxy route.

Raw corpus/source data—including excerpts, adjacent context, quotations, and verifier passages—requires exact backend/model resolution immediately before every handoff and matching fixed-backend consent. Profile generation always handles raw corpus and follows this rule. Because deterministic scripts do not perform network discovery, the harness adapter supplies a fresh `route-resolution.v1` artifact containing harness, route, resolved backend/model, resolution timestamp, and resolver evidence. The profile-generation entry point validates that artifact and consent before corpus handoff; `humanize.py prepare` does so before revision handoff; and `humanize.py resolve` repeats it against a newly supplied artifact before verification handoff. Each handoff manifest binds payload hash, route-resolution hash, harness, route, resolved backend/model, transcript policy, scope, and consent-artifact hash. `finalize` validates the verifier-returned backend against the verification handoff and consent before acceptance. Resolution failure returns `BACKEND_RESOLUTION_REQUIRED`; tuple or payload mismatch returns `CONSENT_INVALID`; backend change returns `CONSENT_BACKEND_MISMATCH`.

Dynamic-route consent is forbidden for raw corpus or source data. It is permitted only for non-private fixtures, a user-approved redacted payload bound by hash, or schema-constrained `profile_summary_only` data containing no raw excerpts. Summary-only payloads must pass the six-token profile-overlap scan; detected overlap reclassifies the payload as raw and blocks unresolved routing. Transcript behavior, location, and purge procedure must be documented as `unknown` or `unavailable` when the harness does not expose them. Consent files contain no corpus excerpts or credentials and use mode `0600`.

## 7. Processing architecture

```text
Source text + requested intent + named voice profile
                         |
                         v
          humanize.py prepare (deterministic)
     protection manifest + immutable passage map
                         |
                         v
        Diagnosis and revision model handoff
                         |
                         v
                 edit-proposal.v1
                         |
                         v
          humanize.py resolve (deterministic)
        edit-set.v1 + restored candidate text
                         |
                         v
         Fresh-context semantic verification
                         |
                         v
         humanize.py finalize (deterministic)
                         |
              +----------+----------+
              |                     |
              v                     v
   Emit accepted output       Reject or request review
       + voice-audit.v1
```

The state machine is the only accepted-output authority. Model calls cannot bypass `prepare`, `resolve`, or `finalize`, and recorded model responses must yield byte-identical deterministic artifacts across harnesses.

### 7.1 Protected-span extraction

Protect at minimum:

- fenced and inline code;
- URLs and email addresses;
- Markdown links;
- block quotations and direct quotations;
- citation forms;
- footnotes;
- numbers, dates, percentages, currencies, and units;
- formulas;
- user-specified terminology;
- named entities when confidence is sufficient;
- headings when the user requests structural preservation.

All extractors run independently against the original source. Their normative precedence is: user-manifested spans/terms/entities; requested preserved headings; fenced code; inline code; complete Markdown links/images; raw URLs; email addresses; formulas; footnotes; block quotations; direct quotations; citation forms; composite dates/times/percentages/currencies/units; plain numbers; high-confidence inferred entities.

Disjoint candidates are both protected. A contained candidate is associated with the containing span and retains both class labels. A candidate containing an already claimed span expands protection to the complete outer candidate. A crossing partial overlap that cannot be represented as safe containment blocks preparation with `PROTECTED_SPAN_OVERLAP`; no candidate is silently fragmented or skipped. Sentinels are inserted only after the complete protection map is resolved, and no extractor runs over substituted text.

Sentinel generation is deterministic and injective within a prepared document. For zero-based `sentinel_index`, compute `SHA-256(UTF-8("vph-sentinel-v1") || raw_32_byte_original_source_sha256 || uint64_be(collision_counter) || uint64_be(sentinel_index))`, encode the digest with a lowercase digit-free base-26 alphabet, and start the single global collision counter at zero. Construct the complete token set; if any token collides with the original pre-substitution source or another generated token, increment the global counter and regenerate the entire set. Persist original-source hash, protected-source hash, final collision counter, and the complete ID/index-to-token mapping in prepared state; there is no separate random nonce. Malformed or source-incompatible prepared state returns `PREPARED_STATE_MISMATCH`. Sentinel IDs in manifests remain separate from raw tokens. Restoration verifies exact cardinality, identity, content, and relative source order for every sentinel. Reordering protected sentinels is unsupported in v1 and returns `SENTINEL_ORDER_CHANGED`. Replaying identical inputs reproduces byte-identical prepared artifacts.

The 100% exact-preservation guarantee applies to user-manifested and detected protected spans—not to every entity-like token the extractor may have missed. To close that gap, `finalize` compares numeric tokens, citation-shaped tokens, and capitalized sequences across every changed slice and across the whole source/output pair. A changed manifested token fails deterministically. A changed unprotected candidate token returns `review_required` with `UNVERIFIED_TOKEN_CHANGE`. Every unedited region must remain byte-identical; any other difference returns `EDIT_OUTSIDE_AUTHORIZED_SCOPE`.

#### Named-entity policy

The initial standard-library implementation uses a conservative hierarchy rather than pretending to provide general-purpose named-entity recognition:

1. User-specified entities and entities listed in the profile manifest are always protected by exact match, including configured aliases.
2. Deterministic heuristics may protect high-confidence forms such as repeated capitalized multi-token names, organization suffixes, and explicitly labeled document metadata. Every heuristic match is recorded in the protection manifest.
3. A model may propose additional entities, but those entities are `uncertain` until matched against the manifest or resolved by a matching user-authored `voice-review-approval.v1` artifact. They cannot silently become protected facts.
4. Any edit touching an uncertain or previously unseen entity returns `review_required` with `UNVERIFIED_ENTITY_CHANGE`.
5. The skill never claims complete entity preservation without an approved manifest or a separately reviewed NER dependency.

The verifier compares the source, edit ranges, protection manifest, and output. Deterministic entity or sentinel failures are fail-closed and cannot be overridden by a language-model semantic verdict.

### 7.2 Diagnosis

Classify findings into:

- voice drift from the author corpus;
- formulaic AI residue;
- factual or semantic risk;
- optional readability issue;
- intentional author feature;
- uncertain conflict requiring human review.

Every proposed style change must cite corpus evidence or a concrete, cataloged defect in the source. “Sounds AI-generated” is not sufficient.

Every entry in `references/ai-patterns.md` has a stable `pattern_id`, an evidence kind (`countable` or `contextual`), a versioned deterministic matcher when countable, and pattern-specific evidence requirements. A `formulaic_ai_residue` finding must include exact source evidence, passage ID, advisory corpus disposition, and advisory rates/thresholds for countable patterns. `humanize.py resolve` recomputes the countable evidence and records non-excerpting counts, denominators, rates, disposition, matcher version, and evidence IDs in `voice-audit.v1.evidence_by_edit`. Contextual findings require corpus evidence or counterevidence and a fresh-context verifier decision of `confirmed`, `not_confirmed`, or `uncertain`, also retained by edit in the audit. Unknown patterns, missing or mismatched evidence, and universal source-to-corpus multipliers are invalid.

### 7.3 Revision

Provide the model with:

- source text with protected sentinels;
- explicit edit intent;
- voice hypotheses and evidence;
- measurable profile summary;
- a concise list of implicated passages;
- hard constraints;
- a prohibition on new facts or experiences.

The model returns only `edit-proposal.v1` against orchestrator-assigned passages. It does not return byte ranges, hashes, or a free-form complete document. Exact model text is staged privately for schema validation and unique target resolution; only `humanize.py` may assemble a candidate or accepted document.

### 7.4 Verification

Reject or flag output when any of the following occurs:

- protected-span mismatch;
- number, citation, quotation, or named-entity drift;
- unsupported factual addition;
- lost qualification or changed modality;
- changed conclusion or causal relationship;
- unexplained register reduction;
- broad rewrite outside the authorized passage set;
- warning-level per-metric voice drift outside the included corpus envelope;
- unresolved uncertainty from the verifier.

The first version requires semantic verification in a fresh context that receives only the original passage, proposed replacement, bounded adjacent context required to interpret qualifications, the profile summary, and the verification rubric—not the reviser transcript or reasoning. Its structured verdict covers factual additions, modality, qualification, causality, conclusion, register, and one `confirmed | not_confirmed | uncertain` decision for every applicable contextual AI-pattern claim. Failure rejects; uncertainty requires review. A different backend is used only when it is separately configured and consented. The audit records whether verification used the same or a different backend and retains each contextual-pattern decision by edit ID.

Voice drift is reported independently for sentence-length median and p90, paragraph-length median, punctuation rates, and contraction rate. For each metric, compare source and output with the included corpus envelope; warn only when output moves farther from the corpus median than the source and crosses the observed envelope. Report `insufficient_sample` instead of unstable metrics when there are fewer than five sentences for a median, ten sentences for p90, three paragraphs for paragraph metrics, or 100 words for rate metrics. These checks are warnings in the first version, never an aggregate voice score, and cannot override semantic or protected-span failures.

Language-model verification cannot override any deterministic failure. Missing verifier output cannot yield an accepted document.

## 8. Proposed skill layout

```text
voice-preserving-humanizer/
├── SKILL.md
├── README.md
├── THIRD_PARTY_NOTICES.md
├── references/
│   ├── ai-patterns.md
│   ├── candidate-provenance.md
│   ├── harness-privacy.md
│   ├── high-register-editing.md
│   ├── profile-schema.md
│   └── verification-rubric.md
├── scripts/
│   ├── humanize.py
│   ├── profile.py
│   ├── protect.py
│   ├── style_metrics.py
│   └── verify.py
├── templates/
│   ├── consent.json
│   ├── edit-proposal.json
│   ├── edit-set.json
│   ├── handoff-manifest.json
│   ├── prepared-state.json
│   ├── profile.yaml
│   ├── review-approval.json
│   ├── route-resolution.json
│   └── audit.json
└── tests/
    ├── fixtures/
    ├── test_humanize.py
    ├── test_profile.py
    ├── test_protect.py
    ├── test_style_metrics.py
    └── test_verify.py
```

Scripts should use the Python standard library unless a dependency produces a material and verified improvement. No install-time hooks, remote downloads, or executable acquisition.

## 9. Evaluation plan

### 9.1 Evaluation set

Create a private local set containing:

- five authentic author samples for profile creation;
- at least two held-out authentic samples;
- at least ten AI-assisted or over-smoothed passages requiring revision;
- analytical, technical, and personal-essay examples where available;
- adversarial examples containing citations, numbers, quotations, technical terms, and complex qualifications.

Freeze the held-out set before profile generation. It cannot be read while developing profiles, prompts, pattern thresholds, or repairs. During blind review, held-out passages appear under opaque IDs as authorship-likeness anchors; they are never generation inputs.

Do not commit the private corpus or model outputs containing private text. The evaluation runner records one generation per method and passage in the first version. This is a cost-conscious limitation, not a claim of statistical robustness.

### 9.2 Baselines

Compare against:

1. no revision;
2. stock `dannwaneri/voice-humanizer` behavior;
3. stock or minimally configured `blader/humanizer` behavior;
4. a strong same-model prompt supplied with the same permitted writing samples and explicit voice-preservation instructions;
5. the custom skill with the production profile;
6. an evaluation-only custom-skill ablation with profile conditioning removed.

Do not execute or benchmark the excluded translation-chain or hostile repositories.

### 9.3 Mechanical acceptance criteria

- 100% exact restoration of user-manifested and detected protected spans.
- 100% preservation of user-specified protected terms.
- No invented manifested numbers, citations, named entities, quotations, or autobiographical claims.
- Every unmanifested numeric, citation-shaped, or capitalized-sequence delta is surfaced for review rather than silently accepted.
- No edits outside authorized spans in conservative mode. Sentinel substitution is internal only; after restoration every unedited region is byte-identical.
- Every changed passage represented in the mandatory private audit.
- After all edits and sentinel restoration, maximal contiguous changed regions of the restored output are scanned against included profile samples for normalized contiguous overlap of six or more tokens. Touching edits form one changed region. All matches for the same changed region and review code coalesce into one finding; its `subject_edit_ids` lists every contributing edit in source-offset order, its subject hash/range identifies the complete changed region, and its sorted evidence IDs include every matched sample ID and alignment hash. Normalize with Unicode NFKC and case-folding; tokenize maximal Unicode letter/number sequences, retain apostrophes only when internal to letters, and treat hyphens/dashes as boundaries. Restored protected spans, citations, direct quotations, and exact configured glossary terms/aliases break scan windows and cannot be bridged. Ignore a candidate sequence only when that same normalized sequence already occurs in the source. A six-token-or-longer match returns `review_required` with `PROFILE_MEMORIZATION_OVERLAP` and records sample IDs, alignment hashes, token counts, and subject hashes rather than corpus text.
- Deterministic scripts pass on macOS ARM64 with the project’s selected Python version.
- No network activity from deterministic scripts.

### 9.4 Voice acceptance criteria

Brooks reviews blind outputs without knowing which method produced each one and rates:

- sounds like me;
- preserves my vocabulary and intellectual register;
- preserves rhythm and rhetorical structure;
- retains meaning and qualifications;
- removes formulaic AI residue;
- adds no false personality;
- requires little further editing.

Use a five-point scale plus free-text notes. The v1 scored packet contains exactly ten randomized passage groups selected from the larger frozen evaluation set. Each output and authentic held-out anchor receives an opaque ID; the method-to-ID key remains separate until scoring is complete. The rubric records one score per criterion, free-text notes, factual-fidelity failures, and an explicit blinded head-to-head `voice_preference: left | right | tie` for every required method comparison. Voice preference is never inferred by aggregating criterion scores. A tie counts as no win for either method. A custom factual automatic failure counts as no custom win; a baseline factual failure does not manufacture a custom voice win. Any invented fact, changed qualification, citation error, protected-span failure, or unsupported autobiographical detail is an automatic failure regardless of voice preference.

All fixed gates must pass:

- zero factual-fidelity automatic failures;
- AI-residue-removal median at least 4/5 and improvement over no revision in at least seven of ten groups;
- custom output explicitly preferred for voice fidelity in at least seven of ten groups against each stock baseline and the strong prompt-plus-samples baseline, counting ties as no win;
- profiled custom output explicitly preferred over the profile ablation in at least six of ten groups, counting ties as no win.

The evaluation runner must reproduce the randomized packet and hidden method key from a recorded seed. An identity transform fails unless it also passes the residue-improvement gate. Any change to a generation prompt, pattern definition, threshold, profile-conditioning rule, or acceptance rule invalidates prior scores and requires a newly randomized blind rerun of the final artifact.

### 9.5 Supporting style metrics

Use metrics as diagnostics, not as a replacement for human judgment:

- sentence-length distribution;
- paragraph-length distribution;
- punctuation rates;
- function-word frequencies;
- contraction rate;
- type-token ratio with sample-length normalization;
- lexical sophistication and domain-term retention;
- rate of first-person statements and rhetorical questions;
- source-to-output edit locality.

For sentence-length median/p90, paragraph-length median, punctuation rates, and contraction rate, record source value, output value, corpus median/envelope, sample sufficiency, and warning result independently. Do not collapse these into a single unsupported “voice score.”

Every evaluation run pins and records harness route, resolved backend/model version, model parameters, exact prompts, method order, corpus/profile versions, code revision, and randomization seed. The shipped prompt, patterns, thresholds, and profile-conditioning behavior must be exactly those evaluated.

### 9.6 Detector evidence

If detector scores are collected, label them experimental and non-authoritative. Never optimize against one detector or claim that an output is undetectable. A detector regression does not justify weakening semantic or voice fidelity.

## 10. Security and privacy requirements

1. Stage every upstream skill or update in `/tmp/skillspector-candidates/`.
2. Run SkillSpector static analysis before installation or source reuse.
3. Complete a semantic review of prompts and scripts before activation.
4. Record upstream repository, commit, license, and copied elements.
5. Do not execute upstream setup scripts during evaluation.
6. Do not render raw hostile URLs; use defanged notation.
7. Do not include corpus text in skill-generated logs or audits beyond what the selected model call requires.
8. Store private corpus data and every private artifact written by the skill only under `$VOICE_PROFILE_DIR`; create directories with mode `0700` and files with mode `0600`. This controls skill-written files, not harness transcripts.
9. Keep raw evaluation outputs exactly as produced, but never store them in Git, the shared skill source, or a presentation wrapper.
10. Before private text is sent to a model, disclose the harness, provider route, immediately resolved backend/model, transcript policy, known transcript location, and purge procedure. Require consent for the exact profile/harness/route/backend/data-class/policy/scope tuple, and bind each handoff manifest to its payload and consent hashes.
11. Backend changes behind an unchanged route invalidate fixed-backend consent. If exact backend resolution is unavailable, raw corpus/source handoffs block. Dynamic-route consent is valid only for non-private fixtures, user-approved redacted payloads, or overlap-scanned profile summaries containing no excerpts. If transcript persistence cannot be prevented, do not claim ephemeral processing; offer a fixed local model, a redacted sample, sanitized summary-only operation, or cancellation.
12. Derived audits contain hashes and evidence identifiers by default, not corpus excerpts.
13. Do not transmit corpus or source text through translation services.
14. Support an approved VibeProxy endpoint only after resolving its actual backend/model for every raw handoff; an unresolved dynamic VibeProxy route may receive only the sanitized data classes allowed by item 11.
15. Run semantic verification in a fresh context. Use a different backend only when separately configured and consented; record same-backend versus different-backend verification in the audit.
16. Keep model selection outside the skill’s source code.
17. Ensure deterministic scripts have no network imports or subprocess execution; model handoffs are performed by the harness using artifacts emitted and consumed by `humanize.py`.
18. Run static checks again after every substantial upstream-inspired change.

## 11. Implementation sequence

The work is deliberately flat rather than phase-based.

1. Create `voice-preserving-humanizer/` with `SKILL.md`, README, provenance, references, templates, scripts, and tests.
2. Document private-corpus storage, each harness’s transcript behavior/location/purge procedure, and the consent tuple; establish `VOICE_PROFILE_DIR` outside Git.
3. Define and test the profile and `voice-consent.v1` schemas, including fixed-backend raw consent and sanitized-only dynamic-route consent.
4. Define and test `edit-proposal.v1`, internal `edit-set.v1`, `voice-audit.v1`, `voice-review-approval.v1`, prepared state, semantic-verifier output, and every rejection code.
5. Implement `scripts/humanize.py` as the deterministic `prepare`/`resolve`/`finalize` state machine, with separate revision- and verification-handoff consent gates, review-approval gate, and sole output authority.
6. Implement deterministic style metrics, corpus envelopes, sample-sufficiency rules, and independent warning records.
7. Implement independently detected protected spans, total precedence/overlap resolution, index-distinct source-derived deterministic sentinels, exact restoration/order enforcement, and fragmentation/collision/reordering fixtures.
8. Implement differential numeric/citation/capitalized-sequence scanning and byte-identical unedited-region verification.
9. Implement the conservative named-entity hierarchy and `UNVERIFIED_ENTITY_CHANGE` behavior.
10. Define stable AI-pattern IDs, deterministic matcher versions, countable/contextual evidence requirements, per-pattern thresholds, orchestrator recomputation, corpus dispositions, and audit records.
11. Create the corpus-analysis prompt; enforce observable hypotheses with evidence from two included samples, counterevidence, acceptable-alternative genericity checks, explicit user confirmation, and `descriptive_only` fallback.
12. Create the diagnosis prompt; reject uncataloged or unevidenced AI-residue findings and prohibit `voice_drift` without a profile.
13. Create the surgical-revision prompt against `edit-proposal.v1` only.
14. Implement exact target resolution, anchor disambiguation, orchestrator-owned UTF-8 offsets/hashes, descending application, and malformed-output retry-once behavior.
15. Create the fresh-context semantic-verification prompt and structured verdict; ensure failure/uncertainty blocks acceptance.
16. Add `conservative`, `high-register`, `technical`, and `diagnose-only` contracts, including profile-required production behavior.
17. Add paired high-register fixtures where precise corpus/glossary diction survives and ornamental inflation is removed, plus complex syntax, semicolon, em-dash, anaphora, passive-voice, and terminology tests.
18. Add adversarial fixtures for anecdotes, numbers, citations, entities, modality, conclusion drift, Unicode normalization, emoji, deterministic sentinel replay/intra-set collision/reordering, URL/email fragmentation, target ambiguity, touching edits, model-requested review, multi-edit/multi-sample finding approval, evidence-ID collision, approval replay, verification-backend change, and hash mismatch.
19. Prepare the sealed exactly-ten-group evaluation packet, hidden method key, raw-output directories, post-restoration changed-region six-token memorization gate, explicit head-to-head preferences, strong prompt baseline, and profile ablation outside Git.
20. Run no-revision, stock Dannwaneri, stock Blader, strong prompt-plus-samples, profiled custom, and ablation methods with pinned run metadata.
21. Conduct Brooks’s blind evaluation and apply all fixed factual, residue, voice, and ablation gates.
22. If any prompt, pattern, threshold, profile-conditioning rule, or acceptance rule changes, invalidate prior scores and rerun the randomized final evaluation.
23. Run SkillSpector static analysis and an independent semantic review on the completed skill.
24. Add shared-library symlinks only after security and acceptance gates pass; run Hermes, Claude, and Codex discovery/invocation smoke tests.
25. Run a final full-pipeline personal document test through Hermes and reproduce its output/audit hashes.

## 12. Activation plan

After the skill passes its gates:

```bash
ln -sfn ~/Code/skills/voice-preserving-humanizer ~/.hermes/skills/voice-preserving-humanizer
ln -sfn ~/Code/skills/voice-preserving-humanizer ~/.claude/skills/voice-preserving-humanizer
ln -sfn ~/Code/skills/voice-preserving-humanizer ~/.codex/skills/voice-preserving-humanizer
```

Hermes activation:

```text
/reload-skills
/skill voice-preserving-humanizer
```

CLI preload:

```bash
hermes -s voice-preserving-humanizer
```

Cross-harness smoke tests:

| Harness | Discovery and invocation check | Pass condition |
|---|---|---|
| Hermes | Start a fresh session after `/reload-skills`; run `/skill voice-preserving-humanizer` | Hermes reports the skill loaded from the shared symlink and performs a diagnose-only fixture without reading private profile data |
| Claude Code | Restart Claude Code after creating `~/.claude/skills/voice-preserving-humanizer`; invoke `/voice-preserving-humanizer` | The slash skill resolves to the shared source and performs the same diagnose-only fixture |
| Codex | Start a fresh Codex session after creating `~/.codex/skills/voice-preserving-humanizer`; invoke `$voice-preserving-humanizer` | Codex resolves the shared source and performs the same diagnose-only fixture |

Before activation, verify every symlink resolves to `/Users/brooks/Code/skills/voice-preserving-humanizer` and that no corpus, profile, or evaluation directory exists below the skill source. Do not create these symlinks until the local source has passed static and semantic review.

## 13. Definition of done

The skill is complete when:

- all deterministic tests pass;
- `humanize.py` is the sole accepted-output authority and reproduces source/output/audit hashes from recorded model responses;
- model proposals never supply trusted offsets or hashes, and all target ambiguity, Unicode, sentinel-boundary, duplicate-token, and sentinel-reordering fixtures fail closed;
- protected-span restoration is exact for every manifested and detected span across the adversarial set;
- differential token scanning prevents unmanifested numeric, citation-shaped, or entity-like changes from passing silently;
- every review state has a deterministic finding ID and exact subject binding, including findings spanning multiple edits;
- no network activity occurs in deterministic scripts;
- no hostile or excluded code is included;
- provenance and MIT attribution are complete;
- SkillSpector static analysis has no unresolved high or critical finding;
- semantic review finds no hidden data-exfiltration or instruction-conflict behavior;
- every accepted revision has a passing fresh-context semantic-verifier record and a separately validated verification-handoff consent/backend binding;
- missing or invalid profiles cannot produce revised output in any harness;
- all fixed factual, AI-residue, stock-baseline, strong-prompt-baseline, and ablation evaluation gates pass on the shipped configuration;
- paired high-register tests preserve precise corpus/glossary diction while allowing evidence-backed removal of ornamental inflation;
- no output invents autobiographical or evidentiary content;
- the source is present in `/Users/brooks/Code/skills/voice-preserving-humanizer`;
- activation and the diagnose-only smoke fixture work from fresh Hermes, Claude Code, and Codex sessions using the same shared source;
- a recorded full-pipeline fixture produces byte-identical deterministic artifacts across all three harnesses from the same model responses;
- the final end-to-end output and audit are both verified.

## 14. Deferred questions

These do not block initial implementation but must be resolved before claiming broad portability:

- Whether voice profiles should support multiple genre-specific subprofiles.
- Whether a separately consented second backend materially improves fresh-context semantic verification enough to justify routine use.
- Whether local embedding models materially improve voice comparison enough to justify a dependency.
- Whether an optional interactive diff view is useful.
- Whether profile versioning requires migration support after the first schema change.
- Whether future harness APIs can enforce ephemeral transcript handling rather than relying on disclosure and consent.

---

## Appendix A: Review record

### Evidence reviewed

- Current source of all candidate repositories listed in Section 4.
- Published prompt and workflow contracts.
- Candidate tests and benchmark implementations where present.
- Current repository licenses.
- The 2026-07-15 hostile-download incident and local containment checks.

### Review status

Codex plan review round 1 returned `NEEDS_REVISION`. It found four important gaps: missing machine schemas, an under-specified named-entity guarantee, unresolved private transcript/output persistence, and incomplete cross-harness smoke tests. It also requested a reproducible blind-evaluation packet and clarification of the license count.

Codex plan review round 2 returned `APPROVED`. All six round-1 fixes were verified. No critical or important issue at confidence 80 or above remained. Its only suggestion, at confidence 72, was to define a profile-local provider/transcript consent artifact; `voice-consent.v1` now addresses that suggestion in Section 6.3.

Fable 5 then reviewed the plan independently as an explicitly adversarial reviewer through the Ask skill. The successful review artifact is `.pipeline/voice-preserving-humanizer/review/fable-adversarial-r2/artifact.md`; its condensed summary is adjacent as `summary.md`. Fable returned `VERDICT: REVISE` and identified the following minimum repair set before implementation:

1. Move byte offsets and hashes out of model-generated data: models return passage IDs, exact original text, and optional anchors; the orchestrator resolves unique matches and computes byte ranges and digests.
2. Define a single deterministic `scripts/humanize.py` orchestration boundary; revised documents must be emitted by it rather than hand-written by the agent.
3. Operationalize AI residue through pattern IDs and corpus-relative frequency evidence.
4. Replace the scalar voice-deviation check with enumerated per-metric drift checks and warning-level tolerances.
5. Specify fail-closed behavior when no voice profile is available.
6. Close undetected protected-token drift through differential scanning and precise extractor/sentinel precedence.
7. Strengthen evaluation with a fixed decision rule, strong prompt-plus-samples baseline, profile ablation, held-out protocol, memorization check, pinned model/run count, and mandatory reruns after revisions.
8. Require a fresh-context semantic verifier in the first implementation rather than deferring it.
9. Resolve route-versus-backend consent semantics and document harness transcript persistence and purge locations.
10. Make high-register protection corpus- or glossary-relative and test precise diction against inflated diction.

Codex then adjudicated all ten Fable findings through the Ask skill. The artifact is `.pipeline/voice-preserving-humanizer/review/codex-fable-adjudication-r1/artifact.md`; its condensed summary is adjacent as `summary.md`. Codex returned `VERDICT: READY_TO_REVISE`, accepted the substance of all ten findings, and bounded two of them: fresh-context verification is mandatory but a different backend is conditional on separate consent, and high-register protection is exact corpus/glossary-relative rather than based on rarity or morphological inference. This revision incorporates the reconciled repair set. The plan remains unauthorized until Codex and Fable independently accept this same revision.

Codex and Fable then independently reviewed document hash `ab507ba2dd7b22b4de67b3e1a15038005fc05c8a0c2a87903d300f06ae90b20d` in `.pipeline/voice-preserving-humanizer/review/codex-dual-r1/` and `fable-dual-r1/`. Both returned `REVISE`. Their overlapping blockers concerned deterministic sentinels, total extractor precedence, durable residue evidence, exact backend consent, explicit blind preferences, contiguous anchors, and the memorization threshold. Fable additionally required governed review approval, a consent-enforcement owner, and an operational test that demotes generic profile maxims.

Codex reconciled the disagreements in `.pipeline/voice-preserving-humanizer/review/codex-fable-reconciliation-r2/` and returned `VERDICT: READY_TO_REVISE`. It selected an acceptable-alternative genericity test rather than a non-author classifier corpus, a six-token review tripwire, and strict backend resolution for raw text while retaining dynamic routing only for sanitized data. This second revision incorporates the resulting nine-item repair set and remains unauthorized until both reviewers accept the same new hash.

Codex and Fable independently reviewed the second revision at hash `28efaa64f6be0e2aa4871c9dcb71219d9fea61b42586c952585f975027e9e1fd` in `.pipeline/voice-preserving-humanizer/review/codex-dual-r2/` and `fable-dual-r2/`. Both returned `REVISE` while affirming that all preceding repairs were substantively resolved. The remaining concrete blockers were non-injective sentinel derivation, undefined sentinel-order preservation, missing verification-handoff consent validation, an unmapped low-confidence review state, per-proposal rather than changed-region memorization ambiguity, and inconsistent evaluation-group denominators. This third revision resolves those compatible findings directly and remains unauthorized until both reviewers accept the same new hash.

Codex reviewed the third revision at hash `60ae71b334af363a87c3f24985e3aec57ff9251e681d786c40ee97e587ffd235` in `.pipeline/voice-preserving-humanizer/review/codex-dual-r3/`. It confirmed all five preceding blockers resolved and returned `REVISE` for one remaining approval-ownership ambiguity when a memorization finding spans multiple touching edits. Fable's parallel Ask run exceeded the ten-minute timeout and produced no artifact or verdict; it is not counted as acceptance or rejection. This fourth revision replaces single-edit review ownership with deterministic finding IDs and complete ordered subject-edit bindings.

Codex and Fable independently reviewed the fourth revision at hash `e6659a98dea5be6c8218d59a09d128c64ff7e2d09f26cc74427e267591c091cf` in `.pipeline/voice-preserving-humanizer/review/codex-dual-r4/` and `fable-dual-r4/`. Both confirmed all preceding blockers resolved and returned `REVISE` for adjacent approval-schema gaps: model-set `requires_review: true` lacked a code at high confidence, and finding IDs did not distinguish multiple sample/pattern evidence sets for the same code and subject. This fifth revision adds deterministic review precedence, `MODEL_REQUESTED_REVIEW`, canonical evidence-bound finding IDs, and coalesced display of every evidence identifier.

Codex and Fable independently reviewed the fifth substantive revision at hash `640ba67f7993cda9c52d9f987127e8fc5a8566818269c6c5b681bb076e17a3fb` in `.pipeline/voice-preserving-humanizer/review/codex-dual-r5/` and `fable-dual-r5/`. Both returned `VERDICT: ACCEPT`. Codex confirmed deterministic handling for both low-confidence and model-requested review plus exact subject/evidence approval binding. Fable confirmed its evidence-collision attack was structurally closed by coalescing and canonical evidence-bound finding IDs, and found no remaining concrete v1 safety or acceptance bypass.

## Appendix B: Critical pass

### Strongest reason not to build

A sufficiently capable model given a writing sample and a concise prompt may already perform most of the desired work. The custom skill risks becoming an elaborate prompt wrapper whose deterministic metrics create false confidence.

### Why build anyway

The value is not merely the rewrite prompt. It is the enforceable contract around the prompt:

- corpus sovereignty;
- protected spans;
- edit locality;
- explicit no-fabrication rules;
- high-register preservation;
- reproducible evaluation;
- provenance and security gates;
- cross-harness activation.

### Principal failure modes

- The profile overfits a small corpus.
- Genre differences are mistaken for voice drift.
- Semantic checks miss changed implications or modality.
- The model follows generic AI-pattern rules more strongly than corpus evidence.
- Mechanical metrics reward superficial mimicry.
- Private corpus text is sent to an unintended remote provider.
- The skill becomes detector-oriented despite its stated priorities.

### Countermeasures

- Hold out author samples.
- Label corpus genre and context.
- Keep human blind review authoritative.
- Require evidence for every style change.
- Fail closed on protected-span errors.
- Display provider-routing implications before private-corpus use.
- Keep detector metrics outside acceptance gates.

## Appendix C: Assumptions and actions

### Assumptions

- Brooks can provide five to ten representative writing samples and at least two held-out samples.
- The first deployment target is personal use on macOS through Hermes, Claude, and Codex.
- VibeProxy or the active harness supplies model access; the skill does not manage credentials.
- Python standard-library scripts are acceptable for deterministic analysis and verification.
- Candidate MIT licenses remain applicable to any material actually reused; this must be reconfirmed at copy time.

### Actions taken

- Inspected candidate source in quarantine.
- Excluded translation-chain approaches from the target architecture.
- Permanently excluded the hostile repository.
- Selected Dannwaneri as the primary conceptual base.
- Selected Harshaneel, Untell, and Blader only for bounded mechanisms.
- Defined a private-corpus, preservation-first architecture.
- Defined security, privacy, evaluation, activation, and completion gates.

### Next action

Obtain Brooks's implementation authorization. Once approved, scaffold `/Users/brooks/Code/skills/voice-preserving-humanizer/` and execute the flat implementation sequence in Section 11 without weakening any accepted gate.
