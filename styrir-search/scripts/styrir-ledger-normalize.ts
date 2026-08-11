import { readFileSync } from "node:fs";
import { pathToFileURL } from "node:url";

type JsonValue = string | number | boolean | null | JsonObject | JsonValue[];
type JsonObject = { [key: string]: JsonValue };

interface CanonicalBudget {
  maxSearchQueries?: number;
  maxFetches?: number;
}

interface CanonicalMeta {
  mode: string;
  searchId: string;
  totalQueriesRun?: number;
  totalSourcesFetched?: number;
  budget: CanonicalBudget;
}

interface CanonicalEntry {
  id: string;
  observation: string;
  possibleImplication: string;
  sourceId: string;
  sourceUrl: string;
  sourceType: string;
  dateObserved: string;
  confidence: string;
  entity?: string;
  signalType?: string;
  relevance?: number;
}

interface CanonicalProofGap {
  description: string;
  attemptedQueries: string[];
}

interface CanonicalSource {
  id: string;
  url: string;
  title?: string;
  sourceType?: string;
  fetched?: boolean;
}

export interface CanonicalLedger {
  meta: CanonicalMeta;
  entries: CanonicalEntry[];
  proofGaps: CanonicalProofGap[];
  sources: CanonicalSource[];
}

const MODE_ALIASES = new Map<string, string>([
  ["structured_search", "styrir_search"],
  ["structured_plus", "styrir_plus"],
  ["deep_research", "deep_search_local"],
  ["aiq_deep_tbd", "nvidia_aiq_handoff"],
]);

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

