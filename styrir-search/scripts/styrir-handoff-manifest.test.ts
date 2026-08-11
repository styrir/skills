import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { classifyAiqHealthResponse, createHandoffManifest } from "./styrir-handoff-manifest.ts";
import { chooseRoute } from "./styrir-route.ts";

test("creates a local Deep Search manifest with concrete next commands", () => {
  const manifest = createHandoffManifest({
    route: chooseRoute({
      question: "Make this report grade",
      objective: "Produce a reusable cited report",
      lane: "decision_trace",
      requiresCurrentInfo: true,
      requiresOfficialSources: true,
      contestedOrHighStakes: false,
      needsClaimLevelValidation: true,
      needsReportArtifact: true,
      estimatedSearchQueries: 12,
      estimatedFetches: 12,
      preferredProviders: ["context7"],
      sourceScope: ["official docs", "fetched web sources"],
    }),
    descriptor: {
      question: "Make this report grade",
      objective: "Produce a reusable cited report",
      lane: "decision_trace",
      requiresCurrentInfo: true,
      requiresOfficialSources: true,
      contestedOrHighStakes: false,
      needsClaimLevelValidation: true,
      needsReportArtifact: true,
      estimatedSearchQueries: 12,
      estimatedFetches: 12,
      preferredProviders: ["context7"],
      sourceScope: ["official docs", "fetched web sources"],
    },
    ledgerPath: "/tmp/styrir-ledger.json",
    gateResult: { gateStatus: "pass", blockers: [], warnings: [], counts: { entries: 3, sources: 3, proofGaps: 1 } },
  });

  assert.equal(manifest.manifestVersion, 1);
  assert.match(manifest.createdAt, /^\d{4}-\d{2}-\d{2}T/);
  assert.equal(manifest.nextSystem, "deep-search-cli");
  assert.equal(manifest.ledgerPath, "/tmp/styrir-ledger.json");
  assert.equal(manifest.gateStatus, "pass");
  assert.ok(manifest.commands.some((command) => command.includes("plan-research-lanes")));
  assert.ok(manifest.commands.some((command) => command.includes("render-report-bundle --strict")));
  assert.ok(manifest.commands.some((command) => command.includes("gated-report-mode.md")));
});

test("creates a NVIDIA AI-Q handoff manifest without pretending local execution exists", () => {
  const manifest = createHandoffManifest({
    route: chooseRoute({
      question: "Use NVIDIA AI-Q",
      objective: "Prepare external deep research handoff",
      lane: "deep_research",
      requiresCurrentInfo: true,
      requiresOfficialSources: true,
      contestedOrHighStakes: false,
      needsClaimLevelValidation: false,
      needsReportArtifact: true,
      forceMode: "nvidia_aiq_handoff",
      estimatedSearchQueries: 12,
      estimatedFetches: 12,
      preferredProviders: ["nvidia-aiq"],
      sourceScope: ["official docs"],
    }),
    descriptor: {
      question: "Use NVIDIA AI-Q",
      objective: "Prepare external deep research handoff",
      lane: "deep_research",
      requiresCurrentInfo: true,
      requiresOfficialSources: true,
      contestedOrHighStakes: false,
      needsClaimLevelValidation: false,
      needsReportArtifact: true,
      forceMode: "nvidia_aiq_handoff",
      estimatedSearchQueries: 12,
      estimatedFetches: 12,
      preferredProviders: ["nvidia-aiq"],
      sourceScope: ["official docs"],
    },
  });

  assert.equal(manifest.nextSystem, "NVIDIA AI-Q");
  assert.deepEqual(manifest.commands, []);
  assert.ok(manifest.blockers.includes("NVIDIA AI-Q execution is not wired in this local skill."));
});

test("keeps NVIDIA AI-Q manifest-only behavior when no local target is configured", () => {
  const manifest = createHandoffManifest({
    route: chooseRoute({
      question: "Use NVIDIA AI-Q without a configured target",
      objective: "Prepare external deep research handoff",
      lane: "deep_research",
      needsReportArtifact: true,
      forceMode: "nvidia_aiq_handoff",
      preferredProviders: ["nvidia-aiq"],
      sourceScope: ["official docs"],
    }),
    descriptor: {
      question: "Use NVIDIA AI-Q without a configured target",
      objective: "Prepare external deep research handoff",
      lane: "deep_research",
      needsReportArtifact: true,
      forceMode: "nvidia_aiq_handoff",
      preferredProviders: ["nvidia-aiq"],
      sourceScope: ["official docs"],
    },
  });

  assert.equal(manifest.nextSystem, "NVIDIA AI-Q");
  assert.deepEqual(manifest.commands, []);
  assert.ok(manifest.blockers.some((blocker) => blocker.includes("No configured local AI-Q target")));
});

test("includes AI-Q REST health and async job commands when a local target is configured", () => {
  const descriptor = {
    question: "Use the configured AI-Q server",
    objective: "Run deep research through local AI-Q",
    lane: "deep_research",
    needsReportArtifact: true,
    forceMode: "nvidia_aiq_handoff" as const,
    preferredProviders: ["nvidia-aiq"],
    sourceScope: ["official docs"],
    aiqBaseUrl: "http://127.0.0.1:8000",
  };

  const manifest = createHandoffManifest({
    route: chooseRoute(descriptor),
    descriptor,
  });

  assert.equal(manifest.nextSystem, "NVIDIA AI-Q");
  assert.ok(manifest.blockers.some((blocker) => blocker.includes("health is unverified")));
  assert.ok(manifest.commands.some((command) => command.includes("curl -sf http://127.0.0.1:8000/health")));
  assert.ok(manifest.commands.some((command) => command.includes("/v1/jobs/async")));
  assert.ok(manifest.commands.some((command) => command.includes("/v1/jobs/async/<job-id>/status")));
  assert.ok(manifest.commands.some((command) => command.includes("/v1/jobs/async/<job-id>/report")));
  assert.ok(manifest.commands.some((command) => command.includes("Use the configured AI-Q server")));
});

