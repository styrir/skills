import assert from "node:assert/strict";
import { existsSync, mkdtempSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { renderHtmlReport, writeHtmlReport } from "./styrir-html-report.ts";

function writeJson(path: string, value: unknown) {
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`);
}

function makeRunDir(): string {
  const dir = mkdtempSync(join(tmpdir(), "styrir-html-report-"));
  writeJson(join(dir, "plan.json"), {
    mode: "styrir_plus",
    question: "Best methodologies for layered AI-agent search",
    objective: "Dogfood Styrir Plus and produce a readable brief",
    outputs: { htmlReport: true },
    facets: ["methodology", "cost controls", "contradiction sweep"],
  });
  writeJson(join(dir, "source-registry.json"), {
    sources: [
      {
        id: "s1",
        title: "Official retrieval guidance",
        url: "https://example.com/retrieval",
        sourceType: "official",
        fetched: true,
      },
    ],
  });
  writeJson(join(dir, "ledger.json"), {
    meta: {
      mode: "styrir_plus",
      budget: { maxSearchQueries: 10, maxFetches: 10 },
      totalQueriesRun: 3,
      totalSourcesFetched: 1,
    },
    sources: [
      {
        id: "s1",
        title: "Official retrieval guidance",
        url: "https://example.com/retrieval",
        sourceType: "official",
        fetched: true,
      },
    ],
    entries: [
      {
        id: "e1",
        observation: "Layered search works best when routing, source capture, and synthesis are separate steps.",
        possibleImplication: "The cheap lane can stay useful if it records why a result was trusted before synthesis.",
        sourceId: "s1",
        sourceUrl: "https://example.com/retrieval",
        sourceType: "official",
        signalType: "methodology",
        confidence: "high",
        dateObserved: "2026-07-03",
      },
      {
        id: "e2",
        observation: "Escaped user content <script>alert('x')</script> must render as text, not executable markup.",
        possibleImplication: "The report renderer should escape all ledger-sourced prose.",
        sourceId: "s1",
        sourceUrl: "https://example.com/retrieval",
        sourceType: "official",
        signalType: "safety",
        confidence: "medium",
        dateObserved: "2026-07-03",
      },
    ],
    proofGaps: [
      {
        description: "No paid deep-research result was run for comparison.",
        attemptedQueries: ["deep research cost comparison"],
      },
    ],
  });
  writeJson(join(dir, "gate-result.json"), { gateStatus: "pass", ledgerSha256: "abc123" });
  writeFileSync(join(dir, "contradiction-sweep.md"), "# Contradiction Sweep\n\nNo material contradiction found.\n");
  writeFileSync(
    join(dir, "progress.jsonl"),
    '{"phase":"routing","message":"Selected styrir_plus","at":"2026-07-03T12:00:00Z"}\n',
  );
  return dir;
}

test("renders a self-contained print-friendly HTML report from a run bundle", () => {
  const dir = makeRunDir();
  const html = renderHtmlReport(dir);

  assert.match(html, /^<!doctype html>/i);
  assert.match(html, /<html lang="en"/);
  assert.match(html, /data-styrir-report/);
  assert.match(html, /Best methodologies for layered AI-agent search/);
  assert.match(html, /Layered search works best when routing, source capture, and synthesis are separate steps/);
  assert.match(html, /e1/);
  assert.match(html, /Evidence Ledger/);
  assert.match(html, /Source Registry/);
  assert.match(html, /Gate passed/);
  assert.match(html, /@media print/);
  assert.match(html, /color-scheme: dark/);
  assert.match(html, /--background: #0e0f0c/);
  assert.match(html, /&lt;script&gt;alert\(&#39;x&#39;\)&lt;\/script&gt;/);
  assert.doesNotMatch(html, /fonts\.googleapis|cdn\.jsdelivr|unpkg\.com/);
  assert.doesNotMatch(html, /Evidence Highlights|not a ranking or recommendation|derived from ledger/);
  assert.doesNotMatch(html, /Recommended winner|Best option|Executive Summary/);
});

test("does not render explicit bundle takeaways in the HTML report", () => {
  const dir = makeRunDir();
  writeJson(join(dir, "plan.json"), {
    mode: "styrir_plus",
    question: "Best methodologies for layered AI-agent search",
    objective: "Dogfood Styrir Plus and produce a readable brief",
    outputs: { htmlReport: true },
    takeaways: [
      {
        id: "t1",
        title: "Use tiered routing before spending on deep research",
        text: "A small route decision prevents every question from becoming an expensive deep-search run.",
        evidenceIds: ["e1"],
        confidence: "high",
      },
    ],
    facets: ["methodology", "cost controls", "contradiction sweep"],
  });

  const html = renderHtmlReport(dir);

  assert.match(html, /Evidence Ledger/);
  assert.doesNotMatch(html, /Evidence Highlights/);
  assert.doesNotMatch(html, /Use tiered routing before spending on deep research/);
  assert.doesNotMatch(html, /A small route decision prevents every question from becoming an expensive deep-search run/);
  assert.doesNotMatch(html, /Evidence e1/);
  assert.doesNotMatch(html, /Recommended winner|Best option|Candidate Ranking/);
});

test("writes report.html by default and supports an explicit output path", () => {
  const dir = makeRunDir();
  const defaultPath = writeHtmlReport(dir);
  assert.equal(defaultPath, join(dir, "report.html"));
  assert.equal(existsSync(defaultPath), true);
  assert.match(readFileSync(defaultPath, "utf8"), /data-styrir-report/);

  const explicitPath = join(dir, "print-report.html");
  assert.equal(writeHtmlReport(dir, explicitPath), explicitPath);
  assert.match(readFileSync(explicitPath, "utf8"), /Print stylesheet/);
});
