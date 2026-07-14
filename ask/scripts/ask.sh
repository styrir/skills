#!/usr/bin/env bash
# ask.sh — unified, observable model consultation.
#   ask.sh <provider> [-m model] [-d workdir] [-o outdir] [-b budget-usd] [--research] [--build] (-p prompt-file | "prompt text")
# Streams provider JSONL through the matching *-stream-surface.ts adapter:
# raw trace lands in <outdir>/trace.jsonl (tail-able), compact progress goes to
# stderr in realtime, and the final answer renders to <outdir>/artifact.md.
# Providers without a streaming adapter fall back to `omc ask`.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
SKILL_DIR="$(dirname "$SCRIPT_DIR")"
REGISTRY="$SKILL_DIR/providers.json"

usage() {
  echo 'Usage: ask.sh <provider> [-m model] [-d workdir] [-o outdir] [-b budget-usd] [--research] [--build] (-p prompt-file | "prompt text")' >&2
  echo '  --research, --with-research-tools  Let the reviewer use bounded web search and Context7 when useful.' >&2
  echo '  --build, --write                   Write-enabled builder pass (grok only): full toolset, tool executions auto-approved.' >&2
  echo "Providers: $(python3 -c "import json;print(' '.join(json.load(open('$REGISTRY'))['providers']))" 2>/dev/null || echo 'claude codex gemini antigravity grok cursor')" >&2
  exit 1
}

[ $# -ge 2 ] || usage
PROVIDER="$1"; shift

MODEL="" WORKDIR="$PWD" WORKDIR_SET=0 OUTDIR="" BUDGET="" PROMPT_FILE="" PROMPT_TEXT="" RESEARCH_TOOLS=0 BUILD_MODE=0
while [ $# -gt 0 ]; do
  case "$1" in
    -m) MODEL="$2"; shift 2 ;;
    -d) WORKDIR="$2"; WORKDIR_SET=1; shift 2 ;;
    -o) OUTDIR="$2"; shift 2 ;;
    -b) BUDGET="$2"; shift 2 ;;
    -p) PROMPT_FILE="$2"; shift 2 ;;
    --research|--with-research|--with-research-tools) RESEARCH_TOOLS=1; shift ;;
    --build|--write) BUILD_MODE=1; shift ;;
    -h|--help) usage ;;
    *) PROMPT_TEXT="$1"; shift ;;
  esac
done

