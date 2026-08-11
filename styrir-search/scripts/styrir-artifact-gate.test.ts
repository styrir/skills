import assert from "node:assert/strict";
import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { validateArtifactRun } from "./styrir-artifact-gate.ts";

function makeRunDir(): string {
  return mkdtempSync(join(tmpdir(), "styrir-artifacts-"));
}

function writeJson(path: string, value: unknown) {
  writeFileSync(path, `${JSON.stringify(value, null, 2)}\n`);
}

function writeText(path: string, value: string) {
  writeFileSync(path, `${value}\n`);
}

function longParagraph(prefix: string, count: number): string {
  return Array.from({ length: count }, (_, index) => `${prefix}${index + 1}`).join(" ");
}

function validLedger() {
  return {
    meta: {
      mode: "styrir_plus",
      budget: { maxSearchQueries: 6, maxFetches: 6 },
      totalQueriesRun: 1,
      totalSourcesFetched: 1,
    },
    sources: [{ id: "s1", url: "https://example.com", sourceType: "official", fetched: true }],
    entries: [
      {
        id: "e1",
        observation: "The source documents a bounded structured search lane.",
        sourceId: "s1",
        sourceUrl: "https://example.com",
        sourceType: "official",
        confidence: "high",
        dateObserved: "2026-07-02",
      },
    ],
    proofGaps: [{ description: "No additional provider contradiction was found.", attemptedQueries: ["provider contradiction"] }],
  };
}

function writeValidDeepBundle(dir: string, overrides: {
  plan?: unknown;
  registry?: unknown;
  findings?: string;
  report?: string;
  gateResult?: unknown;
} = {}) {
  mkdirSync(join(dir, "research-notes"));
  writeJson(join(dir, "plan.json"), overrides.plan ?? { mode: "deep_search_local", facets: ["official docs"] });
  writeText(join(dir, "research-notes", "q1.md"), "# Query 1\n\nNotes for a bounded research lane.");
  writeJson(
    join(dir, "source-registry.json"),
    overrides.registry ?? { sources: [{ id: "s1", url: "https://example.com", fetched: true }] },
  );
  writeText(
    join(dir, "consolidated-findings.md"),
    overrides.findings ?? `# Findings\n\n## Theme\n\nThe local evidence bundle cites the registered source [s1]. ${longParagraph("finding", 45)}`,
  );
  writeText(
    join(dir, "report.md"),
    overrides.report ??
      `# Report\n\n## Findings\n\nThe final report cites the registered source [s1]. ${longParagraph("report", 65)}\n\n## Sources\n\n- [s1] https://example.com`,
  );
  writeJson(join(dir, "gate-result.json"), overrides.gateResult ?? { gateStatus: "pass" });
}

test("accepts styrir_plus artifact minima without requiring report-grade files", () => {
  const dir = makeRunDir();
  writeJson(join(dir, "plan.json"), { mode: "styrir_plus", facets: ["official docs", "contradiction sweep"] });
  writeJson(join(dir, "source-registry.json"), { sources: [{ id: "s1", url: "https://example.com", fetched: true }] });
  writeJson(join(dir, "ledger.json"), validLedger());
  writeText(join(dir, "contradiction-sweep.md"), "# Contradiction Sweep\n\nNo material contradiction found.");
  writeJson(join(dir, "gate-result.json"), { gateStatus: "pass" });

  const result = validateArtifactRun("styrir_plus", dir);

  assert.equal(result.gateStatus, "pass");
  assert.equal(result.blockers.length, 0);
});

test("rejects styrir_plus runs missing contradiction sweep", () => {
  const dir = makeRunDir();
  writeJson(join(dir, "plan.json"), { mode: "styrir_plus", facets: ["official docs"] });
  writeJson(join(dir, "source-registry.json"), { sources: [{ id: "s1", url: "https://example.com", fetched: true }] });
  writeJson(join(dir, "ledger.json"), validLedger());
  writeJson(join(dir, "gate-result.json"), { gateStatus: "pass" });

  const result = validateArtifactRun("styrir_plus", dir);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "missing_contradiction_sweep"));
});

test("rejects styrir_plus runs whose ledger fails the normal Styrir gate", () => {
  const dir = makeRunDir();
  const ledger = validLedger();
  ledger.entries[0].observation = "This suggests the plus path is always superior.";
  writeJson(join(dir, "plan.json"), { mode: "styrir_plus", facets: ["official docs"] });
  writeJson(join(dir, "source-registry.json"), { sources: [{ id: "s1", url: "https://example.com", fetched: true }] });
  writeJson(join(dir, "ledger.json"), ledger);
  writeText(join(dir, "contradiction-sweep.md"), "# Contradiction Sweep\n\nNo material contradiction found.");
  writeJson(join(dir, "gate-result.json"), { gateStatus: "pass" });

  const result = validateArtifactRun("styrir_plus", dir);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "ledger_inference_in_observation"));
});

test("accepts deep_search_local artifact bundle with notes and final report", () => {
  const dir = makeRunDir();
  writeValidDeepBundle(dir);

  const result = validateArtifactRun("deep_search_local", dir);

  assert.equal(result.gateStatus, "pass");
});

