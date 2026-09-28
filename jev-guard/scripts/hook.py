#!/usr/bin/env python3
"""jev-guard hook adapter for Claude Code, Codex CLI, and Grok CLI command hooks.

  hook.py --harness claude|codex|grok --mode pretool|posttool|permission|prompt [--enforce]
          [--allow-family REGEX] [--timeout SECONDS]

Profiles:
  observe (default)  ask Jev and write the decision ledger, emit nothing: a shadow run, zero behaviour change.
  --enforce          emit decisions. pretool may only DENY; posttool may only ADD a warning; prompt may only
                     SHOW the user an advisory; permission may only ALLOW, and only for --allow-family matches.

Every failure (no key, timeout, bad stdin, Jev error) prints nothing and exits 0: the harness proceeds exactly
as it would without this hook. The static rules in guard_policy are applied even when Jev is unreachable.

Grok imports Claude Code hooks by default and sends camelCase stdin; when GROK_HOOK_EVENT is set the adapter
parses as Grok regardless of --harness. Contracts verified 2026-09-28 against Claude Code 2.1.283 docs,
Codex 0.157.1 source, and Grok 1.0.42 shipped docs (see references/hook-contracts.md).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(os.path.realpath(__file__)).parent))
import guard_policy as gp  # noqa: E402

LEDGER = Path(os.path.expanduser(os.environ.get("JEV_GUARD_LEDGER", "~/.local/state/jev-guard/decisions.jsonl")))
STATE_DIR = LEDGER.parent
SHELL_TOOLS = {"Bash", "bash", "run_terminal_command", "run_terminal_cmd", "exec_command", "shell"}
SCREEN_CHARS = 6000


def field(ev: dict, *names, default=None):
    for n in names:
        if n in ev and ev[n] is not None:
            return ev[n]
    return default


def parse(ev: dict) -> dict:
    tool_input = field(ev, "tool_input", "toolInput", default={}) or {}
    result = field(ev, "tool_response", "toolResult", "tool_output", default=None)
    return {
        "event": field(ev, "hook_event_name", "hookEventName", default=""),
        "tool": field(ev, "tool_name", "toolName", default=""),
        "command": tool_input.get("command") if isinstance(tool_input, dict) else None,
        "cwd": field(ev, "cwd", "workspaceRoot", default=os.getcwd()),
        "session": field(ev, "session_id", "sessionId", default=""),
        "transcript": field(ev, "transcript_path", "transcriptPath", default=None),
        "prompt": field(ev, "prompt", "userPrompt", default=""),
        "permission_mode": field(ev, "permission_mode", "permissionMode", default=""),
        "result": result,
    }


def emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj))
    sys.stdout.flush()


def log(entry: dict) -> None:
    try:
        LEDGER.parent.mkdir(parents=True, exist_ok=True)
        with LEDGER.open("a") as f:
            f.write(json.dumps({"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "policy": gp.POLICY_VERSION, **entry}) + "\n")
    except OSError:
        pass


def sha(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def result_text(result) -> str:
    """Flatten the harness's tool result into text; judge only the head, where an injection leads."""
    if result is None:
        return ""
    if isinstance(result, str):
        return result
    if isinstance(result, dict):
        parts = [str(result[k]) for k in ("stdout", "stderr", "output", "content", "text", "result") if result.get(k)]
        return "\n".join(parts) if parts else json.dumps(result)[:SCREEN_CHARS]
    if isinstance(result, list):
        return "\n".join(x.get("text", "") if isinstance(x, dict) else str(x) for x in result)
    return str(result)


# ---------------------------------------------------------------- modes

def mode_pretool(p: dict, args) -> None:
    cmd = p["command"]
    if p["tool"] not in SHELL_TOOLS or not isinstance(cmd, str) or not cmd.strip():
        return
    static = bool(gp.STATIC_HOLD.search(cmd))
    answers = None if static else gp.judge({"command": cmd, "cwd": p["cwd"]}, gp.BASH_QUESTIONS,
                                           timeout=args.timeout, tag="guard:pretool")
    block, reason = gp.hold_decision(cmd, answers)
    log({"mode": "pretool", "harness": args.harness, "enforce": args.enforce, "cmd_sha": sha(cmd),
         "block": block, "reason": reason, "jev": answers is not None, "static": static})
    if block and args.enforce:
        emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                     "permissionDecisionReason": f"{reason}. {gp.BLOCK_NOTICE}"}})


def mode_permission(p: dict, args) -> None:
    if args.harness == "grok":
        return  # Grok has no PermissionRequest event; a hook cannot approve there.
    cmd = p["command"]
    if p["tool"] not in SHELL_TOOLS or not isinstance(cmd, str) or not cmd.strip():
        return
    if not args.allow_family or not re.search(args.allow_family, cmd):
        log({"mode": "permission", "harness": args.harness, "cmd_sha": sha(cmd), "allow": False,
             "reason": "outside --allow-family"})
        return
    answers = gp.judge({"command": cmd, "cwd": p["cwd"]}, gp.BASH_QUESTIONS, timeout=args.timeout,
                       tag="guard:permission")
    ok, reason = gp.approve_decision(cmd, answers)
    log({"mode": "permission", "harness": args.harness, "enforce": args.enforce, "cmd_sha": sha(cmd),
         "allow": ok, "reason": reason, "jev": answers is not None})
    if ok and args.enforce:
        emit({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "allow"}}})


