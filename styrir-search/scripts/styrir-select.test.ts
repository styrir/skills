import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  bm25,
  chunk,
  DECISIONS_URL,
  nanoDecider,
  normalizeUrl,
  passages,
  payload,
  scoreStage,
  triage,
  type Decider,
} from "./styrir-select.ts";

const noSleep = async () => {};

function runDir(results: Record<string, unknown> = {}) {
  const dir = mkdtempSync(join(tmpdir(), "styrir-select-"));
  writeFileSync(join(dir, "request.json"), JSON.stringify({ question: "How do cockpits handle approval waits?" }));
  for (const [name, body] of Object.entries(results)) writeFileSync(join(dir, name), JSON.stringify(body));
  return dir;
}

const fixed = (scores: Record<string, number>): Decider => async (state) => {
  const hit = Object.keys(scores).find((k) => state.includes(k));
  return { score: hit ? scores[hit] : 0.1, tokens: 100 };
};

test("payload is one noul question with ZDR on PPLX v1.2", () => {
  const body = payload("Q?", "passage");
  assert.equal(body.model, "perplexity/pplx-decider-v1.2");
  assert.deepEqual(body.provider, { zdr: true });
  assert.equal(body.state, "passage");
  assert.deepEqual(Object.keys(body.questions), ["a"]);
  assert.equal(body.questions.a.type, "noul");
  assert.equal(body.questions.a.instructions, "Does this passage help answer the question: Q?");
});

test("decider posts one candidate, retries 5xx, and reads noul and tokens", async () => {
  const calls: any[] = [];
  const fetchImpl = async (url: string, init: any) => {
    calls.push({ url, init });
    if (calls.length === 1) return { ok: false, status: 503 };
    return { ok: true, status: 200, json: async () => ({ model: "perplexity/pplx-decider-v1.2-20261016", answers: { a: { noul: 0.9 } }, usage: { input_tokens: 42 } }) };
  };
  let model = "";
  const d = nanoDecider("k", "Q?", { fetchImpl: fetchImpl as any, sleep: noSleep, onModel: (m) => (model = m) });
  assert.deepEqual(await d("one"), { score: 0.9, tokens: 42 });
  assert.equal(calls.length, 2);
  assert.equal(calls[1].url, DECISIONS_URL);
  assert.equal(JSON.parse(calls[1].init.body).state, "one");
  assert.equal(model, "perplexity/pplx-decider-v1.2-20261016");
});

test("decider does not retry a 4xx", async () => {
  let n = 0;
  const d = nanoDecider("k", "Q?", { fetchImpl: (async () => (n++, { ok: false, status: 400 })) as any, sleep: noSleep });
  await assert.rejects(d("x"), /HTTP 400/);
  assert.equal(n, 1);
});

test("bm25 ranks term overlap and chunker overlaps by about 10%", () => {
  const s = bm25("approval waits", ["human approval waits in cockpits", "unrelated cooking recipe", "approval"]);
  assert.ok(s[0] > s[2] && s[2] > s[1] && s[1] === 0);
  const text = Array.from({ length: 600 }, (_, i) => `w${i}`).join(" ");
  const parts = chunk(text);
  assert.ok(parts.length >= 3);
  assert.ok(parts.every((p) => p.text.length <= 1000));
  assert.ok(text.slice(parts[1].start, parts[0].start + parts[0].text.length).length >= 90);
});

