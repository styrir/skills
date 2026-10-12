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

ASK_TEST_TMP="$(mktemp -d)"
trap 'rm -rf "$ASK_TEST_TMP"' EXIT

BIN="$ASK_TEST_TMP/bin"
mkdir -p "$BIN" "$ASK_TEST_TMP/work"

cat > "$BIN/claude" <<'SH'
#!/usr/bin/env bash
set -euo pipefail
if [ "${1:-}" = "auth" ]; then
  if [ "${CLAUDE_STUB_MODE:-}" = "noauth" ]; then echo '{"loggedIn": false}'; else echo '{"loggedIn": true, "authMethod": "claude.ai"}'; fi
  exit 0
fi
cat >/dev/null
python3 -c 'import json,os,sys; json.dump({"argv":sys.argv[1:],"cwd":os.getcwd()},open(os.environ["CLAUDE_ARGS_CAPTURE"],"w"))' "$@"
cat <<'JSON'
{"type":"assistant","message":{"content":[{"type":"text","text":"stub claude review"}]}}
{"type":"result","subtype":"success","result":"stub claude review"}
JSON
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
    echo "  * grok-4.6 (default)"
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

# Hermetic grok route config: proxy-owned models (base_url); the native xAI
# model has no [model.*] section at all. Claude is native-only and never here.
cat > "$ASK_TEST_TMP/grok-config.toml" <<'TOML'
[model."gpt-5.6-sol"]
model = "gpt-5.6-sol"
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
export ASK_GROK_CONFIG="$ASK_TEST_TMP/grok-config.toml"

# Same routes pointed at a closed port for the fail-closed case.
cat > "$ASK_TEST_TMP/grok-config-down.toml" <<'TOML'
[model."gpt-5.6-sol"]
model = "gpt-5.6-sol"
base_url = "http://127.0.0.1:1/v1"
api_key = "sk-dummy"
TOML

# Native claude argv contract: read-only OS sandbox scoped to the workdir.
cat > "$ASK_TEST_TMP/check-claude-args.py" <<'PY'
import json, os, sys
cap = json.load(open(sys.argv[1])); argv = cap["argv"]; work = os.path.realpath(sys.argv[2]); research = sys.argv[3] == "research"
def val(flag):
    assert flag in argv, (flag, argv)
    return argv[argv.index(flag) + 1]
assert argv[0] == "-p", argv
assert cap["cwd"] == work, cap
assert ("--safe-mode" in argv) is (not research), argv
assert "--no-session-persistence" in argv, argv
assert val("--permission-mode") == "dontAsk", argv
assert val("--output-format") == "stream-json", argv
sandbox = json.loads(val("--settings"))["sandbox"]
assert sandbox["enabled"] is True and sandbox["failIfUnavailable"] is True, sandbox
assert sandbox["allowUnsandboxedCommands"] is False, sandbox
assert sandbox["filesystem"]["denyWrite"] == [work], sandbox
assert json.loads(val("--settings"))["disableAllHooks"] is True, argv
assert val("--setting-sources") == "user", argv
if research:
    assert val("--model") == "claude-fable-5", argv
    assert val("--tools") == "Read,Grep,Glob,Bash,WebSearch,WebFetch,MCPSearch", argv
    assert "mcp__context7__*" in val("--allowedTools"), argv
else:
    assert val("--model") == "claude-opus-5", argv
    assert val("--tools") == "Read,Grep,Glob,Bash", argv
    assert "--allowedTools" not in argv, argv
    assert val("--effort") == "medium", argv
    assert val("--max-budget-usd") == "2", argv
PY

# Grok must never be invoked for the claude provider.
export GROK_ARGS_CAPTURE="$ASK_TEST_TMP/grok-called-for-claude.txt"
CLAUDE_ARGS_CAPTURE="$ASK_TEST_TMP/claude-default-args.json" \
  "$ASK" claude -m claude-opus-5 --effort medium -b 2 -d "$ASK_TEST_TMP/work" -o "$ASK_TEST_TMP/default" "Review the local change" >/dev/null

assert_not_contains "Optional Research Tools" "$ASK_TEST_TMP/default/prompt.md"
assert_contains "stub claude review" "$ASK_TEST_TMP/default/artifact.md"
python3 "$ASK_TEST_TMP/check-claude-args.py" "$ASK_TEST_TMP/claude-default-args.json" "$ASK_TEST_TMP/work" default

# Relative -o resolves against the caller's cwd, not the claude workdir.
(cd "$ASK_TEST_TMP" && CLAUDE_ARGS_CAPTURE="$ASK_TEST_TMP/claude-research-args.json" \
  "$ASK" claude --research -m claude-fable-5 -d "$ASK_TEST_TMP/work" -o research "Review the local change" >/dev/null)
