"""Codex's review-completion adapter; shared/Claude closeout stays unchanged."""
import json
from pathlib import Path
import subprocess
import time

import closeout as shared
from codex_review import complete_goal

# A blocked Stop costs a model turn. The limit is on unchanged results, so a result that moves keeps its continuations.
MAX_BLOCKED_STOPS = 10


def complete(repo, env, request, wait=0):
    """Writes: may answer an independently approved goal under the request's recorded delegation. Use shared.observe to only read."""
    deadline = time.monotonic() + wait
    while True:
        result = shared.observe(repo, env, request["contract"], request["head"], 0, call_timeout=5)
        if result["status"] != "review_pending":
            return result
        if request.get("delegate_approved_goals"):
            view = shared.call(repo, env, "view", request["contract"], "--json", timeout=5)
            for review in result["reviews"]:
                decision = shared.call(repo, env, "view", review, "--json", timeout=5)
                current = lambda: shared.request_is_current(shared.state_path(env), request)
                if complete_goal(repo, env, view, decision, request["head"], shared.call, shared.git, current):
                    return shared.observe(repo, env, request["contract"], request["head"], 0)
        if time.monotonic() >= deadline:
            return result
        time.sleep(min(2, max(0, deadline - time.monotonic())))


def ready(repo, request):
    if (shared.git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir") != request["common_dir"]
            or shared.git(repo, "rev-parse", "HEAD") != request["head"]
            or shared.git(repo, "status", "--porcelain")):
        raise ValueError("Ready work changed; re-qualify and request closeout at current HEAD")


def checkout_present(repo):
    if not repo.is_dir():
        return False
    try:
        shared.git(repo, "rev-parse", "--git-dir")
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def current_receipt(view, request):
    """Only the receipt Verk names as current proof, for this request's own target. A matching historical entry is not proof."""
    proof = view.get("proof") or {}
    described = view.get("contract") or {}
    if (proof.get("status") != "valid" or described.get("id") != request["contract"]
            or (request.get("project") and described.get("project") != request["project"])):
        return None
    receipt = next((r for r in view.get("receipts", []) if r.get("id") == proof.get("receipt")), None)
    if not receipt:
        return None
    artifact = receipt.get("artifact") or {}
    if request["head"] not in (receipt.get("revision"), artifact.get("revision")):
        return None
    wanted = request.get("artifact") or {}
    if any(artifact.get(key) != value for key, value in wanted.items()):
        return None
    return receipt


def recover(read_dir, env, request, path):
    """The missing-checkout branch: at most one Verk read and no writes to Verk. The selected directory only hosts the read; it runs nothing and answers nothing."""
    contract = request["contract"]
    receipt, proof = None, "not_read: no surviving directory selected"
    if read_dir:
        try:
            view = shared.call(read_dir, env, "view", contract, "--json", timeout=5)
            receipt = current_receipt(view, request)
            proof = (view.get("proof") or {}).get("status")
        except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
            proof = f"unreadable: {str(error)[:200]}"
    if receipt:
        return {"status": "receipt", "contract": contract, "receipt": receipt["id"], "revision": request["head"], "recovered": "checkout_missing"}
    result = {"status": "needs_action", "needs_action": "checkout_missing", "contract": contract, "revision": request["head"], "proof": proof,
              "reason": "The recorded checkout is gone and no selected directory shows a current receipt for this request; no checks or repair were started",
              "request_id": request.get("request_id")}
    return result


def counted(path, request, result):
    """How many Stops in a row have blocked on this same result for this same request. Any change starts again at 1."""
    result = dict(result, request_id=(request or {}).get("request_id"))
    try:
        with shared.request_lock(path):
            previous = json.loads(path.with_suffix(".result.json").read_text())
    except (OSError, ValueError):
        previous = {}
    unchanged = isinstance(previous, dict) and {k: v for k, v in previous.items() if k != "repeat"} == result
    return dict(result, repeat=shared.number(previous.get("repeat")) + 1 if unchanged else 1)


def selected_directory(env):
    """The directory the operator or author selected to host recovery's read. Never inferred from the host's cwd or home."""
    selected = env.get("VERK_CLOSEOUT_READ_DIR")
    return Path(selected).resolve() if selected and Path(selected).is_dir() else None


