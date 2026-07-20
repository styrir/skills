# voice-preserving-humanizer

Local skill that revises AI-assisted or over-smoothed prose while preserving the author's demonstrated voice.

## Status

Scaffolded from the dual-approved plan. Implementation is in progress under Beads epic `skills-cfw`.

- Plan: [`docs/plans/voice-preserving-humanizer.md`](../docs/plans/voice-preserving-humanizer.md)
- Dual-review synthesis: [`docs/reviews/voice-preserving-humanizer-dual-review-synthesis.md`](../docs/reviews/voice-preserving-humanizer-dual-review-synthesis.md)
- Final plan SHA-256: `bc26bca227c496e90e2d219de096d88b1ad6f3a7e0a77120f998cec0b6d62dbe`

## Layout

```text
voice-preserving-humanizer/
├── SKILL.md
├── README.md
├── THIRD_PARTY_NOTICES.md
├── references/
├── scripts/
├── templates/
└── tests/
```

## Design rulings (candidate repos)

| Candidate | Ruling |
|---|---|
| `dannwaneri/voice-humanizer` | Primary conceptual base (reimplement; no runtime dep) |
| `harshaneel/humanize` | Borrow selected hypothesis-extraction mechanism only |
| `ssamba1/untell` | Borrow protected-span / semantic-gate concepts only |
| `blader/humanizer` | Advisory AI-pattern catalog only |
| `rudra496/StealthHumanizer` | No runtime dependency; defer UI |
| `lynote-ai/humanize-text` | Excluded (translation-chain) |
| `anasu1/text-humanizer` | Permanently excluded (hostile) |

## Private data

Corpus, consent, approvals, and evaluation artifacts live under `$VOICE_PROFILE_DIR` (default `~/.local/share/voice-preserving-humanizer/profiles/`). Never commit them.

## Development

```bash
cd voice-preserving-humanizer
python3 -m unittest discover -s tests -v
```

Deterministic scripts use the Python standard library only and must not perform network I/O.

## Activation

Harness symlinks are deferred until gates pass.
