#!/usr/bin/env node
// Styrir Plus v2 selector: PPLX Decider triage before fetch, passage ranking after fetch.
// Wire format and question wording are the ones measured in styrir-os
// agent-guidance/research/gptr-plus-decider-20261101/eval/run_eval.py (pplx_noul).
import { existsSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

export const DECISIONS_URL = "https://nano-gpt.com/api/v1/decisions";
export const MODEL = "perplexity/pplx-decider-v1.2";
export const USD_PER_M_INPUT = 0.02; // list price; output is free
export const TOTAL_FETCHES = 10; // styrir_plus maxFetches
export const ROUND_CAPS: Record<number, number> = { 1: 7, 2: 3 };
export const DEFAULT_THRESHOLD = 0.5;
export const DEFAULT_KEEP = 40;
const CONCURRENCY = 8;
const RETRY_STATUS = new Set([429, 500, 502, 503, 529]);

export type Candidate = { url: string; title?: string; snippet?: string; query?: string };
export type Scored = { score: number; tokens: number };
export type Decider = (state: string) => Promise<Scored>;
export type Stage = {
  stage: string;
  selector: "pplx-decider-v1.2" | "bm25";
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

// One candidate per request (Perplexity: batching independent candidates hurts answers).
export function nanoDecider(
  key: string,
  question: string,
  opts: { fetchImpl?: typeof fetch; sleep?: (ms: number) => Promise<void>; onModel?: (m: string) => void } = {},
): Decider {
  const doFetch = opts.fetchImpl ?? fetch;
  const sleep = opts.sleep ?? ((ms: number) => new Promise<void>((r) => setTimeout(r, ms)));
  return async (state) => {
    let err = "";
    for (let attempt = 0; attempt < 5; attempt++) {
      try {
        const res = await doFetch(DECISIONS_URL, {
          method: "POST",
          headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
          body: JSON.stringify(payload(question, state)),
        });
        if (res.ok) {
          const body = await res.json();
          const score = body?.answers?.a?.noul;
          if (typeof score !== "number") throw new Error(`no noul answer: ${JSON.stringify(body).slice(0, 200)}`);
          if (body.model) opts.onModel?.(body.model);
          return { score, tokens: Number(body?.usage?.input_tokens) || 0 };
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
  if (!decider) return bm25Stage("no NanoGPT key in the environment (run through infisical)");
  const results: (Scored | Error)[] = new Array(texts.length);
  let next = 0;
  await Promise.all(
    Array.from({ length: Math.min(CONCURRENCY, texts.length) }, async () => {
      while (next < texts.length) {
        const i = next++;
        results[i] = await decider(texts[i]).catch((e: Error) => e);
      }
    }),
  );
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

function cost(tokens: number) {
  return Math.round(tokens * USD_PER_M_INPUT * 1e4) / 1e10;
}

export function normalizeUrl(url: string): string {
  try {
    const u = new URL(url);
    u.hash = "";
    for (const k of [...u.searchParams.keys()]) if (k.startsWith("utm_")) u.searchParams.delete(k);
    return `${u.host.replace(/^www\./, "")}${u.pathname.replace(/\/$/, "")}${u.search}`.toLowerCase();
  } catch {
    return url.trim().toLowerCase();
  }
}

export function triageText(c: Candidate) {
  return `${c.title ?? ""}\n${c.url}\n${c.snippet ?? ""}`;
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

export async function triage(runDir: string, round: number, decider: Decider | null, threshold = DEFAULT_THRESHOLD, model = { name: null as string | null }) {
  if (!ROUND_CAPS[round]) throw new Error("--round must be 1 or 2.");
  const question = runQuestion(runDir);
  const raw: Candidate[] = readJson(join(runDir, `search-results.r${round}.json`));
  const seen = new Set<string>();
  if (round === 2) for (const u of readJson(join(runDir, "triage.r1.json")).selected) seen.add(normalizeUrl(u));
  const pool = raw.filter((c) => {
    const k = normalizeUrl(c.url);
    if (!c.url || seen.has(k)) return false;
    seen.add(k);
    return true;
  });
  const already = round === 1 ? 0 : fetchedFiles(runDir).length;
  const cap = Math.min(ROUND_CAPS[round], TOTAL_FETCHES - already);
  const { scores, meta } = await scoreStage(`triage.r${round}`, question, pool.map(triageText), decider, model);
  const { ranked, selected } = select(pool, scores, meta.selector, threshold, cap);
  const out = {
    round,
    question,
    selector: meta.selector,
    fallbackReason: meta.fallbackReason,
    threshold: meta.selector === "bm25" ? null : threshold,
    cap,
    selected: selected.map((r) => r.item.url),
    candidates: ranked.map((r) => ({ url: r.item.url, title: r.item.title ?? "", query: r.item.query ?? "", score: r.score })),
  };
  writeFileSync(join(runDir, `triage.r${round}.json`), `${JSON.stringify(out, null, 2)}\n`);
  recordStage(runDir, meta);
  return out;
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

async function main(argv: string[]) {
  const [cmd, runDir, ...rest] = argv;
  const flag = (name: string) => {
    const i = rest.indexOf(name);
    return i >= 0 ? rest[i + 1] : undefined;
  };
  if (!runDir || (cmd !== "triage" && cmd !== "passages")) {
    throw new Error("Usage: styrir-select.ts triage <run-dir> --round 1|2 [--threshold 0.5] | passages <run-dir> [--threshold 0.5] [--keep 40]");
  }
  const threshold = Number(flag("--threshold") ?? DEFAULT_THRESHOLD);
  const key: string | undefined = process.env.nanogpt;
  const model = { name: null as string | null };
  const decider = key ? nanoDecider(key, runQuestion(runDir), { onModel: (m) => (model.name = m) }) : null;
  const result =
    cmd === "triage"
      ? await triage(runDir, Number(flag("--round")), decider, threshold, model)
      : await passages(runDir, decider, threshold, Number(flag("--keep") ?? DEFAULT_KEEP), model);
  const n = "selected" in result ? `${result.selected.length} of ${result.candidates.length} candidates selected` : `${result.kept} of ${result.chunks.length} chunks kept`;
  console.log(`${cmd}: ${result.selector}${result.fallbackReason ? ` (fallback: ${result.fallbackReason})` : ""}; ${n}`);
}

if (import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2)).catch((e) => {
    console.error((e as Error).message);
    process.exit(1);
  });
}
