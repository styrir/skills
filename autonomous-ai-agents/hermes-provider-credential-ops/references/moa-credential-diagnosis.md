# MoA credential diagnosis — worked recipe & field map

Detailed companion to the umbrella SKILL.md. Captured from a real `/moa` failure on 2026-06-28.

## The failure that prompted this

`/moa <prompt>` produced:
- Reference model `openrouter:deepseek/deepseek-v4-pro` → `401 - {"error":{"message":"User not found.","code":401}}`
- Aggregator → `HTTP 429 rate_limit_error`, retried 3× (2.8s → 5.3s backoff) then exhausted, request_id `req_011CcUi6efPLJEjUFEeTjD1p` (Anthropic-style ID → aggregator was Anthropic).

Both were credential problems. The repo under review was irrelevant; `cargo check` passed clean. A request debug dump was written to `~/.hermes/sessions/request_dump_<ts>.json` with `url: moa://local/chat/completions`, `error.type: rate_limit_error`, `status_code: 429`.

## auth.json field map

`~/.hermes/auth.json`:
- `active_provider` — provider this session uses (can be healthy while MoA's providers are dead).
- `providers{}` — OAuth token bundles per provider (access/refresh tokens, expiry).
- `credential_pool{}` — the diagnostic gold. `provider -> [ {id, label, auth_type, source, last_status, last_status_at, last_error_code, last_error_message, base_url, secret_fingerprint}, ... ]`.

Quick extract (read-only, no tools beyond python):
```python
import json
d=json.load(open(os.path.expanduser('~/.hermes/auth.json')))
print("active:", d["active_provider"])
for name,creds in d["credential_pool"].items():
    for c in creds:
        print(name, c.get("last_status"), c.get("last_error_code"), c.get("source"))
```
In the incident this showed: `openrouter exhausted 401`, three `anthropic exhausted` (two with 429), and `openai-codex / xai-oauth / nous` all `ok`.

## Confirm an OpenRouter key is actually dead (without leaking it)

```bash
KEY=$(grep -E '^OPENROUTER_API_KEY=*** ~/.hermes/.env | head -1 | cut -d= -f2-)
curl -s -o /dev/null -w '%{http_code}\n' https://openrouter.ai/api/v1/key -H "Authorization: Bearer ***"
unset KEY
```
`401` = revoked/invalid key (replace it). `200` = key fine, problem is elsewhere (model slug, rate limit).

## Validate slugs / provider names before editing

- Valid provider names = subdirs of `~/.hermes/hermes-agent/plugins/model-providers/` (e.g. alibaba, anthropic, copilot, custom, deepseek, gemini, minimax, nous, openai-codex, openrouter, qwen-oauth, xai, zai…). `requesty` is NOT among them → use `custom`.
- Valid Anthropic slugs from `provider_models_cache.json`: `claude-opus-4-8`, `claude-opus-4-7`, `claude-sonnet-4-6`, … (dashes, no `anthropic/` prefix). `anthropic/claude-opus-4.8` is malformed.
- A plugin dir name can differ from its credential-pool key (e.g. dir `xai` vs cred `xai-oauth`) — don't assume they match; verify in the pool before choosing a slot.

## Fix path

`config.yaml` is agent-write-protected, so:
```
hermes moa list                 # see current preset
hermes moa configure default    # interactive: pick healthy reference + aggregator slots
hermes auth reset anthropic     # clear stale 'exhausted' flags if quota recovered
hermes auth add                 # add/replace a credential (e.g. fresh OpenRouter key)
```
`hermes moa configure` is an interactive picker (needs PTY) — give the user the command rather than driving it blind.

## Requesty via custom provider

Requesty router is OpenAI-compatible at `https://router.requesty.ai/v1`. Add to the `providers:` map (user applies it) and reference as `custom:requesty` in reference/aggregator slots.
