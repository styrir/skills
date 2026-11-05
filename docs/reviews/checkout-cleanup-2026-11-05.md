---
summary: "Review and disposition of outstanding skills edits, including preserved drafts and source qualification limits."
read_when:
  - "Resuming vk-2588 cleanup or recovering the deferred initializer and ethnicity-report drafts."
---

# Checkout cleanup review - 2026-11-05

Contract: `vk-2588`. This is an author review with source checks, not an independent
review verdict or a claim that the imported features passed live qualification.

## Findings and disposition

1. **Incomplete tracking migration.** The pending root and documentation edits
   correctly moved task authority to Verk, but README, Claude instructions, a
   repository-local Beads skill and both harness hook configurations still
   instructed or invoked bd. Completed the active guidance migration. Retained
   the old workflow and skill paths as compatibility pointers. Removed only
   this repository's bd hook definitions; did not disable the hooks feature,
   modify user/global hooks, change approval/trust hashes or change Verk policy.
2. **Obsolete initializer edits.** The pending branch-preservation and shared-Dolt
   changes extended a bootstrap that still executes bd and installs legacy
   tracking guidance. Preserved its exact original draft, then replaced the
   executable entrypoint with an explicit refusal. Legacy templates remain
   inactive migration inputs. A Verk replacement is deferred to `vk-2589`.
3. **Humanizer preflight.** Kept the pending capability, consent and held-out-data
   safeguards, plus the stated author preference. Source inspection confirms
   `resolve` and `finalize` are scaffolds. Retained readable multiline examples;
   did not implement or claim a revision engine or activate new harness links.
   The plan fingerprint still matches the skill's approved hash.
4. **VST3 installer skill.** Reviewed the two-file import. Removed unsupported
   `platforms` frontmatter, corrected the CLI help's authorization description,
   and added synthetic source checks for exact token selection and refusal
   before any privileged installation. Imported source only; did not install
   packages, request elevation, link the skill into harnesses, or claim DAW loading.
5. **Ethnicity-report import.** Per the operator's explicit choice, preserved it
   as a draft under `vk-2590`, without publishing or activating it. Entry-contract
   review found hardcoded Linux Hermes paths and a referenced missing
   `test_report_tier_consistency.py`. Its full code, methodology and outputs
   remain unreviewed; no research pipeline or API was run.

## Draft preservation

- Ethnicity-report: 70 source/config files in local Git stash
  `1dd174d8da18ccb612362ccc6d88d24ab56d7cf7`, untracked-file tree (third parent).
- Legacy initializer: four original draft files in local Git stash
  `9e56e4d86c9c3de8960727f3149302ae2b9c3c69`. Tracked file contents are in the
  stash tree; the two new identity scripts are in its third parent.
- All 74 source/config file blob identities were checked against the originals.
  Six ignored Python caches remain unchanged locally. No original draft file
  was discarded. The installed Hermes copy is a separate real directory.
- These stashes are local recovery objects, not published backups. Exact recovery
  instructions are also recorded in each Verk task. Recover selected paths;
  do not blanket-pop a stash over the replacement source.

## Source checks and limits

- Retired initializer self-check passed: new target absent, existing sentinel
  unchanged, and no tracker/Git invocation. The legacy test was not run.
- Three VST3 source checks passed with synthetic metadata and mocked subprocesses.
  They cover ancestor/token selection, preview without installation, selection
  mismatch refusal and absent-VST3 refusal before elevation.
- Fifteen existing humanizer scaffold checks passed. These establish scaffold
  behavior, not accepted document revision.
- Skill validation passed for the VST3, humanizer and retired initializer skills.
  Tracking JSON parsed; active root/Claude/README guidance has no bd commands;
  routed paths exist. Git whitespace checks passed.
- No real installer, live harness callback, native-provider behavior or user
  confirmation is qualified here. Publication and Verk receipts are separate.

## Review artifact provenance

Local raw review inputs remain under ignored `.pipeline/checkout-cleanup/`:

- `reviewed.patch`: SHA-256
  `7508b797f4f3807d041a6f806c000d7ee98b00ecaeceed4676ad8c518868e1fa`.
  Captures reviewed tracked edits before committing the cleanup groups.
- `apple-source-manifest.json`: SHA-256
  `c32d8893952546ec295d6b2ba15edc748c9bea16cf6a96cbc3973ed84625c95d`.
  Lists hashes for the three reviewed VST3 skill source/check files.
- `draft-inventory.json` records original draft hashes used for stash verification.
  These are local investigation artifacts, not portable release evidence.
