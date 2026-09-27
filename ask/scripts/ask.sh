#!/usr/bin/env bash
# ask.sh — unified, observable model consultation.
#   ask.sh <provider> [-m model] [-d workdir] [-o outdir] [-b budget-usd] [--research] [--build] (-p prompt-file | "prompt text")
# Streams provider JSONL through the matching *-stream-surface.ts adapter:
# raw trace lands in <outdir>/trace.jsonl (tail-able), compact progress goes to
# stderr in realtime, and the final answer renders to <outdir>/artifact.md.
# Providers without qualified JSONL completion adapters cannot launch.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
REGISTRY="$SKILL_DIR/providers.json"

# Freeze executing bytes. Editing the shared source must never change a live shell's continuation.
if [ "${ASK_RUNTIME_SNAPSHOT:-}" != "1" ]; then
  ASK_RUNTIME_DIR="$(mktemp -d "${TMPDIR:-/tmp}/ask-runtime.XXXXXX")"
  cp -R "$SCRIPT_DIR" "$ASK_RUNTIME_DIR/scripts"
  cp "$REGISTRY" "$ASK_RUNTIME_DIR/providers.json"
  export ASK_RUNTIME_SNAPSHOT=1 ASK_RUNTIME_DIR ASK_CANONICAL_SKILL_ROOT="$SKILL_DIR"
  exec bash "$ASK_RUNTIME_DIR/scripts/ask.sh" "$@"
fi
# Only remove the private runtime directory whose runner is actually executing.
if [ "$SKILL_DIR" = "${ASK_RUNTIME_DIR:-}" ] && [[ "$SKILL_DIR" == */ask-runtime.* ]]; then
  trap 'rm -rf -- "$ASK_RUNTIME_DIR"' EXIT
fi

usage() {
  echo 'Usage: ask.sh <provider> [-m model] [-d workdir] [-o outdir] [-b budget-usd] [--effort low|medium|high|xhigh] [--research] [--build] (-p prompt-file | "prompt text")' >&2
  echo '       ask.sh <provider> [-m model] --route-status' >&2
  echo '  --research, --with-research-tools  Let the reviewer use bounded web search and Context7 when useful.' >&2
  echo '  --build, --write                   Write-enabled builder pass (grok only): full toolset, tool executions auto-approved.' >&2
  echo '  --effort LEVEL                     Codex/Claude reasoning effort when supported (default: unset / provider default).' >&2
  echo '  --transport proxy                 Explicit tool-free loopback SSE review using the configured model route.' >&2
  echo '  --first-output-seconds N --wall-seconds N  Watcher budgets (defaults 180/600).' >&2
  echo '  --max-output-tokens N             Direct proxy output budget (default 16384).' >&2
  echo '  --route-status                     Print one JSON object describing the resolved route and its health; no consultation runs.' >&2
  echo "Providers: $(python3 -c "import json;print(' '.join(json.load(open('$REGISTRY'))['providers']))" 2>/dev/null || echo 'claude codex gemini antigravity grok cursor')" >&2
  exit 1
}

[ $# -ge 2 ] || usage
PROVIDER="$1"; shift

MODEL="" WORKDIR="$PWD" WORKDIR_SET=0 OUTDIR="" BUDGET="" PROMPT_FILE="" PROMPT_TEXT="" RESEARCH_TOOLS=0 BUILD_MODE=0 EFFORT="" ROUTE_STATUS=0 TRANSPORT_OVERRIDE="" FIRST_OUTPUT="${ASK_FIRST_OUTPUT_SECONDS:-180}" WALL="${ASK_WALL_SECONDS:-600}" MAX_OUTPUT="${ASK_MAX_OUTPUT_TOKENS:-16384}"
while [ $# -gt 0 ]; do
  case "$1" in
    -m) MODEL="$2"; shift 2 ;;
    -d) WORKDIR="$2"; WORKDIR_SET=1; shift 2 ;;
    -o) OUTDIR="$2"; shift 2 ;;
    -b) BUDGET="$2"; shift 2 ;;
    -p) PROMPT_FILE="$2"; shift 2 ;;
    --effort) EFFORT="$2"; shift 2 ;;
    --research|--with-research|--with-research-tools) RESEARCH_TOOLS=1; shift ;;
    --build|--write) BUILD_MODE=1; shift ;;
    --route-status) ROUTE_STATUS=1; shift ;;
    --transport) TRANSPORT_OVERRIDE="$2"; shift 2 ;;
    --first-output-seconds) FIRST_OUTPUT="$2"; shift 2 ;;
    --wall-seconds) WALL="$2"; shift 2 ;;
    --max-output-tokens) MAX_OUTPUT="$2"; shift 2 ;;
    -h|--help) usage ;;
    *) PROMPT_TEXT="$1"; shift ;;
  esac
