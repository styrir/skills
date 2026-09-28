#!/usr/bin/env python3
"""jev — stdlib client and CLI for Jev, TypeSafe's System One decision model.

One answer shape across three explicit routes (no silent fallback between them):

  requesty    POST https://router.requesty.ai/v1/chat/completions   REQUESTY_API_KEY   (default)
  openrouter  POST https://openrouter.ai/api/alpha/decisions         OPENROUTER_API_KEY
  typesafe    POST https://api.typesafe.ai/v1/systemone              TYPESAFE_API_KEY
  mock        deterministic offline stand-in; tests only, must be selected explicitly

Select with --route or JEV_ROUTE. Keys come from the environment only; inject them with
`infisical run ... -- jev.py ...` and never print them.

Subcommands:
  ask           one state, one question block
  files         judge many files in parallel; the caller gets answers, never file contents
  calibrate     score a labeled JSONL set; accuracy and threshold sweeps
  route-status  key presence, pinned model, and (unless --offline) a one-question ping

Library use:
  from jev import ask, noul, choice, score
  result = ask({"command": cmd}, {"risky": noul("Is `command` risky?")})
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import fnmatch
import glob as globlib
import hashlib
import json
import os
import random
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROUTES = {
    "requesty": {
        "url": "https://router.requesty.ai/v1/chat/completions",
        "key": "REQUESTY_API_KEY",
        "model": "typesafe/jev-1.13.0",
    },
    "openrouter": {
        "url": "https://openrouter.ai/api/alpha/decisions",
        "key": "OPENROUTER_API_KEY",
        "model": "typesafe/jev-1.13",
    },
    "typesafe": {
        "url": "https://api.typesafe.ai/v1/systemone",
        "key": "TYPESAFE_API_KEY",
        "model": "jev-1.13",
    },
    "mock": {"url": None, "key": None, "model": "mock-jev"},
}
DEFAULT_ROUTE = "requesty"
INFISICAL_HINT = (
    "infisical run --projectId 2588c473-4c4c-4b5a-b0f5-e261184b6b53 --env dev -- <command>"
)
RETRY_STATUSES = {429, 502, 503, 529}
MAX_CHOICE_OPTIONS = 255
SCORE_LEVELS = (2, 10)
# Jev 1.13: 32k tokens for state plus the longest question. Chars/4 is a coarse guard, not a tokenizer.
MAX_STATE_CHARS = 110_000
INPUT_USD_PER_MTOK = 0.042


class JevError(Exception):
    """Transport, auth, or contract failure. Callers decide their own fail-open/closed policy."""


# ---------------------------------------------------------------- local egress controls
# Everything in `state` leaves the machine. Redact credential-shaped text locally first; never ask a hosted
# model whether a secret may be sent to a hosted model.

import re as _re

_REDACTIONS = [
    (_re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"), "[REDACTED:private-key]"),
    (_re.compile(r"(?i)\b(bearer|token|basic)\s+[A-Za-z0-9._~+/=-]{16,}"), r"\1 [REDACTED]"),
    (_re.compile(r"\b(sk|rk|pk)-[A-Za-z0-9_-]{16,}"), "[REDACTED:key]"),
    (_re.compile(r"\b(gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{20,}|xox[abprs]-[A-Za-z0-9-]{10,}|AKIA[0-9A-Z]{16}|AIza[0-9A-Za-z_-]{30,})\b"), "[REDACTED:key]"),
    (_re.compile(r"(?i)\b([A-Z0-9_]*(API_?KEY|SECRET|TOKEN|PASSWORD|PASSWD|PRIVATE_KEY|CLIENT_SECRET)[A-Z0-9_]*)\s*[:=]\s*(\"[^\"\n]{6,}\"|'[^'\n]{6,}'|[^\s'\"]{6,})"), r"\1=[REDACTED]"),
    (_re.compile(r"(https?://)[^/\s:@]+:[^/\s@]+@"), r"\1[REDACTED]@"),
    (_re.compile(r"([?&](?:sig|signature|token|key|X-Amz-Signature|X-Amz-Credential)=)[^&\s]{8,}"), r"\1[REDACTED]"),
    (_re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"), "[REDACTED:jwt]"),
]


def redact(text: str) -> tuple[str, int]:
    """Return (text with credential-shaped substrings replaced, number of replacements)."""
    n = 0
    for pat, rep in _REDACTIONS:
        text, k = pat.subn(rep, text)
        n += k
    return text, n


def redact_state(state: Any) -> tuple[Any, int]:
    if isinstance(state, str):
        return redact(state)
    if isinstance(state, list):
        out, total = [], 0
        for v in state:
            r, k = redact_state(v); out.append(r); total += k
        return out, total
    if isinstance(state, dict):
        out, total = {}, 0
        for key, v in state.items():
            r, k = redact_state(v); out[key] = r; total += k
        return out, total
    return state, 0


# ---------------------------------------------------------------- question builders

def noul(instructions: str, true: str | None = None, false: str | None = None) -> dict:
    q: dict[str, Any] = {"type": "noul", "instructions": instructions}
    crit = {k: v for k, v in (("true", true), ("false", false)) if v}
    if crit:
        q["criteria"] = crit
    return q


def choice(instructions: str, options: dict[str, str | None], other: bool = True) -> dict:
    opts = dict(options)
    if other and not any(k in opts for k in ("other", "none_of_the_above")):
        opts["other"] = "None of the listed options fits"
    return {"type": "choice", "instructions": instructions, "criteria": opts}


def score(instructions: str, levels: list[str]) -> dict:
    return {"type": "score", "instructions": instructions, "criteria": list(levels)}


# ---------------------------------------------------------------- validation

def validate_questions(questions: Any) -> None:
    if not isinstance(questions, dict) or not questions:
        raise JevError("questions must be a non-empty object keyed by question id")
    for qid, q in questions.items():
        if not isinstance(q, dict) or q.get("type") not in ("noul", "choice", "score"):
            raise JevError(f"question {qid!r}: type must be noul, choice, or score")
        ins = q.get("instructions")
        if not (isinstance(ins, dict) or (isinstance(ins, str) and ins.strip())):
            raise JevError(f"question {qid!r}: instructions must be a non-blank string or object")
        crit = q.get("criteria")
        if q["type"] == "noul" and crit is not None:
            if not isinstance(crit, dict) or set(crit) - {"true", "false"}:
                raise JevError(f"noul {qid!r}: criteria may only have true/false")
        if q["type"] == "choice":
            if not isinstance(crit, dict) or not crit:
                raise JevError(f"choice {qid!r}: criteria must be a non-empty object")
            if len(crit) > MAX_CHOICE_OPTIONS:
                raise JevError(f"choice {qid!r}: {len(crit)} options exceeds {MAX_CHOICE_OPTIONS}")
        if q["type"] == "score":
            if not isinstance(crit, list) or not SCORE_LEVELS[0] <= len(crit) <= SCORE_LEVELS[1]:
                raise JevError(f"score {qid!r}: criteria must be 2-10 level descriptions")


def validate_answers(answers: Any, questions: dict) -> None:
    if not isinstance(answers, dict):
        raise JevError("contract: answers is not an object")
    for qid, q in questions.items():
        a = answers.get(qid)
        if not isinstance(a, dict) or a.get("type") != q["type"]:
            raise JevError(f"contract: missing or mismatched answer for {qid!r}")
        if q["type"] == "noul":
            if not _unit(a.get("noul")):
                raise JevError(f"contract: invalid noul for {qid!r}")
            continue
        probs = a.get("probabilities")
        keys = list(q["criteria"]) if q["type"] == "choice" else [str(i) for i in range(len(q["criteria"]))]
        if not isinstance(probs, dict) or set(probs) != set(keys) or not all(_unit(probs[k]) for k in keys):
            raise JevError(f"contract: distribution keys do not match criteria for {qid!r}")
        if abs(sum(probs[k] for k in keys) - 1) > 0.025:
            raise JevError(f"contract: distribution for {qid!r} does not sum to 1")
        if not _unit(a.get("confidence")):
            raise JevError(f"contract: invalid confidence for {qid!r}")
        if q["type"] == "choice" and a.get("choice") not in keys:
            raise JevError(f"contract: undeclared choice returned for {qid!r}")
        if q["type"] == "score":
            s = a.get("score")
            if not isinstance(s, (int, float)) or not 0 <= s <= len(keys) - 1:
                raise JevError(f"contract: score out of range for {qid!r}")


def _unit(x: Any) -> bool:
    return isinstance(x, (int, float)) and not isinstance(x, bool) and 0 <= x <= 1


# ---------------------------------------------------------------- transport

def resolve_route(route: str | None = None) -> str:
    r = (route or os.environ.get("JEV_ROUTE") or DEFAULT_ROUTE).strip()
    if r not in ROUTES:
        raise JevError(f"unknown route {r!r}; use one of {', '.join(ROUTES)}")
    return r


def _key(route: str) -> str:
    """Environment first; then the macOS Keychain item `jev.<route>` (for hooks, which run without
    `infisical run`). Same key either way; this is key sourcing, not route fallback. Never printed."""
    cfg = ROUTES[route]
    key = (os.environ.get(cfg["key"]) or "").strip()
    if key or sys.platform != "darwin" or os.environ.get("JEV_NO_KEYCHAIN") == "1":
        return key
    import subprocess
    try:
        out = subprocess.run(["security", "find-generic-password", "-s", f"jev.{route}", "-w"],
                             capture_output=True, text=True, timeout=3)
        return out.stdout.strip() if out.returncode == 0 else ""
    except (OSError, subprocess.TimeoutExpired):
        return ""


def _body(route: str, model: str, state: Any, questions: dict) -> dict:
    if route == "requesty":
        content = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False)
        return {
            "model": model,
            "messages": [{"role": "user", "content": content}],
            "response_format": {"type": "questions", "questions": questions},
        }
    return {"model": model, "state": state, "questions": questions}


def _normalize(route: str, raw: dict) -> tuple[dict, dict, str]:
    """Return (answers, usage{input_tokens, output_tokens, cost}, resolved_model)."""
    if route == "requesty":
        try:
            answers = json.loads(raw["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as e:
            raise JevError(f"contract: unreadable Requesty answer payload ({e.__class__.__name__})")
        u = raw.get("usage") or {}
        usage = {
            "input_tokens": u.get("prompt_tokens", 0),
            "output_tokens": u.get("completion_tokens", 0),
            "cost": u.get("cost"),
        }
        return answers, usage, raw.get("model", "")
    u = raw.get("usage") or {}
    usage = {
        "input_tokens": u.get("input_tokens", u.get("inputTokens", 0)),
        "output_tokens": u.get("output_tokens", u.get("outputTokens", 0)),
        "cost": u.get("cost"),
    }
    return raw.get("answers"), usage, raw.get("model", "")


def _mock_answers(state: Any, questions: dict) -> dict:
    """Deterministic shape-only stand-in: hash of (state, qid) drives the numbers. Not intelligence."""
    out = {}
    blob = json.dumps(state, sort_keys=True, ensure_ascii=False)
    for qid, q in questions.items():
        h = int(hashlib.sha256(f"{blob}|{qid}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        if q["type"] == "noul":
            out[qid] = {"type": "noul", "noul": round(h, 2)}
            continue
        keys = list(q["criteria"]) if q["type"] == "choice" else [str(i) for i in range(len(q["criteria"]))]
        pick = int(h * len(keys)) % len(keys)
        probs = {k: (0.85 if i == pick else round(0.15 / max(1, len(keys) - 1), 4)) for i, k in enumerate(keys)}
        if q["type"] == "choice":
            out[qid] = {"type": "choice", "choice": keys[pick], "probabilities": probs, "confidence": 0.8}
        else:
            out[qid] = {"type": "score", "score": float(pick), "probabilities": probs, "confidence": 0.8,
                        "legend": {str(i): lvl for i, lvl in enumerate(q["criteria"])}}
    return out


def ask(state: Any, questions: dict, *, route: str | None = None, model: str | None = None,
        timeout: float | None = None, ledger: str | None = None, receipt_dir: str | None = None,
        tag: str | None = None) -> dict:
    """One Jev call. Returns {answers, usage, meta}. Raises JevError on any failure."""
    validate_questions(questions)
    r = resolve_route(route)
    cfg = ROUTES[r]
    mdl = model or os.environ.get("JEV_MODEL") or cfg["model"]
    state, redacted = redact_state(state)
    state_text = state if isinstance(state, str) else json.dumps(state, ensure_ascii=False)
    if len(state_text) > MAX_STATE_CHARS:
        raise JevError(f"state is {len(state_text)} chars; over the ~32k-token budget. Filter in code first.")
    timeout = timeout if timeout is not None else float(os.environ.get("JEV_TIMEOUT", "20"))
    t0 = time.monotonic()
    attempts = 0

    if r == "mock":
        answers, usage, resolved = _mock_answers(state, questions), {"input_tokens": 0, "output_tokens": 0, "cost": 0.0}, "mock-jev"
        attempts = 1
    else:
        key = _key(r)
        if not key:
            raise JevError(f"route {r}: {cfg['key']} is not set and no Keychain item 'jev.{r}'. Inject it, e.g. {INFISICAL_HINT}")
        data = json.dumps(_body(r, mdl, state, questions)).encode()
        deadline = t0 + timeout
        raw = None
        for attempts in range(1, 4):
            req = urllib.request.Request(cfg["url"], data=data, method="POST", headers={
                "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise JevError(f"route {r}: timed out after {timeout}s")
            try:
                with urllib.request.urlopen(req, timeout=remaining) as resp:
                    raw = json.loads(resp.read())
                break
            except urllib.error.HTTPError as e:
                if e.code in RETRY_STATUSES and attempts < 3:
                    wait = min(4.0, 0.5 * 2 ** (attempts - 1) * (1 + random.random() * 0.2))
                    ra = e.headers.get("Retry-After") if e.headers else None
                    if ra and ra.strip().replace(".", "", 1).isdigit():
                        wait = min(8.0, max(wait, float(ra)))
                    time.sleep(min(wait, max(0.0, deadline - time.monotonic())))
                    continue
                hint = {401: f" Check {cfg['key']}.", 402: " Check account credits.", 404: f" Model {mdl!r} not found on {r}."}.get(e.code, "")
                raise JevError(f"route {r}: HTTP {e.code}.{hint}")
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                raise JevError(f"route {r}: network error ({e.__class__.__name__})")
            except json.JSONDecodeError:
                raise JevError(f"route {r}: response was not JSON")
        answers, usage, resolved = _normalize(r, raw)

    validate_answers(answers, questions)
    _check_pin(mdl, resolved)
    if usage.get("cost") is None:
        usage["cost_source"] = "estimated"
        usage["cost"] = usage.get("input_tokens", 0) * INPUT_USD_PER_MTOK / 1e6
    else:
        usage["cost_source"] = "reported" if r != "mock" else "mock"
    meta = {
        "route": r, "requested_model": mdl, "resolved_model": resolved,
        "elapsed_ms": int((time.monotonic() - t0) * 1000), "attempts": attempts,
        "state_sha256": hashlib.sha256(state_text.encode()).hexdigest(),
        "redactions": redacted,
    }
    if tag:
        meta["tag"] = tag
    result = {"answers": answers, "usage": usage, "meta": meta}
    _record(result, questions, ledger or os.environ.get("JEV_LEDGER"), receipt_dir)
    return result


def _check_pin(requested: str, resolved: str) -> None:
    """Thresholds are tuned to a version. A pinned request that resolves to another version is an error,
    not an observation. Aliases (`*latest*`) and the mock are exempt; JEV_ALLOW_MODEL_DRIFT=1 opts out."""
    if "latest" in requested or requested.startswith("mock") or os.environ.get("JEV_ALLOW_MODEL_DRIFT") == "1":
        return
    want = requested.split("/")[-1]          # typesafe/jev-1.13.0 -> jev-1.13.0 ; typesafe/jev-1.13 -> jev-1.13
    want = want[:-2] if want.count(".") >= 2 and want.endswith(".0") else want   # jev-1.13.0 -> jev-1.13
    got = resolved.split("/")[-1]
    if not got.startswith(want):
        raise JevError(f"model drift: requested {requested!r} but {resolved!r} answered; recalibrate or set JEV_ALLOW_MODEL_DRIFT=1")


def _record(result: dict, questions: dict, ledger: str | None, receipt_dir: str | None) -> None:
    """Ledger lines carry numbers and hashes only, never state. Receipts add the questions."""
    line = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S%z"), **result["meta"], "usage": result["usage"],
            "answers": result["answers"]}
    if ledger:
        p = Path(os.path.expanduser(ledger))
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a") as f:
            f.write(json.dumps(line) + "\n")
    if receipt_dir:
        d = Path(os.path.expanduser(receipt_dir))
        d.mkdir(parents=True, exist_ok=True)
        name = f"{int(time.time() * 1000)}-{result['meta']['state_sha256'][:12]}.json"
        (d / name).write_text(json.dumps({**line, "questions": questions}, indent=1))


# ---------------------------------------------------------------- files (levels 8-9)

SKIP_DIRS = {"node_modules", ".git", ".beads", ".venv", "venv", "__pycache__", "dist", "build",
             "coverage", ".next", ".pi", ".omc", "target", ".sessions"}
SKIP_EXT = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".tgz", ".woff",
            ".woff2", ".ttf", ".mp3", ".mp4", ".mov", ".lock", ".sqlite", ".db", ".bin", ".so", ".dylib")
# Never shipped to a hosted model, whatever the caller asks.
SECRET_GLOBS = (".env", ".env.*", "*.pem", "*.key", "id_rsa*", "id_ed25519*", "auth.json", "credentials*",
                "*.p12", "*.keychain*", ".netrc", ".npmrc", ".pypirc")
MAX_FILE_CHARS = 60_000


def expand(patterns: list[str], cwd: str, recursive: bool) -> list[str]:
    out: set[str] = set()
    for pat in patterns:
        p = pat.strip()
        if not p:
            continue
        full = p if os.path.isabs(p) else os.path.join(cwd, p)
        if any(c in p for c in "*?[]{}"):
            out.update(os.path.relpath(x, cwd) for x in globlib.glob(full, recursive=True))
        elif os.path.isdir(full):
            it = Path(full).rglob("*") if recursive else Path(full).glob("*")
            out.update(os.path.relpath(str(x), cwd) for x in it)
        else:
            out.add(os.path.relpath(full, cwd))
    return sorted(out)


def prune(paths: list[str], cwd: str, cap: int = MAX_CHOICE_OPTIONS) -> tuple[list[str], list[dict]]:
    keep, skipped = [], []
    root = os.path.realpath(cwd)
    for rel in paths:
        full = os.path.join(cwd, rel)
        name = os.path.basename(rel)
        real = os.path.realpath(full)
        if rel.startswith("..") or os.path.commonpath([root, real]) != root:
            skipped.append({"path": rel, "reason": "outside cwd (after resolving symlinks)"}); continue
        if any(fnmatch.fnmatch(os.path.basename(real), g) for g in SECRET_GLOBS):
            skipped.append({"path": rel, "reason": "symlink to a secret-like file, never sent"}); continue
        if any(part in SKIP_DIRS for part in Path(rel).parts):
            skipped.append({"path": rel, "reason": "skipped directory"}); continue
        if not os.path.isfile(full):
            if not os.path.exists(full):
                skipped.append({"path": rel, "reason": "not found"})
            continue
        if any(fnmatch.fnmatch(name, g) for g in SECRET_GLOBS):
            skipped.append({"path": rel, "reason": "secret-like file, never sent"}); continue
        if rel.lower().endswith(SKIP_EXT):
            skipped.append({"path": rel, "reason": "binary or lock file"}); continue
        size = os.path.getsize(full)
        if size == 0:
            skipped.append({"path": rel, "reason": "empty"}); continue
        if size > MAX_FILE_CHARS:
            skipped.append({"path": rel, "reason": f"too large ({size} bytes); judge a slice instead"}); continue
        if len(keep) >= cap:
            skipped.append({"path": rel, "reason": f"over the {cap}-file cap; narrow the pattern"}); continue
        keep.append(rel)
    return keep, skipped


def judge_files(paths: list[str], questions: dict, cwd: str, *, concurrency: int = 12,
                route: str | None = None, context: str | None = None, **kw) -> list[dict]:
    def one(rel: str) -> dict:
        try:
            text = Path(cwd, rel).read_text(errors="replace")
        except OSError as e:
            return {"path": rel, "error": f"read failed ({e.__class__.__name__})"}
        state = {"path": rel, "content": text}
        if context:
            state["context"] = context
        try:
            r = ask(state, questions, route=route, tag=f"files:{rel}", **kw)
            return {"path": rel, "answers": r["answers"], "cost": r["usage"]["cost"], "ms": r["meta"]["elapsed_ms"],
                    "model": r["meta"]["resolved_model"]}
        except JevError as e:
            return {"path": rel, "error": str(e)}
    with cf.ThreadPoolExecutor(max_workers=max(1, concurrency)) as ex:
        return list(ex.map(one, paths))


def pick_file(candidates: list[str], instruction: str, context: str | None = None, **kw) -> dict:
    """Level 9's second pass: one Choice keyed by real paths, so the pick is always a real file."""
    q = {"pick": choice(instruction, {p: None for p in candidates[:MAX_CHOICE_OPTIONS - 1]})}
    state = {"candidates": candidates}
    if context:
        state["context"] = context
    return ask(state, q, tag="files:pick", **kw)


