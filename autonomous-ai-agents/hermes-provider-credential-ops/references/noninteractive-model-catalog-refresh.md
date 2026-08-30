# Non-interactive Hermes model catalog refresh

Use when the desktop/TUI model picker is missing a newly released model or
reasoning level, and `hermes model --refresh` cannot run (no TTY).

## Failure mode

```text
Error: 'hermes model' requires an interactive terminal.
It cannot be run through a pipe or non-interactive subprocess.
Run it directly in your terminal instead.
```

Same constraint applies to the interactive model picker itself.

## Caches involved

| File | Purpose | Bust how |
|------|---------|----------|
| `~/.hermes/provider_models_cache.json` | Live `/v1/models` ids per provider (1h TTL, credential fingerprint) | `clear_provider_models_cache()` then live fetch |
| `~/.hermes/models_dev_cache.json` | models.dev registry (reasoning_options, context, cost) | `fetch_models_dev(force_refresh=True)` |
| `~/.hermes/cache/model_catalog.json` | Curated snapshot for docs/picker badges | Usually not the live source of truth |

Profiles under `~/.hermes/profiles/<name>/` have their own `provider_models_cache.json`.

## Python refresh (runtime venv)

```bash
cd ~/.hermes/hermes-agent
./venv/bin/python <<'PY'
from hermes_cli.models import (
    clear_provider_models_cache,
    cached_provider_model_ids,
    provider_model_ids,
)
from agent.models_dev import fetch_models_dev

clear_provider_models_cache()  # wipe all; or pass "xai-oauth"
fetch_models_dev(force_refresh=True)
print("xai-oauth live:", provider_model_ids("xai-oauth", force_refresh=True))
print("warmed cache:", cached_provider_model_ids("xai-oauth", force_refresh=True))

# Optional: picker-shaped payload
from hermes_cli.inventory import build_models_payload, load_picker_context
payload = build_models_payload(load_picker_context(), refresh=True)
print("current", payload.get("provider"), payload.get("model"))
for row in payload.get("providers") or []:
    if "xai" in str(row.get("slug", "")).lower():
        print(row.get("slug"), row.get("total_models"), row.get("models"))
PY
```

Inspect allowed reasoning efforts for a model from the models.dev cache:

```python
from agent.models_dev import _load_disk_cache
xai = _load_disk_cache().get("xai", {}).get("models", {})
for mid, meta in sorted(xai.items()):
    print(mid, meta.get("reasoning"), meta.get("reasoning_options"))
```

Example (as of 2026-08):

- `grok-4.5` → `['low', 'medium', 'high']` (no xhigh)
- `grok-4.6` → `['low', 'medium', 'high', 'xhigh']`
- `grok-4.20-multi-agent-0309` → includes `xhigh`

## Desktop dashboard HTTP API

When Hermes.app is up it usually runs:

```text
python -m hermes_cli.main dashboard --no-open --tui --host 127.0.0.1 --port 9120
```

### Auth

Ephemeral token in the dashboard process environment:

```bash
# macOS example — find PID then env
pgrep -lf 'hermes_cli.main dashboard'
ps eww -p <PID> | tr ' ' '\n' | grep HERMES_DASHBOARD_SESSION_TOKEN
```

Send on every protected call:

```http
X-Hermes-Session-Token: <token>
```

(`Authorization: Bearer <token>` is legacy-compatible.)

`/api/model/info` may respond without auth; `/api/model/options` and `/api/model/set` require the token.

### Refresh options

```bash
TOKEN=...   # from process env — never commit
curl -sS -m 90 \
  -H "X-Hermes-Session-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  "http://127.0.0.1:9120/api/model/options?refresh=1" \
  -o /tmp/hermes-model-options.json
```

Parse the file afterward. Avoid `curl | python` (pipe-to-interpreter policy).

### Set main model

Body schema (`ModelAssignment`):

```json
{
  "scope": "main",
  "provider": "xai-oauth",
  "model": "grok-4.6",
  "confirm_expensive_model": true
}
```

- `scope` is required: `main` or `auxiliary`
- Missing `scope` → HTTP 422
- Success shape: `{"ok": true, "scope": "main", "provider": "...", "model": "...", "base_url": "..."}`

```bash
curl -sS -m 30 -X POST \
  -H "X-Hermes-Session-Token: $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"scope":"main","provider":"xai-oauth","model":"grok-4.6","confirm_expensive_model":true}' \
  "http://127.0.0.1:9120/api/model/set" \
  -o /tmp/hermes-model-set.json
```

### Set reasoning effort (separate from model)

```bash
hermes config set agent.reasoning_effort xhigh
```

Valid levels: `none`, `minimal`, `low`, `medium`, `high`, `xhigh`.

In-session equivalent: `/reasoning xhigh` (add `--global` to persist).

### Verify

```bash
curl -sS -H "X-Hermes-Session-Token: $TOKEN" \
  "http://127.0.0.1:9120/api/model/info" -o /tmp/hermes-model-info.json
# expect model + provider; capabilities.supports_reasoning true for Grok reasoning models

python - <<'PY'
import yaml
from pathlib import Path
cfg = yaml.safe_load(Path.home().joinpath(".hermes/config.yaml").read_text())
print(cfg.get("model"))
print((cfg.get("agent") or {}).get("reasoning_effort"))
PY
```

## xAI provider id reminder

| Provider slug | Lane |
|---------------|------|
| `xai-oauth` | SuperGrok / Premium+ OAuth (typical desktop default) |
| `xai` | Direct `XAI_API_KEY` API-key lane |

Do not set OAuth models under `xai` and expect SuperGrok auth to apply.

## Session lifecycle caveat

`POST /api/model/set` updates disk config and dashboard “current model” immediately.
Already-running TUI slash workers (`python -m tui_gateway.slash_worker --model grok-4.5 …`) keep the old model until the chat/session is restarted. After a switch, tell the user to open a new chat or re-open the model picker.

## Config write path

`~/.hermes/config.yaml` remains agent-write-protected via `patch`/`write_file`.
Prefer:

- `hermes config set model.default …`
- `hermes config set model.provider …`
- `hermes config set agent.reasoning_effort …`
- or authenticated `POST /api/model/set` when the dashboard is live
