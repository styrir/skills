import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
import { validateLedger } from "./styrir-search-gate.ts";

type ArtifactMode = "styrir_plus" | "deep_search_local";
type GateStatus = "pass" | "fail";

export interface ArtifactGateIssue {
  code: string;
  path: string;
  message: string;
}

export interface ArtifactGateResult {
  gateStatus: GateStatus;
  mode: ArtifactMode;
  runDir: string;
  blockers: ArtifactGateIssue[];
  warnings: ArtifactGateIssue[];
}

const MIN_FINDINGS_WORDS = 40;
const MIN_REPORT_WORDS = 60;

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function issue(code: string, path: string, message: string): ArtifactGateIssue {
  return { code, path, message };
}

function requireFile(blockers: ArtifactGateIssue[], runDir: string, relativePath: string, code: string) {
  const path = join(runDir, relativePath);
  if (!existsSync(path) || !statSync(path).isFile()) {
    blockers.push(issue(code, relativePath, `${relativePath} is required.`));
  }
}

function readJson(blockers: ArtifactGateIssue[], runDir: string, relativePath: string): Record<string, unknown> {
  const path = join(runDir, relativePath);
  if (!existsSync(path) || !statSync(path).isFile()) {
    return {};
  }

  try {
    const parsed = JSON.parse(readFileSync(path, "utf8"));
    if (!isRecord(parsed)) {
      blockers.push(issue("invalid_json_object", relativePath, `${relativePath} must contain a JSON object.`));
      return {};
    }
    return parsed;
  } catch (error) {
    const message = error instanceof Error ? error.message : "could not parse JSON";
    blockers.push(issue("invalid_json", relativePath, `${relativePath} is not valid JSON: ${message}`));
    return {};
  }
}

function readText(blockers: ArtifactGateIssue[], runDir: string, relativePath: string): string {
  const path = join(runDir, relativePath);
  if (!existsSync(path) || !statSync(path).isFile()) {
    return "";
  }
  return readFileSync(path, "utf8");
}

function wordCount(text: string): number {
  return text.trim().split(/\s+/).filter(Boolean).length;
}