# ---------------------------------------------------------------- CLI helpers

def _load(arg: str) -> Any:
    """Accept inline JSON, @file, or - for stdin."""
    if arg == "-":
        text = sys.stdin.read()
    elif arg.startswith("@"):
        text = Path(arg[1:]).read_text()
    else:
        text = arg
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text  # a plain-string state


def _brief(a: dict) -> str:
    if a["type"] == "noul":
        return f"{a['noul']:.2f}"
    if a["type"] == "choice":
        return f"{a['choice']} ({a['confidence']:.2f})"
    return f"{a['score']:.2f} ({a['confidence']:.2f})"


def cmd_ask(args) -> int:
    questions = _load(args.questions)
    if not isinstance(questions, dict):
        raise JevError("--questions must be a JSON object")
    r = ask(_load(args.state), questions, route=args.route, model=args.model, timeout=args.timeout,
            ledger=args.ledger, receipt_dir=args.receipt_dir)
    if args.json:
        print(json.dumps(r, indent=1))
    else:
        for qid, a in r["answers"].items():
            print(f"{qid}: {_brief(a)}")
        m, u = r["meta"], r["usage"]
        print(f"# {m['resolved_model']} via {m['route']} · {m['elapsed_ms']} ms · ${u['cost']:.7f} ({u['cost_source']})",
              file=sys.stderr)
    return 0