[ ! -e "$ASK_TEST_TMP/work/research" ] || fail "relative outdir landed in the claude workdir"

assert_contains "Optional Research Tools" "$ASK_TEST_TMP/research/prompt.md"
# shellcheck disable=SC2016 # literal skill token, not shell expansion.
assert_contains '$styrir-search' "$ASK_TEST_TMP/research/prompt.md"
assert_contains "Context7" "$ASK_TEST_TMP/research/prompt.md"
python3 "$ASK_TEST_TMP/check-claude-args.py" "$ASK_TEST_TMP/claude-research-args.json" "$ASK_TEST_TMP/work" research
[ ! -e "$ASK_TEST_TMP/grok-called-for-claude.txt" ] || fail "claude provider invoked grok"
unset GROK_ARGS_CAPTURE

echo "ok - ask runner native read-only claude route"

GROK_ARGS_CAPTURE="$ASK_TEST_TMP/grok-default-args.txt" \
  "$ASK" grok -d "$ASK_TEST_TMP/work" -o "$ASK_TEST_TMP/grok-default" "Review the local change" >/dev/null

assert_contains "--tools read_file,grep,list_dir" "$ASK_TEST_TMP/grok-default-args.txt"
assert_contains "--output-format streaming-json" "$ASK_TEST_TMP/grok-default-args.txt"
assert_not_contains "web_search" "$ASK_TEST_TMP/grok-default-args.txt"
assert_not_contains "--always-approve" "$ASK_TEST_TMP/grok-default-args.txt"
assert_contains "stub grok review" "$ASK_TEST_TMP/grok-default/artifact.md"
assert_contains "stub-session" "$ASK_TEST_TMP/grok-default/artifact.md"
assert_contains "stub grok review" "$ASK_TEST_TMP/grok-default/summary.md"
assert_not_contains "## Progress" "$ASK_TEST_TMP/grok-default/summary.md"

GROK_ARGS_CAPTURE="$ASK_TEST_TMP/grok-research-args.txt" \
  "$ASK" grok --research -d "$ASK_TEST_TMP/work" -o "$ASK_TEST_TMP/grok-research" "Review the local change" >/dev/null

assert_contains "--disallowed-tools run_terminal_cmd,get_task_output,kill_task,task,Agent,search_replace,hashline_edit,ask_user_question,enter_plan_mode,exit_plan_mode" "$ASK_TEST_TMP/grok-research-args.txt"
assert_not_contains "--tools " "$ASK_TEST_TMP/grok-research-args.txt"
assert_contains "Optional Research Tools" "$ASK_TEST_TMP/grok-research/prompt.md"

echo "ok - ask runner grok review lane"

GROK_ARGS_CAPTURE="$ASK_TEST_TMP/grok-build-args.txt" \
  "$ASK" grok --build --research -d "$ASK_TEST_TMP/work" -o "$ASK_TEST_TMP/grok-build" "Implement the change" >/dev/null

assert_contains "--always-approve" "$ASK_TEST_TMP/grok-build-args.txt"
assert_not_contains "--tools" "$ASK_TEST_TMP/grok-build-args.txt"
assert_not_contains "Optional Research Tools" "$ASK_TEST_TMP/grok-build/prompt.md"
assert_contains "stub grok review" "$ASK_TEST_TMP/grok-build/artifact.md"

if "$ASK" claude --build -d "$ASK_TEST_TMP/work" -o "$ASK_TEST_TMP/claude-build" "Implement the change" >/dev/null 2>&1; then
  fail "expected claude --build to be blocked"
fi
assert_contains "--build is currently wired for grok only" "$ASK_TEST_TMP/claude-build/artifact.md"

if "$ASK" grok --build -o "$ASK_TEST_TMP/grok-build-nod" "Implement the change" >/dev/null 2>&1; then
  fail "expected grok --build without -d to be blocked"
fi
assert_contains "requires an explicit -d" "$ASK_TEST_TMP/grok-build-nod/artifact.md"

echo "ok - ask runner grok build mode"

if GROK_ARGS_CAPTURE="$ASK_TEST_TMP/grok-trunc-args.txt" GROK_STUB_MODE=truncated \
  "$ASK" grok -d "$ASK_TEST_TMP/work" -o "$ASK_TEST_TMP/grok-trunc" "Review the local change" >/dev/null; then
  fail "unterminated stream must not pass"
fi
assert_contains "partial grok answer" "$ASK_TEST_TMP/grok-trunc/partial.md"
assert_contains "missing_completion" "$ASK_TEST_TMP/grok-trunc/result.json"
assert_contains "INCOMPLETE" "$ASK_TEST_TMP/grok-trunc/summary.md"

