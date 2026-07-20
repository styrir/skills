# AI-pattern catalog (advisory)

**Plan:** §5.4, §7.2 · **DR:** DR-03, DR-15

Patterns are advisory diagnostics, not universal bans. Corpus-attested patterns require review rather than automatic removal.

Each pattern needs a stable versioned `pattern_id`, `evidence_kind` (`countable`|`contextual`), deterministic matcher version, countable threshold or contextual verifier path, and corpus disposition (`absent`|`attested`|`insufficient_evidence`).

## Initial pattern IDs (scaffold)

| pattern_id | kind | Notes |
|---|---|---|
| `transition.stock-conclusion.v1` | countable | Formulaic closing transitions |
| `transition.stock-opener.v1` | countable | Formulaic openers |
| `hedge.performative-certainty.v1` | contextual | Empty certainty / hollow emphasis |
| `list.triadic-padding.v1` | countable | Artificial three-item padding |
| `voice.false-anecdote.v1` | contextual | Fabricated personal experience — always reject if unsupported |

Model-supplied rates are recomputed by the orchestrator; mismatches return `PATTERN_EVIDENCE_MISMATCH`.
