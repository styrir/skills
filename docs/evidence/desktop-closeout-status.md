# Desktop closeout status: Claude Code and Codex

State at 2026-11-06T17:45Z, with the Codex plugin install updated at 20:37Z and Codex host observations from 2026-11-07. This summarizes the two host records and adds the Codex foreground outcome, which Codex's own record does not contain. Neither host is broadly qualified: each route below is shown only as far as its evidence goes.

- [Codex qualification](codex-desktop-closeout/qualification.md), in this repository
- Claude qualification: `docs/evidence/claude-code-desktop-closeout/qualification.md` in `plg-crk`, commit `03d2a7b`

**Superseded lines:** Codex's `qualification.md` and `final-assessment.json` still say foreground submission and review are NOT RUN. They describe the state before `vk-2628` was submitted; the tables below replace those entries.

## Outcome by host

| Case | Claude Code desktop | Codex desktop |
|---|---|---|
| Installed identity and hook dispatch | PASS: `verk-adapter claude-code stop`, plugin 0.1.1 | PASS: `closeout.py hook-stop`, plugin 0.2.6 |
| Stop with no request | PASS (narrow): one Stop recorded, nonblocking, no output | INCOMPLETE: host completion recorded, handler dispatch and output unobserved |
| Stop while a review is pending | PASS (narrow): three recorded Stops, silent and nonblocking | PASS (narrow): on a real review, counter reached 11 with the request retained; see the capture below |
| Unchanged-result callback limit | Not applicable: its native Stop does not block | PASS on a synthetic probe: ten blocks with host timestamps, then counter and result at 11 and host completion |
| Foreground closeout | PASS: `vk-2624`, one submission | PASS: `vk-2628`, one submission from the installed helper |
| Python marker follow-up | Unavailable: no consumer loaded, marker untouched by Stop | Read by the loaded hook. Source keeps the marker until a receipt, but settlement is unobserved: earlier markers were removed by manual cleanup, and the real one is still on disk |
| Interruption | NOT RUN: needs the operator to press Stop during a pending closeout | PASS on a synthetic probe only: stopped after four callbacks, and the one-to-two-callback target was missed. Not shown on a real pending closeout, so this is not the test Claude has yet to run |
| Positive reconciliation at Stop | Not observed | Not observed |
| Notice visibility in the app | UNOBSERVED | INCOMPLETE |

**Codex Stop capture, 17:29:07Z.** This record is the only committed copy; the files are live cache state and the next Stop is expected to change them. In `~/.cache/verk-closeout/01a1b1e6-b113-74d3-a6ea-33f0de73bf87.stops.json`, the counter read repeat 11 for `vk-2628` at `826ac1e`, on an unchanged result of `review_pending` for `vk-d281`, with no receipt in that result. The marker remained on disk. How many callbacks the host delivered was not counted from host events, so the counter is the evidence.

## Foreground stages

These are separate facts. The policy on both contracts is agent review with no approved checks, so there is no check admission to report.

| Stage | `vk-2624` (Claude) | `vk-2628` (Codex) |
|---|---|---|
| Reviewed revision | `010ee5d` | `826ac1e` |
| Independent review | `vk-d276` approved, after three refused tries | `vk-d281` approved |
| Automated gate | Approve, lowest clause 0.90 | **Reject**, lowest clause 0.42 |
| Check admission | None | None |
| Receipt | `vk-r145`, 15:49:17Z | `vk-r149`, 17:37:48Z |

**Gate disagreement on `vk-d281`:** the gate scored "A fresh actual desktop no-request baseline is recorded" at 0.42, the same gap Codex's record marks INCOMPLETE. The reviewer judged that the clause asks for a record, not proof of a handler no-op, and that a fresh no-request turn was recorded with its limit stated. Under this policy the reviewer decides, so the receipt stands, and it should not be read as evidence that the baseline handler ran.

The `vk-2624` refusal is recorded in the Claude qualification. Why the same revision passed on retry is not established.

## Other contracts

| Contract | Purpose | Review | Automated gate | Check admission | Receipt | Revision |
|---|---|---|---|---|---|---|
| `vk-2625` | Claude qualification result | `vk-d279` approved | Approve, lowest 0.94 | None | `vk-r147` | `03d2a7b` in `plg-crk` |
| `vk-2626` | Codex limit probe record | `vk-d280` approved | Approve, lowest 0.53 | None | `vk-r148` | `5d5eee3` |
| `vk-2627` | Stop telling readers to wait when no verdict is coming | `vk-d277` rejected at `65723cd`, then `vk-d278` approved | `vk-d277`: reject, lowest 0.27. `vk-d278`: approve, lowest 0.61 | None | `vk-r146` | `5d5eee3` |

