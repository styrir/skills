import { existsSync, readFileSync, statSync } from "node:fs";
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

function readJsonlIds(blockers: ArtifactGateIssue[], runDir: string, relativePath: string, idField: string): Set<string> {
  const ids = new Set<string>();
  const text = readText(blockers, runDir, relativePath);
  for (const [index, line] of text.split("\n").entries()) {
    if (!line.trim()) {
      continue;
    }
    try {
      const row = JSON.parse(line);
      if (isRecord(row) && typeof row[idField] === "string" && row[idField]) {
        ids.add(row[idField] as string);
      }
    } catch {
      blockers.push(issue("invalid_jsonl", relativePath, `${relativePath} line ${index + 1} is not valid JSON.`));
    }
  }
  return ids;
}

// deep_search_local validates a real deep-search-mcp run dir. strict render-report-bundle owns the report checks
// (sections, citations, claim support, contradictions) and only promotes report.candidate.md to report.md on pass.
function validateDeepLocal(blockers: ArtifactGateIssue[], runDir: string) {
  requireFile(blockers, runDir, "run_manifest.json", "missing_run_manifest");
  const manifest = readJson(blockers, runDir, "run_manifest.json");
  if (existsSync(join(runDir, "run_manifest.json")) && typeof manifest.run_id !== "string") {
    blockers.push(issue("missing_run_id", "run_manifest.json", "run_manifest.json must come from deep-search-mcp init-run."));
  }
  if (readJsonlIds(blockers, runDir, "sources.jsonl", "source_id").size === 0) {
    blockers.push(issue("missing_registered_sources", "sources.jsonl", "sources.jsonl must register at least one source."));
  }
  const claimIds = readJsonlIds(blockers, runDir, "claims.jsonl", "claim_id");
  if (claimIds.size === 0) {
    blockers.push(issue("missing_claims", "claims.jsonl", "claims.jsonl must record at least one claim."));
  }

  const reportPath = join(runDir, "report.md");
  if (!existsSync(reportPath) || !statSync(reportPath).isFile()) {
    const candidate = existsSync(join(runDir, "report.candidate.md"));
    blockers.push(
      issue(
        candidate ? "report_bundle_not_passed" : "missing_report",
        "report.md",
        candidate
          ? "report.candidate.md exists but report.md does not; strict render-report-bundle has not passed."
          : "report.md is required; run render-report-bundle with {\"strict\":true}.",
      ),
    );
    return;
  }

  const markers = new Set([...readFileSync(reportPath, "utf8").matchAll(/\[claim:([A-Za-z0-9_-]+)\]/g)].map((match) => match[1]));
  if (markers.size === 0) {
    blockers.push(issue("missing_report_claim_markers", "report.md", "report.md must carry [claim:<id>] markers."));
  }
  for (const marker of markers) {
    if (!claimIds.has(marker)) {
      blockers.push(issue("unknown_report_claim", "report.md", `Report cites unknown claim '${marker}'.`));
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
    validateDeepLocal(blockers, runDir);
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
