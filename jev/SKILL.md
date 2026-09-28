---
name: jev
description: Use when a bounded judgment (yes/no, pick one of N, grade on a scale) would otherwise cost an LLM call, a long think, or reading files into context — gates, routers, classifiers, "which of these files matters", "is this output a real failure", "is this diff risky". Calls Jev (TypeSafe System One, ~0.4 s, ~$0.00003/call) through Requesty, OpenRouter, or TypeSafe. Also for calibrating Jev thresholds on labeled data. Not for prose, code, math, counting, dates, or anything a grep answers.
---

# Jev — typed decisions in ~400 ms for fractions of a cent

Jev is a **decision model, not an LLM**. You send a `state` (text or JSON) and typed questions; it returns
probabilities your code branches on. It never writes prose, code, or explanations. Think in *ands*:
**code** for numbers and thresholds, **Jev** for bounded judgments, **agents/LLMs** for open work.

| Type | Ask | Get back | Use for |
|---|---|---|---|
| `noul` | yes/no, optional `true`/`false` criteria | `noul` = P(yes) | gates, flags, the smart `if` |
| `choice` | one of ≤255 options you define | `choice`, `probabilities`, `confidence` — **never an undeclared label** | routing, classification |
| `score` | 2–10 ordered levels, low→high | fractional `score`, `legend`, `probabilities`, `confidence` | severity, risk, grading |

## Run it

The CLI is stdlib Python; keys come from the environment only. Our Requesty key lives in Infisical:

```bash
infisical run --projectId 2588c473-4c4c-4b5a-b0f5-e261184b6b53 --env dev -- \
  python3 <skill-dir>/scripts/jev.py route-status            # key present? pinned model? one paid ping (~$0.00001)
```

| Command | What it does |
|---|---|
| `jev.py ask --state @s.json --questions @q.json` | One call. `--json` for the full result (answers, usage, meta). |
| `jev.py files -r src --question "Does this file validate tokens?"` | **Cheap reads**: code reads each file and asks Jev in parallel; **you get answers, never contents**. Secret-like files (`.env`, keys, `auth.json`…) are never sent. |
| `jev.py files -r . --question "Related to the rounding bug?" --context "<bug report>" --pick "Which file most likely holds the bug?"` | Scout a repo, then one Choice keyed by real paths. Open only the pick. |
| `jev.py compose --questions @q.json --paths src/a.ts tests/a.test.ts --artifact /tmp/test-output.txt --note "user says totals are off by a cent"` | **Level 10**: your own questions over approved paths + an already-captured artifact + a note. Code assembles the state; you get answers only. It never runs commands; run them through the harness (its permissions and hooks apply) and pass the saved output. |
| `jev.py calibrate --cases labeled.jsonl --questions @q.json` | Accuracy and threshold sweeps on your own labeled rows `{"state":…, "expected":{qid: value}}`. Run before trusting a threshold. |
| `jev.py --route mock …` | Deterministic offline shape stand-in for tests. Not intelligence. |

Keys: environment first, then the macOS Keychain item `jev.<route>` (for hooks, which run without `infisical run`).
Credential-shaped text (keys, bearer tokens, URL credentials, JWTs, private keys) is redacted locally before any
request; `meta.redactions` counts them. A pinned request that resolves to a different model version is an error.

Routes: `requesty` (default, pinned `typesafe/jev-1.13.0`), `openrouter` (`OPENROUTER_API_KEY`, `typesafe/jev-1.13`),
`typesafe` (`TYPESAFE_API_KEY`). Choose with `--route` / `JEV_ROUTE`; there is **no silent fallback** between routes.
`JEV_LEDGER=~/.local/state/jev/ledger.jsonl` appends numbers and hashes (never state) for every call.

Library: `sys.path.insert(0, "<skill-dir>/scripts"); from jev import ask, noul, choice, score, JevError`.

## When an agent should reach for it

- **You want to learn something about a file, not change it.** Ask with `files` instead of reading it into
  context: it never enters your window, is never re-billed on later turns, and 17 files judge in ~2 s wall.
  Read the file only when you need to edit or quote it.
- **Before acting on output**: classify a test failure (`bug_in_code | wrong_test | environment | flaky | other`),
  score a diff's risk before committing, check whether a request is clear enough to plan.
- **Any code path that ends "LLM call → parse JSON → if/switch"** is a Jev question. Keep the LLM only for the
  branch that needs prose.
- **Fan out**: ask every question you might need in one call; they share the state and cost the same.

## Question design (the rules that decide accuracy)

Read [references/question-design.md](references/question-design.md) before writing a gate, router, or anything
that acts. The short form:

1. One judgment per question. Describe **situations** in criteria, not degrees ("blocked, no workaround", not "high").
2. Always give a Choice an `other` exit (the builder adds one) and route `other` to review.
3. **Jev only answers what you ask.** A "what does this do to the machine" gate approved `cat ~/.codex/auth.json`
   at 1.00 read-only — nothing asked about secrets. Ask each risk class explicitly.
4. Send only the state the question needs; irrelevant detail costs accuracy (context rot). Keep state under ~32k tokens.
5. Numbers, counts, dates, arithmetic → code. Extract parts with a Choice if needed; compare in code.
6. The answer says *what*; confidence says *whether*. Use a floor (→ human) and a bar (→ act). Thresholds do not
   transfer between a Noul and a Choice. Probabilities jitter ~±0.06 between identical calls — leave margin.
7. Pin the model (`jev-1.13.0`) for anything thresholded; re-run `calibrate` before moving to a new version.

## Where it must not decide alone

Security boundaries (a static deny list comes first and is never overridden by a Jev "safe"), anything that
approves, ships, deploys, clears a review count, or demotes severity, and any authorization. Jev may **hold,
raise, flag, route, or filter**; clearing needs calibration evidence and an explicit owner decision.
Everything in `state` leaves the machine (hosted model) — never send secrets or files you would not paste into a
third-party API.

## Related

- `jev-guard` — Jev in Claude Code / Codex / OMP hooks (bash gate, hostile-output screen, compaction advisor).
- Evidence and measurements: `research/jev/` (analysis, live calibration sets, GPT-6 Sol adversarial set).
- Upstream: https://github.com/disler/ten-levels-of-jev · https://docs.requesty.ai/features/decisions ·
  https://docs.typesafe.ai/model-jaggedness/jev-1.13
