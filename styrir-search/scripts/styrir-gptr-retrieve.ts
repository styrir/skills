import { spawn } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

// GPT Researcher deep mode as a source-discovery component, for qualification only; no route selects it.
// It finds sources; it never writes evidence. See references/gpt-researcher-retrieval.md.

// Settings the 2026-11-01 bake-off qualified (GPT Researcher 0.16.0 / v3.7.0).
export const GPTR_SETTINGS: Record<string, string> = {
  OPENAI_BASE_URL: "https://api.nano-gpt.com/api/v1",
  STRATEGIC_LLM: "openai:openai/gpt-6.1-sol",
  SMART_LLM: "openai:openai/gpt-6.1-terra",
  FAST_LLM: "openai:openai/gpt-6-luna",
  EMBEDDING: "custom:text-embedding-3-small",
  RETRIEVER: "tavily",
  CONTEXT_FILTER: "keyword",
  DEEP_RESEARCH_BREADTH: "4",
  DEEP_RESEARCH_DEPTH: "2",
  DEEP_RESEARCH_CONCURRENCY: "4",
};

export const DEFAULT_SPEND_CAP_USD = 1;
// "Primary" as the bake-off measured it; ranked ahead of everything else.
export const PRIMARY_TYPES = new Set(["legal", "official", "academic"]);

const RULES: Array<[string[], string]> = [
  [["learn.microsoft.com/en-us/answers", "stackoverflow.com", "community."], "social"],
  [["docs.github.com", "github.com/cloudevents/spec", "cloudevents.io"], "official"],
  [["uscourts.gov", "courtlistener.com", "govinfo.gov", "justia.com/cases", "caselaw.findlaw.com"], "legal"],
  [["copyright.gov", "wipo.int", "developer.apple.com", "w3.org", "whatwg.org", "ietf.org", "a2a-protocol.org",
    "modelcontextprotocol.io", "opentelemetry.io", "learn.microsoft.com", "docs.anthropic.com", "platform.openai.com",
    "khronos.org"], "official"],
  [["slsa.dev", "cdevents.dev", "fidoalliance.org", "web.dev", "mlflow.org"], "official"],
  [["arxiv.org", "acm.org", "ieee.org", "lawreview", "ssrn.com"], "academic"],
  [["github.com", "gitlab.com"], "repo"],
  [["linkedin.com", "reddit.com", "youtube.com", "facebook.com", "x.com", "twitter.com", "news.ycombinator.com",
    "medium.com", "substack.com"], "social"],
  [["reuters.com", "bloomberglaw.com", "courthousenews.com", "theverge.com", "techcrunch.com", "arstechnica.com",
    "deadline.com", "ipwatchdog.com", "niemanlab.org"], "news"],
];

function host(url: string): string {
  try {
    return new URL(url).hostname.toLowerCase().replace(/^www\./, "");
  } catch {
    return "";
  }
}

// Domain-rule typing (ported from the bake-off's classify.py); emits the gate's sourceType vocabulary.
export function classifySource(url: string): string {
  const u = url.toLowerCase();
  const h = host(u);
  for (const [needles, kind] of RULES) {
    // Dotted host needles match the host or a subdomain; path or dotless needles match anywhere in the URL.
    if (needles.some((n) => (/^[a-z0-9-]+\.[a-z.]+$/.test(n) ? h === n || h.endsWith(`.${n}`) : u.includes(n)))) {
      return kind;
    }
  }
  if (/\.(gov|mil)$/.test(h) || /\.gov\.[a-z]{2}$/.test(h) || /^(docs|developer|developers|spec)\./.test(h)) {
    return "official";
  }
  if (h.endsWith(".edu") || h.includes("journal")) {
    return "academic";
  }
  if (h === "patents.google.com") {
    return "legal";
  }
  return "analysis";
}

export type Verdict = "relevant" | "off_topic" | "unknown";

// One page, one bounded judgment. Only the question and the re-fetched page enter the prompt;
// GPT Researcher's report and context never exist in this pipeline.
export function judgePrompt(question: string, objective: string | undefined, page: { url: string; title: string; text: string }) {
  return [
    "Is this web page on-topic for the research question? A page is on-topic if it could supply evidence for any",
    "part of the question, including tangential background or sub-topics a researcher would reasonably search",
    "(platform docs, implementation techniques, related tooling). It is off-topic only if it merely shares a word",
    "with the question (wrong sense, unrelated product, dictionary entry, generic marketing or tool landing page).",
    'When unsure, answer "relevant". Answer with exactly one word: "relevant" or "off_topic".',
    "",
    `Question: ${question}`,
    ...(objective ? [`Objective: ${objective}`] : []),
    "",
    `URL: ${page.url}`,
    `Title: ${page.title}`,
    `Page text (start): ${page.text.slice(0, 1500)}`,
  ].join("\n");
}