def cmd_files(args) -> int:
    cwd = os.path.abspath(args.cwd)
    if args.questions:
        questions = _load(args.questions)
    elif args.question:
        questions = {"match": noul(args.question)}
    else:
        raise JevError("give --question TEXT or --questions JSON")
    keep, skipped = prune(expand(args.patterns, cwd, args.recursive), cwd, cap=args.cap)
    if not keep:
        print(json.dumps({"files": [], "skipped": skipped}, indent=1) if args.json else "no files to judge")
        return 1
    t0 = time.monotonic()
    rows = judge_files(keep, questions, cwd, concurrency=args.concurrency, route=args.route,
                       context=args.context, ledger=args.ledger)
    wall = int((time.monotonic() - t0) * 1000)
    first = next(iter(questions))
    ok = [r for r in rows if "answers" in r]

    def key(r):
        a = r["answers"][first]
        return a.get("noul", a.get("confidence", 0))

    ok.sort(key=key, reverse=True)
    picked = None
    if args.pick:
        threshold = args.threshold
        cands = [r["path"] for r in ok if r["answers"][first].get("noul", 1) >= threshold]
        if cands:
            pr = pick_file(cands, args.pick, context=args.context, route=args.route, ledger=args.ledger)
            pa = pr["answers"]["pick"]
            # `other` is the exit Jev takes when no candidate fits; never report it as a path.
            picked = {"path": pa["choice"] if pa["choice"] in cands else None, "confidence": pa["confidence"]}
    total = sum(r.get("cost") or 0 for r in ok)
    if args.json:
        print(json.dumps({"files": ok, "errors": [r for r in rows if "error" in r], "skipped": skipped,
                          "pick": picked, "wall_ms": wall, "cost_usd": total}, indent=1))
        return 0
    for r in ok:
        print(f"{r['path']}\t" + "\t".join(f"{q}={_brief(a)}" for q, a in r["answers"].items()))
    for r in rows:
        if "error" in r:
            print(f"{r['path']}\tERROR {r['error']}")
    if picked:
        print(f"PICK\t{picked['path'] or 'none of the candidates fit'} ({picked['confidence']:.2f})")
    print(f"# {len(ok)} judged, {len(skipped)} skipped, {wall} ms wall, ${total:.6f} — contents never returned",
          file=sys.stderr)
    return 0


