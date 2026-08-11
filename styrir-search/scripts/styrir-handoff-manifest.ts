import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";
import { chooseRoute, parseRequest, type CanonicalRouteRequest, type RouteDecision } from "./styrir-route.ts";
import type { GateResult } from "./styrir-search-gate.ts";

export interface HandoffManifest {
  manifestVersion: 1;
  createdAt: string;
  mode: RouteDecision["mode"];
  nextSystem: "deep-search-cli" | "NVIDIA AI-Q";
  question: string;
  objective: string;
  sourceScope: string[];
  ledgerPath: string | null;
  gateStatus: GateResult["gateStatus"] | "not_run";
  commands: string[];
  blockers: string[];
  aiqBaseUrl?: string;
  aiqContract?: "rest_api" | "handoff_only";
}

export interface HandoffManifestInput {
  route?: RouteDecision;
  descriptor: CanonicalRouteRequest;
  ledgerPath?: string;
  gateResult?: GateResult;
}

const GATED_REPORT_REFERENCE =
  "/Users/brooks/Code/skills/research/deep-search-cli/references/gated-report-mode.md";

function buildDeepSearchCommands(question: string): string[] {
  return [
    "cd /Users/brooks/Code/refs/deep-search",
    `# Create <run-dir>, register sources/evidence/claims, and draft report.candidate.md per ${GATED_REPORT_REFERENCE} before running verification commands.`,
    ".venv/bin/deep-search-mcp plan-research-lanes --query " + JSON.stringify(question),
    ".venv/bin/deep-search-mcp verify-claims --dir <run-dir> --strict",
    ".venv/bin/deep-search-mcp verify-citations --report <run-dir>/report.candidate.md --strict --no-network",
    ".venv/bin/deep-search-mcp validate-report --report <run-dir>/report.candidate.md",
    ".venv/bin/deep-search-mcp render-report-bundle --strict --dir <run-dir> --draft-report <run-dir>/report.candidate.md",
  ];
}

function normalizeBaseUrl(baseUrl: string): string {
  return baseUrl.replace(/\/+$/, "");
}

function validateAiqBaseUrl(baseUrl: string): string {
  try {
    const parsed = new URL(baseUrl);
    if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
      throw new Error("unsupported protocol");
    }
  } catch {
    throw new Error("AI-Q aiqBaseUrl must be an absolute http(s) URL.");
  }
  return normalizeBaseUrl(baseUrl);
}

function buildAiqRestCommands(baseUrl: string, question: string, sourceScope: string[]): string[] {
  const normalizedBaseUrl = validateAiqBaseUrl(baseUrl);
  return [
    `curl -sf ${normalizedBaseUrl}/health`,
    `# Create <aiq-request.json> with query ${JSON.stringify(question)} and sourceScope ${JSON.stringify(sourceScope)}.`,
    `curl -sS -X POST ${normalizedBaseUrl}/v1/jobs/async -H 'Content-Type: application/json' -d @<aiq-request.json>`,
    `curl -sS ${normalizedBaseUrl}/v1/jobs/async/<job-id>/status`,
    `curl -sS ${normalizedBaseUrl}/v1/jobs/async/<job-id>/report > <run-dir>/report.md`,
  ];
}

export function classifyAiqHealthResponse(raw: string): "healthy" {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("Malformed AI-Q health response.");
  }

  if (typeof parsed !== "object" || parsed === null || Array.isArray(parsed)) {
    throw new Error("Malformed AI-Q health response.");
  }

  const record = parsed as Record<string, unknown>;
  if (record.ok === true || record.healthy === true || record.status === "healthy" || record.status === "ok") {
    return "healthy";
  }

  throw new Error("AI-Q target is not healthy.");
}

export function createHandoffManifest(input: HandoffManifestInput): HandoffManifest {
  const route = input.route ?? chooseRoute(input.descriptor);
  const objective = input.descriptor.objective ?? "Preserve the route decision and required evidence handoff.";

  if (route.mode !== "deep_search_local" && route.mode !== "nvidia_aiq_handoff") {
    throw new Error("Handoff manifest requires a deep_search_local or nvidia_aiq_handoff route.");
  }

  if (route.mode === "nvidia_aiq_handoff") {
    const aiqBaseUrl = input.descriptor.aiqBaseUrl;
    if (aiqBaseUrl) {
      const normalizedAiqBaseUrl = validateAiqBaseUrl(aiqBaseUrl);
      return {
        manifestVersion: 1,
        createdAt: new Date().toISOString(),
        mode: route.mode,
        nextSystem: "NVIDIA AI-Q",
        question: input.descriptor.question,
        objective,
        sourceScope: input.descriptor.sourceScope ?? [],
        ledgerPath: input.ledgerPath ?? null,
        gateStatus: input.gateResult?.gateStatus ?? "not_run",
        commands: buildAiqRestCommands(normalizedAiqBaseUrl, input.descriptor.question, input.descriptor.sourceScope ?? []),
        blockers: ["AI-Q target health is unverified; run the health check before posting a research job."],
        aiqBaseUrl: normalizedAiqBaseUrl,
        aiqContract: "rest_api",
      };
    }

    return {
      manifestVersion: 1,
      createdAt: new Date().toISOString(),
      mode: route.mode,
      nextSystem: "NVIDIA AI-Q",
      question: input.descriptor.question,
      objective,
      sourceScope: input.descriptor.sourceScope ?? [],
      ledgerPath: input.ledgerPath ?? null,
      gateStatus: input.gateResult?.gateStatus ?? "not_run",
      commands: [],
      blockers: [
        "No configured local AI-Q target; emit manifest-only handoff.",
        "NVIDIA AI-Q execution is not wired in this local skill.",
      ],
      aiqContract: "handoff_only",
    };
  }

  return {
    manifestVersion: 1,
    createdAt: new Date().toISOString(),
    mode: route.mode,
    nextSystem: "deep-search-cli",
    question: input.descriptor.question,
    objective,
    sourceScope: input.descriptor.sourceScope ?? [],
    ledgerPath: input.ledgerPath ?? null,
    gateStatus: input.gateResult?.gateStatus ?? "not_run",
    commands: buildDeepSearchCommands(input.descriptor.question),
    blockers: [],
  };
}

function readCliInput(argv: string[]): CanonicalRouteRequest {
  const filePath = argv[2];
  const raw = filePath ? readFileSync(filePath, "utf8") : readFileSync(0, "utf8");
  return parseRequest(JSON.parse(raw));
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const descriptor = readCliInput(process.argv);
    const manifest = createHandoffManifest({ descriptor });
    process.stdout.write(`${JSON.stringify(manifest, null, 2)}\n`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown handoff manifest error.";
    process.stdout.write(`${JSON.stringify({ error: { message } }, null, 2)}\n`);
    process.exitCode = 1;
  }
}
