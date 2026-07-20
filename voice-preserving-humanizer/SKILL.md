---
name: voice-preserving-humanizer
description: Use when revising AI-assisted or over-smoothed prose while preserving the author's demonstrated voice, high-register diction, protected spans, and factual fidelity — not for detector evasion or wholesale paraphrase.
---

# Voice-Preserving Humanizer

Revise AI-assisted or over-smoothed prose without erasing the author's actual voice.

**Normative plan:** `../docs/plans/voice-preserving-humanizer.md`  
**Dual-review synthesis:** `../docs/reviews/voice-preserving-humanizer-dual-review-synthesis.md`  
**Approved plan SHA-256:** `bc26bca227c496e90e2d219de096d88b1ad6f3a7e0a77120f998cec0b6d62dbe`

## Decision snapshot

- Primary conceptual base: `dannwaneri/voice-humanizer` (reimplemented locally; not a runtime dependency).
- Borrow selected mechanisms only from Harshaneel (hypothesis extraction) and Untell (protected spans / semantic gate concepts).
- Blader AI-pattern catalog is advisory evidence, not universal law.
- Permanently exclude `anasu1/text-humanizer`. Exclude translation-chain humanizers.
- Optimization order: factual/semantic fidelity → author voice → high-register precision → concrete AI residue → readability → detector response (diagnostic only).

## Authority split (DR-02)

1. The active model **proposes** edits via `edit-proposal.v1`.
2. `scripts/humanize.py` is the sole `prepare` / `resolve` / `finalize` state machine and the only authority that may emit an accepted revised document.
3. Deterministic code owns protection, targeting, offsets, hashes, evidence recomputation, restoration, verification gates, audits, and final output.
4. No semantic model can override a deterministic failure.

## Modes

| Mode | Emits revised text? | Profile required? |
|---|---|---|
| `conservative` (default) | Yes | Yes |
| `high-register` | Yes | Yes |
| `technical` | Yes | Yes |
| `diagnose-only` | No | No — findings are `source_only`; no `voice_drift` |

Without a resolvable profile, revision modes fail with `PROFILE_REQUIRED_FOR_REVISION` (DR-05).

## Invocation (deterministic core)

```bash
python3 scripts/humanize.py prepare \
  --source path/to/draft.md \
  --profile "$VOICE_PROFILE_DIR/<profile>/profile.yaml" \
  --consent "$VOICE_PROFILE_DIR/<profile>/consent/<consent>.json" \
  --route-resolution path/to/route-resolution.json \
  --mode conservative \
  --outdir /tmp/vph-run

python3 scripts/humanize.py resolve \
  --prepared /tmp/vph-run/prepared-state.json \
  --proposal path/to/edit-proposal.json \
  --route-resolution path/to/verify-route-resolution.json \
  --outdir /tmp/vph-run

python3 scripts/humanize.py finalize \
  --prepared /tmp/vph-run/prepared-state.json \
  --candidate /tmp/vph-run/candidate.md \
  --verifier path/to/verifier-verdict.json \
  --outdir /tmp/vph-run

python3 scripts/humanize.py approve \
  --audit /tmp/vph-run/audit.json \
  --finding <finding_id> \
  --profile-dir "$VOICE_PROFILE_DIR/<profile>"
```

Harnesses must not hand-assemble accepted revisions. Noninteractive agents cannot invoke `approve`.

## Private storage

```text
$VOICE_PROFILE_DIR/<profile-name>/
  corpus/
  profile.yaml
  consent/
  approvals/
  evaluation/
```

Default root when unset: `~/.local/share/voice-preserving-humanizer/profiles/`.  
Create directories `0700` and files `0600`. Never put private corpus or raw evaluation outputs in this skill tree or Git.

## Consent (DR-13)

Before any raw corpus/source handoff: resolve exact backend/model; disclose harness/route/backend/transcript posture; require user consent for the exact tuple; bind handoff manifests to payload + consent hashes. Dynamic routing is limited to fixtures, hash-bound redactions, or overlap-scanned profile summaries without excerpts.

## What this skill is not

- Not a detector-evasion tool.
- Not a translation-chain rewriter.
- Not a wholesale paraphraser.
- Not a fabricator of personality, anecdotes, evidence, or citations.

## Implementation traceability

Cite one plan section, one synthesis ledger ID (`DR-01`…`DR-20`), the schema/code, and the proving test.

## Activation

Do **not** create harness symlinks until security, evaluation, and SkillSpector gates pass (plan §11.24–25, §12).