done

field() {
  python3 - "$REGISTRY" "$PROVIDER" "$1" <<'PYFIELD'
import json, sys
with open(sys.argv[1]) as source:
    provider = json.load(source)['providers'].get(sys.argv[2])
if provider is None:
    sys.exit(1)
print(provider.get(sys.argv[3], ''))
PYFIELD
}

# ops-ts4: models routed through the grok transport may be proxy-owned — the
# grok CLI config declares a [model.*] section with a base_url pointing at a
# local CLIProxyAPI. Resolve that route so preflight can gate on the endpoint
# the run actually depends on. Endpoint truth stays in the grok config; the
# registry never duplicates it.
GROK_ROUTE_CONFIG="${ASK_GROK_CONFIG:-$HOME/.grok/config.toml}"

resolve_route_value() { # $1: requested model. Prints base_url ('' when the
  # model has no [model.*] section, i.e. a native xAI model). rc 1 on config
  # read/parse failure so callers can fall back with a warning.
  python3 - "$GROK_ROUTE_CONFIG" "$1" "${2:-base_url}" 2>/dev/null <<'PY'
import sys, tomllib

def strip_effort(name: str) -> str:
    head, sep, _ = name.partition("(")
    return head if sep else name

cfg_path, requested, field = sys.argv[1:]
target = strip_effort(requested)
try:
    with open(cfg_path, "rb") as fh:
        cfg = tomllib.load(fh)
except Exception:
    sys.exit(1)
models = cfg.get("model")
if isinstance(models, dict):
    for key, section in models.items():
        if not isinstance(section, dict):
            continue
        if target in (strip_effort(key), strip_effort(str(section.get("model", "")))):
            print(section.get(field, requested if field == "model" else ""))
            break
PY
}

resolve_route_base_url() { resolve_route_value "$1" base_url; }
resolve_route_model() { resolve_route_value "$1" model; }

model_listed() { # $1: /models JSON body, $2: bare model id. rc 0 when listed.
  printf '%s' "$1" | python3 -c '
import json, sys
try:
    ids = {m.get("id", "") for m in json.load(sys.stdin).get("data", [])}
except Exception:
    sys.exit(1)
sys.exit(0 if sys.argv[1] in ids else 1)
' "$2" 2>/dev/null
}

TIER="$(field tier)" || { echo "ask.sh: unknown provider '$PROVIDER'" >&2; usage; }
[ -n "$MODEL" ] || MODEL="$(field defaultModel)"
TRANSPORT="$(field transport)"
[ -n "$TRANSPORT" ] || TRANSPORT="$PROVIDER"
if [ -n "$TRANSPORT_OVERRIDE" ]; then
  [ "$TRANSPORT_OVERRIDE" = "proxy" ] || { echo 'ask: only explicit proxy transport override is supported' >&2; exit 2; }
  TRANSPORT=proxy
fi
ADAPTER="$(field adapter)"

# --route-status: report the resolved route and its health as one JSON object
# on stdout (everything else stays on stderr), then exit. No consultation, no
# outdir, no credential material.
if [ "$ROUTE_STATUS" = "1" ] && [ "$TRANSPORT" = "proxy" ]; then
  exec python3 "$SCRIPT_DIR/proxy-stream.py" --model "$MODEL" --status
