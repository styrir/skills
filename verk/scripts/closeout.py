#!/usr/bin/env python3
"""Close explicitly ready Verk work; the Stop hook only follows a pending request."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True  # Running from the source checkout must not dirty it.
from verk import invocation


def git(repo, *args):
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True, timeout=5).strip()


def call(repo, env, *args, timeout=30, structured=True):
    command, cwd, scoped = invocation(["--harness", env.get("VERK_CLOSEOUT_HARNESS", "codex"), "--repo", str(repo), *args], env)
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
    _, _, scoped = invocation(["--harness", env.get("VERK_CLOSEOUT_HARNESS", "codex"), "--repo", str(repo), "brief", "--json"], env)
    # Scratch stores keep their requests isolated too; this cache is never task truth.
    root = Path(env["VERK_HOME"]) / "codex-closeout" if env.get("VERK_HOME") else Path.home() / ".cache/verk-closeout"
    # ponytail: one pending request per session; add a queue if concurrent hook observations are needed.
    prefix = "claude-code-" if env.get("VERK_CLOSEOUT_HARNESS") == "claude-code" else ""
    return root / (prefix + scoped["VERK_SESSION"] + ".json")


def save(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    with temporary.open("w") as handle:
        os.chmod(temporary, 0o600)
        json.dump(data, handle)
    temporary.replace(path)


def observe(repo, env, contract, head, wait, call_timeout=10):
    """Pure read: Verk view only. No writes, producers, reconciliation or delegated completion."""
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


def reconcile(repo, env, contract, head, wait=0):
    """Explicit and writing: asks Verk to act on ready evidence, then reports. Observing never does this."""
    call(repo, env, "reconcile", "--id", contract, "--json")
    return observe(repo, env, contract, head, wait)


def current(repo, env, contract, attempt):
    """Re-observe before acting: a lapsed lease may let other work take this contract during long checks."""
    view = call(repo, env, "view", contract, "--json")
    attempts = view.get("attempts", [])
    rival = [a["id"] for a in attempts if a.get("state") == "active" and a.get("id") != attempt]
    if rival or not any(a.get("id") == attempt for a in attempts):
        raise ValueError(f"Attempt {attempt} is no longer current for {contract}"
                         f"{' (now ' + ', '.join(rival) + ')' if rival else ''}; closeout stopped without writing")
    return view


def admitted_at(check, head):
    """Core's own verdict on one check at this revision. A process exit or an aggregate passed flag never establishes it."""
    return any(e.get("revision") == head and e.get("status") in ("accepted", "used") and e.get("bindings_current") is True
               for e in check.get("evidence", []))


def review_covers(view, decision, head):
    """An open review of exactly this target: same contract, revision or artifact revision, acceptance, subjects and policy."""
    target, bound = decision.get("target") or {}, decision.get("bindings") or {}
    contract = view["contract"]
    return (decision.get("lifecycle") == "open" and contract["id"] in decision.get("contracts", [decision.get("contract")])
            and (target.get("revision") or (target.get("artifact") or {}).get("revision")) == head
            and bound.get("acceptanceVersion") == contract.get("acceptance_version")
            and bound.get("subjectsVersion") == contract.get("subjects_version")
            and bound.get("policyVersion") == view["policy"].get("version"))


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
    elif not source_only:
        raise ValueError("Declare --qualification PATH for installed/live evidence, or --source-only when acceptance requires none")
    view = call(repo, env, "view", contract, "--json")
    contract = view["contract"]["id"]
    if view["state"] != "satisfied":
        open_reviews = [call(repo, env, "view", r["decision"], "--json")
                        for r in view.get("reviews", []) if r["lifecycle"] == "open"]
        current_review = any(review_covers(view, r, head) for r in open_reviews)
        if not current_review:
            # start refuses to replace another held task; every later write names the attempt it returned.
            attempt = (call(repo, env, "start", contract, "--json").get("attempt") or {}).get("id")
            if not attempt:
                raise ValueError(f"Verk start returned no attempt for {contract}")
            checks = view["policy"]["checks"]
            proofs = list(dict.fromkeys(p for p in [proof, qualification] if p))
            if not checks and not proofs:
                raise ValueError("Review-only code needs --proof pointing to a committed repository file")
            declaration = f"Qualification record: {qualification}" if qualification else "Source-only acceptance explicitly declared"
            checkpoint = ["checkpoint", attempt, "--next", f"Independent review of ready work. {declaration}"]
            for item in proofs:
                checkpoint.extend(["--proof", item])
            # Persist the declaration and evidence before any check can open a review.
            call(repo, env, *checkpoint, *(["--keep"] if checks else []), "--json")
            admitted = False
            for check in checks:
                if current(repo, env, contract, attempt)["state"] == "satisfied":
                    admitted = True  # a receipt was admitted meanwhile; observe it instead of running more checks
                    break
                if admitted_at(check, head):
                    continue  # Verk already admitted this check for this revision under the current bindings
                # Producer deadline ends its check process group before this outer timeout.
                until = str(int((time.time() + 590) * 1000))
                call(repo, env, "check", check["name"], "--id", contract, "--until", until, timeout=600, structured=False)
                seen = current(repo, env, contract, attempt)
                ran = next((c for c in seen["policy"]["checks"] if c["name"] == check["name"]), {})
                # A Verk older than per-check evidence shows no list to confirm against.
                if "evidence" in ran and not admitted_at(ran, head):
                    why = [e.get("reason") or e.get("status") for e in ran["evidence"] if e.get("revision") == head]
                    raise ValueError(f"Check {check['name']} exited 0 but Verk did not admit it at {head}: {', '.join(why) or 'no evidence recorded'}")
        if git(repo, "rev-parse", "HEAD") != head or git(repo, "status", "--porcelain"):
            raise ValueError("Ready work changed during closeout; inspect evidence before requesting it again")
        if not current_review and checks and not admitted:
            names = ", ".join(check["name"] for check in checks)
            current(repo, env, contract, attempt)
            call(repo, env, "checkpoint", attempt, "--keep", "--next",
                 f"Independent review. {declaration}. Approved checks passed at {head}: {names}", "--json")
        call(repo, env, "reconcile", "--id", contract, "--json")
    result = observe(repo, env, contract, head, wait)
    if result["status"] == "review_pending":
        save(path, {"repo": str(repo), "contract": contract, "head": head,
                    "common_dir": git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"),
                    "qualification": qualification, "source_only": source_only})
    elif path.exists():
        previous = json.loads(path.read_text())
        if previous.get("contract") == contract and previous.get("repo") == str(repo):
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
    claude = env.get("VERK_CLOSEOUT_HARNESS") == "claude-code"
    existing = env.get("CLAUDE_CODE_SESSION_ID") if claude else env.get("CODEX_THREAD_ID") or env.get("CODEX_SESSION_ID")
    if existing and existing != session:
        raise ValueError("Stop session differs from harness execution identity")
    scoped = dict(env)
    scoped["CLAUDE_CODE_SESSION_ID" if claude else "CODEX_THREAD_ID"] = session
    repo = Path(payload["cwd"]).resolve()
    path = state_path(repo, scoped)
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


