import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import {
  bm25,
  chunk,
  claimPayload,
  claims,
  DECISIONS_URL,
  evidenceWindow,
  nanoDecider,
  passages,
  payload,
  scoreStage,
  type Asker,
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

test("no key falls back to BM25 and says so", async () => {
  const dir = runDir();
  mkdirSync(join(dir, "fetched"));
  writeFileSync(join(dir, "fetched", "s1.txt"), "pasta recipe");
  writeFileSync(join(dir, "fetched", "s2.txt"), "approval waits in cockpits");
  const out = await passages(dir, null);
  assert.equal(out.selector, "bm25");
  assert.match(out.fallbackReason ?? "", /no NanoGPT key/);
  assert.equal(out.chunks[0].sourceId, "s2");
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

test("claim payload asks whether the source supports the observation, with concrete criteria", () => {
  const body = claimPayload("X rose 5%.", "text");
  assert.deepEqual(body.provider, { zdr: true });
  assert.equal(body.questions.a.type, "noul");
  assert.equal(body.questions.a.instructions, "Does this source text support this observation: X rose 5%.");
  assert.match(body.questions.a.criteria.false, /goes beyond it/);
});

test("evidence window keeps the page's best-matching chunks within the budget, in page order", () => {
  const filler = (w: string) => Array.from({ length: 200 }, () => w).join(" ");
  const page = [filler("alpha"), "the io_workers setting needs a restart " + filler("beta"), filler("gamma")].join(" ");
  const w = evidenceWindow("io_workers needs a restart", page, 1000);
  assert.equal(w.chunks.length, 1);
  assert.match(w.text, /io_workers setting needs a restart/);
  const all = evidenceWindow("io_workers", page);
  assert.equal(all.chunks.length, chunk(page).length);
  assert.deepEqual(all.chunks, [...all.chunks].sort((a, b) => a - b));
});

function claimRun() {
  const dir = runDir({
    "ledger.json": {
      entries: [
        { id: "e1", sourceId: "s1", observation: "The cockpit pauses for approval." },
        { id: "e2", sourceId: "s1", observation: "The cockpit approves everything automatically." },
        { id: "e3", sourceId: "s9", observation: "Unfetched source." },
      ],
    },
  });
  mkdirSync(join(dir, "fetched"));
  writeFileSync(join(dir, "fetched", "s1.txt"), "The cockpit pauses for approval before any write.");
  return dir;
}

test("claims flags weakly supported entries, skips unfetched sources, and records cost", async () => {
  const dir = claimRun();
  const seen: any[] = [];
  const ask: Asker = async (body: any) => {
    seen.push(body);
    return { score: body.questions.a.instructions.includes("automatically") ? 0.08 : 0.97, tokens: 50 };
  };
  const out = await claims(dir, ask);
  assert.equal(out.checker, "pplx-decider-v1.2");
  assert.deepEqual(out.flagged, ["e2"]);
  assert.deepEqual(out.unchecked, ["e3"]);
  assert.equal(seen.length, 2);
  assert.match(seen[0].state, /pauses for approval/);
  assert.equal(out.entries[2].note, "no fetched/s9.txt");
  const manifest = JSON.parse(readFileSync(join(dir, "selector-manifest.json"), "utf8"));
  assert.equal(manifest.stages[0].stage, "claims");
  assert.equal(manifest.totals.inputTokens, 100);
  assert.ok(JSON.parse(readFileSync(join(dir, "claims.json"), "utf8")).entries.length === 3);
});

test("claims without a key or with a failed call leaves support null and says why", async () => {
  const none = await claims(claimRun(), null);
  assert.equal(none.checker, "none");
  assert.deepEqual(none.unchecked, ["e1", "e2", "e3"]);
  assert.match(none.entries[0].note ?? "", /no NanoGPT key/);
  const failing = await claims(claimRun(), async () => {
    throw new Error("HTTP 503");
  });
  assert.deepEqual(failing.flagged, []);
  assert.equal(failing.entries[0].note, "HTTP 503");
});