fi
if [ "$ROUTE_STATUS" = "1" ]; then
  RS_AUTH_OWNER="$(field authOwner)"
  RS_ROLLBACK="$(field rollbackNote)"
  RS_ENDPOINT="" RS_ENDPOINT_HEALTHY="" RS_MODEL_LISTED="" RS_CLI_FOUND="false" RS_AUTH_PASSED=""
  RS_BIN="$TRANSPORT"
  RS_VERSION_CHECK="$(field versionCheck)"
  if [ -n "$RS_VERSION_CHECK" ]; then RS_BIN="${RS_VERSION_CHECK%% *}"; fi
  if command -v "$RS_BIN" >/dev/null 2>&1; then RS_CLI_FOUND="true"; fi
  case "$TRANSPORT" in
    grok)
      if [ "$RS_CLI_FOUND" = "true" ] && [ -z "$(resolve_route_base_url "$MODEL")" ]; then
        RS_AUTH_OUT="$(grok models 2>&1 || true)"
        if ! printf '%s' "$RS_AUTH_OUT" | grep -qi 'logged in'; then
          # same transient-OAuth-refresh retry as the consultation preflight
          sleep 2
          RS_AUTH_OUT="$(grok models 2>&1 || true)"
        fi
        if printf '%s' "$RS_AUTH_OUT" | grep -qi 'logged in'; then RS_AUTH_PASSED="true"; else RS_AUTH_PASSED="false"; fi
      fi
      if [ -n "$MODEL" ]; then
        if ! RS_ENDPOINT="$(resolve_route_base_url "$MODEL")"; then
          RS_ENDPOINT=""
          echo "ask: warning: cannot parse grok route config ($GROK_ROUTE_CONFIG); endpoint unresolved" >&2
        fi
        if [ -n "$RS_ENDPOINT" ]; then
          if RS_MODELS_JSON="$(curl -sf -m 5 "$RS_ENDPOINT/models")"; then
            RS_ENDPOINT_HEALTHY="true"
            RS_RESOLVED="$(resolve_route_model "$MODEL")"
            if model_listed "$RS_MODELS_JSON" "${RS_RESOLVED%%\(*}"; then RS_MODEL_LISTED="true"; else RS_MODEL_LISTED="false"; fi
          else
            RS_ENDPOINT_HEALTHY="false"
          fi
        fi
      fi
      ;;
    claude)
      if [ "$RS_CLI_FOUND" = "true" ]; then
        RS_AUTH_OUT="$(claude auth status 2>&1 || true)"
        if printf '%s' "$RS_AUTH_OUT" | grep -qiE 'not logged in|loggedIn.*false'; then RS_AUTH_PASSED="false"; else RS_AUTH_PASSED="true"; fi
      fi
      ;;
  esac
  python3 - "$PROVIDER" "$TRANSPORT" "$MODEL" "$RS_ENDPOINT" "$RS_AUTH_OWNER" "$RS_ENDPOINT_HEALTHY" "$RS_MODEL_LISTED" "$RS_CLI_FOUND" "$RS_AUTH_PASSED" "$RS_ROLLBACK" <<'PY'
import json, sys

vals = sys.argv[1:]

def tri(v):  # "" = not applicable / unknown
    return None if v == "" else v == "true"

def txt(v):
    return v if v else None

print(json.dumps({
    "provider": vals[0],
    "transport": vals[1],
    "model": txt(vals[2]),
    "endpoint": txt(vals[3]),
    "authOwner": txt(vals[4]),
    "endpointHealthy": tri(vals[5]),
    "modelListed": tri(vals[6]),
    "cliFound": tri(vals[7]),
    "authCheckPassed": tri(vals[8]),
    "rollback": txt(vals[9]),
}, indent=2))
PY
  exit 0
fi

# Materialize the prompt as a file so it is preserved with the run.
STAMP="$(date +%Y%m%d-%H%M%S)"
if [ -n "$PROMPT_FILE" ]; then
  [ -f "$PROMPT_FILE" ] || { echo "ask.sh: prompt file not found: $PROMPT_FILE" >&2; exit 1; }
  SLUG="$(basename "$PROMPT_FILE" | tr -cs 'a-zA-Z0-9' '-' | cut -c1-32 | sed 's/-$//')"
else
  [ -n "$PROMPT_TEXT" ] || usage
  SLUG="$(printf '%s' "$PROMPT_TEXT" | tr -cs 'a-zA-Z0-9' '-' | cut -c1-32 | sed 's/-$//')"