- **`vk-d280`:** the 0.53 clause was "The implementation records real no-request Stop", the same no-request gap as `vk-d281`. That reviewer said a stricter reading of its clause would make the result a rejection.
- **`vk-d277` and `vk-d278`:** the lowest clause on both was "The closeout test suites pass". The tests ran only on the author's side, with no approved check to record them.
- **`vk-2626`:** it was submitted from a Claude session at the operator's instruction. All of its host evidence is Codex's own, and its record was not edited.

## Remaining limits

**Open work**

1. **The `vk-2627` wording itself is still unobserved in Codex, though its code now runs there.** The operator installed it at 20:23:55Z, after the session's permission system blocked the agent from doing so. The version still reads 0.2.6, so only the hashes tell the builds apart: cached `closeout.py` moved from `ec21b3bc` to `0140d345`. `vk-2635` then moved `codex_closeout.py` to `2046a205`, identical to source. The Stops below ran this code, but none of them reached a failed-reviewer result.
2. **Scope of the fix on Claude.** The foreground helper reads the source through a symlink, so it has the fix. Claude's native Stop is `verk-adapter`, not this helper, and whether it words these cases the same way is not established.
3. **Codex marker for session `01a1b1e6-b113-74d3-a6ea-33f0de73bf87` is settled.** The earlier expectation that the next Stop would settle it was wrong: Stop compared the recorded revision with the checkout's HEAD before it looked for a receipt, so it reported "Ready work changed; re-qualify" for finished work. `vk-2636` fixed that (`vk-r156`), moving cached `codex_closeout.py` to `b513c1b4`. At 07:10Z on 7 November a real turn in that session finished with no block, the request file was removed, a `.settled` file appeared, and `result.json` reads `receipt`, `vk-2628`, `vk-r149`. This is the first Codex Stop observed reporting a receipt. Its `systemMessage` is not in the rollout.
4. **Claude interruption.** It stays NOT RUN until the operator stops a turn during a fresh pending closeout.
5. **Positive Stop reconciliation.** Neither host has shown one. Both foreground receipts were issued when a review answered, not at an observed Stop. By source reading, not a host trace, Claude's `stopReconcile` skips contracts with an open review, and checkpoints with proof already reconcile at once, so ordinary work leaves it little to do.
6. **Publication.** Commits in `skills` and `plg-crk` are local. Codex's original captures in `plg-crk/docs/evidence/codex-desktop-closeout/` remain untracked; the archive in this repository is the committed copy.

**Evidence limits**

- **Codex trust:** a plugin update can silently stop the Stop hook. On 7 November, with `hooks/closeout.json` still `75577268` and the version and command unchanged, a real turn at 06:45Z finished without running the hook. The only signal was a Review hooks icon in the composer, listing the hook as Modified. After the operator allowed it, `trusted_content_hash` moved from `695b8f8a` to `c0111b5a` and `trusted_hash` stayed `7da9e6fd`. What that content hash covers is not established. The same happened after each of the two later installs on 7 November: the turn finished without the hook until the operator allowed it again. One approval, at 07:01Z, was given after the 06:55Z install and still left the hook Modified; why is not established. A further allow at 07:06Z, with `trusted_content_hash` at `2ad1a911`, was followed by the hook running at 07:10Z.
- **Codex Stop limit:** observed in a real host on 7 November, in session `01a1b1e6-b113-74d3-a6ea-33f0de73bf87`. Blocks arrived at 06:48:04Z, 06:48:11Z and 06:48:18Z with repeat 1, 2 and 3; the third carried the last-continuation text. The fourth Stop let the turn finish, with the result file at repeat 4. Its raw `systemMessage` is not in the rollout, so the fourth is inferred from the counter and the completed turn. The blocked result was a stale-work one, not a pending review.
- **Codex callback 11:** its raw `systemMessage` was never captured in the limit probe, and its nonblocking behaviour is inferred from the counter, result file and host completion.
- **Codex baseline:** the hook-specific no-op output is unobserved.
- **Codex synthetic probes:** the callback-limit and interruption results used synthetic contracts and revisions, with no real contract behind them. The real `vk-2628` session adds counter evidence for the limit only, and no Codex interruption of a real pending closeout is recorded.
- **Codex interruption account:** that it was a normal Stop press rests on the operator's statement, and the exact moment of the press is unobserved.
- **Codex record defects reported by `vk-d281`, not rechecked here:**
  - `final-assessment.json` holds a `qualification.md` hash that cannot match the file after `826ac1e`.
  - `archive-manifest.json` still claims byte-identical copies, although `interruption-probe.json` was amended afterward. That amendment is additive.
  - "Three unresolved callback replies" is not backed by the capture, whose `agent_finals` is empty.
- **Claude Stop results:** the record has no per-hook exit code, so success is inferred from an empty error list.
- **Claude handlers and adapter:** two Stop handlers are recorded only as `callback`, and the adapter's hash is not tied to a source commit.
- **Claude display:** what the app showed is unobserved, because the agent cannot see its own interface.
