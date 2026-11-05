# Upstream source map

SuperGhidra release checked: **v1.0.8**, commit
`566fbcbda795fcee5333733b805be9adfce51c29`. Installed REA checked: **6.4.0**,
checkout `91886982fccc50a9f7f31d4f320b25ffbcff35af`.
These are qualification identities, not an automatic-update policy.

- [SuperGhidra release README](https://github.com/yuatemycat/SuperGhidra/blob/566fbcbda795fcee5333733b805be9adfce51c29/README.md): capabilities and known limits. Read before choosing an unfamiliar specialist operation.
- [SuperGhidra agent router](https://github.com/yuatemycat/SuperGhidra/blob/566fbcbda795fcee5333733b805be9adfce51c29/AGENTS.md): domain-specific documentation routes. This is repository guidance, not a drop-in analysis skill or authority to broaden the user's task.
- [SuperGhidra release tree](https://github.com/yuatemycat/SuperGhidra/tree/566fbcbda795fcee5333733b805be9adfce51c29): locate the specific domain guide named by the router. The release's `skills/` directory contains design/video skills, not a reverse-engineering skill to bulk-install.
- [REA Ghidra provider](https://github.com/morluto/rea/blob/91886982fccc50a9f7f31d4f320b25ffbcff35af/docs/ghidra-provider.md): version-matched provider semantics.
- [REA CLI and evidence](https://github.com/morluto/rea/blob/91886982fccc50a9f7f31d4f320b25ffbcff35af/docs/cli.md): version-matched export workflows.

The connected `mcp__superghidra__*` tool schemas are the operational contract.
The local `superghidra` CLI and its optional MCP package are separate installation
components; a working CLI does not establish a working MCP connection.

The qualified smoke case used one locally compiled ARM64 Mach-O with an integer
addition function. Both tools recovered addition from the same input. This proves
basic operation on that fixture only: no speed, large-app coverage, specialized
recovery, neural backend or general semantic-equivalence claim follows.
