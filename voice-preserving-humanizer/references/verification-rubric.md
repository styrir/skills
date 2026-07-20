# Semantic verification rubric

**Plan:** §7.4, §9 · **DR:** DR-12

## Fresh context (mandatory)

The verifier receives only the original passage, proposed replacement, bounded adjacent context needed for qualifications, profile summary (no reviser transcript/reasoning), and this rubric.

## Structured verdict fields

For each edit / applicable claim: factual additions, modality, qualification, causality, conclusion, register, and each contextual AI-pattern claim as `confirmed` | `not_confirmed` | `uncertain`.

## Outcomes

| Result | Effect |
|---|---|
| failure / `not_confirmed` on required claim | reject |
| `uncertain` | `review_required` |
| all pass | may proceed only if deterministic gates also pass |

Language-model verification **cannot** override deterministic failures. Missing verifier output cannot yield `accepted`. A different backend is optional and requires separate configuration + consent.