def cmd_compose(args) -> int:
    """Level 10: agent-authored questions over approved paths + an already-captured artifact + a note.
    Code assembles the state; the caller receives answers only. No command execution here: run the command
    through the harness (so its permissions and hooks apply), save the output, and pass it as --artifact."""
    questions = _load(args.questions)
    if not isinstance(questions, dict):
        raise JevError("--questions must be a JSON object")
    cwd = os.path.abspath(args.cwd)
    state: dict[str, Any] = {}
    if args.note:
        state["note"] = args.note
    if args.paths:
        keep, skipped = prune(expand(args.paths, cwd, False), cwd, cap=20)
        if skipped:
            print(f"# skipped: {skipped}", file=sys.stderr)
        state["files"] = {rel: Path(cwd, rel).read_text(errors="replace") for rel in keep}
    if args.artifact:
        text = Path(args.artifact).read_text(errors="replace")
        # Judge the tail of long logs: failures and summaries come last.
        state["output"] = text if len(text) <= 40_000 else "[…truncated head…]\n" + text[-40_000:]
    if not state:
        raise JevError("give at least one of --note, --paths, --artifact")
    r = ask(state, questions, route=args.route, ledger=args.ledger, tag="compose")
    for qid, a in r["answers"].items():
        print(f"{qid}: {_brief(a)}")
    m, u = r["meta"], r["usage"]
    print(f"# {m['resolved_model']} · {m['elapsed_ms']} ms · ${u['cost']:.7f} · redactions {m['redactions']} — contents never returned",
          file=sys.stderr)
    return 0


