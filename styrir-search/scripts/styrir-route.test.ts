import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { chooseRoute, type CanonicalRouteRequest, type LegacyRouteRequest } from "./styrir-route.ts";

function makeRequest(overrides: Partial<CanonicalRouteRequest> = {}): CanonicalRouteRequest {
  return {
    question: "Compare current docs-backed search providers",
    objective: "Pick a default provider",
    lane: "technical_decision",
    requiresCurrentInfo: true,
    requiresOfficialSources: false,
    contestedOrHighStakes: false,
    needsClaimLevelValidation: false,
    needsReportArtifact: false,
    estimatedSearchQueries: 6,
    estimatedFetches: 6,
    preferredProviders: [],
    sourceScope: ["official docs", "repo files"],
    ...overrides,
  };
}

function makeLegacyRequest(overrides: Partial<LegacyRouteRequest> = {}): LegacyRouteRequest {
  return {
    question: "Legacy route request",
    stakes: "medium",
    freshness: "current",
    sourceStrictness: "balanced",
    expectedOutput: "answer",
    maxBudgetDollars: 3,
    requiresOfficialSources: false,
    preferredProviders: [],
    deadlineMinutes: 30,
    ...overrides,
  };
}

test("routes a quick single-source lookup to direct_search", () => {
  const result = chooseRoute(
    makeRequest({
      question: "What is Tavily?",
      lane: "current_status",
      requiresCurrentInfo: false,
      estimatedSearchQueries: 1,
      estimatedFetches: 1,
    }),
  );

  assert.equal(result.mode, "direct_search");
  assert.equal(result.gate, "optional-ledger-gate");
  assert.deepEqual(result.budget, {
    maxSearchQueries: 2,
    maxFetches: 2,
    maxFollowups: 0,
    maxConcurrency: 2,
  });
  assert.equal(result.handoff, null);
});

test("routes normal current technical decisions to styrir_search", () => {
  const result = chooseRoute(
    makeRequest({
      question: "Compare Context7 and Tavily for docs lookup",
      requiresOfficialSources: true,
      preferredProviders: ["context7", "tavily"],
      sourceScope: ["official docs", "repo files", "existing local research skills"],
    }),
  );

  assert.equal(result.mode, "styrir_search");
  assert.deepEqual(result.providerHints, ["context7", "tavily"]);
  assert.deepEqual(result.requiredReferences, [
    "references/ledger-contract.md",
    "references/provider-matrix.md",
  ]);
  assert.equal(result.gate, "styrir-search-gate");
});

test("routes contested multi-entity work to styrir_plus", () => {
  const result = chooseRoute(
    makeRequest({
      question: "Which provider should back paid structured search?",
      lane: "comparison",
      contestedOrHighStakes: true,
      estimatedSearchQueries: 9,
      estimatedFetches: 8,
    }),
  );

  assert.equal(result.mode, "styrir_plus");
  assert.equal(result.contradictionSweep, "required");
  assert.equal(result.gate, "styrir-search-gate");
});

test("routes claim-level report validation to deep_search_local", () => {
  const result = chooseRoute(
    makeRequest({
      question: "Produce a reusable report on search providers",
      lane: "decision_trace",
      needsClaimLevelValidation: true,
      needsReportArtifact: true,
      estimatedSearchQueries: 12,
      estimatedFetches: 12,
    }),
  );

  assert.equal(result.mode, "deep_search_local");
  assert.equal(result.gate, "deep-search-strict-gates");
  assert.equal(result.handoff?.nextSystem, "deep-search-cli");
});

test("routes explicit NVIDIA AI-Q requests to nvidia_aiq_handoff", () => {
  const result = chooseRoute(
    makeRequest({
      question: "Prepare this for NVIDIA AI-Q deep research",
      lane: "deep_research",
      needsReportArtifact: true,
      forceMode: "nvidia_aiq_handoff",
      preferredProviders: ["nvidia-aiq"],
      estimatedSearchQueries: 12,
      estimatedFetches: 12,
      sourceScope: ["official docs"],
    }),
  );

  assert.equal(result.mode, "nvidia_aiq_handoff");
  assert.equal(result.gate, "handoff-only");
  assert.equal(result.handoff?.nextSystem, "NVIDIA AI-Q");
});

