# T1 qualification: the skill wrapper never overwrites another principal (vk-2872)

Clauses that the Python tests do not prove, and how each is shown.

- **Branch and live checkout.** Branch `vk-2872` is cut from skills `origin/main` (`9d03cd9`) in the separate worktree `skills-wt/T1`. Nothing was written to `/Users/brooks/Code/skills`; its uncommitted work (vk-2870) was only read, to locate the moved `closeout.py:160` line.
- **`closeout.py:160`.** In this tree the `approved_awaiting_answer` line (159 here, 160 in the dirty live checkout) now says the operator's action comes from Verk's notice and the agent does not run `answer`. The two other "ask the operator" lines (`:151`, `:154-155`) are T11's.
- **Docs scope.** `verk/SKILL.md` and `verk/references/desktop.md` scope the wrapper to Codex desktop and the explicit Claude closeout, list the refusals, and say Pi and reviewer sessions run `verk` directly.
- **Marker set.** `CODEX_THREAD_ID`/`CODEX_SESSION_ID`, `CLAUDE_CODE_SESSION_ID`/`CLAUDECODE`, `PI_CODING_AGENT`/`PI_SESSION_ID`. M5 (desktop variable) is T6/T11's; they extend `HOST_VARIABLES` in `verk/scripts/verk.py`.
- **Check environment.** `setja` needs `node_modules`, which `run-skill-tests.py` never installs; `npm ci` was run in the scratch worktree (ignored by git) so all 18 suites run.
- **Limits.** Delivery to `origin/main` is the coordinator's; nothing was pushed or installed.
