#!/usr/bin/env python3
"""List Rúnir facts about one function and flag those written before its last change.

Reads only: two Rúnir searches, one git log. Stores nothing.
Env: RUNIR_API_KEY, RUNIR_USER_ID, optional RUNIR_BASE (default http://127.0.0.1:7700).
"""
import argparse, json, os, re, subprocess, sys, urllib.request
from datetime import datetime, timezone
from pathlib import Path

p = argparse.ArgumentParser()
p.add_argument("--symbol", required=True)
p.add_argument("--file", required=True, help="path relative to the repo root")
p.add_argument("--lines", help="START,END (1-based) from a code index; default finds the function by name")
p.add_argument("--repo", default=".", help="repo root (default: current folder)")
p.add_argument("--limit", type=int, default=50, help="hits per search; Rúnir caps this at 50")
p.add_argument("--file-facts", action="store_true", help="also list facts that name only the file")
p.add_argument("--full", nargs="*", metavar="ID",
               help="print whole fact text: only the facts with these ids (prefixes work), or every listed fact when no id is given")
a = p.parse_args()

def git(*args):
    return subprocess.run(["git", "-C", a.repo, *args], capture_output=True, text=True)

# History of the function itself, newest first. Falls back to the whole file.
what = "function"
scope = "function, by line range" if a.lines else "function, found by name"
log = git("log", "-s", "--format=%cI%x09%h%x09%s", "-L", f"{a.lines}:{a.file}" if a.lines else f":{a.symbol}:{a.file}")
if log.returncode != 0 or not log.stdout.strip():
    what = "whole file"
    scope = "whole file (line range not valid)" if a.lines else "whole file (function not found; pass --lines)"
    log = git("log", "--format=%cI%x09%h%x09%s", "--", a.file)
commits = [l.split("\t", 2) for l in log.stdout.splitlines() if l.count("\t") == 2]
if not commits:
    sys.exit(f"no git history for {a.file} in {a.repo}")
commits = [(datetime.fromisoformat(d), h, s) for d, h, s in commits]
last = commits[0]

key, user = os.environ.get("RUNIR_API_KEY"), os.environ.get("RUNIR_USER_ID")
if not key or not user:
    sys.exit("RUNIR_API_KEY and RUNIR_USER_ID must be set")
base = os.environ.get("RUNIR_BASE", "http://127.0.0.1:7700").rstrip("/")

def search(query):
    body = json.dumps({"userId": user, "query": query, "limit": a.limit}).encode()
    req = urllib.request.Request(f"{base}/memory/search", data=body, method="POST",
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        return json.load(urllib.request.urlopen(req, timeout=20)).get("results", [])
    except Exception as e:
        sys.exit(f"Rúnir search failed: {e}")

# Search the symbol and the file name separately, merge by id, then keep only
# facts that actually name one of them.
fname = Path(a.file).name
batches = [search(n) for n in (a.symbol, fname)]
hits = {h["id"]: h for b in batches for h in b}.values()
by_symbol = [h for h in hits if a.symbol in str(h.get("memory", ""))]
by_file = [h for h in hits if a.symbol not in str(h.get("memory", "")) and fname in str(h.get("memory", ""))]
full = any(len(b) >= a.limit for b in batches)

def judge(h):
    """(flag, block) for one fact. created_at, not updated_at: a later touch must not make an old fact look fresh."""
    text = " ".join(str(h["memory"]).split())
    when = datetime.fromisoformat(h["created_at"].replace("Z", "+00:00"))
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    since = sum(1 for d, _, _ in commits if d > when)
    flag = "RE-CHECK" if since else "OK"
    note = f"{since} commit(s) to the {what} since" if since else "written after the last change"
    if when < commits[-1][0]:
        note += f"; note: older than this checkout's history of the {what}, so the count includes its first commit"
    absent = [m for m in re.findall(r"[\w./-]+/[\w.-]+\.\w{1,4}\b", text) if not (Path(a.repo) / m).exists()]
    if absent:
        note += f"; note: names {absent[0]}, absent from this checkout"
    body = text if a.full is not None else text[:220]
    # Many facts name the function only in passing, past the preview. Show where.
    needle = a.symbol if a.symbol in text else fname
    at = text.find(needle)
    if a.full is None and at + len(needle) > 220:
        body += f"\n          mention: …{text[max(0, at - 90):at + len(needle) + 90]}…"
    return flag, f"{flag:8}  {when.date()}  {note}\n          {h['id']}\n          {body}\n"

def show(facts):
    for h in sorted(facts, key=lambda h: h["created_at"]):
        print(judge(h)[1])

print(f"{a.symbol}  {a.file}")
print(f"last changed {last[0].date()} ({last[1]}) {last[2][:70]}")
print(f"scope: {scope}")

if a.full:  # ids given: print just those facts, whole
    listed = [*by_symbol, *by_file]
    missing = [i for i in a.full if not any(h["id"].startswith(i) for h in listed)]
    print()
    show([h for h in listed if any(h["id"].startswith(i) for i in a.full)])
    for i in missing:
        print(f"no listed fact has an id starting with {i}")
    sys.exit(1 if missing else 0)

print(f"{len(by_symbol)} fact(s) name the function"
      + ("; search hit its limit, so this list may be partial" if full else "") + "\n")
show(by_symbol)
flags = [judge(h)[0] for h in by_file]
print(f"{len(by_file)} more name only {fname}: {flags.count('RE-CHECK')} re-check, {flags.count('OK')} ok"
      + ("" if a.file_facts or not by_file else "  (--file-facts lists them)") + "\n")
if a.file_facts:
    show(by_file)
