# Single-pass review: Jev for our agent workflows (analysis v1)

You are GPT-6 Astra, giving ONE independent review pass. There will be no follow-up rounds, so put everything
you want to say in this one answer. Do not edit files. Read whatever you need.

## The user's request (verbatim intent, from the repo owner)

> Get the transcript from this video and assess how we could better improve our workflows with Jev, and
> let's create some skills for this. https://www.youtube.com/watch?v=_U-O5lYhJ7Q
> Also, he has a GitHub repo for this. We should take what's going on here and maximize that, especially
> for our Grok workgraph workflows. I don't know how deeply we can integrate with Claude Code and Codex, but
> we have hooks that we can use. We need to consider how Jev can improve our performance and lower our
> costs all the way around. https://github.com/disler/ten-levels-of-jev
> When you do your first analysis, generate some output in a document that details your takeaway from all
> of this and how we can use things, and then have GPT Astra, via the ask skill, provide its feedback. …
> We don't want any rounds back and forth. We just want Astra to do one pass on what you've done.
> … generate your final analysis in a very detailed briefing. … We have the Requesty API key up at
> Infisical … if you want to do some testing with Jev …

## Sources (all readable from the working directory `/Users/brooks/Code/skills`)

- The video is "10 Levels of Jev For Agentic Engineers" by IndyDevDan, 2026-09-28: https://www.youtube.com/watch?v=_U-O5lYhJ7Q
  - Transcript (auto-captions; "Jeb/Java/Jeva" means Jev): `research/jev/transcript.md`
- The repo is https://github.com/disler/ten-levels-of-jev. A full clone is at `research/jev/repo/`. Key paths:
  - `README.md`
  - `apps/ten-levels/src/core/{client,types}.ts`
  - `apps/ten-levels/src/levels/level06..10/`
  - `apps/ten-levels/extensions/*.ts` (pi extensions)
  - `.claude/skills/hyper-jev/` (SKILL.md + cookbook)
- **The analysis under review:** `research/jev/analysis-v1.md`. The external sources it used are listed in `research/jev/SOURCES.md`.
- Live test harness and every raw result: `research/jev/live/`. The layout is:
  - `jevq.py` is the Requesty client.
  - `*-cases.json` are the inputs, `*.jsonl` the outputs, and `score_gate*.py` the scoring policies.
  - Label sets: `commands-labeled.json`, `commands-heldout.json`, and `commands-sol-adversarial.json` (the last one was generated independently by GPT-6 Sol).
- The prior internal WorkGraph-specific assessment is `/Users/brooks/Code/agent-ops/docs/jev-workgraph-assessment.md`. The WorkGraph source lives under `/Users/brooks/Code/agent-ops/grok/`, and the intent router is `/Users/brooks/Code/agent-ops/bin/workgraph-intent` (its tests are in `tests/workgraph-intent/`).
- Our existing consult tooling is in `ask/` (SKILL.md, providers.json).

## What I want from you

Review `analysis-v1.md` critically against the sources and the raw data. Specifically:

1. **Correctness.** Is anything in the analysis wrong about Jev, the repo, the video, our harnesses (Claude Code, Codex, Grok/WorkGraph, OMP/pi), or the measured numbers? Recompute at least two of the headline numbers from the raw `live/*.jsonl` files.
2. **Test validity.** Are the gate/injection/intent/compaction tests sound? Look for label leakage, overfitting (I tuned gate v2 on the 40-command set), and missing classes of commands or outputs. Say what additional test would most change the conclusions.
3. **Placements (§4.1).** For each of H1–H6, W1–W7, A1, and P1: is it placed at the right event, with the right direction (hold vs clear) and the right unreachable behaviour? Name any placement that is wrong, missing, or should be cut. Give particular attention to:
   - the Grok WorkGraph items, where the user said "especially"
   - the headless-auto-approve risk
4. **Cost model (§5).** Is the arithmetic honest? What would you measure to turn it into real numbers from our logs (Claude Code transcripts, `~/.grok/sessions/*/usage.json`, `.pipeline/*/trace.jsonl`, Codex sqlite)?
5. **Skills (§6).** Is "two skills (`jev`, `jev-guard`) plus beads for agent-ops" the right cut? What must each skill contain to be safe and useful? What's missing from its design?
6. **What did the video or repo offer that the analysis under-used?** Examples: L7 cut-point selection, L10 `ask_jev` with an agent-authored questions_json, the spend ledger, and the "think in ands" framing.

## Output format

Start with `VERDICT: <SHIP-AS-IS | SHIP-WITH-CHANGES | RETHINK>` on its own line. Follow it with numbered
findings, most important first. Each finding gives:
- severity (blocking / major / minor)
- the section or file:line it concerns
- the concrete change

End with a short list: "Top 5 changes to make before the final briefing."

## Optional Research Tools

Research tools are enabled for this review.

- Use local files first. Use external research only when current public facts, library/API docs, or contradiction checks materially affect the review.
- Prefer `$styrir-search` for bounded web research. Route the request, choose the smallest adequate search mode, fetch/read sources before treating them as evidence, and cite source IDs or URLs in findings.
- Use Context7 for current library, SDK, CLI, API, framework, and cloud documentation. Resolve the library ID before querying docs.
- You are the review orchestrator for this pass: choose which searches are appropriate, keep budgets small, and report any unavailable research tool plainly.
- Do not edit files.
