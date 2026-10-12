import assert from "node:assert/strict";
import { existsSync, mkdtempSync, writeFileSync } from "node:fs";
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

function writeValidPlusBundle(dir: string, overrides: { plan?: unknown; registry?: unknown; gateResult?: unknown } = {}) {
  writeJson(join(dir, "plan.json"), overrides.plan ?? { mode: "styrir_plus", facets: ["official docs", "contradiction sweep"] });
  writeJson(join(dir, "source-registry.json"), overrides.registry ?? { sources: [{ id: "s1", url: "https://example.com", fetched: true }] });
  writeJson(join(dir, "ledger.json"), validLedger());
  writeText(join(dir, "contradiction-sweep.md"), "# Contradiction Sweep\n\nNo material contradiction found.");
  writeJson(join(dir, "gate-result.json"), overrides.gateResult ?? { gateStatus: "pass" });
}

const HTML_PLAN = { mode: "styrir_plus", facets: ["official docs", "contradiction sweep"], outputs: { htmlReport: true } };

test("requires report.html when a styrir_plus plan requests an HTML report", () => {
  const dir = makeRunDir();
  writeValidPlusBundle(dir, { plan: HTML_PLAN });

  const result = validateArtifactRun("styrir_plus", dir);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "missing_html_report"));
});

test("accepts requested HTML reports with Styrir report markers", () => {
  const dir = makeRunDir();
  writeValidPlusBundle(dir, { plan: HTML_PLAN });
  writeText(
    join(dir, "report.html"),
    '<!doctype html><html lang="en" data-styrir-report><body><h1>Report</h1><section>Evidence Ledger</section></body></html>',
  );

  const result = validateArtifactRun("styrir_plus", dir);

  assert.equal(result.gateStatus, "pass");
  assert.equal(result.blockers.length, 0);
});

test("rejects styrir_plus ledger sources missing from source registry", () => {
  const dir = makeRunDir();
  writeValidPlusBundle(dir, { registry: { sources: [{ id: "s2", url: "https://example.com/other", fetched: true }] } });

  const result = validateArtifactRun("styrir_plus", dir);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "ledger_source_missing_from_registry"));
});

test("warns when styrir_plus source registry has sources absent from the ledger", () => {
  const dir = makeRunDir();
  writeValidPlusBundle(dir, {
    registry: {
      sources: [
        { id: "s1", url: "https://example.com", fetched: true },
        { id: "s2", url: "https://example.com/unused", fetched: true },
      ],
    },
  });

  const result = validateArtifactRun("styrir_plus", dir);

  assert.equal(result.gateStatus, "pass");
  assert.ok(result.warnings.some((issue) => issue.code === "registry_source_missing_from_ledger"));
});

test("rejects styrir_plus URL mismatches between ledger and source registry", () => {
  const dir = makeRunDir();
  writeValidPlusBundle(dir, { registry: { sources: [{ id: "s1", url: "https://example.com/registry", fetched: true }] } });

  const result = validateArtifactRun("styrir_plus", dir);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "source_registry_url_mismatch"));
});

test("warns when persisted gate-result digest is stale", () => {
  const dir = makeRunDir();
  writeValidPlusBundle(dir, { gateResult: { gateStatus: "pass", ledgerSha256: "0".repeat(64) } });

  const result = validateArtifactRun("styrir_plus", dir);

  assert.equal(result.gateStatus, "pass");
  assert.ok(result.warnings.some((issue) => issue.code === "stale_gate_result"));
});

function writePlusRun(dir: string, plan: unknown, gateResult: unknown = { gateStatus: "pass" }) {
  writeJson(join(dir, "plan.json"), plan);
  writeJson(join(dir, "source-registry.json"), { sources: [{ id: "s1", url: "https://example.com", fetched: true }] });
  writeJson(join(dir, "ledger.json"), validLedger());
  writeText(join(dir, "contradiction-sweep.md"), "# Contradiction Sweep\n\nNo material contradiction found.");
  writeJson(join(dir, "gate-result.json"), gateResult);
}