fi
[ -n "$OUTDIR" ] || OUTDIR=".ask/${PROVIDER}-${SLUG}-${STAMP}"
umask 077
mkdir -p "$OUTDIR"
TRACE="$OUTDIR/trace.jsonl" ARTIFACT="$OUTDIR/artifact.md" SUMMARY="$OUTDIR/summary.md"
[ ! -e "$OUTDIR/result.json" ] && [ ! -e "$TRACE" ] || { echo 'ask: output directory contains an earlier attempt; choose a fresh -o directory' >&2; exit 2; }
if [ -n "$PROMPT_FILE" ]; then if [ "$PROMPT_FILE" -ef "$OUTDIR/prompt.md" ]; then echo "ask: prompt file already at destination ($OUTDIR/prompt.md); using in place" >&2; else cp "$PROMPT_FILE" "$OUTDIR/prompt.md"; fi; else printf '%s\n' "$PROMPT_TEXT" > "$OUTDIR/prompt.md"; fi


# The research appendix is reviewer-shaped ("Do not edit files"), so build
# passes skip it; grok build mode has web tools available by default anyway.
if [ "$RESEARCH_TOOLS" = "1" ] && [ "$BUILD_MODE" = "1" ]; then
  echo "ask: --research is a review-pass option; skipping its appendix in build mode" >&2
fi
if [ "$RESEARCH_TOOLS" = "1" ] && [ "$BUILD_MODE" != "1" ]; then
  cat >> "$OUTDIR/prompt.md" <<'EOF'

## Optional Research Tools

Research tools are enabled for this review.

- Use local files first. Use external research only when current public facts, library/API docs, or contradiction checks materially affect the review.
- Prefer `$styrir-search` for bounded web research. Route the request, choose the smallest adequate search mode, fetch/read sources before treating them as evidence, and cite source IDs or URLs in findings.
- Use Context7 for current library, SDK, CLI, API, framework, and cloud documentation. Resolve the library ID before querying docs.
- You are the review orchestrator for this pass: choose which searches are appropriate, keep budgets small, and report any unavailable research tool plainly.
- Do not edit files.
EOF
fi

join_csv() {
  local IFS=,
  printf '%s' "$*"
}

blocker() { # $1 = reason text
  if [ -f "$OUTDIR/result.json" ]; then
    echo "blocked: $1" >&2
    echo "artifact: $ARTIFACT"
    exit 2
  fi
  if [ -f "$ARTIFACT" ]; then mv "$ARTIFACT" "$OUTDIR/partial.md"; fi
  {
    echo "# ${PROVIDER} consultation blocked"
    echo
    echo "The requested ${PROVIDER} run did not produce a result."
    echo
    echo '```text'
    printf '%s\n' "$1"
    echo '```'
    echo
    echo "Prompt: \`$OUTDIR/prompt.md\` — retry after fixing the blocker."
  } > "$ARTIFACT"
  printf 'blocked: %s\n' "$1" > "$SUMMARY"
  echo "blocked: $1" >&2
  echo "artifact: $ARTIFACT"
  exit 2
}

if [ "$BUILD_MODE" = "1" ]; then
  [ "$PROVIDER" = "grok" ] || blocker "--build is currently wired for grok only; $PROVIDER consultations stay read-only"
  # Auto-approved writes land in the workdir; never let that default to $PWD.
  [ "$WORKDIR_SET" = "1" ] || blocker "--build requires an explicit -d workdir (auto-approved writes land there)"
  [ -d "$WORKDIR" ] || blocker "--build workdir not found: $WORKDIR"
  WORKDIR="$(cd "$WORKDIR" && pwd -P)"
fi

echo "ask: provider=$PROVIDER transport=$TRANSPORT model=${MODEL:-<cli-default>} tier=$TIER" >&2
echo "ask: tail -f $TRACE" >&2

run_supervised() {
  python3 "$SCRIPT_DIR/supervise.py" --outdir "$OUTDIR" --adapter "$SCRIPT_DIR/$ADAPTER" \
    --model "$MODEL" --transport "$TRANSPORT" --first-output-seconds "$FIRST_OUTPUT" --wall-seconds "$WALL" -- "$@"
}

