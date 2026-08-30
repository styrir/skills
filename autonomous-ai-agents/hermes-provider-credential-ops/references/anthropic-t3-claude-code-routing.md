# Anthropic subscription routing via Claude Code / T3 Code pattern

Session lesson: the user expected Hermes Anthropic usage to consume the same first-party Claude Code/T3 Code subscription path they were already logged into, not the direct Anthropic dashboard OAuth / extra-usage lane. A `dashboard_pkce` credential can be 429-rate-limited while the user's Claude subscription path is conceptually still the desired route.

## Diagnosis checklist

Run these as separate checks; do not conflate their meanings:

```bash
hermes status
hermes auth list anthropic
command -v claude
claude --version
claude auth status
```

Interpretation:
- `hermes status` showing provider/model only identifies the current Hermes backend.
- `hermes auth list anthropic` showing `dashboard PKCE oauth rate-limited (429)` means the direct Hermes Anthropic OAuth/dashboard credential is exhausted/rate-limited.
- `claude auth status` is the gate for first-party Claude Code routing. If it reports `loggedIn=false`, the correct failure is "fix Claude Code auth", not "fall back to direct Anthropic OAuth".

## Implementation shape

For T3-style routing, adapt the native Anthropic OAuth/setup-token path so `build_anthropic_client(...)` returns a small Anthropic-compatible bridge client when:

- the key is an OAuth/setup token (`_is_oauth_token(api_key)`), and
- the base URL is empty/default or first-party Anthropic/Claude (`api.anthropic.com`, `claude.ai`, etc.).

The bridge should call the official CLI:

```bash
claude --print \
  --output-format json \
  --model <normalized-claude-model> \
  --permission-mode bypassPermissions \
  --no-session-persistence \
  --setting-sources user,project,local \
  --append-system-prompt '<sanitized system text>'
```

Pass the conversation prompt on stdin. Parse the JSON `result` field into a minimal Anthropic Message-like object with `content=[SimpleNamespace(type="text", text=...)]`, `stop_reason="end_turn"`, and a no-op `close()` method on the client. This preserves the surrounding Hermes Anthropic response-normalization path.

## Prompt and identity hygiene

- Do not prepend a local Hermes-branded identity block on this path.
- Claude Code already supplies its own first-party system identity.
- If existing Anthropic kwargs builder injected `You are Claude Code, Anthropic's official CLI for Claude.`, strip that before passing `--append-system-prompt` to avoid double identity.
- Sanitize local branding in appended system text: replace/remove `Hermes Agent`, `hermes-agent`, and `Nous Research` where it would travel over the Anthropic-bound Claude Code path.

## Fallback rule

Do **not** silently fall back from this bridge to direct Anthropic SDK OAuth/dashboard auth. If `claude auth status` fails or reports logged out, raise a clear error like:

```text
Claude Code first-party auth is unavailable, so Hermes is refusing to fall back to the direct Anthropic OAuth/dashboard extra-usage path. Run `claude auth login` or fix Claude Code auth.
```

This avoids the confusing state where the user asks for subscription usage but receives dashboard extra-usage / 429 behavior.

## Overwrite-proof local repair pattern

If this is a local runtime patch rather than an upstreamed Hermes change, keep the repair mechanism outside the Hermes checkout so `hermes update` cannot overwrite it:

- `~/.hermes/scripts/apply-t3-claude-code-routing.py` — idempotent patcher that inserts/replaces the marked code block and hook.
- `~/.hermes/scripts/apply-t3-claude-code-routing.sh` — wrapper using the Hermes runtime venv Python.
- `~/Library/LaunchAgents/<label>.plist` on macOS with `WatchPaths` pointing at `~/.hermes/hermes-agent/agent/anthropic_adapter.py`.

The patcher should:
- use explicit `BEGIN/END LOCAL ... PATCH` markers,
- replace an existing marked block rather than duplicating it,
- add missing imports (`shutil`, `SimpleNamespace`) idempotently,
  - Check imports as exact top-level lines, not substring presence: a local `import shutil` inside `run_oauth_setup_token()` can otherwise make the repair script skip the global import while the T3 bridge still calls `shutil.which` at module scope.
- insert the `build_anthropic_client` hook only if absent,
- run `py_compile` on the modified file.

Verification:

```bash
~/.hermes/scripts/apply-t3-claude-code-routing.sh
~/.hermes/hermes-agent/venv/bin/python -m py_compile agent/anthropic_adapter.py
~/.hermes/hermes-agent/venv/bin/python -m pytest tests/agent/test_anthropic_adapter.py -q -o 'addopts='
plutil -lint ~/Library/LaunchAgents/<label>.plist
```

## Regression tests to add when editing Hermes source

- OAuth/setup-token `build_anthropic_client(...)` returns the Claude Code bridge and does not instantiate `anthropic.Anthropic`.
- Explicit native `https://api.anthropic.com/v1` also routes through the bridge.
- The bridge invokes `claude --print --output-format json --append-system-prompt ...`.
- Appended system prompt contains no `Hermes Agent` / `Nous Research` branding and no duplicate Claude Code identity line.
- If `claude auth status` reports logged out, bridge raises a clear no-fallback error.