test("triage round 1 keeps scores above threshold, caps at 7, dedupes URLs, records cost", async () => {
  const results = Array.from({ length: 12 }, (_, i) => ({ url: `https://ex.com/p${i}`, title: `t${i}`, snippet: i < 9 ? "GOOD" : "bad" }));
  results.push({ url: "https://www.ex.com/p0/?utm_source=x", title: "dup", snippet: "GOOD" });
  const dir = runDir({ "search-results.r1.json": results });
  const out = await triage(dir, 1, fixed({ GOOD: 0.8 }));
  assert.equal(out.selector, "pplx-decider-v1.2");
  assert.equal(out.candidates.length, 12);
  assert.equal(out.selected.length, 7);
  const manifest = JSON.parse(readFileSync(join(dir, "selector-manifest.json"), "utf8"));
  assert.equal(manifest.stages[0].stage, "triage.r1");
  assert.equal(manifest.totals.calls, 12);
  assert.equal(manifest.totals.inputTokens, 1200);
  assert.equal(manifest.totals.listCostUsd, 0.000024);
});

test("triage may return fewer than the cap", async () => {
  const dir = runDir({ "search-results.r1.json": [{ url: "https://a.org/1", snippet: "GOOD" }, { url: "https://a.org/2", snippet: "bad" }] });
  const out = await triage(dir, 1, fixed({ GOOD: 0.7 }));
  assert.deepEqual(out.selected, ["https://a.org/1"]);
});

test("triage round 2 excludes round-1 picks and respects the remaining fetch budget", async () => {
  const dir = runDir({
    "triage.r1.json": { selected: ["https://a.org/1"] },
    "search-results.r2.json": [{ url: "https://a.org/1", snippet: "GOOD" }, ...[2, 3, 4, 5].map((i) => ({ url: `https://a.org/${i}`, snippet: "GOOD" }))],
  });
  mkdirSync(join(dir, "fetched"));
  for (let i = 0; i < 8; i++) writeFileSync(join(dir, "fetched", `s${i}.txt`), "x");
  const out = await triage(dir, 2, fixed({ GOOD: 0.9 }));
  assert.equal(out.cap, 2);
  assert.equal(out.candidates.length, 4);
  assert.equal(out.selected.length, 2);
});

test("no key falls back to BM25 and says so", async () => {
  const dir = runDir({ "search-results.r1.json": [{ url: "https://a.org/1", title: "approval waits" }, { url: "https://a.org/2", title: "pasta" }] });
  const out = await triage(dir, 1, null);
  assert.equal(out.selector, "bm25");
  assert.match(out.fallbackReason ?? "", /no NanoGPT key/);
  assert.deepEqual(out.selected, ["https://a.org/1"]);
  const manifest = JSON.parse(readFileSync(join(dir, "selector-manifest.json"), "utf8"));
  assert.equal(manifest.stages[0].selector, "bm25");
});

test("any failed call switches the whole stage to BM25 with the reason", async () => {
  let n = 0;
  const flaky: Decider = async () => {
    if (n++ === 1) throw new Error("HTTP 503");
    return { score: 0.9, tokens: 10 };
  };
  const { scores, meta } = await scoreStage("x", "approval", ["approval", "b", "c"], flaky);
  assert.equal(meta.selector, "bm25");
  assert.match(meta.fallbackReason ?? "", /1 of 3 decision calls failed: HTTP 503/);
  assert.deepEqual(scores, bm25("approval", ["approval", "b", "c"]));
});

test("passages rank chunks across fetched pages and write a best-first reading file", async () => {
  const dir = runDir();
  mkdirSync(join(dir, "fetched"));
  writeFileSync(join(dir, "fetched", "s1.txt"), "menu home login");
  writeFileSync(join(dir, "fetched", "s2.txt"), "the cockpit pauses for APPROVAL");
  const out = await passages(dir, fixed({ APPROVAL: 0.95 }));
  assert.equal(out.chunks[0].sourceId, "s2");
  assert.equal(out.kept, 1);
  assert.match(readFileSync(join(dir, "passages.md"), "utf8"), /## s2 · chunk 0 · char 0 · 0\.950/);
});

test("normalizeUrl drops www, trailing slash, fragments and utm params", () => {
  assert.equal(normalizeUrl("https://www.Ex.com/a/?utm_x=1#h"), normalizeUrl("https://ex.com/a"));
});
