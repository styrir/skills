"""Codex-only operator delegation for already independently approved goals.

No reviewer or policy is created here. The operator must explicitly delegate
this completion step; the author wrapper remains author-only.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

from verk import invocation


def approved_report(environment, decision, contract, head):
    root = Path(environment.get("VERK_HOME", Path.home() / ".verk")) / "reviews"
    candidates = []
    for manifest in root.glob("*/verdicts.jsonl"):
        if manifest.is_symlink():
            continue
        for line in manifest.read_text().splitlines():
            try:
                row = json.loads(line)
            except ValueError:
                continue  # A reviewer may still be appending its last line.
            if isinstance(row, dict) and isinstance(row.get("at"), int) and row.get("decision") == decision["id"]:
                candidates.append((row, manifest.parent / (decision["id"] + ".md")))
    if not candidates:
        return None
    row, path = max(candidates, key=lambda item: item[0].get("at", 0))
    if row.get("contract") != contract or row.get("revision") != head:
        raise ValueError("Independent goal approval is for a different target")
    if row.get("exit") == 0 and row.get("proposed") == "reject":
        raise ValueError("Independent goal review rejected the work")
    if (row.get("contract") != contract or row.get("revision") != head
            or row.get("exit") != 0 or row.get("proposed") != "approve"
            or row.get("answered") is not False or row.get("at", 0) < decision["created_at"]
            or row.get("decider", {}).get("verdict", "approve") != "approve"):
        return None
    # Only the installed independent reviewer's output, never an author-supplied
    # report argument. Symlinks and shared-writable files are not trusted input.
    for item in (root.parent, root, path.parent, path, path.parent / "verdicts.jsonl"):
        if item.is_symlink() or item.stat().st_uid != os.getuid() or item.stat().st_mode & 0o022:
            raise ValueError("Independent review output is not owner-controlled")
    body = path.read_text()
    if (len(body) != row.get("chars")
            or not re.search(r"(?m)^Reviewed:\s*(?:" + re.escape(head) + "|" + re.escape(head[:8]) + r")\s*$", body)
            or not re.search(r"(?m)^VERDICT:\s*approve[^\n]*\s*\Z", body)):
        raise ValueError("Independent approval report does not match its manifest/target")
    return path, hashlib.sha256(path.read_bytes()).hexdigest()


def complete_goal(repo, environment, view, decision, head, call, git):
    if environment.get("VERK_CLOSEOUT_HARNESS", "codex") != "codex":
        raise ValueError("Delegated goal completion is Codex-only")
    if view["contract"]["kind"] != "goal":
        return False
    contract = view["contract"]["id"]
    if call(repo, environment, "brief", "--json").get("project") != view["contract"]["project"]:
        raise ValueError("Goal belongs to another repository project")
    target = decision.get("target", {})
    revision = target.get("revision") or target.get("artifact", {}).get("revision")
    if (decision.get("kind") != "review" or decision.get("lifecycle") != "open"
            or decision.get("contracts") != [contract] or revision != head
            or decision["bindings"].get("acceptanceVersion") != view["contract"]["acceptance_version"]
            or decision["bindings"].get("subjectsVersion") != view["contract"]["subjects_version"]):
        raise ValueError("Delegated completion requires the current goal review and acceptance")
    if any(child["state"] != "satisfied" for child in view.get("children", [])):
        raise ValueError("Goal children are not all satisfied")
    if any(item["state"] != "satisfied" for item in view.get("prerequisites", [])):
        raise ValueError("Goal prerequisites are not all satisfied")
    report = approved_report(environment, decision, contract, head)
    if not report:
        return False
    path, digest = report
    bound_children = decision["bindings"].get("children", [])
    if {c["id"] for c in bound_children} != {c["id"] for c in view.get("children", [])}:
        raise ValueError("Goal children changed after review")
    for child in bound_children:
        observed = call(repo, environment, "view", child["id"], "--json")
        if (observed["state"] != "satisfied" or child.get("source") != "receipt"
                or child.get("receipt") not in {r["id"] for r in observed["receipts"]}):
            raise ValueError("Goal review does not cover its current child receipts")
    # Re-read after the independent report lookup; the CLI retains responsibility
    # for withdrawn decisions, bindings, receipt admission and reconciliation.
    current = call(repo, environment, "view", decision["id"], "--json")
    if current != decision or git(repo, "rev-parse", "HEAD") != head or git(repo, "status", "--porcelain"):
        raise ValueError("Goal review or ready work changed before delegated completion")
    command, cwd, scoped = invocation(["--repo", str(repo), "view", decision["id"], "--json"], environment)
    import pwd  # The desktop adapter currently supports POSIX operator identity.
    operator = "operator:" + pwd.getpwuid(os.getuid()).pw_name
    if decision.get("responsible") != operator:
        raise ValueError("Review is assigned to another operator")
    author = scoped["VERK_ACTOR"]
    scoped["VERK_ACTOR"] = operator
    reason = f"Codex operator-delegated completion by {author}; independent approval {decision['id']}; report SHA256 {digest}"
    result = subprocess.run([command[0], "answer", decision["id"], reason, "--report", str(path), "--json"],
                            cwd=cwd, env=scoped, capture_output=True, text=True, timeout=10)
    if result.returncode:
        raise ValueError((result.stderr or result.stdout).strip()[-2000:])
    if not json.loads(result.stdout).get("ok"):
        raise ValueError("Verk did not admit the delegated review answer")
    call(repo, environment, "reconcile", "--id", contract, "--json")
    return True