def cmd_calibrate(args) -> int:
    """Rows: {"state": ..., "expected": {qid: bool | option | level}} ; questions shared via --questions."""
    questions = _load(args.questions)
    rows = [json.loads(l) for l in Path(args.cases).read_text().splitlines() if l.strip()]
    with cf.ThreadPoolExecutor(max_workers=args.concurrency) as ex:
        def run(row):
            try:
                return row, ask(row["state"], questions, route=args.route, ledger=args.ledger)
            except JevError as e:
                return row, e
        results = list(ex.map(run, rows))
    report: dict[str, Any] = {"cases": len(rows), "errors": sum(isinstance(r, JevError) for _, r in results),
                              "questions": {}}
    for qid, q in questions.items():
        pairs = [(row["expected"][qid], res["answers"][qid]) for row, res in results
                 if not isinstance(res, JevError) and qid in row.get("expected", {})]
        if not pairs:
            continue
        if q["type"] == "noul":
            sweep = []
            for t in [x / 20 for x in range(2, 20)]:
                tp = sum(1 for e, a in pairs if e and a["noul"] >= t)
                fp = sum(1 for e, a in pairs if not e and a["noul"] >= t)
                fn = sum(1 for e, a in pairs if e and a["noul"] < t)
                tn = len(pairs) - tp - fp - fn
                sweep.append({"threshold": t, "accuracy": round((tp + tn) / len(pairs), 3), "false_pos": fp,
                              "false_neg": fn})
            report["questions"][qid] = {"type": "noul", "n": len(pairs), "sweep": sweep}
        else:
            field = "choice" if q["type"] == "choice" else "score"
            floors = []
            for f in [0.0, 0.5, 0.6, 0.7, 0.8, 0.9]:
                kept = [(e, a) for e, a in pairs if a["confidence"] >= f]
                right = sum(1 for e, a in kept if (a[field] == e if field == "choice" else round(a[field]) == e))
                floors.append({"confidence_floor": f, "kept": len(kept),
                               "accuracy": round(right / len(kept), 3) if kept else None})
            report["questions"][qid] = {"type": q["type"], "n": len(pairs), "by_confidence_floor": floors}
    print(json.dumps(report, indent=1))
    return 0


