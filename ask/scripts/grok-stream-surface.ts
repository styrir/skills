// Grok adapter: normalizes `grok --output-format streaming-json` headless
// events for stream-core.
// Verified event shape on this machine (grok CLI 0.2.93, 2026-07-09 probe):
//   {"type":"thought","data":"The"}   <- token-level deltas, one per event
//   {"type":"text","data":"ok"}       <- token-level deltas, one per event
//   {"type":"end","stopReason":"EndTurn","sessionId":"...","requestId":"..."}
//   {"type":"error","message":"..."}  (documented; not observed in probes)
// Tool calls do NOT surface in the stream (verified: read_file ran silently),
// so progress cadence is thought/text only — coarser than codex/claude.
// Docs also name max_turns_reached and auto_compact_* events; unknown types
// degrade to a generic "<type>: received" line, never a crash.
//
// Because data arrives as token deltas, this adapter is stateful: it
// accumulates the full answer and flushes throttled progress lines instead of
// emitting one line per token.

import {
  compact,
  isRecord,
  runAdapterCli,
  type LineSummarizer,
  type ProgressEvent,
} from "./stream-core.ts";

const TEXT_FLUSH_CHARS = 400;
const THOUGHT_FLUSH_CHARS = 240;

export function createGrokSummarizer(): LineSummarizer {
  let answer = ""; // full accumulated assistant text (the durable artifact body)
  let pendingText = ""; // answer text since the last progress flush
  let pendingThought = "";

  const flushThought = (events: ProgressEvent[]) => {
    if (pendingThought.trim()) {
      events.push({ progressLine: `thinking: ${compact(pendingThought, 140)}` });
    }
    pendingThought = "";
  };

  const flushText = (events: ProgressEvent[]) => {
    if (pendingText.trim()) {
      events.push({ progressLine: `assistant: ${compact(pendingText)}` });
    }
    pendingText = "";
  };

  return (line: string): ProgressEvent[] => {
    const trimmed = line.trim();
    if (!trimmed) {
      return [];
    }
    let event: unknown;
    try {
      event = JSON.parse(trimmed);
    } catch (error) {
      const message = error instanceof Error ? error.message : "invalid JSON";
      return [{ parseError: message, progressLine: `parse-error: ${message}` }];
    }
    if (!isRecord(event) || typeof event.type !== "string") {
      return [];
    }

    const events: ProgressEvent[] = [];
    if (event.type === "thought" && typeof event.data === "string") {
      flushText(events); // keep progress ordering honest across phase changes
      pendingThought += event.data;
      if (pendingThought.length >= THOUGHT_FLUSH_CHARS) {
        flushThought(events);
      }
      return events;
    }
    if (event.type === "text" && typeof event.data === "string") {
      flushThought(events);
      answer += event.data;
      pendingText += event.data;
      if (pendingText.length >= TEXT_FLUSH_CHARS) {
        flushText(events);
      }
      // Keep the durable answer current on every delta so a stream that dies
      // without an `end` event (crash, truncation) loses nothing.
      events.push({ assistantText: answer.trim() });
      return events;
    }
    if (event.type === "end") {
      flushThought(events);
      flushText(events);
      const stopReason = typeof event.stopReason === "string" ? event.stopReason : "unknown";
      const sessionId = typeof event.sessionId === "string" ? event.sessionId : "";
      events.push({
        progressLine: `end: ${stopReason}${sessionId ? `, session ${sessionId} (resume: grok -r ${sessionId})` : ""}`,
        assistantText: answer.trim() || undefined,
      });
      return events;
    }
    if (event.type === "error") {
      flushThought(events);
      flushText(events);
      const message = typeof event.message === "string" ? event.message : JSON.stringify(event);
      events.push({ progressLine: `error: ${compact(message)}` });
      return events;
    }
    // Unknown types include terminal events (max_turns_reached, auto_compact_*):
    // flush pending buffers so their progress isn't stranded behind them.
    flushThought(events);
    flushText(events);
    events.push({ progressLine: `${event.type}: received` });
    return events;
  };
}

if (typeof process.argv[1] === "string" && process.argv[1].endsWith("grok-stream-surface.ts")) {
  runAdapterCli("grok-stream-surface.ts", createGrokSummarizer(), "Grok Run Result");
}
