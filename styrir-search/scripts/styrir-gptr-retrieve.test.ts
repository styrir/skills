import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";
import {
  assessSpend,
  childEnv,
  classifySource,
  judgePrompt,
  judgeRelevance,
  parseArgs,
  parseVerdict,
  providerKeys,
  rankCandidates,
  sourceRegistry,
  tavilyCredits,
  type SourceRow,
} from "./styrir-gptr-retrieve.ts";

const scriptsDir = dirname(fileURLToPath(import.meta.url));

test("types sources by domain rule with generic fallbacks", () => {
  assert.equal(classifySource("https://www.w3.org/TR/webaudio/"), "official");
  assert.equal(classifySource("https://developer.apple.com/documentation/swiftui"), "official");
  assert.equal(classifySource("https://www.courtlistener.com/opinion/1/"), "legal");
  assert.equal(classifySource("https://houstonlawreview.org/article/1"), "academic");
  assert.equal(classifySource("https://arxiv.org/abs/2501.00001"), "academic");
  assert.equal(classifySource("https://github.com/a2aproject/A2A"), "repo");
  assert.equal(classifySource("https://www.reddit.com/r/swift/"), "social");
  assert.equal(classifySource("https://www.copyright.gov/ai/"), "official");
  assert.equal(classifySource("https://docs.example.dev/guide"), "official");
  assert.equal(classifySource("https://law.stanford.edu/x"), "academic");
  assert.equal(classifySource("https://netflix.com/title/1"), "analysis");
  assert.equal(classifySource("https://brush.ninja/create/animation-maker"), "analysis");
});

function row(url: string, overrides: Partial<SourceRow> = {}): SourceRow {
  return { url, title: url, fetchStatus: "ok", verdict: "relevant", ...overrides };
}

test("drops dead and off-topic sources and ranks primary first in original order", () => {
  const { candidates, dropped } = rankCandidates([
    row("https://blog.example.com/a"),
    row("https://www.w3.org/TR/webaudio/"),
    row("https://brush.ninja/create/animation-maker", { verdict: "off_topic" }),
    row("https://developer.apple.com/dead", { fetchStatus: "failed", verdict: null }),
    row("https://developer.apple.com/documentation/xcode/versions", { verdict: "off_topic" }),
    row("https://arxiv.org/abs/1", { verdict: "unknown" }),
  ]);

  assert.deepEqual(
    candidates.map((c) => [c.id, c.url, c.primary]),
    [
      ["s1", "https://www.w3.org/TR/webaudio/", true],
      ["s2", "https://arxiv.org/abs/1", true],
      ["s3", "https://developer.apple.com/documentation/xcode/versions", true],
      ["s4", "https://blog.example.com/a", false],
    ],
  );
  assert.deepEqual(
    dropped.map((d) => [d.url, d.reason]),
    [
      ["https://brush.ninja/create/animation-maker", "off_topic"],
      ["https://developer.apple.com/dead", "dead"],
    ],
  );
  assert.ok(candidates.every((c) => c.fetched === true && c.fetchStatus === "ok"));
});

test("judge fails safe to unknown and never sees report text", async () => {
  assert.equal(parseVerdict("relevant"), "relevant");
  assert.equal(parseVerdict(" Off_topic."), "off_topic");
  assert.equal(parseVerdict(""), "unknown");
  assert.equal(await judgeRelevance("p", async () => { throw new Error("HTTP 500"); }), "unknown");
  assert.equal(await judgeRelevance("p", async () => "off_topic"), "off_topic");

  const prompt = judgePrompt("Q?", "O", { url: "https://x.test", title: "T", text: "a".repeat(5000) });
  assert.match(prompt, /Question: Q\?/);
  assert.ok(prompt.length < 2500, "page text is truncated");

  const shim = readFileSync(join(scriptsDir, "gptr_deep_sources.py"), "utf8");
  assert.doesNotMatch(shim, /write_report\(|get_research_context\(/);
});

test("spend is the provider balance delta, split by phase, checked against the cap", () => {
  assert.deepEqual(assessSpend({ before: 12.5, afterGptr: 11.8, afterJudge: 11.79 }, 1), {
    balanceBeforeUsd: 12.5,
    balanceAfterUsd: 11.79,
    gptrCostUsd: 0.7,
    judgeCostUsd: 0.01,
    costUsd: 0.71,
    capUsd: 1,
    overCap: false,
  });
  assert.equal(assessSpend({ before: 12.5, afterGptr: 11.4, afterJudge: 11.3 }, 1).overCap, true);
  assert.equal(parseArgs(["r.json", "out"], {}).capUsd, 1);
  assert.equal(parseArgs(["r.json", "out", "--cap-usd", "2"], { GPTR_PYTHON: "/v/bin/python" }).python, "/v/bin/python");
  assert.throws(() => parseArgs(["r.json", "out", "--cap-usd", "0"], {}), /cap-usd/);
});

test("keys come only from the Infisical names; other secrets do not reach GPT Researcher", () => {
  assert.throws(() => providerKeys({ OPENAI_API_KEY: "ambient", TAVILY_API_KEY: "ambient" }), /Infisical/);
  const env = childEnv(
    { PATH: "/bin", nanogpt: "n", tavily: "t", OTHER_SECRET: "x", OPENAI_API_KEY: "ambient" },
    providerKeys({ nanogpt: "n", tavily: "t" }),
  );
  assert.equal(env.OPENAI_API_KEY, "n");
  assert.equal(env.TAVILY_API_KEY, "t");
  assert.equal(env.DEEP_RESEARCH_BREADTH, "4");
  assert.equal(env.DEEP_RESEARCH_DEPTH, "2");
  assert.equal(env.RETRIEVER, "tavily");
  assert.equal(env.CONTEXT_FILTER, "keyword");
  assert.equal(env.PATH, "/bin");
  assert.equal("OTHER_SECRET" in env || "nanogpt" in env, false);
});

test("CLI refuses to run without Infisical keys, before any network call", () => {
  const result = spawnSync(
    process.execPath,
    ["--experimental-strip-types", join(scriptsDir, "styrir-gptr-retrieve.ts"), "missing.json", "out"],
    { encoding: "utf8", env: { PATH: process.env.PATH, OPENAI_API_KEY: "ambient", TAVILY_API_KEY: "ambient" } },
  );
  assert.equal(result.status, 1);
  assert.match(result.stderr, /Missing provider keys/);
});

test("Tavily credits count both GPT Researcher searches and adapter extracts", () => {
  assert.deepEqual(
    tavilyCredits({ usage: 100, search: 80, extract: 20 }, { usage: 172, search: 140, extract: 32 }),
    { measured: true, totalCredits: 72, searchCredits: 60, extractCredits: 12, paygoEstimateUsd: 0.576 },
  );
  assert.equal(tavilyCredits(null, { usage: 1, search: 1, extract: 0 }).measured, false);
});

test("source registry records a selection decision for every returned URL", () => {
  const { candidates, dropped } = rankCandidates([
    row("https://www.w3.org/TR/webaudio/"),
    row("https://brush.ninja/x", { verdict: "off_topic" }),
    row("https://dead.example/x", { fetchStatus: "failed", verdict: null }),
  ]);
  assert.deepEqual(
    sourceRegistry(candidates, dropped).sources.map((s) => [s.id, s.selection, s.fetched]),
    [["s1", "candidate", true], ["x1", "off_topic", true], ["x2", "dead", false]],
  );
});