def cmd_route_status(args) -> int:
    r = resolve_route(args.route)
    cfg = ROUTES[r]
    status: dict[str, Any] = {"route": r, "endpoint": cfg["url"], "pinned_model": os.environ.get("JEV_MODEL") or cfg["model"],
                              "key_env": cfg["key"], "key_present": bool(cfg["key"] and _key(r)),
                              "ping": None}
    if r == "mock":
        status["key_present"] = True
    if not args.offline and status["key_present"]:
        try:
            p = ask({"x": "hello"}, {"greeting": noul("Is `x` a greeting?")}, route=r, timeout=10)
            status["ping"] = {"ok": True, "resolved_model": p["meta"]["resolved_model"], "ms": p["meta"]["elapsed_ms"],
                              "noul": p["answers"]["greeting"]["noul"]}
        except JevError as e:
            status["ping"] = {"ok": False, "error": str(e)}
    if not status["key_present"]:
        status["hint"] = INFISICAL_HINT
    print(json.dumps(status, indent=1))
    return 0 if status["key_present"] and (args.offline or (status["ping"] or {}).get("ok")) else 1


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="jev", description=__doc__.split("\n\n")[0])
    ap.add_argument("--route", choices=list(ROUTES), help="default: $JEV_ROUTE or requesty")
    ap.add_argument("--ledger", default=None, help="append JSONL ledger (numbers + hashes only); default $JEV_LEDGER")
    sub = ap.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("ask", help="one state, one question block")
    a.add_argument("--state", required=True, help="JSON, @file, - (stdin), or a plain string")
    a.add_argument("--questions", required=True, help="JSON object, @file, or -")
    a.add_argument("--model")
    a.add_argument("--timeout", type=float)
    a.add_argument("--receipt-dir")
    a.add_argument("--json", action="store_true")
    a.set_defaults(fn=cmd_ask)

    f = sub.add_parser("files", help="judge files in parallel; answers only, never contents")
    f.add_argument("patterns", nargs="+", help="paths, directories, or globs (quote globs)")
    f.add_argument("--question", help="shorthand: one yes/no question named `match`")
    f.add_argument("--questions", help="full question block (JSON / @file); first question sorts the output")
    f.add_argument("--context", help="extra state every file is judged against, e.g. the bug report")
    f.add_argument("--recursive", "-r", action="store_true")
    f.add_argument("--pick", help="then pick ONE file among matches with this instruction")
    f.add_argument("--threshold", type=float, default=0.5, help="noul cut for --pick candidates")
    f.add_argument("--cap", type=int, default=MAX_CHOICE_OPTIONS)
    f.add_argument("--concurrency", type=int, default=12)
    f.add_argument("--cwd", default=".")
    f.add_argument("--json", action="store_true")
    f.set_defaults(fn=cmd_files)

    k = sub.add_parser("compose", help="L10: your questions over approved paths + a captured artifact")
    k.add_argument("--questions", required=True, help="JSON object, @file, or -")
    k.add_argument("--paths", nargs="*", help="files code reads for you (≤20; secret-like files refused)")
    k.add_argument("--artifact", help="file holding already-captured output, e.g. saved test output")
    k.add_argument("--note", help="what only you can say: the request, your plan, one line of context")
    k.add_argument("--cwd", default=".")
    k.set_defaults(fn=cmd_compose)

    c = sub.add_parser("calibrate", help="score a labeled JSONL set")
    c.add_argument("--cases", required=True)
    c.add_argument("--questions", required=True)
    c.add_argument("--concurrency", type=int, default=8)
    c.set_defaults(fn=cmd_calibrate)

    s = sub.add_parser("route-status", help="key presence, pinned model, and a one-question ping")
    s.add_argument("--offline", action="store_true", help="skip the paid ping")
    s.set_defaults(fn=cmd_route_status)

    args = ap.parse_args(argv)
    try:
        return args.fn(args)
    except JevError as e:
        print(f"jev: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