test("rejects malformed AI-Q REST targets even when a prebuilt route is supplied", () => {
  const descriptor = {
    question: "Use the configured AI-Q server",
    objective: "Run deep research through local AI-Q",
    lane: "deep_research",
    needsReportArtifact: true,
    forceMode: "nvidia_aiq_handoff" as const,
    preferredProviders: ["nvidia-aiq"],
    sourceScope: ["official docs"],
    aiqBaseUrl: "file:///tmp/aiq.sock",
  };

  assert.throws(
    () =>
      createHandoffManifest({
        route: {
          mode: "nvidia_aiq_handoff",
          reason: "prebuilt route",
          budget: { maxSearchQueries: 10, maxFetches: 10, maxFollowups: 0, maxConcurrency: 1 },
          providerHints: ["nvidia-aiq"],
          requiredReferences: [],
          gate: "handoff-only",
          contradictionSweep: "off",
          handoff: { nextSystem: "NVIDIA AI-Q", reason: "prebuilt" },
        },
        descriptor,
      }),
    /aiqBaseUrl must be an absolute http\(s\) URL/,
  );
});

test("classifies AI-Q health responses and fails closed on malformed or unhealthy payloads", () => {
  assert.equal(classifyAiqHealthResponse('{"status":"healthy"}'), "healthy");
  assert.equal(classifyAiqHealthResponse('{"ok":true}'), "healthy");
  assert.throws(() => classifyAiqHealthResponse("not json"), /Malformed AI-Q health response/);
  assert.throws(() => classifyAiqHealthResponse('{"status":"down"}'), /AI-Q target is not healthy/);
});

test("carries route mode and source scope through the manifest", () => {
  const manifest = createHandoffManifest({
    route: chooseRoute({
      question: "Produce a reusable report on search providers",
      objective: "Produce a reusable cited report",
      lane: "decision_trace",
      requiresCurrentInfo: true,
      requiresOfficialSources: true,
      contestedOrHighStakes: false,
      needsClaimLevelValidation: true,
      needsReportArtifact: true,
      estimatedSearchQueries: 12,
      estimatedFetches: 12,
      preferredProviders: ["context7"],
      sourceScope: ["official docs", "repo files"],
    }),
    descriptor: {
      question: "Produce a reusable report on search providers",
      objective: "Produce a reusable cited report",
      lane: "decision_trace",
      requiresCurrentInfo: true,
      requiresOfficialSources: true,
      contestedOrHighStakes: false,
      needsClaimLevelValidation: true,
      needsReportArtifact: true,
      estimatedSearchQueries: 12,
      estimatedFetches: 12,
      preferredProviders: ["context7"],
      sourceScope: ["official docs", "repo files"],
    },
  });

  assert.equal(manifest.mode, "deep_search_local");
  assert.deepEqual(manifest.sourceScope, ["official docs", "repo files"]);
});

test("rejects non-handoff routes instead of silently escalating to Deep Search", () => {
  assert.throws(
    () =>
      createHandoffManifest({
        route: chooseRoute({
          question: "Compare current docs-backed search providers",
          objective: "Pick a default provider",
          lane: "technical_decision",
          requiresCurrentInfo: true,
          requiresOfficialSources: true,
          contestedOrHighStakes: false,
          needsClaimLevelValidation: false,
          needsReportArtifact: false,
          estimatedSearchQueries: 6,
          estimatedFetches: 6,
          preferredProviders: ["context7", "tavily"],
          sourceScope: ["official docs"],
        }),
        descriptor: {
          question: "Compare current docs-backed search providers",
          objective: "Pick a default provider",
          lane: "technical_decision",
          requiresCurrentInfo: true,
          requiresOfficialSources: true,
          contestedOrHighStakes: false,
          needsClaimLevelValidation: false,
          needsReportArtifact: false,
          estimatedSearchQueries: 6,
          estimatedFetches: 6,
          preferredProviders: ["context7", "tavily"],
          sourceScope: ["official docs"],
        },
      }),
    /requires a deep_search_local or nvidia_aiq_handoff route/,
  );
});

test("CLI reads a request file and writes manifest JSON", () => {
  const dir = mkdtempSync(join(tmpdir(), "styrir-handoff-"));
  const requestPath = join(dir, "request.json");
  writeFileSync(
    requestPath,
    JSON.stringify({
      question: "Compare current docs-backed search providers",
      objective: "Prepare external deep research handoff",
      lane: "deep_research",
      requiresCurrentInfo: true,
      requiresOfficialSources: true,
      contestedOrHighStakes: false,
      needsClaimLevelValidation: false,
      needsReportArtifact: true,
      forceMode: "nvidia_aiq_handoff",
      estimatedSearchQueries: 12,
      estimatedFetches: 12,
      preferredProviders: ["nvidia-aiq"],
      sourceScope: ["official docs"],
    }),
  );

  const result = spawnSync(
    process.execPath,
    ["--experimental-strip-types", new URL("./styrir-handoff-manifest.ts", import.meta.url).pathname, requestPath],
    { encoding: "utf8" },
  );

  assert.equal(result.status, 0);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.nextSystem, "NVIDIA AI-Q");
  assert.deepEqual(payload.commands, []);
});