def recover_pending(read_dir, env, contract):
    """The explicit foreground route to recover(), hosted by the directory the caller chose."""
    path = shared.state_path(env)
    with shared.request_lock(path):
        request = shared.read_request(path)
    if request is None:
        raise ValueError("No pending closeout request in this session")
    if checkout_present(Path(request["repo"]).resolve()):
        raise ValueError("The recorded checkout is present; use closeout or reconcile there")
    if shared.call(read_dir, env, "view", contract, "--json", timeout=5)["contract"]["id"] != request["contract"]:
        raise ValueError(f"The pending closeout request is not for {contract}")
    result = recover(read_dir, env, request, path)
    shared.settle(path, request, result, consume=result["status"] == "receipt")
    return result


def complete_pending(repo, env, contract, wait=0):
    """The explicit foreground route to complete(), for the pending request of this session and contract."""
    path = shared.state_path(env)
    with shared.request_lock(path):
        request = shared.read_request(path)
    if request is None:
        raise ValueError("No pending closeout request in this session")
    canonical = shared.call(repo, env, "view", contract, "--json")["contract"]["id"]
    if request.get("contract") != canonical:
        raise ValueError(f"The pending closeout request is not for {canonical}")
    target = Path(request["repo"]).resolve()
    ready(target, request)
    result = complete(target, env, request, wait)
    shared.settle(path, request, result, consume=result["status"] == "receipt")
    return result


def closeout(repo, env, contract, proof, wait, qualification=None, source_only=False, delegate_approved_goals=False):
    if env.get("VERK_CLOSEOUT_HARNESS", "codex") != "codex":
        raise ValueError("This review-completion adapter is Codex-only")
    result = shared.closeout(repo, env, contract, proof, 0, qualification, source_only, delegate_approved_goals)
    if result["status"] != "review_pending" or result.get("superseded"):
        return result
    path = shared.state_path(env)
    with shared.request_lock(path):
        request = shared.read_request(path)
    # Only the request this closeout wrote, with the delegation written alongside it: never another's.
    if request is None or request.get("request_id") != result.get("request_id"):
        return dict(result, superseded=True)
    result = complete(repo, env, request, wait)
    shared.settle(path, request, result, consume=result["status"] == "receipt")
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
    path = shared.state_path(scoped)
    request = None
    result = {"status": "needs_action", "reason": "Malformed Codex closeout request"}
    try:
        with shared.request_lock(path):
            request = shared.read_request(path)
        if request is None:
            return {}
        repo = Path(request["repo"]).resolve()
        if checkout_present(repo):
            ready(repo, request)
            shared.call(repo, scoped, "reconcile", "--id", request["contract"], "--json", timeout=5)
            result = complete(repo, scoped, request)
        else:
            result = recover(selected_directory(scoped), scoped, request, path)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        result = {"status": "needs_action", "reason": str(error)}
    if result["status"] != "receipt":
        result = counted(path, request, result)
    if request is None:  # Unreadable: keep it and block, as nothing could be checked.
        with shared.request_lock(path):
            shared.save(path.with_suffix(".result.json"), result)
    else:
        # Leave the marker in place through every fallible call and hard exit; only the same request is settled.
        settled = shared.settle(path, request, result, consume=result["status"] == "receipt")
        if settled == "gone":
            return {}  # An overlapping Stop or foreground closeout already settled it.
        if settled == "replaced":
            result = {"status": "needs_action", "reason": "A newer closeout request replaced the one this Stop checked; it stays pending"}
        elif result["status"] == "receipt":
            return {"systemMessage": "Verk closeout: " + json.dumps(result)}
    repeat = result.get("repeat", 1)
    if repeat > MAX_BLOCKED_STOPS:
        return {"systemMessage": f"Verk closeout is unresolved and no longer continuing this session: unchanged after {MAX_BLOCKED_STOPS} blocked Stops. "
                "Nothing was accepted and the request is kept; a changed result blocks again. " + json.dumps(result)}
    last = (" This is the last continuation: if it is still unchanged, say in your final message that the closeout is unresolved."
            if repeat == MAX_BLOCKED_STOPS else "")
    if result.get("needs_action") == "checkout_missing":
        if repeat > 1:
            return {"decision": "block", "reason": f"Verk closeout: still checkout_missing for {result['contract']}, unchanged ({repeat} callbacks)." + last}
        return {"decision": "block", "reason": "Verk closeout is blocked: " + json.dumps(result)
                + f". Restore the checkout, request closeout again from a current one, or look for its receipt with `closeout.py recover --repo <surviving directory> --id {result['contract']}`. "
                "Do not start checks or repair from this callback, and do not ask for terminal chores."}
    return {"decision": "block", "reason": "Complete the requested Verk review before finishing. "
            + json.dumps(result) + ". Wait for the independent verdict, repair findings and rerun Codex closeout; "
            "use the recorded operator delegation for an independently approved goal. Do not ask for terminal chores." + last}
