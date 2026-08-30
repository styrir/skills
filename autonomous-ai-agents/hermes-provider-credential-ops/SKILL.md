---
name: hermes-provider-credential-ops
description: "Diagnose and fix Hermes provider/credential failures (MoA, model switching, fallback, credential pools), refresh stale model catalogs non-interactively, and work around config.yaml write-protection. Use when a /moa run, model call, or provider switch fails with 401/429/auth errors; when the model picker is missing new models/reasoning levels; or when you need to change Hermes provider/MoA config but patch/write_file refuse config.yaml."
version: 1.3.0
author: agent
license: MIT
metadata:
  hermes:
    tags: [hermes, moa, providers, credentials, auth, troubleshooting, config, models, xai]
    related_skills: [hermes-agent, claude-code]
---

# Hermes Provider & Credential Operations

Diagnosing why a Hermes model/provider call failed, and how to fix provider/MoA configuration given that `config.yaml` is agent-write-protected. Complements the bundled `hermes-agent` skill (which is protected and cannot be edited) — load that for the general CLI/feature reference, load this for the provider/credential failure lane.

## When to use

- A `/moa <prompt>` one-shot dies with 401 / 429 / auth errors.
- A model call, fallback, or provider switch fails and you need to know *which credential* is the problem.
- You diagnosed a provider/MoA config fix but `patch`/`write_file` refused to edit `~/.hermes/config.yaml`.
- The Hermes model picker is missing a newly released model (e.g. Grok 4.6) or a reasoning level (e.g. `xhigh` / extra high) and needs a catalog refresh + optional non-interactive model switch.

## Core principle: diagnose at the credential layer, not by re-running

Provider failures are almost always credential/config problems, **not** your repo, prompt, or code. The fastest signal is the credential pool, not another failed call.

Read `~/.hermes/auth.json` → `credential_pool`. Each provider maps to a list of credential entries; each entry carries:
- `last_status` — `ok`, `exhausted`, or `null` (untested)
- `last_error_code` — e.g. `401`, `429`
- `last_error_message` — the verbatim provider error
- `source` — where the cred came from (`env:OPENROUTER_API_KEY`, `manual:dashboard_pkce`, `device_code`, …)

A provider whose every pooled entry is `exhausted` has no usable backend — that's why the call fails. `active_provider` at the top tells you which provider this session is actually using (it may be healthy while a *different* provider used by MoA/fallback is dead).

Validate model slugs against `~/.hermes/provider_models_cache.json` (per-provider `models` list) before writing any config — malformed slugs are a common silent failure.

## MoA (`/moa`) failure diagnosis

`/moa` is two-stage: N **reference models** queried in parallel → one **aggregator** synthesizes. A failure in *either* stage kills the turn.

Start with memory/context if this is a known local routing customization: for Brooks's runtime, Anthropic subscription routing is intentionally T3-style through Claude Code (`claude --print` / SDK), xAI uses `xai-oauth`, and Codex uses `openai-codex` OAuth. Do not diagnose these as ordinary missing API keys until you have checked the current runtime and the relevant remembered patch/repair contract.

