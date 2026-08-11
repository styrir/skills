import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import test from "node:test";
import { normalizeLedger, normalizeMode, parseLedgerText } from "./styrir-ledger-normalize.ts";
import { validateLedger } from "./styrir-search-gate.ts";

const legacyJsonLedger = {
  meta: {
    mode: "structured_search",
    search_id: "search-2026-07-02-normalize-json",
    total_queries_run: 4,
    total_sources_extracted: 2,
    budget: {
      max_search_queries: 6,
      max_sources_to_extract: 6,
    },
  },
  entries: [
    {
      id: "entry-docs",
      observation: "The official docs expose a bounded search endpoint.",
      possible_implication: "The ledger can normalize structured evidence without escalation.",
      source_url: "https://docs.example.test/search?mode=bounded:risk=high",
      source_type: "official",
      date_observed: "2026-07-02",
      confidence: "high",
    },
    {
      id: "entry-blog",
      observation: "A comparison write-up recommends treating snippets as discovery only.",
      possibleImplication: "The gate should require fetched evidence before strong claims.",
      sourceId: "src-blog",
      sourceUrl: "https://blog.example.test/search-review",
      sourceType: "analysis",
      dateObserved: "2026-07-01",
      confidence: "medium",
    },
  ],
  proof_gaps: [
    {
      description: "Need an official pricing source for extraction limits.",
      attempted_queries: ["official extraction limits pricing 2026"],
    },
  ],
  sourceAppendix: [
    {
      url: "https://docs.example.test/search?mode=bounded:risk=high",
      title: "Bounded Search Docs",
      source_type: "official",
    },
    {
      id: "src-blog",
      url: "https://blog.example.test/search-review",
      title: "Search Review",
      sourceType: "analysis",
    },
  ],
};

const legacyYamlLedger = `
meta:
  mode: structured_search
  search_id: search-2026-07-02-normalize-yaml
  total_queries_run: 3
  total_sources_extracted: 1
  budget:
    max_search_queries: 6
    max_sources_to_extract: 6
entries:
  - id: yaml-entry
    observation: Official docs list a local deep search handoff manifest.
    possible_implication: URLs with labels like risk: high must survive parsing.
    source_url: https://docs.example.test/deep-search?manifest=1:risk=high
    source_type: official
    date_observed: 2026-07-02
    confidence: high
proof_gaps:
  -
    description: Could not confirm NVIDIA AI-Q runtime wiring.
    attempted_queries:
      - nvidia aiq local runtime wiring
source_appendix:
  - title: Deep Search Docs
    url: https://docs.example.test/deep-search?manifest=1:risk=high
    source_type: official
`;

test("normalizes legacy JSON fields into the canonical ledger contract", () => {
  const result = normalizeLedger(JSON.stringify(legacyJsonLedger));

  assert.equal(result.meta.mode, "styrir_search");
  assert.equal(result.meta.searchId, "search-2026-07-02-normalize-json");
  assert.deepEqual(result.meta.budget, {
    maxSearchQueries: 6,
    maxFetches: 6,
  });
  assert.equal(result.proofGaps[0].attemptedQueries[0], "official extraction limits pricing 2026");
  assert.equal(result.entries[0].possibleImplication, legacyJsonLedger.entries[0].possible_implication);
  assert.equal(result.entries[0].sourceUrl, "https://docs.example.test/search?mode=bounded:risk=high");
  assert.equal(result.entries[0].sourceId, result.sources[0].id);
  assert.equal(result.sources[0].fetched, true);
  assert.equal(result.sources[1].id, "src-blog");
});

test("normalizes constrained YAML while preserving colon-space values and assigning missing source ids", () => {
  const result = normalizeLedger(legacyYamlLedger);

  assert.equal(result.meta.mode, "styrir_search");
  assert.equal(result.entries[0].possibleImplication, "URLs with labels like risk: high must survive parsing.");
  assert.equal(result.entries[0].sourceUrl, "https://docs.example.test/deep-search?manifest=1:risk=high");
  assert.equal(result.entries[0].id, "yaml-entry");
  assert.equal(result.entries[0].sourceId, "s1");
  assert.equal(result.entries[0].sourceId, result.sources[0].id);
  assert.equal(result.sources[0].id, "s1");
  assert.equal(result.sources[0].fetched, true);
});

test("parseLedgerText preserves punctuation in YAML scalar values", () => {
  const parsed = parseLedgerText(`
entries:
  - observation: URLs with labels like risk: high must survive parsing.
`);

  assert.deepEqual(parsed, {
    entries: [
      {
        observation: "URLs with labels like risk: high must survive parsing.",
      },
    ],
  });
});

test("normalizeMode maps legacy aliases and preserves canonical modes", () => {
  assert.equal(normalizeMode("structured_plus"), "styrir_plus");
  assert.equal(normalizeMode("deep_search_local"), "deep_search_local");
});

test("fails closed on unsupported flow YAML with unsupported_yaml_shape", () => {
  assert.throws(
    () =>
      parseLedgerText(`
entries: [{ id: e1, observation: nope }]
sources: []
`),
    /unsupported_yaml_shape/,
  );
});

test("fails on malformed YAML", () => {
  assert.throws(
    () =>
      normalizeLedger(`
meta:
  mode structured_search
entries:
  -
    id: bad
`),
    /Malformed YAML/,
  );
});

test("fails on YAML with tab indentation", () => {
  assert.throws(
    () =>
      normalizeLedger(`
meta:
\tmode: structured_search
`),
    /tabs are not supported/,
  );
});

test("normalized output passes the existing gate", () => {
  const normalized = normalizeLedger(legacyYamlLedger);
  const result = validateLedger(normalized);

  assert.equal(result.gateStatus, "pass");
  assert.deepEqual(result.blockers, []);
});

test("CLI normalizes a YAML file path to canonical JSON on stdout", () => {
  const dir = mkdtempSync(join(tmpdir(), "styrir-ledger-normalize-"));
  const ledgerPath = join(dir, "legacy-ledger.yaml");
  writeFileSync(ledgerPath, legacyYamlLedger);

  const result = spawnSync(
    process.execPath,
    ["--experimental-strip-types", new URL("./styrir-ledger-normalize.ts", import.meta.url).pathname, ledgerPath],
    { encoding: "utf8" },
  );

  assert.equal(result.status, 0);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.meta.mode, "styrir_search");
  assert.equal(payload.sources[0].url, "https://docs.example.test/deep-search?manifest=1:risk=high");
});

test("CLI reads JSON from stdin when no file path is provided", () => {
  const result = spawnSync(
    process.execPath,
    ["--experimental-strip-types", new URL("./styrir-ledger-normalize.ts", import.meta.url).pathname],
    {
      encoding: "utf8",
      input: JSON.stringify(legacyJsonLedger),
    },
  );

  assert.equal(result.status, 0);
  const payload = JSON.parse(result.stdout);
  assert.equal(payload.meta.searchId, "search-2026-07-02-normalize-json");
  assert.equal(payload.entries[1].sourceId, "src-blog");
});
