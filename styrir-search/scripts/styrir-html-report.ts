import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

type JsonRecord = Record<string, unknown>;

interface ReportSource {
  id: string;
  title: string;
  url: string;
  sourceType: string;
  fetched: boolean;
}

interface ReportEntry {
  id: string;
  observation: string;
  possibleImplication: string;
  sourceId: string;
  sourceUrl: string;
  sourceType: string;
  signalType: string;
  confidence: string;
  dateObserved: string;
}

interface ReportBundle {
  runDir: string;
  plan: JsonRecord;
  ledger: JsonRecord;
  sourceRegistry: JsonRecord;
  gateResult: JsonRecord;
  contradictionSweep: string;
  progressEvents: JsonRecord[];
}

function isRecord(value: unknown): value is JsonRecord {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function readOptionalJson(runDir: string, fileName: string): JsonRecord {
  const path = join(runDir, fileName);
  if (!existsSync(path)) {
    return {};
  }
  const parsed = JSON.parse(readFileSync(path, "utf8"));
  return isRecord(parsed) ? parsed : {};
}

function readRequiredJson(runDir: string, fileName: string): JsonRecord {
  const path = join(runDir, fileName);
  if (!existsSync(path)) {
    throw new Error(`${fileName} is required to render a Styrir HTML report.`);
  }
  const parsed = JSON.parse(readFileSync(path, "utf8"));
  if (!isRecord(parsed)) {
    throw new Error(`${fileName} must contain a JSON object.`);
  }
  return parsed;
}

function readOptionalText(runDir: string, fileName: string): string {
  const path = join(runDir, fileName);
  return existsSync(path) ? readFileSync(path, "utf8") : "";
}

function readProgressEvents(runDir: string): JsonRecord[] {
  const raw = readOptionalText(runDir, "progress.jsonl");
  if (!raw.trim()) {
    return [];
  }
  return raw
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      try {
        const parsed = JSON.parse(line);
        return isRecord(parsed) ? parsed : {};
      } catch {
        return { phase: "unparsed", message: line };
      }
    });
}

function asString(value: unknown, fallback = ""): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function asBoolean(value: unknown): boolean {
  return typeof value === "boolean" ? value : false;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function escapeHtml(value: unknown): string {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function titleCase(value: string): string {
  return value
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase())
    .trim();
}

function collectSources(bundle: ReportBundle): ReportSource[] {
  const registrySources = asArray(bundle.sourceRegistry.sources);
  const ledgerSources = asArray(bundle.ledger.sources);
  const sourceMap = new Map<string, ReportSource>();
  for (const raw of [...registrySources, ...ledgerSources]) {
    if (!isRecord(raw)) {
      continue;
    }
    const id = asString(raw.id);
    if (!id) {
      continue;
    }
    sourceMap.set(id, {
      id,
      title: asString(raw.title, id),
      url: asString(raw.url),
      sourceType: asString(raw.sourceType, "unknown"),
      fetched: asBoolean(raw.fetched),
    });
  }
  return [...sourceMap.values()].sort((left, right) => left.id.localeCompare(right.id));
}

function collectEntries(ledger: JsonRecord): ReportEntry[] {
  return asArray(ledger.entries)
    .filter(isRecord)
    .map((entry, index) => ({
      id: asString(entry.id, `e${index + 1}`),
      observation: asString(entry.observation),
      possibleImplication: asString(entry.possibleImplication),
      sourceId: asString(entry.sourceId),
      sourceUrl: asString(entry.sourceUrl),
      sourceType: asString(entry.sourceType, "unknown"),
      signalType: asString(entry.signalType, "evidence"),
      confidence: asString(entry.confidence, "unknown"),
      dateObserved: asString(entry.dateObserved),
    }));
}

function collectProofGaps(ledger: JsonRecord): JsonRecord[] {
  return asArray(ledger.proofGaps).filter(isRecord);
}

function metric(label: string, value: unknown): string {
  return `
    <div class="metric">
      <span>${escapeHtml(label)}</span>
      <strong>${escapeHtml(value)}</strong>
    </div>`;
}

function badge(value: string, tone = "neutral"): string {
  return `<span class="badge badge-${escapeHtml(tone)}">${escapeHtml(value)}</span>`;
}

function renderSourceLink(source: ReportSource): string {
  if (!source.url) {
    return `<span>${escapeHtml(source.title)}</span>`;
  }
  return `<a href="${escapeHtml(source.url)}" rel="noreferrer">${escapeHtml(source.title)}</a>`;
}

function renderMarkdownLite(markdown: string): string {
  if (!markdown.trim()) {
    return '<p class="muted">No contradiction sweep was included in this run bundle.</p>';
  }
  const lines = markdown.trim().split(/\r?\n/);
  const rendered: string[] = [];
  let inList = false;
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed) {
      if (inList) {
        rendered.push("</ul>");
        inList = false;
      }
      continue;
    }
    const heading = trimmed.match(/^(#{1,3})\s+(.+)$/);
    if (heading) {
      if (inList) {
        rendered.push("</ul>");
        inList = false;
      }
      const level = Math.min(heading[1].length + 2, 4);
      rendered.push(`<h${level}>${escapeHtml(heading[2])}</h${level}>`);
      continue;
    }
    const bullet = trimmed.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      if (!inList) {
        rendered.push("<ul>");
        inList = true;
      }
      rendered.push(`<li>${escapeHtml(bullet[1])}</li>`);
      continue;
    }
    if (inList) {
      rendered.push("</ul>");
      inList = false;
    }
    rendered.push(`<p>${escapeHtml(trimmed)}</p>`);
  }
  if (inList) {
    rendered.push("</ul>");
  }
  return rendered.join("\n");
}