case "$TIER" in
  stream-json)
    case "$TRANSPORT" in
      proxy)
        [ "$BUILD_MODE" = "0" ] && [ "$RESEARCH_TOOLS" = "0" ] || blocker "Direct proxy mode is tool-free; build/research require a qualified CLI route"
        [ -z "$BUDGET" ] || blocker "Direct proxy cost cap is not supported; use an enforced provider route"
        ADAPTER=grok-stream-surface.ts
        run_supervised python3 "$SCRIPT_DIR/proxy-stream.py" --model "$MODEL" --prompt "$OUTDIR/prompt.md" \
          --effort "${EFFORT:-medium}" --max-output-tokens "$MAX_OUTPUT" || blocker "Proxy consultation incomplete; see result.json"
        ;;
      claude)
        command -v claude >/dev/null || blocker "claude CLI not found on PATH"
        AUTH_OUT="$(claude auth status 2>&1 || true)"
        printf '%s' "$AUTH_OUT" | grep -qiE 'not logged in|loggedIn.*false' && blocker "Not logged in — this gate applies to the NATIVE claude transport only; providers routed through another transport (see providers.json) never reach it. Consult providers.json authOwner before running 'claude auth login': run it only when the claude CLI itself owns auth for this provider."$'\n'"$AUTH_OUT"
        CLAUDE_TOOLS=(Read Grep Glob Bash)
        CLAUDE_ARGS=(-p --model "$MODEL" --permission-mode dontAsk)
        if [ "$RESEARCH_TOOLS" = "1" ]; then
          CLAUDE_TOOLS+=(WebSearch WebFetch MCPSearch)
          CLAUDE_ALLOWED_TOOLS=(Read Grep Glob Bash WebSearch WebFetch MCPSearch 'mcp__context7__*' 'mcp__Parallel-Search-MCP__*')
          CLAUDE_ARGS+=(--allowedTools "$(join_csv "${CLAUDE_ALLOWED_TOOLS[@]}")")
        fi
        CLAUDE_ARGS+=(--tools "$(join_csv "${CLAUDE_TOOLS[@]}")" --output-format stream-json --verbose)
        if [ -n "$EFFORT" ]; then
          CLAUDE_ARGS+=(--effort "$EFFORT")
          echo "ask: claude effort=$EFFORT" >&2
        fi
        if [ -n "$BUDGET" ]; then
          CLAUDE_ARGS+=(--max-budget-usd "$BUDGET")
        fi
        run_supervised claude "${CLAUDE_ARGS[@]}" < "$OUTDIR/prompt.md" || blocker "Claude consultation incomplete; see result.json"
        ;;
      codex)
        command -v codex >/dev/null || blocker "codex CLI not found on PATH"
        set +e
        # --disable multi_agent_v2: its injected spawn_agent tool collides with
        # gpt-5.6-sol's reserved collaboration.spawn_agent schema → HTTP 400 on
        # every turn (openai/codex#26753, closed not_planned). Harmless for
        # other models; the config.toml table form does not reliably disable it.
        CODEX_EFFORT_ARGS=()
        if [ -n "$EFFORT" ]; then
          CODEX_EFFORT_ARGS=(-c "model_reasoning_effort=\"$EFFORT\"")
          echo "ask: codex effort=$EFFORT" >&2
        fi
        run_supervised codex exec --json --sandbox read-only --skip-git-repo-check --disable multi_agent_v2 \
          ${MODEL:+-m "$MODEL"} "${CODEX_EFFORT_ARGS[@]}" -C "$WORKDIR" "$(cat "$OUTDIR/prompt.md")" </dev/null || blocker "Codex consultation incomplete; see result.json"
        set -e
        ;;
      grok)
        command -v grok >/dev/null || blocker "grok CLI not found on PATH"
        # Proxy routes do not use xAI authentication. Native xAI still does.
        AUTH_ENDPOINT="$(resolve_route_base_url "$MODEL")" || blocker "Cannot parse configured model route"
        if [ -z "$AUTH_ENDPOINT" ] && [ "$PROVIDER" != "claude" ]; then
          AUTH_OUT="$(grok models 2>&1 || true)"
          if ! printf '%s' "$AUTH_OUT" | grep -qi 'logged in'; then
            sleep 2
            AUTH_OUT="$(grok models 2>&1 || true)"
          fi
          printf '%s' "$AUTH_OUT" | grep -qi 'logged in' || blocker "grok not authenticated · run: grok login"$'\n'"$AUTH_OUT"
          if [ -n "$MODEL" ]; then
            printf '%s' "$AUTH_OUT" | python3 -c 'import re,sys; names={m.group(1) for line in sys.stdin for m in [re.match(r"^\s*[-*]\s+(\S+)",line)] if m}; sys.exit(0 if sys.argv[1] in names else 1)' "$MODEL" || blocker "Requested native model is not listed: $MODEL; no fallback permitted"
          fi
        fi
        # ops-ts4: `grok models` proves xAI auth only. Proxy-owned models
        # (claude-*, gpt-5.6-*) ride a local CLIProxyAPI declared as a
        # [model.*] base_url in the grok config; probe the endpoint the run
        # actually depends on so a dead proxy blocks at preflight instead of
        # dying generically mid-run.
        ROUTE_BASE_URL=""
        if [ -n "$MODEL" ]; then
          if ! ROUTE_BASE_URL="$(resolve_route_base_url "$MODEL")"; then
            ROUTE_BASE_URL=""
            echo "ask: warning: cannot parse grok route config ($GROK_ROUTE_CONFIG); proxy probe skipped, grok auth gate still applies" >&2
          fi
        fi
        if [ "$PROVIDER" = "claude" ] && [ -z "$ROUTE_BASE_URL" ]; then
          blocker "Claude proxy model is not configured: $MODEL; no fallback permitted"
        fi
        if [ -n "$ROUTE_BASE_URL" ]; then
          AUTH_OWNER="$(field authOwner)"
          ROLLBACK_NOTE="$(field rollbackNote)"
          RESOLVED_MODEL="$(resolve_route_model "$MODEL")"
          BARE_MODEL="${RESOLVED_MODEL%%\(*}"
          if PROXY_MODELS_JSON="$(curl -sf -m 5 "$ROUTE_BASE_URL/models")"; then
            if ! model_listed "$PROXY_MODELS_JSON" "$BARE_MODEL"; then
              blocker "$BARE_MODEL is not listed at $ROUTE_BASE_URL/models; no model substitution permitted"
            fi
          else
            blocker "proxy-owned model route unreachable: $MODEL is served by ${AUTH_OWNER:-vibeproxy} (CLIProxyAPI) at $ROUTE_BASE_URL, which did not answer.
