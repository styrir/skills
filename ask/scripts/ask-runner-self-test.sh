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
echo "native claude must not be invoked for proxy-owned routing" > "${CLAUDE_NATIVE_CALLED:?}"
exit 99
SH
chmod +x "$BIN/claude"

export PATH="$BIN:$PATH"

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

# curl stub: answers the ops-ts4 proxy preflight probe. Serves a model list
# for any endpoint except the deliberately closed 127.0.0.1:1, which fails
# like a refused connection. Records probed URLs when CURL_CALLS_CAPTURE is
# set so cases can assert the probe ran (or did not).
cat > "$BIN/curl" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
url=""
for arg in "$@"; do url="$arg"; done
if [ -n "${CURL_CALLS_CAPTURE:-}" ]; then
  printf '%s\n' "$url" >> "$CURL_CALLS_CAPTURE"
fi
case "$url" in
  *127.0.0.1:1/*) exit 7 ;;
esac
cat <<'JSON'
{"object":"list","data":[{"id":"claude-opus-5","object":"model"},{"id":"claude-fable-5","object":"model"},{"id":"gpt-5.6-sol","object":"model"}]}
JSON
SH
chmod +x "$BIN/curl"

# Hermetic grok route config: claude models are proxy-owned (base_url), the
# native xAI model has no [model.*] section at all.
cat > "$TMPDIR/grok-config.toml" <<'TOML'
[model.claude-opus-5]
model = "claude-opus-5"
base_url = "http://127.0.0.1:8318/v1"
api_key = "sk-dummy"

[model.claude-fable-5]
model = "claude-fable-5"
base_url = "http://127.0.0.1:8318/v1"
api_key = "sk-dummy"

[model.claude-opus-5-high]
model = "claude-opus-5(high)"
base_url = "http://127.0.0.1:8318/v1"
api_key = "sk-dummy"
TOML
export ASK_GROK_CONFIG="$TMPDIR/grok-config.toml"

# Same routes pointed at a closed port for the fail-closed case.
cat > "$TMPDIR/grok-config-down.toml" <<'TOML'
[model.claude-opus-5]
model = "claude-opus-5"
base_url = "http://127.0.0.1:1/v1"
api_key = "sk-dummy"
TOML

CLAUDE_NATIVE_CALLED="$TMPDIR/native-claude-called.txt" GROK_ARGS_CAPTURE="$TMPDIR/claude-default-args.txt" \
  CURL_CALLS_CAPTURE="$TMPDIR/curl-default-calls.txt" \
  "$ASK" claude -m claude-opus-5 --effort medium -d "$TMPDIR/work" -o "$TMPDIR/default" "Review the local change" >/dev/null

[ ! -e "$TMPDIR/native-claude-called.txt" ] || fail "proxy-owned Claude route invoked native claude"
assert_contains "http://127.0.0.1:8318/v1/models" "$TMPDIR/curl-default-calls.txt"
assert_not_contains "Optional Research Tools" "$TMPDIR/default/prompt.md"
assert_contains "-m claude-opus-5" "$TMPDIR/claude-default-args.txt"
assert_contains "--reasoning-effort medium" "$TMPDIR/claude-default-args.txt"
assert_contains "--tools read_file,grep,list_dir" "$TMPDIR/claude-default-args.txt"

CLAUDE_NATIVE_CALLED="$TMPDIR/native-claude-called-research.txt" GROK_ARGS_CAPTURE="$TMPDIR/claude-research-args.txt" \
  "$ASK" claude --research -m claude-fable-5 -d "$TMPDIR/work" -o "$TMPDIR/research" "Review the local change" >/dev/null

[ ! -e "$TMPDIR/native-claude-called-research.txt" ] || fail "proxy-owned Claude research route invoked native claude"
assert_contains "Optional Research Tools" "$TMPDIR/research/prompt.md"
# shellcheck disable=SC2016 # literal skill token, not shell expansion.
assert_contains '$styrir-search' "$TMPDIR/research/prompt.md"
assert_contains "Context7" "$TMPDIR/research/prompt.md"
assert_contains "-m claude-fable-5" "$TMPDIR/claude-research-args.txt"
assert_contains "--disallowed-tools run_terminal_cmd,get_task_output,kill_task,task,Agent,search_replace,hashline_edit,ask_user_question,enter_plan_mode,exit_plan_mode" "$TMPDIR/claude-research-args.txt"

echo "ok - ask runner proxy-owned claude route"

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

if CLAUDE_NATIVE_CALLED="$TMPDIR/native-claude-called-noauth.txt" GROK_ARGS_CAPTURE="$TMPDIR/claude-noauth-args.txt" GROK_STUB_MODE=noauth \
  "$ASK" claude -m claude-opus-5 -d "$TMPDIR/work" -o "$TMPDIR/claude-noauth" "Review the local change" >/dev/null 2>&1; then
  fail "expected proxy-unavailable claude route to be blocked"
fi
[ ! -e "$TMPDIR/native-claude-called-noauth.txt" ] || fail "failed proxy route fell back to native claude"
assert_contains "grok not authenticated" "$TMPDIR/claude-noauth/artifact.md"
assert_not_contains "claude auth login" "$TMPDIR/claude-noauth/artifact.md"

echo "ok - ask runner grok and claude transport guard rails"

# ops-ts4: proxy-down fail-closed — the resolved base_url points at a closed
# port, so preflight must block (exit 2) naming the endpoint and the auth
# owner, without suggesting a native claude login and without invoking claude.
set +e
CLAUDE_NATIVE_CALLED="$TMPDIR/native-claude-called-proxydown.txt" GROK_ARGS_CAPTURE="$TMPDIR/claude-proxydown-args.txt" \
  ASK_GROK_CONFIG="$TMPDIR/grok-config-down.toml" \
  "$ASK" claude -m claude-opus-5 -d "$TMPDIR/work" -o "$TMPDIR/claude-proxydown" "Review the local change" >/dev/null 2>&1
PROXY_DOWN_STATUS=$?
set -e
[ "$PROXY_DOWN_STATUS" -eq 2 ] || fail "expected proxy-down claude route to exit 2, got $PROXY_DOWN_STATUS"
[ ! -e "$TMPDIR/native-claude-called-proxydown.txt" ] || fail "proxy-down claude route fell back to native claude"
assert_contains "http://127.0.0.1:1/v1" "$TMPDIR/claude-proxydown/artifact.md"
assert_contains "vibeproxy" "$TMPDIR/claude-proxydown/artifact.md"
assert_not_contains "claude auth login" "$TMPDIR/claude-proxydown/artifact.md"
assert_not_contains "claude auth login" "$TMPDIR/claude-proxydown/summary.md"

# ops-ts4: native xAI model — no [model.*] base_url in the route config, so
# the proxy probe must not run at all.
GROK_ARGS_CAPTURE="$TMPDIR/grok-native-args.txt" CURL_CALLS_CAPTURE="$TMPDIR/curl-native-calls.txt" \
  "$ASK" grok -m grok-4.6 -d "$TMPDIR/work" -o "$TMPDIR/grok-native" "Review the local change" >/dev/null

assert_contains "-m grok-4.6" "$TMPDIR/grok-native-args.txt"
assert_contains "stub grok review" "$TMPDIR/grok-native/artifact.md"
[ ! -e "$TMPDIR/curl-native-calls.txt" ] || fail "native xAI model unexpectedly probed the proxy"

echo "ok - ask runner proxy route preflight probe"

# ops-ts4: --route-status prints exactly one JSON object on stdout, runs no
# consultation, and reports route + health facts without credential material.
mkdir -p "$TMPDIR/route-status-cwd"
(cd "$TMPDIR/route-status-cwd" && "$ASK" claude --route-status) > "$TMPDIR/route-status.json" 2>"$TMPDIR/route-status.err"
python3 - "$TMPDIR/route-status.json" <<'PY'
import json, sys

d = json.load(open(sys.argv[1]))
expected_keys = {"provider", "transport", "model", "endpoint", "authOwner",
                 "endpointHealthy", "modelListed", "cliFound",
                 "authCheckPassed", "rollback"}
assert set(d) == expected_keys, sorted(d)
assert d["provider"] == "claude", d
assert d["transport"] == "grok", d
assert d["model"] == "claude-opus-5", d
assert d["endpoint"] == "http://127.0.0.1:8318/v1", d
assert d["authOwner"] == "vibeproxy", d
assert d["endpointHealthy"] is True, d
assert d["modelListed"] is True, d
assert d["cliFound"] is True, d
assert d["authCheckPassed"] is True, d
assert d["rollback"] == "127.0.0.1:8319 standalone (agent-ops:ops-ts4)", d
assert "sk-dummy" not in json.dumps(d), d
PY
[ ! -e "$TMPDIR/route-status-cwd/.ask" ] || fail "--route-status must not create an outdir"

echo "ok - ask runner route status"

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
