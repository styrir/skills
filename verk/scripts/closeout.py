#!/usr/bin/env python3
"""Close explicitly ready Verk work; the Stop hook only follows a pending request."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from verk import invocation


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, timeout=5).strip()


def call(repo, env, *args, timeout=30, structured=True):
    command, cwd, scoped = invocation(["--repo", str(repo), *args], env)
    result = subprocess.run(command, cwd=cwd, env=scoped, capture_output=True, text=True, timeout=timeout)
    if result.returncode:
        raise ValueError((result.stderr or result.stdout).strip()[-3000:] or f"Verk exited {result.returncode}")
    if not structured:
        return None
    response = json.loads(result.stdout)
    if not response.get("ok"):
        raise ValueError(json.dumps(response.get("error", response)))
    return response["data"]


def state_path(repo, env):
    _, _, scoped = invocation(["--repo", str(repo), "brief", "--json"], env)
    # Scratch stores keep their requests isolated too; this cache is never task truth.
    root = Path(env["VERK_HOME"]) / "codex-closeout" if env.get("VERK_HOME") else Path.home() / ".cache/verk-closeout"
    return root / (scoped["VERK_SESSION"] + ".json")


def save(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    with temporary.open("w") as handle:
        os.chmod(temporary, 0o600)
        json.dump(data, handle)
    temporary.replace(path)


def observe(repo, env, contract, head, wait, call_timeout=10):
    deadline = time.monotonic() + wait
    while True:
        view = call(repo, env, "view", contract, "--json", timeout=call_timeout)
        if view["state"] == "satisfied":
            receipt = next((r for r in reversed(view["receipts"]) if r["revision"] == head), None)
            if receipt:
                return {"status": "receipt", "contract": contract, "receipt": receipt["id"], "revision": head}
            return {"status": "needs_action", "contract": contract, "reason": "Receipt does not cover current HEAD"}
        reviews = view.get("reviews", [])
        pending = [r["decision"] for r in reviews if r["lifecycle"] == "open"]
        if not pending and any(r["verdict"] == "rejected" and r["lifecycle"] == "answered" for r in reviews):
            return {"status": "needs_action", "contract": contract, "reason": "Independent review rejected the work; inspect the review report"}
        if not pending:
            return {"status": "needs_action", "contract": contract, "reason": "No receipt or open review; inspect Verk view", "state": view["state"]}
        if time.monotonic() >= deadline:
            return {"status": "review_pending", "contract": contract, "reviews": pending}
        time.sleep(min(2, max(0, deadline - time.monotonic())))


def closeout(repo, env, contract, proof, wait, qualification=None, source_only=False):
    repo = repo.resolve()
    path = state_path(repo, env)
    head = git(repo, "rev-parse", "HEAD")
    if git(repo, "status", "--porcelain"):
        raise ValueError("Closeout requires a committed, clean worktree")
    if qualification:
        record = repo / qualification
        if record.is_symlink() or not record.is_file():
            raise ValueError("Qualification must be a regular committed repository file")
        qualification = str(record.resolve().relative_to(repo))
        git(repo, "ls-files", "--error-unmatch", "--", qualification)
        proof = qualification
    elif not source_only:
        raise ValueError("Declare --qualification PATH for installed/live evidence, or --source-only when acceptance requires none")
    view = call(repo, env, "view", contract, "--json")
    contract = view["contract"]["id"]
    if view["state"] != "satisfied":
        open_reviews = [call(repo, env, "view", r["decision"], "--json")
                        for r in view.get("reviews", []) if r["lifecycle"] == "open"]
        current_review = any(r.get("target", {}).get("revision") == head for r in open_reviews)
        if not current_review:
            # checkpoint acts on the selected attempt: start refuses to replace another held task.
            call(repo, env, "start", contract, "--json")
            checks = view["policy"]["checks"]
            for check in checks:
                if check["status"] != "passed" or open_reviews:
                    # Producer deadline ends its check process group before this outer timeout.
                    until = str(int((time.time() + 590) * 1000))
                    call(repo, env, "check", check["name"], "--id", contract, "--until", until, timeout=600, structured=False)
            if not checks:
                if not proof:
                    raise ValueError("Review-only code needs --proof pointing to a committed repository file")
                # Verk validates the path, repository, committed bytes and policy; never synthesize evidence here.
                call(repo, env, "checkpoint", "--next", "Independent review of ready work", "--proof", proof, "--json")
        if git(repo, "rev-parse", "HEAD") != head or git(repo, "status", "--porcelain"):
            raise ValueError("Ready work changed during closeout; inspect evidence before requesting it again")
        call(repo, env, "reconcile", "--id", contract, "--json")
    result = observe(repo, env, contract, head, wait)
    if result["status"] == "review_pending":
        save(path, {"repo": str(repo), "contract": contract, "head": head,
                    "common_dir": git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"),
                    "qualification": qualification, "source_only": source_only})
    else:
        path.unlink(missing_ok=True)
    save(path.with_suffix(".result.json"), result)
    return result


def hook(payload, env):
    if not isinstance(payload, dict):
        raise ValueError("Stop payload must be an object")
    if payload.get("hook_event_name") != "Stop" or payload.get("stop_hook_active"):
        return {}
    session = payload.get("session_id")
    if not isinstance(session, str) or not session:
        raise ValueError("Stop payload has no session identity")
    existing = env.get("CODEX_THREAD_ID") or env.get("CODEX_SESSION_ID")
    if existing and existing != session:
        raise ValueError("Stop session differs from Codex execution identity")
    scoped = dict(env, CODEX_THREAD_ID=session)
    repo = Path(payload["cwd"]).resolve()
    try:
        path = state_path(repo, scoped)
    except subprocess.CalledProcessError:
        return {}  # No repository means no requested repository closeout.
    claim = path.with_suffix(f".{os.getpid()}.running")
    try:
        # Atomic consumption prevents duplicate Stop deliveries from replaying a write.
        path.rename(claim)
    except FileNotFoundError:
        return {}
    request = {}
    try:
        request = json.loads(claim.read_text())
        if not isinstance(request, dict):
            raise ValueError("Malformed closeout request")
        repo = Path(request["repo"]).resolve()
        if (git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir") != request["common_dir"] or
                git(repo, "rev-parse", "HEAD") != request["head"] or git(repo, "status", "--porcelain")):
            raise ValueError("Ready work changed; request closeout again after checking it")
        call(repo, scoped, "reconcile", "--id", request["contract"], "--json", timeout=5)
        result = observe(repo, scoped, request["contract"], request["head"], 0, call_timeout=5)
        save(path.with_suffix(".result.json"), result)
        return {"systemMessage": "Verk closeout: " + json.dumps(result)}
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        result = {"status": "needs_action", "contract": request.get("contract") if isinstance(request, dict) else None, "reason": str(error)}
        save(path.with_suffix(".result.json"), result)
        return {"systemMessage": "Verk closeout: " + json.dumps(result)}
    finally:
        claim.unlink(missing_ok=True)


def main():
    if sys.argv[1:] == ["hook-stop"]:
        try:
            result = hook(json.load(sys.stdin), os.environ)
        except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
            result = {"systemMessage": f"Verk closeout needs attention: {error}"}
        print(json.dumps(result))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--id", required=True)
    parser.add_argument("--proof")
    qualification = parser.add_mutually_exclusive_group(required=True)
    qualification.add_argument("--qualification", help="Committed diagnosis/checks/installed/operator/limits record")
    qualification.add_argument("--source-only", action="store_true", help="Acceptance requires no installed/live/operator qualification")
    parser.add_argument("--wait", type=int, default=30, choices=range(0, 61), metavar="0..60")
    args = parser.parse_args()
    try:
        result = closeout(args.repo.resolve(), os.environ, args.id, args.proof, args.wait, args.qualification, args.source_only)
        print(json.dumps(result))
        return 0 if result["status"] == "receipt" else 3
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Verk closeout: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