function renderEvidence(entries: ReportEntry[], sourceMap: Map<string, ReportSource>): string {
  if (entries.length === 0) {
    return '<p class="muted">No evidence entries were found in ledger.json.</p>';
  }
  return entries
    .map((entry) => {
      const source = sourceMap.get(entry.sourceId);
      const sourceLabel = source ? renderSourceLink(source) : escapeHtml(entry.sourceId || "Unknown source");
      return `
        <article class="evidence-card">
          <div class="evidence-meta">
            ${badge(entry.signalType, "soft")}
            ${badge(entry.confidence, entry.confidence === "high" ? "success" : "neutral")}
            <span>${escapeHtml(entry.dateObserved || "undated")}</span>
          </div>
          <h3>${escapeHtml(entry.observation)}</h3>
          ${
            entry.possibleImplication
              ? `<p class="implication"><span>Implication</span>${escapeHtml(entry.possibleImplication)}</p>`
              : ""
          }
          <footer>
            <strong>${escapeHtml(entry.id)}</strong>
            <span>Source ${escapeHtml(entry.sourceId)} · ${sourceLabel}</span>
          </footer>
        </article>`;
    })
    .join("\n");
}

function renderSources(sources: ReportSource[]): string {
  if (sources.length === 0) {
    return '<p class="muted">No source registry was found.</p>';
  }
  return `
    <div class="source-list">
      ${sources
        .map(
          (source) => `
            <article class="source-row">
              <div>
                <strong>${escapeHtml(source.id)}</strong>
                ${badge(source.sourceType, "soft")}
                ${source.fetched ? badge("fetched", "success") : badge("unfetched", "warning")}
              </div>
              <p>${renderSourceLink(source)}</p>
            </article>`,
        )
        .join("\n")}
    </div>`;
}

function renderProofGaps(gaps: JsonRecord[]): string {
  if (gaps.length === 0) {
    return '<p class="muted">No proof gaps were recorded.</p>';
  }
  return gaps
    .map((gap) => {
      const attempted = asArray(gap.attemptedQueries).map((query) => `<li>${escapeHtml(query)}</li>`).join("");
      return `
        <article class="gap-row">
          <p>${escapeHtml(asString(gap.description, "Unspecified proof gap."))}</p>
          ${attempted ? `<ul>${attempted}</ul>` : ""}
        </article>`;
    })
    .join("\n");
}

function renderProgress(events: JsonRecord[]): string {
  if (events.length === 0) {
    return '<p class="muted">No progress trace was included.</p>';
  }
  return `
    <ol class="timeline">
      ${events
        .map(
          (event) => `
            <li>
              <span>${escapeHtml(asString(event.phase, "event"))}</span>
              <strong>${escapeHtml(asString(event.message, "No message"))}</strong>
              <time>${escapeHtml(asString(event.at))}</time>
            </li>`,
        )
        .join("\n")}
    </ol>`;
}

