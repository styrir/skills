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

- Skill frontmatter validation and Git whitespace checks passed. The fixture
  builder passed its two-directory byte-identity check and existing-output refusal.
  REA documentation links now pin the exact installed checkout revision.
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

## Reproducible fixture and exact analysis provenance

The fixture source is committed at `tests/fixtures/companion_check.c`, SHA-256
`db0e1aff94a303afac9a26dd7d09613079df3b5b736a087773e1e1499ed42365`.
Reproduce it on macOS with Apple clang using:

```sh
python3 scripts/build_fixture.py --output /absolute/new-fixture-directory
```

The builder invokes `/usr/bin/clang` with `-O0 -arch arm64
-mmacosx-version-min=14.0 -Wl,-no_uuid`, the committed C source and `-o` pointing
to a file named `companion_check`. It omits debug paths and linker UUIDs, builds
in two separate directories and requires byte-for-byte equality before saving
`companion_check` and `build.json`. It never executes the target.

Observed toolchain: Apple clang 21.0.0 (`clang-2100.3.34.2`), target
`arm64-apple-darwin27.2.0`, Xcode default toolchain. The linked Mach-O records
SDK 27.2, minimum macOS 14.0 and linker version 27037.1. Both separate builds
were identical, SHA-256
`cd23578f77b646f0e2a5f45d97c69cdc13f7e07b964caae3338e820b61e1de08`.
Different compilers/SDKs can produce different bytes: use the recorded toolchain
to reproduce this identity, and always compare both engines on the same newly
built bytes. A second invocation with the existing output directory failed and
the existing target's digest remained unchanged.

SuperGhidra: package/MCP 1.0.8. Its live `list_project_binary_metadata` reported
`Created With Ghidra Version: 12.1.4`, language
`AARCH64:LE:64:AppleSilicon (1.5)`, image minimum `0x100000000` and the exact
fixture SHA-256 above. The configured installation's application metadata also
reported 12.1.4 PUBLIC, build `2026-Sep-21 1613 UTC`; its properties SHA-256 was
`e84c26b08545eee63d24a1a8a4dd7905e4209538e2e7192093877c435c64eb67`.

After import completion, a function-only symbol query for `companion_add`
returned `_companion_add` at `0x100000310`. The exact decompilation request was:

```json
{
  "binary_name": "/companion_check-6aecdc",
  "name_or_address": "0x100000310",
  "emit_compilable": false,
  "include_callees": false,
  "include_strings": false,
  "include_xrefs": false,
  "timeout_sec": 60
}
```

The response resolved `_companion_add-100000310`, returned an integer-addition
function and no error. The binary name is the actual server-selected name from
this run; a reproduction must use its own returned name. Only this disposable
fixture import was removed after collecting its results.

REA: CLI 6.4.0, checkout `91886982fccc50a9f7f31d4f320b25ffbcff35af`.
The exact arguments were `rea decompile <fixture-output>/companion_check
0x100000310 --provider ghidra --format json`. The resulting canonical Evidence
record reports provider `ghidra`, name `Ghidra`, version `12.1.4`, the same
fixture SHA-256 and Evidence ID
`ev_771ebd152bc86150c01c47c3e3512e2c9069b230acaef7359a6ae9c2ab3642b6`.
Both engines returned the same pseudocode after trimming outer whitespace.
This is a same-Ghidra cross-check, not independent-engine equivalence proof.

Complete results remain outside the source repository to avoid committing binary
artifacts and machine paths. They are identified by these file hashes:

- `build.json`: `6e52b3a4679d60abbd5d5ecbcb3f0fac58011027a09e9ba4b4af7c2f5d9a6694`
- `rea-decompile.json`: `251bb6de65ac18df1eef5bc19bde84813476d41ad1c9c32ee8698ba81e4acbbd`
- `superghidra-decompile.json`: `1938398820276557692bd6207cd4c7af61f95e79bce580d93edd42668f2d6983`

The committed source, builder, toolchain identity and requests permit regeneration
of a new result pair without access to those local files. Fresh engine runs and
new build paths can legitimately change result IDs and metadata.

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
