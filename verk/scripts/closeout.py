#!/usr/bin/env python3
"""Close explicitly ready Verk work; the Stop hook only follows a pending request."""
import argparse
from contextlib import contextmanager
import fcntl
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

sys.dont_write_bytecode = True  # Running from the source checkout must not dirty it.
from verk import invocation, session_identity


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


def state_path(env):
    """Derived from harness, session and store only, so a request can be found after its checkout is gone."""
    harness = env.get("VERK_CLOSEOUT_HARNESS", "codex")
    # Scratch stores keep their requests isolated too; this cache is never task truth.
    root = Path(env["VERK_HOME"]).expanduser() / "codex-closeout" if env.get("VERK_HOME") else Path.home() / ".cache/verk-closeout"
    # ponytail: one pending request per session; add a queue if concurrent hook observations are needed.
    prefix = "claude-code-" if harness == "claude-code" else ""
    return root / (prefix + session_identity(harness, env) + ".json")


@contextmanager
def request_lock(path):
    """Every read-validate-replace-delete of a session's request. Never hold it across a wait or a child process."""
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    descriptor = os.open(path.with_suffix(".lock"), os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        yield
    finally:
        os.close(descriptor)  # Closing releases the lock, as does any hard exit.


def read_request(path):
    try:
        request = json.loads(path.read_text())
    except FileNotFoundError:
        return None
    if not isinstance(request, dict):
        raise ValueError("Malformed closeout request")
    return request


def same_request(first, second):
    """Requests from before request IDs compare whole; a Stop claim never changes which request it is."""
    if first is None or second is None:
        return False
    plain = lambda r: {k: v for k, v in r.items() if k != "stop_claim"}
    return first.get("request_id") == second.get("request_id") and plain(first) == plain(second)


def number(value):
    return value if isinstance(value, (int, float)) and not isinstance(value, bool) else 0


def settled_before(path):
    """The start time of the latest closeout settled in this session. Survives deletion, so an older run can't revive a settled request."""
    try:
        return int(path.with_suffix(".settled").read_text())
    except (FileNotFoundError, ValueError):
        return 0


def mark_settled(path, request):
    began = number(request.get("began"))
    if began > settled_before(path):
        path.with_suffix(".settled").write_text(str(began))


def request_is_current(path, request):
    """For the last moment before an irreversible child call: is this still the session's request?"""
    with request_lock(path):
        try:
            return same_request(read_request(path), request)
        except ValueError:
            return False


def settle(path, request, result, consume=False):
    """Apply a finished observation only if its request is still current. Returns applied, replaced or gone."""
    with request_lock(path):
        try:
            current = read_request(path)
        except ValueError:
            return "replaced"
        if current is None:
            return "gone"
        if not same_request(current, request):
            return "replaced"
        save(path.with_suffix(".result.json"), result)
        if consume:
            mark_settled(path, current)
            path.unlink()
        elif "stop_claim" in current:
            save(path, {k: v for k, v in current.items() if k != "stop_claim"})
    return "applied"


def save(path, data):
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(f".{os.getpid()}.tmp")
    with temporary.open("w") as handle:
        os.chmod(temporary, 0o600)
        json.dump(data, handle)
    temporary.replace(path)


def verdict_row(env, decision):
    """The reviewer's latest manifest line for a decision. Diagnostic input only: Verk stays the authority."""
    rows = []
    for manifest in (Path(env.get("VERK_HOME", Path.home() / ".verk")) / "reviews").glob("*/verdicts.jsonl"):
        try:
            lines = [] if manifest.is_symlink() else manifest.read_text().splitlines()
        except (OSError, ValueError):  # Diagnostic only: an unreadable manifest must never fail closeout.
            continue
        for line in lines:
            try:
                row = json.loads(line)
            except ValueError:
                continue  # A reviewer may still be appending its last line.
            if isinstance(row, dict) and row.get("decision") == decision:
                rows.append(row)
    return max(rows, key=lambda r: number(r.get("at")), default=None)


NEXT_ACTION = {
    "receipt": "None: a receipt covers this revision.",
    "disagreement_gate_rejected": "The reviewer approved but the automated gate rejected. Read both, then repair or ask the operator; do not wait.",
    "disagreement_reviewer_rejected": "The reviewer rejected though the automated gate approved. Read the report and repair the work.",
    "process_failure": ("The reviewer process failed before judging, so nothing was assessed. It may retry briefly; after that the review stays open "
                        "until another review opens or `verk-reviewer` runs. Read the report or ask the operator; do not keep waiting. This is not a rejection."),
    "unavailable": "The reviewer could not assess this. It stays open; retry explicitly or ask the operator. This is not a rejection.",
    "stale_bindings": "Terms or policy changed after this evidence. Run closeout again under the current terms.",
    "review_rejected": "The review rejected the work. Read the report, repair, and request closeout again.",
    "check_rejected": "Verk rejected a check run. Fix the cause it names and run the check again.",
    "approved_awaiting_answer": "The reviewer approved; the review waits for whoever may answer it.",
    "answered_no_receipt": "The review was answered approved, but no receipt covers this revision. Inspect Verk view, then close out at the current HEAD.",
    "stale_target": "This review judged another revision. Run closeout again at the current HEAD.",
    "review_withdrawn": "The review was withdrawn. Inspect Verk view, then request closeout again if the work is still wanted.",
    "review_pending": "Wait for the independent verdict.",
    "needs_action": "Inspect Verk view.",
}


def outcomes(env, view, head, receipt=None):
    """Review, gate, admission and receipt as separate facts, plus the one outcome they add up to. Reads only."""
    reviews = view.get("reviews") or []
    latest = reviews[-1] if reviews else None
    row = verdict_row(env, latest.get("decision")) if latest else None
    # What the reviewer concluded and what Verk's answer says are different facts: an operator can answer against the reviewer.
    if not row:
        review = "none" if not latest else "pending" if latest.get("lifecycle") == "open" else "not_recorded"
    elif row.get("exit") != 0 or row.get("proposed") == "retry":
        review = "process_failure"
    else:
        review = row["proposed"] if row.get("proposed") in ("approve", "reject") else "unavailable"
    lifecycle = (latest or {}).get("lifecycle")
    answer = ("none" if not latest else "open" if lifecycle == "open" else "withdrawn" if lifecycle == "withdrawn"
              else latest.get("verdict") or "none")
    decider = (row or {}).get("decider")
    gate = "not_run" if not decider else "unavailable" if decider.get("error") else decider.get("verdict", "unavailable")
    admission = []
    for check in (view.get("policy") or {}).get("checks", []):
        runs = check.get("evidence")
        state = ("unknown" if runs is None else "admitted" if admitted_at(check, head) else "none" if not runs
                 else "stale" if any(e.get("bindings_current") is False for e in runs)
                 and not any(e.get("bindings_current") and e.get("status") in ("rejected", "pending") for e in runs)
                 else "rejected" if any(e.get("status") == "rejected" for e in runs)
                 else "pending" if any(e.get("status") == "pending" for e in runs) else "other_revision")
        admission.append({"check": check.get("name"), "state": state})
    states = {a["state"] for a in admission}
    reviewed = (row or {}).get("revision")
    disagreement = ("disagreement_gate_rejected" if review == "approve" and gate == "reject"
                    else "disagreement_reviewer_rejected" if review == "reject" and gate == "approve" else None)
    other_target = bool(reviewed and reviewed != head)
    if receipt:
        outcome = "receipt"
    elif other_target and answer in ("open", "approved"):
        outcome = "stale_target"
    elif disagreement:
        outcome = disagreement
    elif answer == "rejected":
        outcome = "review_rejected"
    elif answer == "approved":
        outcome = "stale_bindings" if "stale" in states else "answered_no_receipt"
    elif answer == "withdrawn":
        outcome = "review_withdrawn"
    elif review in ("process_failure", "unavailable"):
        outcome = review
    elif "stale" in states:
        outcome = "stale_bindings"
    elif review == "reject":
        outcome = "review_rejected"
    elif "rejected" in states:
        outcome = "check_rejected"
    elif review == "approve":
        outcome = "approved_awaiting_answer"
    elif review == "pending":
        outcome = "review_pending"
    else:
        outcome = "needs_action"
    return {"outcome": outcome, "review": review, "answer": answer, "gate": gate, "admission": admission, "receipt": receipt,
            "disagreement": disagreement,
            "coverage": {"reviewed_revision": reviewed, "requested_revision": head, "covers_requested_revision": None if not reviewed else not other_target,
                         "report_chars": (row or {}).get("chars"), "gate_clauses": (decider or {}).get("clauses"),
                         "checks_admitted": sorted(a["check"] for a in admission if a["state"] == "admitted"),
                         "checks_not_admitted": sorted(a["check"] for a in admission if a["state"] != "admitted")},
            "next_action": NEXT_ACTION[outcome]}


def reported(result):
    """What a reader is told. Control flow keeps `review_pending` while a review is open, so its request survives; a reader must not wait on a verdict nothing is producing."""
    outcome = result.get("outcomes") or {}
    if result.get("status") == "review_pending" and outcome.get("outcome") in ("process_failure", "unavailable"):
        return dict(result, status="needs_action", reason=outcome["next_action"])
    return result


def observe(repo, env, contract, head, wait, call_timeout=10):
    """Pure read: Verk view and the reviewer's manifest only. No writes, producers, reconciliation or delegated completion."""
    deadline = time.monotonic() + wait
    while True:
        view = call(repo, env, "view", contract, "--json", timeout=call_timeout)
        if view["state"] == "satisfied":
            receipt = next((r for r in reversed(view["receipts"]) if r["revision"] == head), None)
            if receipt:
                return {"status": "receipt", "contract": contract, "receipt": receipt["id"], "revision": head,
                        "outcomes": outcomes(env, view, head, receipt["id"])}
            return {"status": "needs_action", "contract": contract, "reason": "Receipt does not cover current HEAD",
                    "outcomes": outcomes(env, view, head)}
        reviews = view.get("reviews", [])
        pending = [r["decision"] for r in reviews if r["lifecycle"] == "open"]
        if not pending and any(r["verdict"] == "rejected" and r["lifecycle"] == "answered" for r in reviews):
            return {"status": "needs_action", "contract": contract, "reason": "Independent review rejected the work; inspect the review report",
                    "outcomes": outcomes(env, view, head)}
        if not pending:
            return {"status": "needs_action", "contract": contract, "reason": "No receipt or open review; inspect Verk view", "state": view["state"],
                    "outcomes": outcomes(env, view, head)}
        if time.monotonic() >= deadline:
            return {"status": "review_pending", "contract": contract, "reviews": pending, "outcomes": outcomes(env, view, head)}
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


def check_named(view, name, head):
    check = next((c for c in view["policy"]["checks"] if c["name"] == name), None)
    if check is None:
        raise ValueError(f"Check {name} is no longer in the policy; nothing was claimed for it at {head}")
    if "evidence" not in check:  # Fail closed: without this list a zero exit can't be told from admission.
        raise ValueError("The installed Verk shows no per-check evidence; update Verk before closeout")
    return check


def review_covers(view, decision, head):
    """An open review of exactly this target: same contract, revision or artifact revision, acceptance, subjects and policy."""
    target, bound = decision.get("target") or {}, decision.get("bindings") or {}
    contract = view["contract"]
    return (decision.get("lifecycle") == "open" and contract["id"] in decision.get("contracts", [decision.get("contract")])
            and (target.get("revision") or (target.get("artifact") or {}).get("revision")) == head
            and bound.get("acceptanceVersion") == contract.get("acceptance_version")
            and bound.get("subjectsVersion") == contract.get("subjects_version")
            and bound.get("policyVersion") == view["policy"].get("kind_version"))


def closeout(repo, env, contract, proof, wait, qualification=None, source_only=False, delegate_approved_goals=False):
    repo = repo.resolve()
    path = state_path(env)
    began = time.time_ns()  # Overlapping closeouts settle by when they began, not by which finished last.
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
            for name in [check["name"] for check in checks]:
                # Decide from a fresh view each time: an earlier check can run for minutes, and terms can move meanwhile.
                seen = current(repo, env, contract, attempt)
                if seen["state"] == "satisfied":
                    admitted = True  # a receipt was admitted meanwhile; observe it instead of running more checks
                    break
                if admitted_at(check_named(seen, name, head), head):
                    continue  # Verk already admitted this check for this revision under the current bindings
                # Producer deadline ends its check process group before this outer timeout.
                until = str(int((time.time() + 590) * 1000))
                call(repo, env, "check", name, "--id", contract, "--until", until, timeout=600, structured=False)
                ran = check_named(current(repo, env, contract, attempt), name, head)
                if not admitted_at(ran, head):
                    why = [e.get("reason") or e.get("status") for e in ran["evidence"] if e.get("revision") == head]
                    raise ValueError(f"Check {name} exited 0 but Verk did not admit it at {head}: {', '.join(why) or 'no evidence recorded'}")
        if git(repo, "rev-parse", "HEAD") != head or git(repo, "status", "--porcelain"):
            raise ValueError("Ready work changed during closeout; inspect evidence before requesting it again")
        if not current_review and checks and not admitted:
            names = ", ".join(check["name"] for check in checks)
            # What this note claims must still hold after the last check, for every check.
            seen = current(repo, env, contract, attempt)
            if seen["state"] != "satisfied":
                stale = [check["name"] for check in checks if not admitted_at(check_named(seen, check["name"], head), head)]
                if stale:
                    raise ValueError(f"Verk no longer shows {', '.join(stale)} admitted at {head}; run closeout again under the current terms")
            call(repo, env, "checkpoint", attempt, "--keep", "--next",
                 f"Independent review. {declaration}. Approved checks passed at {head}: {names}", "--json")
        call(repo, env, "reconcile", "--id", contract, "--json")
    result = observe(repo, env, contract, head, wait)
    # Observed outside the lock, applied inside it, and only if no closeout that began later has already settled.
    common_dir = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
    target = {}
    if result["status"] == "review_pending" and result.get("reviews"):
        target = call(repo, env, "view", result["reviews"][-1], "--json").get("target") or {}
    with request_lock(path):
        try:
            previous = read_request(path)
        except ValueError:
            previous = None
        if max(number((previous or {}).get("began")), settled_before(path)) > began:
            return dict(result, superseded=True)
        if result["status"] == "review_pending":
            described = view["contract"]
            request_id = uuid.uuid4().hex
            save(path, {"request_id": request_id, "began": began, "store": env.get("VERK_HOME") or str(Path.home() / ".verk"),
                        "harness": env.get("VERK_CLOSEOUT_HARNESS", "codex"), "session": path.stem.removeprefix("claude-code-"),
                        "repo": str(repo), "contract": contract, "project": described.get("project"), "head": head,
                        "artifact": target.get("artifact"), "common_dir": common_dir,
                        "bindings": {"acceptanceVersion": described.get("acceptance_version"),
                                     "subjectsVersion": described.get("subjects_version"),
                                     "policyVersion": (view.get("policy") or {}).get("kind_version")},
                        "delegate_approved_goals": delegate_approved_goals,
                        "qualification": qualification, "source_only": source_only})
            result = dict(result, request_id=request_id)
        elif previous and previous.get("contract") == contract:  # Contract IDs are store-wide, so a moved checkout still matches.
            mark_settled(path, dict(previous, began=began))
            path.unlink()
        save(path.with_suffix(".result.json"), result)
    return result


CLAIM_SECONDS = 60  # Longer than one Stop's bounded calls.


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
    path = state_path(scoped)
    with request_lock(path):
        try:
            request = read_request(path)
        except ValueError as error:
            path.unlink()
            result = {"status": "needs_action", "contract": None, "reason": str(error)}
            save(path.with_suffix(".result.json"), result)
            return {"systemMessage": "Verk closeout: " + json.dumps(result)}
        if request is None:
            return {}
        # A duplicate Stop while one is working replays nothing. A claim left by a hard exit expires, and the request survives it.
        if time.time() - number(request.get("stop_claim")) < CLAIM_SECONDS:
            return {}
        request = dict(request, stop_claim=time.time())
        save(path, request)
    try:
        repo, contract, head, common_dir = Path(request["repo"]).resolve(), request["contract"], request["head"], request["common_dir"]
    except KeyError as error:
        result = {"status": "needs_action", "contract": request.get("contract"), "reason": f"Malformed closeout request: {error}"}
        settle(path, request, result, consume=True)
        return {"systemMessage": "Verk closeout: " + json.dumps(result)}
    consume = True
    try:
        if git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir") != common_dir:
            # The path now holds another repository, or the checkout moved: a location change isn't a verdict on the work.
            raise ValueError("The recorded checkout no longer holds this repository; the request stays pending")
        if git(repo, "rev-parse", "HEAD") != head or git(repo, "status", "--porcelain"):
            result = {"status": "needs_action", "contract": contract, "reason": "Ready work changed; request closeout again after checking it"}
        else:
            call(repo, scoped, "reconcile", "--id", contract, "--json", timeout=5)
            result = observe(repo, scoped, contract, head, 0, call_timeout=5)
    except (ValueError, KeyError, OSError, subprocess.SubprocessError) as error:
        # Claude's Stop is nonblocking: report it, keep the request, and try once more on the next Stop.
        consume = False
        result = {"status": "needs_action", "contract": contract, "retained": True, "reason": str(error)}
    settled = settle(path, request, result, consume)
    if settled == "gone":
        return {}  # Another Stop or foreground closeout already settled it.
    if settled == "replaced":
        return {"systemMessage": "Verk closeout: a newer request replaced the one this Stop checked; it stays pending."}
    return {"systemMessage": "Verk closeout: " + json.dumps(reported(result))}


OPERATIONS = ("observe", "reconcile", "complete", "recover")


def operation(name, arguments, harness, env):
    parser = argparse.ArgumentParser(prog=f"closeout.py {name}", description={
        "observe": "Pure read of current state: writes nothing and starts nothing.",
        "reconcile": "Explicitly ask Verk to act on ready evidence, then report.",
        "complete": "Codex only: finish an independently approved goal under the pending request's recorded delegation.",
        "recover": "Codex only: with the recorded checkout gone, read Verk from --repo, any surviving directory, for the receipt of the pending request. Starts nothing.",
    }[name])
    # Recovery's directory is always the caller's explicit choice, and a deleted cwd must not stop it.
    parser.add_argument("--repo", type=Path, required=name == "recover")
    parser.add_argument("--id", required=True)
    parser.add_argument("--wait", type=int, default=0, choices=range(0, 61), metavar="0..60")
    if name not in ("complete", "recover"):
        parser.add_argument("--revision", help="Revision the receipt must cover; defaults to HEAD")
    args = parser.parse_args(arguments)
    try:
        repo = (args.repo or Path.cwd()).resolve()
        if name == "complete":
            if harness != "codex":
                raise ValueError("Delegated goal completion is Codex-only")
            from codex_closeout import complete_pending
            result = complete_pending(repo, env, args.id, args.wait)
        elif name == "recover":
            if harness != "codex":
                raise ValueError("Missing-checkout recovery is Codex-only")
            from codex_closeout import recover_pending
            result = recover_pending(repo, env, args.id)
        else:
            head = args.revision or git(repo, "rev-parse", "HEAD")
            result = (observe if name == "observe" else reconcile)(repo, env, args.id, head, args.wait)
        print(json.dumps(dict(reported(result), operation=name)))
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
    parser.add_argument("--repo", type=Path)
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
        repo = (args.repo or Path.cwd()).resolve()
        if selected.harness == "codex":
            from codex_closeout import closeout as runner
            result = runner(repo, env, args.id, args.proof, args.wait, args.qualification, args.source_only,
                            args.delegate_approved_goals)
        else:
            if args.delegate_approved_goals:
                raise ValueError("Delegated goal completion is Codex-only")
            result = closeout(repo, env, args.id, args.proof, args.wait, args.qualification, args.source_only)
        print(json.dumps(reported(result)))
        return 0 if result["status"] == "receipt" else 3
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Verk closeout: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