function firstString(record: Record<string, unknown>, keys: string[]): string {
  for (const key of keys) {
    const value = asString(record[key]);
    if (value) {
      return value;
    }
  }
  return "";
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

export function normalizeMode(mode: string): string {
  return MODE_ALIASES.get(mode) ?? mode;
}

function parseScalar(value: string): JsonValue {
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  if (value === "null") {
    return null;
  }
  if (/^-?\d+(?:\.\d+)?$/.test(value) && !/^\d{4}-\d{2}-\d{2}$/.test(value)) {
    return Number(value);
  }
  if (
    (value.startsWith('"') && value.endsWith('"')) ||
    (value.startsWith("'") && value.endsWith("'"))
  ) {
    return value.slice(1, -1);
  }
  return value;
}

function splitYamlKeyValue(content: string): { key: string; value: string | null } {
  if (content.endsWith(":")) {
    return { key: content.slice(0, -1).trim(), value: null };
  }

  const separator = content.indexOf(": ");
  if (separator === -1) {
    throw new Error(`Malformed YAML: expected 'key: value' or 'key:' but got '${content}'.`);
  }

  return {
    key: content.slice(0, separator).trim(),
    value: content.slice(separator + 2),
  };
}

interface YamlLine {
  raw: string;
  indent: number;
  content: string;
}

function parseYamlSubset(input: string): JsonValue {
  const lines = input
    .replace(/\r/g, "")
    .split("\n")
    .map((raw) => {
      const indent = raw.match(/^ */)?.[0].length ?? 0;
      return { raw, indent, content: raw.trim() };
    })
    .filter((line) => line.content.length > 0);

  for (const line of lines) {
    if (line.raw.includes("\t")) {
      throw new Error("Malformed YAML: tabs are not supported.");
    }
    if (/: *[\[{]/.test(line.content) || /^-\s*[\[{]/.test(line.content)) {
      throw new Error("unsupported_yaml_shape: inline objects and lists are not supported.");
    }
  }

  let index = 0;

  function parseNode(expectedIndent: number): JsonValue {
    const line = lines[index];
    if (!line || line.indent < expectedIndent) {
      throw new Error("Malformed YAML: unexpected indentation.");
    }
    if (line.indent !== expectedIndent) {
      throw new Error("Malformed YAML: inconsistent indentation.");
    }
    return line.content.startsWith("-") ? parseSequence(expectedIndent) : parseMapping(expectedIndent);
  }

  function parseMapping(expectedIndent: number): JsonObject {
    const record: JsonObject = {};

    while (index < lines.length) {
      const line = lines[index];
      if (line.indent < expectedIndent) {
        break;
      }
      if (line.indent !== expectedIndent) {
        throw new Error("Malformed YAML: inconsistent indentation inside mapping.");
      }
      if (line.content.startsWith("-")) {
        break;
      }

      const { key, value } = splitYamlKeyValue(line.content);
      if (!key) {
        throw new Error("Malformed YAML: empty key.");
      }
      index += 1;

      if (value === null) {
        const next = lines[index];
        if (!next || next.indent <= expectedIndent) {
          record[key] = {};
        } else {
          record[key] = parseNode(next.indent);
        }
      } else {
        record[key] = parseScalar(value);
      }
    }

    return record;
  }

  function parseSequence(expectedIndent: number): JsonValue[] {
    const items: JsonValue[] = [];

    while (index < lines.length) {
      const line = lines[index];
      if (line.indent < expectedIndent) {
        break;
      }
      if (line.indent !== expectedIndent) {
        throw new Error("Malformed YAML: inconsistent indentation inside sequence.");
      }
      if (!line.content.startsWith("-")) {
        break;
      }

      const remainder = line.content.slice(1).trim();
      index += 1;

      if (!remainder) {
        const next = lines[index];
        if (!next || next.indent <= expectedIndent) {
          throw new Error("Malformed YAML: list item is missing a value.");
        }
        items.push(parseNode(next.indent));
        continue;
      }

      if (remainder.endsWith(":") || remainder.includes(": ")) {
        const { key, value } = splitYamlKeyValue(remainder);
        const item: JsonObject = {};
        if (value === null) {
          const next = lines[index];
          item[key] = next && next.indent > expectedIndent ? parseNode(next.indent) : {};
        } else {
          item[key] = parseScalar(value);
        }
        const next = lines[index];
        if (next && next.indent > expectedIndent) {
          const continuation = parseNode(next.indent);
          if (!isRecord(continuation)) {
            throw new Error("Malformed YAML: list item continuation must be a mapping.");
          }
          Object.assign(item, continuation);
        }
        items.push(item);
        continue;
      }

      const next = lines[index];
      if (next && next.indent > expectedIndent) {
        throw new Error("Malformed YAML: scalar list item cannot have nested content.");
      }
      items.push(parseScalar(remainder));
    }

    return items;
  }

  if (lines.length === 0) {
    throw new Error("Malformed YAML: input is empty.");
  }

  const parsed = parseNode(lines[0].indent);
  if (index !== lines.length) {
    throw new Error("Malformed YAML: trailing content could not be parsed.");
  }
  return parsed;
}

export function parseLedgerText(text: string): Record<string, unknown> {
  const raw = text.trim();
  if (!raw) {
    throw new Error("Ledger input is empty.");
  }

  const parsed = raw.startsWith("{") || raw.startsWith("[")
    ? JSON.parse(raw)
    : parseYamlSubset(raw);

  if (!isRecord(parsed)) {
    throw new Error("Ledger root must be an object.");
  }

  return parsed;
}

function parseLedgerInput(input: unknown): Record<string, unknown> {
  if (isRecord(input)) {
    return input;
  }

  if (typeof input !== "string") {
    throw new Error("Ledger input must be an object or a string.");
  }

  const raw = input.trim();
  if (!raw) {
    throw new Error("Ledger input is empty.");
  }

  return parseLedgerText(raw);
}

function normalizeBudget(meta: Record<string, unknown>): CanonicalBudget {
  const budget = asRecord(meta.budget);
  const maxSearchQueries = firstNumber(budget, ["maxSearchQueries", "max_search_queries", "maxQueries", "max_queries"]);
  const maxFetches = firstNumber(budget, ["maxFetches", "max_sources_to_extract", "maxSourcesToExtract", "max_sources_fetched"]);

  return {
    ...(maxSearchQueries !== undefined ? { maxSearchQueries } : {}),
    ...(maxFetches !== undefined ? { maxFetches } : {}),
  };
}

function normalizeProofGaps(input: Record<string, unknown>): CanonicalProofGap[] {
  return asArray(input.proofGaps ?? input.proof_gaps).map((rawGap) => {
    const gap = asRecord(rawGap);
    return {
      description: firstString(gap, ["description"]),
      attemptedQueries: asArray(gap.attemptedQueries ?? gap.attempted_queries).map((query) => asString(query)).filter(Boolean),
    };
  });
}

interface SourceRegistry {
  sources: CanonicalSource[];
  byId: Map<string, CanonicalSource>;
  byUrl: Map<string, CanonicalSource>;
  nextId: number;
}

function createRegistry(): SourceRegistry {
  return {
    sources: [],
    byId: new Map(),
    byUrl: new Map(),
    nextId: 1,
  };
}

function nextGeneratedSourceId(registry: SourceRegistry): string {
  while (registry.byId.has(`s${registry.nextId}`)) {
    registry.nextId += 1;
  }
  const id = `s${registry.nextId}`;
  registry.nextId += 1;
  return id;
}

function upsertSource(
  registry: SourceRegistry,
  rawSource: Record<string, unknown>,
  options: { explicitAppendix: boolean },
): CanonicalSource {
  const url = firstString(rawSource, ["url", "sourceUrl", "source_url"]);
  const explicitId = firstString(rawSource, ["id", "sourceId", "source_id"]);
  const sourceType = firstString(rawSource, ["sourceType", "source_type"]);
  const title = firstString(rawSource, ["title"]);
  const fetched = asBoolean(rawSource.fetched);

  const existingById = explicitId ? registry.byId.get(explicitId) : undefined;
  const existingByUrl = url ? registry.byUrl.get(url) : undefined;
  const existing = existingById ?? existingByUrl;
  const id = explicitId || existing?.id || nextGeneratedSourceId(registry);

  const source: CanonicalSource = existing ?? { id, url };
  source.id = id;
  if (url) {
    source.url = url;
  }
  if (title) {
    source.title = title;
  }
  if (sourceType) {
    source.sourceType = sourceType;
  }
  if (fetched !== undefined) {
    source.fetched = fetched;
  } else if (options.explicitAppendix && source.fetched === undefined && url) {
    source.fetched = true;
  }

  if (!existing) {
    registry.sources.push(source);
  }
  registry.byId.set(source.id, source);
  if (source.url) {
    registry.byUrl.set(source.url, source);
  }

  return source;
}

function normalizeEntries(input: Record<string, unknown>, registry: SourceRegistry): CanonicalEntry[] {
  return asArray(input.entries).map((rawEntry, index) => {
    const entry = asRecord(rawEntry);
    const sourceUrl = firstString(entry, ["sourceUrl", "source_url", "url"]);
    const explicitSourceId = firstString(entry, ["sourceId", "source_id"]);
    const matchedSourceById = explicitSourceId ? registry.byId.get(explicitSourceId) : undefined;
    const matchedSourceByUrl = sourceUrl ? registry.byUrl.get(sourceUrl) : undefined;
    const matchedSource = matchedSourceById ?? matchedSourceByUrl;
    const sourceType = firstString(entry, ["sourceType", "source_type"]) || matchedSource?.sourceType || "analysis";
    const source = matchedSource ?? upsertSource(
      registry,
      {
        id: explicitSourceId,
        url: sourceUrl,
        sourceType,
      },
      { explicitAppendix: false },
    );

    return {
      id: firstString(entry, ["id"]) || `e${index + 1}`,
      observation: firstString(entry, ["observation", "fact", "claim", "text"]),
      possibleImplication: firstString(entry, ["possibleImplication", "possible_implication", "implication"]),
      sourceId: source.id,
      sourceUrl: sourceUrl || source.url,
      sourceType,
      dateObserved: firstString(entry, ["dateObserved", "date_observed"]),
      confidence: firstString(entry, ["confidence"]) || "medium",
      ...(firstString(entry, ["entity"]) ? { entity: firstString(entry, ["entity"]) } : {}),
      ...(firstString(entry, ["signalType", "signal_type"]) ? { signalType: firstString(entry, ["signalType", "signal_type"]) } : {}),
      ...(asNumber(entry.relevance) !== undefined ? { relevance: asNumber(entry.relevance) } : {}),
    };
  });
}

export function normalizeLedger(input: unknown): CanonicalLedger {
  const ledger = parseLedgerInput(input);
  const meta = asRecord(ledger.meta);
  const registry = createRegistry();
  const sourceAppendix = asArray(ledger.sourceAppendix ?? ledger.source_appendix ?? ledger.sources);

  for (const rawSource of sourceAppendix) {
    upsertSource(registry, asRecord(rawSource), { explicitAppendix: true });
  }

  return {
    meta: {
      mode: normalizeMode(firstString(meta, ["mode"])),
      searchId: firstString(meta, ["searchId", "search_id", "id"]),
      ...(firstNumber(meta, ["totalQueriesRun", "total_queries_run", "searchCalls", "search_calls"]) !== undefined
        ? { totalQueriesRun: firstNumber(meta, ["totalQueriesRun", "total_queries_run", "searchCalls", "search_calls"]) }
        : {}),
      ...(firstNumber(meta, ["totalSourcesFetched", "total_sources_fetched", "totalSourcesExtracted", "total_sources_extracted", "fetchCalls", "fetch_calls"]) !== undefined
        ? { totalSourcesFetched: firstNumber(meta, ["totalSourcesFetched", "total_sources_fetched", "totalSourcesExtracted", "total_sources_extracted", "fetchCalls", "fetch_calls"]) }
        : {}),
      budget: normalizeBudget(meta),
    },
    entries: normalizeEntries(ledger, registry),
    proofGaps: normalizeProofGaps(ledger),
    sources: registry.sources,
  };
}

function readInput(pathArg: string | undefined): string {
  return pathArg ? readFileSync(pathArg, "utf8") : readFileSync(0, "utf8");
}

function main() {
  try {
    const normalized = normalizeLedger(readInput(process.argv[2]));
    process.stdout.write(`${JSON.stringify(normalized, null, 2)}\n`);
    process.exitCode = 0;
  } catch (error) {
    process.stderr.write(`${error instanceof Error ? error.message : String(error)}\n`);
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main();
}
