# Desktop integration boundaries

## Installed shape

The skill's source belongs in the shared skills repository. A symlink in `~/.agents/skills/verk` makes it discoverable as `$verk` in Codex desktop. The selected desktop execution environment also reads `~/.codex/skills`, so a compatibility symlink there points to the same source. There are no divergent copies. Codex follows symlinked skills and detects new skills; restart only if it does not appear. `agents/openai.yaml` supplies the picker label. Local skills are sufficient for this CLI workflow; no MCP server or published plugin is needed.

Examples: “Use $verk to show my work”, “Resume vk-123”, and “Checkpoint this contract with the remaining verification”. The skill uses CLI state and reports it in chat; it does not draw a persistent sidebar.

## Existing Verk adapters

Read `/Users/brooks/Code/verk/README.md` and `src/adapters/guidance.ts` for the maintained contract. `adapters/claude-code/hooks/verk.ts` is the existing Claude Code band/pane. Its hooks handle lease upkeep and enforce the edit guard; the visible mod is not the store.

`adapters/codex/hooks.json` and `src/adapters/codex.ts` are a bounded Codex CLI prototype, tested against the version recorded in that README. It does not establish desktop coverage. Its quoted shell commands can run as the operator because only plain-word commands are identity-rewritten. The skill wrapper avoids that dependency by explicitly setting the current Codex actor and session before calling the CLI. It grants no shell approval and installs no hooks.

Do not replace existing hook files or their trust settings. Hook installation requires reviewing the actual host's events and trusted-hook mechanism. Skill use alone does not provide automatic renewal, compaction checkpoints, footprint capture, a persistent pane, or guaranteed edit blocking.

## Explicit closeout and plugin follow-up

`scripts/closeout.py --repo <repo> --id <contract> --qualification <committed-record>` is the foreground closeout route. The record must separate diagnosis, source checks, installed identity/behavior, operator confirmations and limits before review. For source-only acceptance explicitly choose `--source-only` (and `--proof` when review-only). It uses the same session wrapper, runs missing approved checks, supports review-only code when checks are empty, reconciles and waits at most 60 seconds for a current-HEAD receipt. Pending and rejected reviews are distinct from receipt success. Review execution stays in Verk's independent on-demand reviewer, never in the author or a new service.

Plugin version 0.2.0 packages a Stop hook calling `closeout.py hook-stop`. It consumes only an explicit pending closeout for the current repository/session from `~/.cache/verk-closeout/`; it rechecks HEAD and cleanliness, reconciles once and reports the current result. It does not infer readiness from transcript prose or make ordinary unfinished tasks block a response. No request means no Verk call. Results in `.result.json` are disposable diagnostics, not task authority. A changed request, rejected review, missing executable or timeout is surfaced rather than converted to success.

Install/update the built plugin through the host's plugin mechanism. An update may refresh an active session, but the exact new hook definition still needs operator trust. Never write hook trust hashes or bypass trust. Test the installed handler with synthetic payloads first, then observe a real host Stop callback and its result on a later turn before claiming desktop hook qualification. If the host cannot load or trust it here, the foreground route remains usable and the hook qualification stays open.

A future Pi extension should consume the same public `verk … --json` output and supply a Pi session actor through an actual Pi adapter. Do not claim that this Codex wrapper supports Pi. Keep UI, policy, store and check production in their existing owners; do not recreate task truth in a panel.

## Authoritative references

- [Codex skill discovery and symlinks](https://developers.openai.com/codex/build-skills)
- [Plugin packaging and trusted lifecycle hooks](https://developers.openai.com/plugins/build/plugins)
- Local Verk source: `/Users/brooks/Code/verk/README.md`, `src/help.ts`, `src/public.ts`, `src/adapters/codex.ts`, and `src/producers/check.ts`.

When CLI behaviour differs from an example, use wrapper `help <verb>` and inspect the current Verk source. Do not revive decommissioned Beads commands.
