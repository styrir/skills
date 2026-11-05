# REA report qualification - 2026-11-05

Verk contract: `vk-2587`. This record qualifies the reporting wrapper at the
source revision containing this file, not a new REA engine or provider release.

## Diagnosis and scope

The installed morluto/rea already returns complete structured Evidence and can
export canonical bundles. The missing personal workflow was consistent report
assembly. The new skill guides analysis; its script packages analyst-authored
plain-text findings and saved records without launching REA or the target.

## Source checks

- Six stdlib unittest checks passed with ReportLab 5.1.0. They cover retention of
  complete bundle documents and unknowns, PDF text extraction with Latin accents,
  literal HTML handling, citation membership, incomplete/conflicting records,
  existing destinations and symlinks, duplicate JSON keys, non-JSON constants,
  input budgets, and PDF-failure cleanup before output publication.
- Skill frontmatter validation passed. Scoped Git whitespace checks passed.
- The renderer uses pinned ReportLab through uv; the only added runtime package
  is ReportLab and its resolved dependencies. No REA source/configuration changes.

## Installation checks

- The existing harness-link manager created only the new `rea-report` links for
  Codex and Claude; its dry run showed the other selected links already correct.
- Both links resolve to this checkout's `rea-report` directory. The link manager's
  selected-harness check passed after installation.
- The packager ran successfully through the installed Codex skill path with
  `uv run --offline`; all three outputs were present and the saved source Evidence
  document compared equal to the complete input.

## Observed behavior

- Installed morluto/rea 6.4.0 statically inspected a newly generated local ZIP
  containing one README text file. The wrapper packaged its genuine
  `inspect_artifact` record with one observed finding and one explicit unknown.
- Markdown, JSON and a one-page PDF were generated. The JSON preserved the complete
  record including its nested coverage, source limitations and next probes.
- Poppler reported a valid A4 PDF with no JavaScript. Extracted text retained the
  finding, exact Evidence ID, source limitations and subject metadata.
- The rendered PDF page was visually inspected: no clipping, overlap or missing
  text; headings, line wrapping and footer were legible.
- Test reports, fixture bytes and rendered pages remain in the ignored
  `.pipeline/rea-report-smoke/` workspace, outside committed skill source.

## Operator confirmations and limits

- No operator confirmation or fresh-session automatic skill-selection result is
  claimed. A new agent session may be needed to refresh skill discovery.
- Packaging validates record shape and citation membership, not Evidence ID
  authentication or the truth of analyst prose. REA owns canonical validation.
- Full records can describe partial analysis. Readable reports index top-level
  records; complete nested facts and bundle unknowns remain in JSON. The agent
  must include question-relevant limits in its narrative.
- PDF supports bundled Vera's Western European Latin glyphs and refuses missing
  glyphs. Arbitrary rich Markdown/images and other scripts are outside this version.
- Combined input defaults to 64 MiB and can be raised explicitly. First dependency
  acquisition requires network access; the qualified warm path worked offline.
- No native decompilation, runtime capture, live user application investigation or
  cross-harness model behavior was qualified by this reporting smoke check.
- Unrelated pre-existing working-tree edits were preserved. Publication and any
  Verk receipt must be checked separately; this document does not assert either.