test("keeps NVIDIA AI-Q preferredProviders as provider hints instead of rerouting", () => {
  const result = chooseRoute(
    makeRequest({
      question: "Compare providers without committing to AI-Q",
      lane: "technical_decision",
      requiresCurrentInfo: true,
      needsReportArtifact: false,
      estimatedSearchQueries: 6,
      estimatedFetches: 6,
      preferredProviders: ["context7", "nvidia-aiq"],
      sourceScope: ["official docs"],
    }),
  );

  assert.equal(result.mode, "styrir_search");
  assert.ok(result.providerHints.includes("nvidia-aiq"));
});

test("preserves configured AI-Q REST targets in canonical route requests", () => {
  const request = makeRequest({
    question: "Run this through a configured local NVIDIA AI-Q target",
    lane: "deep_research",
    needsReportArtifact: true,
    preferredProviders: ["nvidia-aiq"],
    forceMode: "nvidia_aiq_handoff",
    aiqBaseUrl: "http://127.0.0.1:8000",
  });

  assert.equal(request.aiqBaseUrl, "http://127.0.0.1:8000");
  const result = chooseRoute(request);
  assert.equal(result.mode, "nvidia_aiq_handoff");
});

test("rejects configured AI-Q targets that are not absolute http(s) URLs", () => {
  assert.throws(
    () =>
      chooseRoute(
        makeRequest({
          forceMode: "nvidia_aiq_handoff",
          aiqBaseUrl: "file:///tmp/aiq.sock",
        }),
      ),
    /aiqBaseUrl must be an absolute http\(s\) URL/,
  );
});

test("accepts legacy route requests when compatibility mapping is straightforward", () => {
  const result = chooseRoute(
    makeLegacyRequest({
      stakes: "high",
      expectedOutput: "report",
      maxBudgetDollars: 4,
      requiresOfficialSources: true,
    }),
  );

  assert.equal(result.mode, "deep_search_local");
  assert.equal(result.handoff?.nextSystem, "deep-search-cli");
});

test("CLI rejects invalid canonical request fields", () => {
  const result = spawnSync(
    process.execPath,
    ["--experimental-strip-types", new URL("./styrir-route.ts", import.meta.url).pathname],
    {
      encoding: "utf8",
      input: JSON.stringify({
        ...makeRequest(),
        lane: 42,
      }),
    },
  );

  assert.equal(result.status, 1);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.error.code, "invalid_request");
  assert.match(payload.error.message, /lane must be a non-empty string/);
});

test("CLI reads file input and writes canonical route JSON", () => {
  const dir = mkdtempSync(join(tmpdir(), "styrir-route-"));
  const requestPath = join(dir, "request.json");
  writeFileSync(
    requestPath,
    JSON.stringify(
      makeRequest({
        requiresOfficialSources: true,
        preferredProviders: ["context7", "tavily"],
        sourceScope: ["official docs"],
      }),
      null,
      2,
    ),
  );

  const result = spawnSync(
    process.execPath,
    ["--experimental-strip-types", new URL("./styrir-route.ts", import.meta.url).pathname, requestPath],
    { encoding: "utf8" },
  );

  assert.equal(result.status, 0);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.mode, "styrir_search");
  assert.deepEqual(payload.providerHints, ["context7", "tavily"]);
  assert.equal(payload.gate, "styrir-search-gate");
});

test("CLI maps a legacy request payload when canonical fields are absent", () => {
  const result = spawnSync(
    process.execPath,
    ["--experimental-strip-types", new URL("./styrir-route.ts", import.meta.url).pathname],
    {
      encoding: "utf8",
      input: JSON.stringify(
        makeLegacyRequest({
          stakes: "high",
          expectedOutput: "report",
          maxBudgetDollars: 7,
        }),
      ),
    },
  );

  assert.equal(result.status, 0);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.mode, "deep_search_local");
});
