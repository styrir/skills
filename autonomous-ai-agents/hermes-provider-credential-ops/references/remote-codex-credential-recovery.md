# Remote Codex Credential Recovery

Use this when a trusted remote Hermes/Codex host has expired Codex OAuth credentials and a validated local Codex login is available.

## Recovery sequence

Treat the remote CLI update and credential transfer as one maintenance transaction. Do not call the transfer complete if either half is skipped.

1. Run a minimal local `codex exec` smoke. Do not transfer an untested auth file.
2. Discover the remote `codex` binary, its real path, installation method/prefix, and installed version. Resolve the current release from the authoritative package channel.
3. Update the remote CLI through its existing installation mechanism before staging credentials. For npm installs:
   - resolve with `npm view @openai/codex version`
   - record `npm config get prefix` and the binary real path
   - install the resolved version with `npm install -g @openai/codex@<resolved-version>`
   - verify `codex --version` and the binary real path afterward
   Do not create a second installation or update npm itself as an unrelated side effect.
4. Stage `~/.codex/auth.json` to a uniquely named remote temporary path over SSH/SCP. Never print token fields.
5. On the remote host, parse the staged JSON and assert that a non-empty `tokens` mapping exists.
6. Create timestamped, mode-preserving backups of both `~/.codex/auth.json` and `~/.hermes/auth.json`.
7. Install the staged file as remote `~/.codex/auth.json` with mode `0600`.
8. Import the complete `tokens` mapping and `last_refresh` into Hermes using the installed `hermes_cli.auth._save_codex_tokens` helper or a supported equivalent. Do not edit only a credential-pool row.
9. Verify the stores and runtimes separately:
   - `codex --version` reports the resolved current release
   - a minimal remote `codex exec` smoke succeeds without model-catalog decode errors
   - `hermes auth list openai-codex` reports a usable credential
   - a minimal `hermes chat -Q -q` smoke succeeds through `openai-codex`
10. Restart the long-lived Hermes gateway, then verify its service is active and `hermes status --all` reports Codex logged in.

## CLI compatibility contract

Credential validity and CLI compatibility are separate failure surfaces but one operational workflow. Every credential transfer must include the scoped CLI update and post-update smoke. Model-catalog decode errors, including unknown newly introduced reasoning-effort enum variants, fail verification even when inference succeeds. Do not misdiagnose them as bad OAuth, and do not defer the update as optional follow-up.

## SSH stdin pitfall

`codex exec` reads additional prompt text from stdin when stdin is open. If it is launched inside an SSH heredoc that also contains later shell commands, Codex can consume those commands as prompt input, so they never execute.

Use one of these patterns:

- Run the Codex smoke in its own SSH invocation.
- Redirect its stdin from `/dev/null` when the complete prompt is already supplied as an argument.
- Put post-smoke Hermes and gateway verification in a separate SSH call.

Do not claim gateway verification from a combined heredoc unless the post-Codex commands produced independent output.

## Security and hardening

- Treat the transfer as sensitive egress. Require explicit user authorization naming the Codex auth payload and trusted destination host before reading or sending token material.
- Use only the standard local Codex auth store supplied by the user-authorized workflow. Do not probe browser profiles, logs, or unrelated credential stores.
- Resolve updates from the existing package manager's authoritative channel and verify the package identity, configured registry, installation prefix, version, and binary real path before and after installation.
- Preserve `0600` on both credential stores.
- Avoid checksums or diagnostics that expose token material.
- A copied refresh token may share single-use refresh lineage with another Codex client. Prefer a dedicated server-side device-code login for durable isolation when the user can complete it.
- Keep timestamped backups until the refreshed gateway and both smoke tests pass.
