# Codex review adapter validation — 2 November 2026

The operator requested automatic review completion in each individual harness
adapter, explicitly leaving standard Verk code unchanged. Codex's completion
logic is in `codex_closeout.py` and `codex_review.py`. The shared script's only
production changes dispatch the Codex entrypoint and parse its explicit delegation
flag. Shared functions, `verk.py` author identity, Claude behavior and Verk
core/store/policy/reviewer code are unchanged.

`python3 -m unittest discover -s verk/scripts -p 'test_*.py'`: **28 passed**.
Skill Creator `quick_validate.py verk`: passed. Coverage includes missing,
failed, rejected, altered and stale approval; wrong project/acceptance/harness;
unfinished or changed child receipts; dirty/moved work; untrusted report paths;
operator-delegation audit reason; repeated native Stop continuation and marker
persistence; receipt/duplicate completion; all existing author/Claude tests.
The existing real-CLI resume fixture omitted acceptance; it now supplies its
synthetic acceptance because current Verk correctly refuses absent acceptance.
No core behavior was changed to make that test pass.

A real isolated temporary Verk store produced a goal receipt through the new
Codex route using a **synthetic independent-report fixture**. This is a boundary
integration test, not a real model review. Operator fixture setup is confined to
that store. The before/after policy is identical and author attempts retain their
Codex session. No live goal is approved by that test.

The native Stop JSON contract was checked against official OpenAI documentation:
https://learn.chatgpt.com/docs/hooks#stop . Pending review returns a continuation
(`decision: block`), not `continue: false`. No independent verdict is synthesized,
no tests run at Stop, and no daemon is created. Installed package refresh used the existing local marketplace and public
`codex plugin add verk@brooks-local --json`. The native manifest and Stop command
bytes matched the prior installed definition exactly; no hook trust/configuration
was edited. Cache contents were verified against the package. Its 27 tests passed;
the existing packager's five tests passed. A direct invocation of the installed
hook entrypoint with a synthetic pending marker observed actual Orakel receipt
`vk-r96` and removed the marker. This verifies installed handler behavior; it is
not a claim of a newly observed desktop Stop dispatch. That final host event can
only be observed when the current turn actually ends.

## Live completion

The operator's instruction explicitly requested automatic completion in the
individual harness adapter without changing standard Verk code. Under that
instruction the new Codex route consumed the existing independent approval for
`vk-d183`, bound to Orakel goal `vk-2550` at
`124c8947e34b14226df52c323d65185322869086`. All children/prerequisites were satisfied.
It recorded the delegated operator action through the public CLI, with the real
Codex session and independent report SHA-256 in the resolution. Verk issued
**vk-r96** for that exact revision. The goal's operator-only review policy remained
unchanged; no actor was promoted to an independent reviewer and no store was
edited directly. The first live attempt correctly refused the reviewer's numbered
bold Markdown Reviewed heading; the parser was corrected to accept that actual
format while still requiring the exact revision, with a regression added.

The common author's `answer` refusal is unchanged. Claude retains its existing
entrypoint/tests. No file in Verk core or another harness adapter was modified.
The skill entry contract and desktop/Codex reference own these behavior changes;
root routing/ownership is unchanged and unrelated dirty work is preserved.

## Crash persistence follow-up

The first independent adapter review approved the implementation (vk-r97 at
8feee18) and identified an untested crash window around renaming the pending
marker. Codex now reads that marker in place and removes it only after an actual
receipt, rather than moving the only reminder while processing. A subprocess
regression hard-exits with code 17 inside the handler before its Verk call and
proves the original pending request remains byte-for-byte available. All 28
adapter tests and skill validation pass. Codex serializes Stop per session;
Verk's existing decision handling rejects duplicate answers. Common/Claude
functions and Verk core remain unchanged.

The crash-safe runtime at source `c6ad747` was refreshed through the same public
plugin installer. The installed `codex_closeout.py` SHA-256 is
`b77afec4104bd1d0319b44419f92f280eabadaec15337779a97c519a534bbaf6`,
byte-identical to the package/source. All 28 tests pass from the installed bundle
as well. The hook command/manifest and trust settings remain unchanged.

**Correction, 7 November 2026.** The refresh notes above don't show that the hook
kept running. An unchanged hook definition doesn't keep trust: Codex's trust record
also has a content hash, and a plugin refresh can change it. Codex then lists the
hook as Modified and finishes turns without running it, with a Review hooks icon
beside Full access as the only sign, until the operator allows it. This was
observed live on Codex desktop after each of three installs on 7 November. See
`docs/evidence/desktop-closeout-status.md`.
