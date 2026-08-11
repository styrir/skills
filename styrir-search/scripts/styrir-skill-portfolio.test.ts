import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const skillDir = dirname(dirname(fileURLToPath(import.meta.url)));
const skillsRoot = dirname(skillDir);

function readSkill(relativePath: string): string {
  return readFileSync(join(skillsRoot, relativePath), "utf8");
}

function spawnCodexExecReviewHelp() {
  const result = spawnSync("codex", ["exec", "review", "--help"], { encoding: "utf8" });
  if (result.error && "code" in result.error && result.error.code === "ENOENT") {
    return null;
  }
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return result.stdout;
}

function spawnCodexExecHelp() {
  const result = spawnSync("codex", ["exec", "--help"], { encoding: "utf8" });
  if (result.error && "code" in result.error && result.error.code === "ENOENT") {
    return null;
  }
  assert.equal(result.status, 0, result.stderr || result.error?.message);
  return result.stdout;
}

test("ask is the unified skill for Codex and Claude second opinions", () => {
  const skill = readSkill("ask/SKILL.md");
  const providers = readSkill("ask/providers.json");

  assert.match(skill, /name: ask/);
  assert.match(skill, /ask Codex/i);
  assert.match(skill, /ask Claude/i);
  assert.match(skill, /second opinion/i);
  assert.match(skill, /artifact: <path>/);
  assert.match(skill, /summary: <path>/);
  assert.match(skill, /streams/i);
  assert.match(providers, /"codex"/);
  assert.match(providers, /"claude"/);
});

test("ask documents the current Codex exec and Claude proxy routes", () => {
  const skill = readSkill("ask/SKILL.md");
  const runner = readSkill("ask/scripts/ask.sh");
  const execHelp = spawnCodexExecHelp();
  const reviewHelp = spawnCodexExecReviewHelp();

  if (execHelp && reviewHelp) {
    assert.match(execHelp, /-o,\s+--output-last-message/);
    assert.match(execHelp, /-C,\s+--cd/);
    assert.match(execHelp, /--sandbox/);
    assert.match(reviewHelp, /--uncommitted/);
    assert.match(reviewHelp, /-o,\s+--output-last-message/);
  }
  assert.match(skill, /codex exec --json/);
  assert.match(skill, /VibeProxy-owned route/);
  assert.match(runner, /TRANSPORT="\$\(field transport\)"/);
  assert.match(runner, /grok "\$\{GROK_ARGS\[@\]\}" --prompt-file/);
});

test("ask surfaces provider authentication failures as explicit blockers", () => {
  const skill = readSkill("ask/SKILL.md");
  const runner = readSkill("ask/scripts/ask.sh");

  assert.match(skill, /Never claim a blocked run happened/);
  assert.match(runner, /blocker\(\)/);
  assert.match(runner, /grok not authenticated/);
  assert.match(runner, /requested .* run did not produce a result/);
});

test("ask preserves surfaced progress and durable artifacts", () => {
  const skill = readSkill("ask/SKILL.md");

  assert.match(skill, /trace\.jsonl/);
  assert.match(skill, /tail -f/);
  assert.match(skill, /artifact\.md/);
  assert.match(skill, /summary\.md/);
  assert.match(skill, /No silent redirects/);
});
