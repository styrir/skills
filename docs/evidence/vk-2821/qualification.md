# vk-2821: `ask.sh codex` with no `-m` uses gpt-6.1-sol

Evidence snapshot. Date: 2026-11-16. Machine: the operator's macOS box. codex-cli 0.169.0.

## The run

Run from the worktree holding commit 4923b81, where `ask/providers.json` sets the codex `defaultModel` to `gpt-6.1-sol`. No `-m` flag was passed:

```
ask/scripts/ask.sh codex -d <empty scratch folder> -o <fresh scratch folder> "Reply with exactly: OK"
```

The runner's launch line:

```
ask: provider=codex transport=codex model=gpt-6.1-sol tier=stream-json
```

## What the run recorded

From its `result.json` (paths and runtime hashes left out):

```json
{
  "run_id": "fa61c885-fde6-4d59-8642-e809e8193564",
  "status": "complete",
  "reason": "completed",
  "requested_model": "gpt-6.1-sol",
  "transport": "codex",
  "provider_exit": 0,
  "adapter_exit": 0,
  "stream": {
    "complete": true,
    "reason": "completed",
    "terminal": { "ok": true, "reason": "turn.completed" },
    "parseErrors": [],
    "failures": [],
    "waived": []
  },
  "artifact_sha256": {
    "trace.jsonl": "d283aef966d4ac42077bb64f9570ce40e5ffd2e8be39870b13ffe76b93f09fa3",
    "artifact.md": "3ddc4b94d7b0f0d5dc1d038a08915644e24cbdf0d90c7037d4b2042a4cf71ede",
    "summary.md": "a12b7cb43c9d9134b5bb1b35e9096b66775d9e92e7611d1cc92b02edd6782a87"
  }
}
```

- Its `status.jsonl` has a `watcher_attached` event with `"model": "gpt-6.1-sol"` and `"transport": "codex"`.
- Its `trace.jsonl` holds four events: `thread.started`, `turn.started`, one `item.completed` of type `agent_message`, and `turn.completed`. It has no `error` events.
- The final response in `artifact.md` is `OK`.

## Limits

- The raw run folder was in a session scratch directory and is not kept. This file holds the excerpt and the checksums the run recorded.
- One run, one prompt. It shows the default resolves and the route works, not answer quality.
- The Codex trace does not name the model. The model is taken from the runner's launch line, `requested_model` and the watcher event, which all come from `providers.json`.
