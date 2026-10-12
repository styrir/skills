import { appendFileSync, existsSync, mkdirSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { pathToFileURL } from "node:url";

export const PROGRESS_PHASES = [
  "routing",
  "planning",
  "searching",
  "fetching",
  "ledger",
  "contradiction_sweep",
  "gate",
  "synthesis",
  "handoff",
] as const;

export type ProgressPhase = (typeof PROGRESS_PHASES)[number];

export interface ProgressEventInput {
  phase: ProgressPhase;
  mode: string;
  message: string;
  budgetUsed?: number;
  budgetLimit?: number;
  currentSourceId?: string;
}

export interface ProgressEvent extends ProgressEventInput {
  timestamp: string;
}

const PHASE_INDEX = new Map<ProgressPhase, number>(PROGRESS_PHASES.map((phase, index) => [phase, index]));
const REQUIRED_PREDECESSORS: Partial<Record<ProgressPhase, ProgressPhase>> = {
  gate: "ledger",
  synthesis: "gate",
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isProgressPhase(value: unknown): value is ProgressPhase {
  return typeof value === "string" && PHASE_INDEX.has(value as ProgressPhase);
}

function asNumber(value: unknown): number | undefined {
  return typeof value === "number" && Number.isFinite(value) ? value : undefined;
}

function progressPath(runDir: string): string {
  return join(runDir, "progress.jsonl");
}

function readExistingEvents(runDir: string): ProgressEvent[] {
  const path = progressPath(runDir);
  if (!existsSync(path)) {
    return [];
  }

  return readFileSync(path, "utf8")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const parsed = JSON.parse(line);
      if (!isRecord(parsed) || !isProgressPhase(parsed.phase)) {
        throw new Error("progress.jsonl contains an invalid progress event.");
      }
      return parsed as unknown as ProgressEvent;
    });
}

function validateProgressEvent(input: ProgressEventInput) {
  if (!isProgressPhase(input.phase)) {
    throw new Error(`Unknown progress phase '${String(input.phase)}'.`);
  }
  if (!input.mode || typeof input.mode !== "string") {
    throw new Error("Progress event mode is required.");
  }
  if (!input.message || typeof input.message !== "string") {
    throw new Error("Progress event message is required.");
  }
  if (input.budgetUsed !== undefined && !Number.isFinite(input.budgetUsed)) {
    throw new Error("Progress event budgetUsed must be a finite number.");
  }
  if (input.budgetLimit !== undefined && !Number.isFinite(input.budgetLimit)) {
    throw new Error("Progress event budgetLimit must be a finite number.");
  }
}

function validatePhaseOrder(existing: ProgressEvent[], nextPhase: ProgressPhase) {
  const nextIndex = PHASE_INDEX.get(nextPhase) ?? -1;
  const latest = existing.reduce<ProgressEvent | undefined>((latestEvent, event) => {
    const latestIndex = latestEvent ? PHASE_INDEX.get(latestEvent.phase) ?? -1 : -1;
    const eventIndex = PHASE_INDEX.get(event.phase) ?? -1;
    return eventIndex >= latestIndex ? event : latestEvent;
  }, undefined);

  if (latest) {
    const latestIndex = PHASE_INDEX.get(latest.phase) ?? -1;
    if (nextIndex < latestIndex) {
      throw new Error(`Progress phase order violation: cannot append '${nextPhase}' after '${latest.phase}'.`);
    }
  }

  const requiredPredecessor = REQUIRED_PREDECESSORS[nextPhase];
  if (requiredPredecessor && !existing.some((event) => event.phase === requiredPredecessor)) {
    throw new Error(`Progress phase '${nextPhase}' requires prior phase '${requiredPredecessor}'.`);
  }
}

function formatProgressLine(event: ProgressEvent): string {
  const details: string[] = [];
  if (event.budgetUsed !== undefined && event.budgetLimit !== undefined) {
    details.push(`budget ${event.budgetUsed}/${event.budgetLimit}`);
  }
  if (event.currentSourceId) {
    details.push(`source ${event.currentSourceId}`);
  }
  return `[styrir:${event.phase}] ${event.message}${details.length ? ` (${details.join(", ")})` : ""}`;
}

export function appendProgressEvent(runDir: string, input: ProgressEventInput, now = new Date()): string {
  validateProgressEvent(input);
  mkdirSync(runDir, { recursive: true });
  const existing = readExistingEvents(runDir);
  validatePhaseOrder(existing, input.phase);

  const event: ProgressEvent = {
    timestamp: now.toISOString(),
    phase: input.phase,
    mode: input.mode,
    message: input.message,
  };

  if (input.budgetUsed !== undefined) {
    event.budgetUsed = input.budgetUsed;
  }
  if (input.budgetLimit !== undefined) {
    event.budgetLimit = input.budgetLimit;
  }
  if (input.currentSourceId) {
    event.currentSourceId = input.currentSourceId;
  }

  appendFileSync(progressPath(runDir), `${JSON.stringify(event)}\n`);
  return formatProgressLine(event);
}

function readFlagValue(argv: string[], flag: string): string | undefined {
  const index = argv.indexOf(flag);
  return index === -1 ? undefined : argv[index + 1];
}

function readCliArgs(argv: string[]): { runDir: string; input: ProgressEventInput } {
  const runDir = argv[2];
  const phase = argv[3];
  const message = argv[4];
  const mode = readFlagValue(argv, "--mode");
  const budgetUsed = readFlagValue(argv, "--budget-used");
  const budgetLimit = readFlagValue(argv, "--budget-limit");
  const sourceId = readFlagValue(argv, "--source-id");

  if (!runDir || !phase || !message || !mode) {
    throw new Error(
      "Usage: styrir-progress-event.ts <run-dir> <phase> <message> --mode <mode> [--budget-used n] [--budget-limit n] [--source-id id]",
    );
  }

  if (!isProgressPhase(phase)) {
    throw new Error(`Unknown progress phase '${phase}'.`);
  }

  return {
    runDir,
    input: {
      phase,
      mode,
      message,
      budgetUsed: budgetUsed === undefined ? undefined : Number(budgetUsed),
      budgetLimit: budgetLimit === undefined ? undefined : Number(budgetLimit),
      currentSourceId: sourceId,
    },
  };
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  try {
    const { runDir, input } = readCliArgs(process.argv);
    process.stdout.write(`${appendProgressEvent(runDir, input)}\n`);
  } catch (error) {
    const message = error instanceof Error ? error.message : "Unknown progress event error.";
    process.stderr.write(`[styrir:error] ${message}\n`);
    process.exitCode = 1;
  }
}