1. `hermes moa list` — shows the preset's reference models + aggregator (provider:model slugs).
2. Map each slug's provider to its `credential_pool` health (above), and check provider-specific auth (`hermes auth list openai-codex`, `hermes auth list xai-oauth`, `claude auth status` for the Claude Code path).
3. Inspect the failing request/debug dump for the actual URL/model before blaming credentials. A request to `moa://local/chat/completions` with `model: default` means the live Hermes process is still using the virtual MoA provider as the main request path; that is different from an `openai-codex:gpt-5.5` OAuth failure.
4. Common causes:
   - **Stale live model routing after switching away from MoA**: config or the running process still carries `provider=moa` / `base_url=moa://local`, so the request goes to the virtual provider and fallback may later surface an unrelated OpenAI API-key 401. `/new` is not enough for provider/client-code changes; fully `/quit` and restart Hermes, then confirm `model.provider`, `model.default`, and `model.base_url` with `hermes status --all` / config inspection. If disk config still has a non-MoA provider with `base_url: moa://local`, clear it with `hermes config set model.base_url ""`.
   - **401 "Incorrect API key" with `sk-proj-...` after MoA connection errors** → usually a fallback/API-key path was reached after the virtual MoA route failed; do not confuse this with Codex OAuth, which does not use that `sk-proj` key.
   - **401 "User not found"** on an OpenRouter reference model → the OpenRouter key is revoked/dead (not transient). Replace via `hermes auth` or `~/.hermes/.env`.
   - **429 rate_limit_error** on the aggregator (Anthropic request IDs look like `req_011C…`) → aggregator creds rate-limited/exhausted. For Brooks's T3 path, verify the Claude Code route before accepting direct Anthropic extra-usage semantics.
   - **Malformed slug**, e.g. `anthropic/claude-opus-4.8` (dot + prefix) vs the real `claude-opus-4.8`/local normalized slug expected by the selected provider.
   - **Wrong xAI provider id**: `provider: xai` is the direct API-key lane; use `provider: xai-oauth` for logged-in SuperGrok/OAuth models such as `grok-4.3`.
   - **`provider: <name>` with no plugin** — valid provider names = the dirs under `~/.hermes/hermes-agent/plugins/model-providers/`. There is **no `requesty` plugin**; route OpenAI-compatible routers through `custom` (see below).
5. Prove the actual slot health before changing config: run small provider-specific smokes through the same helper path where possible (`openai-codex:gpt-5.5`, `xai-oauth:grok-4.3`, `anthropic:claude-opus-4.8`), then a tiny MoA aggregate smoke. If all slots pass but the CLI still fails, suspect stale live process/client state and restart.
6. Fix with `hermes moa configure <preset>` (interactive picker) only after you know the preset itself is wrong. Pick slots from providers whose pool/auth checks are healthy.

## config.yaml is write-protected from the agent

`patch`/`write_file` **refuse** `~/.hermes/config.yaml` ("Agent cannot modify security-sensitive configuration"). Deliberate: stops an LLM reconfiguring its own security/provider settings mid-task. Use the CLI surface instead:

- `hermes config set <section.key> <value>` — scalar settings.
- Interactive wizards for structured blocks: `hermes moa configure`, `hermes model`, `hermes setup`, `hermes tools`, `hermes auth`.
- `hermes config edit` — opens in `$EDITOR` for the **user** (not the agent).

These wizards are interactive (curses/prompt pickers) — they need a real PTY and block on keystrokes. Don't drive them blind from a non-interactive tool call. When you've diagnosed a fix but can't apply it, hand the user the exact command. `~/.hermes/.env` is NOT under this guard — secret keys there can be read/edited normally.

## Non-interactive model catalog refresh + switch

`hermes model` / `hermes model --refresh` **require an interactive TTY**. From agent tools they exit with: `Error: 'hermes model' requires an interactive terminal.` Do not retry with a PTY hope — use the disk-cache + API path below.

### What is stale

| Cache | Path | Role |
|-------|------|------|
| Provider live IDs | `~/.hermes/provider_models_cache.json` | 1h TTL per-provider `/v1/models` lists (keyed by credential fingerprint) |
| models.dev metadata | `~/.hermes/models_dev_cache.json` | Reasoning options, context windows, display metadata |
| Curated catalog snapshot | `~/.hermes/cache/model_catalog.json` | Static curated ids (not the sole live source) |