test("rejects styrir_plus runs with plan mode mismatches, missing facets, or a failed gate result", () => {
  const modeMismatch = makeRunDir();
  writePlusRun(modeMismatch, { mode: "deep_search_local", facets: ["official docs"] });
  const missingFacets = makeRunDir();
  writePlusRun(missingFacets, { mode: "styrir_plus", facets: [] });
  const failedGate = makeRunDir();
  writePlusRun(failedGate, { mode: "styrir_plus", facets: ["official docs"] }, { gateStatus: "fail" });

  assert.ok(validateArtifactRun("styrir_plus", modeMismatch).blockers.some((issue) => issue.code === "plan_mode_mismatch"));
  assert.ok(validateArtifactRun("styrir_plus", missingFacets).blockers.some((issue) => issue.code === "missing_planner_facets"));
  assert.ok(validateArtifactRun("styrir_plus", failedGate).blockers.some((issue) => issue.code === "artifact_gate_not_passed"));
});

// Mirrors the layout deep-search-mcp init-run + strict render-report-bundle produce.
function writeDeepSearchRun(dir: string, overrides: { report?: string | null; candidate?: boolean; sources?: string; claims?: string } = {}) {
  writeJson(join(dir, "run_manifest.json"), { run_id: "f13bf63dae1c50e2", query: "q", artifact_paths: { report: "report.md" } });
  writeText(join(dir, "sources.jsonl"), overrides.sources ?? JSON.stringify({ source_id: "78c0941cf095f395", raw_url: "https://example.com" }));
  writeText(join(dir, "claims.jsonl"), overrides.claims ?? JSON.stringify({ claim_id: "995af60b47336154", claim_type: "factual", text: "x" }));
  const report = overrides.report === undefined
    ? "# Report\n\n## Executive Summary\n\nKent resigned. [1] [claim:995af60b47336154]\n\n## Bibliography\n\n[1] https://example.com"
    : overrides.report;
  if (report !== null) {
    writeText(join(dir, "report.md"), report);
  }
  if (overrides.candidate) {
    writeText(join(dir, "report.candidate.md"), "# Draft");
  }
}

test("accepts a rendered deep-search run", () => {
  const dir = makeRunDir();
  writeDeepSearchRun(dir);

  const result = validateArtifactRun("deep_search_local", dir);

  assert.equal(result.gateStatus, "pass", JSON.stringify(result.blockers));
});

test("rejects deep-search runs whose report bundle has not passed", () => {
  const unrendered = makeRunDir();
  writeDeepSearchRun(unrendered, { report: null, candidate: true });
  const missing = makeRunDir();
  writeDeepSearchRun(missing, { report: null });

  assert.ok(validateArtifactRun("deep_search_local", unrendered).blockers.some((issue) => issue.code === "report_bundle_not_passed"));
  assert.ok(validateArtifactRun("deep_search_local", missing).blockers.some((issue) => issue.code === "missing_report"));
});

test("rejects deep-search runs without sources, claims, or a run manifest", () => {
  const empty = makeRunDir();
  writeDeepSearchRun(empty, { sources: "", claims: "" });
  const bare = makeRunDir();

  const emptyCodes = validateArtifactRun("deep_search_local", empty).blockers.map((issue) => issue.code);
  const bareCodes = validateArtifactRun("deep_search_local", bare).blockers.map((issue) => issue.code);

  assert.ok(emptyCodes.includes("missing_registered_sources"));
  assert.ok(emptyCodes.includes("missing_claims"));
  assert.ok(bareCodes.includes("missing_run_manifest"));
});

test("rejects reports with unknown or missing claim markers", () => {
  const unknown = makeRunDir();
  writeDeepSearchRun(unknown, { report: "# Report\n\nText [claim:deadbeef]" });
  const unmarked = makeRunDir();
  writeDeepSearchRun(unmarked, { report: "# Report\n\nText [1]" });

  assert.ok(validateArtifactRun("deep_search_local", unknown).blockers.some((issue) => issue.code === "unknown_report_claim"));
  assert.ok(validateArtifactRun("deep_search_local", unmarked).blockers.some((issue) => issue.code === "missing_report_claim_markers"));
});

const REAL_RUN = "/Users/brooks/Code/refs/deep-search/runs/joekent-foreign-influence-20260602-0857";

test("accepts a real rendered deep-search run", { skip: !existsSync(REAL_RUN) && "deep-search runs are not present" }, () => {
  const result = validateArtifactRun("deep_search_local", REAL_RUN);

  assert.equal(result.gateStatus, "pass", JSON.stringify(result.blockers));
});