diagnostics: curl $ROUTE_BASE_URL/models
rollback route: ${ROLLBACK_NOTE:-127.0.0.1:8319 per agent-ops:ops-ts4}
Do NOT log in with the claude CLI ('auth login') — auth for this route is owned by ${AUTH_OWNER:-vibeproxy}, not the claude CLI."
          fi
        fi
        GROK_ARGS=(--no-auto-update --cwd "$WORKDIR" --output-format streaming-json)
        if [ -n "$MODEL" ]; then
          GROK_ARGS+=(-m "$MODEL")
        fi
        if [ -n "$EFFORT" ]; then
          GROK_ARGS+=(--reasoning-effort "$EFFORT")
          echo "ask: $PROVIDER via grok effort=$EFFORT" >&2
        fi
        if [ "$BUILD_MODE" = "1" ]; then
          # Builder pass: grok's full default toolset with tool executions
          # auto-approved (headless runs cannot prompt for approval).
          GROK_ARGS+=(--always-approve)
          echo "ask: grok build mode — writes and commands auto-approved in $WORKDIR" >&2
        elif [ "$RESEARCH_TOOLS" = "1" ]; then
          # grok 0.2.93: a --tools allowlist that names web_search/web_fetch
          # pulls run_terminal_cmd into the toolset with enabled_background=false
          # while auto_background_on_timeout stays true, and session creation
          # fails that params constraint. Denylist mode keeps the default
          # (valid) params, so strip shell/edit/subagent/interactive tools from
          # the default set instead: same read-only surface plus web tools.
          GROK_DENY=(run_terminal_cmd get_task_output kill_task task Agent
            search_replace hashline_edit ask_user_question
            enter_plan_mode exit_plan_mode)
          GROK_ARGS+=(--disallowed-tools "$(join_csv "${GROK_DENY[@]}")")
        else
          GROK_ARGS+=(--tools "read_file,grep,list_dir")
        fi
        if [ -n "$BUDGET" ]; then
          blocker "Grok transport cannot enforce -b; no consultation launched"
        fi
        run_supervised grok "${GROK_ARGS[@]}" --prompt-file "$OUTDIR/prompt.md" || blocker "Grok consultation incomplete; see result.json"
        ;;
      *) blocker "no streaming adapter wired for $PROVIDER" ;;
    esac
    ;;
  final-json|text-tee)
    blocker "Provider $PROVIDER has no qualified JSONL completion adapter/watcher route; no black-box fallback permitted"
    ;;
esac

echo "artifact: $ARTIFACT"
echo "summary: $SUMMARY"
