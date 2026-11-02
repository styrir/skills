#!/usr/bin/env node
// Styrir Search decision-model steps, both on fetched text: passage ranking after fetch, and a shadow
// claim check of each ledger entry against its source. The passage question is the one measured in styrir-os
// agent-guidance/research/gptr-plus-decider-20261101/eval/run_eval.py (pplx_noul). Choosing fetches from search
// snippets was tried and removed: it fetched fewer primary sources (eval-step4-results.md there).
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

export const DECISIONS_URL = "https://nano-gpt.com/api/v1/decisions";
export const MODEL = "perplexity/pplx-decider-v1.2";
export const USD_PER_M_INPUT = 0.02; // list price; output is free
export const DEFAULT_THRESHOLD = 0.5;
export const DEFAULT_KEEP = 40;
export const CLAIM_FLAG = 0.5; // an entry its source supports with less than this is flagged for a recheck
// Characters of the cited page sent as the state: the whole page when it fits, else its chunks that best match the
// observation (BM25). Three chunks missed compound observations' numbers; 24K stays well inside the 32K-token training length.
export const CLAIM_WINDOW_CHARS = 24_000;
const CONCURRENCY = 8;
const RETRY_STATUS = new Set([429, 500, 502, 503, 529]);

export type Scored = { score: number; tokens: number };
export type Decider = (state: string) => Promise<Scored>;
export type Stage = {
  stage: string;
  selector: "pplx-decider-v1.2" | "bm25" | "none";
  model: string | null;
  calls: number;
  inputTokens: number;
  listCostUsd: number;
  fallbackReason: string | null;
};

export function payload(question: string, state: string) {
  return {
    model: MODEL,
    provider: { zdr: true },
    state,
    questions: {
      a: {
        type: "noul",
        instructions: `Does this passage help answer the question: ${question}`,
        criteria: {
          true: "It contains information that would help write an accurate answer to the question",
          false: "It is unrelated, only on the same general topic, navigation or boilerplate",
        },
      },
    },
  };
}

export function claimPayload(observation: string, state: string) {
  return {
    model: MODEL,
    provider: { zdr: true },
    state,
    questions: {
      a: {
        type: "noul",
        instructions: `Does this source text support this observation: ${observation}`,
        criteria: {
          true: "The text states this, or states facts that directly establish it",
          false: "The text does not say this, says only part of it, says something different, or the observation goes beyond it",
        },
      },
    },
  };
}

type DeciderOpts = { fetchImpl?: typeof fetch; sleep?: (ms: number) => Promise<void>; onModel?: (m: string) => void };
export type Asker = (body: object) => Promise<Scored>;

// One candidate per request (Perplexity: batching independent candidates hurts answers).
export function nanoDecider(key: string, question: string, opts: DeciderOpts = {}): Decider {
  const ask = nanoAsker(key, opts);
  return (state) => ask(payload(question, state));
}

// Posts one noul request; retries overload and 5xx, never a 4xx.
export function nanoAsker(key: string, opts: DeciderOpts = {}): Asker {
  const doFetch = opts.fetchImpl ?? fetch;
  const sleep = opts.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
  return async (body) => {
    let err = "";
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        const res = await doFetch(DECISIONS_URL, {
          method: "POST",
          headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
        if (res.ok) {
          const out = await res.json();
          const score = out?.answers?.a?.noul;
          if (typeof score !== "number") throw new Error(`no noul answer: ${JSON.stringify(out).slice(0, 200)}`);
          if (out.model) opts.onModel?.(out.model);
          return { score, tokens: Number(out?.usage?.input_tokens) || 0 };
        }
        err = `HTTP ${res.status}`;
        if (!RETRY_STATUS.has(res.status)) break;
      } catch (e) {
        err = (e as Error).message;
        if (err.startsWith("no noul answer")) break;
      }
      await sleep(1500 * 2 ** attempt);
    }
    throw new Error(err);
  };
}

export function tokenize(text: string): string[] {
  return text.toLowerCase().match(/[\p{L}\p{N}]+/gu) ?? [];
}