def mode_posttool(p: dict, args) -> None:
    text = result_text(p["result"])[:SCREEN_CHARS]
    if len(text.strip()) < 40:
        return
    answers = gp.judge({"tool": p["tool"], "content": text}, gp.HOSTILE_QUESTIONS, timeout=args.timeout,
                       tag="guard:posttool")
    if answers is None:
        return
    v = answers["hostile"]["noul"]
    flag = v >= gp.HOSTILE_T
    log({"mode": "posttool", "harness": args.harness, "enforce": args.enforce, "tool": p["tool"],
         "content_sha": sha(text), "hostile": v, "flag": flag})
    if flag and args.enforce:
        # additionalContext only: Codex would REPLACE the tool result on decision:block.
        emit({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": gp.hostile_banner(v)}})


def transcript_state(path: str | None, prompt: str) -> tuple[dict | None, int]:
    """Claude Code transcript JSONL -> (compaction state, context tokens). Format is not a stable interface."""
    if not path or not os.path.isfile(path):
        return None, 0
    users, last_assistant, tokens = [], "", 0
    try:
        with open(path, errors="replace") as f:
            for line in f:
                try:
                    e = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if e.get("isSidechain"):
                    continue
                msg = e.get("message") or {}
                if e.get("type") == "assistant":
                    u = msg.get("usage") or {}
                    if u:
                        tokens = (u.get("input_tokens", 0) + u.get("cache_creation_input_tokens", 0)
                                  + u.get("cache_read_input_tokens", 0))
                    texts = [c.get("text", "") for c in msg.get("content", []) if isinstance(c, dict) and c.get("type") == "text"]
                    if texts:
                        last_assistant = texts[-1]
                elif e.get("type") == "user" and isinstance(msg.get("content"), str):
                    users.append(msg["content"])
    except OSError:
        return None, 0
    prev = [u for u in users if not u.startswith("<")][-4:]
    state = {"current_request": prompt[:1500], "previous_work": "\n---\n".join(x[:600] for x in prev),
             "recent_turn": last_assistant[-1500:]}
    return state, tokens


def mode_prompt(p: dict, args) -> None:
    if args.harness != "claude":
        return  # Codex transcript_path is nullable/unstable; Grok discards UserPromptSubmit output.
    state, tokens = transcript_state(p["transcript"], p["prompt"] or "")
    if not state or tokens < args.min_context or not state["previous_work"]:
        return
    cool = STATE_DIR / f"prompt-cooldown-{sha(p['session'] or 'none')}"
    try:
        if cool.exists() and time.time() - cool.stat().st_mtime < args.cooldown:
            return
    except OSError:
        pass
    answers = gp.judge(state, gp.COMPACT_QUESTIONS, timeout=args.timeout, tag="guard:prompt")
    if answers is None:
        return
    switched = answers["switched_gears"]["noul"]
    mid = answers["mid_operation"]["noul"]
    needs = answers["needs_history"]["score"]
    advise = switched > 0.7 and mid < 0.6 and needs < 1.5
    log({"mode": "prompt", "harness": args.harness, "enforce": args.enforce, "tokens": tokens,
         "switched": switched, "mid_operation": mid, "needs_history": needs, "advise": advise})
    if advise and args.enforce:
        try:
            STATE_DIR.mkdir(parents=True, exist_ok=True); cool.touch()
        except OSError:
            pass
        emit({"systemMessage": (f"jev-guard: this looks like a new task (switch {switched:.2f}) while the session "
                                f"carries ~{tokens // 1000}k tokens of earlier context. Consider /compact (keeps a "
                                f"summary) or /clear before continuing.")})


MODES = {"pretool": mode_pretool, "permission": mode_permission, "posttool": mode_posttool, "prompt": mode_prompt}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--harness", required=True, choices=["claude", "codex", "grok"])
    ap.add_argument("--mode", required=True, choices=list(MODES))
    ap.add_argument("--enforce", action="store_true", help="emit decisions (default: observe/shadow only)")
    ap.add_argument("--allow-family", default=None, help="permission mode: regex a command must match to be eligible")
    ap.add_argument("--timeout", type=float, default=float(os.environ.get("JEV_GUARD_TIMEOUT", "3")))
    ap.add_argument("--min-context", type=int, default=150_000, help="prompt mode: tokens before advising")
    ap.add_argument("--cooldown", type=int, default=1800, help="prompt mode: seconds between advisories")
    args = ap.parse_args()
    if os.environ.get("GROK_HOOK_EVENT"):
        args.harness = "grok"   # Grok runs imported Claude hooks with its own camelCase contract.
    try:
        ev = json.loads(sys.stdin.read() or "{}")
        MODES[args.mode](parse(ev if isinstance(ev, dict) else {}), args)
    except Exception as e:  # noqa: BLE001 — a hook must never break the harness
        print(f"jev-guard: {e.__class__.__name__}: {e}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