OPERATIONS = ("observe", "reconcile", "complete")


def operation(name, arguments, harness, env):
    parser = argparse.ArgumentParser(prog=f"closeout.py {name}", description={
        "observe": "Pure read of current state: writes nothing and starts nothing.",
        "reconcile": "Explicitly ask Verk to act on ready evidence, then report.",
        "complete": "Codex only: finish an independently approved goal under the pending request's recorded delegation.",
    }[name])
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--id", required=True)
    parser.add_argument("--wait", type=int, default=0, choices=range(0, 61), metavar="0..60")
    if name != "complete":
        parser.add_argument("--revision", help="Revision the receipt must cover; defaults to HEAD")
    args = parser.parse_args(arguments)
    repo = args.repo.resolve()
    try:
        if name == "complete":
            if harness != "codex":
                raise ValueError("Delegated goal completion is Codex-only")
            from codex_closeout import complete_pending
            result = complete_pending(repo, env, args.id, args.wait)
        else:
            head = args.revision or git(repo, "rev-parse", "HEAD")
            result = (observe if name == "observe" else reconcile)(repo, env, args.id, head, args.wait)
        print(json.dumps(dict(result, operation=name)))
        return 0 if result["status"] == "receipt" else 3
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        print(f"Verk {name}: {error}", file=sys.stderr)
        return 2


def main():
    arguments = sys.argv[1:]
    identity = argparse.ArgumentParser(add_help=False)
    identity.add_argument("--harness", choices=("codex", "claude-code"), default="codex")
    selected, arguments = identity.parse_known_args(arguments)
    env = dict(os.environ, VERK_CLOSEOUT_HARNESS=selected.harness)
    if arguments == ["hook-stop"]:
        try:
            handler = hook
            if selected.harness == "codex":
                from codex_closeout import hook as handler
            result = handler(json.load(sys.stdin), env)
        except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
            result = {"systemMessage": f"Verk closeout needs attention: {error}"}
        print(json.dumps(result))
        return 0
    if arguments[:1] and arguments[0] in OPERATIONS:
        return operation(arguments[0], arguments[1:], selected.harness, env)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--id", required=True)
    parser.add_argument("--proof")
    parser.add_argument("--delegate-approved-goals", action="store_true",
                        help="Codex only: operator-delegated completion from an independent exact-target approval")
    qualification = parser.add_mutually_exclusive_group(required=True)
    qualification.add_argument("--qualification", help="Committed diagnosis/checks/installed/operator/limits record")
    qualification.add_argument("--source-only", action="store_true", help="Acceptance requires no installed/live/operator qualification")
    parser.add_argument("--wait", type=int, default=30, choices=range(0, 61), metavar="0..60")
    args = parser.parse_args(arguments)
    try:
        if selected.harness == "codex":
            from codex_closeout import closeout as runner
            result = runner(args.repo.resolve(), env, args.id, args.proof, args.wait, args.qualification, args.source_only,
                            args.delegate_approved_goals)
        else:
            if args.delegate_approved_goals:
                raise ValueError("Delegated goal completion is Codex-only")
            result = closeout(args.repo.resolve(), env, args.id, args.proof, args.wait, args.qualification, args.source_only)
        print(json.dumps(result))
        return 0 if result["status"] == "receipt" else 3
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Verk closeout: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