Reasoning effort is **not** a model id. It lives in `agent.reasoning_effort` (`none|minimal|low|medium|high|xhigh`). Per-model allowed efforts come from models.dev `reasoning_options` (e.g. `grok-4.6` → low/medium/high/**xhigh**; `grok-4.5` → low/medium/high only). Switching the default model does not change reasoning; set both when the user wants “Grok 4.6 + extra high”.

### Refresh without a TTY

Run against the installed runtime (`~/.hermes/hermes-agent/venv/bin/python`):

```python
from hermes_cli.models import clear_provider_models_cache, cached_provider_model_ids, provider_model_ids
from agent.models_dev import fetch_models_dev

clear_provider_models_cache()  # or clear_provider_models_cache("xai-oauth")
fetch_models_dev(force_refresh=True)
live = provider_model_ids("xai-oauth", force_refresh=True)
# also warm disk cache:
cached_provider_model_ids("xai-oauth", force_refresh=True)
```

Optional inventory check (picker payload the desktop uses):

```python
from hermes_cli.inventory import build_models_payload, load_picker_context
payload = build_models_payload(load_picker_context(), refresh=True)
```

### Desktop/dashboard API (when Hermes.app is running)

Typical local dashboard: `http://127.0.0.1:9120` (`hermes … dashboard --tui --host 127.0.0.1 --port 9120`).

1. Read the live session token from the dashboard process env: `HERMES_DASHBOARD_SESSION_TOKEN=…` (ephemeral per start; do not hardcode).
2. Auth header: `X-Hermes-Session-Token: <token>` (legacy `Authorization: Bearer <token>` also works).
3. Refresh picker data: `GET /api/model/options?refresh=1`
4. Set main model: `POST /api/model/set` with body:
   ```json
   {"scope":"main","provider":"xai-oauth","model":"grok-4.6","confirm_expensive_model":true}
   ```
   `scope` is **required** (`main` | `auxiliary`). Without it you get a 422.
5. Set reasoning separately (config CLI, not model/set):
   ```bash
   hermes config set agent.reasoning_effort xhigh
   ```
6. Verify: `GET /api/model/info` and `hermes config show` / read `model.default` + `agent.reasoning_effort`.

Write API JSON to a temp file, then parse — do **not** `curl | python` (security scanners flag pipe-to-interpreter).

### After a switch

- Existing TUI/desktop slash-worker processes keep the old `--model …` until the chat is restarted / new session. Tell the user to reopen the model picker or start a new chat.
- Prefer `provider: xai-oauth` for SuperGrok OAuth models; `provider: xai` is the direct API-key lane.

Full recipe + xAI effort map: `references/noninteractive-model-catalog-refresh.md`.

## Using a non-built-in provider (e.g. Requesty) via `custom`

Routers exposing an OpenAI-compatible endpoint that lack a dedicated plugin go through the `custom` provider. Add under the `providers:` map in config.yaml (user-applied, since agent can't write it):
```yaml
providers:
  requesty:
    base_url: https://router.requesty.ai/v1
    api_key: <key>      # or env:REQUESTY_API_KEY
```
then reference as `custom:requesty` in model/MoA slots.

## Anthropic subscription / T3 Code-style routing

When the user expects Anthropic subscription-backed Claude usage to behave like T3 Code / Claude Code, do **not** treat a Hermes `anthropic` OAuth/dashboard credential as equivalent to first-party Claude Code auth. A 429 on `dashboard_pkce` / direct Anthropic OAuth is an extra-usage/dashboard lane problem, not proof the user's logged-in Claude subscription cannot be used.

Preferred shape for this class of fix:
1. Confirm the active runtime/provider with `hermes status`, then inspect `hermes auth list anthropic` and `claude auth status` separately.
2. If implementing or restoring T3-style routing, route first-party Anthropic OAuth/setup-token execution through the official Claude Code CLI (`claude --print --output-format json ...`) rather than extracting tokens and hand-rolling Anthropic HTTP.
3. Use `--append-system-prompt` for sanitized appended system text; let Claude Code keep its native first-party identity and avoid Hermes/Nous branding on Anthropic-bound prompts.
4. Refuse silent fallback from Claude Code subscription routing to the direct Anthropic OAuth/dashboard extra-usage path. Do **not** gate on `claude auth status`; the Claude Code runtime (`claude --print`) is the auth boundary and should surface its own `/login` error if it cannot run.
5. MoA slots are literal provider IDs. A Grok slot configured as `provider: xai` uses the direct `XAI_API_KEY` route, not the logged-in SuperGrok OAuth route; use `provider: xai-oauth` for the authenticated route.
6. For local runtime customizations likely to be overwritten by `hermes update`, store the reapply script outside `~/.hermes/hermes-agent` (for example under `~/.hermes/scripts/`) and optionally attach a LaunchAgent/WatchPaths repair job to re-run it after the target file changes.

Session-derived implementation/repair pattern: `references/anthropic-t3-claude-code-routing.md`.

## Remote Codex recovery when a server gateway has an expired token

When a remote Hermes gateway reports `openai-codex` HTTP 401 `token_expired`, distinguish the two credential stores:

- Codex CLI credentials: `~/.codex/auth.json`
- Hermes-owned credentials: `~/.hermes/auth.json`

Credential transfer is sensitive egress. Before reading or sending token material, require explicit user authorization for the Codex auth payload and the named trusted destination host. Do not infer approval from a generic troubleshooting request, and do not source credentials from browser profiles, logs, or other unintended stores.

Hermes intentionally does **not** auto-import `~/.codex/auth.json` during pool loading, because Codex refresh tokens are single-use and sharing them with Codex CLI/VS Code can cause refresh-token races. Copying only `~/.codex/auth.json` therefore does not repair a running Hermes gateway.

If a trusted local Codex login is available and an immediate repair is needed, treat CLI compatibility and credential transfer as one maintenance transaction. A token-transfer workflow is not complete while the remote Codex CLI is stale:

1. Verify the local login with a real, minimal `codex exec` smoke test; do not copy unvalidated credentials.
2. Before transferring credentials, discover the remote Codex binary, installation method/prefix, installed version, and current release. For npm installs, resolve the release with `npm view @openai/codex version` and update through the existing prefix with `npm install -g @openai/codex@<resolved-version>`. Do not create a parallel installation or update npm itself as a side effect.
3. Verify `codex --version` resolves to the updated binary. If the update is blocked, report the transfer workflow as incomplete rather than silently continuing with a stale client.
4. Back up both the remote `~/.codex/auth.json` and `~/.hermes/auth.json` with mode `0600`.
5. Transfer the validated Codex auth file securely to the remote `~/.codex/auth.json`, without printing token contents.
6. Import the tokens into Hermes's own store using the installed Hermes auth persistence helper (`hermes_cli.auth._save_codex_tokens`) or an equivalent supported import path. Preserve the full `tokens` mapping and `last_refresh`; do not hand-edit only the pool entry.
7. Verify the standalone CLI with a minimal remote `codex exec` smoke. Its output must be free of model-catalog decode errors such as unknown reasoning-effort enum variants; successful inference alone is insufficient when refresh errors are present.
8. Verify with `hermes auth list openai-codex`, then run a real default-model smoke such as `hermes chat -Q -q "Reply with exactly: ..."`.
9. Restart the long-lived gateway and verify `systemctl --user is-active hermes-gateway.service`, `hermes status --all`, and fresh post-restart logs. A CLI smoke alone does not prove the gateway reloaded its in-memory credentials.

Current Hermes versions may display `hermes login` in help while the command itself has been removed; `hermes auth add openai-codex` starts a fresh device-code flow rather than importing Codex CLI credentials. Prefer a dedicated server-side device-code login when the user can complete browser approval. A temporary import from another trusted Codex login may share refresh-token lineage with that client, so record this as a hardening follow-up rather than assuming the credentials are independent.

Full update, transfer, verification, and SSH-stdin procedure: `references/remote-codex-credential-recovery.md`.

## Pitfalls

- Don't conclude "my code/prompt is broken" from a provider 401/429 — check `credential_pool` first.
- Don't record "provider X is broken" as a durable fact — a dead key or spent quota is environment state the user fixes; capture the *fix* (replace key / `hermes auth reset`), not a refusal.
- Don't attempt to `patch` config.yaml after the first refusal — switch to `hermes config set` / the right wizard immediately.
- Verify provider names against the plugin dir and slugs against `provider_models_cache.json` before proposing a config edit.
- Don't run `hermes model --refresh` from agent tools expecting it to work non-interactively — use the Python cache bust + dashboard API path.
- Don't treat “extra high” as a model slug — it is `reasoning_effort: xhigh`, and only some models advertise it in models.dev.
- Don't assume a successful `/api/model/set` rewires already-running session workers; new chat / reopen picker is required.
- Don't hardcode `HERMES_DASHBOARD_SESSION_TOKEN`; scrape it from the live dashboard process each time.

Detailed field map, the live OpenRouter key probe, and a worked end-to-end MoA diagnosis: `references/moa-credential-diagnosis.md`.

Non-interactive model catalog refresh + desktop `/api/model/*` set flow: `references/noninteractive-model-catalog-refresh.md`.
