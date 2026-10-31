# Claude helper identity validation

Scope: source-only prerequisite vk-2538. Desktop mod installation and live behavior belong to vk-2532.

The existing helper assumed Codex identity. An explicit `--harness claude-code` now requires `CLAUDE_CODE_SESSION_ID`, validates it through the existing session rules and sets an author actor. It never falls back to Codex identity, inherits no reviewer role, and still refuses operator verbs. Codex remains the default. Claude request markers use a separate prefix, so identical session strings do not consume each other's request.

Source verification: `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s verk/scripts -p 'test_*.py'` passed all 18 checks. These include real isolated-store lifecycles, missing identity, forbidden operator verbs, explicit Claude identity with a conflicting Codex environment, separate markers, mismatched Stop identities, and existing closeout regressions.

No installed/live claims are made. No permanent process or policy change was added. DOX pass: the skill entry documents the new invocation; repository ownership is unchanged.
