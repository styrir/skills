import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

export type RouteMode =
  | "direct_search"
  | "styrir_search"
  | "styrir_plus"
  | "deep_search_local"
  | "nvidia_aiq_handoff";

export type RouteCompatibilityMode = RouteMode | "aiq_deep_tbd";

export interface CanonicalRouteRequest {
  question: string;
  objective?: string;
  lane: string;
  requiresCurrentInfo?: boolean;
  requiresOfficialSources?: boolean;
  contestedOrHighStakes?: boolean;
  needsClaimLevelValidation?: boolean;
  needsReportArtifact?: boolean;
  estimatedSearchQueries?: number;
  estimatedFetches?: number;
  preferredProviders?: string[];
  sourceScope?: string[];
  aiqBaseUrl?: string;
  forceMode?: RouteCompatibilityMode;
}

export interface LegacyRouteRequest {
  question: string;
  stakes: "low" | "medium" | "high";
  freshness: "stable" | "current";
  sourceStrictness: "balanced" | "official_preferred" | "official_only";
  expectedOutput: "answer" | "comparison_brief" | "report";
  maxBudgetDollars: number;
  requiresOfficialSources?: boolean;
  preferredProviders?: string[];
  deadlineMinutes: number;
  forceMode?: RouteCompatibilityMode;
}

export interface RouteDecision {
  mode: RouteMode;
  reason: string;
  budget: {
    maxSearchQueries: number;
    maxFetches: number;
    maxFollowups: number;
    maxConcurrency: number;
  };
  providerHints: string[];
  requiredReferences: string[];
  gate: "optional-ledger-gate" | "styrir-search-gate" | "deep-search-strict-gates" | "handoff-only";
  contradictionSweep: "off" | "required";
  handoff: null | {
    nextSystem: "deep-search-cli" | "NVIDIA AI-Q";
    reason: string;
  };
}

type RouteRequest = CanonicalRouteRequest;
type CliErrorCode = "invalid_force_mode" | "invalid_json" | "invalid_request";

const VALID_FORCE_MODES = new Set<RouteCompatibilityMode>([
  "direct_search",
  "styrir_search",
  "styrir_plus",
  "deep_search_local",
  "nvidia_aiq_handoff",
  "aiq_deep_tbd",
]);

