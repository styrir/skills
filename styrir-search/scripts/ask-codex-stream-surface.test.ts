import assert from "node:assert/strict";
import test from "node:test";

import { summarizeClaudeStreamLine } from "../../ask/scripts/claude-stream-surface.ts";
import { renderMarkdown, summarizeJsonl } from "../../ask/scripts/stream-core.ts";

const sampleStream = [
  JSON.stringify({
    type: "assistant",
    message: {
      content: [
        {
          type: "text",
          text: "I am reading the staged skill files now.",
        },
        {
          type: "tool_use",
          name: "Read",
          input: { file_path: "/tmp/work/skills/ask-codex/SKILL.md" },
        },
      ],
    },
  }),
  JSON.stringify({
    type: "user",
    message: {
      content: [
        {
          type: "tool_result",
          content: "1\\t---\\n2\\tname: ask-codex\\n",
        },
      ],
    },
  }),
  JSON.stringify({
    type: "system",
    subtype: "thinking_tokens",
    estimated_tokens: 1250,
  }),
  JSON.stringify({
    type: "assistant",
    message: {
      content: [
        {
          type: "text",
          text: "Findings first: no blocking issues remain.",
        },
      ],
    },
  }),
  JSON.stringify({
    type: "result",
    subtype: "success",
    total_cost_usd: 0.42,
    duration_ms: 12000,
  }),
].join("\n");

test("summarizes Claude stream-json into readable progress lines", () => {
  const summary = summarizeJsonl(summarizeClaudeStreamLine, sampleStream);

  assert.deepEqual(summary.parseErrors, []);
  assert.equal(summary.finalAssistantText, "Findings first: no blocking issues remain.");
  assert.match(summary.progressLines.join("\n"), /assistant: I am reading the staged skill files now\./);
  assert.match(summary.progressLines.join("\n"), /tool: Read \/tmp\/work\/skills\/ask-codex\/SKILL\.md/);
  assert.match(summary.progressLines.join("\n"), /tool-result: 1\\t---/);
  assert.match(summary.progressLines.join("\n"), /thinking: 1250 tokens/);
  assert.match(summary.progressLines.join("\n"), /result: success, cost \$0\.42, duration 12\.0s/);
});

test("renders a durable Markdown artifact from a Claude stream summary", () => {
  const summary = summarizeJsonl(summarizeClaudeStreamLine, sampleStream);
  const markdown = renderMarkdown("Claude Review Result", summary, {
    tracePath: "outputs/review.jsonl",
    promptPath: "work/review-prompt.md",
  });

  assert.match(markdown, /^# Claude Review Result/);
  assert.match(markdown, /Trace: `outputs\/review\.jsonl`/);
  assert.match(markdown, /Prompt: `work\/review-prompt\.md`/);
  assert.match(markdown, /## Final Response/);
  assert.match(markdown, /Findings first: no blocking issues remain\./);
  assert.match(markdown, /## Progress/);
  assert.match(markdown, /tool: Read \/tmp\/work\/skills\/ask-codex\/SKILL\.md/);
});