// Okapi BM25 (k1 1.5, b 0.75) with IDF over the given pool, as GPT Researcher's keyword filter does.
export function bm25(query: string, docs: string[]): number[] {
  const toks = docs.map(tokenize);
  const avg = toks.reduce((n, t) => n + t.length, 0) / (toks.length || 1) || 1;
  const df = new Map<string, number>();
  for (const t of toks) for (const w of new Set(t)) df.set(w, (df.get(w) ?? 0) + 1);
  const q = [...new Set(tokenize(query))];
  return toks.map((t) => {
    const tf = new Map<string, number>();
    for (const w of t) tf.set(w, (tf.get(w) ?? 0) + 1);
    return q.reduce((s, w) => {
      const f = tf.get(w) ?? 0;
      if (!f) return s;
      const n = df.get(w) ?? 0;
      const idf = Math.log((toks.length - n + 0.5) / (n + 0.5) + 1);
      return s + (idf * f * 2.5) / (f + 1.5 * (0.25 + (0.75 * t.length) / avg));
    }, 0);
  });
}

// ponytail: fixed 1000-char window, 100 overlap, snapped back to whitespace; the eval used
// LangChain's recursive splitter. Switch only if passage quality shows boundary damage.
export function chunk(text: string, size = 1000, overlap = 100): { start: number; text: string }[] {
  const out: { start: number; text: string }[] = [];
  let start = 0;
  while (start < text.length) {
    let end = Math.min(start + size, text.length);
    if (end < text.length) {
      const ws = text.lastIndexOf(" ", end);
      const nl = text.lastIndexOf("\n", end);
      const cut = Math.max(ws, nl);
      if (cut > start + size / 2) end = cut;
    }
    const piece = text.slice(start, end).trim();
    if (piece) out.push({ start, text: piece });
    if (end >= text.length) break;
    start = end - overlap;
  }
  return out;
}

// Whole-stage scoring: all PPLX or all BM25, never mixed.
export async function scoreStage(
  stage: string,
  question: string,
  texts: string[],
  decider: Decider | null,
  model: { name: string | null } = { name: null },
): Promise<{ scores: number[]; meta: Stage }> {
  const bm25Stage = (reason: string, calls = 0, tokens = 0) => ({
    scores: bm25(question, texts),
    meta: {
      stage,
      selector: "bm25" as const,
      model: null,
      calls,
      inputTokens: tokens,
      listCostUsd: cost(tokens),
      fallbackReason: reason,
    },
  });
  if (!decider) return bm25Stage(NO_KEY);
  const results = await inPool(texts, decider);
  const tokens = results.reduce((n, r) => n + (r instanceof Error ? 0 : r.tokens), 0);
  const failed = results.filter((r): r is Error => r instanceof Error);
  if (failed.length) {
    return bm25Stage(`${failed.length} of ${texts.length} decision calls failed: ${failed[0].message}`, texts.length, tokens);
  }
  return {
    scores: results.map((r) => (r as Scored).score),
    meta: {
      stage,
      selector: "pplx-decider-v1.2",
      model: model.name ?? MODEL,
      calls: texts.length,
      inputTokens: tokens,
      listCostUsd: cost(tokens),
      fallbackReason: null,
    },
  };
}

const NO_KEY = "no NanoGPT key in the environment (run through infisical)";

async function inPool<T>(items: T[], fn: (item: T) => Promise<Scored>): Promise<(Scored | Error)[]> {
  const results: (Scored | Error)[] = new Array(items.length);
  let next = 0;
  await Promise.all(
    Array.from({ length: Math.min(CONCURRENCY, items.length) }, async () => {
      while (next < items.length) {
        const i = next++;
        results[i] = await fn(items[i]).catch((e: Error) => e);
      }
    }),
  );
  return results;
}

function cost(tokens: number) {
  return Math.round(tokens * USD_PER_M_INPUT * 1e4) / 1e10;
}