function renderStyles(): string {
  return `
    :root {
      color-scheme: dark;
      --background: #0e0f0c;
      --foreground: #f5f1e8;
      --card: #171812;
      --muted: #aaa18f;
      --muted-surface: #24261d;
      --border: #3a3a2f;
      --accent: #7dd3c7;
      --accent-foreground: #08110f;
      --warning: #f5b869;
      --success: #8bd6a4;
      --ring: #9be0d8;
      --radius: 8px;
    }
    * { box-sizing: border-box; }
    html { background: var(--background); color: var(--foreground); }
    body {
      margin: 0;
      font-family: Georgia, "Iowan Old Style", "New York", serif;
      line-height: 1.55;
      color: var(--foreground);
      background:
        linear-gradient(90deg, rgba(125, 211, 199, 0.12), transparent 20rem),
        linear-gradient(180deg, rgba(245, 184, 105, 0.08), transparent 16rem),
        var(--background);
    }
    a { color: var(--accent); text-decoration-thickness: 0.08em; text-underline-offset: 0.18em; }
    .report-shell { max-width: 1180px; margin: 0 auto; padding: 32px 28px 72px; }
    .topbar {
      display: flex;
      justify-content: space-between;
      align-items: center;
      gap: 16px;
      margin-bottom: 32px;
      font-family: "Avenir Next", "DIN Condensed", "Trebuchet MS", sans-serif;
    }
    .brand { display: flex; align-items: center; gap: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0; }
    .mark { width: 34px; height: 34px; border: 1px solid var(--foreground); display: grid; place-items: center; border-radius: 6px; }
    .button {
      appearance: none;
      border: 1px solid var(--border);
      background: var(--card);
      color: var(--foreground);
      border-radius: 7px;
      padding: 9px 12px;
      font: inherit;
      cursor: pointer;
    }
    .button:focus-visible { outline: 3px solid var(--ring); outline-offset: 2px; }
    header.hero {
      display: grid;
      grid-template-columns: minmax(0, 1fr) 280px;
      gap: 28px;
      align-items: end;
      padding-bottom: 30px;
      border-bottom: 1px solid var(--border);
    }
    .eyebrow {
      font-family: "Avenir Next", "DIN Condensed", "Trebuchet MS", sans-serif;
      color: var(--accent);
      text-transform: uppercase;
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0;
    }
    h1 {
      margin: 8px 0 12px;
      max-width: 15ch;
      font-size: clamp(2.4rem, 7vw, 5.75rem);
      line-height: 0.95;
      letter-spacing: 0;
    }
    .subtitle { max-width: 62ch; color: var(--muted); font-size: 1.08rem; }
    .metrics {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 10px;
    }
    .metric {
      min-height: 82px;
      border: 1px solid var(--border);
      background: rgba(23, 24, 18, 0.82);
      border-radius: var(--radius);
      padding: 14px;
    }
    .metric span {
      display: block;
      color: var(--muted);
      font-family: "Avenir Next", "DIN Condensed", "Trebuchet MS", sans-serif;
      font-size: 0.77rem;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .metric strong { display: block; margin-top: 8px; font-size: 1.45rem; line-height: 1.1; }
    main { display: grid; grid-template-columns: 220px minmax(0, 1fr); gap: 36px; margin-top: 34px; }
    nav.toc {
      position: sticky;
      top: 18px;
      align-self: start;
      padding: 14px 0;
      font-family: "Avenir Next", "DIN Condensed", "Trebuchet MS", sans-serif;
    }
    nav.toc a { display: block; padding: 8px 0; color: var(--muted); text-decoration: none; }
    nav.toc a:hover { color: var(--foreground); }
    section.report-section { padding: 0 0 34px; margin-bottom: 34px; border-bottom: 1px solid var(--border); }
    h2 {
      margin: 0 0 14px;
      font-size: 1.55rem;
      line-height: 1.12;
      letter-spacing: 0;
    }
    h3 { margin: 8px 0 10px; font-size: 1.06rem; line-height: 1.35; letter-spacing: 0; }
    .section-kicker {
      margin: 0 0 18px;
      color: var(--muted);
      max-width: 70ch;
    }
    .evidence-grid { display: grid; gap: 14px; }
    .evidence-card,
    .source-row,
    .gap-row,
    .gate-panel {
      background: var(--card);
      border: 1px solid var(--border);
      border-radius: var(--radius);
      padding: 16px;
      box-shadow: 0 18px 42px rgba(0, 0, 0, 0.22);
    }
    .evidence-meta, .source-row > div, .gate-line {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      align-items: center;
      color: var(--muted);
      font-family: "Avenir Next", "DIN Condensed", "Trebuchet MS", sans-serif;
      font-size: 0.84rem;
    }
    .badge {
      display: inline-flex;
      align-items: center;
      min-height: 24px;
      padding: 2px 8px;
      border: 1px solid var(--border);
      border-radius: 999px;
      background: var(--muted-surface);
      color: var(--foreground);
      font-family: "Avenir Next", "DIN Condensed", "Trebuchet MS", sans-serif;
      font-size: 0.76rem;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .badge-success { background: rgba(139, 214, 164, 0.12); color: var(--success); border-color: rgba(139, 214, 164, 0.34); }
    .badge-warning { background: rgba(245, 184, 105, 0.12); color: var(--warning); border-color: rgba(245, 184, 105, 0.34); }
    .badge-soft { background: rgba(125, 211, 199, 0.11); color: var(--accent); border-color: rgba(125, 211, 199, 0.32); }
    .implication {
      margin: 12px 0 0;
      padding-left: 12px;
      border-left: 3px solid var(--accent);
      color: var(--muted);
    }
    .implication span {
      display: block;
      font-family: "Avenir Next", "DIN Condensed", "Trebuchet MS", sans-serif;
      font-size: 0.76rem;
      font-weight: 800;
      color: var(--accent);
      text-transform: uppercase;
      letter-spacing: 0;
    }
    .evidence-card footer {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
      padding-top: 12px;
      border-top: 1px solid var(--border);
      color: var(--muted);
      font-size: 0.9rem;
    }
    .source-list { display: grid; gap: 10px; }
    .source-row p { margin: 8px 0 0; word-break: break-word; }
    .gap-row + .gap-row { margin-top: 10px; }
    .gap-row p { margin: 0 0 8px; }
    .timeline {
      list-style: none;
      display: grid;
      gap: 10px;
      padding: 0;
      margin: 0;
      counter-reset: progress;
    }
    .timeline li {
      counter-increment: progress;
      display: grid;
      grid-template-columns: 120px minmax(0, 1fr) auto;
      gap: 12px;
      align-items: baseline;
      padding: 11px 0;
      border-bottom: 1px solid var(--border);
    }
    .timeline span {
      color: var(--accent);
      font-family: "Avenir Next", "DIN Condensed", "Trebuchet MS", sans-serif;
      font-weight: 800;
      text-transform: uppercase;
      font-size: 0.78rem;
    }
    .timeline time { color: var(--muted); font-size: 0.85rem; }
    .muted { color: var(--muted); }
    .markdown-body p { margin: 0 0 10px; }
    .markdown-body h3, .markdown-body h4 { margin: 18px 0 8px; }
    footer.report-footer {
      color: var(--muted);
      font-size: 0.86rem;
      margin-top: 34px;
      padding-top: 18px;
      border-top: 1px solid var(--border);
    }
    @media (max-width: 840px) {
      .report-shell { padding: 22px 18px 52px; }
      header.hero { grid-template-columns: 1fr; }
      main { grid-template-columns: 1fr; }
      nav.toc { position: static; display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 0 16px; }
      .metrics { grid-template-columns: 1fr; }
      .timeline li { grid-template-columns: 1fr; gap: 2px; }
    }
    /* Print stylesheet */
    @page { margin: 0.65in; }
    @media print {
      :root { --background: #ffffff; --card: #ffffff; --foreground: #000000; --muted: #4b4b4b; --border: #c8c8c8; }
      body { background: #ffffff; }
      .report-shell { max-width: none; padding: 0; }
      .topbar, nav.toc, .button { display: none !important; }
      header.hero { grid-template-columns: 1fr; break-after: avoid; }
      main { display: block; }
      section.report-section { break-inside: avoid; page-break-inside: avoid; }
      .evidence-card, .source-row, .gap-row, .gate-panel { box-shadow: none; break-inside: avoid; }
      a::after { content: " (" attr(href) ")"; font-size: 0.82em; color: var(--muted); word-break: break-all; }
    }
  `;
}

