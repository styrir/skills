import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

type GateStatus = "pass" | "fail";
type Severity = "blocker" | "warning";

export interface GateIssue {
  severity: Severity;
  code: string;
  path: string;
  message: string;
}

export interface GateResult {
  gateStatus: GateStatus;
  blockers: GateIssue[];
  warnings: GateIssue[];
  counts: {
    entries: number;
    sources: number;
    proofGaps: number;
  };
}

const ALLOWED_MODES = new Set([
  "direct_search",
  "styrir_search",
  "styrir_plus",
  "deep_search_local",
  "nvidia_aiq_handoff",
  "aiq_deep_tbd",
  "structured_search",
  "structured_plus",
  "deep_research",
]);

const ALLOWED_SOURCE_TYPES = new Set([
  "official",
  "news",
  "blog",
  "analysis",
  "academic",
  "social",
  "legal",
  "product",
  "comparison",
  "repo",
  "memory",
  "local",
]);

const PRIMARY_SOURCE_TYPES = new Set(["official", "legal", "product", "academic", "repo", "local"]);
const ALLOWED_CONFIDENCE = new Set(["high", "medium", "low"]);
const INFERENCE_RE = /\b(suggests?|indicates?|means|implies?|therefore|proves?|likely|it follows that)\b/i;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function asRecord(value: unknown): Record<string, unknown> {
  return isRecord(value) ? value : {};
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function asBoolean(value: unknown): boolean | undefined {
  return typeof value === "boolean" ? value : undefined;
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function pushIssue(issues: GateIssue[], code: string, path: string, message: string, severity: Severity = "blocker") {
  issues.push({ severity, code, path, message });
}

function firstNumber(record: Record<string, unknown>, keys: string[]): number | undefined {
  for (const key of keys) {
    const value = asNumber(record[key]);
    if (value !== undefined) {
      return value;
    }
  }
  return undefined;
}

function looksBundled(text: string): boolean {
  const sentences = text.split(/[.!?]+/).map((part) => part.trim()).filter(Boolean);
  return sentences.length > 1 || /\b(and also|as well as)\b/i.test(text) || text.includes(";");
}

export function validateLedger(input: unknown): GateResult {
  const blockers: GateIssue[] = [];
  const warnings: GateIssue[] = [];
  const ledger = asRecord(input);
  const meta = asRecord(ledger.meta);
  const entries = asArray(ledger.entries);
  const sources = asArray(ledger.sources);
  const proofGaps = asArray(ledger.proofGaps ?? ledger.proof_gaps);

  if (!isRecord(input)) {
    pushIssue(blockers, "invalid_root", "$", "Ledger must be a JSON object.");
  }

  const mode = asString(meta.mode);
  if (!mode) {
    pushIssue(blockers, "missing_mode", "$.meta.mode", "Ledger meta.mode is required.");
  } else if (!ALLOWED_MODES.has(mode)) {
    pushIssue(blockers, "invalid_mode", "$.meta.mode", `Unknown mode '${mode}'.`);
  }

  if (entries.length === 0) {
    pushIssue(blockers, "missing_entries", "$.entries", "Ledger must contain at least one evidence entry.");
  }

  if (sources.length === 0) {
    pushIssue(blockers, "missing_sources", "$.sources", "Ledger must contain a sources appendix.");
  }

  if (proofGaps.length === 0) {
    pushIssue(blockers, "missing_proof_gaps", "$.proofGaps", "Proof gaps are mandatory, even when the gap is small.");
  }

  validateBudget(meta, blockers);

  const sourceById = new Map<string, Record<string, unknown>>();
  sources.forEach((rawSource, sourceIndex) => {
    const source = asRecord(rawSource);
    const path = `$.sources[${sourceIndex}]`;
    const id = asString(source.id);
    const url = asString(source.url);
    const sourceType = asString(source.sourceType ?? source.source_type);

    if (!id) {
      pushIssue(blockers, "missing_source_id", `${path}.id`, "Every source needs a stable id.");
    } else if (sourceById.has(id)) {
      pushIssue(blockers, "duplicate_source_id", `${path}.id`, `Duplicate source id '${id}'.`);
    } else {
      sourceById.set(id, source);
    }

    if (!url) {
      pushIssue(blockers, "missing_source_url", `${path}.url`, "Every source needs a URL or local locator.");
    }

    if (sourceType && !ALLOWED_SOURCE_TYPES.has(sourceType)) {
      pushIssue(blockers, "invalid_source_type", `${path}.sourceType`, `Unknown source type '${sourceType}'.`);
    }
  });

  entries.forEach((rawEntry, entryIndex) => {
    validateEntry(asRecord(rawEntry), entryIndex, sourceById, blockers, warnings);
  });

  proofGaps.forEach((rawGap, gapIndex) => {
    const gap = asRecord(rawGap);
    const attemptedQueries = asArray(gap.attemptedQueries ?? gap.attempted_queries);
    if (!asString(gap.description)) {
      pushIssue(blockers, "missing_proof_gap_description", `$.proofGaps[${gapIndex}].description`, "Each proof gap needs a description.");
    }
    if (attemptedQueries.length === 0) {
      pushIssue(blockers, "missing_attempted_queries", `$.proofGaps[${gapIndex}].attemptedQueries`, "Each proof gap needs attempted queries.");
    }
  });

  return {
    gateStatus: blockers.length > 0 ? "fail" : "pass",
    blockers,
    warnings,
    counts: {
      entries: entries.length,
      sources: sources.length,
      proofGaps: proofGaps.length,
    },
  };
}

function validateBudget(meta: Record<string, unknown>, blockers: GateIssue[]) {
  const budget = asRecord(meta.budget);
  const queriesRun = firstNumber(meta, ["totalQueriesRun", "total_queries_run", "searchCalls", "search_calls"]);
  const fetchesRun = firstNumber(meta, ["totalSourcesFetched", "total_sources_extracted", "totalSourcesExtracted", "fetchCalls", "fetch_calls"]);
  const maxQueries = firstNumber(budget, ["maxSearchQueries", "max_search_queries", "maxQueries", "max_queries"]);
  const maxFetches = firstNumber(budget, ["maxFetches", "max_sources_to_extract", "maxSourcesToExtract", "max_sources_fetched"]);

  if (queriesRun !== undefined && maxQueries !== undefined && queriesRun > maxQueries) {
    pushIssue(
      blockers,
      "search_budget_exceeded",
      "$.meta.totalQueriesRun",
      `Search budget exceeded: ran ${queriesRun}, max ${maxQueries}.`,
    );
  }

  if (fetchesRun !== undefined && maxFetches !== undefined && fetchesRun > maxFetches) {
    pushIssue(
      blockers,
      "fetch_budget_exceeded",
      "$.meta.totalSourcesFetched",
      `Fetch budget exceeded: fetched ${fetchesRun}, max ${maxFetches}.`,
    );
  }
}

function validateEntry(
  entry: Record<string, unknown>,
  entryIndex: number,
  sourceById: Map<string, Record<string, unknown>>,
  blockers: GateIssue[],
  warnings: GateIssue[],
) {
  const path = `$.entries[${entryIndex}]`;
  const id = asString(entry.id);
  const observation = asString(entry.observation);
  const sourceId = asString(entry.sourceId ?? entry.source_id);
  const sourceUrl = asString(entry.sourceUrl ?? entry.source_url);
  const sourceType = asString(entry.sourceType ?? entry.source_type);
  const confidence = asString(entry.confidence);
  const dateObserved = asString(entry.dateObserved ?? entry.date_observed);

  if (!id) {
    pushIssue(blockers, "missing_entry_id", `${path}.id`, "Every entry needs a stable id.");
  }

  if (!observation) {
    pushIssue(blockers, "missing_observation", `${path}.observation`, "Every entry needs a factual observation.");
  } else {
    if (INFERENCE_RE.test(observation)) {
      pushIssue(
        blockers,
        "inference_in_observation",
        `${path}.observation`,
        "Observation contains inference language; move interpretation to possibleImplication.",
      );
    }

    if (looksBundled(observation)) {
      pushIssue(
        warnings,
        "possibly_bundled_observation",
        `${path}.observation`,
        "Observation may bundle multiple facts; split it if each clause needs independent support.",
        "warning",
      );
    }
  }

  if (!sourceId) {
    pushIssue(blockers, "missing_source_id_reference", `${path}.sourceId`, "Every entry must reference a source id.");
  }

  if (!sourceUrl) {
    pushIssue(blockers, "missing_entry_source_url", `${path}.sourceUrl`, "Every entry must include the source URL or locator.");
  }

  const source = sourceById.get(sourceId);
  if (sourceId && !source) {
    pushIssue(blockers, "source_missing_from_appendix", `${path}.sourceId`, `Entry references missing source '${sourceId}'.`);
  } else if (source) {
    const fetched = asBoolean(source.fetched);
    const appendixUrl = asString(source.url);
    const appendixType = asString(source.sourceType ?? source.source_type);

    if (fetched !== true) {
      pushIssue(blockers, "source_not_fetched", `${path}.sourceId`, `Source '${sourceId}' was not fetched/read.`);
    }

    if (sourceUrl && appendixUrl && sourceUrl !== appendixUrl) {
      pushIssue(blockers, "source_url_mismatch", `${path}.sourceUrl`, `Entry URL does not match source '${sourceId}'.`);
    }

    if (sourceType && appendixType && sourceType !== appendixType) {
      pushIssue(blockers, "source_type_mismatch", `${path}.sourceType`, `Entry source type does not match source '${sourceId}'.`);
    }
  }

  if (!sourceType) {
    pushIssue(blockers, "missing_source_type", `${path}.sourceType`, "Every entry needs a source type.");
  } else if (!ALLOWED_SOURCE_TYPES.has(sourceType)) {
    pushIssue(blockers, "invalid_entry_source_type", `${path}.sourceType`, `Unknown source type '${sourceType}'.`);
  }

  if (!confidence) {
    pushIssue(blockers, "missing_confidence", `${path}.confidence`, "Every entry needs confidence: high, medium, or low.");
  } else if (!ALLOWED_CONFIDENCE.has(confidence)) {
    pushIssue(blockers, "invalid_confidence", `${path}.confidence`, `Unknown confidence '${confidence}'.`);
  } else if (confidence === "high" && !PRIMARY_SOURCE_TYPES.has(sourceType)) {
    pushIssue(
      blockers,
      "high_confidence_non_primary",
      `${path}.confidence`,
      "High confidence is reserved for primary, official, legal, product, academic, repo, or local sources.",
    );
  }

  if (!dateObserved) {
    pushIssue(blockers, "missing_date_observed", `${path}.dateObserved`, "Every entry needs a dateObserved value.");
  } else if (!/^\d{4}-\d{2}-\d{2}$/.test(dateObserved)) {
    pushIssue(blockers, "invalid_date_observed", `${path}.dateObserved`, "dateObserved must use YYYY-MM-DD.");
  }
}

function readJsonInput(pathArg: string | undefined): unknown {
  const raw = pathArg ? readFileSync(pathArg, "utf8") : readFileSync(0, "utf8");
  return JSON.parse(raw);
}

function main() {
  try {
    const payload = readJsonInput(process.argv[2]);
    const result = validateLedger(payload);
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    process.exitCode = result.gateStatus === "pass" ? 0 : 1;
  } catch (error) {
    const issue: GateIssue = {
      severity: "blocker",
      code: "gate_runtime_error",
      path: "$",
      message: error instanceof Error ? error.message : String(error),
    };
    process.stdout.write(
      `${JSON.stringify({ gateStatus: "fail", blockers: [issue], warnings: [], counts: { entries: 0, sources: 0, proofGaps: 0 } }, null, 2)}\n`,
    );
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
