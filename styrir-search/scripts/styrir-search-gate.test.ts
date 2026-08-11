import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { validateLedger } from "./styrir-search-gate.ts";

const baseLedger = {
  meta: {
    searchId: "search-2026-07-02-agent-search",
    mode: "structured_search",
    totalQueriesRun: 4,
    totalSourcesFetched: 3,
    budget: {
      maxSearchQueries: 6,
      maxFetches: 6,
    },
  },
  entries: [
    {
      id: "e1",
      entity: "Tavily",
      signalType: "pricing",
      observation: "Tavily documents an advanced search call as a billable provider operation.",
      possibleImplication: "A bounded controller should count provider calls before escalation.",
      sourceId: "s1",
      sourceUrl: "https://docs.example.test/tavily",
      sourceType: "official",
      dateObserved: "2026-07-02",
      confidence: "high",
      relevance: 0.91,
    },
    {
      id: "e2",
      entity: "Exa",
      signalType: "integration_patterns",
      observation: "Exa returns search results with URLs that can be fetched for source evidence.",
      possibleImplication: "Search snippets should be treated as discovery candidates only.",
      sourceId: "s2",
      sourceUrl: "https://blog.example.test/exa",
      sourceType: "analysis",
      dateObserved: "2026-07-02",
      confidence: "medium",
      relevance: 0.72,
    },
  ],
  proofGaps: [
    {
      description: "Could not confirm current extraction pricing from an official source.",
      attemptedQueries: ["exa extraction pricing official docs 2026"],
    },
  ],
  sources: [
    {
      id: "s1",
      url: "https://docs.example.test/tavily",
      title: "Tavily Docs",
      sourceType: "official",
      fetched: true,
    },
    {
      id: "s2",
      url: "https://blog.example.test/exa",
      title: "Exa Analysis",
      sourceType: "analysis",
      fetched: true,
    },
  ],
};

function cloneLedger(overrides: Record<string, unknown> = {}) {
  return {
    ...structuredClone(baseLedger),
    ...overrides,
  };
}

test("passes a bounded ledger with fetched citations, proof gaps, and compatible confidence", () => {
  const result = validateLedger(baseLedger);

  assert.equal(result.gateStatus, "pass");
  assert.deepEqual(result.blockers, []);
});

test("accepts deep_search_local and nvidia_aiq_handoff as current modes", () => {
  for (const mode of ["deep_search_local", "nvidia_aiq_handoff"]) {
    const result = validateLedger(cloneLedger({ meta: { ...baseLedger.meta, mode } }));
    assert.equal(result.gateStatus, "pass");
  }
});

test("keeps aiq_deep_tbd compatibility for legacy ledgers", () => {
  const result = validateLedger(cloneLedger({ meta: { ...baseLedger.meta, mode: "aiq_deep_tbd" } }));

  assert.equal(result.gateStatus, "pass");
});

test("blocks invalid modes instead of accepting unknown deep labels", () => {
  const result = validateLedger(cloneLedger({ meta: { ...baseLedger.meta, mode: "deep_magic" } }));

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "invalid_mode"));
});

test("blocks entries whose cited source was not fetched", () => {
  const ledger = cloneLedger({
    sources: [
      {
        id: "s1",
        url: "https://docs.example.test/tavily",
        title: "Tavily Docs",
        sourceType: "official",
        fetched: false,
      },
    ],
  });

  const result = validateLedger(ledger);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "source_not_fetched"));
});

test("blocks inference language inside observation fields", () => {
  const ledger = cloneLedger({
    entries: [
      {
        ...baseLedger.entries[0],
        observation: "This suggests Tavily is better for all structured search.",
      },
    ],
  });

  const result = validateLedger(ledger);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "inference_in_observation"));
});

test("blocks high confidence for non-primary source types", () => {
  const ledger = cloneLedger({
    entries: [
      {
        ...baseLedger.entries[0],
        sourceType: "analysis",
        confidence: "high",
      },
    ],
  });

  const result = validateLedger(ledger);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "high_confidence_non_primary"));
});

test("blocks ledgers with no proof gaps", () => {
  const result = validateLedger(cloneLedger({ proofGaps: [] }));

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "missing_proof_gaps"));
});

test("blocks search and fetch budget overages", () => {
  const ledger = cloneLedger({
    meta: {
      ...baseLedger.meta,
      totalQueriesRun: 7,
      totalSourcesFetched: 9,
      budget: {
        maxSearchQueries: 6,
        maxFetches: 6,
      },
    },
  });

  const result = validateLedger(ledger);

  assert.equal(result.gateStatus, "fail");
  assert.ok(result.blockers.some((issue) => issue.code === "search_budget_exceeded"));
  assert.ok(result.blockers.some((issue) => issue.code === "fetch_budget_exceeded"));
});

test("CLI writes JSON gate output and exits non-zero on blockers", () => {
  const dir = mkdtempSync(join(tmpdir(), "styrir-search-gate-"));
  const ledgerPath = join(dir, "ledger.json");
  writeFileSync(
    ledgerPath,
    JSON.stringify(
      cloneLedger({
        entries: [
          {
            ...baseLedger.entries[0],
            observation: "This implies the direct search path is obsolete.",
          },
        ],
      }),
      null,
      2,
    ),
  );

  const result = spawnSync(
    process.execPath,
    ["--experimental-strip-types", new URL("./styrir-search-gate.ts", import.meta.url).pathname, ledgerPath],
    { encoding: "utf8" },
  );

  assert.equal(result.status, 1);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.gateStatus, "fail");
  assert.ok(payload.blockers.some((issue: { code: string }) => issue.code === "inference_in_observation"));
}
);