function readBundle(runDir: string): ReportBundle {
  return {
    runDir,
    plan: readOptionalJson(runDir, "plan.json"),
    ledger: readRequiredJson(runDir, "ledger.json"),
    sourceRegistry: readOptionalJson(runDir, "source-registry.json"),
    gateResult: readOptionalJson(runDir, "gate-result.json"),
    contradictionSweep: readOptionalText(runDir, "contradiction-sweep.md"),
    progressEvents: readProgressEvents(runDir),
  };
}

export function renderHtmlReport(runDir: string): string {
  const bundle = readBundle(runDir);
  const entries = collectEntries(bundle.ledger);
  const sources = collectSources(bundle);
  const sourceMap = new Map(sources.map((source) => [source.id, source]));
  const proofGaps = collectProofGaps(bundle.ledger);
  const meta = isRecord(bundle.ledger.meta) ? bundle.ledger.meta : {};
  const title = asString(bundle.plan.question, asString(meta.question, "Styrir Search Report"));
  const objective = asString(bundle.plan.objective, "Human-readable rendering of the data-backed Styrir evidence bundle.");
  const mode = asString(bundle.plan.mode, asString(meta.mode, "styrir_search"));
  const gateStatus = asString(bundle.gateResult.gateStatus, "unknown");
  const generatedAt = new Date().toISOString();

  return `<!doctype html>
<html lang="en" data-styrir-report>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>${escapeHtml(title)} · Styrir Search Report</title>
  <style>${renderStyles()}</style>
</head>
<body>
  <div class="report-shell">
    <div class="topbar" aria-label="Report controls">
      <div class="brand"><span class="mark">S</span><span>Styrir Search</span></div>
      <button class="button" type="button" data-print>Print</button>
    </div>

    <header class="hero">
      <div>
        <p class="eyebrow">Data-backed search report</p>
        <h1>${escapeHtml(title)}</h1>
        <p class="subtitle">${escapeHtml(objective)}</p>
        <p>${badge(titleCase(mode), "soft")} ${badge(gateStatus === "pass" ? "Gate passed" : `Gate ${gateStatus}`, gateStatus === "pass" ? "success" : "warning")}</p>
      </div>
      <aside class="metrics" aria-label="Run metrics">
        ${metric("Evidence entries", entries.length)}
        ${metric("Sources", sources.length)}
        ${metric("Proof gaps", proofGaps.length)}
        ${metric("Generated", generatedAt.slice(0, 10))}
      </aside>
    </header>

    <main>
      <nav class="toc" aria-label="Sections">
        <a href="#evidence">Evidence Ledger</a>
        <a href="#sources">Source Registry</a>
        <a href="#gaps">Proof Gaps</a>
        <a href="#sweep">Contradiction Sweep</a>
        <a href="#gate">Gate Result</a>
        <a href="#progress">Progress Trace</a>
      </nav>

      <div>
        <section class="report-section" id="evidence">
          <h2>Evidence Ledger</h2>
          <p class="section-kicker">Atomic observations from ledger.json. Interpretation stays in implication fields so the report remains traceable back to source-backed data.</p>
          <div class="evidence-grid">${renderEvidence(entries, sourceMap)}</div>
        </section>

        <section class="report-section" id="sources">
          <h2>Source Registry</h2>
          <p class="section-kicker">Fetched source inventory used by the agent-readable ledger and this human report.</p>
          ${renderSources(sources)}
        </section>

        <section class="report-section" id="gaps">
          <h2>Proof Gaps</h2>
          <p class="section-kicker">Known limits and follow-up queries recorded before synthesis.</p>
          ${renderProofGaps(proofGaps)}
        </section>

        <section class="report-section" id="sweep">
          <h2>Contradiction Sweep</h2>
          <div class="markdown-body">${renderMarkdownLite(bundle.contradictionSweep)}</div>
        </section>

        <section class="report-section" id="gate">
          <h2>Gate Result</h2>
          <div class="gate-panel">
            <p class="gate-line">${badge(gateStatus === "pass" ? "Gate passed" : `Gate ${gateStatus}`, gateStatus === "pass" ? "success" : "warning")} <span>ledgerSha256: ${escapeHtml(asString(bundle.gateResult.ledgerSha256, "not recorded"))}</span></p>
          </div>
        </section>

        <section class="report-section" id="progress">
          <h2>Progress Trace</h2>
          ${renderProgress(bundle.progressEvents)}
        </section>
      </div>
    </main>

    <footer class="report-footer">
      This HTML is a derivative view. The authoritative artifact remains the agent-readable Styrir run bundle, especially ledger.json and gate-result.json.
    </footer>
  </div>
  <script>
    document.querySelector("[data-print]")?.addEventListener("click", () => window.print());
  </script>
</body>
</html>
`;
}

export function writeHtmlReport(runDir: string, outputPath = join(runDir, "report.html")): string {
  writeFileSync(outputPath, renderHtmlReport(runDir));
  return outputPath;
}

function main(argv: string[]) {
  const runDir = argv[2];
  if (!runDir) {
    throw new Error("Usage: styrir-html-report.ts <run-dir> [output.html]");
  }
  const outputPath = writeHtmlReport(runDir, argv[3]);
  process.stdout.write(`${outputPath}\n`);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    main(process.argv);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown HTML report error.";
    process.stderr.write(`${message}\n`);
    process.exitCode = 1;
  }
}
