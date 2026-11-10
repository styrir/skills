# vk-2714 proof: run-skill-tests.py at 3326c430

Policy v5 (test = python3 scripts/run-skill-tests.py) approved by the operator 2026-11-10.
Recorded check under v5: vk-e626 at 3326c430, 16 of 17 suites pass, setja fails (declares dependencies, no node_modules) -- the owner's accepted outcome.

- proof-clean.txt: clean worktree at 3326c430. 16 PASS, setja FAIL, exit 1.
- proof-break.txt: same commit after mutate.py (one break per kind). Exit 1. Each break fails its own suite, untouched suites still pass:
  - unittest assertion (code-memory-check), plain-script exit (jev-guard test_policy), node test (styrir-search), uv suite (rea-report), shell (styrir-init): FAIL
  - zero-test unittest (zero/), aliased TestCase (aliased/), syntax error (syntax/), unstaged deletion (session-eval test_history): FAIL
  - orphans: lonely/foo_test.ts, dotfile .regression.test.ts, echopkg/broken.test.js (only echoed by its test script): FAIL as unclaimed
  - nested setja/test/unit/new.test.ts: setja's other test files reported unclaimed (fails closed)
  - hang/test-hang.sh: killed at the 600 s limit, FAIL
  - controls that must pass: litpkg (literal path), echopkg good test, mockonly (unittest.mock-only script): PASS
