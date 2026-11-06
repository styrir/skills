# Desktop closeout status: Claude Code and Codex

State at 2026-11-06T17:45Z. This summarizes the two host records and adds the Codex foreground outcome, which Codex's own record does not contain. Neither host is broadly qualified: each route below is shown only as far as its evidence goes.

- [Codex qualification](codex-desktop-closeout/qualification.md), in this repository
- Claude qualification: `docs/evidence/claude-code-desktop-closeout/qualification.md` in `plg-crk`, commit `03d2a7b`

**Superseded lines:** Codex's `qualification.md` and `final-assessment.json` still say foreground submission and review are NOT RUN. They describe the state before `vk-2628` was submitted; the tables below replace those entries.

## Outcome by host

| Case | Claude Code desktop | Codex desktop |
|---|---|---|
| Installed identity and hook dispatch | PASS: `verk-adapter claude-code stop`, plugin 0.1.1 | PASS: `closeout.py hook-stop`, plugin 0.2.6 |
| Stop with no request | PASS (narrow): one Stop recorded, nonblocking, no output | INCOMPLETE: host completion recorded, handler dispatch and output unobserved |
| Stop while a review is pending | PASS (narrow): three recorded Stops, silent and nonblocking | PASS (narrow): counter reached 11 with the request retained; see the capture below |
| Foreground closeout | PASS: `vk-2624`, one submission | PASS: `vk-2628`, one submission from the installed helper |
| Python marker follow-up | Unavailable: no consumer loaded, marker untouched by Stop | Read by the loaded hook; the marker stays until a receipt |
| Interruption | NOT RUN: needs the operator to press Stop during a pending closeout | PASS: stopped after four callbacks; the one-to-two-callback target was missed |
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
| `vk-2627` | Stop telling readers to wait when no verdict is coming | `vk-d277` rejected at `65723cd`, then `vk-d278` approved | `vk-d278`: approve, lowest 0.61 | None | `vk-r146` | `5d5eee3` |

- **`vk-d280`:** the 0.53 clause was "The implementation records real no-request Stop", the same no-request gap as `vk-d281`. That reviewer said a stricter reading of its clause would make the result a rejection.
- **`vk-d278`:** the 0.61 clause was "The closeout test suites pass". The tests ran only on the author's side, with no approved check to record them.
- **`vk-2626`:** it was submitted from a Claude session at the operator's instruction. All of its host evidence is Codex's own, and its record was not edited.

## Remaining limits

**Open work**

1. **Installed Codex plugin lacks the `vk-2627` fix.** Plugin 0.2.6 still has `closeout.py` starting `ec21b3bc`, so its Stop can still say to wait on a review that has no verdict coming. The session's permission system blocked the install. A side-effect-free build from current source differs in five files, all from `vk-2627`, and `hooks/closeout.json` is byte-identical. The fixed path has not been observed in a Codex host.
2. **Scope of the fix on Claude.** The foreground helper reads the source through a symlink, so it has the fix. Claude's native Stop is `verk-adapter`, not this helper, and whether it words these cases the same way is not established.
3. **Codex marker for session `01a1b1e6-b113-74d3-a6ea-33f0de73bf87`.** At this writing it remains on disk, after the review it was waiting on already reached a receipt. That session's next Stop is expected to settle it, which would also be the first Codex Stop observed reporting a receipt.
4. **Claude interruption.** It stays NOT RUN until the operator stops a turn during a fresh pending closeout.
5. **Positive Stop reconciliation.** Neither host has shown one. Both foreground receipts were issued when a review answered, not at an observed Stop. On Claude, `stopReconcile` skips contracts with an open review, and checkpoints with proof already reconcile at once, so ordinary work leaves it little to do.
6. **Publication.** Commits in `skills` and `plg-crk` are local. Codex's original captures in `plg-crk/docs/evidence/codex-desktop-closeout/` remain untracked; the archive in this repository is the committed copy.

**Evidence limits**

- **Codex trust:** values were read from persisted settings only. They are not proof of current trust validation, and the trust UI was not inspected. A byte-identical hook file suggests an install would not change trust, but that has not been tested.
- **Codex callback 11:** its raw `systemMessage` was never captured in the limit probe, and its nonblocking behaviour is inferred from the counter, result file and host completion.
- **Codex baseline:** the hook-specific no-op output is unobserved.
- **Codex interruption timing:** the exact moment the operator pressed Stop is unobserved.
- **Claude Stop results:** the record has no per-hook exit code, so success is inferred from an empty error list.
- **Claude handlers and adapter:** two Stop handlers are recorded only as `callback`, and the adapter's hash is not tied to a source commit.
- **Claude display:** what the app showed is unobserved, because the agent cannot see its own interface.
