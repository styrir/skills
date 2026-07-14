// Claude adapter: normalizes `claude -p --output-format stream-json --verbose`
// events (assistant/user messages, thinking, result) for stream-core.

import {
  compact,
  isRecord,
  runAdapterCli,
  type ProgressEvent,
} from "./stream-core.ts";

function stringifyToolInput(input: unknown): string {
  if (!isRecord(input)) {
    return "";
  }
  if (typeof input.file_path === "string") {
    return input.file_path;
  }
  if (typeof input.pattern === "string" && typeof input.path === "string") {
    return `${input.pattern} in ${input.path}`;
  }
  if (typeof input.command === "string") {
    return compact(input.command, 120);
  }
  if (typeof input.cmd === "string") {
    return compact(input.cmd, 120);
  }
  return compact(JSON.stringify(input), 120);
}

function formatToolUse(content: Record<string, unknown>): string {
  const name = typeof content.name === "string" ? content.name : "tool";
  const input = stringifyToolInput(content.input);
  return input ? `tool: ${name} ${input}` : `tool: ${name}`;
}

function formatToolResult(content: Record<string, unknown>): string {
  const result = typeof content.content === "string" ? content.content : "";
  return result ? `tool-result: ${compact(result)}` : "tool-result: received";
}

function formatResult(event: Record<string, unknown>): string {
  const subtype = typeof event.subtype === "string" ? event.subtype : "complete";
  const details = [`result: ${subtype}`];
  if (typeof event.total_cost_usd === "number") {
    details.push(`cost $${event.total_cost_usd.toFixed(2)}`);
  }
  if (typeof event.duration_ms === "number") {
    details.push(`duration ${(event.duration_ms / 1000).toFixed(1)}s`);
  }
  return details.join(", ");
}

function summarizeContent(content: unknown): ProgressEvent[] {
  if (!Array.isArray(content)) {
    return [];
  }
  const events: ProgressEvent[] = [];
  for (const item of content) {
    if (!isRecord(item) || typeof item.type !== "string") {
      continue;
    }
    if (item.type === "text" && typeof item.text === "string" && item.text.trim()) {
      events.push({
        progressLine: `assistant: ${compact(item.text)}`,
        assistantText: item.text.trim(),
      });
    } else if (item.type === "tool_use") {
      events.push({ progressLine: formatToolUse(item) });
    } else if (item.type === "tool_result") {
      events.push({ progressLine: formatToolResult(item) });
    }
  }
  return events;
}

export function summarizeClaudeStreamLine(line: string): ProgressEvent[] {
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
  if (!isRecord(event)) {
    return [];
  }

  if (event.type === "assistant" && isRecord(event.message)) {
    return summarizeContent(event.message.content);
  }
  if (event.type === "user" && isRecord(event.message)) {
    return summarizeContent(event.message.content);
  }
  if (event.type === "system" && event.subtype === "thinking_tokens" && typeof event.estimated_tokens === "number") {
    return [{ progressLine: `thinking: ${event.estimated_tokens} tokens` }];
  }
  if (event.type === "result") {
    return [{ progressLine: formatResult(event) }];
  }
  if (typeof event.type === "string") {
    return [{ progressLine: `${event.type}: received` }];
  }
  return [];
}

if (typeof process.argv[1] === "string" && process.argv[1].endsWith("claude-stream-surface.ts")) {
  runAdapterCli("claude-stream-surface.ts", summarizeClaudeStreamLine, "Claude Review Result");
}
