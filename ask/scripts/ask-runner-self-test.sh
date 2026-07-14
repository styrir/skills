#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
ASK="$ROOT/scripts/ask.sh"

fail() {
  echo "not ok - $*" >&2
  exit 1
}

assert_contains() {
  local needle="$1" file="$2"
  grep -Fq -- "$needle" "$file" || fail "expected '$needle' in $file"
}

assert_not_contains() {
  local needle="$1" file="$2"
  if grep -Fq -- "$needle" "$file"; then
    fail "did not expect '$needle' in $file"
  fi
}

TMPDIR="$(mktemp -d)"
trap 'rm -rf "$TMPDIR"' EXIT

BIN="$TMPDIR/bin"
mkdir -p "$BIN" "$TMPDIR/work"

cat > "$BIN/claude" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "auth" ] && [ "${2:-}" = "status" ]; then
  echo "logged in"
  exit 0
fi

printf '%s\n' "$*" > "${CLAUDE_ARGS_CAPTURE:?}"
cat <<'JSON'
{"type":"assistant","message":{"content":[{"type":"text","text":"stub review"}]}}
{"type":"result","subtype":"success","duration_ms":1}
JSON
SH
chmod +x "$BIN/claude"

export PATH="$BIN:$PATH"

CLAUDE_ARGS_CAPTURE="$TMPDIR/default-args.txt" \
  "$ASK" claude -d "$TMPDIR/work" -o "$TMPDIR/default" "Review the local change" >/dev/null

assert_not_contains "Optional Research Tools" "$TMPDIR/default/prompt.md"
assert_not_contains "WebSearch" "$TMPDIR/default-args.txt"
assert_not_contains "mcp__context7__*" "$TMPDIR/default-args.txt"

CLAUDE_ARGS_CAPTURE="$TMPDIR/research-args.txt" \
  "$ASK" claude --research -d "$TMPDIR/work" -o "$TMPDIR/research" "Review the local change" >/dev/null

assert_contains "Optional Research Tools" "$TMPDIR/research/prompt.md"
assert_contains '$styrir-search' "$TMPDIR/research/prompt.md"
assert_contains "Context7" "$TMPDIR/research/prompt.md"
assert_contains "WebSearch" "$TMPDIR/research-args.txt"
assert_contains "WebFetch" "$TMPDIR/research-args.txt"
assert_contains "mcp__context7__*" "$TMPDIR/research-args.txt"

echo "ok - ask runner research tool option"

cat > "$BIN/grok" <<'SH'
#!/usr/bin/env bash
set -euo pipefail

if [ "${1:-}" = "models" ]; then
  if [ "${GROK_STUB_MODE:-}" = "noauth" ]; then
    echo "You are not authenticated."
  else
    echo "You are logged in with grok.com."
  fi
  exit 0
fi

printf '%s\n' "$*" > "${GROK_ARGS_CAPTURE:?}"
if [ "${GROK_STUB_MODE:-}" = "truncated" ]; then
  # Stream that dies without an `end` event (crash/truncation).
  cat <<'JSON'
{"type":"thought","data":"checking the local change"}
{"type":"text","data":"partial grok answer"}
JSON
  exit 0
fi
cat <<'JSON'
{"type":"thought","data":"checking the local change"}
{"type":"text","data":"stub grok review"}
{"type":"end","stopReason":"EndTurn","sessionId":"stub-session"}
JSON
SH
chmod +x "$BIN/grok"

GROK_ARGS_CAPTURE="$TMPDIR/grok-default-args.txt" \
  "$ASK" grok -d "$TMPDIR/work" -o "$TMPDIR/grok-default" "Review the local change" >/dev/null

assert_contains "--tools read_file,grep,list_dir" "$TMPDIR/grok-default-args.txt"
assert_contains "--output-format streaming-json" "$TMPDIR/grok-default-args.txt"
assert_not_contains "web_search" "$TMPDIR/grok-default-args.txt"
assert_not_contains "--always-approve" "$TMPDIR/grok-default-args.txt"
assert_contains "stub grok review" "$TMPDIR/grok-default/artifact.md"
assert_contains "stub-session" "$TMPDIR/grok-default/artifact.md"
assert_contains "stub grok review" "$TMPDIR/grok-default/summary.md"
assert_not_contains "## Progress" "$TMPDIR/grok-default/summary.md"

GROK_ARGS_CAPTURE="$TMPDIR/grok-research-args.txt" \
  "$ASK" grok --research -d "$TMPDIR/work" -o "$TMPDIR/grok-research" "Review the local change" >/dev/null

assert_contains "--disallowed-tools run_terminal_cmd,get_task_output,kill_task,task,Agent,search_replace,hashline_edit,ask_user_question,enter_plan_mode,exit_plan_mode" "$TMPDIR/grok-research-args.txt"
assert_not_contains "--tools " "$TMPDIR/grok-research-args.txt"
assert_contains "Optional Research Tools" "$TMPDIR/grok-research/prompt.md"