function headingCount(text: string): number {
  return (text.match(/^##+\s+\S.+$/gm) ?? []).length;
}

function extractRegistrySourceIds(registry: Record<string, unknown>): Set<string> {
  const ids = new Set<string>();
  const sources = Array.isArray(registry.sources) ? registry.sources : [];
  for (const source of sources) {
    if (isRecord(source) && typeof source.id === "string" && source.id.trim()) {
      ids.add(source.id);
    }
  }
  return ids;
}

function extractSourceCitations(text: string): Set<string> {
  return new Set([...text.matchAll(/\[(s[0-9][A-Za-z0-9_-]*)\]/g)].map((match) => match[1]));
}

function validatePlan(blockers: ArtifactGateIssue[], runDir: string, mode: ArtifactMode) {
  requireFile(blockers, runDir, "plan.json", "missing_plan");
  const plan = readJson(blockers, runDir, "plan.json");
  const facets = plan.facets;
  if (plan.mode !== mode) {
    blockers.push(issue("plan_mode_mismatch", "plan.json", `plan.json mode must be ${mode}.`));
  }
  if (!Array.isArray(facets) || facets.length === 0) {
    blockers.push(issue("missing_planner_facets", "plan.json", "plan.json must include at least one planner facet."));
  }
}

function validateSourceRegistry(blockers: ArtifactGateIssue[], runDir: string): Set<string> {
  requireFile(blockers, runDir, "source-registry.json", "missing_source_registry");
  const registry = readJson(blockers, runDir, "source-registry.json");
  const sourceIds = extractRegistrySourceIds(registry);
  if (sourceIds.size === 0) {
    blockers.push(issue("missing_registered_sources", "source-registry.json", "source-registry.json must include sources[]."));
  }
  return sourceIds;
}

function validateGateResult(blockers: ArtifactGateIssue[], runDir: string) {
  requireFile(blockers, runDir, "gate-result.json", "missing_gate_result");
  const gateResult = readJson(blockers, runDir, "gate-result.json");
  if (gateResult.gateStatus !== "pass") {
    blockers.push(issue("artifact_gate_not_passed", "gate-result.json", "gate-result.json must have gateStatus='pass'."));
  }
}

function validatePlus(blockers: ArtifactGateIssue[], warnings: ArtifactGateIssue[], runDir: string) {
  validatePlan(blockers, runDir, "styrir_plus");
  validateSourceRegistry(blockers, runDir);
  requireFile(blockers, runDir, "ledger.json", "missing_ledger");
  requireFile(blockers, runDir, "contradiction-sweep.md", "missing_contradiction_sweep");
  const ledgerPath = join(runDir, "ledger.json");
  if (existsSync(ledgerPath) && statSync(ledgerPath).isFile()) {
    const ledgerResult = validateLedger(readJson(blockers, runDir, "ledger.json"));
    for (const gateBlocker of ledgerResult.blockers) {
      blockers.push(issue(`ledger_${gateBlocker.code}`, "ledger.json", gateBlocker.message));
    }
    for (const gateWarning of ledgerResult.warnings) {
      warnings.push(issue(`ledger_${gateWarning.code}`, "ledger.json", gateWarning.message));
    }
  }
  validateGateResult(blockers, runDir);
}

function validateDeepLocal(blockers: ArtifactGateIssue[], warnings: ArtifactGateIssue[], runDir: string) {
  validatePlan(blockers, runDir, "deep_search_local");
  const sourceIds = validateSourceRegistry(blockers, runDir);
  const notesDir = join(runDir, "research-notes");
  if (!existsSync(notesDir) || !statSync(notesDir).isDirectory()) {
    blockers.push(issue("missing_research_notes", "research-notes", "research-notes/*.md is required."));
  } else {
    const notes = readdirSync(notesDir).filter((name) => name.endsWith(".md"));
    if (notes.length === 0) {
      blockers.push(issue("missing_research_notes", "research-notes", "research-notes/*.md is required."));
    }
  }
  requireFile(blockers, runDir, "consolidated-findings.md", "missing_consolidated_findings");
  requireFile(blockers, runDir, "report.md", "missing_report");
  const findingsCitations = validateFindings(blockers, runDir, sourceIds);
  const reportCitations = validateReport(blockers, runDir, sourceIds);
  warnOnUncitedSources(warnings, sourceIds, new Set([...findingsCitations, ...reportCitations]));
  validateGateResult(blockers, runDir);
}

function validateFindings(blockers: ArtifactGateIssue[], runDir: string, sourceIds: Set<string>): Set<string> {
  const text = readText(blockers, runDir, "consolidated-findings.md");
  if (!text) {
    return new Set();
  }
  if (wordCount(text) < MIN_FINDINGS_WORDS) {
    blockers.push(issue("findings_too_short", "consolidated-findings.md", "consolidated-findings.md must contain substantive findings."));
  }
  if (headingCount(text) === 0) {
    blockers.push(issue("missing_findings_sections", "consolidated-findings.md", "consolidated-findings.md must contain at least one section heading."));
  }
  const citations = extractSourceCitations(text);
  for (const citation of citations) {
    if (!sourceIds.has(citation)) {
      blockers.push(issue("unknown_findings_citation", "consolidated-findings.md", `Findings cite unknown source id '${citation}'.`));
    }
  }
  return citations;
}

function validateReport(blockers: ArtifactGateIssue[], runDir: string, sourceIds: Set<string>): Set<string> {
  const text = readText(blockers, runDir, "report.md");
  if (!text) {
    return new Set();
  }

  if (wordCount(text) < MIN_REPORT_WORDS) {
    blockers.push(issue("report_too_short", "report.md", "report.md must contain substantive final prose."));
  }
  if (headingCount(text) < 2) {
    blockers.push(issue("missing_report_sections", "report.md", "report.md must contain findings and sources sections."));
  }
  if (!/^##+\s+Sources\b/im.test(text)) {
    blockers.push(issue("missing_sources_section", "report.md", "report.md must contain a Sources section."));
  }

  const citations = extractSourceCitations(text);
  if (citations.size === 0) {
    blockers.push(issue("missing_report_citations", "report.md", "report.md must cite source ids from source-registry.json."));
  }
  for (const citation of citations) {
    if (!sourceIds.has(citation)) {
      blockers.push(issue("unknown_report_citation", "report.md", `Report cites unknown source id '${citation}'.`));
    }
  }
  return citations;
}

function warnOnUncitedSources(warnings: ArtifactGateIssue[], sourceIds: Set<string>, citations: Set<string>) {
  for (const sourceId of sourceIds) {
    if (!citations.has(sourceId)) {
      warnings.push(issue("uncited_registered_source", "source-registry.json", `Registered source '${sourceId}' is not cited in findings or report.`));
    }
  }
}

export function validateArtifactRun(mode: ArtifactMode, runDir: string): ArtifactGateResult {
  const blockers: ArtifactGateIssue[] = [];
  const warnings: ArtifactGateIssue[] = [];

  if (!existsSync(runDir) || !statSync(runDir).isDirectory()) {
    blockers.push(issue("missing_run_dir", runDir, "Run directory does not exist."));
  } else if (mode === "styrir_plus") {
    validatePlus(blockers, warnings, runDir);
  } else {
    validateDeepLocal(blockers, warnings, runDir);
  }

  return {
    gateStatus: blockers.length === 0 ? "pass" : "fail",
    mode,
    runDir,
    blockers,
    warnings,
  };
}

function readCliArgs(argv: string[]): { mode: ArtifactMode; runDir: string } {
  const mode = argv[2];
  const runDir = argv[3];
  if (mode !== "styrir_plus" && mode !== "deep_search_local") {
    throw new Error("Usage: styrir-artifact-gate.ts <styrir_plus|deep_search_local> <run-dir>");
  }
  if (!runDir) {
    throw new Error("Run directory is required.");
  }
  return { mode, runDir };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const { mode, runDir } = readCliArgs(process.argv);
    const result = validateArtifactRun(mode, runDir);
    process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
    process.exitCode = result.gateStatus === "pass" ? 0 : 1;
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown artifact gate error.";
    process.stdout.write(`${JSON.stringify({ error: { message } }, null, 2)}\n`);
    process.exitCode = 1;
  }
}
