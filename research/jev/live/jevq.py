#!/usr/bin/env python3
"""Minimal Jev client over Requesty (chat-completions + response_format=questions).

Usage: jevq.py <cases.json> [out.jsonl]
cases.json: [{"id": str, "state": str|obj, "questions": {...}}]
Reads REQUESTY_API_KEY from env (inject with `infisical run`); never prints it.
Writes one JSONL row per case: id, answers, usage, model, elapsed_ms, http, error.
"""
import json, os, sys, time, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

URL = os.environ.get("JEV_REQUESTY_URL", "https://router.requesty.ai/v1/chat/completions")
MODEL = os.environ.get("JEV_MODEL", "typesafe/jev-latest")


def ask(state, questions, timeout=20):
    key = os.environ.get("REQUESTY_API_KEY", "").strip()
    if not key:
        raise SystemExit("REQUESTY_API_KEY not injected")
    content = state if isinstance(state, str) else json.dumps(state)
    body = json.dumps({
        "model": MODEL,
        "messages": [{"role": "user", "content": content}],
        "response_format": {"type": "questions", "questions": questions},
    }).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={
        "Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    t0 = time.time()
    for attempt in range(3):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                raw = json.loads(r.read())
            ms = int((time.time() - t0) * 1000)
            answers = json.loads(raw["choices"][0]["message"]["content"])
            return {"answers": answers, "usage": raw.get("usage"), "model": raw.get("model"),
                    "elapsed_ms": ms, "http": 200, "attempts": attempt + 1}
        except urllib.error.HTTPError as e:
            if e.code in (429, 502, 503, 529) and attempt < 2:
                time.sleep(0.5 * 2 ** attempt)
                continue
            return {"http": e.code, "error": e.read().decode()[:500],
                    "elapsed_ms": int((time.time() - t0) * 1000)}
        except Exception as e:  # network / parse
            return {"http": None, "error": repr(e)[:500], "elapsed_ms": int((time.time() - t0) * 1000)}


def main():
    cases = json.load(open(sys.argv[1]))
    out = open(sys.argv[2] if len(sys.argv) > 2 else "results.jsonl", "w")
    with ThreadPoolExecutor(max_workers=int(os.environ.get("JEV_CONCURRENCY", "8"))) as ex:
        results = list(ex.map(lambda c: {"id": c["id"], **ask(c["state"], c["questions"])}, cases))
    for r in results:
        out.write(json.dumps(r) + "\n")
        a = r.get("answers") or {}
        brief = {k: (v.get("noul") if v.get("type") == "noul" else
                     (v.get("choice"), round(v.get("confidence", 0), 2)) if v.get("type") == "choice" else
                     (round(v.get("score", 0), 2), round(v.get("confidence", 0), 2))) for k, v in a.items()}
        print(r["id"], r.get("http"), f'{r["elapsed_ms"]}ms', brief or r.get("error"))


if __name__ == "__main__":
    main()
