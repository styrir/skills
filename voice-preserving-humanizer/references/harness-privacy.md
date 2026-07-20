# Harness privacy and consent

**Plan:** §6.3, §10 · **DR:** DR-13

## Storage

| Class | Location | Mode |
|---|---|---|
| Profiles / corpus / consent / approvals | `$VOICE_PROFILE_DIR` (default `~/.local/share/voice-preserving-humanizer/profiles/`) | dirs `0700`, files `0600` |
| Skill source | this repository tree | public/shared |
| Raw evaluation outputs | under profile evaluation dirs only | never Git |

## Consent tuple (`voice-consent.v1`)

Valid only for recorded `profile_id`, `harness`, `provider_route`, `resolved_backend_model`, `data_class`, `transcript_policy`, and `scope`. Any field change requires renewed consent.

## Raw vs dynamic

- **Raw** corpus/source/excerpts/verifier passages: exact backend resolution required; fixed-backend consent only.
- **Dynamic route:** fixtures, hash-bound redactions, or overlap-scanned profile summaries without excerpts only.

## Known harness transcript posture

Document per harness at first raw handoff. If location or purge procedure is unknown, record `unknown` / `unavailable` and do not claim ephemeral processing.

| Harness | Transcript policy | Location | Purge |
|---|---|---|---|
| Hermes | document at first raw handoff | TBD per install | TBD |
| Claude Code | document at first raw handoff | TBD per install | TBD |
| Codex | document at first raw handoff | TBD per install | TBD |