// Select: PPLX keeps scores >= threshold (it may return fewer than the cap); BM25 has no
// calibrated threshold, so it keeps the top non-zero scores.
export function select<T>(items: T[], scores: number[], selector: Stage["selector"], threshold: number, cap: number) {
  const ranked = items.map((item, i) => ({ item, score: scores[i] })).sort((a, b) => b.score - a.score);
  const pass = ranked.filter((r) => (selector === "bm25" ? r.score > 0 : r.score >= threshold));
  return { ranked, selected: pass.slice(0, Math.max(0, cap)) };
}

function readJson(path: string) {
  return JSON.parse(readFileSync(path, "utf8"));
}

export function runQuestion(runDir: string): string {
  for (const f of ["request.json", "plan.json"]) {
    const p = join(runDir, f);
    if (existsSync(p) && typeof readJson(p).question === "string") return readJson(p).question;
  }
  throw new Error(`No question in ${runDir}/request.json or plan.json.`);
}

export function fetchedFiles(runDir: string): string[] {
  const dir = join(runDir, "fetched");
  return existsSync(dir) ? readdirSync(dir).filter((f) => /\.(txt|md)$/.test(f)).sort() : [];
}

export function recordStage(runDir: string, meta: Stage) {
  const path = join(runDir, "selector-manifest.json");
  const prev = existsSync(path) ? readJson(path) : { stages: [] };
  const stages: Stage[] = [...prev.stages.filter((s: Stage) => s.stage !== meta.stage), meta];
  const totals = {
    calls: stages.reduce((n, s) => n + s.calls, 0),
    inputTokens: stages.reduce((n, s) => n + s.inputTokens, 0),
    listCostUsd: cost(stages.reduce((n, s) => n + s.inputTokens, 0)),
  };
  writeFileSync(path, `${JSON.stringify({ pricing: { model: MODEL, usdPerMillionInput: USD_PER_M_INPUT }, stages, totals }, null, 2)}\n`);
}

export async function passages(runDir: string, decider: Decider | null, threshold = DEFAULT_THRESHOLD, keep = DEFAULT_KEEP, model = { name: null as string | null }) {
  const question = runQuestion(runDir);
  const items = fetchedFiles(runDir).flatMap((f) =>
    chunk(readFileSync(join(runDir, "fetched", f), "utf8")).map((c, i) => ({ sourceId: f.replace(/\.(txt|md)$/, ""), i, ...c })),
  );
  const { scores, meta } = await scoreStage("passages", question, items.map((c) => c.text), decider, model);
  const { ranked, selected } = select(items, scores, meta.selector, threshold, keep);
  const out = {
    question,
    selector: meta.selector,
    fallbackReason: meta.fallbackReason,
    threshold: meta.selector === "bm25" ? null : threshold,
    chunks: ranked.map((r) => ({ sourceId: r.item.sourceId, chunk: r.item.i, start: r.item.start, score: r.score })),
  };
  writeFileSync(join(runDir, "passages.json"), `${JSON.stringify(out, null, 2)}\n`);
  const md = [
    `# Passages, best first (${meta.selector}${meta.fallbackReason ? `; fallback: ${meta.fallbackReason}` : ""})`,
    "",
    "Reading aid only. Cite the source, not this file; every observation still comes from the fetched page.",
    "",
    ...selected.flatMap((r) => [`## ${r.item.sourceId} · chunk ${r.item.i} · char ${r.item.start} · ${r.score.toFixed(3)}`, "", r.item.text, ""]),
  ];
  writeFileSync(join(runDir, "passages.md"), md.join("\n"));
  recordStage(runDir, meta);
  return { ...out, kept: selected.length };
}

// The evidence the check reads: the cited page's best-matching chunks up to the budget, in page order.
export function evidenceWindow(observation: string, pageText: string, budget = CLAIM_WINDOW_CHARS) {
  const parts = chunk(pageText);
  const s = bm25(observation, parts.map((p) => p.text));
  const picked: number[] = [];
  let used = 0;
  for (const i of parts.map((_, i) => i).sort((a, b) => s[b] - s[a])) {
    if (picked.length && used + parts[i].text.length > budget) break;
    picked.push(i);
    used += parts[i].text.length;
  }
  picked.sort((a, b) => a - b);
  return { chunks: picked, text: picked.map((i) => parts[i].text).join("\n…\n") };
}