echo "ok - ask runner grok review lane"

GROK_ARGS_CAPTURE="$TMPDIR/grok-build-args.txt" \
  "$ASK" grok --build --research -d "$TMPDIR/work" -o "$TMPDIR/grok-build" "Implement the change" >/dev/null

assert_contains "--always-approve" "$TMPDIR/grok-build-args.txt"
assert_not_contains "--tools" "$TMPDIR/grok-build-args.txt"
assert_not_contains "Optional Research Tools" "$TMPDIR/grok-build/prompt.md"
assert_contains "stub grok review" "$TMPDIR/grok-build/artifact.md"

if "$ASK" claude --build -d "$TMPDIR/work" -o "$TMPDIR/claude-build" "Implement the change" >/dev/null 2>&1; then
  fail "expected claude --build to be blocked"
fi
assert_contains "--build is currently wired for grok only" "$TMPDIR/claude-build/artifact.md"

if "$ASK" grok --build -o "$TMPDIR/grok-build-nod" "Implement the change" >/dev/null 2>&1; then
  fail "expected grok --build without -d to be blocked"
fi
assert_contains "requires an explicit -d" "$TMPDIR/grok-build-nod/artifact.md"

echo "ok - ask runner grok build mode"

GROK_ARGS_CAPTURE="$TMPDIR/grok-trunc-args.txt" GROK_STUB_MODE=truncated \
  "$ASK" grok -d "$TMPDIR/work" -o "$TMPDIR/grok-trunc" "Review the local change" >/dev/null

assert_contains "partial grok answer" "$TMPDIR/grok-trunc/artifact.md"
assert_not_contains "No assistant text was found in the stream" "$TMPDIR/grok-trunc/artifact.md"

if GROK_ARGS_CAPTURE="$TMPDIR/grok-noauth-args.txt" GROK_STUB_MODE=noauth \
  "$ASK" grok -d "$TMPDIR/work" -o "$TMPDIR/grok-noauth" "Review the local change" >/dev/null 2>&1; then
  fail "expected unauthenticated grok run to be blocked"
fi
assert_contains "not authenticated" "$TMPDIR/grok-noauth/artifact.md"
assert_contains "not authenticated" "$TMPDIR/grok-noauth/summary.md"

echo "ok - ask runner grok guard rails"

# summary.md extraction: review-shaped output keeps VERDICT + numbered
# findings only; other output falls back to the last paragraph.
mkdir -p "$TMPDIR/verdict"
cat > "$TMPDIR/verdict/trace.jsonl" <<'JSON'
{"type":"text","data":"Preamble prose that must not leak into the summary.\n\nVERDICT: REVISE\n\nExplanatory paragraph, also excluded.\n\n1. finding one\n2. finding two\n   with a wrapped continuation line\n\nClosing remarks, excluded."}
{"type":"end","stopReason":"EndTurn","sessionId":"stub-verdict"}
JSON
node --experimental-strip-types "$ROOT/scripts/grok-stream-surface.ts" \
  --from-file "$TMPDIR/verdict/trace.jsonl" "$TMPDIR/verdict/artifact.md" 2>/dev/null

assert_contains "VERDICT: REVISE" "$TMPDIR/verdict/summary.md"
assert_contains "1. finding one" "$TMPDIR/verdict/summary.md"
assert_contains "wrapped continuation line" "$TMPDIR/verdict/summary.md"
assert_not_contains "Preamble prose" "$TMPDIR/verdict/summary.md"
assert_not_contains "Explanatory paragraph" "$TMPDIR/verdict/summary.md"
assert_not_contains "Closing remarks" "$TMPDIR/verdict/summary.md"
assert_contains "Preamble prose" "$TMPDIR/verdict/artifact.md"

mkdir -p "$TMPDIR/jsonl-tail"
cat > "$TMPDIR/jsonl-tail/trace.jsonl" <<'JSON'
{"type":"text","data":"Build narration that should not appear.\n\n{\"slice\":\"s1\",\"status\":\"done\"}\n{\"slice\":\"s2\",\"status\":\"done\"}"}
{"type":"end","stopReason":"EndTurn","sessionId":"stub-jsonl"}
JSON
node --experimental-strip-types "$ROOT/scripts/grok-stream-surface.ts" \
  --from-file "$TMPDIR/jsonl-tail/trace.jsonl" "$TMPDIR/jsonl-tail/artifact.md" 2>/dev/null

assert_contains '{"slice":"s1","status":"done"}' "$TMPDIR/jsonl-tail/summary.md"
assert_not_contains "Build narration" "$TMPDIR/jsonl-tail/summary.md"

echo "ok - ask runner summary extraction"