export function parseVerdict(reply: string): Verdict {
  const word = reply.trim().toLowerCase().replace(/[^a-z_]/g, " ").split(/\s+/).find(Boolean) ?? "";
  return word === "relevant" ? "relevant" : word === "off_topic" || word === "off" ? "off_topic" : "unknown";
}

// Fail-safe on keep: a failed or unparseable judgment is "unknown", never a drop.
export async function judgeRelevance(prompt: string, call: (prompt: string) => Promise<string>): Promise<Verdict> {
  try {
    return parseVerdict(await call(prompt));
  } catch {
    return "unknown";
  }
}

async function pool<T, R>(items: T[], size: number, fn: (item: T) => Promise<R>): Promise<R[]> {
  const out: R[] = new Array(items.length);
  let next = 0;
  const worker = async () => {
    while (next < items.length) {
      const i = next++;
      out[i] = await fn(items[i]);
    }
  };
  await Promise.all(Array.from({ length: Math.min(size, items.length) }, worker));
  return out;
}

export const JUDGE_MODEL = "openai/gpt-6-luna";

export function nanoJudge(key: string) {
  return async (prompt: string) => {
    const res = await fetch(`${GPTR_SETTINGS.OPENAI_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
      body: JSON.stringify({ model: JUDGE_MODEL, temperature: 0, max_tokens: 512, messages: [{ role: "user", content: prompt }] }),
    });
    if (!res.ok) {
      throw new Error(`HTTP ${res.status}`);
    }
    const body = await res.json();
    return String(body.choices?.[0]?.message?.content ?? "");
  };
}

export type FetchStatus = "ok" | "empty" | "failed" | "error" | "missing";

export interface SourceRow {
  url: string;
  title: string;
  fetchStatus: FetchStatus;
  verdict: Verdict | null;
  textFile?: string;
}

export interface Candidate {
  id: string;
  rank: number;
  url: string;
  title: string;
  sourceType: string;
  primary: boolean;
  fetched: true;
  fetchStatus: "ok";
  verdict: Verdict;
  textFile?: string;
}

export interface Dropped {
  url: string;
  title: string;
  sourceType: string;
  reason: "dead" | "off_topic";
  fetchStatus: FetchStatus;
  verdict: Verdict | null;
}

// Dead and judged-off-topic sources go to dropped[] (kept for audit and rescue); the rest rank primary first,
// then in GPT Researcher's original order. Primary sources are never dropped as off-topic: losing an official page
// costs more than reading a tangential one, so a primary off_topic verdict only sorts it last among primaries.
export function rankCandidates(rows: SourceRow[]) {
  const dropped: Dropped[] = [];
  const kept: Array<SourceRow & { sourceType: string; primary: boolean; order: number }> = [];
  rows.forEach((row, order) => {
    const sourceType = classifySource(row.url);
    const primary = PRIMARY_TYPES.has(sourceType);
    const reason = row.fetchStatus !== "ok" ? "dead" : row.verdict === "off_topic" && !primary ? "off_topic" : null;
    if (reason) {
      dropped.push({ url: row.url, title: row.title, sourceType, reason, fetchStatus: row.fetchStatus, verdict: row.verdict });
    } else {
      kept.push({ ...row, sourceType, primary, order });
    }
  });
  const tier = (r: { primary: boolean; verdict: Verdict | null }) => (r.primary ? (r.verdict === "off_topic" ? 1 : 0) : 2);
  kept.sort((a, b) => tier(a) - tier(b) || a.order - b.order);
  const candidates: Candidate[] = kept.map((row, i) => ({
    id: `s${i + 1}`,
    rank: i + 1,
    url: row.url,
    title: row.title,
    sourceType: row.sourceType,
    primary: row.primary,
    fetched: true,
    fetchStatus: "ok",
    verdict: row.verdict ?? "unknown",
    ...(row.textFile ? { textFile: row.textFile } : {}),
  }));
  return { candidates, dropped };
}

export function assessSpend(balances: { before: number; afterGptr: number; afterJudge: number }, capUsd: number) {
  const usd = (n: number) => Math.round(n * 10000) / 10000;
  const costUsd = usd(balances.before - balances.afterJudge);
  return {
    balanceBeforeUsd: balances.before,
    balanceAfterUsd: balances.afterJudge,
    gptrCostUsd: usd(balances.before - balances.afterGptr),
    judgeCostUsd: usd(balances.afterGptr - balances.afterJudge),
    costUsd,
    capUsd,
    overCap: costUsd > capUsd,
  };
}

// Tavily bills both the searches inside GPT Researcher and the adapter's own extract calls, so both are counted.
// Readings are per key: other use of the same key during a run is counted too.
export const TAVILY_PAYGO_USD_PER_CREDIT = 0.008;

export interface TavilyReading {
  usage: number;
  search: number;
  extract: number;
}

export function tavilyCredits(before: TavilyReading | null, after: TavilyReading | null) {
  if (!before || !after) {
    return { measured: false, totalCredits: null, searchCredits: null, extractCredits: null, paygoEstimateUsd: null };
  }
  const totalCredits = after.usage - before.usage;
  return {
    measured: true,
    totalCredits,
    searchCredits: after.search - before.search,
    extractCredits: after.extract - before.extract,
    paygoEstimateUsd: Math.round(totalCredits * TAVILY_PAYGO_USD_PER_CREDIT * 10000) / 10000,
  };
}

async function tavilyUsage(key: string): Promise<TavilyReading | null> {
  try {
    const res = await fetch("https://api.tavily.com/usage", { headers: { Authorization: `Bearer ${key}` } });
    const k = (await res.json()).key ?? {};
    const reading = { usage: Number(k.usage), search: Number(k.search_usage), extract: Number(k.extract_usage) };
    return res.ok && Object.values(reading).every(Number.isFinite) ? reading : null;
  } catch {
    return null;
  }
}

export const SELECTION_RULES = [
  "dead: the adapter's own Tavily extract returned no text, a failure, or under 200 characters; dropped.",
  "off_topic: the NanoGPT judge answered off_topic; dropped unless the source type is primary (legal, official, academic).",
  "unknown: the judge failed or answered unparseably; kept.",
  "rank: primary on-topic first, then primary judged off_topic, then the rest; ties keep GPT Researcher's order.",
];

// Every returned URL, in the styrir_plus registry shape, with its selection decision. Candidates keep their s<n>
// ids; dropped sources get x<n>, so a reviewer can audit every decision against the ledger.
export function sourceRegistry(candidates: Candidate[], dropped: Dropped[]) {
  return {
    sources: [
      ...candidates.map((c) => ({ id: c.id, url: c.url, title: c.title, sourceType: c.sourceType, fetched: true, selection: "candidate", verdict: c.verdict })),
      ...dropped.map((d, i) => ({ id: `x${i + 1}`, url: d.url, title: d.title, sourceType: d.sourceType, fetched: d.fetchStatus === "ok", selection: d.reason, verdict: d.verdict })),
    ],
  };
}

// Keys come only from Infisical (styrir / prod / /providers), which injects them as `nanogpt` and `tavily`.
// Ambient OPENAI_API_KEY / TAVILY_API_KEY are never read, so a stray shell key can't be billed.
export function providerKeys(env: Record<string, string | undefined>) {
  const nanogpt = env.nanogpt;
  const tavily = env.tavily;
  if (!nanogpt || !tavily) {
    throw new Error(
      "Missing provider keys. Run under Infisical: npm run gptr-retrieve -- <request.json> <run-dir> " +
        "(injects nanogpt and tavily from styrir/prod/providers).",
    );
  }
  return { nanogpt, tavily };
}

// Allowlisted: other Infisical secrets in the parent environment never reach GPT Researcher.
export function childEnv(env: Record<string, string | undefined>, keys: { nanogpt: string; tavily: string }): Record<string, string> {
  const out: Record<string, string> = {};
  for (const k of ["PATH", "HOME", "LANG", "TMPDIR", "VIRTUAL_ENV"]) {
    const v = env[k];
    if (v !== undefined) {
      out[k] = v;
    }
  }
  return { ...out, ...GPTR_SETTINGS, OPENAI_API_KEY: keys.nanogpt, TAVILY_API_KEY: keys.tavily };
}

async function nanoBalance(key: string) {
  const res = await fetch("https://nano-gpt.com/api/check-balance", {
    method: "POST",
    headers: { "x-api-key": key, "Content-Type": "application/json" },
  });
  const body = await res.json();
  const usd = Number(body.usd_balance);
  if (!res.ok || !Number.isFinite(usd)) {
    throw new Error(`NanoGPT balance check failed (HTTP ${res.status}).`);
  }
  return { usd, pendingUsage: body.usd_pending_usage ?? null };
}

export async function refetch(urls: string[], key: string, runDir: string) {
  const status = new Map<string, { fetchStatus: FetchStatus; textFile?: string; head: string }>();
  mkdirSync(join(runDir, "fetched"), { recursive: true });
  for (let i = 0; i < urls.length; i += 20) {
    const batch = urls.slice(i, i + 20);
    try {
      const res = await fetch("https://api.tavily.com/extract", {
        method: "POST",
        headers: { Authorization: `Bearer ${key}`, "Content-Type": "application/json" },
        body: JSON.stringify({ urls: batch, format: "text" }),
      });
      if (!res.ok) {
        throw new Error(`HTTP ${res.status}`);
      }
      const body = await res.json();
      for (const r of body.results ?? []) {
        const n = urls.indexOf(r.url);
        const text: string = r.raw_content ?? "";
        if (n < 0) {
          continue;
        }
        const textFile = `fetched/${String(n).padStart(3, "0")}.txt`;
        writeFileSync(join(runDir, textFile), `URL: ${r.url}\n\n${text}`);
        status.set(r.url, { fetchStatus: text.length > 200 ? "ok" : "empty", textFile, head: text.slice(0, 1500) });
      }
      for (const f of body.failed_results ?? []) {
        status.set(f.url, { fetchStatus: "failed", head: "" });
      }
    } catch {
      for (const u of batch) {
        status.set(u, { fetchStatus: "error", head: "" });
      }
    }
  }
  return status;
}

function runShim(python: string, question: string, rawPath: string, env: Record<string, string>) {
  const shim = join(dirname(fileURLToPath(import.meta.url)), "gptr_deep_sources.py");
  // GPT Researcher's own logs go to our stderr; stdout stays free for the result line.
  return spawn(python, ["-I", shim, question, rawPath], { env, stdio: ["ignore", 2, 2] });
}

export function parseArgs(argv: string[], env: Record<string, string | undefined>) {
  const [requestPath, runDir, ...rest] = argv;
  if (!requestPath || !runDir) {
    throw new Error("Usage: styrir-gptr-retrieve.ts <request.json> <run-dir> [--cap-usd 1] [--python <path>]");
  }
  const flag = (name: string) => {
    const i = rest.indexOf(name);
    return i >= 0 ? rest[i + 1] : undefined;
  };
  const capUsd = Number(flag("--cap-usd") ?? DEFAULT_SPEND_CAP_USD);
  if (!(capUsd > 0)) {
    throw new Error("--cap-usd must be a positive number.");
  }
  return { requestPath, runDir, capUsd, python: flag("--python") ?? env.GPTR_PYTHON ?? "python3" };
}

async function main(argv: string[]) {
  const args = parseArgs(argv, process.env);
  const keys = providerKeys(process.env);
  const request = JSON.parse(readFileSync(args.requestPath, "utf8"));
  const question: string = request.question;
  if (!question) {
    throw new Error("Request question is required.");
  }
  mkdirSync(args.runDir, { recursive: true });
  const started = Date.now();
  const seconds = (from: number) => Math.round((Date.now() - from) / 1000);
  const tavilyBefore = await tavilyUsage(keys.tavily);
  const before = await nanoBalance(keys.nanogpt);
  if (before.usd < args.capUsd) {
    throw new Error(`NanoGPT balance $${before.usd} is below the $${args.capUsd} spend cap; refusing to start.`);
  }

  // The cap is enforced by polling the provider balance during the GPT Researcher phase. Reported usage can lag,
  // so a run can overshoot by up to one poll interval of spend; the final reading still flags overCap.
  const rawPath = join(args.runDir, "gptr-sources.raw.json");
  const child = runShim(args.python, question, rawPath, childEnv(process.env, keys));
  let capHit = false;
  let polling = false;
  const poll = setInterval(async () => {
    if (polling) {
      return;
    }
    polling = true;
    try {
      if (before.usd - (await nanoBalance(keys.nanogpt)).usd >= args.capUsd) {
        capHit = true;
        child.kill("SIGTERM");
      }
    } catch {
      // A failed poll is not a reason to kill the run; the final reading still decides overCap.
    } finally {
      polling = false;
    }
  }, 20000);
  const exitCode: number | null = await new Promise((resolve) => {
    child.on("exit", (code: number | null) => resolve(code));
    child.on("error", () => resolve(-1));
  });
  clearInterval(poll);
  const afterGptr = await nanoBalance(keys.nanogpt);
  const phases: Record<string, number> = { gptrSeconds: seconds(started) };
  const manifest: Record<string, unknown> = {
    backend: "gpt_researcher_deep",
    question,
    objective: request.objective ?? null,
    settings: GPTR_SETTINGS,
    judgeModel: JUDGE_MODEL,
  };
  const writeManifest = async (status: string, spend: object) => {
    const tavily = tavilyCredits(tavilyBefore, await tavilyUsage(keys.tavily));
    const adapterMinutes = Math.round(seconds(started) / 6) / 10;
    writeFileSync(
      join(args.runDir, "retrieval-manifest.json"),
      `${JSON.stringify({
        status,
        ...manifest,
        spend: { nanogpt: spend, tavily },
        effort: {
          ...phases,
          adapterMinutes,
          // Filled in by whoever writes the ledger; qualification needs adapter plus ledger-writing time.
          ledgerWritingMinutes: null,
        },
      }, null, 2)}\n`,
    );
  };

  if (capHit || exitCode !== 0) {
    await writeManifest(capHit ? "aborted_spend_cap" : "gptr_failed", { ...assessSpend({ before: before.usd, afterGptr: afterGptr.usd, afterJudge: afterGptr.usd }, args.capUsd), capHit });
    throw new Error(capHit ? "Spend cap reached; GPT Researcher run was stopped." : `GPT Researcher exited with ${exitCode}.`);
  }

  const raw = JSON.parse(readFileSync(rawPath, "utf8"));
  const titles = new Map<string, string>();
  for (const s of raw.sources) {
    if (!titles.has(s.url)) {
      titles.set(s.url, s.title ?? "");
    }
  }
  const urls = [...titles.keys()];
  let mark = Date.now();
  const fetched = await refetch(urls, keys.tavily, args.runDir);
  phases.refetchSeconds = seconds(mark);
  mark = Date.now();
  const judge = nanoJudge(keys.nanogpt);
  const rows: SourceRow[] = await pool(urls, 8, async (url) => {
    const f = fetched.get(url) ?? { fetchStatus: "missing" as FetchStatus, head: "" };
    const title = titles.get(url) ?? "";
    const verdict = f.fetchStatus === "ok"
      ? await judgeRelevance(judgePrompt(question, request.objective, { url, title, text: f.head }), judge)
      : null;
    return { url, title, fetchStatus: f.fetchStatus, verdict, ...(f.textFile ? { textFile: f.textFile } : {}) };
  });
  phases.judgeSeconds = seconds(mark);
  const afterJudge = await nanoBalance(keys.nanogpt);
  const spend = {
    ...assessSpend({ before: before.usd, afterGptr: afterGptr.usd, afterJudge: afterJudge.usd }, args.capUsd),
    capHit,
    pendingUsageAfter: afterJudge.pendingUsage,
  };
  const { candidates, dropped } = rankCandidates(rows);
  writeFileSync(
    join(args.runDir, "candidate-sources.json"),
    `${JSON.stringify({ question, selectionRules: SELECTION_RULES, candidates, dropped }, null, 2)}\n`,
  );
  writeFileSync(join(args.runDir, "source-registry.json"), `${JSON.stringify(sourceRegistry(candidates, dropped), null, 2)}\n`);
  const counts = {
    returned: urls.length,
    dead: dropped.filter((d) => d.reason === "dead").length,
    offTopic: dropped.filter((d) => d.reason === "off_topic").length,
    unjudged: candidates.filter((c) => c.verdict === "unknown").length,
    candidates: candidates.length,
    primary: candidates.filter((c) => c.primary).length,
  };
  Object.assign(manifest, { gptResearcher: raw.gpt_researcher, gptrCostEstimateUsd: raw.gptr_cost_estimate_usd, counts });
  const status = spend.overCap ? "complete_over_cap" : "complete";
  await writeManifest(status, spend);
  process.stdout.write(`${JSON.stringify({ status, ...counts, costUsd: spend.costUsd })}\n`);
  if (spend.overCap) {
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv.slice(2)).catch((error) => {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  });
}