if GROK_ARGS_CAPTURE="$ASK_TEST_TMP/grok-noauth-args.txt" GROK_STUB_MODE=noauth \
  "$ASK" grok -d "$ASK_TEST_TMP/work" -o "$ASK_TEST_TMP/grok-noauth" "Review the local change" >/dev/null 2>&1; then
  fail "expected unauthenticated grok run to be blocked"
fi
assert_contains "not authenticated" "$ASK_TEST_TMP/grok-noauth/artifact.md"
assert_contains "not authenticated" "$ASK_TEST_TMP/grok-noauth/summary.md"

if CLAUDE_ARGS_CAPTURE="$ASK_TEST_TMP/claude-noauth-args.json" CLAUDE_STUB_MODE=noauth \
  "$ASK" claude -m claude-opus-5 -d "$ASK_TEST_TMP/work" -o "$ASK_TEST_TMP/claude-noauth" "Review the local change" >/dev/null 2>&1; then
  fail "expected unauthenticated claude run to be blocked"
fi
[ ! -e "$ASK_TEST_TMP/claude-noauth-args.json" ] || fail "unauthenticated claude launched"
assert_contains "claude auth login" "$ASK_TEST_TMP/claude-noauth/artifact.md"

echo "ok - ask runner grok and claude transport guard rails"

# ops-ts4: proxy-down fail-closed — the resolved base_url points at a closed
# port, so preflight must block (exit 2) naming the endpoint and the auth
# owner. Proxy-owned routes remain a grok-provider concern.
set +e
GROK_ARGS_CAPTURE="$ASK_TEST_TMP/grok-proxydown-args.txt" \
  ASK_GROK_CONFIG="$ASK_TEST_TMP/grok-config-down.toml" \
  "$ASK" grok -m gpt-5.6-sol -d "$ASK_TEST_TMP/work" -o "$ASK_TEST_TMP/grok-proxydown" "Review the local change" >/dev/null 2>&1
PROXY_DOWN_STATUS=$?
set -e
[ "$PROXY_DOWN_STATUS" -eq 2 ] || fail "expected proxy-down grok route to exit 2, got $PROXY_DOWN_STATUS"
[ ! -e "$ASK_TEST_TMP/grok-proxydown-args.txt" ] || fail "proxy-down route launched grok"
assert_contains "http://127.0.0.1:1/v1" "$ASK_TEST_TMP/grok-proxydown/artifact.md"
assert_contains "vibeproxy" "$ASK_TEST_TMP/grok-proxydown/artifact.md"

# ops-ts4: native xAI model — no [model.*] base_url in the route config, so
# the proxy probe must not run at all.
GROK_ARGS_CAPTURE="$ASK_TEST_TMP/grok-native-args.txt" CURL_CALLS_CAPTURE="$ASK_TEST_TMP/curl-native-calls.txt" \
  "$ASK" grok -m grok-4.6 -d "$ASK_TEST_TMP/work" -o "$ASK_TEST_TMP/grok-native" "Review the local change" >/dev/null

assert_contains "-m grok-4.6" "$ASK_TEST_TMP/grok-native-args.txt"
assert_contains "stub grok review" "$ASK_TEST_TMP/grok-native/artifact.md"
[ ! -e "$ASK_TEST_TMP/curl-native-calls.txt" ] || fail "native xAI model unexpectedly probed the proxy"

echo "ok - ask runner proxy route preflight probe"

# ops-ts4: --route-status prints exactly one JSON object on stdout, runs no
# consultation, and reports route + health facts without credential material.
mkdir -p "$ASK_TEST_TMP/route-status-cwd"
(cd "$ASK_TEST_TMP/route-status-cwd" && "$ASK" claude --route-status) > "$ASK_TEST_TMP/route-status.json" 2>"$ASK_TEST_TMP/route-status.err"
python3 - "$ASK_TEST_TMP/route-status.json" <<'PY'
import json, sys

d = json.load(open(sys.argv[1]))
expected_keys = {"provider", "transport", "model", "endpoint", "authOwner",
                 "endpointHealthy", "modelListed", "cliFound",
                 "authCheckPassed", "rollback"}
assert set(d) == expected_keys, sorted(d)
assert d["provider"] == "claude", d
assert d["transport"] == "claude", d
assert d["model"] == "claude-opus-5-5", d
assert d["endpoint"] is None and d["authOwner"] is None and d["rollback"] is None, d
assert d["endpointHealthy"] is None and d["modelListed"] is None, d
assert d["cliFound"] is True, d
assert d["authCheckPassed"] is True, d
assert "sk-dummy" not in json.dumps(d), d
PY
[ ! -e "$ASK_TEST_TMP/route-status-cwd/.ask" ] || fail "--route-status must not create an outdir"

