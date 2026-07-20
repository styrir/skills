# Third-party notices

This skill reimplements selected concepts after quarantined inspection. It does **not** vendor runtime dependencies from the candidate repositories.

Inspection date: 2026-07-15
Inspection staging: `/tmp/skillspector-candidates/voice-tools/`

## Conceptual sources (MIT at inspected commits)

| Project | Inspected commit | Use |
|---|---|---|
| [dannwaneri/voice-humanizer](https://github.com/dannwaneri/voice-humanizer) | `1b24c4ded4237ea5bd6135f131976b61f74bb015` | Corpus-first voice review concepts |
| [harshaneel/humanize](https://github.com/harshaneel/humanize) | `4ec797314537ec9c2105f276d4561d240a0390ba` | Hypothesis-extraction inspiration |
| [ssamba1/untell](https://github.com/ssamba1/untell) | `64d7fdc5a3ff9bceb0960fb24661f207bf6148e9` | Protected-span / semantic-gate concepts |
| [blader/humanizer](https://github.com/blader/humanizer) | `1b48564898e999219882660237fde01bf4843a0f` | Advisory AI-pattern taxonomy |
| [rudra496/StealthHumanizer](https://github.com/rudra496/StealthHumanizer) | `1aacbda6e2f66afbdcb6714a85347307068373e9` | Deferred style-feature ideas only |

Before copying any source text or substantial prompt material from an upstream tree:

1. Re-verify the license at the exact commit.
2. Preserve copyright notices.
3. Record the copied elements in this file.
4. Run SkillSpector static analysis and semantic review (plan §10).

## Exclusions

- `lynote-ai/humanize-text` — architectural exclusion (translation-chain drift).
- `anasu1/text-humanizer` — permanent security exclusion; hostile behavior observed. Do not acquire further code. Defang any hostile URLs in documentation.

## Current copied upstream source

None. Scaffold only; no upstream source files have been copied into this skill tree yet.