field() { python3 -c "
import json,sys
p=json.load(open('$REGISTRY'))['providers'].get('$PROVIDER')
sys.exit(1) if p is None else print(p.get('$1',''))
"; }

TIER="$(field tier)" || { echo "ask.sh: unknown provider '$PROVIDER'" >&2; usage; }
[ -n "$MODEL" ] || MODEL="$(field defaultModel)"
ADAPTER="$(field adapter)"

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
mkdir -p "$OUTDIR"
if [ -n "$PROMPT_FILE" ]; then if [ "$PROMPT_FILE" -ef "$OUTDIR/prompt.md" ]; then echo "ask: prompt file already at destination ($OUTDIR/prompt.md); using in place" >&2; else cp "$PROMPT_FILE" "$OUTDIR/prompt.md"; fi; else printf '%s\n' "$PROMPT_TEXT" > "$OUTDIR/prompt.md"; fi
TRACE="$OUTDIR/trace.jsonl" ARTIFACT="$OUTDIR/artifact.md" SUMMARY="$OUTDIR/summary.md"

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

echo "ask: provider=$PROVIDER model=${MODEL:-<cli-default>} tier=$TIER" >&2
echo "ask: tail -f $TRACE" >&2

case "$TIER" in
  stream-json)
    case "$PROVIDER" in
      claude)
        command -v claude >/dev/null || blocker "claude CLI not found on PATH"
        AUTH_OUT="$(claude auth status 2>&1 || true)"
        printf '%s' "$AUTH_OUT" | grep -qiE 'not logged in|loggedIn.*false' && blocker "Not logged in · run: claude auth login"$'\n'"$AUTH_OUT"
        CLAUDE_TOOLS=(Read Grep Glob Bash)
        CLAUDE_ARGS=(-p --model "$MODEL" --permission-mode dontAsk)
        if [ "$RESEARCH_TOOLS" = "1" ]; then
          CLAUDE_TOOLS+=(WebSearch WebFetch MCPSearch)
          CLAUDE_ALLOWED_TOOLS=(Read Grep Glob Bash WebSearch WebFetch MCPSearch 'mcp__context7__*' 'mcp__Parallel-Search-MCP__*')
          CLAUDE_ARGS+=(--allowedTools "$(join_csv "${CLAUDE_ALLOWED_TOOLS[@]}")")
        fi
        CLAUDE_ARGS+=(--tools "$(join_csv "${CLAUDE_TOOLS[@]}")" --output-format stream-json --verbose)
        if [ -n "$BUDGET" ]; then
          CLAUDE_ARGS+=(--max-budget-usd "$BUDGET")
        fi
        set +e
        claude "${CLAUDE_ARGS[@]}" < "$OUTDIR/prompt.md" \
          | node --experimental-strip-types "$SCRIPT_DIR/$ADAPTER" "$TRACE" "$ARTIFACT" "$OUTDIR/prompt.md"
        STATUSES=("${PIPESTATUS[@]}")
        set -e
        [ "${STATUSES[0]}" -eq 0 ] || blocker "claude exited ${STATUSES[0]} — see $TRACE"
        [ "${STATUSES[1]}" -eq 0 ] || blocker "stream adapter exited ${STATUSES[1]} — see $TRACE"
        ;;
      codex)
        command -v codex >/dev/null || blocker "codex CLI not found on PATH"
        set +e
        # --disable multi_agent_v2: its injected spawn_agent tool collides with
        # gpt-5.6-sol's reserved collaboration.spawn_agent schema → HTTP 400 on
        # every turn (openai/codex#26753, closed not_planned). Harmless for
        # other models; the config.toml table form does not reliably disable it.
        codex exec --json --sandbox read-only --skip-git-repo-check --disable multi_agent_v2 \
          ${MODEL:+-m "$MODEL"} -C "$WORKDIR" "$(cat "$OUTDIR/prompt.md")" </dev/null \
          | node --experimental-strip-types "$SCRIPT_DIR/$ADAPTER" "$TRACE" "$ARTIFACT" "$OUTDIR/prompt.md"
        STATUSES=("${PIPESTATUS[@]}")
        set -e
        [ "${STATUSES[0]}" -eq 0 ] || blocker "codex exited ${STATUSES[0]} — see $TRACE"
        [ "${STATUSES[1]}" -eq 0 ] || blocker "stream adapter exited ${STATUSES[1]} — see $TRACE"
        ;;
      grok)
        command -v grok >/dev/null || blocker "grok CLI not found on PATH"
        # `grok models` can transiently report unauthenticated while the cached
        # OAuth token is mid-refresh (observed 2026-07-09); retry once.
        AUTH_OUT="$(grok models 2>&1 || true)"
        if ! printf '%s' "$AUTH_OUT" | grep -qi 'logged in'; then
          sleep 2
          AUTH_OUT="$(grok models 2>&1 || true)"
        fi
        printf '%s' "$AUTH_OUT" | grep -qi 'logged in' || blocker "grok not authenticated · run: grok login"$'\n'"$AUTH_OUT"
        GROK_ARGS=(--no-auto-update --cwd "$WORKDIR" --output-format streaming-json)
        if [ -n "$MODEL" ]; then
          GROK_ARGS+=(-m "$MODEL")
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
          GROK_ARGS+=(--tools read_file,grep,list_dir)
        fi
        if [ -n "$BUDGET" ]; then
          echo "ask: grok CLI has no budget flag; -b $BUDGET not enforced" >&2
        fi
        set +e
        grok "${GROK_ARGS[@]}" --prompt-file "$OUTDIR/prompt.md" \
          | node --experimental-strip-types "$SCRIPT_DIR/$ADAPTER" "$TRACE" "$ARTIFACT" "$OUTDIR/prompt.md"
        STATUSES=("${PIPESTATUS[@]}")
        set -e
        [ "${STATUSES[0]}" -eq 0 ] || blocker "grok exited ${STATUSES[0]} — see $TRACE"
        [ "${STATUSES[1]}" -eq 0 ] || blocker "stream adapter exited ${STATUSES[1]} — see $TRACE"
        ;;
      *) blocker "no streaming adapter wired for $PROVIDER" ;;
    esac
    ;;
  final-json|text-tee)
    FALLBACK="$(field fallback)"
    [ -n "$FALLBACK" ] || blocker "provider $PROVIDER has no adapter and no fallback"
    echo "ask: no streaming adapter for $PROVIDER — falling back to: $FALLBACK (black-box until it finishes)" >&2
    set +e
    $FALLBACK "$(cat "$OUTDIR/prompt.md")" 2>&1 | tee "$TRACE"
    STATUS=${PIPESTATUS[0]}
    set -e
    [ "$STATUS" -eq 0 ] || blocker "$FALLBACK exited $STATUS"
    {
      echo "# ${PROVIDER} consultation (fallback route)"
      echo
      echo "Ran via \`$FALLBACK\`; raw output captured in \`$TRACE\`."
      echo "The provider's own artifact (if any) is under .omc/artifacts/ask/."
    } > "$ARTIFACT"
    cp "$ARTIFACT" "$SUMMARY"
    ;;
esac

echo "artifact: $ARTIFACT"
echo "summary: $SUMMARY"