test("rejects deep_search_local bundle without research notes", () => {
  const dir = makeRunDir();
  writeJson(join(dir, "plan.json"), { mode: "deep_search_local", facets: ["official docs"] });
  writeJson(join(dir, "source-registry.json"), { sources: [{ id: "s1", url: "https://example.com", fetched: true }] });
  writeText(join(dir, "consolidated-findings.md"), `# Findings\n\n## Theme\n\nThe local evidence bundle cites the registered source [s1]. ${longParagraph("finding", 45)}`);
  writeText(join(dir, "report.md"), `# Report\n\n## Findings\n\nThe final report cites the registered source [s1]. ${longParagraph("report", 65)}\n\n## Sources\n\n- [s1] https://example.com`);
  writeJson(join(dir, "gate-result.json"), { gateStatus: "pass" });

  const result = validateArtifactRun("deep_search_local", dir);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "missing_research_notes"));
});

test("rejects deep_search_local report without a Sources section", () => {
  const dir = makeRunDir();
  writeValidDeepBundle(dir, {
    report: `# Report\n\n## Findings\n\nThe final report cites the registered source [s1]. ${longParagraph("report", 65)}`,
  });

  const result = validateArtifactRun("deep_search_local", dir);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "missing_sources_section"));
});

test("rejects deep_search_local report with citations missing from source registry", () => {
  const dir = makeRunDir();
  writeValidDeepBundle(dir, {
    report: `# Report\n\n## Findings\n\nThe final report cites an unknown source [s2]. ${longParagraph("report", 65)}\n\n## Sources\n\n- [s2] https://example.com/other`,
  });

  const result = validateArtifactRun("deep_search_local", dir);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "unknown_report_citation"));
});

test("rejects artifact runs with plan mode mismatches or missing facets", () => {
  const modeMismatch = makeRunDir();
  writeValidDeepBundle(modeMismatch, { plan: { mode: "styrir_plus", facets: ["official docs"] } });

  const missingFacets = makeRunDir();
  writeValidDeepBundle(missingFacets, { plan: { mode: "deep_search_local", facets: [] } });

  const modeResult = validateArtifactRun("deep_search_local", modeMismatch);
  const facetsResult = validateArtifactRun("deep_search_local", missingFacets);

  assert.equal(modeResult.gateStatus, "fail");
  assert.ok(modeResult.blockers.some((issue) => issue.code === "plan_mode_mismatch"));
  assert.equal(facetsResult.gateStatus, "fail");
  assert.ok(facetsResult.blockers.some((issue) => issue.code === "missing_planner_facets"));
});

test("rejects artifact runs without registered sources or passing gate result", () => {
  const missingSources = makeRunDir();
  writeValidDeepBundle(missingSources, { registry: { sources: [] } });

  const failedGate = makeRunDir();
  writeValidDeepBundle(failedGate, { gateResult: { gateStatus: "fail" } });

  const sourceResult = validateArtifactRun("deep_search_local", missingSources);
  const gateResult = validateArtifactRun("deep_search_local", failedGate);

  assert.equal(sourceResult.gateStatus, "fail");
  assert.ok(sourceResult.blockers.some((issue) => issue.code === "missing_registered_sources"));
  assert.equal(gateResult.gateStatus, "fail");
  assert.ok(gateResult.blockers.some((issue) => issue.code === "artifact_gate_not_passed"));
});

test("rejects thin report prose and missing citations", () => {
  const shortReport = makeRunDir();
  writeValidDeepBundle(shortReport, {
    report: "# Report\n\n## Findings\n\nToo thin [s1].\n\n## Sources\n\n- [s1] https://example.com",
  });

  const missingCitations = makeRunDir();
  writeValidDeepBundle(missingCitations, {
    report: `# Report\n\n## Findings\n\nThis report has enough prose but no source id citation. ${longParagraph("report", 65)}\n\n## Sources\n\n- s1 https://example.com`,
  });

  const shortResult = validateArtifactRun("deep_search_local", shortReport);
  const citationResult = validateArtifactRun("deep_search_local", missingCitations);

  assert.equal(shortResult.gateStatus, "fail");
  assert.ok(shortResult.blockers.some((issue) => issue.code === "report_too_short"));
  assert.equal(citationResult.gateStatus, "fail");
  assert.ok(citationResult.blockers.some((issue) => issue.code === "missing_report_citations"));
});

test("rejects consolidated findings with citations missing from source registry", () => {
  const dir = makeRunDir();
  writeValidDeepBundle(dir, {
    findings: `# Findings\n\n## Theme\n\nThe consolidated findings cite an unknown source [s2]. ${longParagraph("finding", 45)}`,
  });

  const result = validateArtifactRun("deep_search_local", dir);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "unknown_findings_citation"));
});

test("warns when registered sources are not cited in findings or report", () => {
  const dir = makeRunDir();
  writeValidDeepBundle(dir, {
    registry: {
      sources: [
        { id: "s1", url: "https://example.com", fetched: true },
        { id: "s2", url: "https://example.com/unused", fetched: true },
      ],
    },
  });

  const result = validateArtifactRun("deep_search_local", dir);

  assert.equal(result.gateStatus, "pass");
  assert.ok(result.warnings.some((issue) => issue.code === "uncited_registered_source"));
});

test("does not treat ordinary bracketed prose as source citations", () => {
  const dir = makeRunDir();
  writeValidDeepBundle(dir, {
    report: `# Report\n\n## Findings\n\nThe final report includes editorial markers [TODO], [sic], and [summary] while citing source [s1]. ${longParagraph("report", 65)}\n\n## Sources\n\n- [s1] https://example.com`,
  });

  const result = validateArtifactRun("deep_search_local", dir);

  assert.equal(result.gateStatus, "pass");
  assert.ok(!result.blockers.some((issue) => issue.code === "unknown_report_citation"));
});