const BUDGETS = {
  direct_search: { maxSearchQueries: 2, maxFetches: 2, maxFollowups: 0, maxConcurrency: 2 },
  styrir_search: { maxSearchQueries: 6, maxFetches: 6, maxFollowups: 2, maxConcurrency: 3 },
  styrir_plus: { maxSearchQueries: 10, maxFetches: 10, maxFollowups: 3, maxConcurrency: 3 },
  deep_search_local: { maxSearchQueries: 10, maxFetches: 10, maxFollowups: 3, maxConcurrency: 2 },
  nvidia_aiq_handoff: { maxSearchQueries: 10, maxFetches: 10, maxFollowups: 0, maxConcurrency: 1 },
} as const;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asOptionalString(value: unknown): string | undefined {
  return typeof value === "string" && value.trim() ? value : undefined;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function asBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function asStringArray(value: unknown): string[] | undefined {
  if (!Array.isArray(value)) {
    return undefined;
  }
  return value.filter((item): item is string => typeof item === "string");
}

function normalizeForceMode(mode: RouteCompatibilityMode): RouteMode {
  return mode === "aiq_deep_tbd" ? "nvidia_aiq_handoff" : mode;
}

function dedupe(values: string[]): string[] {
  return [...new Set(values.filter(Boolean))];
}

function isCanonicalRequest(input: Record<string, unknown>): boolean {
  return "lane" in input || "estimatedSearchQueries" in input || "estimatedFetches" in input || "sourceScope" in input;
}

function validateCanonicalRequest(request: CanonicalRouteRequest): CanonicalRouteRequest {
  if (!request.question) {
    throw new Error("Route request question is required.");
  }
  if (!request.lane) {
    throw new Error("Route request lane must be a non-empty string.");
  }
  if (request.estimatedSearchQueries !== undefined && !Number.isFinite(request.estimatedSearchQueries)) {
    throw new Error("Route request estimatedSearchQueries must be a finite number.");
  }
  if (request.estimatedFetches !== undefined && !Number.isFinite(request.estimatedFetches)) {
    throw new Error("Route request estimatedFetches must be a finite number.");
  }
  if (request.forceMode && !VALID_FORCE_MODES.has(request.forceMode)) {
    throw new Error(`Invalid forceMode '${request.forceMode}'.`);
  }
  if (request.aiqBaseUrl) {
    try {
      const parsed = new URL(request.aiqBaseUrl);
      if (parsed.protocol !== "http:" && parsed.protocol !== "https:") {
        throw new Error("unsupported protocol");
      }
    } catch {
      throw new Error("Route request aiqBaseUrl must be an absolute http(s) URL.");
    }
  }
  return {
    ...request,
    estimatedSearchQueries: request.estimatedSearchQueries ?? 6,
    estimatedFetches: request.estimatedFetches ?? 6,
    preferredProviders: request.preferredProviders ?? [],
    sourceScope: request.sourceScope ?? [],
    aiqBaseUrl: request.aiqBaseUrl,
    requiresCurrentInfo: request.requiresCurrentInfo ?? false,
    requiresOfficialSources: request.requiresOfficialSources ?? false,
    contestedOrHighStakes: request.contestedOrHighStakes ?? false,
    needsClaimLevelValidation: request.needsClaimLevelValidation ?? false,
    needsReportArtifact: request.needsReportArtifact ?? false,
  };
}

function fromLegacyRequest(input: Record<string, unknown>): CanonicalRouteRequest {
  const question = asString(input.question);
  if (!question) {
    throw new Error("Route request question is required.");
  }

  const stakes = asString(input.stakes);
  const freshness = asString(input.freshness);
  const sourceStrictness = asString(input.sourceStrictness);
  const expectedOutput = asString(input.expectedOutput);
  const maxBudgetDollars = asNumber(input.maxBudgetDollars);

  if (!["low", "medium", "high"].includes(stakes)) {
    throw new Error("Route request stakes must be one of: low, medium, high.");
  }
  if (!["stable", "current"].includes(freshness)) {
    throw new Error("Route request freshness must be one of: stable, current.");
  }
  if (!["balanced", "official_preferred", "official_only"].includes(sourceStrictness)) {
    throw new Error("Route request sourceStrictness must be one of: balanced, official_preferred, official_only.");
  }
  if (!["answer", "comparison_brief", "report"].includes(expectedOutput)) {
    throw new Error("Route request expectedOutput must be one of: answer, comparison_brief, report.");
  }
  if (!Number.isFinite(maxBudgetDollars)) {
    throw new Error("Route request maxBudgetDollars must be a finite number.");
  }
  const budgetDollars = maxBudgetDollars as number;

  return validateCanonicalRequest({
    question,
    objective: expectedOutput === "report" ? "Produce a reusable cited report." : undefined,
    lane: expectedOutput === "comparison_brief" ? "comparison" : expectedOutput === "report" ? "decision_trace" : "technical_decision",
    requiresCurrentInfo: freshness === "current",
    requiresOfficialSources:
      asBoolean(input.requiresOfficialSources) ?? (sourceStrictness === "official_preferred" || sourceStrictness === "official_only"),
    contestedOrHighStakes: stakes === "high" || expectedOutput === "comparison_brief",
    needsClaimLevelValidation: expectedOutput === "report" && budgetDollars < 5,
    needsReportArtifact: expectedOutput === "report",
    estimatedSearchQueries: expectedOutput === "answer" ? 6 : expectedOutput === "comparison_brief" ? 9 : 12,
    estimatedFetches: expectedOutput === "answer" ? 6 : expectedOutput === "comparison_brief" ? 8 : 12,
    preferredProviders: asStringArray(input.preferredProviders) ?? [],
    sourceScope: [],
    forceMode: asOptionalString(input.forceMode) as RouteCompatibilityMode | undefined,
  });
}

export function parseRequest(input: unknown): CanonicalRouteRequest {
  if (!isRecord(input)) {
    throw new Error("Route request must be a JSON object.");
  }

  if (isCanonicalRequest(input)) {
    return validateCanonicalRequest({
      question: asString(input.question),
      objective: asOptionalString(input.objective),
      lane: asString(input.lane),
      requiresCurrentInfo: asBoolean(input.requiresCurrentInfo),
      requiresOfficialSources: asBoolean(input.requiresOfficialSources),
      contestedOrHighStakes: asBoolean(input.contestedOrHighStakes),
      needsClaimLevelValidation: asBoolean(input.needsClaimLevelValidation),
      needsReportArtifact: asBoolean(input.needsReportArtifact),
      estimatedSearchQueries: asNumber(input.estimatedSearchQueries),
      estimatedFetches: asNumber(input.estimatedFetches),
      preferredProviders: asStringArray(input.preferredProviders),
      sourceScope: asStringArray(input.sourceScope),
      aiqBaseUrl: asOptionalString(input.aiqBaseUrl),
      forceMode: asOptionalString(input.forceMode) as RouteCompatibilityMode | undefined,
    });
  }

  return fromLegacyRequest(input);
}

function buildReason(mode: RouteMode, input: CanonicalRouteRequest): string {
  switch (mode) {
    case "direct_search":
      return "The request is narrow enough for a quick lookup with an optional ledger.";
    case "styrir_plus":
      return "The request is still bounded, but contested or broad enough to require a contradiction sweep.";
    case "deep_search_local":
      return "Claim-level validation or a report artifact is required, so the work should hand off into local Deep Search gates.";
    case "nvidia_aiq_handoff":
      return input.aiqBaseUrl
        ? "The request explicitly targets a configured local NVIDIA AI-Q REST endpoint."
        : "The request explicitly targets NVIDIA AI-Q, so this lane prepares a fail-closed handoff manifest.";
    case "styrir_search":
    default:
      return input.requiresCurrentInfo || input.requiresOfficialSources
        ? "The request needs current official evidence and a reusable audit trail, but does not need claim-level report validation."
        : "The request needs a reusable audit trail but remains within the standard bounded Styrir Search lane.";
  }
}

function buildProviderHints(input: CanonicalRouteRequest): string[] {
  const preferredProviders = input.preferredProviders ?? [];
  const providerHints = [...preferredProviders];
  if ((input.requiresCurrentInfo || input.requiresOfficialSources) && !providerHints.includes("context7")) {
    providerHints.unshift("context7");
  }
  if ((input.requiresCurrentInfo || input.contestedOrHighStakes) && !providerHints.includes("tavily")) {
    providerHints.push("tavily");
  }
  return dedupe(providerHints);
}

function inferMode(input: CanonicalRouteRequest): RouteMode {
  if (input.forceMode) {
    if (!VALID_FORCE_MODES.has(input.forceMode)) {
      throw new Error(`Invalid forceMode '${input.forceMode}'.`);
    }
    return normalizeForceMode(input.forceMode);
  }

  if (
    input.needsClaimLevelValidation ||
    input.needsReportArtifact ||
    (input.estimatedSearchQueries ?? 0) > 10 ||
    (input.estimatedFetches ?? 0) > 10
  ) {
    return "deep_search_local";
  }
  if (
    input.contestedOrHighStakes ||
    (input.estimatedSearchQueries ?? 0) > 6 ||
    (input.estimatedFetches ?? 0) > 6
  ) {
    return "styrir_plus";
  }
  if (
    (input.estimatedSearchQueries ?? 0) <= 2 &&
    (input.estimatedFetches ?? 0) <= 2 &&
    !input.needsReportArtifact
  ) {
    return "direct_search";
  }
  return "styrir_search";
}

export function chooseRoute(input: CanonicalRouteRequest | LegacyRouteRequest): RouteDecision {
  const request = parseRequest(input);
  const mode = inferMode(request);
  const providerHints = buildProviderHints(request);

  switch (mode) {
    case "direct_search":
      return {
        mode,
        reason: buildReason(mode, request),
        budget: BUDGETS.direct_search,
        providerHints,
        requiredReferences: ["references/provider-matrix.md"],
        gate: "optional-ledger-gate",
        contradictionSweep: "off",
        handoff: null,
      };
    case "styrir_plus":
      return {
        mode,
        reason: buildReason(mode, request),
        budget: BUDGETS.styrir_plus,
        providerHints,
        requiredReferences: ["references/ledger-contract.md", "references/provider-matrix.md"],
        gate: "styrir-search-gate",
        contradictionSweep: "required",
        handoff: null,
      };
    case "deep_search_local":
      return {
        mode,
        reason: buildReason(mode, request),
        budget: BUDGETS.deep_search_local,
        providerHints,
        requiredReferences: ["references/provider-matrix.md", "references/handoff-manifest.md"],
        gate: "deep-search-strict-gates",
        contradictionSweep: "required",
        handoff: {
          nextSystem: "deep-search-cli",
          reason: "Claim-level report validation is required.",
        },
      };
    case "nvidia_aiq_handoff":
      return {
        mode,
        reason: buildReason(mode, request),
        budget: BUDGETS.nvidia_aiq_handoff,
        providerHints,
        requiredReferences: ["references/provider-matrix.md", "references/handoff-manifest.md"],
        gate: "handoff-only",
        contradictionSweep: "required",
        handoff: {
          nextSystem: "NVIDIA AI-Q",
          reason: request.aiqBaseUrl
            ? "A local NVIDIA AI-Q target is configured; health-check before running async research."
            : "No local NVIDIA AI-Q target is configured; emit a handoff manifest only.",
        },
      };
    case "styrir_search":
    default:
      return {
        mode: "styrir_search",
        reason: buildReason("styrir_search", request),
        budget: BUDGETS.styrir_search,
        providerHints,
        requiredReferences: ["references/ledger-contract.md", "references/provider-matrix.md"],
        gate: "styrir-search-gate",
        contradictionSweep: "off",
        handoff: null,
      };
  }
}

function toCliError(code: CliErrorCode, message: string) {
  return {
    error: {
      code,
      message,
    },
  };
}

function readCliInput(argv: string[]): unknown {
  const filePath = argv[2];
  const raw = filePath ? readFileSync(filePath, "utf8") : readFileSync(0, "utf8");
  try {
    return JSON.parse(raw);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Could not parse JSON input.";
    throw Object.assign(new Error(message), { cliCode: "invalid_json" satisfies CliErrorCode });
  }
}

function main(argv: string[]) {
  try {
    const decision = chooseRoute(parseRequest(readCliInput(argv)));
    process.stdout.write(`${JSON.stringify(decision, null, 2)}\n`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown route error.";
    const cliCode =
      isRecord(error) && typeof error.cliCode === "string"
        ? (error.cliCode as CliErrorCode)
        : /forceMode/.test(message)
          ? "invalid_force_mode"
          : "invalid_request";
    process.stdout.write(`${JSON.stringify(toCliError(cliCode, message), null, 2)}\n`);
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main(process.argv);
}
