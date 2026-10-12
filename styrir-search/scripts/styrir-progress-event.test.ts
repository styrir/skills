import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, readFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { appendProgressEvent } from "./styrir-progress-event.ts";

function makeRunDir(): string {
  return mkdtempSync(join(tmpdir(), "styrir-progress-"));
}

test("appendProgressEvent writes JSONL and returns a compact status line", () => {
  const dir = makeRunDir();
  const line = appendProgressEvent(
    dir,
    {
      phase: "routing",
      mode: "styrir_plus",
      message: "Routed to Plus",
      budgetUsed: 0,
      budgetLimit: 10,
      currentSourceId: "s1",
    },
    new Date("2026-07-02T20:00:00.000Z"),
  );

  assert.equal(line, "[styrir:routing] Routed to Plus (budget 0/10, source s1)");
  const events = readFileSync(join(dir, "progress.jsonl"), "utf8").trim().split("\n").map((lineText) => JSON.parse(lineText));
  assert.deepEqual(events, [
    {
      timestamp: "2026-07-02T20:00:00.000Z",
      phase: "routing",
      mode: "styrir_plus",
      message: "Routed to Plus",
      budgetUsed: 0,
      budgetLimit: 10,
      currentSourceId: "s1",
    },
  ]);
});

test("appendProgressEvent enforces legal phase ordering", () => {
  const dir = makeRunDir();
  appendProgressEvent(dir, { phase: "routing", mode: "styrir_search", message: "Routed" });
  appendProgressEvent(dir, { phase: "ledger", mode: "styrir_search", message: "Ledger ready" });
  appendProgressEvent(dir, { phase: "gate", mode: "styrir_search", message: "Gate passed" });

  assert.throws(
    () => appendProgressEvent(dir, { phase: "fetching", mode: "styrir_search", message: "Late fetch" }),
    /phase order/i,
  );
});

test("appendProgressEvent blocks gate before a ledger event", () => {
  const dir = makeRunDir();

  assert.throws(
    () => appendProgressEvent(dir, { phase: "gate", mode: "styrir_plus", message: "Gate skipped ahead" }),
    /requires prior phase 'ledger'/,
  );
});

test("CLI appends an event and prints the compact line", () => {
  const dir = makeRunDir();
  const result = spawnSync(
    process.execPath,
    [
      "--experimental-strip-types",
      new URL("./styrir-progress-event.ts", import.meta.url).pathname,
      dir,
      "routing",
      "Routed to Plus",
      "--mode",
      "styrir_plus",
      "--budget-used",
      "0",
      "--budget-limit",
      "10",
      "--source-id",
      "s1",
    ],
    { encoding: "utf8" },
  );

  assert.equal(result.status, 0);
  assert.equal(result.stdout.trim(), "[styrir:routing] Routed to Plus (budget 0/10, source s1)");
  assert.equal(readFileSync(join(dir, "progress.jsonl"), "utf8").trim().split("\n").length, 1);
});
