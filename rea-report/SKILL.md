---
name: rea-report
description: Produce a shareable reverse-engineering report in Markdown, JSON and PDF from morluto/rea evidence. Use when asked to document an investigation, explain an app feature with evidence, or package REA results; ordinary codebase questions do not need this workflow.
---

# REA report

Use `morluto/rea` (`rea-agents`), not the unrelated `mytechnotalent/rea` Rust CLI.
Use the installed `reverse-engineer-anything` skill for target routing and analysis;
this skill adds report assembly, not another analysis engine. When unavailable,
consult the installed REA's `--help` and https://github.com/morluto/rea/blob/main/docs/cli.md.

Resolve the user's target and investigation question first. Inspect only that
target. Use existing matching Evidence before rerunning analysis. Static analysis
does not authorize launching, instrumenting or modifying the target. Report
unavailable engines and partial coverage rather than substituting guesses.

## Collect and interpret

Save complete CLI Evidence JSON (`--format json`) or MCP `structuredContent` to
caller-selected local files. For example, `rea inspect-artifact /absolute/target
--format json` inventories an artifact; it does not decompile it. Choose deeper
operations according to the actual question and available providers.

For retained MCP results, call `export_evidence_bundle` with a new absolute output
path before closing the session. Follow the connected server's actual schema.
For an existing canonical bundle, `rea evidence-export SOURCE OUTPUT` validates
and exports it. Never package transport previews, summary projections or filtered
outputs as complete records. Full records can themselves describe partial analysis;
preserve that distinction. Do not fabricate a canonical bundle around unrelated JSON.

Read the evidence before writing conclusions. Cite its exact IDs. Separate
observed facts, derived results, inferences and unknowns. Preserve target digests,
provider identity, source authority, limitations, omissions and unresolved branches.
Evidence IDs establish references, not the truth of an analyst's interpretation.

## Package

Write a small UTF-8 report JSON with this shape. Strings are plain text, not
Markdown/HTML. Each observed/derived/inferred finding needs supplied evidence IDs;
unknowns may have an empty list. Use actual IDs in place of the example below.

```json
{
  "title": "App feature investigation",
  "summary": "What the evidence establishes about the requested feature.",
  "scope": "Exact target, question, analyses performed and coverage boundaries.",
  "findings": [
    {"kind": "observed", "text": "A fact from the saved analysis.", "evidence_ids": ["ev_REPLACE_WITH_ACTUAL_ID"]},
    {"kind": "unknown", "text": "What remains unanswered and the next useful probe.", "evidence_ids": []}
  ],
  "limitations": ["Static evidence does not establish live behavior."]
}
```

Run the bundled packager (resolve its path from this skill's directory):

```sh
uv run /path/to/rea-report/scripts/package_report.py \
  --report /absolute/findings.json \
  --evidence /absolute/evidence.json \
  --output /absolute/new-report-directory
```

Repeat `--evidence` for multiple records or canonical bundles. The parent directory
must exist; the output directory must not exist. Outputs are `report.md`,
`report.json` and `report.pdf`. JSON preserves complete supplied documents and
their source-file SHA-256 hashes, including bundle unknown histories and nested
coverage. The readable reports index top-level records and their limitations;
put question-relevant nested coverage and unknowns in the narrative as well.
Only top-level record IDs (or bundle `records` IDs) can be cited by the packager.

The script checks shape and citation membership; it does not authenticate evidence
IDs or validate that a citation supports a claim. Use REA's own validator for
canonical-bundle authentication. It never launches REA or the target, fetches report
resources, or sends findings to an LLM. First use of `uv` may download the pinned
ReportLab dependency; warm runs work with `uv run --offline`.

The combined input budget defaults to 64 MiB; deliberately increase
`--max-input-mib` for larger complete exports. Do not truncate Evidence to fit.
PDF uses bundled Vera fonts (Western European Latin); unsupported glyphs fail
before publication instead of silently disappearing. Use an appropriate separately
reviewed font/rendering path when a report needs other scripts. Arbitrary rich
Markdown, images and embedded HTML are outside this plain-text report format.

Render the PDF with `pdftoppm`, inspect the pages, and verify text extraction before
delivery. Return links to the three files with the conclusion and remaining gaps.
Do not commit target evidence or generated reports into the skills repository.
