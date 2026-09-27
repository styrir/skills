// Shared core for provider stream-surface adapters.
// An adapter supplies a LineSummarizer that turns one raw JSONL line from its
// provider into normalized progress events; the core owns trace capture,
// realtime stderr progress, and Markdown artifact rendering.

import { appendFileSync, existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

export interface StreamSummary {
  progressLines: string[];
  finalAssistantText: string;
  parseErrors: string[];
  terminal?: { ok: boolean; reason: string; sessionId?: string; requestId?: string };
  failures: string[];
}

export interface ProgressEvent {
  progressLine?: string;
  assistantText?: string;
  parseError?: string;
  completion?: { ok: boolean; reason: string; sessionId?: string; requestId?: string };
  failure?: string;
}

export type LineSummarizer = (line: string) => ProgressEvent[];

export interface RenderOptions {
  tracePath?: string;
  promptPath?: string;
  generatedAt?: string;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

export function compact(text: string, maxLength = 180): string {
  const oneLine = text.replace(/\s+/g, " ").trim();
  if (oneLine.length <= maxLength) {
    return oneLine;
  }
  return `${oneLine.slice(0, maxLength - 1)}...`;
}

export function makeSummary(): StreamSummary {
  return { progressLines: [], finalAssistantText: "", parseErrors: [], failures: [] };
}

export function consumeLine(
  summarizer: LineSummarizer,
  summary: StreamSummary,
  line: string,
  echoProgress: boolean,
): void {
  for (const event of summarizer(line)) {
    if (event.progressLine) {
      summary.progressLines.push(event.progressLine);
      if (echoProgress) {
        process.stderr.write(`${event.progressLine}\n`);
      }
    }
    // Only the latest assistant text is retained; adapters that emit
    // cumulative snapshots (grok) stay O(answer) instead of O(answer^2).
    if (event.assistantText) {
      summary.finalAssistantText = event.assistantText;
    }
    if (event.completion) summary.terminal = event.completion;
    if (event.failure) summary.failures.push(event.failure);
    if (event.parseError) {
      summary.parseErrors.push(event.parseError);
    }
  }
}

export function summarizeJsonl(summarizer: LineSummarizer, jsonl: string): StreamSummary {
  const summary = makeSummary();
  for (const line of jsonl.split(/\r?\n/)) {
    consumeLine(summarizer, summary, line, false);
  }
  return summary;
}

export function renderMarkdown(title: string, summary: StreamSummary, options: RenderOptions = {}): string {
  const generatedAt = options.generatedAt ?? new Date().toISOString();
  const finalText = summary.finalAssistantText || "_No assistant text was found in the stream._";
  const lines = [`# ${title}`, "", `Generated: ${generatedAt}`];

  if (options.tracePath) {
    lines.push(`Trace: \`${options.tracePath}\``);
  }
  if (options.promptPath) {
    lines.push(`Prompt: \`${options.promptPath}\``);
  }

  lines.push("", "## Final Response", "", finalText, "", "## Progress", "");
  if (summary.progressLines.length === 0) {
    lines.push("_No progress events were found._");
  } else {
    for (const line of summary.progressLines) {
      lines.push(`- ${line}`);
    }
  }

  if (summary.parseErrors.length > 0) {
    lines.push("", "## Parse Warnings", "");
    for (const error of summary.parseErrors) {
      lines.push(`- ${error}`);
    }
  }

  return `${lines.join("\n")}\n`;
}

// summary.md sits next to artifact.md so orchestrators can read the verdict
// and findings (or a builder's final records) without paying for the full
// artifact (token discipline directive 2026-07-10). Derived purely from the
// stream's final assistant text — no extra model calls.
const SUMMARY_MAX_LINES = 50;

function capSummaryLines(lines: string[]): string {
  const trimmed = [...lines];
  while (trimmed.length && !trimmed[0].trim()) trimmed.shift();
  while (trimmed.length && !trimmed[trimmed.length - 1].trim()) trimmed.pop();
  if (trimmed.length > SUMMARY_MAX_LINES) {
    return `${trimmed.slice(0, SUMMARY_MAX_LINES).join("\n")}\n\n_… truncated; full response in artifact.md_\n`;
  }
  return `${trimmed.join("\n")}\n`;
}

export function renderSummary(finalAssistantText: string): string {
  const text = finalAssistantText.trim();
  if (!text) {
    return "_No assistant text was found in the stream._\n";
  }
  const lines = text.split("\n");

  // Review-shaped output: keep the VERDICT line plus numbered-finding
  // paragraphs; drop surrounding prose and any progress/command echoes.
  const verdictLine = lines.find((l) => /^[\s#>*_`-]*VERDICT\b/i.test(l));
  if (verdictLine !== undefined) {
    const kept: string[] = [verdictLine.trim()];
    let paragraph: string[] = [];
    const flushParagraph = () => {
      const firstNumbered = paragraph.findIndex((l) => /^[\s>*_`]*\d+[.)]\s/.test(l));
      if (firstNumbered !== -1) {
        kept.push("", ...paragraph.slice(firstNumbered));
      }
      paragraph = [];
    };
    for (const line of lines) {
      if (line.trim()) {
        paragraph.push(line);
      } else {
        flushParagraph();
      }
    }
    flushParagraph();
    return capSummaryLines(kept);
  }

  // Builder/scout output: prefer trailing JSONL summary records...
  const end = lines.length;
  let start = end;
  while (start > 0) {
    const candidate = lines[start - 1].trim();
    if (!candidate.startsWith("{")) {
      break;
    }
    try {
      JSON.parse(candidate);
      start--;
    } catch {
      break;
    }
  }
  if (start < end) {
    return capSummaryLines(lines.slice(start, end));
  }

  // ...then a trailing fenced block (JSON summaries usually land there)...
  if (lines[end - 1].trim().startsWith("```")) {
    for (let i = end - 2; i >= 0; i--) {
      if (lines[i].trim().startsWith("```")) {
        return capSummaryLines(lines.slice(i, end));
      }
    }
  }

  // ...falling back to the last paragraph.
  let paragraphStart = end - 1;
  while (paragraphStart > 0 && lines[paragraphStart - 1].trim()) {
    paragraphStart--;
  }
  return capSummaryLines(lines.slice(paragraphStart, end));
}

function ensureParentDir(path: string) {
  const parent = dirname(path);
  if (parent && parent !== ".") {
    mkdirSync(parent, { recursive: true });
  }
}

export function runFileMode(
  summarizer: LineSummarizer,
  title: string,
  tracePath: string,
  markdownPath: string,
  promptPath?: string,
): void {
  if (existsSync(join(dirname(markdownPath), "result.json"))) {
    process.stderr.write("Replay refused: output is a recorded run; choose a fresh replay directory.\n");
    process.exitCode = 2;
    return;
  }
  const jsonl = readFileSync(tracePath, "utf8");
  const summary = summarizeJsonl(summarizer, jsonl);
  if (!summary.terminal?.ok || !summary.finalAssistantText.trim() || summary.parseErrors.length || summary.failures.length) {
    process.stderr.write("Replay refused: source is empty, incomplete, or malformed; existing artifacts preserved.\n");
    process.exitCode = 2;
    return;
  }
  ensureParentDir(markdownPath);
  writeFileSync(markdownPath, renderMarkdown(title, summary, { tracePath, promptPath }));
  writeFileSync(join(dirname(markdownPath), "summary.md"), renderSummary(summary.finalAssistantText));
}

export function runStreamMode(
  summarizer: LineSummarizer,
  title: string,
  tracePath: string,
  markdownPath: string,
  promptPath?: string,
): void {
  ensureParentDir(tracePath);
  ensureParentDir(markdownPath);
  if (process.env.ASK_TRACE_CAPTURED !== "true") writeFileSync(tracePath, "");

  let buffer = "";
  const summary = makeSummary();

  process.stdin.setEncoding("utf8");
  process.stdin.on("data", (chunk: string) => {
    if (process.env.ASK_TRACE_CAPTURED !== "true") appendFileSync(tracePath, chunk);
    buffer += chunk;
    const lines = buffer.split(/\r?\n/);
    buffer = lines.pop() ?? "";
    for (const line of lines) {
      consumeLine(summarizer, summary, line, true);
    }
  });
  process.stdin.on("end", () => {
    if (buffer.trim()) {
      if (process.env.ASK_TRACE_CAPTURED !== "true") appendFileSync(tracePath, "\n");
      consumeLine(summarizer, summary, buffer, true);
    }
    writeFileSync(markdownPath, renderMarkdown(title, summary, { tracePath, promptPath }));
    const summaryPath = join(dirname(markdownPath), "summary.md");
    writeFileSync(summaryPath, renderSummary(summary.finalAssistantText));
    const complete = Boolean(summary.terminal?.ok && summary.finalAssistantText.trim() && !summary.parseErrors.length && !summary.failures.length);
    const reason = summary.failures[0] || (summary.parseErrors.length ? "malformed_stream" : !summary.terminal ? "missing_completion" : !summary.terminal.ok ? summary.terminal.reason : !summary.finalAssistantText.trim() ? "empty_answer" : "completed");
    writeFileSync(join(dirname(markdownPath), "stream-result.json"), JSON.stringify({complete, reason, terminal: summary.terminal, parseErrors: summary.parseErrors, failures: summary.failures}, null, 2) + "\n");
    if (!complete) process.exitCode = 2;
    process.stderr.write(`artifact: ${markdownPath}\n`);
    process.stderr.write(`summary: ${summaryPath}\n`);
  });
}

export function runAdapterCli(scriptName: string, summarizer: LineSummarizer, title: string): void {
  const printUsage = () => {
    process.stderr.write(
      [
        "Usage:",
        `  ${scriptName} <trace.jsonl> <artifact.md> [prompt.md]`,
        `  ${scriptName} --from-file <trace.jsonl> <artifact.md> [prompt.md]`,
        "",
        "Pipe provider JSONL into the first form for realtime progress plus saved trace and Markdown.",
      ].join("\n") + "\n",
    );
  };

  const args = process.argv.slice(2);
  if (args[0] === "--from-file") {
    const [tracePath, markdownPath, promptPath] = args.slice(1);
    if (!tracePath || !markdownPath) {
      printUsage();
      process.exitCode = 1;
    } else {
      runFileMode(summarizer, title, tracePath, markdownPath, promptPath);
    }
  } else {
    const [tracePath, markdownPath, promptPath] = args;
    if (!tracePath || !markdownPath) {
      printUsage();
      process.exitCode = 1;
    } else {
      runStreamMode(summarizer, title, tracePath, markdownPath, promptPath);
    }
  }
}
