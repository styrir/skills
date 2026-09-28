# Hook contracts behind `hook.py`

These contracts were verified on 2026-09-28 against:
- Claude Code 2.1.283, using the live hooks docs.
- Codex CLI 0.157.1, using the `rust-v0.157.1` source: `codex-rs/hooks/src/events/*`, `core/src/hook_runtime.rs`.
- Grok CLI 1.0.42 alpha, using the shipped docs (`~/.grok/docs/user-guide/10-hooks.md`) and `grok inspect`.
- oh-my-pi 18.1.19, using `src/extensibility/*`.

Re-verify after any harness upgrade.

| | Claude Code | Codex 0.157.1 | Grok 1.0.42 | OMP 18.1.19 |
|---|---|---|---|---|
| Shell tool | `Bash` | `Bash` (unified `exec_command` matches as `Bash`) | `run_terminal_command` (matcher `Bash` aliases) | `bash` |
| Command field | `tool_input.command` | `tool_input.command` | `toolInput.command` | `event.input.command` |
| Deny a tool call | `hookSpecificOutput.permissionDecision:"deny"` + `permissionDecisionReason` | same (legacy `decision:block` also works) | same, or `{"decision":"deny","reason":…}` | return `{block:true, reason}` |
| Add a warning after a tool | `hookSpecificOutput.additionalContext` | `additionalContext`. **`decision:"block"` REPLACES the tool result** | `additionalContext` (a non-zero exit drops it) | return replacement `content` |
| Approve a permission prompt | `PermissionRequest` → `decision.behavior:"allow"`; empty output means the prompt shows; where it can't prompt, **no decision = deny** | same; `updatedInput`/`updatedPermissions`/`interrupt` fail closed | **no PermissionRequest event** | n/a |
| Message to the user | `systemMessage` | `systemMessage` (UI warning) | UserPromptSubmit block reason only (`systemMessage` unverified) | `ctx.ui.notify` |
| Crash / timeout | fails open | fails open (run marked failed) | fails open, except a stdout `deny` is honored on any exit | **`tool_call` fails CLOSED** (30 s default) |
| Default timeout | 600 s (30 s UserPromptSubmit) | 600 s | **5 s** PreToolUse | 30 s |
| Gotchas | stdout must be exactly the JSON; hooks' deny beats allow | **new/changed hooks are skipped until trusted in `/hooks`**; matching hooks run concurrently | **imports `~/.claude/settings.json` hooks by default**; `GROK_HOOK_EVENT` env identifies it | settings.json command hooks are not run; needs a TS extension |

Other observed facts that the adapter depends on:
- Claude Code transcripts are JSONL. Context tokens are `input_tokens + cache_creation_input_tokens + cache_read_input_tokens`, taken from the last non-sidechain assistant `message.usage`. The transcript is written asynchronously and is not a stable interface.
- Agents rewrite commands before running them, for example by appending `; echo "exit=$?"`. Rules must match shell metacharacter boundaries, not end-of-string.

## Not covered yet (tracked in Beads)
- An OMP/pi adapter. OMP needs a TS extension that catches its own errors and timeouts, because `tool_call` fails closed. pi has two installs on this machine (Homebrew 0.87.1 and Volta 0.80.2, depending on PATH). The ten-levels L7 cut-point extension mutates `event.customInstructions`, which the installed pi runtime ignores, so a port must use the supported compaction API.
- End-to-end effect runs for Codex and Grok.
