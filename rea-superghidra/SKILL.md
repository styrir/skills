---
name: rea-superghidra
description: Coordinate REA and SuperGhidra for a binary or packaged-app investigation, using SuperGhidra's specialist analyses alongside REA evidence and optional reporting. Use for combined investigations or deciding which engine to use; ordinary source-code questions and REA-only reports do not need this companion.
---

# REA + SuperGhidra

This is a locally maintained companion. Keep `reverse-engineer-anything`, REA,
SuperGhidra and their MCP registrations under their existing upstream ownership.
Do not patch an upstream skill or replace REA's provider bridge to use this flow.
Load the installed `reverse-engineer-anything` skill for REA target routing,
evidence/session semantics and recovery; this companion owns the cross-tool choice.
For detailed SuperGhidra behavior, read only the relevant pinned upstream source
linked in [the source map](references/upstream.md). A tool's live schema and
installed version take precedence over examples from another release.

## Choose the useful tool

Start with the user's target and question. Reuse matching prior evidence. Do not
run both engines automatically or benchmark them unless the question needs it.
Skills supply instructions; MCP supplies executable tools. Neither installs or
upgrades the other. If a tool is absent, report the missing capability and use an
available route within the requested scope; do not silently replace providers.

| Question | Route |
|---|---|
| What is this app/artifact, and how does its feature work? | REA via `reverse-engineer-anything`; use its native provider when needed. |
| Mach-O fixups, Swift/Objective-C metadata | SuperGhidra `apple_dispatch` on an explicit file and architecture. |
| MSVC/MFC class structure | SuperGhidra `recover_cpp_classes` on a PE; recovery is not original source. |
| Rust/Go provenance or Unity IL2CPP metadata | SuperGhidra `crate_audit` or `il2cpp_recover`, checking input requirements first. REA's existing inspectors may already suffice. |
| Repeated native queries in an existing SuperGhidra project | Direct SuperGhidra decompilation, symbols, strings and xrefs; reuse that project rather than importing it again through REA. |
| Version comparison or reconstructed-code validation | Inspect SuperGhidra's live diff/SMT schemas and documented limits before selecting a tool. |

Use the exact namespace: REA and SuperGhidra both expose names such as
`decompile_function` and `trace_native_values`. Their inputs, state and evidence
contracts are different. Do not pass a session identifier or retained reference
from one server to the other.

## Bind the same bytes

For a native comparison, record the exact input SHA-256, architecture/slice and
each engine's version. A universal-binary slice has its own identity; do not
silently compare it with the whole container. Resolve symbols independently in
each engine; Mach-O names may include a leading underscore. Match by verified
address/image base or bytes when names differ, not by display-name resemblance.

For SuperGhidra, inspect `get_session_info` and `list_project_binaries` when
binding/reusing a project. Import the caller-selected path only if absent, then
wait for that exact import's analysis to complete before querying. Use the binary
name returned by the server, not a name invented from the filename. Leave existing
user projects, pending forks and annotations alone. Remove only disposable imports
created for this task when cleanup is appropriate; never clear shared caches,
merge/discard forks or remove locks merely to obtain access.

Record the command/tool, full parameters, input digest, version, selected function
or address, complete result and limitations. Static inspection does not authorize
target execution, instrumentation, emulator access, project edits or a remote
neural/LLM endpoint. Any such action needs matching user scope. Recompiled C is a
derived artifact, not recovered source. Preserve raw pseudocode before applying
`emit_compilable` or another rewrite. An SMT result applies only to its admitted
instructions, assumptions and bounds; `UNKNOWN` or unsupported input is no proof.

## Reconcile and report

Keep REA's canonical Evidence unchanged and cite its actual IDs. Save complete
SuperGhidra responses separately, with file SHA-256, tool/version, parameters and
target/slice identity. A file hash identifies saved bytes; it does not authenticate
the tool's conclusion. Never invent an `ev_` ID or wrap SuperGhidra JSON in a fake
REA record to satisfy a report packager.

For each material claim, say which saved result supports it and whether it is an
observation, derivation, inference or unknown. Agreement between two Ghidra-based
routes is a cross-check, not independent-engine proof. Preserve disagreements and
missing/truncated coverage rather than choosing the nicer-looking output.

When a report is requested, load the local `rea-report` skill. Its packager accepts
REA Evidence only. Use it for findings supported by REA and provide a separate
SuperGhidra supplement containing its findings, source-file hashes and saved raw
responses. Do not cite an unrelated REA record to support a SuperGhidra-only claim.
Deliver both as one investigation with explicit links and a common target digest.
If the user specifically requires a single combined PDF, compose the two source
sets with the PDF skill, retain their provenance separately, render and inspect
the result; do not pretend the REA-only packager supports supplementary schemas.

## Updates

Keep this companion in the shared skills repo and install it through the harness
link manifest. Upstream updates should not overwrite it. Recheck the source map
and live schemas after a version change; update only the affected routing advice.
Do not copy whole upstream manuals into this skill or bulk-install unrelated
skills from an upstream repository.

To reproduce the macOS ARM64 smoke fixture without executing it, run
`python3 scripts/build_fixture.py --output /absolute/new-fixture-directory` from
this skill's directory. The committed C source is built twice in separate
directories; differing bytes fail the check. See [qualification](qualification.md)
for the observed compiler/SDK, exact analysis parameters, addresses and limits.