# Proxy-owned grok route still reports endpoint health.
(cd "$ASK_TEST_TMP/route-status-cwd" && "$ASK" grok -m gpt-5.6-sol --route-status) > "$ASK_TEST_TMP/route-status-grok.json" 2>/dev/null
python3 - "$ASK_TEST_TMP/route-status-grok.json" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
assert d["transport"] == "grok" and d["endpoint"] == "http://127.0.0.1:8318/v1", d
assert d["endpointHealthy"] is True and d["modelListed"] is True, d
assert "sk-dummy" not in json.dumps(d), d
PY

if "$ASK" claude --transport proxy -m claude-opus-5-5 -o "$ASK_TEST_TMP/claude-proxy" "x" >/dev/null 2>"$ASK_TEST_TMP/claude-proxy.err"; then
  fail "claude --transport proxy must be refused"
fi
grep -q "native claude CLI" "$ASK_TEST_TMP/claude-proxy.err" || fail "claude proxy refusal message missing"

echo "ok - ask runner route status"

# summary.md extraction: review-shaped output keeps VERDICT + numbered
# findings only; other output falls back to the last paragraph.
mkdir -p "$ASK_TEST_TMP/verdict"
cat > "$ASK_TEST_TMP/verdict/trace.jsonl" <<'JSON'
{"type":"text","data":"Preamble prose that must not leak into the summary.\n\nVERDICT: REVISE\n\nExplanatory paragraph, also excluded.\n\n1. finding one\n2. finding two\n   with a wrapped continuation line\n\nClosing remarks, excluded."}
{"type":"end","stopReason":"EndTurn","sessionId":"stub-verdict"}
JSON
node --experimental-strip-types "$ROOT/scripts/grok-stream-surface.ts" \
  --from-file "$ASK_TEST_TMP/verdict/trace.jsonl" "$ASK_TEST_TMP/verdict/artifact.md" 2>/dev/null

assert_contains "VERDICT: REVISE" "$ASK_TEST_TMP/verdict/summary.md"
assert_contains "1. finding one" "$ASK_TEST_TMP/verdict/summary.md"
assert_contains "wrapped continuation line" "$ASK_TEST_TMP/verdict/summary.md"
assert_not_contains "Preamble prose" "$ASK_TEST_TMP/verdict/summary.md"
assert_not_contains "Explanatory paragraph" "$ASK_TEST_TMP/verdict/summary.md"
assert_not_contains "Closing remarks" "$ASK_TEST_TMP/verdict/summary.md"
assert_contains "Preamble prose" "$ASK_TEST_TMP/verdict/artifact.md"

mkdir -p "$ASK_TEST_TMP/jsonl-tail"
cat > "$ASK_TEST_TMP/jsonl-tail/trace.jsonl" <<'JSON'
{"type":"text","data":"Build narration that should not appear.\n\n{\"slice\":\"s1\",\"status\":\"done\"}\n{\"slice\":\"s2\",\"status\":\"done\"}"}
{"type":"end","stopReason":"EndTurn","sessionId":"stub-jsonl"}
JSON
node --experimental-strip-types "$ROOT/scripts/grok-stream-surface.ts" \
  --from-file "$ASK_TEST_TMP/jsonl-tail/trace.jsonl" "$ASK_TEST_TMP/jsonl-tail/artifact.md" 2>/dev/null

assert_contains '{"slice":"s1","status":"done"}' "$ASK_TEST_TMP/jsonl-tail/summary.md"
assert_not_contains "Build narration" "$ASK_TEST_TMP/jsonl-tail/summary.md"

echo "ok - ask runner summary extraction"

# Named models and output directories must fail before provider launch.
if GROK_ARGS_CAPTURE="$ASK_TEST_TMP/unknown-args" "$ASK" grok -m unknown-model -o "$ASK_TEST_TMP/unknown-model" "test" >/dev/null 2>&1; then
  fail "unknown native model must be refused"
fi
[ ! -e "$ASK_TEST_TMP/unknown-args" ] || fail "unknown model launched"
if GROK_ARGS_CAPTURE="$ASK_TEST_TMP/reuse-args" "$ASK" grok -o "$ASK_TEST_TMP/grok-default" "test" >/dev/null 2>&1; then
  fail "existing output directory must be refused"
fi
[ ! -e "$ASK_TEST_TMP/reuse-args" ] || fail "reused directory launched"
echo "ok - exact native model and fresh attempt guards"
