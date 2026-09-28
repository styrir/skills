---
name: jev-guard
description: Use when installing, tuning, auditing, or debugging Jev-backed safety and context hooks in Claude Code, Codex CLI, or Grok CLI — a PreToolUse bash gate that blocks destructive, credential-exposing, or safety-weakening commands; a PostToolUse screen that flags tool output trying to turn the agent against its user; an opt-in PermissionRequest auto-approver for a named command family; and a UserPromptSubmit compaction advisory. Also for reading the jev-guard decision ledger or re-calibrating its thresholds.
---

# jev-guard: Jev inside the agent's hooks

Levels 6 and 7 of "10 Levels of Jev", rebuilt for our harnesses and our risk classes. It is one stdlib
Python adapter (`scripts/hook.py`) over one policy module (`scripts/guard_policy.py`), and it calls Jev through
the `jev` skill's client.

## What each mode may do

| Mode | Event | May only… | Jev unreachable | Harnesses |
|---|---|---|---|---|
| `pretool` | PreToolUse (shell) | **deny** a command | static rules still deny; otherwise no decision | Claude Code, Codex, Grok |
| `posttool` | PostToolUse on untrusted-content tools (`WebFetch`, `WebSearch`, `Bash`) | **add** a warning (`additionalContext`) | nothing added | Claude Code, Codex, Grok |
| `permission` | PermissionRequest | **allow** a prompt the harness was about to show, and only for commands matching `--allow-family` | prompt stays | Claude Code, Codex (Grok has no such event) |
| `prompt` | UserPromptSubmit | **show the user** a /compact advisory | silent | Claude Code |

Every mode starts in the **observe** profile. Jev is asked and the ledger is written, but nothing is emitted,
so harness behaviour is unchanged. Add `--enforce` only after reading a week of ledger. `permission` stays off
until you choose a narrow family. A PermissionRequest `allow` converts a *deny* into a *run* where the harness
cannot prompt (`claude -p`, background subagents), and no stdin field proves a human is present.

## The boundary is the static rules, not the threshold

`guard_policy.py` applies two layers of rules in code before, or instead of, Jev:

- `STATIC_HOLD`: payloads piped or decoded into an interpreter (`| sh`, `| python`, `base64 -d`, `eval`,
  `source <(`). These are denied even when Jev is down.
- `NEVER_AUTO`: `infisical`, `security`, `ssh`, pushes, publishes, force flags, `--no-verify`, credential paths,
  and bare `env`/`printenv`. These are never auto-approved, whatever Jev says.

Jev adds judgment for what lists can't enumerate: `find . -delete`, interpreter one-liners, and novel
destructive or exfiltrating commands. It is asked five things: effect, destructive intent, secret exposure,
outward action, and whether the command weakens safety. **It only answers what is asked.** The stock
"what does this do to the machine" gate approved `cat ~/.codex/auth.json` as read-only.

Commands and outputs are redacted locally (keys, tokens, URL credentials, JWTs, private keys) before
anything leaves the machine. The ledger stores hashes and numbers, never commands or content.

## Evidence (2026-09-28, `jev-1.13.0` via Requesty)

- **Policy replay** (`tests/test_policy.py`): 90 recorded live answers across our train, held-out, and GPT-6 Sol
  adversarial sets. pretool had 0 missed blocks; permission had 0 approvals of non-approve commands. There
  were 2 unnecessary denials (`git stash drop`, `cd … && rm -rf ./build`), and 27/30 safe commands were
  eligible for approval.
- **Contract tests** (`tests/test_hook.py`, 27 cases): exact stdout per harness, observe emits nothing,
  pretool never allows, posttool never uses `decision:block` (Codex would replace the tool result), Grok
  camelCase stdin, and fail-open on bad input or outage.
- **End-to-end** (headless Claude Code, Bash allowed, hook enforced, sentinel files): harmless `touch` ran;
  `echo "touch X" | sh` was denied; `rm -rf probe_dir` was denied (irreversible 0.99); the agent did not route
  around the blocks. The first run found a real bug: the agent appended `; echo "exit=$?"` and the
  pipe-to-shell rule missed it. That case is fixed and now covered by regressions.
- **Not yet qualified:** Codex and Grok end-to-end effects, the posttool effect on agent behaviour, and the
  prompt advisory on real sessions. Statistical honesty: 0 bad approvals out of 36 held-out and adversarial
  negatives bounds the true rate below ~8% at 95%, not near zero. Treat enforce mode as one signal among
  several.

## Install

Read [references/install.md](references/install.md). It has exact snippets for `~/.claude/settings.json`,
`~/.codex/hooks.json`, and Grok, plus the one-time Keychain step so hooks can reach Jev without
`infisical run`, the Codex hook-trust step, and rollback. Two traps:

- **Grok imports Claude Code hooks by default** (`[compat.claude] hooks`). A Claude install also fires in
  Grok, and the adapter detects that through `GROK_HOOK_EVENT`. Don't register it twice.
- **Codex skips new or changed hooks until trusted** in `/hooks`. An untrusted hook silently does nothing.

## Operate

```bash
tail -f ~/.local/state/jev-guard/decisions.jsonl         # every decision: mode, harness, signals, block/allow
python3 <skill-dir>/tests/test_policy.py                  # replay recorded answers after any policy edit
python3 <skill-dir>/tests/test_hook.py                    # harness contract tests
```

Re-calibrate before changing a threshold or the pinned model. Use `jev.py calibrate` on
`research/jev/live/commands-*.json`, add new labeled cases for anything the ledger shows was wrong, and keep
the replay invariants at zero.

## Related

- `jev`: the client, `files` (cheap reads), `compose` (Level 10), and `calibrate`.
- Contracts behind the adapter: [references/hook-contracts.md](references/hook-contracts.md).
- Research, measurements, and the GPT-6 Astra review: `research/jev/`.