// Shadow claim check: does each ledger entry's source say what the entry says? It records and flags; it never
// changes the ledger or a gate. No key or a failed call leaves that support null, with the reason.
export async function claims(runDir: string, ask: Asker | null, model = { name: null as string | null }) {
  const entries: { id: string; sourceId: string; observation: string }[] = readJson(join(runDir, "ledger.json")).entries ?? [];
  const texts = new Map(fetchedFiles(runDir).map((f) => [f.replace(/\.(txt|md)$/, ""), readFileSync(join(runDir, "fetched", f), "utf8")]));
  const items = entries.map((e) => ({ e, page: texts.get(e.sourceId) }));
  const checkable = items.filter((x) => x.page !== undefined);
  const windows = new Map(checkable.map((x) => [x.e.id, evidenceWindow(x.e.observation, x.page!)]));
  const results = ask ? await inPool(checkable, (x) => ask(claimPayload(x.e.observation, windows.get(x.e.id)!.text))) : [];
  const byId = new Map(checkable.map((x, i) => [x.e.id, results[i]]));
  const rows = items.map(({ e, page }) => {
    const r = byId.get(e.id);
    const note = page === undefined ? `no fetched/${e.sourceId}.txt` : !ask ? NO_KEY : r instanceof Error ? r.message : null;
    return { id: e.id, sourceId: e.sourceId, support: r && !(r instanceof Error) ? r.score : null, chunks: windows.get(e.id)?.chunks ?? [], note };
  });
  const tokens = results.reduce((n, r) => n + (r instanceof Error ? 0 : r.tokens), 0);
  const out = {
    checker: ask ? "pplx-decider-v1.2" : "none",
    model: ask ? (model.name ?? MODEL) : null,
    flagBelow: CLAIM_FLAG,
    flagged: rows.filter((r) => r.support !== null && r.support < CLAIM_FLAG).map((r) => r.id),
    unchecked: rows.filter((r) => r.support === null).map((r) => r.id),
    entries: rows,
  };
  writeFileSync(join(runDir, "claims.json"), `${JSON.stringify(out, null, 2)}\n`);
  recordStage(runDir, {
    stage: "claims",
    selector: ask ? "pplx-decider-v1.2" : "none",
    model: out.model,
    calls: results.length,
    inputTokens: tokens,
    listCostUsd: cost(tokens),
    fallbackReason: ask ? null : NO_KEY,
  });
  return out;
}

async function main(argv: string[]) {
  const [cmd, runDir, ...rest] = argv;
  const flag = (name: string) => {
    const i = rest.indexOf(name);
    return i >= 0 ? rest[i + 1] : undefined;
  };
  if (!runDir || (cmd !== "passages" && cmd !== "claims")) {
    throw new Error("Usage: styrir-select.ts passages <run-dir> [--threshold 0.5] [--keep 40] | claims <run-dir>");
  }
  const key: string | undefined = process.env.nanogpt;
  const model = { name: null as string | null };
  if (cmd === "claims") {
    const out = await claims(runDir, key ? nanoAsker(key, { onModel: (m) => (model.name = m) }) : null, model);
    const checked = out.entries.length - out.unchecked.length;
    console.log(`claims: ${out.checker}; ${checked} of ${out.entries.length} entries checked, ${out.flagged.length} below ${CLAIM_FLAG}${out.flagged.length ? ` (${out.flagged.join(", ")})` : ""}`);
    return;
  }
  const threshold = Number(flag("--threshold") ?? DEFAULT_THRESHOLD);
  const decider = key ? nanoDecider(key, runQuestion(runDir), { onModel: (m) => (model.name = m) }) : null;
  const result = await passages(runDir, decider, threshold, Number(flag("--keep") ?? DEFAULT_KEEP), model);
  console.log(`passages: ${result.selector}${result.fallbackReason ? ` (fallback: ${result.fallbackReason})` : ""}; ${result.kept} of ${result.chunks.length} chunks kept`);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2)).catch((e) => {
    console.error((e as Error).message);
    process.exit(1);
  });
}
