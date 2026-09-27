# Consultation and subagent supervision

Every delegated run must have an event channel and an attached watcher before useful child work starts. This is an explicit operator requirement. The ask runner enforces it for its supported CLI and direct-proxy consultation routes. It does not claim to control another harness's native spawning API.

## Ask outputs

- `trace.jsonl`: raw provider events, immediately captured independently of rendering.
- `status.jsonl`: normalized lifecycle and provider-event metadata. Every row has schema version, run/parent/agent identity, sequence and timestamp. Heartbeats name waiting/receiving and the last real provider event.
- `result.json`: complete/failed/timed_out/cancelled, reason, process exits, terminal evidence, route metadata where available, timings, skill root, artifact hashes and locations.
- `artifact.md` and `summary.md`: complete output only when the result confirms completion. Failed runs have an explicit incomplete artifact/summary and retain rendered output in `partial.md`.
- `stderr.log`: private, redacted provider diagnostics. Model request headers, credentials and configuration contents are never printed.
- `watcher-loss.json`: guard receipt if the watcher disappears unexpectedly; the run-owned provider group is drained.

Only `result.json` with `status=complete` authorizes consuming a review as complete. Exit zero alone, a heartbeat, a partial answer, or a provider model listing is insufficient. A valid completion event, usable answer, nonempty raw trace and successful provider/adapter exits are required. Parse errors, provider errors and missing terminal events fail closed.

Read the normalized status and summary, not raw reasoning. Provider thought events produce activity counts, not reasoning excerpts. Heartbeats mean the watcher is alive; they never invent model progress. Runtime code is copied to a private frozen snapshot before execution, and output directories cannot be reused across attempts. Concurrent watcher ownership is locked.

## Invocation and recovery

The watcher defaults to 180 seconds until first model output and 600 seconds total. Override with `--first-output-seconds N` and `--wall-seconds N`. First output includes real model text or reasoning activity; CLI setup events do not satisfy it. Routine watcher heartbeats are emitted every 15 seconds.

Cancellation propagates from the parent or SIGINT/SIGTERM, drains only run-owned process groups, and preserves failure diagnostics. A child guard detects watcher loss. macOS restricted sandboxes may deny process inventory and group signalling: run with the normal approved CLI permissions; a refused capability must fail before provider admission, not weaken cleanup verification.

Retries use a fresh `-o` directory and a bounded explicit budget. Preserve the failed attempt. Do not retry concurrently, silently change models, or consume a partial review as final. Empty/incomplete replay input is refused without overwriting existing artifacts.

## Supported launch surfaces

| Surface | Event channel and watcher | Qualification boundary |
|---|---|---|
| Ask → Grok CLI | Provider JSONL + ask attached watcher | Legacy/current event fixtures; native xAI auth and configured proxy routes distinct |
| Ask → native Claude/Codex CLI | Provider JSONL + same watcher | Result/turn completion adapters; preserve registry ownership and explicit model |
| Ask → direct loopback proxy | SSE normalized to JSONL + same watcher | Explicit `--transport proxy`; content-only; no filesystem, research, or mutation tools |
| WorkGraph consultation | Existing agent-ops supervisor/host monitor + inner ask watcher | WorkGraph owns its ledger, deadlines and immutable attempt identity; ask owns provider completion |
| Native in-process delegated agents | Host JSONL plus host-owned watcher or a qualified adapter | Do not treat another host's status API as automatically qualified. Verify actual lifecycle, parent/child identity, cancellation and terminal reconciliation first |
| Other providers without adapters | No qualified route | Refused; no silent plain-text fallback |

Before invoking a native delegate, the orchestrator must verify the event channel and watcher exist. If a native surface cannot expose them, use an explicitly authorized qualified consultation route or keep the work in the parent. Never claim universal enforcement from an ask-only change. Do not bolt a second scheduler onto WorkGraph or let peer agents independently mutate its sequenced ledger.

## Direct proxy reviews

Use `--transport proxy` for a self-contained prompt with the complete review material included. This opt-in route reads the existing Grok model registration and runtime proxy credential; defaults remain unchanged. It permits loopback endpoints only, verifies the exact configured model against inventory, requests SSE, checks any reported model identity, and rejects non-stop finish reasons. `--max-output-tokens N` defaults to 16384; select a budget and effort proportional to the task.

It has no tools. `--research`, `--build` and unenforceable monetary caps are refused. A proxy SDK/CLI version mismatch is owned by the proxy; updating native Claude Code may not update its compatibility profile. Model aliases advertised by a proxy are not proof of the upstream model's independent identity; record configured and reported identities honestly.

Run `bash scripts/ask-runner-self-test.sh`, `python3 scripts/supervision-test.py`, and `python3 scripts/proxy-test.py` for the offline gates. Then qualify a small synthetic live request before a real review.
