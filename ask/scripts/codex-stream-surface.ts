// Codex adapter: normalizes `codex exec --json` events for stream-core.
// Verified event shape on this machine (codex CLI, 2026-07-05 probe):
//   {"type":"thread.started","thread_id":"..."}
//   {"type":"turn.started"}
//   {"type":"item.completed","item":{"id":"item_0","type":"agent_message","text":"..."}}
//   {"type":"turn.completed","usage":{"input_tokens":N,"output_tokens":N,...}}
// Longer runs may add item.started / item.updated and item types such as
// reasoning, command_execution, file_change, mcp_tool_call, web_search, error.
// Unknown shapes degrade to a generic "<type>: received" line, never a crash.

import {
  compact,
  isRecord,
  runAdapterCli,
  type ProgressEvent,
} from "./stream-core.ts";

function describeItem(item: Record<string, unknown>, phase: string): ProgressEvent[] {
  const itemType = typeof item.type === "string" ? item.type : "item";

  if (itemType === "agent_message" && typeof item.text === "string" && item.text.trim()) {
    // Only completed messages become the durable assistant text; started/updated
    // phases surface as progress without overwriting the final answer.
    if (phase === "completed") {
      return [{ progressLine: `assistant: ${compact(item.text)}`, assistantText: item.text.trim() }];
    }
    return [{ progressLine: `assistant(${phase}): ${compact(item.text)}` }];
  }
  if (itemType === "reasoning") {
    const text = typeof item.text === "string" ? item.text : "";
    return phase === "completed" && text.trim()
      ? [{ progressLine: `thinking: ${compact(text, 140)}` }]
      : [];
  }
  if (itemType === "command_execution") {
    const command = typeof item.command === "string" ? compact(item.command, 120) : "";
    const exit = typeof item.exit_code === "number" ? ` (exit ${item.exit_code})` : "";
    return [{ progressLine: `cmd${phase === "completed" ? exit : ""}: ${command || "running"}` }];
  }
  if (itemType === "file_change") {
    return [{ progressLine: `file-change: ${compact(JSON.stringify(item.changes ?? item), 120)}` }];
  }
  if (itemType === "error") {
    const message = typeof item.message === "string" ? item.message : JSON.stringify(item);
    return [{ progressLine: `error: ${compact(message)}` }];
  }
  return [{ progressLine: `${itemType}: ${phase}` }];
}

function formatUsage(usage: unknown): string {
  if (!isRecord(usage)) {
    return "turn: completed";
  }
  const parts = ["turn: completed"];
  if (typeof usage.input_tokens === "number") {
    parts.push(`in ${usage.input_tokens}`);
  }
  if (typeof usage.output_tokens === "number") {
    parts.push(`out ${usage.output_tokens}`);
  }
  if (typeof usage.reasoning_output_tokens === "number") {
    parts.push(`reasoning ${usage.reasoning_output_tokens}`);
  }
  return parts.join(", ");
}

export function summarizeCodexStreamLine(line: string): ProgressEvent[] {
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

  if (event.type === "thread.started") {
    const threadId = typeof event.thread_id === "string" ? event.thread_id : "";
    return [{ progressLine: threadId ? `thread: ${threadId}` : "thread: started" }];
  }
  if (event.type === "turn.started") {
    return [{ progressLine: "turn: started" }];
  }
  if (event.type === "turn.completed") {
    return [{ progressLine: formatUsage(event.usage) }];
  }
  if (event.type === "turn.failed") {
    return [{ progressLine: `error: turn failed — ${compact(JSON.stringify(event))}` }];
  }
  if (event.type.startsWith("item.") && isRecord(event.item)) {
    const phase = event.type.slice("item.".length);
    return describeItem(event.item, phase);
  }
  if (event.type === "error") {
    const message = typeof event.message === "string" ? event.message : JSON.stringify(event);
    return [{ progressLine: `error: ${compact(message)}` }];
  }
  return [{ progressLine: `${event.type}: received` }];
}

if (typeof process.argv[1] === "string" && process.argv[1].endsWith("codex-stream-surface.ts")) {
  runAdapterCli("codex-stream-surface.ts", summarizeCodexStreamLine, "Codex Review Result");
}
