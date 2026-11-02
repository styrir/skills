"""Codex's review-completion adapter; shared/Claude closeout stays unchanged."""
import json
from pathlib import Path
import subprocess
import time

import closeout as shared
from codex_review import complete_goal


def observe(repo, env, request, wait=0):
    deadline = time.monotonic() + wait
    while True:
        result = shared.observe(repo, env, request["contract"], request["head"], 0, call_timeout=5)
        if result["status"] != "review_pending":
            return result
        if request.get("delegate_approved_goals"):
            view = shared.call(repo, env, "view", request["contract"], "--json", timeout=5)
            for review in result["reviews"]:
                decision = shared.call(repo, env, "view", review, "--json", timeout=5)
                if complete_goal(repo, env, view, decision, request["head"], shared.call, shared.git):
                    return shared.observe(repo, env, request["contract"], request["head"], 0)
        if time.monotonic() >= deadline:
            return result
        time.sleep(min(2, max(0, deadline - time.monotonic())))


def closeout(repo, env, contract, proof, wait, qualification=None, source_only=False, delegate_approved_goals=False):
    if env.get("VERK_CLOSEOUT_HARNESS", "codex") != "codex":
        raise ValueError("This review-completion adapter is Codex-only")
    result = shared.closeout(repo, env, contract, proof, 0, qualification, source_only)
    if result["status"] != "review_pending":
        return result
    path = shared.state_path(repo, env)
    request = json.loads(path.read_text())
    request["delegate_approved_goals"] = delegate_approved_goals
    shared.save(path, request)
    result = observe(repo, env, request, wait)
    shared.save(path.with_suffix(".result.json"), result)
    if result["status"] == "receipt" and json.loads(path.read_text()) == request:
        path.unlink()
    return result


def hook(payload, env):
    if not isinstance(payload, dict):
        raise ValueError("Stop payload must be an object")
    if payload.get("hook_event_name") != "Stop":
        return {}
    session = payload.get("session_id")
    existing = env.get("CODEX_THREAD_ID") or env.get("CODEX_SESSION_ID")
    if not session or existing and existing != session:
        raise ValueError("Stop session differs from Codex execution identity")
    scoped = dict(env, CODEX_THREAD_ID=session)
    path = shared.state_path(Path(payload["cwd"]), scoped)
    try:
        raw = path.read_text()
    except FileNotFoundError:
        return {}
    request = None
    result = {"status": "needs_action", "reason": "Malformed Codex closeout request"}
    try:
        request = json.loads(raw)
        if not isinstance(request, dict):
            raise ValueError("Malformed Codex closeout request")
        repo = Path(request["repo"]).resolve()
        if (shared.git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir") != request["common_dir"]
                or shared.git(repo, "rev-parse", "HEAD") != request["head"]
                or shared.git(repo, "status", "--porcelain")):
            raise ValueError("Ready work changed; re-qualify and request closeout at current HEAD")
        shared.call(repo, scoped, "reconcile", "--id", request["contract"], "--json", timeout=5)
        result = observe(repo, scoped, request)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        result = {"status": "needs_action", "reason": str(error)}
    shared.save(path.with_suffix(".result.json"), result)
    if result["status"] == "receipt":
        # Leave the marker in place through every fallible call and hard exit.
        # Codex serializes Stop per session; Verk rejects duplicate answers.
        if path.exists() and path.read_text() == raw:
            path.unlink()
        return {"systemMessage": "Verk closeout: " + json.dumps(result)}
    return {"decision": "block", "reason": "Complete the requested Verk review before finishing. "
            + json.dumps(result) + ". Wait for the independent verdict, repair findings and rerun Codex closeout; "
            "use the recorded operator delegation for an independently approved goal. Do not ask for terminal chores."}
