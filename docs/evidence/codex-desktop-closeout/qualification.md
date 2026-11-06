# Codex desktop Verk closeout qualification

Status: **INCOMPLETE**. Actual desktop route only; no CLI substitute used. No acceptance, installation, publication, trust changes, reviewer calls or check production performed.

| Item | Status | Observed record |
|---|---|---|
| Identity | PASS | ChatGPT.app bundle com.openai.codex, 26.1029.61003 build 24614; Codex Framework 156.0.8078.79 build 8078.79; Codex Desktop originator, local vscode source, runtime 0.166.0-alpha.6; model gpt-6.1-sol, medium reasoning. Session `01a1b187-17a0-7981-86ef-1afd7f2f72c5` from both host identity variables and session metadata. Repository `~/Code/skills`; Verk store `~/.verk`. |
| UTC bounds | PASS | Preflight began 2026-11-06T15:43:25Z. Probe prepared 16:01:52.402922Z; callback 11 result written 16:03:01.102003Z; host completed 16:03:05.059Z, 72.656 seconds after preparation. Evidence captured and cleanup performed 2026-11-06T16:05:14.125039+00:00. |
| Dispatch/trust | PASS (probe dispatch) | Actual host HookPrompt events identify loaded installed hook `stop:53:~/.codex/plugins/cache/brooks-local/verk/0.2.6/hooks/closeout.json`; ten callbacks delivered without a foreground handler invocation. Installed command: `python3 "${PLUGIN_ROOT}/skills/verk/scripts/closeout.py" hook-stop`. Persisted trust recorded below; execution observed, trust UI not inspected. Baseline-specific dispatch remains UNOBSERVED. |
| No-request | INCOMPLETE | One ordinary turn ended without explicit closeout request. Session marker/counter/result absent before and after. Host Stop phase observed; specific handler no-op result unobserved. No closeout work requested. |
| Limit | PASS | Request `desktop-probe-74b54c5b8a1d481db93006a0bf8fedcc` at `~/.cache/verk-closeout/01a1b187-17a0-7981-86ef-1afd7f2f72c5.json`, synthetic contract `vk-desktop-probe`, revision `synthetic-desktop-probe-revision`. Callback counts 1–10 blocked on unchanged checkout_missing; result/counter reached 11, followed by host task_complete without another continuation. Marker retained through capture; no receipt. Preparation-to-callback-11 elapsed 68.699 seconds, within ten continuations/five minutes. Existing recovery directory unset, delegation false; no real contract backs this probe. See [captured evidence](limit-probe.json). |
| Visibility | INCOMPLETE | Final agent message at 16:03:00.944Z: "The diagnostic probe remains unresolved. Nothing was accepted." Host completed at 16:03:05.059Z; current user message proves messaging resumed afterward. Computer Use denied app access, so screenshot and unresolved systemMessage UI visibility unobserved; raw callback-11 systemMessage not found in inspected rollout/logs. No operator confirmation asserted. |
| Interruption | PASS (cancellation); FAIL (requested timing) | Fresh session `01a1b1bf-e0c4-7e30-b8e1-62425bf76cf7` was interrupted after four actual callbacks, with three unresolved replies. Matching request retained, counter/result 4, no receipt; captured then cleaned under installed lock. See fresh-session record below. |
| Foreground route | NOT RUN | No legitimate documentation closeout submitted. Tracking contract vk-2626 has no acceptance receipt claimed. |
| Cleanup | PASS | Captured request, result and counter with hashes before deletion in limit-probe.json. Under installed request_lock, verified matching request ID, result ID, counter contract/revision and repeat 11, then removed only `01a1b187-17a0-7981-86ef-1afd7f2f72c5.json`, `.result.json`, `.stops.json` from `~/.cache/verk-closeout/`. Verified absent while locked. Existing `.lock` retained. No replacement request encountered; unrelated files/state and missing checkout untouched. This withdraws a synthetic probe and completes no contract. |

Installed plugin root: `~/.codex/plugins/cache/brooks-local/verk/0.2.6`.

- `skills/verk/scripts/closeout.py`: `ec21b3bc6cc9b55a64d94d2219350f85590ed86ef9a11ae04c31ff8ef289ccb6`
- `skills/verk/scripts/codex_closeout.py`: `7252c0065b9393f9fcd4449965bb4a51dbf11a83137f1d6c11c809907f49d55d`
- `hooks/closeout.json`: `75577268887c3767ec0969cde0bc5a609808fd4fcc5c4b7991868975e9f6185f`

Installed Python helper hashes match foreground `~/Code/skills/verk/scripts/` copies and handoff recorded prefixes. Hook definition matches handoff recorded prefix; foreground source hook definition not yet located. No refresh performed.

