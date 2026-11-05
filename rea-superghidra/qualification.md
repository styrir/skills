# REA + SuperGhidra companion qualification - 2026-11-05

Verk contract: `vk-2591`, acceptance v2. This record covers the source revision
containing this document, installed skill links, and the explicitly bounded
same-session fixture observations below.

## Diagnosis and source decisions

Both MCP toolsets already work independently. The integration need is tool choice,
target matching and provenance, not a new REA transport or another tool server.
The new companion composes the existing REA skill, direct SuperGhidra MCP tools
and the local reporting skill. No upstream skill, provider code, MCP registration
or existing reporting implementation was edited.

The upstream SuperGhidra v1.0.8 tag resolves to
`566fbcbda795fcee5333733b805be9adfce51c29`. Its complete recursive tree and current
`skills/` directory were inspected through the GitHub connector. The eight skill
directories concern design/video workflows; none is a reverse-engineering skill
to install. The source map therefore links pinned project/domain guidance rather
than importing unrelated skills or copying an upstream manual.

## Source checks

- Skill frontmatter validation and Git whitespace checks passed.
- Routing was checked against the installed tool inventory: names are qualified
  by server, target-free specialist operations are distinct from project-bound
  queries, and raw SuperGhidra output is not accepted as fabricated REA Evidence.
- The report route explicitly keeps SuperGhidra-only claims in a supplement;
  REA's existing packager remains REA-only. A combined PDF requires the separate
  PDF composition workflow and no unsupported packager schema is advertised.
- The REA upstream checkout remained clean. The installed REA skill's observed
  SHA-256 was `fc05715feb4024a9194ba4a4e7d356d76baa3f06013ddb4580b2df87ce70d82f`.

## Installation checks

- The existing harness-link manager's dry run proposed only two new links.
- It created the Codex and Claude `rea-superghidra` links to this shared checkout.
- Its selected-harness check passed, and both links independently resolved to the
  exact new skill directory. Other selected links were already correct.
- No new daemon, runtime dependency, project hook or provider registration was added.

## Observed fixture behavior

Earlier in this same session, a locally compiled ARM64 Mach-O containing an
integer addition function was inspected without executing it. Its SHA-256 is
`2de9aaefa27dbdbfda5cd40984aeb52a1f8ac42ac13d79acdbeb455ce8176b0f`.

- Installed SuperGhidra 1.0.8 MCP imported and completed analysis of that fixture,
  then returned addition pseudocode from `decompile_function` with rewriting off.
- Installed REA 6.4.0 using Ghidra 12.1.4 returned an overview and then addition
  pseudocode at address `0x100000328`. Its canonical decompilation Evidence ID is
  `ev_549ff34f15937ee3a1f213d1245c17637917ecbc5b17cf763830f3d8d1fb4567`.
- The initial REA lookup without the Mach-O symbol's underscore failed; selecting
  the verified address succeeded. The companion explains independent symbol lookup.
- The complete successful REA record and separate SuperGhidra response were retained
  outside the source repository. A check during this tranche confirmed both recorded
  target digests equal the actual fixture digest, both results contain addition,
  and the SuperGhidra request did not enable compilable-code rewriting.
- Only the disposable fixture import created for this test was removed afterward;
  the fixture and raw results remain available locally. This tranche reused those
  matching results instead of rerunning unchanged engine checks.

## Operator confirmation and limits

- No fresh-session automatic skill-selection or independent behavioral evaluation
  of the companion instructions is claimed. Installed links are separately verified.
- The native smoke test does not establish large-app coverage, performance gains,
  class/metadata recovery, native equivalence proofs, remote neural behavior or runtime
  observation. Two Ghidra-based results are not independent-engine proof.
- No external upstream skills were installed. No mutation/runtime/remote-model
  permission follows from the companion's availability.
- Source publication and Verk review/receipt are separate from this qualification
  record. It does not assert their completion.
