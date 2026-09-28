# Installing jev-guard

Nothing here is applied automatically. Each step changes your live harness configuration. Start in
**observe** (no `--enforce`), read the ledger for a week, then enforce one mode at a time.

## 0. Link the skills

```bash
for h in claude codex grok; do ln -sfn ~/Code/skills/jev ~/.$h/skills/jev; ln -sfn ~/Code/skills/jev-guard ~/.$h/skills/jev-guard; done
```

## 1. Give hooks a key (one time)

Hooks run without `infisical run`. The `jev` client reads `REQUESTY_API_KEY` from the environment first, then
the macOS Keychain item `jev.requesty`. Store the key yourself. It is your credential, and this command reads
it from Infisical and never echoes it:

```bash
security add-generic-password -U -a "$USER" -s jev.requesty -w "$(infisical secrets get REQUESTY_API_KEY --projectId 2588c473-4c4c-4b5a-b0f5-e261184b6b53 --env dev --plain --silent)"
```

The key is briefly visible to `ps` while that one command runs. To avoid that, run `security add-generic-password -U -a "$USER" -s jev.requesty -w` with no value and paste the key when prompted.

Then check it with `python3 ~/Code/skills/jev/scripts/jev.py route-status`, which reports key presence and a
~$0.00001 ping. It never prints the key.

## 2. Claude Code (`~/.claude/settings.json`, merge into `"hooks"`)

```json
{
  "PreToolUse":  [{"matcher": "Bash", "hooks": [{"type": "command", "timeout": 8,
      "command": "python3 ~/Code/skills/jev-guard/scripts/hook.py --harness claude --mode pretool"}]}],
  "PostToolUse": [{"matcher": "WebFetch|WebSearch|Bash", "hooks": [{"type": "command", "timeout": 8,
      "command": "python3 ~/Code/skills/jev-guard/scripts/hook.py --harness claude --mode posttool"}]}],
  "UserPromptSubmit": [{"hooks": [{"type": "command", "timeout": 8,
      "command": "python3 ~/Code/skills/jev-guard/scripts/hook.py --harness claude --mode prompt"}]}]
}
```

PostToolUse screens only the untrusted-content tools by default. Adding `Read` or `mcp__.*` would send
every file or MCP result the agent reads to a hosted model, costing ~0.45 s each, so leave them off until an
approved-roots egress config exists (bead skills-6z3.3).

Grok imports these by default and the adapter re-parses them as Grok. **Don't also add them to Grok**, or turn
off `[compat.claude] hooks` and use step 4.

## 3. Codex (`~/.codex/hooks.json`, merge into `"hooks"`)

```json
{
  "PreToolUse":  [{"matcher": "Bash", "hooks": [{"type": "command", "timeout": 8, "statusMessage": "jev-guard",
      "command": "python3 ~/Code/skills/jev-guard/scripts/hook.py --harness codex --mode pretool"}]}],
  "PostToolUse": [{"matcher": "Bash", "hooks": [{"type": "command", "timeout": 8,
      "command": "python3 ~/Code/skills/jev-guard/scripts/hook.py --harness codex --mode posttool"}]}]
}
```

Then **trust the hooks in Codex's `/hooks` view**; untrusted hooks silently do nothing. While you're there,
note that `~/.codex/hooks.json` currently registers each Xirp hook six times.

## 4. Grok (only if Claude-hook import is off)

`~/.grok/hooks/jev-guard.json`, using the same `{"hooks": {...}}` shape with `--harness grok`. Grok's PreToolUse default timeout is 5 s. The worst case is a Keychain lookup (≤1 s) plus the Jev deadline (3 s,
`JEV_GUARD_TIMEOUT`), which fits. If Grok logs hook timeouts, set `JEV_GUARD_TIMEOUT=2` in the hook's `env`.

## 5. Enforce, one mode at a time

Append `--enforce` to one command after its ledger looks right:
`jq -c 'select(.mode=="pretool" and .block)' ~/.local/state/jev-guard/decisions.jsonl`.

PermissionRequest auto-approval is deliberately not in the snippets above. If you want it, add it to Claude
Code or Codex with a narrow family, for example:

```text
... --mode permission --enforce --allow-family '^(npm|bun|pnpm) (run )?test( |$)|^python3 -m pytest( |$)|^just test$'
```

## Rollback

Remove the entries (or drop `--enforce`) and restart the session. The adapter never writes harness config.
Deleting `~/.local/state/jev-guard/` removes all local state.