Persisted trust at `verk@brooks-local:hooks/closeout.json:stop:0:0`: definition `sha256:7da9e6fd0d2d977587134acb2eb28efa5fdb9ce8d33efcb93de5598a4f036362`; content `sha256:695b8f8a818711aca69aa39faecca46f25cdd8e5f5c85989a466eb3a3e9dfe61`. These are recorded values, not proof of current trust validation.

Budget: one probe, at most ten continued model turns or five minutes from probe preparation, whichever comes first. Continuations only report unresolved; no checks, repair, marker rewrites or polling loops. Expected unchanged callbacks 1–10 block, callback 11 becomes nonblocking with request retained. Actual callback evidence captured below and in limit-probe.json. Full desktop qualification remains INCOMPLETE because the no-request handler result, UI notice visibility, interruption and legitimate foreground route are not established.

[Official OpenAI hook guidance](https://learn.chatgpt.com/docs/hooks) was read; it distinguishes configured hooks from trusted executable hooks and describes Stop continuation output. User handoff governs this bounded test.

## Actual host callback sequence

| Callback | UTC, 6 November 2026 | Outcome |
|---|---|---|
| 1 | 2026-11-06T16:02:00.371Z | Blocked; unchanged checkout_missing |
| 2 | 2026-11-06T16:02:06.421Z | Blocked; unchanged checkout_missing |
| 3 | 2026-11-06T16:02:13.541Z | Blocked; unchanged checkout_missing |
| 4 | 2026-11-06T16:02:19.668Z | Blocked; unchanged checkout_missing |
| 5 | 2026-11-06T16:02:26.218Z | Blocked; unchanged checkout_missing |
| 6 | 2026-11-06T16:02:32.982Z | Blocked; unchanged checkout_missing |
| 7 | 2026-11-06T16:02:40.291Z | Blocked; unchanged checkout_missing |
| 8 | 2026-11-06T16:02:46.259Z | Blocked; unchanged checkout_missing |
| 9 | 2026-11-06T16:02:52.981Z | Blocked; unchanged checkout_missing |
| 10 | 2026-11-06T16:02:59.026Z | Blocked; unchanged checkout_missing |
| 11 | 2026-11-06T16:03:01.102003Z (result-file mtime) | Result and counter repeat 11; nonblocking behavior corroborated by host completion at 16:03:05.059Z. Raw systemMessage output/UI visibility unobserved. |

The hook run ID is shared across callbacks; separate callback identity comes from host HookPrompt event timestamps, counts and rollout ordinals in the evidence JSON. Callback 11 behavior is inferred from the host completion plus actual result/counter files, rather than from a captured raw output event. No handler was rerun to manufacture that output. No receipt or acceptance was produced.


## Fresh-session interruption — 6 November 2026

Task `vk-2628`; prior `vk-2626` lease and limit probe were preserved. This addendum records actual local desktop behavior; no subprocess handler invocation, delegate substitute, plugin refresh, trust edit, policy change, reviewer/check production, installation, publication or acceptance occurred.

| Case | Status | Evidence |
|---|---|---|
| Identity | PASS | Actual host identity variables and rollout identify `01a1b1bf-e0c4-7e30-b8e1-62425bf76cf7`, Codex Desktop/local vscode runtime 0.166.0-alpha.6, model gpt-6.1-sol medium, cwd `~/Code/skills`, store `~/.verk`. App/framework builds match prior record. Preflight began 16:45 UTC. |
| Installed dispatch | PASS (probe) | Four real HookPrompt events name installed `stop:53:~/.codex/plugins/cache/brooks-local/verk/0.2.6/hooks/closeout.json`. Installed hashes match prior limit record. Persisted plugin enabled/trust values were read; trust UI was not inspected. |
| Source drift | PASS (recorded) | Installed closeout.py remains `ec21b3bc6cc9b55a64d94d2219350f85590ed86ef9a11ae04c31ff8ef289ccb6`; current source foreground copy at preflight was `bdf0521ad78d2ad4c7c10b706655971c7f3002f07675922c002c1639db5cc17f`. codex_closeout.py matched. No refresh; source-copy changes are not qualified by this installed test. |
| No-request baseline | INCOMPLETE | Marker/result/counter/settled/lock absent initially; marker/result/counter still absent on next turn. Host task_complete at 16:46:14.400 UTC (ordinal 68) followed the normal unarmed turn. Specific handler dispatch/output UNOBSERVED in inspected rollout; host completion alone does not establish hook no-op. |
| Explicit arm | PASS | Operator sent “start interruption probe”. Installed helper state_path/request_lock/schema used to create only request `desktop-interruption-2e7002fad1d7416e8c83d232a3851de0` at `~/.cache/verk-closeout/01a1b1bf-e0c4-7e30-b8e1-62425bf76cf7.json`. Synthetic missing directory, contract `vk-desktop-interruption-probe`, synthetic revision; no real contract or receipt; delegation false and recovery directory unset. |
| Cancellation | PASS | Four callback events at 17:08:21.789, 17:08:28.734, 17:08:35.119 and 17:08:41.315 UTC; three unresolved callback replies. Host turn_aborted at 17:08:41.416 UTC, reason `interrupted`, turn `01a1b1d4-ae5e-7a10-a5e8-0208573e60af`; no fourth reply. Parent relayed operator “Done” and interrupted thread state. Subsequent message resumed evidence capture. |
| Requested cancellation timing | FAIL | Intended one or two callbacks; actual four. Cancellation effectiveness is observed at four only. No re-arm or rerun. |
| Retention / no receipt | PASS | Matching marker remained through capture; result checkout_missing, needs_action, repeat 4; counter 4. No receipt in result and no real contract behind request. No acceptance inferred from cancellation. |
| Cleanup | PASS | Captured hashes, mtimes and contents before deletion. Under same installed request_lock validated matching request/result IDs and counter contract/revision, then removed only own .json/.result.json/.stops.json. Verified absence while locked, retained .lock; no replacement encountered. Missing directory and unrelated state untouched. |
| UI visibility | INCOMPLETE | No screenshot or direct notice-visibility confirmation. Parent’s relayed “Done” establishes neither notice visibility nor exact timing. Prior Computer Use denial remains a coverage limit. |
| Legitimate foreground route | NOT RUN | No legitimate closeout was submitted. Qualification artifacts remain uncommitted in `plg-crk`, whose unrelated untracked work remains preserved; tracking contract belongs to `skills`. This supplies no committed clean same-repository qualification for a foreground submission. No publication, approval or acceptance authorized; no surrogate task/verdict/receipt manufactured to fill the gap. |

Evidence: [unarmed preflight](interruption-preflight.json) and [interruption capture](interruption-probe.json). The earlier [limit probe](limit-probe.json) remains byte-identical. Independent review, verdict, automated gate, check admission and receipt were **NOT RUN** for this synthetic probe. Overall desktop qualification remains **INCOMPLETE**. Records are uncommitted; no completed contract or receipt is claimed.


## Committed-proof continuation — 6 November 2026

This archive in the owning `skills` repository resolves the earlier cross-repository, uncommitted-proof gap. The four prior artifacts were copied from `plg-crk/docs/evidence/codex-desktop-closeout/`; source artifacts and unrelated files remain untouched. Historical uncommitted/not-run statements above describe their capture stage. This continuation supersedes that proof-location limitation, not the remaining behavioral gaps.

| Case | Status | Current boundary |
|---|---|---|
| Committed proof preparation | PASS | Redacted qualification plus original JSON captures archived together; source capture hashes in archive-manifest.json. JSON parsing, callback/cancellation consistency and git diff --check verified before local commit. No publication. |
| Baseline handler dispatch | INCOMPLETE | Inspected actual session rollout and desktop log around baseline completion at 16:46:14.400 UTC. Host completion and hooks/list RPCs are present; no hook-specific no-op result was found. The later unarmed completion at 17:10:17.429 UTC also does not establish handler dispatch. No logging/trust changes or manual handler invocation used to fill the gap. |
| Notice visibility | INCOMPLETE | Operator observation requested separately; no new visibility confirmation available at preparation. Official hooks documentation says systemMessage can appear in UI or event stream; this is a specified capability, not proof of visibility in this run. |
| Foreground submission | NOT RUN | Installed foreground closeout calls checkpoint and reconcile, which can turn evidence into receipts; it has no submit-without-receipt option. User explicitly excludes acceptance. Work remains behaviorally incomplete, so it is not declared ready or submitted as accepted. Use only pure current-revision observe under this authority; it cannot establish a submission/request lifecycle. |
| Independent review / verdict / gate / admission / receipt | NOT RUN | No new evidence-producing or reconciliation operation authorized under the no-acceptance boundary. No delegation recorded and no synthetic substitute manufactured. |

Owning tracking contract remains `vk-2628`, policy version 1, kind-version 1, review yolo, checks empty as read before this continuation. Policy was not changed. A future legitimate foreground submission requires ready committed scope and authority for normal reconciliation consequences. The archive itself is local proof, not a receipt or full desktop acceptance.

[Official OpenAI hook documentation](https://learn.chatgpt.com/docs/hooks) was consulted for Stop/Interrupt/systemMessage semantics; actual observations retain precedence. Overall desktop qualification remains **INCOMPLETE**. No new probe was armed or rerun.
