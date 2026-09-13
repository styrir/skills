---
summary: Historical local session-format inventory and follow-up trajectory-format research preserved for session-eval.
read_when:
  - Reviewing harness file-format observations or trajectory/reporting follow-up evidence before applying the canonical session-eval specification.
---

# Session-format source dossiers

The [session-eval specification](../../specification.md) is the normative authority. This page is a navigation index for historical evidence only; it does not replace or amend that specification. The source bytes below are snapshots from the 2026-09-13 session-observation run and must not be treated as a competing maintained specification.

## Source identity and evidence class

Both bundles were captured from `/Users/brooks/Code/agent-ops/.styrir/runs/2026-09-13-session-obs/` and are preserved without source-file edits. The evidence classes are intentionally separate:

| Bundle | Source identity | Evidence class | Scope recorded by the bundle |
|---|---|---|---|
| [`session-formats`](evidence/session-formats/) | `.../session-obs/session-formats` | Local read-only format inspection | Representative local paths/records and database schemas for Claude Code, Codex, Pi, Oh My Pi (OMP), Grok Build, WorkGraph/agent-ops, and OMC/OMO adjuncts. The report explicitly records that no web sources were consulted. |
| [`second-pass-formats`](evidence/second-pass-formats/) | `.../session-obs/second-pass-formats` | Online bounded StyrirSearch:plus follow-up | Eight searches and ten fetched primary sources covering ATIF, OpenInference, Claude JSONL analyzers/static HTML, Agent Skills metadata, and skill tree-hash tracking. It follows the local inventory; it is not local format evidence. |

The local inventory is not a web-source registry. The online follow-up's fetched URLs and source types remain in its preserved `source-registry.json`; no search snippet is promoted into local format evidence.

## `session-formats` bundle — local inspection

### Preserved files

| File | Role |
|---|---|
| [`report.md`](evidence/session-formats/report.md) | Historical acceptance table, observed implications, and proof gaps for local harness/session inspection. |
| [`summary.txt`](evidence/session-formats/summary.txt) | Historical local-inventory summary and explicit no-web-search note. |

### Observed findings

- The local report identifies primary streams for Claude Code, Codex, Pi, OMP (including child logs), and Grok, with sidecars treated as enrichment/index sources rather than replacements for primary streams.
- It records source-specific token-accounting differences, derived skill observations, event/line provenance, schema-drift handling, and default redaction of prompts, tool payloads/results, encrypted blobs, system prompts, credential-pin values/hashes, and terminal output.
- The observed Pi and OMP records share a version-3-shaped envelope in the sampled files, while the report explicitly cautions that this does not prove byte-for-byte compatibility across releases. Grok summary variants and timestamp representations also remain observed-format details rather than a universal contract.

### Limits and proof gaps

The local report's [`proofGaps`](evidence/session-formats/report.md) section is the source of truth for limits: `~/.config/claude` was absent on this machine; only representative records and DB schemas were sampled; Pi/OMP sampled files did not expose stable native per-session usage; cross-release Pi/OMP compatibility is unproven; Grok has observed `info` and older `session_info` variants; Codex `item_json` rows were not dumped; generic parsers for Codex, Pi, OMP, and Grok were not found locally; and no web sources were consulted. These are inspection boundaries, not negative claims about other hosts or releases.

No saved `gate-result.json` exists in this original local-inspection bundle, so no synthetic gate result is added here.

## `second-pass-formats` bundle — online follow-up

### Preserved files

| File | Role |
|---|---|
| [`architecture.txt`](evidence/second-pass-formats/architecture.txt) | Historical two-lane ATIF/static-HTML and optional OpenInference projection synthesis. |
| [`contradiction-sweep.md`](evidence/second-pass-formats/contradiction-sweep.md) | Historical contradictions between native formats, normalized reports, viewers, scoring, versions, and licensing. |
| [`gate-result.json`](evidence/second-pass-formats/gate-result.json) | Saved historical gate result: `pass`, 17 entries, 10 sources, 4 proof gaps; not rerun for this snapshot. |
| [`ledger.json`](evidence/second-pass-formats/ledger.json) | Historical online evidence ledger, proof gaps, and source records. |
| [`plan.json`](evidence/second-pass-formats/plan.json) | Historical bounded-search plan and accounting. |
| [`report.md`](evidence/second-pass-formats/report.md) | Historical follow-up report with evidence/borrow list, ATIF shape, OpenInference projection, parser surfaces, skill version tracking, contradiction sweep, and inline artifacts. |
| [`request.json`](evidence/second-pass-formats/request.json) | Historical research request and source-scope metadata. |
| [`source-registry.json`](evidence/second-pass-formats/source-registry.json) | Historical registry for ten fetched official/repository sources. |
| [`summary.txt`](evidence/second-pass-formats/summary.txt) | Historical online follow-up summary. |

### Observed findings

- The follow-up report describes Harbor ATIF as a document-level JSON trajectory format and OpenInference as a transport/file-format-agnostic semantic-convention projection; it records local validation/static-report paths without making an OTel collector a prerequisite.
- It records `ccdiag` checks and `claude-code-transcripts` static HTML as directly fetched Claude-oriented surfaces, and records Agent Skills optional `metadata.version` separately from Vercel's exact-content `skillFolderHash`/tree-SHA mechanism.
- Its architecture artifact describes a two-lane pipeline: file-native normalized trajectories/static HTML, with optional OpenInference spans. This is historical research evidence, not an implementation decision independent of the canonical specification.

### Limits and proof gaps

The follow-up's [`contradiction-sweep.md`](evidence/second-pass-formats/contradiction-sweep.md), [`ledger.json`](evidence/second-pass-formats/ledger.json), and [`report.md`](evidence/second-pass-formats/report.md) retain four proof gaps: no fetched Codex rollout parser/license, no fetched Agent Skills or Vercel CLI LICENSE files, no fetched ready-made Claude/Codex JSONL-to-ATIF exporter, and no common longitudinal SKILL.md evaluator artifact schema. Do not vendor code or infer compatibility from these records. The saved gate result is historical and was not rerun.

## Provenance and gate receipts

[`provenance.json`](provenance.json) is the dossier manifest with schema `session-eval-source-provenance/v1`. It records 11 preserved regular files, each original absolute path, relative snapshot path, byte count, and SHA-256 digest. The [saved second-pass gate result](evidence/second-pass-formats/gate-result.json) is a historical receipt only; the local `session-formats` bundle contained no gate-result file. The manifest, gate receipt, and snapshots are evidence records, not normative requirements.
